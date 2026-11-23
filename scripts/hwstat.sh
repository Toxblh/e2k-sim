#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# hwstat.sh NAME ROUNDS -- CMD...  (on the Elbrus machine): user-mode cycles and wide instructions of CMD,
# ROUNDS times, one line per round in the format hwcmp.py reads:  NAME cycles=C instructions=I scope=all
# Environment: CORE (taskset CPU, default 7), LOCK (optional flock file: hold it for the measurement so that other
#              timing jobs do not run at the same time), EVENTS (default cycles:u,instructions:u).
set -u
N=$1; K=$2; shift 3
CORE=${CORE:-7}; EV=${EVENTS:-cycles:u,instructions:u}
for r in $(seq "$K"); do
  if [ -n "${LOCK:-}" ]; then exec 9>"$LOCK"; flock 9; fi
  x=$(taskset -c "$CORE" perf stat -x, -e "$EV" "$@" 2>&1 >/dev/null | awk -F, '/:u/{sub(":u","",$3); printf "%s=%s ", $3, $1}')
  if [ -n "${LOCK:-}" ]; then flock -u 9; exec 9>&-; fi
  echo "$N ${x}scope=all"
done
