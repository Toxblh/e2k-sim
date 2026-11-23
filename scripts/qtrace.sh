#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# qtrace.sh OUTPFX PLUGINARGS -- CMD...
# Run an e2k Linux program under qemu-e2k (user mode) with the etrace plugin; host ASLR off (setarch -R) so that
# repeated runs see the same addresses.  PLUGINARGS: e.g. skip=1000000,win=2000000,period=20000000,nwin=10
# Writes OUTPFX.code/.info/.maps/.w<N>.bin.zst (plugin), OUTPFX.stdout/.stderr, OUTPFX.done (rc, wall seconds).
# Environment:
#   E2K_QEMU     qemu-e2k binary built with the patch (default: qemu-e2k in PATH)
#   E2K_SYSROOT  e2k root with the guest's shared libraries (qemu -L), default ~/e2k-root
#   ETRACE       the plugin, default <repo>/plugin/libetrace.so
#   PIN          optional CPU list for taskset (a multi-threaded guest runs on these host CPUs)
set -u
O=$1; PA=$2; shift 3
HERE=$(cd "$(dirname "$0")/.." && pwd)
Q=${E2K_QEMU:-qemu-e2k}
ROOT=${E2K_SYSROOT:-$HOME/e2k-root}
P=${ETRACE:-$HERE/plugin/libetrace.so}
command -v zstd >/dev/null || { echo "qtrace.sh: zstd not in PATH (the plugin pipes records through it)" >&2; exit 1; }
mkdir -p "$(dirname "$O")"
s=$(date +%s.%N)
${PIN:+taskset -c $PIN} setarch "$(uname -m)" -R "$Q" -L "$ROOT" -plugin "$P,out=$O,$PA" "$@" > "$O.stdout" 2> "$O.stderr"
rc=$?
echo "rc=$rc wall=$(python3 -c "import time; print(round(time.time()-$s,1))")" > "$O.done"
exit $rc
