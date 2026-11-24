#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# trace.sh OUTDIR [CASES] : trace every dispatch stand (bin/ copied to the qemu host) under qemu-e2k (skip 2 M, one 6 M
# window), decode and model it (2 M warm-up) -> OUTDIR/<tag>.w0.sim.pkl; then:  python3 dcmp.py hw/hw1.txt OUTDIR
# Model settings come from the environment (SIMPY=sim3.py SIM_ISUB=4 ...); see scripts/model.sh.  JOBS (default 4).
set -u
cd "$(dirname "$0")"; O=$1; C=${2:-cases.txt}; mkdir -p "$O"
H=$(cd ../.. && pwd); J=${JOBS:-4}
grep -v '^#' "$C" | while read tag n f r o it; do echo "$tag $it"; done | \
  xargs -P "$J" -L1 sh -c "[ -f '$O'/\$0.w0.sim.pkl ] && exit 0; '$H/scripts/qtrace.sh' '$O'/\$0 skip=2000000,win=6000000 -- bin/\$0 \$1 && JOBS=1 '$H/scripts/model.sh' '$O'/\$0 2000000 > /dev/null"
