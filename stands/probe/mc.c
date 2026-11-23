/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
int main(void) {
  size_t N = 1 << 16;
  unsigned char *src = malloc(N + 64), *dst = malloc(N + 64);
  for (size_t i = 0; i < N + 64; i++) src[i] = (unsigned char)(i * 131 + 7);
  int bad = 0, first = -1;
  size_t sizes[] = {1,7,8,15,16,31,32,63,64,100,127,128,200,255,256,300,511,512,600,1000,1023,1024,1500,2048,3000,4096,5000,8192,10000,16384,30000,65536};
  for (unsigned si = 0; si < sizeof sizes / sizeof sizes[0]; si++)
    for (int so = 0; so < 16; so += 3) for (int dof = 0; dof < 16; dof += 5) {
      size_t n = sizes[si]; if (n + so > N || n + dof > N) continue;
      memset(dst, 0xee, N + 64);
      memcpy(dst + dof, src + so, n);
      if (memcmp(dst + dof, src + so, n) || dst[dof + n] != 0xee) { bad++; if (first < 0) { first = 1; printf("bad n=%zu so=%d do=%d\n", n, so, dof); } }
    }
  printf("memcpy bad %d\n", bad);
  /* memmove overlapping */
  bad = 0;
  for (unsigned si = 0; si < sizeof sizes / sizeof sizes[0]; si++) {
    size_t n = sizes[si]; if (n + 64 > N) continue;
    for (size_t i = 0; i < N; i++) src[i] = (unsigned char)(i * 13);
    memmove(src + 24, src, n);
    for (size_t i = 0; i < n; i++) if (src[24 + i] != (unsigned char)(i * 13)) { bad++; break; }
  }
  printf("memmove bad %d\n", bad);
  return 0;
}
