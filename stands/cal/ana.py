#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ana.py hw/cal1.txt : per-access event rates of the calibration stands ((run - same run with n=0) / n), the tables of docs/EVENTS.md."""
import sys, re, collections
R = collections.defaultdict(dict)
for l in open(sys.argv[1]):
    f = l.split(); tag = f[0]
    for kv in f[2:]:
        if '=' not in kv: continue
        k, v = kv.split('=')
        if v.isdigit(): R[tag].setdefault(k.replace(':u', ''), int(v))
def delta(tag, base, n, ev):
    a, b = R[tag].get(ev), R[base].get(ev, 0)
    return None if a is None else (a - b) / n
EV = ['cycles', 'l1_query', 'l1_ld_hit', 'l1_st_query', 'l1_st_hit', 'l2_query', 'l2_hit', 'dtlb_query', 'dtlb_hit', 'stall_dtlb_miss']
print('per access (run - n=0 run) / n')
print('%-18s' % 'stand' + ''.join('%11s' % e[:11] for e in EV))
for m in ('chase', 'seq', 'st'):
    for F in sorted(set(int(x.split('_')[1]) for x in R if x.startswith(m + '_'))):
        t = [x for x in R if x.startswith('%s_%d_' % (m, F)) and not x.endswith('_0')][0]
        n = int(t.split('_')[-1]); b = '%s_%d_0' % (m, F)
        print('%-18s' % ('%s %dK' % (m, F >> 10)) + ''.join('%11s' % ('-' if delta(t, b, n, e) is None else '%.3f' % delta(t, b, n, e)) for e in EV))
print('\ncode sweep, per wide instruction (and per KB of code per call)')
CE = ['cycles', 'ib_disp_miss', 'ib_ahead_miss', 'ib_disp_query', 'ib_ahead_query', 'ib_no_command', 'bub_b', 'l2_query', 'l2_hit', 'ib_disp_itlb_miss']
print('%-12s %6s' % ('code', 'IPC') + ''.join('%11s' % e[:11] for e in CE))
for t in sorted([x for x in R if x.startswith('code_') and not x.endswith('_0')], key=lambda x: int(x.split('_')[1])):
    kb = t.split('_')[1]; b = 'code_%s_0' % kb
    ins = R[t]['instructions'] - R[b]['instructions']
    print('%-12s %6.3f' % ('code %sK' % kb, ins / (R[t]['cycles'] - R[b]['cycles'])) + ''.join('%11s' % ('-' if delta(t, b, ins, e) is None else '%.4f' % delta(t, b, ins, e)) for e in CE))
print('\nDTLB sweep, per load (P pages, spacing S, huge H)')
TE = ['cycles', 'dtlb_query', 'dtlb_hit', 'stall_dtlb_miss', 'stall_dtlb', 'l1_query']
print('%-22s' % 'tlb' + ''.join('%11s' % e[:11] for e in TE))
for t in [x for x in R if x.startswith('tlb_') and not x.endswith('_0')]:
    _, P, S, h, n = t.split('_'); b = 'tlb_%s_%s_%s_0' % (P, S, h)
    print('%-22s' % ('P=%s S=%dK %s' % (P, int(S) >> 10, 'huge' if h == '1' else '4K')) + ''.join('%11s' % ('-' if delta(t, b, int(n), e) is None else '%.3f' % delta(t, b, int(n), e)) for e in TE))
print('\ncall/return, per call (recursion depth D, frame small/big)')
KE = ['cycles', 'instructions', 'bub_b_chain_spillfill', 'bub_b_rf_spillfill', 'bub_b_chain_ret_nrdy']
print('%-12s' % 'call' + ''.join('%14s' % e[-14:] for e in KE))
for t in sorted([x for x in R if x.startswith('call_')], key=lambda x: (int(x.split('_')[2]), int(x.split('_')[1]))):
    _, d, w = t.split('_'); n = (20000000 // int(d)) * int(d)
    print('%-12s' % ('D=%s %s' % (d, 'big' if w == '1' else 'small')) + ''.join('%14.2f' % (R[t].get(e, 0) / n) for e in KE))
