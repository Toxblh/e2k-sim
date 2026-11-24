# Where the cycles go: the Elbrus-8SV top-down identity

On the Elbrus-8SV (e2k-v5) four user-mode PMU counts add up to the cycle count:

    cycles = instructions + bub_b + ticks_e2 + ib_no_command

| term | what it counts | model causes in it (`model/topdown.py`) |
|---|---|---|
| `instructions` | one cycle per wide instruction issued | `issue` |
| `bub_b` | bubbles at dispatch: explicit nops (`bub_b_nop`), register-file spill/fill (`bub_b_rf_spillfill`), `bub_b_hwcmd`, `bub_b_ip_nrdy` (`ct` one command after its `disp`), ... | `nop`, `call`, `spill` |
| `ticks_e2` | cycles stalled at E2: operands not ready (load misses, latencies, DTLB, store-to-load) | `dep`, `L2`, `L3`, `DRAM`, `stld`, `dtlb` |
| `ib_no_command` | cycles with no wide instruction to dispatch: late `ct`, unprepared `ibranch`, instruction-cache / ITLB misses at taken targets, sequential fetch misses | `ctprep`, `ibranch`, `icache`, `itarget`, `itlb` |

`bub_e0` and `ticks_e0` were 0 on every stand and on the applications.

## How it was checked

`stands/identity/run_hw.sh` measures the five counts (two perf groups of four events, `cycles` in both) on calibration
and fetch stands of known content; raw results `stands/identity/hw/bub_cal.txt`, `bub_fetch.txt`.

| stand | cycles | instructions + bub_b + ticks_e2 + ib_no_command | what dominates |
|---|---|---|---|
| `code 2048` (1.26 MB straight-line code) | 1028.8 M | 522.9 + 301.8 + 0.0 + 197.4 = 1022.1 M | nops (bub_b_nop 303.6), fetch misses |
| `call 128 1` (recursion, big frames) | 731 M | 281.4 + 321.2 + 118.3 + 10.2 = 731.1 M | spill/fill in bub_b |
| `it1m_K8` (ITLB thrash) | 224.7 M | 41.6 + 0.8 + 0.05 + 182.7 = 225.2 M | ib_no_command |
| `prep_d1_near` (`ct` 1 command after `disp`) | 169.8 M | 103.7 + 18.6 + 0.05 + 48.8 = 171.1 M | late ct: ib_no_command, d=1 part in bub_b |
| `ibr_D0` (unprepared ibranch) | 204 M | 103.7 + 2.1 + 0.05 + 97.8 = 203.6 M | ib_no_command |
| `chase 2097152` (L3 chase) | 333 M | 30.4 + 20.0 + 258.1 + 0.2 = 308.6 M | ticks_e2 (-7 %) |
| `chase 67108864` (DRAM chase) | ~480 M | 19.2 + 3.1 + 401.8 + 0.5 = 424.6 M | ticks_e2 (-12 %) |

Within ~1 % except long memory stalls, where some DRAM wait is not in `ticks_e2`.  On five large JavaScript
applications (main thread, `perf stat -i`) the sum closes within 0.3 %, e.g. one run of `tsc`:
58.0 G = 20.3 + 6.15 (nop 3.80, rf_spillfill 0.72, hwcmd 0.72, ip_nrdy 0.17) + 22.0 + 9.56 G.

## Using it

Measure the four terms on the hardware:

```sh
perf stat -i -x, -e cycles:u,instructions:u,bub_b:u,ticks_e2:u      ./prog ...
perf stat -i -x, -e cycles:u,ib_no_command:u,bub_b_nop:u,bub_b_rf_spillfill:u ./prog ...
```

and compare with the model's grouping of the same run (`python3 model/topdown.py run/prog`).  A model that is low
overall can then be checked term by term: the first use of this was finding that sim.py's front end was within
6-12 % on the large applications while its E2 stalls were half of the hardware's (docs/ACCURACY.md).  Per symbol,
`perf record -e ticks_e2:u` (or `ib_no_command:u`) against the model's per-symbol causes places the gap.
