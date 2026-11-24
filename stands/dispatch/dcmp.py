#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""dcmp.py HW.txt SIMDIR [CASES]: dispatch stands, HW vs model: extra cycles per taken transfer and HW events per transfer."""
import sys, glob, pickle, os, collections
R = collections.defaultdict(lambda: collections.defaultdict(list))
F = {}
for l in open(sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases.txt')):
    if l.startswith('#'): continue
    t, n, f, r, o, it = l.split(); F[t] = int(f) + 1
for l in open(sys.argv[1]):
    f = l.split()
    for kv in f[3:]:
        if '=' in kv:
            k, v = kv.split('=')
            if v.isdigit(): R[f[0]][k.replace(':u', '')].append(int(v))
avg = lambda x: sum(x) / len(x)
print('%-20s %6s %6s %6s | %5s %5s %5s %5s %5s %5s | %s' % ('stand', 'hw', 'mod', 'err', 'nocmd', 'dmiss', 'amiss', 'l2q', 'l2hit', 'itlb', 'model split per transfer'))
for t in sorted(R, key=lambda x: (x.split('_')[0], int(x.split('_N')[1].split('_')[0]), x)):
    h = R[t]; ins = avg(h['instructions']); cyc = avg(h['cycles']); ntr = ins / F[t]
    e = lambda k: avg(h[k]) / ntr if k in h else float('nan')
    hw = (cyc - ins) / ntr
    p = '%s/%s.w0.sim.pkl' % (sys.argv[2], t)
    mod = float('nan'); sp = ''
    if os.path.exists(p):
        r = pickle.load(open(p, 'rb')); c = sum(r['totals']); n = r['ninsn'] - r['warm']; mt = n / F[t]
        mod = (c - n) / mt
        sp = ' '.join('%s:%.1f' % (a, v / mt) for a, v in zip(r['causes'], r['totals']) if v / mt > 0.2 and a != 'issue')
    print('%-20s %6.1f %6.1f %+6.1f | %5.1f %5.2f %5.2f %5.2f %5.2f %5.2f | %s' % (t, hw, mod, mod - hw, e('ib_no_command'), e('ib_disp_miss'), e('ib_ahead_miss'), e('l2_query'), e('l2_hit'), e('ib_disp_itlb_miss'), sp))
