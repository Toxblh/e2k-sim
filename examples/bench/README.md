# Example: an open C benchmark, end to end

`bench.c` (this directory, GPL-2.0-or-later) runs five small kernels: a switch-dispatched bytecode interpreter, a
string hash map, quicksort, an 8 MB pointer chase and a 64x64 matrix multiply.  `./bench 2` executes 0.314 G wide
instructions.  The files in `output/` were produced by exactly the commands below.

## 1. Build it for e2k-v5 and measure it (on the Elbrus machine)

```sh
lcc -O2 -g bench.c -o bench            # lcc 1.29.16, e2k-v5-linux
for r in 1 2 3; do taskset -c 7 perf stat -x, -e cycles:u,instructions:u ./bench 2 2>&1 >/dev/null; done
# -> output/hw_8sv.txt (one line per round: "bench cycles=C instructions=I scope=all"; scripts/hwstat.sh writes it)
perf record -c 200000 -e cycles:u -o perf.data ./bench 2
perf report -i perf.data --stdio --sort dso,symbol | grep -v '^#' | grep -v '^$' | head -40 > output/perf_report.txt
```

## 2. Trace it under the patched qemu-e2k (on the x86 host, single-threaded: 1 core is enough)

```sh
export E2K_QEMU=/path/to/qemu-e2k/build/qemu-e2k   # built with ../../qemu/qemu-e2k-sim.patch
export E2K_SYSROOT=/path/to/e2k-root               # e2k /lib64 etc. for qemu -L
export E2K_ROOT=/path/to/e2k-root                  # holds usr/bin/objdump and usr/bin/nm (e2k binutils)
mkdir -p run
scripts/qtrace.sh run/bench skip=1000000,win=2000000,period=5000000,nwin=62 -- ./bench 2
#   20 s; run/bench.w0..w61.bin.zst (43 MB), run/bench.code, run/bench.info, run/bench.maps; stdout identical to the HW run
NM="$E2K_QEMU -L $E2K_ROOT $E2K_ROOT/usr/bin/nm" scripts/mksyms.sh run/syms ./bench $E2K_SYSROOT/lib64/libc.so.6
```

## 3. Decode and model every window (4 cores, PyPy: 2 minutes; CPython ~10x slower)

```sh
JOBS=4 PY=pypy3 scripts/model.sh run/bench 500000     # 0.5 M of each 2 M window warms the caches
```

## 4. Read the summaries

```sh
python3 model/hwcmp.py output/hw_8sv.txt run/bench        > output/hwcmp.txt    # model vs HW, whole run
python3 model/apps.py --top 12 run/bench                  > output/apps.txt     # where / what / why
python3 model/report.py --top 8 run/bench                 > output/report.txt   # per layer and symbol, window counts
python3 model/perfcmp.py output/perf_report.txt run/bench 14 > output/perfcmp.txt # per-symbol shares vs perf record
python3 model/supply.py run/bench                         > output/supply.txt   # instruction-supply costs
```

## Result

```
run               win     CPI  HW CPI CPI err | G cyc mod  G cyc HW     err | qemu Gins   HW Gins    diff
bench              62   1.918   1.940   -1.1% |    0.6020    0.6087   -1.1% |    0.3138    0.3138   +0.0%
```

The whole run is within 1.1 % of the hardware, and qemu executes the same number of wide instructions as the hardware.
Per symbol (`output/perfcmp.txt`), `interp` (28.3 % on HW, 28.6 % in the model), `_IO_default_xsputn`, `hstr` and
`strchrnul` agree within 0.5 points.  The model is wrong in two places:

- `hfind` + `strcmp`, the hash-table lookups, are 17.3 % in the model and 8.1 % on HW: the model sends most of these
  scattered loads to DRAM at a fixed +180 cycles.  On the hardware they cost half of that; whether more of the 2 MB
  table stays in L3 or the misses overlap better is not resolved (a longer warm-up does not change it).
- `run_chase` (the random shuffle that builds the chase list, store-heavy) is 1.7 % in the model and 6.9 % on HW:
  in the model, stores never stall.

`psiginfo` and `cuserid` in the model's list are libc's internal printf code: `nm -D` sees only exported symbols, so
the model attributes the code to the nearest exported symbol before it.  perf shows that code as bare addresses
(`0x1119e0`, ...).  `_init` collects the PLT stubs of the main binary.

How to read `apps.txt`: WHERE are the layers (here `main` = the bench binary, `lib` = libc); WHAT is the split of all
cycles by cause (`issue` = 1 cycle per wide instruction, `nop` = the compiler's explicit nops, `DRAM`/`L3`/`L2` = load
misses, `ctprep` = `ct` too soon after its `disp`); WHY gives the dominant reason per hot symbol.  Here the interpreter
and the sort are bound by the schedule's own nops (latency that lcc could not fill), and the hash lookups by memory.
