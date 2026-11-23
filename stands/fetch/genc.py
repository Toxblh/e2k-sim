#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""genc.py K PAD > x.c : call stand, K noinline functions (each 4 adds), each padded to PAD bytes by an unused array of code"""
import sys
K, PAD = int(sys.argv[1]), int(sys.argv[2])
o = ['#include <stdio.h>', '#include <stdlib.h>', 'volatile long sink;']
for k in range(K):
    o.append('__attribute__((noinline, aligned(%d))) long f%d(long a) { return ((a * 3 + %d) ^ (a >> 2)) + %d; }' % (max(PAD, 8), k, k, k * 7))
o.append('int main(int c, char **v) { long n = atol(v[1]), s = 0;')
o.append('  for (long i = 0; i < n; i++) {')
for k in range(K):
    o.append('    s = f%d(s);' % k)
o.append('  }\n  printf("%ld\\n", s); return 0; }')
print('\n'.join(o))
