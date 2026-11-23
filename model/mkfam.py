#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""mkfam.py PFX OUT.pkl LAYER [op|op2|pack] [--bin NAME] [--simdir DIR]: a "smaller handler set" estimate.

For code made of many specialised variants of the same routine (interpreter handlers, stubs, generated templates)
whose symbols are named "<family> <variant...>" (e.g. perf-map names "op:add int32", "op:add double"): every symbol of
LAYER is mapped line by line onto its family's hottest variant (k-th line -> k-th line of the representative,
wrapped), i.e. the instruction-supply cost as if one shared routine served the family.  The extra work a generic
routine would do is NOT modelled: an upper bound of the supply gain.
  op    family = the first whitespace-separated token of the symbol
  op2   family = the first two tokens
  pack  op aliasing AND the representatives packed by heat from a fresh 1 MB-aligned base
Other code keeps its addresses.  Use with SIM_LAYOUT=OUT.pkl sim.py ..."""
import sys, os, glob, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R


def opt(a, k, d=None):
    if k in a:
        i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
    return d


a = sys.argv[1:]
binname = opt(a, '--bin'); simdir = opt(a, '--simdir')
pfx, out, layer = a[0], a[1], a[2]
mode = a[3] if len(a) > 3 else 'op'
meta = pickle.load(open(pfx + '.dec.pkl', 'rb')); res = R.Resolver(pfx, binname)
heat = collections.Counter(); lines = collections.defaultdict(set)
for p in glob.glob('%s.w*.sim.pkl' % (os.path.join(simdir, os.path.basename(pfx)) if simdir else pfx)):
    r = pickle.load(open(p, 'rb'))
    for iid, n in r['execs'].items():
        ad = meta['addr'][iid]; L, name = res.resolve(ad, meta['syms'][iid])
        if L != layer: continue
        d = meta['dec'].get(iid); sz = d['size'] if d else 16
        heat[name] += n
        for ln in range(ad >> 8, ((ad + sz - 1) >> 8) + 1): lines[name].add(ln)


def fam(n):
    t = n.split()
    return ' '.join(t[:2]) if mode == 'op2' else t[0]


rep = {}
for n, h in heat.most_common():
    rep.setdefault(fam(n), n)
m = {}
if mode == 'pack':
    nxt = (0x30000000 >> 8)
    for f, n in sorted(rep.items(), key=lambda kv: -heat[kv[1]]):
        for ln in sorted(lines[n]): m[ln] = nxt; nxt += 1
for n in heat:
    r_ = rep[fam(n)]; rl = sorted(lines[r_]); ol = sorted(lines[n])
    for k, ln in enumerate(ol):
        t = rl[k % len(rl)]
        m[ln] = m.get(t, t) if n != r_ else m.get(ln, ln)
pickle.dump(m, open(out, 'wb'))
hk = sum(len(lines[n]) for n in heat) * 256 / 1024; rk = sum(len(lines[n]) for n in rep.values()) * 256 / 1024
print('%s: %d hot variants (%.0f KB) -> %d families (%.0f KB)' % (mode, len(heat), hk, len(rep), rk))
