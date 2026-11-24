# Stands

Small programs with a known instruction stream, measured on an Elbrus-8SV with `perf stat` and traced + modelled
through the same pipeline as any program.  The results here were measured on one Elbrus-8SV (1.5 GHz, Linux 6.1),
user mode, core 7, with no other timing job running (all runs of a group under one `flock`).  Other cores were not idle
for the later stands (dispatch, l2code, spec, data, identity): their L3/DRAM numbers include that sharing.

## fetch/ — instruction supply (docs/FETCH.md)
- `gen.py NAME KIND K F D ALIGN OFF DISTD` writes an assembly stand `long stand(long iters)`; `main.c` calls it.
  `genc.py K PAD` writes a C call stand.  `build.sh CASES...` builds `bin/<tag>` with lcc (on the Elbrus machine).
- Case lists (`TAG asm KIND K F D ALIGN OFF DISTD ITERS` or `TAG c K ITERS`) and the raw hardware results:

| case list | stands | HW result (`hw/`) | events |
|---|---|---|---|
| `cases1.txt` | dist, prep, ibr, align, foot, foot1, ibrfoot, call, far (58) | `fetch1.txt` (`far*` repeated in `fetch2.txt`); table `ana.txt` | cycles, instructions, ib_disp_miss, ib_ahead_miss / ib_disp_query, ib_ahead_query, bub_b |
| `cases3.txt` | itlb_P16..P96: P code pages 4 KB apart | `itlb.txt` | + ib_disp_itlb_miss, ib_ahead_itlb_miss |
| `cases4.txt` | span_D4096_K8..: K targets 4 KB apart | `span.txt` | + l2_query |
| `cases5.txt` | sp_S<stride>_K<n>_{a,s}: K targets at stride S (`_a`) or S+64 (`_s`) | `span2.txt` | + ib_ahead_query, ib_disp_itlb_miss |
| `cases6.txt` | it1m/itct K2..K8: targets 1 MB+512 apart vs 1 MB+4.5 KB (control) | `itlb6.txt` (first run) | G1/G2 as `run_hw.sh` |
| `cases8.txt` + `sp_*` of `cases7.txt` | ITLB set/way and L2-set stands | `itlb8.txt` (2 rounds, one lock hold); table `itlb8_ana.txt` | G1/G2 as `run_hw.sh` |

- `run_hw.sh OUT CASES...` measures (CORE, ROUNDS, LOCK env), `ana.py` / `ana8.py` make the per-transfer tables.
- `trace.sh OUTDIR CASES...` traces and models every stand (on the qemu host, with `bin/` copied there);
  `fcmp.py OUTDIR hw/fetch1.txt hw/span2.txt hw/itlb.txt hw/itlb8.txt` compares; `hw/model_vs_hw.txt` is the result
  for the model defaults (138 stands).

## cal/ — PMU events, latencies, calls, code size (docs/EVENTS.md)
- `stand.c` (chase / seq / st / tlb / call modes), `gencode.py > code.c` (straight-line code of 8..2048 KB).
- `runs.txt` lists runs as `TAG<tab>GROUP<tab>EVENTS<tab>COMMAND` (the last batch; `hw/cal1.txt` holds all batches
  in the same format), `run_hw.sh OUT` measures them, `ana.py hw/cal1.txt` makes the tables.
- `stands.txt` names the 16 stands that were traced and modelled; `cmpstand.py hw/cal1.txt SIMDIR` compares.

## dispatch/ — taken transfers in large, irregular code (FACTS.md "sim3")
- `gen3.py N F R ORDER SEED [CH]`: a chain of N blocks of F commands, each `ct` prepared 5 commands ahead, block k in
  slot k of an R-byte region at a random offset; ORDER `rand` (random permutation) or `seq` (address order: every
  transfer is a taken jump into the next line - the next-line fetch case).  `build.sh`, `run_hw.sh OUT` (3 groups x 2
  rounds), `trace.sh OUTDIR`, `dcmp.py hw/hw1.txt SIMDIR` (extra cycles and events per transfer).
- `cases.txt` (20 stands: N 256/1024/4096, R 256K/1M/4M, F 6/8) -> `hw/hw1.txt`; `hw/model_vs_hw.txt`: sim.py and
  sim3.py per transfer, plus the CPI error over these and the 138 `fetch/` stands.

## l2code/ — data L2 hits next to code refills
- `../dispatch/gen3.py ... CH=1` + `main2.c`: every block also loads the next node of a random pointer ring of D bytes.
  Code footprint small (N64 R16K), streamed from L2 (N1024 R256K seq) or random over 1 MB; D = 0 / 256 KB / 4 MB.
- `cases.txt` -> `hw/hw2.txt` (groups add ticks_e2, l1_line); `cmp.py hw/hw2.txt SIMDIR...`; `hw/model_vs_hw.txt`
  for sim.py, sim3.py and sim3.py with SIM_L2XC=24.

## spec/ — speculative loads (ldd,sm) to invalid pages
- `gen.py ADDR USE [STEP]`: 2 speculative loads per 8-command iteration; USE=1 adds a speculative add of their
  results 3 commands later; STEP moves the address every iteration (a new page each time).  `build.sh` (the variants:
  null, unmapped, kernel address, own code = valid, 4 KB and 2 MB steps), `run_hw.sh OUT STAND...`.
- `hw/spec1.txt` (one invalid page; `valid` = 0x600000 was in fact unmapped), `hw/spec2.txt` (valid `own`/`ownuse`),
  `hw/spec3.txt` (a new invalid page every iteration, and the valid control).

## data/ — L1D/L2/L3/DTLB checks
- `dstand.c` modes: `stld` / `ldonly` (store a buffer, reload it), `assoc K S N` (chase over K lines S apart),
  `stride`, `mix P Q N` (P 4 KB + Q 2 MB pages), `chst F N K` (chase with K stores per step).  `run_hw.sh CASES OUT`.
- `cases1..4.txt` -> `hw/d1..d4.txt`.  d1: L1D associativity (its stld/ldonly lines used array-prefetch loads that bypass
  L1D; d2 repeats them with data-dependent scalar loads); d3: mixed DTLB (second group dtlb_query, dtlb_hit,
  dtlb_tlu_query); d4: chase + stores.  `run_l3.sh OUT` -> `hw/l3.txt` (chase 1..32 MB with other jobs running on
  other cores: effective L3 share).  `hw/cal3.txt`: l1_request / l1_line / l1_int_hit / l2_line / dtlb_tlu_query on
  ../cal stands (what those events count).

## identity/ — the top-down cycle identity (docs/IDENTITY.md)
- `run_hw.sh OUT`: cycles, instructions, bub_b, ticks_e2, ib_no_command, bub_b_nop on calibration and fetch stands.
  `hw/bub_cal.txt` (also bub_e0, ticks_e0, bub_e2_mem/opnd, stall_dtlb, ... groups), `hw/bub_fetch.txt`.
- `setwd_gen.py` + `hw/setwd.txt`: call stands whose callees open 8..26-quad windows, with and without setbn: no
  bub_b_hwcmd (the w4 rows failed to run).

## probe/ — qemu correctness and kernel checks
- `mc.c`, `mc2.c`, `aau.c`, `aadrw.c`: memcpy/memmove and AAU register behaviour (run on the hardware and under qemu;
  the outputs must match; see qemu/README.md).
- `thpx.c`: does the kernel give transparent huge pages to executable anonymous memory? (On the 8SV: no.)
