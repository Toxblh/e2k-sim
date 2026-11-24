#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""cmp.py HW.txt SIMDIR...: code+data stands, cycles per transfer: HW (total, e2, nocmd) vs each model variant (total, e2-like, front-end)."""
import sys, glob, pickle, os, collections
R = collections.defaultdict(lambda: collections.defaultdict(list)); F = {}
for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases.txt')):
    if l.startswith('#'): continue
    t, n, f, r, o, ch, d = l.split(); F[t] = int(f) + 1
for l in open(sys.argv[1]):
    f = l.split()
    for kv in f[3:]:
        if '=' in kv:
            k, v = kv.split('=')
            if v.isdigit(): R[f[0]][k.replace(':u', '')].append(int(v))
avg = lambda x: sum(x) / len(x)
E2 = ('dep', 'L2', 'L3', 'DRAM', 'stld', 'dtlb'); FE = ('ctprep', 'ibranch', 'icache', 'itarget', 'itlb')
hdr = '%-24s | %5s %5s %5s %5s %5s' % ('stand', 'HW', 'e2', 'nocmd', 'l2q', 'l2hit')
for v in sys.argv[2:]: hdr += ' | %-17s' % os.path.basename(v)
print(hdr)
for t in sorted(R):
    h = R[t]; ins = avg(h['instructions']); ntr = ins / F[t]
    row = '%-24s | %5.1f %5.1f %5.1f %5.1f %5.1f' % (t, (avg(h['cycles']) - ins) / ntr, avg(h['ticks_e2']) / ntr, avg(h['ib_no_command']) / ntr, avg(h['l2_query']) / ntr, avg(h['l2_hit']) / ntr)
    for v in sys.argv[2:]:
        p = '%s/%s.w0.sim.pkl' % (v, t)
        if not os.path.exists(p): row += ' | %17s' % '-'; continue
        r = pickle.load(open(p, 'rb')); c = sum(r['totals']); n = r['ninsn'] - r['warm']; mt = n / F[t]
        T = dict(zip(r['causes'], r['totals']))
        row += ' | %5.1f %5.1f %5.1f' % ((c - n) / mt, sum(T[x] for x in E2) / mt, sum(T[x] for x in FE) / mt)
    print(row)
