#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# run_hw.sh OUT [CASES] : code+data stands x 3 perf event groups x ROUNDS rounds on one core (on the Elbrus machine);
# "TAG rR GROUP it=ITERS event=count ..." per run (hw/hw2.txt).  Environment: CORE (7), ROUNDS (2), LOCK (optional flock file).
set -u
cd "$(dirname "$0")"; O=$1; C=${2:-cases.txt}
CORE=${CORE:-7}; ROUNDS=${ROUNDS:-2}
G1=cycles:u,instructions:u,ib_no_command:u,l2_query:u
G2=cycles:u,ticks_e2:u,l1_line:u,l2_hit:u
G3=cycles:u,ib_disp_miss:u,bub_b:u,ib_ahead_miss:u
if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
for r in $(seq "$ROUNDS"); do grep -v '^#' "$C" | while read tag n f rr o ch d; do it=$((10000000 / n))
  for gr in G1 G2 G3; do
    x=$(taskset -c "$CORE" perf stat -x, -e ${!gr} bin/$tag $it $d 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
    echo "$tag r$r $gr it=$it $x" >> "$O"
  done
done; done
if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
