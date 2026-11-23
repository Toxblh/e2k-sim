# Elbrus-8SV (e2k-v5) facts used by the model

All measured on one Elbrus-8SV (E8C2, 1.5 GHz, Linux 6.1.180), user mode, one core, one timing job at a time.
"Stand" names the program and its result file in this repository that show the fact; every row can be re-measured
with the scripts in `stands/`.  Cycles are core cycles; "+N" is the cost on top of 1 cycle per wide instruction.

| fact | value | stand (source -> raw result) |
|---|---|---|
| load-to-use latency L1D | 3 | `stands/cal/stand.c chase 16384` -> `stands/cal/hw/cal1.txt` |
| load-to-use latency L2 | 11 (+8) | `stand chase 131072..262144` -> cal1.txt |
| load-to-use latency L3 | 32-33 (+29) | `stand chase 1048576..2097152` -> cal1.txt |
| load-to-use latency DRAM | ~200 (+~180, plus DTLB misses) | `stand chase 33554432..67108864` -> cal1.txt |
| L1D is write-through | `l1_st_hit` ~0 for every store pattern; every store is an `l2_query` (1.07 per store) | `stand st F N` -> cal1.txt |
| DTLB, 4 KB pages | 256 sets (VA 12..19) x 3 ways; miss ~20-28 | `stand tlb P 1048576 N 0`, `tlb 2048 4096` -> cal1.txt |
| DTLB, 2 MB pages | 256 places (VA 21..28) x 1; miss ~36 | `stand tlb P 536870912 N 1`, `tlb 300 2097152` -> cal1.txt |
| data L2/L3 set index is hashed | no conflicts for 2 MB-stride page sweeps | `stand tlb 300 2097152 N 1` -> cal1.txt |
| taken `ct` prepared d commands before it | +max(0, 5-d): 3.65 / 2.7 / 1.8 / 1.0 / 0.1 for d = 1..5 | `stands/fetch` `prep_d*` -> `hw/fetch1.txt`, `hw/ana.txt` |
| unprepared taken `ibranch` | +5.4 (tight loop) .. +6.0 | `ibr_D*`, `ibrfoot_K*` -> fetch1.txt |
| call + return, lcc code | no cost beyond ct preparation and the callee's nops (~3.4 per transfer) | `call_K*` (genc.py) -> fetch1.txt |
| taken target missing L1I (line in L2) | +9.3; L1I behaves 2-way for target lines (sysfs: 128 KB 4-way 256 B) | `dist_D65536`, `far16_D65536` -> fetch1.txt, fetch2.txt |
| L2 for code lines | 4-way, set index VA bits 6..16, unhashed: >4 target lines at a >=16 KB power-of-two stride go to L3 | `sp_S*_K*_a` -> `hw/itlb8.txt`, `hw/itlb8_ana.txt` (`l2_hit` vs `l2_query`) |
| taken target from L3 | ~+35 | `sp_S16384_K64_a`, `sp_S32768_K32_a` -> itlb8.txt |
| ITLB | 64 sets (VA bits 12..17) x 5 ways; a miss at a taken target ~+27..30 (the walk load hits L2) | `it1m_K2..K8`, `itct_K*`, `it64k/128k/256k/512k_K*` -> itlb8.txt, itlb8_ana.txt |
| `ib_disp_miss` | fires 0.1-0.34 per taken transfer also when the transfer costs nothing: not a cost signal | `prep_d5..d8`, `foot_K*` -> fetch1.txt, ana.txt |
| target alignment and distance | free, except a target in the last 8 B of a 256 B line: +0.5 | `align_off0..248`, `dist_D0..4096` -> fetch1.txt |
| sequential code missing L1I | +1.0 (L2) / +3.9 (L3) per 256 B line beyond issue and nops (fetch-ahead) | `stands/cal/code.c` (gencode.py) `code 96..2048` -> cal1.txt |
| register file spill/fill | from call depth 16 (big frames) / 32 (small); ~11 cycles per call at depth 128 | `stand call D W N` -> cal1.txt |
| THP for executable anonymous memory | refused by the e2k kernel: `rw` 8 MB gets AnonHugePages, `rwx` gets 0 KB and `MADV_COLLAPSE` fails | `stands/probe/thpx.c` |

Also measured, with stands that are not part of this repository (earlier work on the same machine):

| fact | value |
|---|---|
| register latencies by producer/consumer class and lane | the table in `model/e2kdis.py` `reg_lat` (int 1, other lane 2; load 3/4; int mul 4-6; fp 4-6; fdiv 13/16; qp/packed 1 own lane, 4 other) |
| early consumer | waits in quanta of 4 cycles; predicates and transfers wait exactly what is missing |
| store -> load | a load of bytes stored 0-1 (cover) / 0-3 (partial, same 8 B) / 0-4 (4 KB alias) cycles earlier: result latency 11; a load crossing 32 B +4; a store crossing 8 B +4 |
| `ct` after `movtd` / `return` | 9 / 6 cycles of preparation (taken) |

Not measured, model estimates: DRAM cost of a code line (sequential 30, taken target 185).
