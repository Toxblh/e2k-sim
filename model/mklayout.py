#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""mklayout.py PFX OUT.pkl [SCOPE] [--bin NAME] [--simdir DIR]: a code layout estimate from the run's own windows.

Functions (symbols) are ordered by execution heat, each function's 256 B lines kept in order and packed one after
another from a fresh base; code outside SCOPE keeps its addresses.  Use with SIM_LAYOUT=OUT.pkl sim.py ...
SCOPE: all (default) | lines (upper bound: every 256 B line placed by its own heat, a perfect hot/cold split)
       | a comma-separated list of layers (see report.py), e.g. jit or main,lib."""
import sys, os, glob, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R


def opt(a, k, d=None):
    if k in a:
        i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
    return d


a = sys.argv[1:]
binname = opt(a, '--bin'); simdir = opt(a, '--simdir')
pfx, out = a[0], a[1]
scope = a[2] if len(a) > 2 else 'all'
layers = None if scope in ('all', 'lines') else set(scope.split(','))
meta = pickle.load(open(pfx + '.dec.pkl', 'rb')); res = R.Resolver(pfx, binname)
sims = glob.glob('%s.w*.sim.pkl' % (os.path.join(simdir, os.path.basename(pfx)) if simdir else pfx))
heat = collections.Counter(); lines = collections.defaultdict(set); lh = collections.Counter()
for p in sims:
    r = pickle.load(open(p, 'rb'))
    for iid, n in r['execs'].items():
        ad = meta['addr'][iid]; d = meta['dec'].get(iid); sz = d['size'] if d else 16
        L, name = res.resolve(ad, meta['syms'][iid])
        if layers is not None and L not in layers: continue
        heat[(L, name)] += n
        for ln in range(ad >> 8, ((ad + sz - 1) >> 8) + 1):
            lines[(L, name)].add(ln); lh[ln] += n
m = {}; nxt = (0x10000000 >> 8)
if scope == 'lines':
    for ln, h in lh.most_common():
        m[ln] = nxt; nxt += 1
else:
    for k, h in heat.most_common():
        for ln in sorted(lines[k]):
            if ln not in m: m[ln] = nxt; nxt += 1
pickle.dump(m, open(out, 'wb'))
print('%s: %d functions, %d lines (%.0f KB) packed' % (scope, len(heat), len(m), len(m) * 256 / 1024))
