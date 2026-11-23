# Elbrus-8SV (e2k-v5) PMU events: what they count

Measured 2026-11-20 on an Elbrus-8SV (1.5 GHz, Linux 6.1), user mode, core 7, one run at a time.
Stands: [`stands/cal`](../stands/cal) (`stand.c`: pointer chase, sequential loads/stores, DTLB sweep, recursion;
`gencode.py` -> `code.c`: straight-line code of 5.8 KB .. 1.26 MB).  Method: perf stat per run, (run - the same run
with n = 0) / n.  Raw: `stands/cal/hw/cal1.txt`; tables: `python3 stands/cal/ana.py stands/cal/hw/cal1.txt`.
Load-use latency = cycles per dependent load of a chase.

## Data side
| event | counts | stand |
|---|---|---|
| l1_query | every L1D access: loads AND stores (1.00 per store), plus replays of a missing load (1.26 at 4 MB, 1.6-1.96 at 8-64 MB footprint) | chase, st |
| l1_ld_hit | loads that hit L1D (1.00 at 16/64 KB, 0.00 from 128 KB) | chase |
| l1_st_query | 0.73-0.86 per store (not all stores; merged stores?): do not use it to count stores | st |
| l1_st_hit | ~0 in every store stand: L1D is write-through, no store hits counted | st |
| l2_query | L1D load misses (1.0) + their replays (up to 2.2 at 64 MB) + every store (1.07, write-through) + instruction fetch requests (0.15-0.58 per instruction in big code) + page-walk loads | chase, st, code |
| l2_hit | L2 hits of all of the above including page-table walks: 1.0 at a 128 KB chase, 0.06 at 1 MB (L3), but 0.6-0.86 at 8-64 MB (the walk loads hit) -> not "data L2 hits" | chase |
| dtlb_query | 1 per access + 1 per DTLB miss (+2 per 2 MB-page miss) | tlb |
| dtlb_hit | 1 per access, always (also on a miss after the refill) -> DTLB misses = dtlb_query - dtlb_hit | tlb |
| stall_dtlb_miss, stall_dtlb | ~5 (4 KB) / ~7 (2 MB) per DTLB miss: a part of the penalty, not all of it | tlb |

## Latencies (load to use, dependent chain)
L1 3; L2 11 (+8; 128-256 KB footprint); L3 32-33 (+29; 1-2 MB); DRAM ~200 (+~180 plus DTLB, 32-64 MB, 4 KB pages).
DTLB 4 KB pages: 256 sets (VA bits 12..19) x 3 ways (3 pages 1 MB apart: no miss; 4: 0.71 miss per load); miss ~20
(page-table entry in L2) to 28 cycles.
DTLB 2 MB pages: 256 places (VA bits 21..28), 1 entry each (2 pages 512 MB apart: every load misses); miss ~36 cycles.

## Instruction side (straight-line code, 24 B per wide instruction, looped; code.c f8..f2048 = 5.8 KB .. 1.26 MB)
| code | CPI | ib_ahead_miss/insn | ib_disp_miss | ib_ahead_query | l2_query/insn | l2_hit/insn |
|---|---|---|---|---|---|---|
| 5.8K | 1.05 | 0.004 | 0 | 0.079 | 0 | 0 |
| 24K | 1.11 | 0.001 | 0 | 0.081 | 0 | 0 |
| 71K | 1.23 | 0.000 | 0 | 0.077 | 0 | 0 |
| 136K | 1.33 | 0.018 | 0.001 | 0.075 | 0.15 | 0.15 |
| 342K | 1.55 | 0.074 | 0 | 0.073 | 0.59 | 0.43 |
| 1.26M | 1.97 | 0.072 | 0 | 0.072 | 0.58 | 0.01 |

- ib_ahead_query: one per 256 B L1I line streamed by the fetch-ahead (~0.077 per instruction = 24/256 + branches).
- ib_ahead_miss: L1I misses of the fetch-ahead (every line once the code exceeds 128 KB) = the L1I miss counter.
- ib_disp_miss: ~0 in straight code; a miss at dispatch after a transfer whose target the fetch-ahead did not fetch.
  Not a cost signal (see [FETCH.md](FETCH.md)).
- Fetch penalty: an L1I miss served by L2 costs ~6.8 cycles per line, by L3 ~12.8 per line in raw cycles, mostly
  overlapped by the fetch-ahead (far below the data penalties).  In model terms (issue and nops already counted) it
  leaves 0 cycles per 256 B line from L1I, 1.0 from L2, 3.9 from L3.

## Calls (recursion depth D, cycles per call+return pair; small frame wsz 8, big wsz 12)
D 1/2/4/8/16/32/64/128: small 38/28/24/22/21/21/22/22, big 41/32/26/24/25/30/34/37.
Base ~12 cycles per call+return over 1 cycle per instruction.  `bub_b_rf_spillfill` appears from D = 16 (big) / 32
(small): register-file spill/fill ~11 cycles per call at depth 128 (big frame); `bub_b_chain_spillfill` from D = 32,
~2.4 per call at 128.

## What the model charges, checked on the same stands (qemu trace -> model vs HW CPI)
- Fetch: as above (0 / 1.0 / 3.9 per sequential line from L1I / L2 / L3).
- Calls: register file of 224 quads resident; a return into a spilled wsz-12 frame costs 13 cycles, wsz-8 frames free.
- Data L2/L3 set index hashed (a 2 MB-stride page sweep has no L2 conflicts on the 8SV; a plain modulo index
  over-predicted by 35-64 %).  Code lines use the plain index (see FETCH.md).
- A 64-bit read of a 32-bit integer result waits only for the integer latency (lcc's 1-cycle pipelined loops rely on it).
- Store -> load: measured windows for cover / part / same word / 4 KB alias; "other word of the same 32 B block" and its
  alias are switched off (they over-predicted a call-heavy benchmark by 12.7 %).
- qemu reports the hardware procedure/chain-stack spill and fill of call/return as memory accesses: the model drops them
  (they are not L1 traffic).

```
stand       CPI_hw CPI_mod     err  model split
chase16k     1.000   1.000   -0.0%  issue:100
chase256k    3.700   3.667   -0.9%  issue:27 L2:73
chase2m     11.018  10.667   -3.2%  issue:9 L3:91
chase64m    68.742  67.360   -2.0%  DRAM:89 dtlb:9
st512k       1.000   1.000   -0.0%  issue:100
seq4m        8.385   7.552   -9.9%  issue:13 nop:4 L2:18 L3:64
call8s       2.264   2.359   +4.2%  issue:42 nop:23 ctprep:15 call:20
call16b      1.686   1.660   -1.6%  issue:60 nop:9 ctprep:14 call:17
call128b     2.594   2.442   -5.9%  issue:41 nop:6 ctprep:9 call:12 spill:33
call128s     2.744   2.489   -9.3%  issue:40 nop:25 ctprep:15 call:20
tlb2048     10.544  10.333   -2.0%  issue:10 L2:26 dtlb:65
tlb300h     10.931   9.622  -12.0%  issue:10 L2:20 dtlb:69
code8        1.051   1.065   +1.3%  issue:94 nop:5
code96       1.232   1.234   +0.1%  issue:81 nop:19
code512      1.549   1.517   -2.1%  issue:66 nop:29 icache:5
code2048     1.970   1.867   -5.2%  issue:54 nop:31 icache:15
```
(model of 2026-11-20; `stands/cal/cmpstand.py` reproduces the table.  The call rows above still include a +2-cycle
call/return term that the later fetch stands removed: `SIM_CALLRET=2` restores it.)
