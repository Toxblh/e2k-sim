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
  applications with the current ITLB/L2 model: see "Large programs (sim3)" below.
- qemu-e2k with the patch executes the same number of wide instructions as the hardware (`instructions:u`) within
  +-1.6 % on the large single-threaded programs checked, +0.3 % on a memcpy probe and +0.0004 % on `examples/bench`;
  programs whose own decisions depend on time (a JIT compiling after N ms) can differ by more (4 % seen).

## Large programs (sim3)

Five large JavaScript applications (`tsc`, `terser`, `prettier`, `babel`, `eslint` run by a JavaScript engine with a
JIT; not included), main thread, 20-25 G wide instructions each, 34-57 windows of 12 M (4 M warm-up) at 600 M
intervals (sim3.py: the even-numbered half); hardware = `perf stat -i` cycles:u, average of 2 runs on core 7.  G cycles:

| app | HW | sim.py | error | sim3.py | error |
|---|---|---|---|---|---|
| tsc | 55.42 | 43.67 | -21.2 % | 49.28 | -11.1 % |
| terser | 19.11 | 16.24 | -15.0 % | 18.78 | -1.7 % |
| prettier | 58.48 | 48.57 | -16.9 % | 57.87 | -1.0 % |
| babel | 64.98 | 51.04 | -21.5 % | 63.26 | -2.6 % |
| eslint | 43.47 | 36.99 | -14.9 % | 40.48 | -6.9 % |

sim3.py with `SIM_ISUB=4 SIM_NEXTN=2 SIM_INFL=1 SIM_SEQT=4:16 SIM_SPEC=12 SIM_L2XC=24` and a pages file with the THP
fractions read from smaps (even-numbered windows).  **`SIM_L2XC=24` is fitted on these applications, not measured**
(docs/FACTS.md); without it sim3.py gives -16.2 / -6.2 / -6.9 / -11.4 / -11.5 %.  The hardware numbers move by up to
+-4 % between runs because other cores of the machine were busy (shared L3 and DRAM).

Term by term ([IDENTITY.md](IDENTITY.md)), the gap of sim.py (HW - model, G) was mostly in E2 stalls, not in
instruction supply:

| app | gap | ticks_e2 | bub_b (not nops) | ib_no_command |
|---|---|---|---|---|
| tsc | 14.3 | 11.6 | 1.9 | 1.0 |
| terser | 3.3 | 2.6 | 0.7 | 0.25 |
| prettier | 12.4 | 9.3 | 2.0 | 0.9 |
| babel | 14.4 | 11.2 | 2.4 | 0.75 |
| eslint | 8.2 | 6.0 | 1.4 | 0.6 |

What sim3.py recovers (G): the fetch settings raise ib_no_command to the hardware's (tsc 9.18 vs 9.56, terser 3.28 vs
3.34, prettier 10.49 vs 9.78, babel 13.54 vs 12.52, eslint 6.43 vs 6.51); whole 256 B code lines in L2 +0.55..1.6;
used speculative loads of invalid pages +0.8..1.0; partial THP +0.1; data L2 hits next to code refills (fitted)
+0.9..5.7.

Stands with sim3.py's fetch settings: the 138 stands of `stands/fetch` median 1.5 %, 90th percentile 15.7 % (sim.py
23.1 %); the 20 dispatch stands median 11.9 % (sim.py 25.1 %), still low on 256-block chains whose lines would all fit
L1I (HW misses on every transfer) and on taken jumps into the next line from L3 (`stands/dispatch/hw/model_vs_hw.txt`).
Code+data stands: `stands/l2code/hw/model_vs_hw.txt`.

Open:
- **DTLB on tsc**: the hardware walks 6.4-9.0 times per 1000 wide instructions (`dtlb_query - dtlb_hit`,
  `dtlb_tlu_query`), the model misses 1.6 (3.2 even with every page 4 KB).  The walks sit in calls into and out of JIT
  code and in string code.  Candidate: speculative loads to ever new invalid pages, which walk (~18 cycles each,
  `stands/spec/hw/spec3.txt`) and which qemu does not record (19 per 1000 wide instructions in the tsc trace).  Worth
  ~2-3 G cycles on tsc.
- E2 stalls of eslint (3 G low; the per-symbol fit puts it on L3-served loads).
- bub_b beyond nops: `bub_b_hwcmd` (0.72 G on tsc, at JIT entry/exit stubs; not setwd/setbn) and register-file
  spill/fill (hardware 0.48-0.72 G, model 0.05-0.36 G).

## Limitations
- One core, user mode only: no kernel time, no other threads' interference; only the main thread (vcpu 0) is traced.
- Sampled windows: each window starts with cold caches and TLBs, warmed by the first `--warm` instructions; a symbol that runs
  only between windows is invisible.
- No branch prediction model (e2k has none for prepared transfers; unprepared `ibranch` is charged a fixed cost).
- Store path: stores never stall (write-through L1D, no store-buffer model); store-heavy code is under-predicted.
- DRAM: a fixed +180; no bandwidth, no prefetcher, no page-walk cache model beyond the DTLB costs.
- Code-line DRAM costs are estimates; L2 replacement is LRU (HW is not, see the `sp_S*_a` misses).
- Event counters of the model (`mem` in the .sim.pkl) do not have the HW events' semantics (see EVENTS.md).
