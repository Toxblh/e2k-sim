#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# run_hw.sh CASES OUT : data stands (dstand, built with  lcc -O2 dstand.c -o dstand  on the Elbrus machine), 2 event
# groups per stand, one core.  Case line: TAG MODE ARGS...  Output: "TAG GROUP event=count ..." (hw/d*.txt).
# Environment: CORE (7), LOCK (optional flock file for the whole list), G1/G2 event lists.  The second group of each
# result file: d1/d2/d4 l2_query,l2_hit,ticks_e2; d3 dtlb_query,dtlb_hit,dtlb_tlu_query.
set -u
cd "$(dirname "$0")"; C=$1; O=$2; CORE=${CORE:-7}
G1=${G1:-cycles:u,instructions:u,l1_query:u,l1_ld_hit:u}
G2=${G2:-cycles:u,l2_query:u,l2_hit:u,ticks_e2:u}
if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
while read tag args; do for gr in G1 G2; do
  x=$(taskset -c "$CORE" perf stat -x, -e ${!gr} ./dstand $args 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
  echo "$tag $gr $x" >> "$O"
done; done < "$C"
if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
