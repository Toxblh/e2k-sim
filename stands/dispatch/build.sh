#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build.sh [CASES] : build every dispatch stand into bin/<tag> (on the Elbrus machine, or with an e2k cross lcc).
# Case line: TAG N F R ORDER ITERS  ->  gen3.py N F R ORDER 1 + ../fetch/main.c.  Environment: CC (default lcc), NICE.
set -u
cd "$(dirname "$0")"; mkdir -p bin
CC=${CC:-lcc}; NICE=${NICE:-nice -n 19}
grep -v '^#' "${1:-cases.txt}" | while read tag n f r o it; do
  [ -x bin/$tag ] && continue
  python3 gen3.py $n $f $r $o 1 > bin/$tag.s && $NICE $CC -O1 ../fetch/main.c bin/$tag.s -o bin/$tag || echo FAIL $tag
done
