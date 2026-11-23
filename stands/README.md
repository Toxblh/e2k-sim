# Stands

Small programs with a known instruction stream, measured on an Elbrus-8SV with `perf stat` and traced + modelled
through the same pipeline as any program.  The results here were measured on one Elbrus-8SV (1.5 GHz, Linux 6.1),
user mode, core 7, with no other timing job running (all runs of a group under one `flock`).

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

## probe/ — qemu correctness and kernel checks
- `mc.c`, `mc2.c`, `aau.c`, `aadrw.c`: memcpy/memmove and AAU register behaviour (run on the hardware and under qemu;
  the outputs must match; see qemu/README.md).
- `thpx.c`: does the kernel give transparent huge pages to executable anonymous memory? (On the 8SV: no.)
