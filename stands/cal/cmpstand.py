#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""cmpstand.py hw/cal1.txt SIMDIR : model CPI of the calibration stands (SIMDIR/<stand>.w0.sim.pkl, names of stands.txt) vs HW."""
import sys, glob, pickle, collections, os
R = collections.defaultdict(dict)
for l in open(sys.argv[1]):
    f = l.split()
    for kv in f[2:]:
        if '=' in kv:
            k, v = kv.split('=')
            if v.isdigit(): R[f[0]].setdefault(k.replace(':u', ''), int(v))
MAP = {'chase16k': 'chase_16384_20000000', 'chase256k': 'chase_262144_20000000', 'chase2m': 'chase_2097152_10000000',
       'chase64m': 'chase_67108864_2000000', 'st512k': 'st_524288_20000000', 'seq4m': 'seq_4194304_5000000',
       'call8s': 'call_8_0', 'call16b': 'call_16_1', 'call128b': 'call_128_1', 'call128s': 'call_128_0',
       'tlb2048': 'tlb_2048_4096_0_10000000', 'tlb300h': 'tlb_300_2097152_1_10000000'}
for k in ('code8', 'code96', 'code512', 'code2048'):
    kb = k[4:]; MAP[k] = [t for t in R if t.startswith('code_%s_' % kb) and not t.endswith('_0')][0]
print('%-10s %7s %7s %7s  %s' % ('stand', 'CPI_hw', 'CPI_mod', 'err', 'model split'))
for st, tag in MAP.items():
    ps = glob.glob(os.path.join(sys.argv[2], '%s.w0.sim.pkl' % st))
    if not ps or tag not in R: print('%-10s missing' % st); continue
    h = R[tag]; parts = tag.split('_'); base = '_'.join(parts[:-1] + ['0'])
    if base in R and 'instructions' in R[base] and not st.startswith('call'):
        cpi = (h['cycles'] - R[base]['cycles']) / (h['instructions'] - R[base]['instructions'])
    else:
        cpi = h['cycles'] / h['instructions']
    r = pickle.load(open(ps[0], 'rb')); c = sum(r['totals']); n = r['ninsn'] - r['warm']
    print('%-10s %7.3f %7.3f %+6.1f%%  %s' % (st, cpi, c / n, 100 * (c / n / cpi - 1),
          ' '.join('%s:%.0f' % (a, 100 * v / c) for a, v in zip(r['causes'], r['totals']) if v / c > 0.02)))
