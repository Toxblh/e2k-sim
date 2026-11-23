/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
typedef struct { const char* n; void* f; int a; } Ent;
static const Ent tab[] = {{"alpha", (void*)1, 1}, {"beta", (void*)2, 2}, {"gamma", (void*)3, 3}, {"delta", (void*)4, 4},
  {"eps", (void*)5, 5}, {"zeta", (void*)6, 6}, {"eta", (void*)7, 7}, {"theta", (void*)8, 8}, {"iota", (void*)9, 9},
  {"kappa", (void*)10, 10}, {"lambda", (void*)11, 11}, {"mu", (void*)12, 12}, {"nu", (void*)13, 13}, {"xi", (void*)14, 14},
  {"omicron", (void*)15, 15}, {"pi", (void*)16, 16}, {"rho", (void*)17, 17}, {"sigma", (void*)18, 18}};
__attribute__((noinline)) uint64_t sum64(const uint64_t* a, int n) { uint64_t s = 0; for (int i = 0; i < n; i++) s += a[i] * (i | 1); return s; }
__attribute__((noinline)) uint64_t sum32s(const uint32_t* a, int n, int st) { uint64_t s = 0; for (int i = 0; i < n; i++) s = s * 3 + a[i * st]; return s; }
__attribute__((noinline)) void scale(double* d, const double* s, int n) { for (int i = 0; i < n; i++) d[i] = s[i] * 1.5 + d[i]; }
__attribute__((noinline)) void cp16(uint16_t* d, const uint16_t* s, int n) { for (int i = 0; i < n; i++) d[i] = s[n - 1 - i]; }
__attribute__((noinline)) uint64_t bytes(const uint8_t* a, int n) { uint64_t s = 0; for (int i = 0; i < n; i++) s += a[i] ^ (uint8_t)i; return s; }
__attribute__((noinline)) uint64_t usetab(int k) {
  struct { const char* n; int v; } m[] = {{"a1", 1}, {"b2", 2}, {"c3", 3}, {"d4", 4}, {"e5", 5}, {"f6", 6}, {"g7", 7}, {"h8", 8}, {"i9", 9}, {"j10", 10}, {"k11", 11}, {"l12", 12}};
  uint64_t s = 0; for (size_t i = 0; i < sizeof m / sizeof m[0]; i++) s = s * 7 + strlen(m[i].n) + m[i].v + k; return s;
}
static uint64_t run(uint8_t* base, const char* tag) {
  uint64_t h = 0;
  uint64_t* a = (uint64_t*)base; for (int i = 0; i < 4096; i++) a[i] = i * 0x9e3779b97f4a7c15ull;
  h = h * 31 + sum64(a, 4096) + sum64(a + 1, 1000) + sum64(a + 3, 7);
  h = h * 31 + sum32s((uint32_t*)base, 1000, 1) + sum32s((uint32_t*)base + 1, 500, 3);
  double* d = (double*)(base + 65536); for (int i = 0; i < 2048; i++) d[i] = i * 0.25;
  scale(d, d + 1024, 1000); for (int i = 0; i < 2048; i++) h = h * 31 + (uint64_t)(d[i] * 8);
  cp16((uint16_t*)(base + 131072), (uint16_t*)base, 3000); h = h * 31 + bytes(base + 131072, 6000) + bytes(base + 131073, 333);
  Ent e[18]; memcpy(e, tab, sizeof e); for (int i = 0; i < 18; i++) h = h * 31 + strlen(e[i].n) + e[i].a;
  Ent* he = (Ent*)(base + 200000); memcpy(he, tab, sizeof tab); for (int i = 0; i < 18; i++) h = h * 31 + strlen(he[i].n) + he[i].a;
  for (int sz = 1; sz < 3000; sz = sz * 2 + 1) { memmove(base + 300000 + (sz & 7), base + 7, sz); h = h * 31 + bytes(base + 300000 + (sz & 7), sz); }
  h = h * 31 + usetab(3);
  printf("%-6s %016llx\n", tag, (unsigned long long)h);
  return h;
}
int main(void) {
  uint8_t* lo = malloc(1 << 20);
  uint8_t* hi = mmap((void*)(1ull << 44), 1 << 20, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
  uint8_t* an = mmap(NULL, 1 << 20, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  uint8_t stk[400000];
  run(lo, "malloc"); run(hi, "1<<44"); run(an, "mmap"); run(stk, "stack");
  return 0;
}
