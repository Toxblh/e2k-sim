#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""gen3.py N F R ORDER SEED [CH] > x.s : dispatch stand  long stand(long iters[, void *ring]).  N blocks of F commands (disp ctpr1 at F-5, then ct ctpr1),
block k sits in slot k of a region of R bytes (slot = R/N) at a random 8-byte-multiple offset inside the slot (SEED),
ORDER rand = blocks visited in a random permutation, seq = in address order. One round of the chain per iteration.
CH=1: every block also starts with one dependent load of a pointer ring (%r20, set from the 2nd argument; main2.c
in ../l2code builds the ring) - the code+data stands of ../l2code."""
import sys, random
N, F, R = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); order = sys.argv[4]; seed = int(sys.argv[5]); CH = int(sys.argv[6]) if len(sys.argv) > 6 else 0
rng = random.Random(seed)
slot = R // N
BS = 8 * F + 32                       # generous upper bound of one block's bytes
slack = max(0, slot - BS)
offs = [k * slot + (rng.randrange(0, slack // 8 + 1) * 8 if slack else 0) for k in range(N)]
perm = list(range(N))
if order == 'rand':
    rng.shuffle(perm)
o = []; w = o.append
w('\t.ignore\tld_st_style\n\t.ignore\tstrict_delay')
w('\t.section\t.text.rgn,"ax",@progbits\n\t.p2align\t20')
w('.Lrgn:')
nxt = {perm[i]: ('.Lb%d' % perm[i + 1] if i + 1 < N else '.Lend') for i in range(N)}
DD = 5
for k in range(N):
    w('\t.org\t%d' % offs[k])
    w('.Lb%d:' % k)
    nf = max(F, DD)
    for i in range(nf):
        if CH and i == 0:                 # data chase: one dependent load per block (%r20 walks the ring built by main2.c)
            w('\t{\n\t  ldd,0\t%r20, 0x0, %r20\n\t  addd,1\t%r5, 0x1, %r5\n\t}')
        elif i == nf - DD:
            w('\t{\n\t  disp\t%%ctpr1, %s\n\t  addd,0\t%%r5, 0x1, %%r5\n\t}' % nxt[k])
        else:
            w('\t{\n\t  addd,0\t%r5, 0x1, %r5\n\t}')
    w('\t{\n\t  ct\t%ctpr1\n\t}')
w('\t.text\n\t.global\tstand\n\t.type\tstand, #function\n\t.align\t256\nstand:')
w('\t{\n\t  setwd\twsz = 0x10, nfx = 0x1, dbl = 0x0\n\t  addd,0\t%r0, 0x0, %r6\n\t  addd,1\t0x0, 0x0, %r5\n\t  addd,2\t%r1, 0x0, %r20\n\t}')
w('.Lhead:')
w('\t{\n\t  disp\t%%ctpr1, .Lb%d\n\t  subd,0\t%%r6, 0x1, %%r6\n\t}' % perm[0])
w('\t{\n\t  nop 1\n\t  cmpedb,0\t%r6, 0x0, %pred0\n\t}')
for i in range(4): w('\t{\n\t  addd,0\t%r5, 0x1, %r5\n\t}')
w('\t{\n\t  ct\t%ctpr1\n\t}')
w('.Lend:')
w('\t{\n\t  disp\t%ctpr2, .Lhead\n\t}')
for i in range(3): w('\t{\n\t  addd,0\t%r5, 0x1, %r5\n\t}')
w('\t{\n\t  return\t%ctpr3\n\t}')
for i in range(3): w('\t{\n\t  addd,0\t%r5, 0x1, %r5\n\t}')
w('\t{\n\t  ct\t%ctpr2 ? ~%pred0\n\t}')
w('\t{\n\t  addd,0\t%r5, 0x0, %r0\n\t  ct\t%ctpr3\n\t}')
w('\t.size\tstand, .- stand')
print('\n'.join(o))
