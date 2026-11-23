/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _GNU_SOURCE
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#ifndef MADV_COLLAPSE
#define MADV_COLLAPSE 25
#endif
static long huge(void *p) { FILE *f = fopen("/proc/self/smaps", "r"); char l[512]; long h = -1; int in = 0; char want[64]; snprintf(want, sizeof want, "%lx-", (unsigned long)p);
  while (fgets(l, sizeof l, f)) { if (strncmp(l, want, strlen(want)) == 0) in = 1; else if (in && strncmp(l, "AnonHugePages:", 14) == 0) { sscanf(l + 14, "%ld", &h); break; } } fclose(f); return h; }
int main(void) {
  for (int x = 0; x < 2; x++) {
    size_t sz = 8 << 20;
    char *p = mmap((void *)(0x50000000ul + x * 0x1000000ul), sz, PROT_READ | PROT_WRITE | (x ? PROT_EXEC : 0), MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    madvise(p, sz, MADV_HUGEPAGE);
    memset(p, 1, sz);
    long h1 = huge(p);
    int rc = madvise(p, sz, MADV_COLLAPSE);
    printf("%s: after touch AnonHuge=%ldK, MADV_COLLAPSE rc=%d -> %ldK\n", x ? "rwx" : "rw ", h1, rc, huge(p));
  }
  return 0;
}
