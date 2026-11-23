#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""hwcmp.py HWFILE PFX... : model vs hardware for whole runs.

Model CPI over all windows of PFX (PFX.w*.sim.pkl) x the run's qemu instruction count gives the model's cycles,
(a) with all threads' instructions, (b) with the main thread's (vcpu0) instructions.
HWFILE: one line per run, `NAME cycles=C instructions=I [scope=all|main]` (perf stat cycles:u / instructions:u;
NAME = basename of PFX; scope main = measured on the main thread only, e.g. perf stat --no-inherit or -i).
Several lines of the same NAME are averaged (rounds)."""
import sys, glob, pickle, os, collections

hw = collections.defaultdict(lambda: collections.defaultdict(list)); scope = {}
for l in open(sys.argv[1]):
    if l.startswith('#') or not l.strip(): continue
    f = l.split(); kv = dict(x.split('=', 1) for x in f[1:] if '=' in x)
    for k in ('cycles', 'instructions'):
        if k in kv: hw[f[0]][k].append(float(kv[k]))
    scope[f[0]] = kv.get('scope', 'all')
print('%-16s %4s %7s %7s %7s | %9s %9s %7s | %9s %9s %7s' % ('run', 'win', 'CPI', 'HW CPI', 'CPI err', 'G cyc mod', 'G cyc HW', 'err',
                                                          'qemu Gins', 'HW Gins', 'diff'))
for pfx in sys.argv[2:]:
    name = os.path.basename(pfx)
    ws = glob.glob(pfx + '.w*.sim.pkl')
    if not ws or name not in hw: print('%-16s missing (windows %d, hw %s)' % (name, len(ws), name in hw)); continue
    c = n = 0
    for p in ws:
        r = pickle.load(open(p, 'rb')); c += sum(r['totals']); n += r['ninsn'] - r['warm']
    for l in open(pfx + '.info'):
        if l.startswith('total_insns'):
            f = l.split(); tot = int(f[1]); v0 = int(f[3])
    h = hw[name]; hc = sum(h['cycles']) / len(h['cycles']); hi = sum(h['instructions']) / len(h['instructions'])
    qi = v0 if scope[name] == 'main' else tot
    cpi = c / n; mc = cpi * qi
    print('%-16s %4d %7.3f %7.3f %+6.1f%% | %9.4f %9.4f %+6.1f%% | %9.4f %9.4f %+6.1f%%' % (
        name, len(ws), cpi, hc / hi, 100 * (cpi / (hc / hi) - 1), mc / 1e9, hc / 1e9, 100 * (mc / hc - 1), qi / 1e9, hi / 1e9, 100 * (qi / hi - 1)))
