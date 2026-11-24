#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build.sh [CASES] : build the code+data stands into bin/<tag> (on the Elbrus machine, or with an e2k cross lcc).
# Case line: TAG N F R ORDER CH D  ->  ../dispatch/gen3.py N F R ORDER 1 CH + main2.c.  Environment: CC, NICE.
set -u
cd "$(dirname "$0")"; mkdir -p bin
CC=${CC:-lcc}; NICE=${NICE:-nice -n 19}
grep -v '^#' "${1:-cases.txt}" | while read tag n f r o ch d; do
  [ -x bin/$tag ] && continue
  python3 ../dispatch/gen3.py $n $f $r $o 1 $ch > bin/$tag.s && $NICE $CC -O1 main2.c bin/$tag.s -o bin/$tag || echo FAIL $tag
done
