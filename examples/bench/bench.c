/* SPDX-License-Identifier: GPL-2.0-or-later */
/* bench.c: a small mixed workload for the e2k-sim example (one thread, no input files).
 *
 *   ./bench [REPS]     (default 4)
 *
 * Five kernels, each a separate noinline function so that the model's per-symbol summary has something to say:
 *   interp   a switch-dispatched bytecode loop (indirect branches, short blocks)
 *   hashmap  open-addressing string hash table: inserts and lookups (byte loops, calls, unpredictable loads)
 *   sort     quicksort of 64-bit keys (data-dependent branches, recursion)
 *   chase    a random pointer chase over 8 MB (L2/L3/DRAM and DTLB misses)
 *   matmul   64x64 double matrix multiply (software-pipelined FP loops)
 * Prints a checksum per kernel; the checksums do not depend on the machine.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t rs = 0x9e3779b97f4a7c15ull;
static uint64_t rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }

/* ---------------------------------------------------------------- interp */
enum { OP_PUSH, OP_ADD, OP_SUB, OP_MUL, OP_XOR, OP_DUP, OP_SWAP, OP_JNZ, OP_DEC, OP_POP, OP_HALT };
__attribute__((noinline)) static int64_t interp(const uint8_t *code, int64_t n) {
    int64_t st[64]; int sp = 0; int pc = 0; int64_t acc = 0;
    st[sp++] = n;
    for (;;) {
        switch (code[pc++]) {
        case OP_PUSH: st[sp++] = code[pc++]; break;
        case OP_ADD: sp--; st[sp - 1] += st[sp]; break;
        case OP_SUB: sp--; st[sp - 1] -= st[sp]; break;
        case OP_MUL: sp--; st[sp - 1] *= st[sp]; break;
        case OP_XOR: sp--; st[sp - 1] ^= st[sp]; break;
        case OP_DUP: st[sp] = st[sp - 1]; sp++; break;
        case OP_SWAP: { int64_t t = st[sp - 1]; st[sp - 1] = st[sp - 2]; st[sp - 2] = t; } break;
        case OP_DEC: st[sp - 1]--; break;
        case OP_POP: acc += st[--sp]; break;
        case OP_JNZ: { int8_t off = (int8_t)code[pc++]; if (st[sp - 1]) pc += off; } break;
        case OP_HALT: return acc + st[sp - 1];
        }
    }
}

static int64_t run_interp(int reps) {
    /* counter on the stack; body: push 3, dup, mul, push 7, xor, pop, dec, jnz body */
    static const uint8_t prog[] = {
        OP_PUSH, 3, OP_DUP, OP_MUL, OP_PUSH, 7, OP_XOR, OP_SWAP, OP_DUP, OP_PUSH, 5, OP_ADD, OP_POP, OP_SWAP,
        OP_POP, OP_DEC, OP_JNZ, (uint8_t)-18, OP_HALT };
    int64_t s = 0;
    for (int r = 0; r < reps; r++) s += interp(prog, 300000 + r);
    return s;
}

/* ---------------------------------------------------------------- hashmap */
#define HBITS 16
typedef struct { char key[24]; int64_t val; } Slot;
__attribute__((noinline)) static uint64_t hstr(const char *s) {
    uint64_t h = 1469598103934665603ull;
    while (*s) { h ^= (uint8_t)*s++; h *= 1099511628211ull; }
    return h;
}
__attribute__((noinline)) static Slot *hfind(Slot *t, const char *k, int insert) {
    uint64_t i = hstr(k) & ((1u << HBITS) - 1);
    for (;;) {
        Slot *s = &t[i];
        if (!s->key[0]) { if (!insert) return NULL; strcpy(s->key, k); s->val = 0; return s; }
        if (!strcmp(s->key, k)) return s;
        i = (i + 1) & ((1u << HBITS) - 1);
    }
}
static int64_t run_hashmap(int reps) {
    Slot *t = calloc(1u << HBITS, sizeof(Slot));
    char k[24]; int64_t s = 0;
    for (int r = 0; r < reps; r++) {
        memset(t, 0, (1u << HBITS) * sizeof(Slot));            /* 40000 keys in 65536 slots */
        for (int i = 0; i < 40000; i++) { snprintf(k, sizeof k, "key%d", i * 7 + r); hfind(t, k, 1)->val += i; }
        for (int i = 0; i < 80000; i++) { snprintf(k, sizeof k, "key%d", i * 3); Slot *e = hfind(t, k, 0); if (e) s += e->val; }
    }
    free(t);
    return s;
}

/* ---------------------------------------------------------------- sort */
__attribute__((noinline)) static void qsort64(uint64_t *a, long lo, long hi) {
    while (hi - lo > 16) {
        uint64_t p = a[lo + (hi - lo) / 2]; long i = lo, j = hi;
        while (i <= j) {
            while (a[i] < p) i++;
            while (a[j] > p) j--;
            if (i <= j) { uint64_t t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; }
        }
        if (j - lo < hi - i) { qsort64(a, lo, j); lo = i; } else { qsort64(a, i, hi); hi = j; }
    }
    for (long i = lo + 1; i <= hi; i++) { uint64_t v = a[i]; long j = i - 1; while (j >= lo && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; }
}
static int64_t run_sort(int reps) {
    long n = 200000; uint64_t *a = malloc(n * sizeof *a); int64_t s = 0;
    for (int r = 0; r < reps; r++) {
        for (long i = 0; i < n; i++) a[i] = rnd();
        qsort64(a, 0, n - 1);
        s += a[n / 2] >> 40;
    }
    free(a);
    return s;
}

/* ---------------------------------------------------------------- chase */
__attribute__((noinline)) static uintptr_t chase(void **p, long n) { while (n--) p = (void **)*p; return (uintptr_t)p; }
static int64_t run_chase(int reps) {
    long k = (8l << 20) / 64; char *b = malloc(k * 64 + 64); long *perm = malloc(k * sizeof(long));
    for (long i = 0; i < k; i++) perm[i] = i;
    for (long i = k - 1; i > 0; i--) { long j = rnd() % (i + 1), t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
    for (long i = 0; i < k; i++) *(void **)(b + perm[i] * 64) = b + perm[(i + 1) % k] * 64;
    int64_t s = 0;
    for (int r = 0; r < reps; r++) s += (int64_t)((chase((void **)(b + perm[r] * 64), 400000) - (uintptr_t)b) >> 6);
    free(perm); free(b);
    return s;
}

/* ---------------------------------------------------------------- matmul */
#define MN 64
__attribute__((noinline)) static void matmul(double *c, const double *a, const double *b) {
    for (int i = 0; i < MN; i++)
        for (int j = 0; j < MN; j++) {
            double s = 0;
            for (int k = 0; k < MN; k++) s += a[i * MN + k] * b[k * MN + j];
            c[i * MN + j] = s;
        }
}
static int64_t run_matmul(int reps) {
    static double a[MN * MN], b[MN * MN], c[MN * MN];
    for (int i = 0; i < MN * MN; i++) { a[i] = (i % 17) * 0.25; b[i] = (i % 13) * 0.5; }
    double s = 0;
    for (int r = 0; r < reps * 8; r++) { matmul(c, a, b); s += c[r % (MN * MN)]; a[r % (MN * MN)] += 1.0; }
    return (int64_t)s;
}

int main(int argc, char **argv) {
    int reps = argc > 1 ? atoi(argv[1]) : 4;
    printf("interp  %lld\n", (long long)run_interp(reps));
    printf("hashmap %lld\n", (long long)run_hashmap(reps));
    printf("sort    %lld\n", (long long)run_sort(reps));
    printf("chase   %lld\n", (long long)run_chase(reps));
    printf("matmul  %lld\n", (long long)run_matmul(reps));
    return 0;
}
