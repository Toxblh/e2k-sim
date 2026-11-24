#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# trace.sh OUTDIR [CASES] : trace the code+data stands under qemu-e2k (skip 6 M: the ring is built first; one 6 M window),
# decode and model (3 M warm-up) -> OUTDIR/<tag>.w0.sim.pkl; then:  python3 cmp.py hw/hw2.txt OUTDIR [OUTDIR2 ...]
# Model settings from the environment (SIMPY=sim3.py SIM_...); JOBS (default 4).
set -u
cd "$(dirname "$0")"; O=$1; C=${2:-cases.txt}; mkdir -p "$O"
H=$(cd ../.. && pwd); J=${JOBS:-4}
grep -v '^#' "$C" | while read tag n f r o ch d; do echo "$tag $((10000000 / n)) $d"; done | \
  xargs -P "$J" -L1 sh -c "[ -f '$O'/\$0.w0.sim.pkl ] && exit 0; '$H/scripts/qtrace.sh' '$O'/\$0 skip=6000000,win=6000000 -- bin/\$0 \$1 \$2 && JOBS=1 '$H/scripts/model.sh' '$O'/\$0 3000000 > /dev/null"
