# Instruction supply on Elbrus-8SV: what a taken transfer costs

Measured 2026-11-21..23 on an Elbrus-8SV (e2k-v5, 1.5 GHz, Linux 6.1), user mode, one core (`taskset -c 7`), one
stand run at a time (no other timing job on the machine).

Stands: [`stands/fetch`](../stands/fetch) — `gen.py` writes assembly chains of K blocks of F commands, each block
ending in a taken transfer to the next block (`disp`+`ct` prepared d commands before, or an unprepared `ibranch`),
with a chosen distance, alignment and offset of the targets; `genc.py` writes K C functions called in turn.
Raw counters: `stands/fetch/hw/*.txt`; per-transfer table `stands/fetch/hw/ana.txt` (cycles per taken transfer beyond
1 cycle per command, events per transfer) and `stands/fetch/hw/itlb8_ana.txt`.

| case | extra cycles per taken transfer | stands | what decides it |
|---|---|---|---|
| `ct` prepared by `disp` d commands earlier, target in L1I | 3.65 / 2.7 / 1.8 / 1.0 / 0.1 for d = 1/2/3/4/>=5 | `prep_d*` | max(0, 5-d); target distance 64 B..4 KB, alignment and a sequential footprint up to 1.4 MB have no effect |
| unprepared `ibranch`, target in L1I | 5.4 (tight loop) .. 6.0 | `ibr_D*`, `ibrfoot_K*` | 6 minus the command's own stall |
| call + return (lcc -O2 code, prepared early) | ~3.4 per transfer | `call_K*` | nothing beyond the ct preparation and the callee's own nops |
| target misses L1I, line served by L2 (8 blocks 64 KB apart) | +9.3 | `dist_D65536`, `far16_D65536` | dispatch waits for the whole refill (the fetch-ahead cannot help a taken target) |
| target line evicted from L2 by a set conflict, served by L3 | ~+35 | `sp_S*_K*_a` (itlb8) | code lines index L2 by VA bits 6..16, unhashed, 4-way: >4 target lines at a power-of-two stride >= 16 KB share an L2 set |
| target page misses the ITLB | ~+27..30 on top | `it1m_K*`, `it256k_K8`, `it512k_K8` (itlb8) | ITLB = 64 sets (VA bits 12..17) x 5 ways: K <= 5 pages of one colour are free, 6 partly and 8 always miss; the walk's load hits L2 (`l2_hit` 0.88 per transfer) |
| sequential code missing L1I | +1.0 (L2) / +3.9 (L3) per 256 B line | `code*` (stands/cal) | the fetch-ahead streams it |
| target in the last 8 bytes of a 256 B line | +0.5 | `align_off248` | the next line is needed at once |

Distance and alignment are otherwise free (`dist_D0..4096`, `align_off0..224` all at 1.0 +- 0.15 per transfer).

L1I behaves as 2-way for these patterns (8 targets 64 KB+64 apart thrash; sysfs says 4-way, 128 KB, 256 B lines);
4 KB+64 strides never miss.  Targets at 64 KB / 128 KB strides spread over ITLB sets and cost nothing
(`it64k_K8`, `it128k_K8`); 256 KB, 512 KB and 1 MB strides put every page in one set (`it256k_K8` = `it1m_K8`).
The wide-span cases (`far64`, `far256`, `sp_S65536_K32_a`: +22..53 per transfer) are the L2-set and ITLB-set
conflicts above together.

**Not a cost signal:** `ib_disp_miss` (and `ib_disp_itlb_miss`) fire 0.1-0.34 per transfer in every stand, also when the
transfer costs nothing (`prep_d5..d8`, `foot_K*` up to 1.4 MB).  A large program's 80-120 `ib_disp_miss` per 1000
instructions therefore say nothing about lost cycles; an earlier model version that charged a fixed penalty per such
event was wrong in principle.

**What costs in real code:** (1) a `ct` prepared fewer than 5 commands before it (5-d each time); (2) an unprepared
`ibranch` (~6); (3) a taken transfer whose target line is not in L1I (+9 from L2, ~+35 from L3) or whose page is not
in the ITLB (~+27): large code reached by jumps rather than by straight-line fetch, made worse by hot code placed at
power-of-two distances (L2 sets) or more than 5 hot pages of one 4 KB colour modulo 256 KB (ITLB sets).

Model (`model/sim.py`, defaults): ctpr preparation and ibranch as above; fetch: sequential misses 1.0 / 3.9, taken-target
misses 9.3 (L2) / 35 (L3), ITLB 64x5 on VA bits 12..17 with +27 at a taken target, L1I 2-way 256 B lines, L2 index for
code lines VA bits 6..16 unhashed.  All 138 fetch stands: median |error| 1.5 %, 90th percentile 23.3 %
(see [ACCURACY.md](ACCURACY.md) for the misses).
