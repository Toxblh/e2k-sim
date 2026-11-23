#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ana.py fetch1.txt cases.txt: per case CPI, cycles per taken transfer beyond 1/insn, ib_disp/ahead events per transfer"""
import sys, collections
R = collections.defaultdict(dict)
for l in open(sys.argv[1]):
    f = l.split()
    for kv in f[2:]:
        if '=' in kv:
            k, v = kv.split('=')
            if v.isdigit(): R[f[0]].setdefault(k.replace(':u', ''), int(v))
C = {}
for l in open(sys.argv[2]):
    f = l.split()
    if f[1] == 'asm':
        tag, kind, K, F, D, AL, OFF, DD, it = f[0], f[2], *map(int, f[3:])
        C[tag] = dict(kind=kind, K=K, F=F, D=D, OFF=OFF, DD=DD, it=it, per=K * (max(F, DD) + 1) + 9, tr=K + 1)
    else:
        C[f[0]] = dict(kind='call', K=int(f[2]), it=int(f[3]), tr=2 * int(f[2]) + 1)
print('%-16s %6s %8s %8s %8s %8s %8s %8s' % ('case', 'CPI', 'cyc/tr', 'ibdm/tr', 'ibam/tr', 'ibdq/tr', 'ibaq/tr', 'bubb/tr'))
for tag, c in C.items():
    r = R.get(tag)
    if not r or 'instructions' not in r: print('%-16s missing' % tag); continue
    ins, cyc = r['instructions'], r['cycles']
    tr = c['tr'] * c['it']
    g = lambda k: r.get(k, float('nan')) / tr
    print('%-16s %6.3f %8.2f %8.3f %8.3f %8.3f %8.3f %8.2f' % (tag, cyc / ins, (cyc - ins) / tr, g('ib_disp_miss'), g('ib_ahead_miss'),
          g('ib_disp_query'), g('ib_ahead_query'), g('bub_b')))
