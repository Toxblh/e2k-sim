/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <stdint.h>
#define RD(tag) do { uint64_t lo, hi; asm volatile("aaurrd,2 %%aad0, %0" : "=r"(lo)); asm volatile("aaurrd,5 %%aad0, %0" : "=r"(hi)); printf("%-28s lo=%016llx hi=%016llx\n", tag, (unsigned long long)lo, (unsigned long long)hi); } while (0)
int main(void) {
  uint64_t a = 0x0000123456789abcull, b = 0x00000fedcba98760ull; uint32_t s = 0x11223344u, t = 0x55667788u;
  asm volatile("aaurwd,2 %0, %%aad0" :: "r"(a)); RD("aaurwd,2 a");
  asm volatile("aaurwd,5 %0, %%aad0" :: "r"(b)); RD("aaurwd,5 b");
  asm volatile("aaurws,2 %0, %%aad0" :: "r"(s)); RD("aaurws,2 s");
  asm volatile("aaurws,5 %0, %%aad0" :: "r"(t)); RD("aaurws,5 t");
  asm volatile("aaurwd,2 %0, %%aad0" :: "r"(a)); RD("aaurwd,2 a again");
  asm volatile("aaurws,2 %0, %%aad0" :: "r"(t)); RD("aaurws,2 t");
  return 0;
}
