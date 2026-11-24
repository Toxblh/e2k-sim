#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# run_l3.sh OUT : dependent chase over 1..32 MB with ../cal/stand (effective L3 share; hw/l3.txt).  Cycles per load =
# (cycles - cycles of the same run with 0 loads) / N.  Environment: CORE (7), LOCK (optional).
set -u
cd "$(dirname "$0")"; O=$1; CORE=${CORE:-7}; N=4000000
if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
for F in 1048576 2097152 4194304 6291456 8388608 12582912 16777216 33554432; do
  x=$(taskset -c "$CORE" perf stat -x, -e cycles:u,instructions:u,l2_hit:u,l2_query:u ../cal/stand chase $F $N 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
  y=$(taskset -c "$CORE" perf stat -x, -e cycles:u ../cal/stand chase $F 0 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
  echo "chase $F $N $x | zero $y" >> "$O"
done
if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
