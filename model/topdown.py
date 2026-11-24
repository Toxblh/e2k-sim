#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""topdown.py PFX... : the model's cycles grouped like the Elbrus-8SV top-down identity (docs/IDENTITY.md)

    cycles = instructions + bub_b + ticks_e2 + ib_no_command

model cause -> HW bucket:  issue -> instructions;  nop, call, spill -> bub_b;  dep, L2, L3, DRAM, stld, dtlb -> ticks_e2;
ctprep, ibranch, icache, itarget, itlb -> ib_no_command.  G cycles over the whole run of the main thread (the model's
CPI over all windows of PFX x the run's vcpu0 instruction count from PFX.info), so the four numbers compare directly
with `perf stat -i -e cycles:u,instructions:u,bub_b:u,ticks_e2:u` and `-e ib_no_command:u` on the hardware.
Also prints every cause and the model's event counters per 1000 wide instructions."""
import sys, glob, pickle

GRP = dict(issue='instructions', nop='bub_b', call='bub_b', spill='bub_b',
           dep='ticks_e2', L2='ticks_e2', L3='ticks_e2', DRAM='ticks_e2', stld='ticks_e2', dtlb='ticks_e2',
           ctprep='ib_no_command', ibranch='ib_no_command', icache='ib_no_command', itarget='ib_no_command', itlb='ib_no_command')
ORDER = ('instructions', 'bub_b', 'ticks_e2', 'ib_no_command')
for pfx in sys.argv[1:]:
    ws = glob.glob(pfx + '.w*.sim.pkl')
    if not ws: print('%s: no windows' % pfx); continue
    n = 0; t = None; mem = {}
    for p in ws:
        r = pickle.load(open(p, 'rb')); n += r['ninsn'] - r['warm']
        if t is None: t = [0.0] * len(r['totals']); C = r['causes']
        for i, v in enumerate(r['totals']): t[i] += v
        for k, v in r['mem'].items(): mem[k] = mem.get(k, 0) + v
    v0 = n
    for l in open(pfx + '.info'):
        if l.startswith('total_insns'): v0 = int(l.split()[3])
    k = v0 / n / 1e9
    g = dict.fromkeys(ORDER, 0.0)
    for c, v in zip(C, t): g[GRP[c]] += v * k
    print('%s  windows %d  G cycles %.3f = %s' % (pfx, len(ws), sum(t) * k, ' + '.join('%s %.3f' % (b, g[b]) for b in ORDER)))
    print('  causes: ' + '  '.join('%s %.3f' % (c, v * k) for c, v in zip(C, t) if v))
    print('  per 1000 wide instructions: ' + '  '.join('%s %.1f' % (kk, 1000.0 * v / n) for kk, v in sorted(mem.items())))
