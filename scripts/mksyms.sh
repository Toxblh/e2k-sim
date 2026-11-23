#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# mksyms.sh OUTDIR BINARY [LIBRARY...] : symbol tables for report.py (OUTDIR/<basename>.nm).
# The main binary gets `nm -l` (source file after a tab, for SIM_LAYERS src rules) when it has debug info,
# libraries `nm -D`.  Environment: NM = an nm that reads e2k ELF files (the e2k binutils nm, natively or as
# "qemu-e2k -L ROOT ROOT/usr/bin/nm"); default nm.
set -u
O=$1; B=$2; shift 2; mkdir -p "$O"
NM=${NM:-nm}
$NM -l --defined-only "$B" > "$O/$(basename "$B").nm" 2>/dev/null || $NM --defined-only "$B" > "$O/$(basename "$B").nm"
for L in "$@"; do $NM -D --defined-only "$L" > "$O/$(basename "$L").nm"; done
wc -l "$O"/*.nm
