#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# trace.sh OUTDIR CASES... : trace every stand (built by build.sh, bin/ copied to the qemu host) under qemu-e2k
# (skip 2 M, one 6 M window), decode it and model it (2 M warm-up) -> OUTDIR/<tag>.w0.sim.pkl;
# then compare with the hardware: python3 fcmp.py OUTDIR hw/fetch1.txt hw/span2.txt hw/itlb.txt hw/itlb8.txt
# Environment: as scripts/qtrace.sh and scripts/model.sh; JOBS parallel stands (default 4).
set -u
cd "$(dirname "$0")"; O=$1; shift; mkdir -p "$O"
H=$(cd .. && cd .. && pwd); J=${JOBS:-4}
cat "$@" | while read tag typ a b c d e f g h; do it=$h; [ $typ = asm ] || it=$b; echo "$tag $it"; done | sort -u | \
  xargs -P "$J" -L1 sh -c "[ -f '$O'/\$0.w0.sim.pkl ] && exit 0; '$H/scripts/qtrace.sh' '$O'/\$0 skip=2000000,win=6000000 -- bin/\$0 \$1 && JOBS=1 '$H/scripts/model.sh' '$O'/\$0 2000000 > /dev/null"
