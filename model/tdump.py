#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""tdump.py PFX WIN [start] [count]: print insn records (vaddr, sym) and their memory accesses of one trace window."""
import sys, struct, os, subprocess
pfx, w = sys.argv[1], int(sys.argv[2])
start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
cnt = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
code = {}
for l in open(pfx + '.code'):
    f = l.split()
    code[int(f[0])] = (int(f[1], 16), f[4] if len(f) > 4 else '-')
fn = '%s.w%d.bin' % (pfx, w)
data = open(fn, 'rb').read() if os.path.exists(fn) else subprocess.run(['zstd', '-q', '-d', '-c', fn + '.zst'], capture_output=True).stdout
n = -1
for (r,) in struct.iter_unpack('<Q', data):
    if r >> 63:
        n += 1
        if n >= start + cnt: break
        if n >= start:
            va, sym = code[r & 0xffffffff]
            print('%8d %x %s' % (n, va, sym))
    elif n >= start:
        va = r & ((1 << 56) - 1); sz = 1 << ((r >> 56) & 7); st = (r >> 59) & 1
        print('           %s %x %d' % ('ST' if st else 'LD', va, sz))
