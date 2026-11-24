/* SPDX-License-Identifier: GPL-2.0-or-later */
/* sim3 data-side stands.  dstand MODE ARGS
 *  stld B N D : buffer B bytes (fits L1D). Round: store every 8 B word, then (D spin-adds later) load every word (sum).
 *               N rounds.  Do loads after stores hit L1D on 8SV?  (D = 0: right after the store pass)
 *  ldonly B N : same loads, no stores (control)
 *  assoc K S N: dependent chase over K nodes S bytes apart (one per line), N loads.  L1D/L2 associativity.
 *  stride B S N: N independent loads striding S over B bytes (spatial use of 32/64 B lines)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/mman.h>
static volatile long sink;
int main(int c, char **v) {
    const char *m = v[1];
    if (!strcmp(m, "stld") || !strcmp(m, "ldonly")) {
        long B = atol(v[2]), N = atol(v[3]), Dd = c > 4 ? atol(v[4]) : 0;
        long n = B / 8, *a = aligned_alloc(4096, B + 4096);
        memset(a, 1, B);
        long s = 0, x = 0;
        int st = !strcmp(m, "stld");
        for (long r = 0; r < N; r++) {
            if (st) for (long i = 0; i < n; i++) a[i] = r + i;
            for (long k = 0; k < Dd; k++) x = x * 3 + k;
            for (long i = 0; i < n; i++) s += a[i ^ (s >> 62)];   /* data-dependent index: no APB */
        }
        sink = s + x;
    } else if (!strcmp(m, "assoc")) {
        long K = atol(v[2]), S = atol(v[3]), N = atol(v[4]);
        char *b = aligned_alloc(1 << 21, K * S + 4096);
        for (long k = 0; k < K; k++) *(char **)(b + k * S) = b + ((k + 1) % K) * S;
        char *p = b;
        for (long i = 0; i < N; i++) p = *(char **)p;
        sink = (long)p;
    } else if (!strcmp(m, "mix")) {   /* mix P Q N: chase alternating over P small pages (4 KB stride) and Q huge pages (2 MB stride, MADV_HUGEPAGE) */
        long P = atol(v[2]), Q = atol(v[3]), N = atol(v[4]);
        char *s = aligned_alloc(1 << 21, (P + 1) * 4096 + (1 << 21)); madvise(s, (P + 1) * 4096 + (1 << 21), MADV_NOHUGEPAGE);
        char *h = aligned_alloc(1 << 21, (Q + 1) * (1L << 21)); madvise(h, (Q + 1) * (1L << 21), MADV_HUGEPAGE);
        for (long q = 0; q <= Q; q++) h[q << 21] = 1;
        long T = P > Q ? P : Q; char **nodes = malloc(2 * T * sizeof(char *)); long k = 0;
        for (long i = 0; i < T; i++) { if (P) nodes[k++] = s + (i % P) * 4096 + 64 * (i % 60); if (Q) nodes[k++] = h + ((i % Q) << 21) + 128 * (i % 60); }
        for (long i = 0; i < k; i++) *(char **)nodes[i] = nodes[(i + 1) % k];
        char *p = nodes[0];
        for (long i = 0; i < N; i++) p = *(char **)p;
        sink = (long)p;
    } else if (!strcmp(m, "chst")) {   /* chst F N K: dependent chase over F bytes (64 B nodes), K stores per step to a 4 KB buffer */
        long F = atol(v[2]), N = atol(v[3]), K = atol(v[4]), k = F / 64;
        char *b = aligned_alloc(1 << 21, F + 64); long *perm = malloc(k * sizeof(long));
        for (long i = 0; i < k; i++) perm[i] = i;
        srand(3); for (long i = k - 1; i > 0; i--) { long j = rand() % (i + 1), t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
        for (long i = 0; i < k; i++) *(char **)(b + perm[i] * 64) = b + perm[(i + 1) % k] * 64;
        volatile long *sb = aligned_alloc(4096, 4096); char *p = b + perm[0] * 64;
        for (long i = 0; i < N; i++) { p = *(char **)p; for (long j = 0; j < K; j++) sb[(i * 8 + j * 8) & 511] = i; }
        sink = (long)p;
    } else if (!strcmp(m, "stride")) {
        long B = atol(v[2]), S = atol(v[3]), N = atol(v[4]);
        char *b = aligned_alloc(1 << 21, B + 4096); memset(b, 1, B);
        long s = 0, o = 0;
        for (long i = 0; i < N; i++) { s += *(long *)(b + (o ^ (s >> 62))); o += S; if (o >= B) o = 0; }
        sink = s;
    }
    return 0;
}
