#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""perfcmp.py PERFREPORT PFX [N] [--bin NAME]: hardware per-symbol cycle shares (perf record -e cycles:u, then
`perf report --stdio --sort symbol` or `--sort dso,symbol`) against the model's shares over its windows.
Note: the model only sees its sampled windows; a symbol that runs between windows is missing from it."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R
R.RAW = True
a = sys.argv[1:]
binname = None
if '--bin' in a:
    i = a.index('--bin'); binname = a[i + 1]; del a[i:i + 2]
top, pfx = a[0], a[1]
N = int(a[2]) if len(a) > 2 else 20


def norm(s):
    s = re.sub(r'^lib[\w+.-]*:', '', s); s = re.sub(r'@.*$', '', s)
    return s.strip()[:60]


hw = []
for l in open(top):
    m = re.match(r'\s*([\d.]+)%\s+(?:\S+\s+)?\[\.\]\s+(\S+)', l)
    if m: hw.append((float(m.group(1)), norm(m.group(2))))
by, ins, n = R.aggregate(pfx, binname)
tot = sum(sum(v) for v in by.values())
mod = {}; lay = {}
for (l, name), v in by.items():
    k = norm(name); mod[k] = mod.get(k, 0) + 100.0 * sum(v) / tot; lay[k] = l
hwd = dict((k, p) for p, k in hw)
print('%-40s %7s %7s %7s' % ('symbol (top %d on HW)' % N, 'HW%', 'model%', 'diff'))
sad = 0
for p, k in hw[:N]:
    m = mod.get(k, 0.0); sad += abs(m - p)
    print('%-40s %7.2f %7.2f %+7.2f' % (k, p, m, m - p))
print('sum |diff| over the HW top %d: %.1f points' % (N, sad))
print('\nmodel top 10 not in the HW list:')
for k, m in sorted(mod.items(), key=lambda kv: -kv[1])[:10]:
    if k not in hwd: print('%-40s %7s %7.2f  %s' % (k, '-', m, lay[k]))
