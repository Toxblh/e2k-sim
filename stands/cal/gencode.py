#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""gencode.py [KB...] > code.c : the straight-line code-size stand of EVENTS.md.

Function f<KB> is one block of 8*KB dependent integer statements (about KB kilobytes of e2k-v5 code
at -O2); main(KB, R) calls f<KB> R times.  Default sizes: 8 32 96 192 512 2048.
"""
import sys

sizes = [int(x) for x in sys.argv[1:]] or [8, 32, 96, 192, 512, 2048]
o = ['#include <stdio.h>', '#include <stdlib.h>']
for kb in sizes:
    o.append('__attribute__((noinline)) long f%d(long a, long b) {' % kb)
    o.append('  long x = a, y = b, z = a ^ b, w = a + b;')
    for i in range(1, 8 * kb + 1):
        o.append('  x = x * %d + y; y = (y ^ %d) + z; z = z * %d - w; w = (w + %d) ^ x;' % (2 * i + 1, 7 * i - 6, 2 * i + 3, 13 * i - 10))
    o.append('  return x + y + z + w; }')
o.append('int main(int c, char **v) { int kb = atoi(v[1]); long r = atol(v[2]), s = 0;')
o.append('  for (long i = 0; i < r; i++) switch (kb) { ' + ' '.join('case %d: s += f%d(i, s); break;' % (k, k) for k in sizes) + ' }')
o.append('  printf("%ld\\n", s); return 0; }')
print('\n'.join(o))
