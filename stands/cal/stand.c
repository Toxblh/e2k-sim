/* SPDX-License-Identifier: GPL-2.0-or-later */
/* calibration stands for 8SV PMU events. usage: stand MODE ARGS
 *  chase F N    : N dependent loads, random cycle over F bytes, one node per 64 B line
 *  seq F N      : N independent loads, stride 32 B over F bytes (repeated)
 *  st F N       : N stores, stride 32 B over F bytes (repeated)
 *  tlb P S N H  : N dependent loads cycling over P pages spaced S bytes; H=1 huge (MADV_HUGEPAGE), 0 small
 *  call D W N   : N calls of a recursion of depth D; W=0 small frame, 1 big frame (many live values)
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
static void *amap(size_t sz, int huge) {
  size_t al = 1ul << 21;
  char *p = mmap(NULL, sz + al, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
  p = (char *)(((uintptr_t)p + al - 1) & ~(al - 1));
  madvise(p, sz, huge ? MADV_HUGEPAGE : MADV_NOHUGEPAGE);
  if (sz <= (256ul << 20) && getenv("NOFILL") == 0) memset(p, 1, sz);
  return p;
}
static uint64_t rs = 88172645463325252ull;
static uint64_t rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }
__attribute__((noinline)) uintptr_t chase(void **p, long n) { while (n--) p = (void **)*p; return (uintptr_t)p; }
__attribute__((noinline)) long seqld(volatile long *a, long words, long n) {
  long s = 0, i = 0; while (n > 0) { for (i = 0; i < words && i < n * 4; i += 4) s += a[i]; n -= words / 4; } return s; }
__attribute__((noinline)) void seqst(volatile long *a, long words, long n) {
  while (n > 0) { for (long i = 0; i < words; i += 4) a[i] = i; n -= words / 4; } }
static long g;
__attribute__((noinline)) long rsmall(int d) { return d ? rsmall(d - 1) + 1 : g; }
__attribute__((noinline)) long rbig(int d, long a) {
  if (!d) return a + g;
  long x0 = a * 3, x1 = a ^ 5, x2 = a + 7, x3 = a * 11, x4 = a - 13, x5 = a ^ 17, x6 = a * 19, x7 = a + 23,
       x8 = a ^ 29, x9 = a * 31, xa = a + 37, xb = a ^ 41, xc = a * 43, xd = a + 47, xe = a ^ 53, xf = a * 59;
  long r = rbig(d - 1, a + 1);
  return r + x0 + x1 * x2 + x3 * x4 + x5 * x6 + x7 * x8 + x9 * xa + xb * xc + xd * xe + xf;
}
int main(int argc, char **argv) {
  const char *m = argv[1];
  if (!strcmp(m, "chase")) {
    long F = atol(argv[2]), n = atol(argv[3]), k = F / 64;
    char *b = amap(F, 0); long *perm = malloc(k * sizeof(long));
    for (long i = 0; i < k; i++) perm[i] = i;
    for (long i = k - 1; i > 0; i--) { long j = rnd() % (i + 1), t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
    for (long i = 0; i < k; i++) *(void **)(b + perm[i] * 64) = b + perm[(i + 1) % k] * 64;
    printf("%lx\n", (long)chase((void **)b, n));
  } else if (!strcmp(m, "seq")) {
    long F = atol(argv[2]), n = atol(argv[3]); long *a = amap(F, 0);
    printf("%ld\n", seqld(a, F / 8, n));
  } else if (!strcmp(m, "st")) {
    long F = atol(argv[2]), n = atol(argv[3]); long *a = amap(F, 0);
    seqst(a, F / 8, n); printf("%ld\n", a[0]);
  } else if (!strcmp(m, "tlb")) {
    long P = atol(argv[2]), S = atol(argv[3]), n = atol(argv[4]); int h = atoi(argv[5]);
    char *b = amap(P * S, h);
    for (long i = 0; i < P; i++) *(void **)(b + i * S + (i % 64) * 64) = b + ((i + 1) % P) * S + (((i + 1) % P) % 64) * 64;
    printf("%lx\n", (long)chase((void **)b, n));
  } else if (!strcmp(m, "call")) {
    int d = atoi(argv[2]), w = atoi(argv[3]); long n = atol(argv[4]), s = 0;
    for (long i = 0; i < n; i++) s += w ? rbig(d, i) : rsmall(d);
    printf("%ld\n", s);
  }
  return 0;
}
