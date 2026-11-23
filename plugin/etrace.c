/* SPDX-License-Identifier: GPL-2.0-or-later */
/* etrace: compact wide-instruction + memory trace for qemu-e2k (user mode), the input of the e2k-v5 cycle model.
 *
 * -plugin ./libetrace.so,out=PFX,skip=N,win=M[,period=P][,nwin=K][,dump=PC:K:ADDR:LEN][,watch=ADDR:LEN][,vwatch=VALUE]
 *   skip   wide instructions to fast-forward before the first window (inline TB counters, cheap); must be >= 1
 *   win    wide instructions per window (traced with per-insn and memory callbacks)
 *   period distance between window starts (0 = one window)
 *   nwin   number of windows (default 1)
 *   dump   debug: at the K-th execution of PC dump LEN bytes at ADDR to stderr (hex)
 *   watch  debug: report every store into [ADDR, ADDR+LEN) to stderr
 *   vwatch debug: report the first stores of VALUE (64-bit) to stderr
 * Output: PFX.code  "id vaddr size hexbytes sym"  one line per translated insn, written on its first execution in a window
 *         PFX.w<N>.bin.zst  u64 records (zstd): bit63=1 -> insn id in bits 0..31; bit63=0 -> memory access:
 *                       vaddr bits 0..55, size_shift bits 56..58, store bit 59
 *         PFX.info  window boundaries (icount), "total_insns ALL vcpu0 V ids N", pid
 *         PFX.maps  the guest's /proc/self/maps at exit (guest_base 0 in user mode: host maps = guest addresses)
 * Only vcpu 0 (the main thread) is traced inside windows; instruction totals cover all vcpus.
 * Code bytes are read with qemu_plugin_read_memory_vaddr (qemu_plugin_insn_data/haddr crash with the e2k translator).
 * Records are piped through `zstd -1` (needs zstd in PATH): ~36x smaller than raw.
 */
#include <glib.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <qemu-plugin.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

static qemu_plugin_id_t me;
static struct qemu_plugin_scoreboard *sb;
static qemu_plugin_u64 icnt;          /* per-vcpu wide instruction count */
static uint64_t skip, win = 1000000, period, nwin = 1, cur_win, win_start, win_n;
static uint64_t next_start;
static int phase;                      /* 0 counting, 1 tracing, 2 done (counting only) */
static char *pfx = "etrace";
static FILE *codef, *binf, *infof;
static GHashTable *byaddr;             /* vaddr -> struct ins* (latest bytes) */
static uint32_t nids;
static GMutex lock;
static uint64_t dump_pc, dump_k, dump_addr, dump_len, dump_seen;
static uint64_t watch_lo, watch_hi, vwatch; static int vwatch_n;  /* debug: report stores into [lo,hi) */

struct ins { uint64_t vaddr; uint32_t id, size; int seen; const char *sym; };
static int is_child;

static void put64(uint64_t v) { fwrite(&v, 8, 1, binf); }

static void stop_window(void);
static void emit_code(struct ins *p);
static void insn_exec(unsigned int vcpu, void *ud) {
    if (vcpu != 0 || phase != 1 || is_child) return;
    struct ins *p = ud;
    if (!p->seen) emit_code(p);
    put64((1ull << 63) | p->id);
    if (++win_n >= win) stop_window();
}

static void mem_cb(unsigned int vcpu, qemu_plugin_meminfo_t info, uint64_t va, void *ud) {
    if (vcpu != 0 || phase != 1 || is_child) return;
    uint64_t r = (va & 0x00ffffffffffffffull) | ((uint64_t)qemu_plugin_mem_size_shift(info) << 56)
               | ((uint64_t)qemu_plugin_mem_is_store(info) << 59);
    put64(r);
}

static void dump_exec(unsigned int vcpu, void *ud) {
    if (++dump_seen != dump_k) return;
    GByteArray *b = g_byte_array_new();
    if (qemu_plugin_read_memory_vaddr(dump_addr, b, dump_len)) {
        GString *s = g_string_new("");
        g_string_append_printf(s, "DUMP pc=%" PRIx64 " k=%" PRIu64 " addr=%" PRIx64 "\n", dump_pc, dump_k, dump_addr);
        for (guint i = 0; i + 8 <= b->len; i += 8) {
            uint64_t v; memcpy(&v, b->data + i, 8);
            g_string_append_printf(s, "%016" PRIx64 "%s", v, (i / 8) % 4 == 3 ? "\n" : " ");
        }
        g_string_append(s, "\n");
        fputs(s->str, stderr);
        g_string_free(s, TRUE);
    } else fprintf(stderr, "DUMP read failed\n");
    g_byte_array_free(b, TRUE);
}

static void watch_cb(unsigned int vcpu, qemu_plugin_meminfo_t info, uint64_t va, void *ud) {
    if (!qemu_plugin_mem_is_store(info)) return;
    uint64_t sz = 1ull << qemu_plugin_mem_size_shift(info);
    if (va + sz > watch_lo && va < watch_hi)
        fprintf(stderr, "WATCH pc=%" PRIx64 " va=%" PRIx64 " sz=%" PRIu64 " icnt=%" PRIu64 " vcpu=%u\n", (uint64_t)(uintptr_t)ud, va, sz, qemu_plugin_u64_get(icnt, vcpu), vcpu);
}
static void vwatch_cb(unsigned int vcpu, qemu_plugin_meminfo_t info, uint64_t va, void *ud) {
    if (!qemu_plugin_mem_is_store(info) || vwatch_n > 30) return;
    qemu_plugin_mem_value v = qemu_plugin_mem_get_value(info);
    uint64_t x = v.type == QEMU_PLUGIN_MEM_VALUE_U64 ? v.data.u64 : v.type == QEMU_PLUGIN_MEM_VALUE_U128 ? v.data.u128.low : v.type == QEMU_PLUGIN_MEM_VALUE_U32 ? v.data.u32 : 0;
    uint64_t hi = v.type == QEMU_PLUGIN_MEM_VALUE_U128 ? v.data.u128.high : 0;
    if (x == vwatch || hi == vwatch) {
        vwatch_n++;
        fprintf(stderr, "VWATCH pc=%" PRIx64 " va=%" PRIx64 " shift=%u icnt=%" PRIu64 "\n", (uint64_t)(uintptr_t)ud, va, qemu_plugin_mem_size_shift(info), qemu_plugin_u64_get(icnt, vcpu));
    }
}
static void start_window(void);

static void at_exit(qemu_plugin_id_t id, void *p);
static struct qemu_plugin_scoreboard *sb_tick, *sb_on;
static qemu_plugin_u64 tick, on;          /* tick: insns since the last 1M check; on: vcpu 0 is inside a window */
#define TICK 1000000

/* every ~1M wide instructions of a vcpu: open a window when vcpu 0 passed next_start (no TB flush, no reset:
 * the previous design deadlocked multi-threaded guests in qemu_plugin_reset) */
static void tick_cb(unsigned int vcpu, void *ud) {
    qemu_plugin_u64_set(tick, vcpu, 0);
    if (vcpu != 0 || is_child) return;
    if (phase == 0 && qemu_plugin_u64_get(icnt, 0) >= next_start) start_window();
}

/* one ins per translated instruction; its bytes are read and written to the code table on its first execution
 * inside a window (vcpu context: reading guest memory during translation deadlocked multi-threaded guests) */
static struct ins *lookup_ins(struct qemu_plugin_insn *insn) {
    struct ins *p = g_new0(struct ins, 1);
    p->vaddr = qemu_plugin_insn_vaddr(insn);
    p->size = qemu_plugin_insn_size(insn);
    p->sym = qemu_plugin_insn_symbol(insn);
    g_mutex_lock(&lock);
    p->id = nids++;
    g_mutex_unlock(&lock);
    return p;
}

static void emit_code(struct ins *p) {
    uint8_t buf[64] = {0};
    uint32_t sz = p->size > 64 ? 64 : p->size;
    GByteArray *b = g_byte_array_new();
    if (qemu_plugin_read_memory_vaddr(p->vaddr, b, sz)) memcpy(buf, b->data, b->len);
    g_byte_array_free(b, TRUE);
    fprintf(codef, "%u %" PRIx64 " %u ", p->id, p->vaddr, p->size);
    for (uint32_t i = 0; i < sz; i++) fprintf(codef, "%02x", buf[i]);
    fprintf(codef, " %s\n", p->sym ? p->sym : "-");
    p->seen = 1;
}

static void tb_trans(qemu_plugin_id_t id, struct qemu_plugin_tb *tb) {
    size_t n = qemu_plugin_tb_n_insns(tb);
    if (dump_pc)
        for (size_t i = 0; i < n; i++) {
            struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
            if (qemu_plugin_insn_vaddr(insn) == dump_pc)
                qemu_plugin_register_vcpu_insn_exec_cb(insn, dump_exec, QEMU_PLUGIN_CB_NO_REGS, NULL);
        }
    qemu_plugin_register_vcpu_tb_exec_inline_per_vcpu(tb, QEMU_PLUGIN_INLINE_ADD_U64, icnt, n);
    if (vwatch)
        for (size_t i = 0; i < n; i++) {
            struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
            qemu_plugin_register_vcpu_mem_cb(insn, vwatch_cb, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_MEM_W, (void *)(uintptr_t)qemu_plugin_insn_vaddr(insn));
        }
    if (watch_hi)
        for (size_t i = 0; i < n; i++) {
            struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
            qemu_plugin_register_vcpu_mem_cb(insn, watch_cb, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_MEM_W, (void *)(uintptr_t)qemu_plugin_insn_vaddr(insn));
        }
    qemu_plugin_register_vcpu_tb_exec_inline_per_vcpu(tb, QEMU_PLUGIN_INLINE_ADD_U64, tick, n);
    qemu_plugin_register_vcpu_tb_exec_cond_cb(tb, tick_cb, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_COND_GE, tick, TICK, NULL);
    if (win)
        for (size_t i = 0; i < n; i++) {
            struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
            struct ins *p = lookup_ins(insn);
            qemu_plugin_register_vcpu_insn_exec_cond_cb(insn, insn_exec, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_COND_EQ, on, 1, p);
            qemu_plugin_register_vcpu_mem_cb(insn, mem_cb, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_MEM_RW, NULL);
        }
}

static void start_window(void) {
    char fn[512];
    snprintf(fn, sizeof fn, "zstd -q -1 -T1 -f -o %s.w%" PRIu64 ".bin.zst", pfx, cur_win);
    binf = popen(fn, "w");                 /* (v5: records go through zstd, ~36x smaller) */
    setvbuf(binf, NULL, _IOFBF, 1 << 24);
    win_start = qemu_plugin_u64_get(icnt, 0);
    win_n = 0;
    fprintf(infof, "window %" PRIu64 " start %" PRIu64 "\n", cur_win, win_start);
    fflush(infof);
    phase = 1;
    qemu_plugin_u64_set(on, 0, 1);
}

static void stop_window(void) {
    qemu_plugin_u64_set(on, 0, 0);
    pclose(binf); binf = NULL;
    fprintf(infof, "window %" PRIu64 " end %" PRIu64 " n %" PRIu64 "\n", cur_win, qemu_plugin_u64_get(icnt, 0), win_n);
    fflush(infof); fflush(codef);
    cur_win++;
    if (cur_win < nwin && period) { next_start = win_start + period; phase = 0; }
    else { phase = 2; }
}

static void at_exit(qemu_plugin_id_t id, void *p) {
    if (is_child) return;
    phase = 2;
    if (binf) { fprintf(infof, "window %" PRIu64 " end(exit) %" PRIu64 " n %" PRIu64 "\n", cur_win, qemu_plugin_u64_get(icnt, 0), win_n); pclose(binf); binf = NULL; }
    uint64_t tot = 0;
    for (int i = 0; i < qemu_plugin_num_vcpus(); i++) tot += qemu_plugin_u64_get(icnt, i);
    fprintf(infof, "total_insns %" PRIu64 " vcpu0 %" PRIu64 " ids %u\n", tot, qemu_plugin_u64_get(icnt, 0), nids);
    fflush(infof); fflush(codef);   /* (left open: translation may still run on other threads) */
    /* guest mappings (guest_base 0: host maps = guest addresses) for symbolization */
    char fn[512]; snprintf(fn, sizeof fn, "%s.maps", pfx);
    FILE *in = fopen("/proc/self/maps", "r"), *out = fopen(fn, "w");
    if (in && out) { char line[1024]; while (fgets(line, sizeof line, in)) fputs(line, out); }
    if (in) fclose(in);
    if (out) fclose(out);
    fprintf(infof, "pid %d\n", (int)getpid()); fflush(infof);
}

static void set_child(void) { is_child = 1; phase = 2; }   /* a forked guest process records nothing */

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id, const qemu_info_t *info, int argc, char **argv) {
    me = id;
    for (int i = 0; i < argc; i++) {
        char *a = argv[i];
        if (g_str_has_prefix(a, "out=")) pfx = g_strdup(a + 4);
        else if (g_str_has_prefix(a, "skip=")) skip = g_ascii_strtoull(a + 5, NULL, 0);
        else if (g_str_has_prefix(a, "win=")) win = g_ascii_strtoull(a + 4, NULL, 0);
        else if (g_str_has_prefix(a, "period=")) period = g_ascii_strtoull(a + 7, NULL, 0);
        else if (g_str_has_prefix(a, "nwin=")) nwin = g_ascii_strtoull(a + 5, NULL, 0);
        else if (g_str_has_prefix(a, "dump=")) {
            gchar **f = g_strsplit(a + 5, ":", 4);
            dump_pc = g_ascii_strtoull(f[0], NULL, 0); dump_k = g_ascii_strtoull(f[1], NULL, 0);
            dump_addr = g_ascii_strtoull(f[2], NULL, 0); dump_len = g_ascii_strtoull(f[3], NULL, 0);
            g_strfreev(f);
        } else if (g_str_has_prefix(a, "vwatch=")) {
            vwatch = g_ascii_strtoull(a + 7, NULL, 0);
        } else if (g_str_has_prefix(a, "watch=")) {
            gchar **f = g_strsplit(a + 6, ":", 2);
            watch_lo = g_ascii_strtoull(f[0], NULL, 0); watch_hi = watch_lo + g_ascii_strtoull(f[1], NULL, 0);
            g_strfreev(f);
        } else { fprintf(stderr, "etrace: bad arg %s\n", a); return -1; }
    }
    char fn[512];
    snprintf(fn, sizeof fn, "%s.code", pfx); codef = fopen(fn, "w");
    snprintf(fn, sizeof fn, "%s.info", pfx); infof = fopen(fn, "w");
    byaddr = g_hash_table_new(g_int64_hash, g_int64_equal);
    sb = qemu_plugin_scoreboard_new(sizeof(uint64_t));
    icnt = qemu_plugin_scoreboard_u64(sb);
    sb_tick = qemu_plugin_scoreboard_new(sizeof(uint64_t)); tick = qemu_plugin_scoreboard_u64(sb_tick);
    sb_on = qemu_plugin_scoreboard_new(sizeof(uint64_t)); on = qemu_plugin_scoreboard_u64(sb_on);
    next_start = skip;
    phase = win ? 0 : 2;
    if (next_start == 0) next_start = 1;
    qemu_plugin_register_vcpu_tb_trans_cb(id, tb_trans);
    qemu_plugin_register_atexit_cb(id, at_exit, NULL);
    pthread_atfork(NULL, NULL, set_child);
    return 0;
}
