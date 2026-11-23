#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""fcmp.py SIMDIR HWFILE... : model CPI of every stand (SIMDIR/<tag>.w0.sim.pkl) vs the measured CPI (first value of
cycles and instructions per tag in the HW files), the model's split by cause, and the error distribution."""
import sys, glob, pickle, os, collections
R = collections.defaultdict(dict)
for fn in sys.argv[2:]:
    for l in open(fn):
        f = l.split()
        for kv in f[1:]:
            if '=' in kv:
                k, v = kv.split('=')
                if v.isdigit(): R[f[0]].setdefault(k.replace(':u', ''), int(v))
errs = []
print('%-16s %7s %7s %7s  %s' % ('stand', 'CPI_hw', 'CPI_mod', 'err', 'model split'))
for p in sorted(glob.glob(os.path.join(sys.argv[1], '*.w0.sim.pkl'))):
    t = os.path.basename(p).split('.')[0]
    if t not in R or 'instructions' not in R[t]: continue
    r = pickle.load(open(p, 'rb')); c = sum(r['totals']); n = r['ninsn'] - r['warm']
    if n <= 0: continue
    h = R[t]['cycles'] / R[t]['instructions']; e = 100 * (c / n / h - 1); errs.append(abs(e))
    print('%-16s %7.3f %7.3f %+6.1f%%  %s' % (t, h, c / n, e, ' '.join('%s:%.0f' % (a, 100 * v / c) for a, v in zip(r['causes'], r['totals']) if v / c > 0.03)))
if errs:
    errs.sort(); print('median |err| %.1f%%, 90%% %.1f%%, n=%d' % (errs[len(errs) // 2], errs[int(len(errs) * 0.9)], len(errs)))
