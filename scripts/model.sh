#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# model.sh PFX [WARM] [extra sim.py args...]
# Decode the code table of a trace (decode.py) and run the cycle model on every window of it in parallel
# -> PFX.w<N>.sim.pkl (+ .sim.log).  WARM: wide instructions at the start of each window that only warm the caches
# (default 2000000).  Environment: JOBS (parallel windows and decode workers, default 4),
# PY (python for sim.py; PyPy is ~10x faster, default python3), and decode.py's E2K_ROOT / E2K_QEMU / E2K_OBJDUMP.
set -u
P=$1; W=${2:-2000000}; shift; [ $# -gt 0 ] && shift
M=$(cd "$(dirname "$0")/../model" && pwd)
J=${JOBS:-4}; PY=${PY:-python3}
python3 "$M/decode.py" "$P" --jobs "$J" > "$P.dec.log" 2>&1 || { cat "$P.dec.log"; exit 1; }
cat "$P.dec.log"
ls "$P".w*.bin* | sed 's/.*\.w\([0-9]*\)\.bin.*/\1/' | sort -n | \
  xargs -P "$J" -I{} sh -c "$PY '$M/sim.py' '$P' {} --warm $W $* > '$P.w{}.sim.log' 2>&1"
grep -h insns "$P".w*.sim.log | awk '{n+=$2; c+=$8} END {printf "windows modelled: %d insns, %d cycles, IPC %.3f\n", n, c, n/c}'
