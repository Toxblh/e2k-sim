#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build.sh : the speculative-load stands (on the Elbrus machine): TAG ADDR USE [STEP].  "own*" load from the stand's
# own code (a valid address); "valid" (0x600000) turned out to be unmapped in this binary (l1_query ~0 in hw/spec1.txt).
set -u
cd "$(dirname "$0")"; mkdir -p bin
CC=${CC:-lcc}
while read tag addr use step; do
  python3 gen.py $addr $use $step > bin/$tag.s || continue
  case $tag in own*) sed -i 's/_f64 0x[0-9a-f]*, %r7/_f64 stand, %r7/' bin/$tag.s ;; esac
  $CC -O1 ../fetch/main.c bin/$tag.s -o bin/$tag || echo FAIL $tag
done <<'L'
valid 0x600000 0
null 0x0 0
nulluse 0x0 1
unmap 0x7ff000000000 0
unmapuse 0x7ff000000000 1
kern 0xe20000000000 0
own 0x0 0
ownuse 0x0 1
sunmap 0x7ff000000000 0 4096
sunmapuse 0x7ff000000000 1 4096
hunmap 0x7ff000000000 0 2097152
hunmapuse 0x7ff000000000 1 2097152
L
