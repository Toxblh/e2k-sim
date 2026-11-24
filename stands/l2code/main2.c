/* SPDX-License-Identifier: GPL-2.0-or-later */
/* main2.c: driver for the code+data stands: builds a random pointer ring of D bytes (one node per 64 B line) and calls
   stand(iters, ring); ../dispatch/gen3.py with CH=1 makes every block load the next node.  usage: TAG ITERS D */
#include <stdio.h>
#include <stdlib.h>
long stand(long iters, void *ring);
int main(int c, char **v) {
    long n = atol(v[1]), D = c > 2 ? atol(v[2]) : 0, k = D / 64;
    if (k < 1) k = 1;
    char *b = aligned_alloc(1 << 21, k * 64 + 64);
    long *perm = malloc(k * sizeof(long)); for (long i = 0; i < k; i++) perm[i] = i;
    srand(7); for (long i = k - 1; i > 0; i--) { long j = rand() % (i + 1), t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
    for (long i = 0; i < k; i++) *(void **)(b + perm[i] * 64) = b + perm[(i + 1) % k] * 64;
    printf("%ld\n", stand(n, b + perm[0] * 64)); return 0;
}
