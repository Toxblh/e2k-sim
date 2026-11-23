#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build.sh CASES... : build every stand of the case lists into bin/<tag> (on the Elbrus machine, or with an e2k cross lcc).
# Case line: TAG asm KIND K F D ALIGN OFF DISTD ITERS   (gen.py stand + main.c)
#            TAG c   K ITERS                             (genc.py call stand)
# Environment: CC (default lcc), NICE (default "nice -n 19").
set -u
cd "$(dirname "$0")"; mkdir -p bin
CC=${CC:-lcc}; NICE=${NICE:-nice -n 19}
cat "$@" | while read tag typ a b c d e f g h; do
  [ -x bin/$tag ] && continue
  if [ $typ = asm ]; then python3 gen.py $tag $a $b $c $d $e $f $g > bin/$tag.s && $NICE $CC -O1 main.c bin/$tag.s -o bin/$tag || echo FAIL $tag
  else python3 genc.py $a 8 > bin/$tag.c && $NICE $CC -O2 bin/$tag.c -o bin/$tag || echo FAIL $tag; fi
done
