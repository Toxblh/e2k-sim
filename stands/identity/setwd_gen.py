#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""setwd_gen.py NAME call K F D ALIGN OFF DISTD > NAME.s : ../fetch/gen.py whose call-stand callees open a window of
WSZ quads (env, default 4) and, with SBN=1, also run setbn: do setwd/setbn cause bub_b_hwcmd? (hw/setwd.txt: no)
Built as  WSZ=w SBN=b python3 setwd_gen.py wd call 64 4 0 64 0 5 > w<w>b<b>.s; lcc -O1 ../fetch/main.c w<w>b<b>.s
KIND  disp    : block ends with ct %ctpr1, prepared by disp DISTD commands before the ct
      ibranch : block ends with an unprepared ibranch
      call    : K functions, called one after another from a driver block (disp DISTD before each call)
K     blocks (or functions) per iteration;  F filler commands per block;  D extra bytes of padding after each block
ALIGN target alignment (bytes);  OFF offset of the target after the alignment (multiple of 8)
"""
import sys, os
WSZ = int(os.environ.get('WSZ', 4)); SBN = int(os.environ.get('SBN', 0))
name, kind, K, F, D, AL, OFF, DD = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:9])
o = []
w = o.append


def filler(n, tag=None):
    for i in range(n):
        if tag is not None and i == tag[0]:
            w('\t{\n\t  %s\n\t  addd,0\t%%r5, 0x1, %%r5\n\t}' % tag[1])
        else:
            w('\t{\n\t  addd,0\t%r5, 0x1, %r5\n\t}')


def place(label):
    if D: w('\t.skip\t%d' % D)
    w('\t.align\t%d' % AL)
    if OFF: w('\t.skip\t%d' % OFF)
    w('%s:' % label)


w('\t.ignore\tld_st_style\n\t.ignore\tstrict_delay\n\t.text')
if kind == 'call':
    for k in range(K):
        w('\t.global\tfn%d\n\t.type\tfn%d, #function' % (k, k))
        place('fn%d' % k)
        w('\t{\n\t  nop 4\n\t  setwd\twsz = 0x%x, nfx = 0x1, dbl = 0x0\n\t}' % WSZ)
        if SBN: w('\t{\n\t  setbn\trsz = 0x4, rbs = 0x8, rcur = 0x0\n\t}')
        nf = max(F, DD)
        for i in range(nf):
            if i == nf - DD:
                w('\t{\n\t  return\t%ctpr3\n\t  addd,0\t0x0, 0x1, %r1\n\t}')
            else:
                w('\t{\n\t  addd,0\t0x0, 0x1, %r1\n\t}')
        if DD == 0:
            w('\t{\n\t  return\t%ctpr3\n\t}')
        w('\t{\n\t  ct\t%ctpr3\n\t}')
        w('\t.size\tfn%d, .- fn%d' % (k, k))
w('\t.global\tstand\n\t.type\tstand, #function\n\t.align\t256\nstand:')
w('\t{\n\t  setwd\twsz = 0x10, nfx = 0x1, dbl = 0x0\n\t  addd,0\t%r0, 0x0, %r6\n\t  addd,1\t0x0, 0x0, %r5\n\t}')
w('.Lhead:')
w('\t{\n\t  subd,0\t%r6, 0x1, %r6\n\t}')
w('\t{\n\t  nop 1\n\t  cmpedb,0\t%r6, 0x0, %pred0\n\t}')
if kind == 'call':
    for k in range(K):
        w('\t{\n\t  disp\t%%ctpr1, fn%d\n\t  addd,0\t%%r5, 0x1, %%r5\n\t}' % k)
        filler(max(DD - 1, 0))
        w('\t{\n\t  call\t%ctpr1, wbs = 0x8\n\t}')
    w('\t{\n\t  disp\t%ctpr2, .Lhead\n\t}')
    filler(3)
    w('\t{\n\t  return\t%ctpr3\n\t}')
    filler(3)
    w('\t{\n\t  ct\t%ctpr2 ? ~%pred0\n\t}')
    w('\t{\n\t  addd,0\t%r5, 0x0, %r0\n\t  ct\t%ctpr3\n\t}')
else:
    for k in range(K):
        nxt = '.Lb%d' % (k + 1) if k + 1 < K else '.Lend'
        if k > 0:
            place('.Lb%d' % k)
        if kind == 'disp':
            nf = max(F, DD)
            filler(nf, (nf - DD, 'disp\t%%ctpr1, %s' % nxt) if DD > 0 else None)
            w('\t{\n\t  ct\t%ctpr1\n\t}')
        else:
            filler(F)
            w('\t{\n\t  ibranch\t%s\n\t}' % nxt)
    place('.Lend')
    w('\t{\n\t  disp\t%ctpr2, .Lhead\n\t}')
    filler(3)
    w('\t{\n\t  return\t%ctpr3\n\t}')
    filler(3)
    w('\t{\n\t  ct\t%ctpr2 ? ~%pred0\n\t}')
    w('\t{\n\t  addd,0\t%r5, 0x0, %r0\n\t  ct\t%ctpr3\n\t}')
w('\t.size\tstand, .- stand')
print('\n'.join(o))
