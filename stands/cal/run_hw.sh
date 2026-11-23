#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# run_hw.sh OUT : every line of runs.txt (TAG<tab>GROUP<tab>EVENTS<tab>COMMAND) under perf stat on one core
# (on the Elbrus machine, in this directory after:  lcc -O2 stand.c -o stand; python3 gencode.py > code.c; lcc -O2 code.c -o code)
# Environment: CORE (default 7), LOCK (optional flock file, taken per run).
set -u
cd "$(dirname "$0")"; O=$1; CORE=${CORE:-7}
while IFS=$'\t' read -r tag g ev cmd; do
  if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
  r=$(eval "taskset -c $CORE perf stat -x, -e $ev $cmd" 2>&1 >/dev/null | awk -F, '/:u/{printf "%s=%s ", $3, $1}')
  if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
  echo "$tag $g $r" >> "$O"
done < runs.txt
