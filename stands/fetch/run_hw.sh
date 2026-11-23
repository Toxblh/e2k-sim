#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# run_hw.sh OUT CASES... : every stand x 2 perf event groups x ROUNDS rounds on one core (on the Elbrus machine).
# One line per run: "TAG rR GROUP it=ITERS event=count ..." (the format of hw/itlb8.txt; ana8.py and fcmp.py read it).
# Environment: CORE (default 7), ROUNDS (default 2), LOCK (optional flock file held for the whole measurement:
#              every stand runs 0.05-0.5 s), G1/G2 event lists (defaults below; Elbrus-8SV PMU event names).
set -u
cd "$(dirname "$0")"; O=$1; shift
CORE=${CORE:-7}; ROUNDS=${ROUNDS:-2}
G1=${G1:-cycles:u,instructions:u,ib_disp_itlb_miss:u,l2_query:u}
G2=${G2:-cycles:u,l2_hit:u,ib_disp_miss:u,ib_ahead_miss:u}
if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
for r in $(seq "$ROUNDS"); do cat "$@" | while read tag typ a b c d e f g h; do
  it=$h; [ $typ = asm ] || it=$b
  for gr in G1 G2; do
    x=$(taskset -c "$CORE" perf stat -x, -e ${!gr} bin/$tag $it 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
    echo "$tag r$r $gr it=$it $x" >> "$O"
  done
done; done
if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
