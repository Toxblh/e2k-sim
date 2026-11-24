#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# run_hw.sh OUT STAND... : 20 M iterations of each stand (2 speculative loads per iteration), 2 event groups, one core.
# "TAG event=count ..." per run (hw/spec*.txt).  Environment: CORE (7), LOCK (optional flock file).
set -u
cd "$(dirname "$0")"; O=$1; shift; CORE=${CORE:-7}
if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
for b in "$@"; do for g in cycles:u,instructions:u,dtlb_tlu_query:u,dtlb_query:u cycles:u,dtlb_hit:u,ticks_e2:u,l1_query:u; do
  x=$(taskset -c "$CORE" perf stat -x, -e $g bin/$b 20000000 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
  echo "$b $x" >> "$O"
done; done
if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
