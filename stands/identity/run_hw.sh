#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# run_hw.sh OUT : the top-down events on calibration and fetch stands (docs/IDENTITY.md), one core, groups of 4 events.
# Needs ../cal/stand, ../cal/code (see ../cal/run_hw.sh) and ../fetch/bin (../fetch/build.sh).  Output lines:
# "TAG event=count ..." (hw/bub_cal.txt, hw/bub_fetch.txt).  Environment: CORE (7), LOCK (optional flock file).
set -u
cd "$(dirname "$0")"; O=$1; CORE=${CORE:-7}
GS="cycles:u,instructions:u,bub_b:u,ticks_e2:u cycles:u,ib_no_command:u,bub_b_nop:u,ib_disp_miss:u"
if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
while read tag dir cmd; do for g in $GS; do
  x=$(cd $dir && taskset -c "$CORE" perf stat -x, -e $g $cmd 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
  echo "$tag $x" >> "$O"
done; done <<'L'
chase16k ../cal ./stand chase 16384 20000000
chase2m ../cal ./stand chase 2097152 10000000
chase64m ../cal ./stand chase 67108864 2000000
code2048 ../cal ./code 2048 7455
code96 ../cal ./code 96 135424
call128b ../cal ./stand call 128 1 156250
tlb2048 ../cal env NOFILL=1 ./stand tlb 2048 4096 10000000 0
prep_d1_near ../fetch bin/prep_d1_near 2040816
prep_d5_near ../fetch bin/prep_d5_near 1754385
ibr_D0 ../fetch bin/ibr_D0 2040816
far64_D65536 ../fetch bin/far64_D65536 150000
call_K64 ../fetch bin/call_K64 260416
it1m_K8 ../fetch bin/it1m_K8 816326
L
if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
