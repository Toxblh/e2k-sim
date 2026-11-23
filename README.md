# e2k-sim: a trace-driven cycle model of the Elbrus-8SV (e2k-v5)

e2k-sim estimates where an e2k-v5 Linux program spends its cycles on an Elbrus-8SV, and why, without access to the
machine's internals: the program runs under qemu-e2k (user mode) with a trace plugin, the traced wide instructions
are decoded with GNU objdump, and a Python model charges each wide instruction its issue cycle, the compiler's
nops, operand waits, cache/TLB misses, store-to-load conflicts, control-transfer preparation and instruction-supply
costs.  Every constant comes from a measurement on the hardware with a small stand that is part of this repository.

```
program (e2k ELF) --qemu-e2k + etrace plugin--> PFX.code + PFX.w<N>.bin.zst (sampled windows) + .info + .maps
        --model/decode.py (objdump + e2kdis.py)--> PFX.dec.pkl
        --model/sim.py, one process per window--> PFX.w<N>.sim.pkl (cycles per instruction and cause)
        --model/apps.py, report.py, supply.py, hwcmp.py, perfcmp.py--> short text summaries: where / what / why
```

Accuracy: 138 instruction-supply stands median |error| 1.5 %, 90th percentile 23.3 %; 16 calibration stands within
-12 .. +4 %; the open example program within 1.1 % of the hardware over the whole run (details and the known misses:
[docs/ACCURACY.md](docs/ACCURACY.md)).

## Repository

| path | what |
|---|---|
| `qemu/` | patch for OpenE2K qemu-e2k (pinned commit) + build instructions ([qemu/README.md](qemu/README.md)) |
| `plugin/` | `etrace.c`, the trace plugin (windows of wide instructions + memory accesses); `regs.c` (debug); `Makefile` |
| `model/` | `e2kdis.py` objdump-listing parser and latency classes, `decode.py`, `sim.py` (the model), summaries `apps.py` `report.py` `supply.py` `hwcmp.py` `perfcmp.py`, layout estimates `mklayout.py` `mkfam.py` `mkcolour.py` `laygain.py`, `tdump.py` (trace dump) |
| `scripts/` | `qtrace.sh` (trace), `model.sh` (decode + model all windows), `simset.sh` (model variants / layouts), `mksyms.sh` (symbol tables), `hwstat.sh` (perf stat on the Elbrus) |
| `stands/` | fetch / ITLB / L2 stand generators, calibration stands, probes, their hardware results ([stands/README.md](stands/README.md)) |
| `docs/` | [FACTS.md](docs/FACTS.md) (the measured facts), [FETCH.md](docs/FETCH.md), [EVENTS.md](docs/EVENTS.md) (PMU events), [ACCURACY.md](docs/ACCURACY.md) |
| `examples/bench/` | an end-to-end run on an open C program, with the committed summaries |

## What you need

- An x86-64 Linux host for qemu (any core count; tracing is single-threaded, the model runs one process per window).
- An e2k-v5 Linux root: the guest's shared libraries (`qemu-e2k -L`) and e2k binutils `objdump` and `nm`
  (run under qemu-e2k themselves, or natively on an Elbrus machine).
- `zstd` in PATH (the plugin pipes trace records through it), Python 3.8+; PyPy 3 makes the model ~10x faster.
- Optional: an Elbrus-8SV with `perf` to measure the program and compare.

## Step by step

### 1. Build qemu-e2k with the patch and the plugin

```sh
git clone -b e2k https://github.com/OpenE2K/qemu-e2k.git && cd qemu-e2k
git checkout ebc4bbdbe5d74bbf5a59784f697a6df64a9aa299
git apply /path/to/e2k-sim/qemu/qemu-e2k-sim.patch
mkdir build && cd build && ../configure --target-list=e2k-linux-user --enable-plugins --disable-docs --disable-werror
make -j4
make -C /path/to/e2k-sim/plugin QEMU_SRC=/path/to/qemu-e2k        # -> plugin/libetrace.so
```

The patch makes the AAU index registers 48-bit sign-extended (glibc's memcpy and ld.so need it), adds the
`adds_fw`/`subs_fw` operations and fixes a plugin assertion for programs that create threads; see qemu/README.md.

### 2. Trace a program

```sh
export E2K_QEMU=/path/to/qemu-e2k/build/qemu-e2k E2K_SYSROOT=/path/to/e2k-root E2K_ROOT=/path/to/e2k-root
scripts/qtrace.sh run/prog skip=1000000,win=2000000,period=20000000,nwin=50 -- ./prog args...
```

`skip` wide instructions run at full speed, then `nwin` windows of `win` instructions start every `period`
instructions; inside a window every wide instruction and memory access of the main thread is recorded.  Pick
`period` so that the windows cover what you care about (the summaries scale the windows to the whole run).  qemu runs
with host ASLR off, so repeated runs see the same addresses.  For a JIT, copy its perf map (`/tmp/perf-<pid>.map`,
pid in `run/prog.info`) to `run/prog.perfmap` to name the generated code.  Symbol tables for the summaries:

```sh
NM="$E2K_QEMU -L $E2K_ROOT $E2K_ROOT/usr/bin/nm" scripts/mksyms.sh run/syms ./prog $E2K_SYSROOT/lib64/libc.so.6
```

### 3. Run the model

```sh
JOBS=4 PY=pypy3 scripts/model.sh run/prog 500000      # decode, then every window with a 0.5 M warm-up
```

Model variants and layout estimates run on the same decoded trace into another directory, e.g.
`scripts/simset.sh run run_w2 "SIM_ITLB=256:1:12 SIM_ITLBX=26 SIM_L2CODE=hashed" prog` (knobs: `model/sim.py` docstring).

### 4. Read the summaries

They are short fixed-width text, cheap to read for a person or a language model:

```sh
python3 model/apps.py run/prog                 # WHERE (layers), WHAT (cycles by cause), WHY (top symbols + reason)
python3 model/report.py --top 20 run/prog      # per layer: top symbols with cycles, instructions, IPC, stall split
python3 model/supply.py run/prog               # instruction supply: L1I/ITLB target misses, ct preparation, ibranch
python3 model/hwcmp.py hw.txt run/prog         # model vs perf stat cycles (hw.txt from scripts/hwstat.sh)
python3 model/perfcmp.py perf_report.txt run/prog   # per-symbol shares vs perf record
python3 model/report.py --diff run_b/prog run/prog  # what changed between two builds or inputs, per symbol
```

Causes: `issue` (1 cycle per wide instruction), `nop` (explicit nops), `dep` (operand latency), `L2`/`L3`/`DRAM`
(load misses), `stld` (store-to-load), `dtlb`, `ctprep` (`ct` too soon after `disp`/`movtd`/`return`), `ibranch`
(unprepared), `icache` (sequential fetch misses), `itarget` (taken target missing L1I), `itlb`, `call`, `spill`
(register file).  Layers: `main` (the binary), `lib` (shared libraries), `jit` (perf map / anonymous code), `other`;
`SIM_LAYERS` splits them further (see `model/report.py`).

Layout estimates: `mklayout.py` (hot functions packed by heat), `mkfam.py` (variants of one routine served by one copy:
an upper bound), `mkcolour.py` (move code regions to spread hot pages over ITLB sets) write a line map; model with
`SIM_LAYOUT=map.pkl` (`scripts/simset.sh`) and compare with `laygain.py`.

## Elbrus-8SV facts the model uses (measured)

| | value | stand |
|---|---|---|
| load-to-use latency | L1 3, L2 11, L3 32, DRAM ~200 | `stands/cal` chase |
| L1D | write-through (no store hits; every store goes to L2) | `stands/cal` st |
| `ct` prepared d commands before it | +max(0, 5-d) | `stands/fetch` prep_d* |
| unprepared taken `ibranch` | +5.4 .. 6 | ibr_*, ibrfoot_* |
| taken target missing L1I | +9.3 from L2; L1I behaves 2-way for targets | dist_D65536, far16 |
| L2 for code lines | 4-way, index VA bits 6..16 unhashed; a target from L3 ~+35 | sp_S*_a (itlb8) |
| ITLB | 64 sets (VA bits 12..17) x 5 ways; miss ~+27..30 | it1m_K*, it*k_K8 (itlb8) |
| `ib_disp_miss` | not a cost signal (fires when transfers cost nothing) | prep_d5..8, foot_* |
| target alignment / distance | free, except the last 8 B of a 256 B line: +0.5 | align_off*, dist_D* |
| sequential code missing L1I | +1.0 (L2) / +3.9 (L3) per 256 B line | `stands/cal` code |
| DTLB | 4 KB: 256x3, miss ~20-28; 2 MB: 256x1, miss ~36 | `stands/cal` tlb |
| THP for executable anonymous memory | refused by the kernel | `stands/probe/thpx.c` |

All rows with sources and raw result files: [docs/FACTS.md](docs/FACTS.md).

## Accuracy

- 138 fetch/ITLB/L2 stands: median |error| 1.5 %, 90th percentile 23.3 %.  The misses (> 20 %) are listed honestly in
  [docs/ACCURACY.md](docs/ACCURACY.md): targets at 16 KB+64 / 64 KB+64 strides (an unidentified extra conflict on HW,
  under-predicted up to -68 %), 6 pages in one ITLB set (partial thrash, -69 %), 256 targets 16 KB apart (-71 %), and
  several 64 KB-stride cases where the model's L1I/L2 replacement is harsher than the hardware's (+21 .. +68 %).
- `examples/bench`: whole run -1.1 %; per symbol up to ~5 points of the run off (memory-bound hash lookups
  over-predicted, store-heavy code under-predicted).

## Limitations

User mode only, the main thread only, no kernel time; sampled windows start cold; stores never stall (no store-buffer
model); DRAM is a fixed latency (no bandwidth, no prefetcher); no model of other cores; code-line DRAM costs are
estimates; L2 replacement is LRU; the register-latency, store-to-load and `movtd`/`return` preparation rules were
measured with stands that are not part of this repository.  The model was built for code produced by lcc (MCST's
compiler) and by a JIT; hand-written assembly with unusual constructs may decode into `unknown` operations
(charged 1 cycle).

## License

GPL-2.0-or-later (see `LICENSE`) for everything in this repository.  The qemu patch changes qemu source files and,
when applied, is under the license of the files it changes (qemu is GPL-2.0).
