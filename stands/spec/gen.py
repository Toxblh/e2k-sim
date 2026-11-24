#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""gen.py ADDR USE [STEP] > x.s : loop of 8 commands, 2 speculative loads (ldd,sm) per iteration from ADDR (+8 per load, same page);
USE=1: the loaded values feed an add 3 commands later (speculative op, diagnostic propagates);
STEP: ADDR advances by STEP bytes every iteration (a new page each time)."""
import sys
addr, use = int(sys.argv[1], 0), int(sys.argv[2]); step = int(sys.argv[3]) if len(sys.argv) > 3 else 0
o = []; w = o.append
w("\t.ignore\tld_st_style\n\t.ignore\tstrict_delay\n\t.text\n\t.global\tstand\n\t.type\tstand, #function\n\t.align\t256\nstand:")
w("\t{\n\t  setwd\twsz = 0x10, nfx = 0x1, dbl = 0x0\n\t  addd,0\t%%r0, 0x0, %%r6\n\t  addd,1\t0x0, 0x0, %%r5\n\t  addd,2\t0x0, _f64 0x%x, %%r7\n\t}" % addr)
w(".Lhead:")
w("\t{\n\t  disp\t%ctpr1, .Lhead\n\t  subd,0\t%r6, 0x1, %r6\n\t}")
w("\t{\n\t  nop 1\n\t  cmpedb,0\t%r6, 0x0, %pred0\n\t}")
w("\t{\n\t  ldd,0,sm\t%r7, 0x0, %r8\n\t  ldd,3,sm\t%r7, 0x8, %r9\n\t  addd,1\t%r5, 0x1, %r5\n\t}")
for i in range(3):
    if step and i == 0: w("\t{\n\t  addd,1\t%%r5, 0x1, %%r5\n\t  addd,2\t%%r7, _f64 0x%x, %%r7\n\t}" % step)
    else: w("\t{\n\t  addd,1\t%r5, 0x1, %r5\n\t}")
if use: w("\t{\n\t  addd,0,sm\t%r8, %r9, %r10\n\t}")
else: w("\t{\n\t  addd,1\t%r5, 0x1, %r5\n\t}")
w("\t{\n\t  addd,1\t%r5, 0x1, %r5\n\t}")
w("\t{\n\t  ct\t%ctpr1 ? ~%pred0\n\t}")
w("\t{\n\t  return\t%ctpr3\n\t}")
w("\t{\n\t  addd,0\t%r5, 0x0, %r0\n\t  ct\t%ctpr3\n\t}")
w("\t.size\tstand, .- stand")
print("\n".join(o))
