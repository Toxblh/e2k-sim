#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""supply.py [--top N] [--bin NAME] PFX... : instruction-supply cost (G cycles, whole run) per layer and top symbols,
the hot code footprint per layer (KB of 256 B lines and 4 KB pages holding 90 % of the executions).
supply = itarget (taken target missing L1I) + itlb (taken target page missing the ITLB) + icache (sequential misses)
       + ctprep (ct sooner than 5 commands after its disp/movtd/return) + ibranch (unprepared taken ibranch, 6 each)."""
import sys, os, glob, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R

SUP = ('itarget', 'itlb', 'icache', 'ctprep', 'ibranch')


def run(pfx, binname=None, top=10):
    meta = pickle.load(open(pfx + '.dec.pkl', 'rb'))
    res = R.Resolver(pfx, binname)
    tot = None
    for l in open(pfx + '.info'):
        if l.startswith('total_insns'): tot = int(l.split()[1])
    acc = collections.defaultdict(lambda: [0.0] * len(R.CAUSES)); ex = collections.Counter(); n = 0
    for p in glob.glob(pfx + '.w*.sim.pkl'):
        r = pickle.load(open(p, 'rb')); n += r['ninsn'] - r['warm']
        for iid, v in r['acc'].items():
            a_ = acc[iid]
            for c in range(len(v)): a_[c] += v[c]
            ex[iid] += r['execs'][iid]
    k = tot / max(n, 1)
    ci = {c: i for i, c in enumerate(R.CAUSES)}
    lay = collections.defaultdict(collections.Counter); sym = collections.defaultdict(collections.Counter)
    hot = collections.defaultdict(list)
    allc = 0.0
    for iid, v in acc.items():
        L, name = res.resolve(meta['addr'][iid], meta['syms'][iid])
        s = sum(v) * k; allc += s
        lay[L]['all'] += s; sym[(L, name)]['all'] += s
        for c in SUP:
            lay[L][c] += v[ci[c]] * k; sym[(L, name)][c] += v[ci[c]] * k
        d_ = meta['dec'].get(iid)
        hot[L].append((ex[iid], d_['size'] if d_ else 16, meta['addr'][iid]))
    sup = sum(lay[L][c] for L in lay for c in SUP)
    out = ['== %s: %.3f G cycles (model), instruction supply %.3f G = %.0f %%' % (
        os.path.basename(pfx), allc / 1e9, sup / 1e9, 100 * sup / max(allc, 1))]
    out.append('  %-10s %7s %7s | %6s %6s %6s %6s %6s | %8s %8s' % ('layer', 'G cyc', 'supply', 'target', 'itlb', 'seq', 'ctprep', 'ibr', 'hot90 KB', 'pages'))
    for L, c in sorted(lay.items(), key=lambda kv: -kv[1]['all']):
        h = sorted(hot[L], reverse=True); te = sum(x[0] for x in h); acc_ = 0; lines = set(); pages = set()
        for e, sz, ad in h:
            if acc_ >= 0.9 * te: break
            acc_ += e; lines.add(ad >> 8); pages.add(ad >> 12)
        s = sum(c[x] for x in SUP)
        out.append('  %-10s %7.3f %7.3f | %6.3f %6.3f %6.3f %6.3f %6.3f | %8.0f %8d' % (
            L, c['all'] / 1e9, s / 1e9, c['itarget'] / 1e9, c['itlb'] / 1e9, c['icache'] / 1e9, c['ctprep'] / 1e9,
            c['ibranch'] / 1e9, len(lines) * 256 / 1024, len(pages)))
    out.append('  top symbols by supply cost (G):  %6s %6s %6s %6s %6s' % SUP)
    for (L, name), c in sorted(sym.items(), key=lambda kv: -sum(kv[1][x] for x in SUP))[:top]:
        out.append('  %-10s %-44s %6.3f %6.3f %6.3f %6.3f %6.3f' % (L, name[:44], *[c[x] / 1e9 for x in SUP]))
    return '\n'.join(out)


if __name__ == '__main__':
    a = sys.argv[1:]
    top = 10; binname = None
    if '--top' in a:
        i = a.index('--top'); top = int(a[i + 1]); del a[i:i + 2]
    if '--bin' in a:
        i = a.index('--bin'); binname = a[i + 1]; del a[i:i + 2]
    if not a:
        print(__doc__); sys.exit(1)
    for p in a:
        print(run(p, binname, top)); print()
