# qemu-e2k patch

`qemu-e2k-sim.patch` applies to the OpenE2K qemu-e2k tree:

- repository: https://github.com/OpenE2K/qemu-e2k.git, branch `e2k`
- pinned commit: `ebc4bbdbe5d74bbf5a59784f697a6df64a9aa299` ("target/e2k: move getfzs/getfzd to helpers", 2025-04-19)

What it changes:

1. **AAU index registers are 48-bit, sign-extended** (`%aaind`, `%aaincr`, `%aasti`: `int64_t`, `sextract64(.., 0, 48)`),
   as the Linux e2k kernel's AAU fault handler treats them (`arch/e2k/kernel/cpu/iset_v5.c`, `do_aau_fault`).
   qemu kept them 32-bit; glibc's `memcpy` and `ld.so` keep a full 64-bit address in `%aaind` with a zero AAD base, so
   APB (array prefetch) loops read and wrote the low 4 GB instead.  A 32-bit `aaurw` to an AAD writes a zero-extended
   base.  Two alternative readings that were tried and refuted are left behind environment switches that default off
   (`SIM_AAD_SAP`, `SIM_AAD5`).  Check: a memcpy probe (`stands/probe/mc2.c`) runs 111,923 wide instructions under qemu
   vs 111,588 on the hardware (+0.3 %); before the fix it ran 50-160 M.
2. **`adds_fw` / `subs_fw`** (ALU ops that write an x86 EFLAGS image of a 32-bit add/subtract) were missing; added as
   helpers.  Values checked on Elbrus-8SV: 5+7 -> 0x4, 0x7fffffff+1 -> 0x894, 0xffffffff+1 -> 0x55.
3. **plugins/core.c**: a guest thread's `cpu_index` can be reused while the exited thread's entry is still in the
   plugin table (user mode, a guest creating threads after others exited): replace instead of asserting.

The trace plugin (`../plugin/etrace.c`) reads code bytes with `qemu_plugin_read_memory_vaddr`, because
`qemu_plugin_insn_data` / `qemu_plugin_insn_haddr` crash with the e2k translator; no qemu change is needed for that.

## Build (x86-64 Linux host)

```sh
git clone -b e2k https://github.com/OpenE2K/qemu-e2k.git
cd qemu-e2k
git checkout ebc4bbdbe5d74bbf5a59784f697a6df64a9aa299
git apply /path/to/e2k-sim/qemu/qemu-e2k-sim.patch
mkdir build && cd build
../configure --target-list=e2k-linux-user --enable-plugins --disable-docs --disable-werror
make -j4
./qemu-e2k --version          # qemu-e2k version 9.2.50
```

Then build the plugin: `make -C /path/to/e2k-sim/plugin QEMU_SRC=/path/to/qemu-e2k`.

You also need an e2k-v5 Linux root with the guest's shared libraries (for `qemu-e2k -L`) and e2k binutils
(`objdump`, `nm`) for the decoder; copying `/lib64`, `/usr/lib64` and `/usr/bin/{objdump,nm}` with their libraries
from an Elbrus machine (or using an e2k distribution's root filesystem) works.
