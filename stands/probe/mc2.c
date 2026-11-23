/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
typedef struct { const char* n; void* f; long a; } Ent;
static const Ent tab[18] = {{"alpha", (void*)1, 1}, {"beta", (void*)2, 2}, {"gamma", (void*)3, 3}, {"delta", (void*)4, 4},
  {"eps", (void*)5, 5}, {"zeta", (void*)6, 6}, {"eta", (void*)7, 7}, {"theta", (void*)8, 8}, {"iota", (void*)9, 9},
  {"kappa", (void*)10, 10}, {"lambda", (void*)11, 11}, {"mu", (void*)12, 12}, {"nu", (void*)13, 13}, {"xi", (void*)14, 14},
  {"omicron", (void*)15, 15}, {"pi", (void*)16, 16}, {"rho", (void*)17, 17}, {"sigma", (void*)18, 18}};
__attribute__((noinline)) static void chk(const char* tag, const Ent* e) {
  int bad = 0; for (int i = 0; i < 18; i++) if (e[i].n != tab[i].n || e[i].a != tab[i].a) bad++;
  printf("%s %p bad=%d\n", tag, (void*)e, bad);
}
int main(void) {
  Ent e[18];
  uint8_t* hi = mmap((void*)(1ull << 44), 1 << 16, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  static Ent lo[18];
  memcpy(lo, tab, sizeof tab); chk("lo", lo);
  memcpy(hi + 8, tab, sizeof tab); chk("hi", (Ent*)(hi + 8));
  memcpy(e, tab, sizeof tab); chk("stack", e);
  memcpy(hi + 4096, e, sizeof tab); chk("stack->hi", (Ent*)(hi + 4096));
  return 0;
}
