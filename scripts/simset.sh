#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# simset.sh SRCDIR OUTDIR "ENV" RUN... : model every window of SRCDIR/RUN (already decoded) into OUTDIR under a model
# variant or layout given as environment assignments, e.g. "SIM_LAYOUT=/tmp/lay.pkl" or "SIM_ITLB=256:1:12".
# OUTDIR gets links to RUN.info/.dec.pkl/.maps/.perfmap so that report.py/apps.py/supply.py work on it.
# Environment: JOBS (default 4), PY (default python3), WARM (default 2000000), SIMPY (sim.py or sim3.py),
#              WSTEP=2 to model only even-numbered windows (cheap paired comparisons with laygain.py).
set -u
S=$1; O=$2; E=$3; shift 3; mkdir -p "$O"
M=$(cd "$(dirname "$0")/../model" && pwd)
J=${JOBS:-4}; PY=${PY:-python3}; WARM=${WARM:-2000000}; WS=${WSTEP:-1}
S=$(cd "$S" && pwd)
for r in "$@"; do for x in info dec.pkl maps perfmap; do [ -e "$S/$r.$x" ] && ln -sf "$S/$r.$x" "$O/$r.$x"; done; done
for r in "$@"; do ls "$S/$r".w*.bin* | sed 's/.*\.w\([0-9]*\)\.bin.*/\1/' | awk -v s=$WS '$1 % s == 0' | sed "s#^#$r #"; done | \
  xargs -P "$J" -L1 sh -c "[ -f '$O'/\$0.w\$1.sim.pkl ] || env $E $PY '$M/${SIMPY:-sim.py}' '$S'/\$0 \$1 --warm $WARM --out '$O'/\$0.w\$1.sim.pkl > /dev/null 2>&1"
echo done > "$O/done"
