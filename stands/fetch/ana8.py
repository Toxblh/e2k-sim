#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ana8.py RAW...: per stand, cycles per taken transfer (all cycles / (it*K)), events per transfer, mean of rounds."""
import sys, collections
R = collections.defaultdict(lambda: collections.defaultdict(list)); META = {}
for fn in sys.argv[1:]:
    for l in open(fn):
        f = l.split(); t = f[0]
        if '_K' not in t: continue
        it = [int(x[3:]) for x in f if x.startswith('it=')][0]; META[t] = (it, int(t.split('_K')[1].split('_')[0]))
        for kv in f:
            if ':u=' in kv:
                k, v = kv.split(':u='); R[t][k].append(int(v))
print('%-18s %7s %6s %7s %6s %6s %6s %6s' % ('stand', 'cyc/tr', 'ins/tr', 'itlb/tr', 'l2q/tr', 'l2hit', 'dmiss', 'amiss'))
for t in sorted(R, key=lambda s: (s.split('_K')[0], META[s][1])):
    it, K = META[t]; n = it * K; d = R[t]
    m = lambda k: (sum(d[k]) / len(d[k]) / n) if d.get(k) else float('nan')
    print('%-18s %7.2f %6.2f %7.2f %6.2f %6.2f %6.2f %6.2f' % (t, m('cycles'), m('instructions'), m('ib_disp_itlb_miss'), m('l2_query'), m('l2_hit'), m('ib_disp_miss'), m('ib_ahead_miss')))
