# Model accuracy

## Stands (138 fetch/ITLB/L2 stands of `stands/fetch`, model defaults)

Each stand: qemu trace (skip 2 M, one 6 M window), model with a 2 M warm-up, CPI vs the CPI that perf stat measured on
the Elbrus-8SV.  Full table: [`stands/fetch/hw/model_vs_hw.txt`](../stands/fetch/hw/model_vs_hw.txt)
(`python3 stands/fetch/fcmp.py SIMDIR stands/fetch/hw/{fetch1,span2,itlb,itlb8}.txt` rebuilds it).

**median |error| 1.5 %, 90th percentile 23.3 %, n = 138.**

The known misses (|error| > 20 %), all instruction-supply corner cases:

| stand | HW CPI | model CPI | error | what the model lacks |
|---|---|---|---|---|
| `far256_D16384` | 5.541 | 1.594 | -71.2 % | 256 targets 16 KB+64 apart over 4 MB: HW pays ~+22 per transfer, the model sees no L1I/L2/ITLB conflict |
| `it1m_K6` | 3.754 | 1.171 | -68.8 % | 6 pages in one ITLB set: HW thrashes partly (25 cycles per transfer), a 5-way LRU model hits always or misses always |
| `sp_S16384_K{8,16,32,64}_s` | 1.7-3.7 | 1.18-1.20 | -31 .. -68 % | targets at a 16 KB+64 stride: an extra conflict on HW not identified (not L1I, not ITLB by the counters) |
| `sp_S65536_K{32,64}_s` | 5.7 / 11.3 | 4.0 / 8.1 | -30 / -28 % | same family as above at 64 KB+64 |
| `dist_D16384` | 1.659 | 1.176 | -29.1 % | same family (8 targets 16 KB+64 apart) |
| `sp_S16384_K8_a` | 2.599 | 2.018 | -22.4 % | partial L2-set conflict |
| `sp_S65536_K8_a` | 3.700 | 6.220 | +68.1 % | the model sends 8 lines of one L2 set to L3; HW keeps more of them in L2 (replacement not plain LRU) |
| `sp_S32768_K16_a` | 3.958 | 5.270 | +33.2 % | same |
| `far16_D65536` | 2.945 | 3.858 | +31.0 % | 16 targets 64 KB+64 apart: the model's 2-way L1I misses more than HW |
| `sp_S65536_K16_s` | 2.985 | 3.858 | +29.3 % | same |
| `dist_D65536` | 3.001 | 3.700 | +23.3 % | same |
| `ibr_D65536` | 3.654 | 4.484 | +22.7 % | same, with unprepared ibranch |
| `sp_S65536_K8_s` | 3.050 | 3.700 | +21.3 % | same |

The ITLB stands other than `it1m_K6` are within +-4 %; the thrashing ones (`it*_K8`) are -10 % (HW miss cost ~+30
vs the model's +27).

## Calibration stands (`stands/cal`)
16 data/code/call/TLB stands within -12 .. +4 % (table in [EVENTS.md](EVENTS.md)).

## Whole programs
- `examples/bench` (C, 5 kernels, 0.31 G wide instructions): model 0.602 G cycles vs HW 0.609 G: **-1.1 %**
  (62 windows of 2 M, 30 % of the run).  Per symbol the model is off by up to ~5 points of the run: the memory-bound
  hash lookups are over-predicted ~2x, the store-heavy shuffle in `run_chase` under-predicted (see the example).
- Earlier validation (same model family, a JavaScript engine's workloads, not included): six small workloads within
  -3.4 .. +9.3 %; five large applications -10 .. +11 % with an older, since refuted ITLB model.  The re-check of the large
  applications with the current ITLB/L2 model was not finished when this repository was prepared.
- qemu-e2k with the patch executes the same number of wide instructions as the hardware (`instructions:u`) within
  +-1.6 % on the large single-threaded programs checked, +0.3 % on a memcpy probe and +0.0004 % on `examples/bench`;
  programs whose own decisions depend on time (a JIT compiling after N ms) can differ by more (4 % seen).

## Limitations
- One core, user mode only: no kernel time, no other threads' interference; only the main thread (vcpu 0) is traced.
- Sampled windows: each window starts with cold caches and TLBs, warmed by the first `--warm` instructions; a symbol that runs
  only between windows is invisible.
- No branch prediction model (e2k has none for prepared transfers; unprepared `ibranch` is charged a fixed cost).
- Store path: stores never stall (write-through L1D, no store-buffer model); store-heavy code is under-predicted.
- DRAM: a fixed +180; no bandwidth, no prefetcher, no page-walk cache model beyond the DTLB costs.
- Code-line DRAM costs are estimates; L2 replacement is LRU (HW is not, see the `sp_S*_a` misses).
- Event counters of the model (`mem` in the .sim.pkl) do not have the HW events' semantics (see EVENTS.md).
