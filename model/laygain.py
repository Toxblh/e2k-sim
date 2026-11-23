#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""laygain.py BASEDIR VARDIR... -- RUN... : G cycles saved by layout variants, scaled to the whole run.

For each run RUN and variant directory VARDIR (sim.py results of the same trace with SIM_LAYOUT=..., possibly on a
subset of windows): saved = (base - variant) on the SAME windows, scaled to the whole run's model G cycles
(BASEDIR/RUN.info total_insns x the base model's CPI over all its windows).  [E] estimates: a layout map moves code
lines, it does not model the extra work of the code that would make it possible.
In brackets: the itarget / itlb / icache parts."""
import sys, glob, pickle, os

CA = ('issue', 'nop', 'dep', 'L2', 'L3', 'DRAM', 'stld', 'dtlb', 'ctprep', 'ibranch', 'icache', 'call', 'spill', 'itarget', 'itlb')
a = sys.argv[1:]
if '--' not in a:
    print(__doc__); sys.exit(1)
k = a.index('--'); dirs, runs = a[:k], a[k + 1:]
base, variants = dirs[0], dirs[1:]


def load(d, r, ws=None):
    out = {}
    for p in glob.glob('%s/%s.w*.sim.pkl' % (d, r)):
        w = int(p.split('.w')[-1].split('.')[0])
        if ws is not None and w not in ws: continue
        out[w] = pickle.load(open(p, 'rb'))
    return out


def tot(rs):
    c = [0.0] * len(CA); n = 0
    for r in rs.values():
        for i, x in enumerate(r['totals']): c[i] += x
        n += r['ninsn'] - r['warm']
    return c, n


print('G cycles saved over the whole run [E]; in brackets: itarget / itlb / icache parts')
print('%-14s' % 'variant' + ''.join('%28s' % r for r in runs))
G = {}
for r in runs:
    c, n = tot(load(base, r))
    for l in open('%s/%s.info' % (base, r)):
        if l.startswith('total_insns'): G[r] = sum(c) / max(n, 1) * int(l.split()[1]) / 1e9
for v in variants:
    row = '%-14s' % os.path.basename(v.rstrip('/'))
    for r in runs:
        vr = load(v, r)
        if not vr: row += '%28s' % '-'; continue
        cb, nb = tot(load(base, r, set(vr))); cv, nv = tot(vr)
        f = G[r] / max(sum(cb), 1)
        d = [(cb[i] - cv[i]) * f for i in range(len(CA))]
        row += '%9.4f (%5.3f/%5.3f/%5.3f)' % (sum(d), d[CA.index('itarget')], d[CA.index('itlb')], d[CA.index('icache')])
    print(row)
