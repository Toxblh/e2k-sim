#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""report.py [--top N] [--bin NAME] [--diff OTHER_PFX [--bin2 NAME]] PFX [windows...]

Aggregates sim.py results (PFX.w<N>.sim.pkl) per symbol and per layer and prints fixed-width tables:
where the cycles go (layer, symbol), what they are (issue vs stall causes) and why (the dominant cause).

Symbols come from
  - the main binary NAME (--bin, default: the basename of PFX up to the first '-'): SYMS/NAME.nm,
  - shared libraries mapped in PFX.maps: SYMS/<lib basename>.nm,
  - a perf map of JIT code (PFX.perfmap, "start size name" lines, the format of /tmp/perf-<pid>.map),
  - anonymous executable mappings (named anon@page).
SYMS is $SIM_SYMS or <dir of PFX>/syms; the .nm files are `nm` output (`nm -l` adds the source file after a tab,
which the src rules below can use).  scripts/mksyms.sh makes them.

Layers: main (main binary), lib (shared libraries), jit (perf map and anonymous code), other.
$SIM_LAYERS names a rules file to split them further, first match wins, one rule per line:
  perf PREFIX LAYER   perf-map symbols starting with PREFIX
  sym  REGEX  LAYER   main-binary or library symbols matching REGEX (re.search)
  src  SUBSTR LAYER   main-binary symbols whose `nm -l` source path contains SUBSTR
  lib  SUBSTR LAYER   shared libraries whose basename contains SUBSTR
--diff OTHER_PFX: per-symbol cycles per 1000 wide instructions of both runs, sorted by the change.
"""
import sys, os, glob, pickle, bisect, collections, re

RAW = os.environ.get('SIM_RAWSYM') == '1'
CAUSES = ('issue', 'nop', 'dep', 'L2', 'L3', 'DRAM', 'stld', 'dtlb', 'ctprep', 'ibranch', 'icache', 'call', 'spill', 'itarget', 'itlb')
WHY = {'issue': 'width', 'nop': 'nops', 'dep': 'latency', 'L2': 'cache', 'L3': 'cache', 'DRAM': 'memory',
       'stld': 'st->ld', 'dtlb': 'tlb', 'ctprep': 'ct-prep', 'ibranch': 'branch', 'icache': 'fetch', 'call': 'call',
       'spill': 'spill', 'itarget': 'target', 'itlb': 'itlb'}


def syms_dir(pfx):
    return os.environ.get('SIM_SYMS') or os.path.join(os.path.dirname(os.path.abspath(pfx)), 'syms')


def default_bin(pfx):
    return os.path.basename(pfx).split('-')[0].split('.')[0]


def load_rules():
    rules = []
    fn = os.environ.get('SIM_LAYERS')
    if fn:
        for l in open(fn):
            f = l.split()
            if len(f) == 3 and not l.startswith('#'):
                rules.append((f[0], f[1], f[2]))
    return rules


class NmTable:
    def __init__(self, path, base=0):
        rows = []
        for l in open(path):
            f = l.rstrip('\n').split('\t')
            p = f[0].split()
            if len(p) < 3 or p[1] not in 'TtWw': continue
            try: a = int(p[0], 16)
            except ValueError: continue
            if a == 0: continue                  # undefined-address markers (weak symbols at 0)
            src = f[1] if len(f) > 1 else ''
            rows.append((a, p[2], src))
        rows.sort()
        self.base = base
        self.a = [r[0] for r in rows]; self.r = rows

    def lowest(self):
        return self.a[0] if self.a else 0

    def find(self, x):
        i = bisect.bisect_right(self.a, x - self.base) - 1
        return self.r[i] if i >= 0 else None


def demangle_short(s):
    m = re.match(r'_ZN(?:K?)((?:\d+\w+?)+)E', s)
    if not m: return s
    out, rest = [], m.group(1)
    while rest:
        mm = re.match(r'(\d+)', rest)
        if not mm: break
        n = int(mm.group(1)); rest = rest[len(mm.group(1)):]
        out.append(rest[:n]); rest = rest[n:]
    return '::'.join(out) if out else s


class Resolver:
    def __init__(self, pfx, binname=None):
        sd = syms_dir(pfx)
        binname = binname or default_bin(pfx)
        self.rules = load_rules()
        mf = '%s/%s.nm' % (sd, binname)
        self.main = NmTable(mf) if os.path.exists(mf) else None
        self.mainr = []       # (lo, hi) of the main binary's mappings
        self.libs = []        # (lo, hi, name, NmTable|None)
        self.anon = []
        mp = pfx + '.maps'
        if os.path.exists(mp):
            first = {}
            for l in open(mp):
                f = l.split()
                lo, hi = [int(x, 16) for x in f[0].split('-')]
                path = f[5] if len(f) > 5 else ''
                off = int(f[2], 16)
                b = os.path.basename(path)
                if path and path not in first: first[path] = lo - off   # load base (keyed by path: in user mode the
                if b == binname:                                         # host's own libraries are mapped too)
                    self.mainr.append((lo, hi))
                    if self.main is not None and self.main.lowest() < first[path]:
                        self.main.base = first[path]       # PIE: nm addresses are relative to the load base
                elif '.so' in b:
                    nmf = '%s/%s.nm' % (sd, b)
                    t = NmTable(nmf, first[path]) if os.path.exists(nmf) else None
                    self.libs.append((lo, hi, b, t))
                elif 'x' in f[1] and not path:
                    self.anon.append((lo, hi))
        self.perf = []
        pm = pfx + '.perfmap'
        if os.path.exists(pm):
            for l in open(pm):
                f = l.split(None, 2)
                if len(f) == 3:
                    self.perf.append((int(f[0], 16), int(f[1], 16), f[2].strip()))
        self.perf.sort(); self.pa = [p[0] for p in self.perf]
        self.cache = {}

    def rule(self, kind, text, default):
        for k, pat, layer in self.rules:
            if k != kind and not (k == 'sym' and kind in ('symmain', 'symlib')): continue
            if k == 'perf' and text.startswith(pat): return layer
            if k == 'sym' and re.search(pat, text): return layer
            if k in ('src', 'lib') and pat in text: return layer
        return default

    def resolve(self, a, qsym=None):
        if a in self.cache: return self.cache[a]
        r = self._resolve(a, qsym); self.cache[a] = r
        return r

    def _resolve(self, a, qsym):
        i = bisect.bisect_right(self.pa, a) - 1
        if i >= 0 and a < self.perf[i][0] + self.perf[i][1]:
            n = self.perf[i][2]
            return self.rule('perf', n, 'jit'), n[:60]
        in_main = any(lo <= a < hi for lo, hi in self.mainr) if self.mainr else True
        if in_main and self.main is not None:
            e = self.main.find(a)
            if e:
                name, src = e[1], e[2]
                layer = self.rule('src', src, None) if src else None
                layer = layer or self.rule('symmain', name, 'main')
                return layer, (name if RAW else demangle_short(name))[:60]
        for lo, hi, b, t in self.libs:
            if lo <= a < hi:
                e = t.find(a) if t else None
                name = '%s:%s' % (b.split('.so')[0], e[1] if e else hex(a))
                layer = self.rule('lib', b, None) or self.rule('symlib', name, 'lib')
                return layer, name[:60]
        for lo, hi in self.anon:
            if lo <= a < hi:
                return 'jit', 'anon@%x' % (a & ~0xfff)
        if qsym and qsym != '-':
            return ('main' if in_main and self.mainr else 'other'), qsym[:60]
        return 'other', 'code@%x' % (a & ~0xffff)


def load_runs(pfx, wins=None, simdir=None):
    meta = pickle.load(open(pfx + '.dec.pkl', 'rb'))
    rs = []
    base = os.path.join(simdir, os.path.basename(pfx)) if simdir else pfx
    for p in sorted(glob.glob(base + '.w*.sim.pkl')):
        w = int(re.search(r'\.w(\d+)\.sim\.pkl$', p).group(1))
        if wins and w not in wins: continue
        rs.append(pickle.load(open(p, 'rb')))
    return meta, rs


def aggregate(pfx, binname=None, wins=None, simdir=None):
    meta, rs = load_runs(pfx, wins, simdir)
    res = Resolver(pfx, binname)
    by = collections.defaultdict(lambda: [0] * len(CAUSES))
    ins = collections.Counter()
    ninsn = 0
    for r in rs:
        ninsn += r['ninsn'] - r['warm']
        for iid, a in r['acc'].items():
            key = res.resolve(meta['addr'][iid], meta['syms'][iid])
            v = by[key]
            for c in range(len(CAUSES)): v[c] += a[c]
            ins[key] += r['execs'][iid]
    return by, ins, ninsn


def why_of(v):
    s = sum(v)
    st = sorted(((v[c], CAUSES[c]) for c in range(1, len(CAUSES)) if v[c]), reverse=True)
    return WHY[st[0][1]] if st and st[0][0] > 0.15 * s else 'width'


def table(by, ins, ninsn, top):
    tot = sum(sum(v) for v in by.values())
    out = []
    out.append('window: %d wide instructions counted, %d model cycles, IPC %.3f' % (ninsn, tot, ninsn / max(tot, 1)))
    lay = collections.defaultdict(lambda: [0] * len(CAUSES))
    for (l, n), v in by.items():
        for c in range(len(CAUSES)): lay[l][c] += v[c]
    out.append('%-10s %6s %6s %6s  %s' % ('layer', 'cyc%', 'issue%', 'stall%', 'stall causes (% of layer cycles)'))
    for l, v in sorted(lay.items(), key=lambda kv: -sum(kv[1])):
        s = sum(v)
        st = sorted(((v[c], CAUSES[c]) for c in range(1, len(CAUSES)) if v[c]), reverse=True)[:4]
        out.append('%-10s %6.1f %6.1f %6.1f  %s' % (l, 100.0 * s / tot, 100.0 * v[0] / s, 100.0 * (s - v[0]) / s,
                                                    ' '.join('%s:%.0f' % (n, 100.0 * x / s) for x, n in st)))
    for l, _ in sorted(lay.items(), key=lambda kv: -sum(kv[1])):
        rows = sorted(((sum(v), k, v) for k, v in by.items() if k[0] == l), reverse=True)[:top]
        if not rows: continue
        out.append('')
        out.append('-- %s: top %d' % (l, len(rows)))
        out.append('%4s %6s %10s %9s %5s %6s %6s  %-26s %-8s %s' % ('#', 'cyc%', 'cycles', 'insns', 'IPC', 'issue%', 'stall%',
                                                                  'top stalls (% of row)', 'why', 'symbol'))
        for i, (s, k, v) in enumerate(rows):
            st = sorted(((v[c], CAUSES[c]) for c in range(1, len(CAUSES)) if v[c]), reverse=True)[:3]
            out.append('%4d %6.2f %10d %9d %5.2f %6.1f %6.1f  %-26s %-8s %s' % (
                i + 1, 100.0 * s / tot, s, ins[k], ins[k] / max(s, 1), 100.0 * v[0] / s, 100.0 * (s - v[0]) / s,
                ' '.join('%s:%.0f' % (n, 100.0 * x / s) for x, n in st), why_of(v), k[1]))
    return '\n'.join(out)


def diff(a, b, top):
    (ba, ia, na), (bb, ib, nb) = a, b
    keys = set(ba) | set(bb)
    rows = []
    for k in keys:
        ca = sum(ba.get(k, [0])) * 1000.0 / max(na, 1); cb = sum(bb.get(k, [0])) * 1000.0 / max(nb, 1)
        rows.append((cb - ca, ca, cb, k))
    rows.sort(key=lambda r: -abs(r[0]))
    ta = sum(sum(v) for v in ba.values()) * 1000.0 / max(na, 1); tb = sum(sum(v) for v in bb.values()) * 1000.0 / max(nb, 1)
    out = ['diff: cycles per 1000 wide instructions  A %.1f  B %.1f  (%+.1f%%)' % (ta, tb, 100 * (tb / ta - 1)),
           '%9s %9s %9s  %-10s %s' % ('A', 'B', 'B-A', 'layer', 'symbol')]
    for d, ca, cb, k in rows[:top]:
        out.append('%9.2f %9.2f %+9.2f  %-10s %s' % (ca, cb, d, k[0], k[1]))
    return '\n'.join(out)


def main():
    a = sys.argv[1:]
    top = 15
    if '--top' in a:
        i = a.index('--top'); top = int(a[i + 1]); del a[i:i + 2]
    binname = None
    if '--bin' in a:
        i = a.index('--bin'); binname = a[i + 1]; del a[i:i + 2]
    bin2 = None
    if '--bin2' in a:
        i = a.index('--bin2'); bin2 = a[i + 1]; del a[i:i + 2]
    other = None
    if '--diff' in a:
        i = a.index('--diff'); other = a[i + 1]; del a[i:i + 2]
    if not a:
        print(__doc__); sys.exit(1)
    pfx = a[0]
    wins = set(int(x) for x in a[1:]) if len(a) > 1 else None
    A = aggregate(pfx, binname, wins)
    if other:
        print(diff(A, aggregate(other, bin2 or binname, wins), top))
    else:
        print(table(*A, top))


if __name__ == '__main__':
    main()
