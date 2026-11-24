#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""sim3.py PFX WIN [--warm N] [--pages FILE] [--out OUT.pkl] [--limit N]

sim.py plus the mechanisms found on large programs (docs/FACTS.md "sim3", docs/IDENTITY.md, docs/ACCURACY.md).  With no
SIM_* environment set it behaves exactly as sim.py.  Recommended settings for real programs:
  SIM_ISUB=4 SIM_NEXTN=2 SIM_INFL=1 SIM_SEQT=4:16 SIM_SPEC=12 SIM_L2XC=24  and  --pages FILE (THP coverage).

Trace-driven cycle model of Elbrus-8SV (e2k-v5) for one trace window (PFX.w<WIN>.bin[.zst], decoded by decode.py).
Runs under CPython; PyPy is ~10x faster for big windows.  Output: OUT.pkl (default PFX.w<WIN>.sim.pkl) with cycles per
instruction id and cause, plus a one-line summary on stdout.  See docs/FACTS.md for where every constant comes from.

Per wide instruction:
  fetch: L1I 128 KB modelled 2-way with 256 B lines; a sequential line that misses L1I costs 1.0 (L2) / 3.9 (L3) /
    30 (DRAM, ESTIMATE) cycles beyond issue and nops (the fetch-ahead streams it); a line reached by a taken transfer
    that misses L1I stalls for the refill: 9.3 (L2) / 35 (L3) / 185 (DRAM, ESTIMATE); the fetch-ahead also pulls the
    line after a taken target (NEXTF 5 when it misses L1I); code lines index L2 by VA bits 6..16 unhashed;
    ITLB 64 sets (VA bits 12..17) x 5 ways, +27 at a taken target whose page misses;
  operand wait: measured pair latency (e2kdis.reg_lat); a load that missed L1 has result latency 3 + L2 8 / L3 29 /
    DRAM 180 [measured]; register waits in quanta of 4, predicate waits (elp 1, rlp/mrg 2, ct 3) of 2;
  store -> load (measured windows): relation cover {0,1} / part {0..3} / same 8 B no common byte {0..3} /
    other word of the 32 B block {0,2,3} / 4 KB alias {0..4} / alias of the block {0} cycles after the store:
    load result latency 11; misaligned load latency 11; a load crossing 32 B waits 4; a store crossing 8 B costs 4;
  DTLB at the load: 2 MB pages 256 places x 1 (+36), 4 KB pages 256 sets x 3 (+20) [measured];
  control: taken ct/call/return max(0, prep - d) (disp 5, movtd 9, return 6; not taken 2/5/6); ibranch taken 6 - stall;
  register file: RF_CAP quads resident; a return into a spilled frame fills it [fit, call stand];
  rotating registers: %b[i] maps to (i - 2*rotations) mod 2*(rsz+1) after setbn; abn rotates.
Causes: issue nop dep L2 L3 DRAM stld dtlb ctprep ibranch icache call spill itarget itlb

Environment knobs (defaults = the model fitted to the Elbrus-8SV stands):
  SIM_ITLB=64:5:12   ITLB sets:ways:page-shift     SIM_ITLBX=27   ITLB miss cost at a taken target
  SIM_L1I=128:2:256  L1I KB:ways:line              SIM_NEXTF=5    next-line-after-target miss cost
  SIM_L2CODE=plain   code lines use an unhashed L2 index (anything else: the data hash)
  SIM_HASH=23        which data caches use a hashed set index (1 L1, 2 L2, 3 L3); SIM_L2FOLD=15 fold width
  SIM_IB, SIM_CALLRET, SIM_I32, SIM_STLD_OFF        see the code
  SIM_LAYOUT=FILE    pickled {old 256 B line: new line} map (layout estimates, mklayout/mkfam/mkcolour)
sim3 knobs (all off by default):
  SIM_ISUB=4         a 256 B code line fills 4 x 64 B lines of L2/L3 (HW: 8 x 32 B L2 queries per L1I line fill) [measured]
  SIM_NEXTN=2        lines the fetch-ahead pulls after a taken target (HW: 2-2.7 lines per target miss) [measured]
  SIM_INFL=1         lines pulled after a target are in flight until their refill completes
  SIM_SEQT=4:16      cost (L2:L3) of a next line reached by a TAKEN transfer instead of the streamed 1.0/3.9 [measured]
  SIM_SPEC=12        result latency of a speculative load (ldd,sm) to an invalid page; qemu records no access for such a
                     load, so it is recognised as a speculative load without a record [measured: consumer waits ~8]
  SIM_L2XC=24        extra latency of a data load that hits L2 within SIM_L2XW (200) wide instructions of a code-line
                     refill from L2/L3 (data L2 under code traffic).  FITTED on large programs, NOT measured: the
                     code+data stand gives 16.9 cycles where this term gives 20.0 (stands/l2code)
  SIM_L2X=8          data L2-hit extra latency (stands: 8)
  SIM_L2=512:4 SIM_L2RAND=1 SIM_L3=16   L2 KB:ways, random L2 victims, L3 MB (experiments; not recommended)
  --pages FILE       "LO HI [FRACTION]" per line (hex or decimal, '#' comments): data in [LO, HI) is on 2 MB pages;
                     with FRACTION < 1 only that share of its 2 MB chunks (chosen by a fixed hash) is (partial THP)
The previous variant ("w2": 256-entry direct-mapped ITLB on VA bits 12..19, hashed L2 index for code), refuted by
the ITLB/L2 stands of stands/fetch (itlb8), is SIM_ITLB=256:1:12 SIM_ITLBX=26 SIM_L2CODE=hashed.
"""
import os, sys, pickle, bisect, collections
from array import array
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2kdis as D

L2X, L3X, DRAMX = float(os.environ.get('SIM_L2X', 8)), 29, 180
TLB2M, TLB4K = 36, 20
IB_SIZE = int(os.environ.get("SIM_IB", 16 << 10))
_it = os.environ.get('SIM_ITLB', '64:5:12').split(':')
ITLB_S, ITLB_W, ITLB_G = int(_it[0]), int(_it[1]), int(_it[2])
ITLB_X = float(os.environ.get('SIM_ITLBX', 27))
L2CP = os.environ.get("SIM_L2CODE", "plain") == "plain"   # code lines: L2 index VA bits 6..16 unhashed (stands/fetch itlb8)
NEXTF = float(os.environ.get('SIM_NEXTF', 5))   # the fetch-ahead also pulls the line after a taken target; cost when it misses L1I
NEXTN = int(os.environ.get('SIM_NEXTN', 1))     # lines the fetch-ahead pulls after a taken target (fill L1I + L2)
_st = os.environ.get('SIM_SEQT', '')            # 'L2:L3' cost of the next line reached by a TAKEN transfer (else streamed)
SEQT = tuple(float(x) for x in _st.split(':')) if _st else None
SPEC_LAT = float(os.environ.get('SIM_SPEC', 0)) # result latency of a speculative load to an invalid page (no trace record); 0 = off
INFL = os.environ.get('SIM_INFL', '0') == '1'   # lines pulled after a target are in flight until their refill completes
ISUB = int(os.environ.get('SIM_ISUB', 1))       # 64 B L2/L3 lines filled per 256 B code line (HW: 4)
# code-page TLB: 64 sets (VA bits 12..17) x 5 ways, miss +27 at a taken target (walk load hits L2): stands/fetch itlb8
FT_L2, FT_L3, FT_DRAM = 9.3, 35.0, 185.0   # taken-transfer target missing L1I: L2 / L3 served (fetch stands far16/far64), DRAM ESTIMATE
FS_L1, FS_L2, FS_L3, FS_DRAM = 0.0, 1.0, 3.9, 30.0   # cycles per 256 B line beyond issue+nops (code sweep; DRAM ESTIMATE)
CALLRET = float(os.environ.get('SIM_CALLRET', 0))   # fetch stands: call cost = ct preparation + the callee's nops
I32_FAST = os.environ.get('SIM_I32', '1') == '1'   # measured: a 64-bit read of a 32-bit write waits only for the int latency
RF_CAP = 224   # quads resident (fit: depth-16 x wsz-12 recursion barely spills on 8SV)
CTPR_LAT = {'disp': (5, 2), 'movtd': (9, 5), 'ret': (6, 6)}
PRED_LAT = {'rlp': 2, 'mrg': 2, 'elp': 1, 'ct': 3}
CAUSES = ('issue', 'nop', 'dep', 'L2', 'L3', 'DRAM', 'stld', 'dtlb', 'ctprep', 'ibranch', 'icache', 'call', 'spill', 'itarget', 'itlb')
CI = {c: i for i, c in enumerate(CAUSES)}
NC = len(CAUSES)
STLD_WIN = {'cover': (0, 1), 'part': (0, 1, 2, 3), 'dword': (0, 1, 2, 3), 'blk': (0, 2, 3), 'a4k': (0, 1, 2, 3, 4), 'a4kblk': (0,)}
for _r in os.environ.get('SIM_STLD_OFF', 'blk,a4kblk').split(','):   # block-neighbour hits: cancelled in practice (ablation on a recursive benchmark)
    if _r: STLD_WIN[_r] = ()
LATK = ('int', 'int32', 'load', 'mul', 'fp', 'fp2int', 'fw', 'fdivd', 'fdivs', 'qp', 'qpfp', 'sreg', 'comb', 'apb')


def q4(x):
    return 0 if x <= 0 else (x + 3) // 4 * 4


class Cache:
    __slots__ = ('nsets', 'ways', 'shift', 'sets', 'hits', 'miss', 'hb', 'rnd')

    def __init__(self, size, ways, line, hashed=False):
        self.nsets = size // (ways * line)
        self.hb = (hashed if type(hashed) is int and hashed is not True else (self.nsets.bit_length() - 1)) if hashed else 0
        self.ways = ways
        self.shift = line.bit_length() - 1
        self.sets = [[] for _ in range(self.nsets)]
        self.hits = self.miss = 0
        self.rnd = None

    def access(self, addr, fill=True, plain=False):
        ln = addr >> self.shift
        hb = 0 if plain else self.hb
        s = self.sets[(ln ^ (ln >> hb) ^ (ln >> (2 * hb))) % self.nsets if hb else ln % self.nsets]
        if ln in s:
            if s[-1] != ln:
                s.remove(ln); s.append(ln)
            self.hits += 1
            return True
        self.miss += 1
        if fill:
            if len(s) >= self.ways and self.rnd is not None:   # random victim (SIM_L2RAND)
                self.rnd = (self.rnd * 6364136223846793005 + 1442695040888963407) & 0xffffffffffffffff
                del s[(self.rnd >> 33) % self.ways]
            s.append(ln)
            if len(s) > self.ways: del s[0]
        return False

    def probe_update(self, addr):
        ln = addr >> self.shift
        hb = self.hb
        s = self.sets[(ln ^ (ln >> hb) ^ (ln >> (2 * hb))) % self.nsets if hb else ln % self.nsets]
        if ln in s:
            if s[-1] != ln:
                s.remove(ln); s.append(ln)
            return True
        return False


class Mem:
    def __init__(self, pages=None):
        self.l1 = Cache(64 << 10, 4, 32)
        hs = os.environ.get('SIM_HASH', '23')
        self.l1 = Cache(64 << 10, 4, 32, '1' in hs)
        _l2 = os.environ.get('SIM_L2', '512:4').split(':')
        self.l2 = Cache(int(_l2[0]) << 10, int(_l2[1]), 64, int(os.environ.get('SIM_L2FOLD', 15)) if '2' in hs else 0)   # hashed set index (tlb stands: no 2 MB-stride conflicts on 8SV)
        if os.environ.get('SIM_L2RAND') == '1': self.l2.rnd = 12345
        self.l3 = Cache(int(float(os.environ.get('SIM_L3', 16)) * (1 << 20)), 16, 64, '3' in hs)   # SIM_L3: L3 MB
        _l1i = os.environ.get('SIM_L1I', '128:2:256').split(':')   # KB:ways:block -- index VA bits 9..14 (span stands, FETCH.md)
        self.l1i = Cache(int(_l1i[0]) << 10, int(_l1i[1]), int(_l1i[2]))
        self.itlb = [[] for _ in range(ITLB_S)]
        self.ib = collections.OrderedDict()
        self.ibn = IB_SIZE >> 8
        self.t2m = [None] * 256
        self.t4k = [[] for _ in range(256)]
        self.huge = pages or []
        self.hlo = [r[0] for r in self.huge]
        self.cnt = collections.Counter()
        self.lastline = -1
        self.prevline = -1
        self.ptaken = False
        self.iready = {}
        self.icnt = 0; self.last_ifill = -10 ** 9; self.l2c = False
        self.tf = 0.0
        lf = os.environ.get('SIM_LAYOUT')
        self.layout = pickle.load(open(lf, 'rb')) if lf else None   # old 256 B code line -> new line (layout estimate)
        self.pages = set()

    def is_huge(self, a):
        i = bisect.bisect_right(self.hlo, a) - 1
        if i < 0 or a >= self.huge[i][1]: return False
        f = self.huge[i][2]
        if f >= 1.0: return True
        c = a >> 21                       # only a fraction f of the 2 MB chunks of this range are THP (HW smaps)
        return ((c * 2654435761) & 0xffffffff) < f * 4294967296.0

    def dtlb(self, a):
        if self.is_huge(a):
            pg = a >> 21; p = pg & 255
            if self.t2m[p] == pg: return 0
            self.t2m[p] = pg; self.cnt['dtlb_miss'] += 2
            return TLB2M
        pg = a >> 12
        s = self.t4k[pg & 255]
        if pg in s:
            if s[-1] != pg: s.remove(pg); s.append(pg)
            return 0
        s.append(pg)
        if len(s) > 3: del s[0]
        self.cnt['dtlb_miss'] += 1
        return TLB4K

    def load(self, a, size):
        self.cnt['ld'] += 1
        lvl = self._lvl(a)
        e = a + size - 1
        if (e >> 5) != (a >> 5):
            lvl = max(lvl, self._lvl(e))
        return lvl

    def first_touch(self, a):
        """a page first seen by a store inside the window: a fresh allocation the kernel has just zeroed (page fault)"""
        pg = a >> 12
        if pg in self.pages: return
        self.pages.add(pg); self.cnt['new_pages'] += 1
        b = pg << 12
        for o in range(0, 4096, 64):
            self.l3.access(b + o); self.l2.access(b + o)

    def _lvl(self, a):
        if (a >> 12) not in self.pages: self.pages.add(a >> 12)   # seen first by a load: an old page, no help
        if self.l1.access(a):
            return 0
        self.cnt['l1_ld_miss'] += 1; self.cnt['l2_query'] += 1
        if self.l2.access(a):
            if L2XC and self.icnt - self.last_ifill < L2XW: self.l2c = True
            return 1
        if self.l3.access(a):
            self.cnt['replay'] += 0.3
            return 2
        self.cnt['replay'] += 1.0
        self.cnt['l3_miss'] += 1
        return 3

    def store(self, a, size):
        if (a >> 12) not in self.pages: self.first_touch(a)
        self.cnt['st'] += 1; self.cnt['l2_query'] += 1
        self.l1.probe_update(a)
        if not self.l2.access(a):
            self.l3.access(a)

    def ifill(self, ln):
        """code line ln (256 B) from L2/L3: returns level 1 (L2) / 2 (L3) / 3 (DRAM) of its first 64 B; fills ISUB 64 B lines"""
        a = ln << 8
        self.last_ifill = self.icnt
        self.cnt['icode_l2_lines'] += 1
        if self.l2.access(a, plain=L2CP): lv = 1
        elif self.l3.access(a): lv = 2
        else: lv = 3
        if lv > 1: self.cnt['icode_l2_miss'] += 1
        for q in range(1, ISUB):
            b = a + 64 * q
            if not self.l2.access(b, plain=L2CP): self.l3.access(b)
        return lv

    def remap(self, ln):
        m = self.layout
        if m is None: return ln
        r = m.get(ln)
        return r if r is not None else ln + (1 << 40)      # cold code: far away from the packed hot region

    def fetch(self, a, size, T0):
        """instruction supply (fetch stands, reports/FETCH.md): the fetch-ahead streams sequential lines, so a sequential
        line costs only FS_L2 / FS_L3 / FS_DRAM beyond issue and nops when it misses L1I; a line reached by a taken transfer
        (non-sequential) that misses L1I stalls dispatch for the whole refill: FT_L2 / FT_L3 / FT_DRAM.  A target in L1I is
        free (taken-transfer cost is the ctpr preparation, modelled at the ct)."""
        st = 0.0; tg = 0.0; tl = 0.0
        self.icnt += 1
        for ln0 in range(a >> 8, ((a + size - 1) >> 8) + 1):
            ln = self.remap(ln0)
            if ln == self.lastline: continue
            seq = ln == self.lastline + 1
            tseq = seq and self.ptaken and SEQT is not None
            self.ptaken = False
            self.lastline = ln
            self.cnt['ib_ahead_query'] += 1
            pg = (ln << 8) >> ITLB_G
            it = self.itlb[pg % ITLB_S]
            if pg in it:
                if it[-1] != pg: it.remove(pg); it.append(pg)
            else:
                it.append(pg)
                if len(it) > ITLB_W: del it[0]
                self.cnt['itlb_miss'] += 1
                if not seq: tl += ITLB_X
            if (not seq or tseq) and NEXTF and size <= 256:
                for q in range(1, NEXTN + 1):
                    if not self.l1i.access((ln + q) << 8):
                        self.cnt['next_miss'] += 1
                        lq = self.ifill(ln + q)
                        if q == 1: tg += NEXTF
                        if INFL:
                            if len(self.iready) > 4096: self.iready.clear()
                            self.iready[ln + q] = T0 + (FT_L2, FT_L3, FT_DRAM)[lq - 1] + 2 * q
            if self.l1i.access(ln << 8):
                if INFL and ln in self.iready:
                    w_ = self.iready.pop(ln) - (T0 + st + tg + tl)
                    if w_ > 0:
                        self.cnt['inflight'] += 1
                        if seq and not tseq: st += w_
                        else: tg += w_
                continue
            self.cnt['l1i_miss'] += 1; self.cnt['l2_query'] += 1
            if not seq: self.cnt['l1i_target_miss'] += 1
            lv = self.ifill(ln)
            if tseq:
                self.cnt['l1i_tseq_miss'] += 1
                tg += (SEQT[0], SEQT[1], FT_DRAM)[lv - 1]
            elif seq:
                st += (FS_L2, FS_L3, FS_DRAM)[lv - 1]
            else:
                tg += (FT_L2, FT_L3, FT_DRAM)[lv - 1]
        self.ptaken = False
        return st, tg, tl


L2XC = float(os.environ.get('SIM_L2XC', 0))     # data L2-hit extra while code is being refilled from L2 (0 = off)
L2XW = int(os.environ.get('SIM_L2XW', 200))     #       "while" = a code line came from L2/L3 within the last L2XW instructions
LVLX = (0, L2X, L3X, DRAMX, L2XC)
LVLC = (None, 'L2', 'L3', 'DRAM', 'L2')


def prep_static(dec):
    st = {}
    for i, d in dec.items():
        if d is None:
            st[i] = None; continue
        ops = []
        for o in d['ops']:
            if o['k'] == 'logic':
                ops.append(('logic', -1, 'logic', (), (), tuple(o['pr']), tuple(o['pw']), None))
                continue
            pk = o['pk']; mem = o.get('mem')
            if mem == 'ld' and o.get('sm') and not o['pr']: mem = 'lds'   # speculative load (may hit an invalid page)
            if pk == 'apb' and o['name'].startswith('mova'):
                pk = 'load'
            if pk not in LATK: pk = 'int'
            ops.append((o['name'], o['ch'], pk, tuple((k, w, u) for k, w, u in o['reads']), tuple(k for k, w in o['writes']),
                        tuple(o['pr']), tuple(o['pw']), mem))
        nld = sum(1 for o in ops if o[7] in ('ld', 'lds')); nst = sum(1 for o in ops if o[7] == 'st')
        for o in d['ops']:            # quad (qp) memory ops make two 8 B records in qemu: allow them
            if o.get('mem') and (o['name'].endswith(('qp', 'q')) or 'qp' in o['name']):
                if o['mem'] == 'ld': nld += 1
                else: nst += 1
        st[i] = (d['addr'], d['size'], d['nop'], tuple(ops), d['ctl'], tuple(d['preps']), d['hwloop'], d['nalu'],
                 d.get('wsz'), d.get('setbn'), d.get('rot', False), nld, nst)
    return st


def stld_rel(s0, ssz, l0, lsz):
    if l0 < s0 + ssz and s0 < l0 + lsz:
        return 'cover' if (s0 <= l0 and l0 + lsz <= s0 + ssz) else 'part'
    if (s0 >> 3) == (l0 >> 3): return 'dword'
    if (s0 >> 5) == (l0 >> 5): return 'blk'
    a, b = s0 & 0xfff, l0 & 0xfff
    if a < b + lsz and b < a + ssz: return 'a4k'
    if (a >> 5) == (b >> 5): return 'a4kblk'
    return None


class Frame:
    __slots__ = ('id', 'rsz', 'rot', 'wsz')

    def __init__(self, fid):
        self.id = fid; self.rsz = 0; self.rot = 0; self.wsz = 8


def run(pfx, win, warm=0, pages=None, limit=None):
    meta = pickle.load(open(pfx + '.dec.pkl', 'rb'))
    st = prep_static(meta['dec'])
    mem = Mem(pages)
    recs = array('Q')
    fn = '%s.w%d.bin' % (pfx, win)
    if os.path.exists(fn):
        recs.frombytes(open(fn, 'rb').read())
    else:                                   # zstd-compressed window (plugin v5 / compressed after tracing)
        import subprocess
        recs.frombytes(subprocess.run(['zstd', '-q', '-d', '-c', fn + '.zst'], capture_output=True).stdout)
    n = len(recs)
    acc = {}
    execs = collections.Counter()
    regs = {}; preds = {}; ctpr = {}
    fr = Frame(0); fstack = []; nextid = 1
    depth_q = 8; base_q = 0; sdepth = 0
    T = 0.0; i = 0; ninsn = 0
    totals = [0.0] * NC
    stores = collections.deque(maxlen=12)
    unk = 0
    reg_lat = D.reg_lat
    prev_nop = 0
    while i < n and not (recs[i] >> 63): i += 1
    while i < n:
        r = recs[i]
        iid = r & 0xffffffff
        j = i + 1
        lds = []; sts = []
        while j < n:
            m = recs[j]
            if m >> 63: break
            va = m & 0xffffffffffffff
            sz = 1 << ((m >> 56) & 7)
            if (m >> 59) & 1: sts.append((va, sz))
            else: lds.append((va, sz))
            j += 1
        nxt_va = None
        if j < n:
            s2 = st.get(recs[j] & 0xffffffff)
            nxt_va = s2[0] if s2 else None
        i = j
        s = st.get(iid)
        ninsn += 1
        counting = ninsn > warm
        if ninsn == warm + 1:
            mem.cnt.clear()
        if s is None:
            unk += 1; T += 1
            continue
        addr, size, nop, ops, ctl, preps, hwloop, nalu, wsz, setbn, rot, nld, nst = s
        if len(lds) > nld:          # qemu's hardware-stack spill/fill (call/return) shows up as memory records
            mem.cnt['hwstack'] += len(lds) - nld; lds = lds[:nld]
        if len(sts) > nst:
            mem.cnt['hwstack'] += len(sts) - nst; sts = sts[:nst]
        if wsz:
            fr.wsz = wsz
            depth_q = sdepth + wsz             # frames below + this one (quads)
            if depth_q - base_q > RF_CAP: base_q = depth_q - RF_CAP
        if setbn: fr.rsz = 2 * (setbn[1] + 1); fr.rot = 0
        cyc = [0.0] * NC
        T0 = T
        fs, ft, fl = mem.fetch(addr, size, T0)
        if fs or ft or fl:
            cyc[10] += fs; cyc[13] += ft; cyc[14] += fl; T0 += fs + ft + fl
        fid = fr.id; rsz = fr.rsz; rotv = fr.rot
        stall = 0; scause = 'dep'; smem = 0
        for name, ch, pk, reads, writes, pr, pw, mk in ops:
            for k, w, use in reads:
                t = k[0]
                if t == 'b':
                    key = (fid, 'b', (k[1] - rotv) % rsz if rsz else k[1])
                elif t == 'r':
                    key = (fid, 'r', k[1])
                else:
                    key = k
                p = regs.get(key)
                if p is None: continue
                tp, ppk, pch, extra, ecause = p
                if ppk == 'logic': continue
                other = (pch // 3) != (ch // 3) if pch >= 0 and ch >= 0 else False
                lat = reg_lat('int' if (ppk == 'int32' and I32_FAST) else ppk, use, w, other, name)
                need = q4(tp + lat - T0)
                if extra:
                    need2 = tp + extra - T0
                    if need2 > need:
                        if need2 > stall:
                            stall = need2; scause = ecause; smem = max(0, need2 - max(need, 0))
                        continue
                if need > stall:
                    stall = need; scause = 'dep'; smem = 0
            for p, how in pr:
                tr = preds.get(p)
                if tr is not None:
                    need = tr + PRED_LAT.get(how, 2) - T0
                    if need > 0:
                        need = (need + 1) // 2 * 2
                        if need > stall:
                            stall = need; scause = 'dep'; smem = 0
        if ctl is not None:
            for p, how in ctl[3]:
                tr = preds.get(p)
                if tr is not None:
                    need = tr + PRED_LAT['ct'] - T0
                    if need > stall:
                        need = (need + 1) // 2 * 2
                        stall = need; scause = 'dep'; smem = 0
        if stall > 0:
            if scause != 'dep':
                cyc[CI[scause]] += smem; cyc[2] += stall - smem
            else:
                cyc[2] += stall
        T1 = T0 + stall
        tl = 0; lres = []; unal = 0
        for va, sz in lds:
            x = mem.dtlb(va)
            if x > tl: tl = x
            mem.l2c = False
            lvl = mem.load(va, sz)
            if lvl == 1 and mem.l2c: lvl = 4; mem.cnt['l2_under_code'] += 1
            lat = 0
            for ts, s0, ssz in stores:
                d = T1 - ts
                if d > 4: continue
                rel = stld_rel(s0, ssz, va, sz)
                if rel and int(d) in STLD_WIN[rel]:
                    lat = 11; break
            if va % (sz if sz <= 8 else 8):          # (16 B qp accesses: 8 B alignment is aligned)
                lat = 11
                if (va & 31) + sz > 32: unal = 4
            lres.append((lvl, lat))
        if tl:
            cyc[7] += tl; T1 += tl
        if unal:
            cyc[6] += unal; T1 += unal
        stbub = 0
        for va, sz in sts:
            mem.dtlb(va); mem.store(va, sz)
            stores.append((T1, va, sz))
            if sz <= 8 and (va & 7) + sz > 8: stbub += 4     # a misaligned store crossing 8 B
            elif sz > 8 and va & 7: stbub += 4
        bub = 0; bcause = None; extra_call = 0; spill = 0
        if ctl is not None:
            kind, cp, cond, cpr = ctl
            taken = nxt_va is not None and (nxt_va != addr + size or not cond)   # unconditional: taken even to the fall-through
            mem.ptaken = taken
            if kind == 'ibranch':
                if taken:
                    bub = max(0, 6 - stall); bcause = 'ibranch'
            else:
                pt = ctpr.get(cp)
                if pt is not None:
                    d = T1 - pt[0]
                    lt, lnt = CTPR_LAT.get(pt[1], (5, 2))
                    bub = max(0, (lt if taken else lnt) - d); bcause = 'ctprep'
                if taken:
                    if kind == 'call':
                        fstack.append(fr); sdepth += fr.wsz or 8
                        fr = Frame(nextid); nextid += 1
                        fr.wsz = None
                        if len(fstack) > mem.cnt['maxdepth']: mem.cnt['maxdepth'] = len(fstack)
                        extra_call = CALLRET / 2
                        mem.cnt['calls'] += 1
                    elif pt is not None and pt[1] == 'ret':
                        if fstack:
                            fr = fstack.pop(); sdepth -= fr.wsz or 8
                        else:
                            fr = Frame(nextid); nextid += 1; sdepth = 0
                        fw = fr.wsz or 8
                        depth_q = sdepth + fw
                        bottom = sdepth
                        if bottom < base_q:
                            filled = base_q - max(bottom, 0)
                            spill = 1.08 * fw if fw > 8 else 0.0   # fit: a return into a spilled frame: wsz 8 free, wsz 12 13 cycles (call stand)
                            mem.cnt['fills'] += 1
                            base_q = max(bottom, 0)
                        extra_call = CALLRET / 2
        if bub: cyc[CI[bcause]] += bub
        if stbub: cyc[6] += stbub
        if extra_call: cyc[11] += extra_call
        if spill: cyc[12] += spill
        li = 0; nl = len(lres)
        skip = 0
        if SPEC_LAT and nl < nld:                 # loads without a record: speculative loads to invalid pages (stands/spec)
            skip = nld - nl
        for name, ch, pk, reads, writes, pr, pw, mk in ops:
            extra = 0; ecause = None
            if mk == 'lds' and skip:
                skip -= 1; extra = SPEC_LAT; ecause = 'dtlb'; mem.cnt['spec_inval'] += 1
            elif mk in ('ld', 'lds') and li < nl:
                lvl, lat = lres[li]; li += 1
                if name.startswith('mova'): lvl = 0
                if lvl:
                    extra = 3 + LVLX[lvl] + (lat if lat else 0) * 0; ecause = LVLC[lvl]
                elif lat:
                    extra = lat; ecause = 'stld'
            for k in writes:
                t = k[0]
                if t == 'b':
                    key = (fid, 'b', (k[1] - rotv) % rsz if rsz else k[1])
                elif t == 'r':
                    key = (fid, 'r', k[1])
                else:
                    key = k
                regs[key] = (T1, pk, ch, extra, ecause)
            for p in pw:
                preds[p] = T1 + (2 if name.startswith('fcmp') else 0)
        for c, kind in preps:
            ctpr[c] = (T1, kind)
        if rot and rsz:
            fr.rot += 2
        cyc[0] += 1; cyc[1] += nop
        T = T1 + 1 + nop + bub + stbub + extra_call + spill
        prev_nop = nop + bub
        if counting:
            a = acc.get(iid)
            if a is None:
                a = acc[iid] = [0.0] * NC
            for c in range(NC):
                v = cyc[c]
                if v:
                    a[c] += v; totals[c] += v
            execs[iid] += 1
        if limit and ninsn >= limit:
            break
    return dict(acc=acc, execs=execs, totals=totals, ninsn=ninsn, warm=warm, unk=unk,
                mem=dict(mem.cnt), causes=CAUSES, ver=2)


def main():
    a = sys.argv
    pfx, win = a[1], int(a[2])
    warm = int(a[a.index('--warm') + 1]) if '--warm' in a else 0
    limit = int(a[a.index('--limit') + 1]) if '--limit' in a else None
    pages = []
    if '--pages' in a:
        for l in open(a[a.index('--pages') + 1]):
            f = l.split()
            if len(f) >= 2 and not l.startswith('#'):
                pages.append((int(f[0], 0), int(f[1], 0), float(f[2]) if len(f) > 2 else 1.0))
    pages.sort()
    out = a[a.index('--out') + 1] if '--out' in a else '%s.w%d.sim.pkl' % (pfx, win)
    r = run(pfx, win, warm, pages, limit)
    pickle.dump(r, open(out, 'wb'))
    cyc = sum(r['totals']); n = r['ninsn'] - r['warm']
    print('insns %d (warm %d, unknown %d) cycles %d  IPC %.3f' % (n, r['warm'], r['unk'], cyc, n / max(cyc, 1)))
    print('  ' + '  '.join('%s %.1f%%' % (c, 100.0 * v / max(cyc, 1)) for c, v in zip(CAUSES, r['totals']) if v))
    print('  mem', {k: int(v) for k, v in r['mem'].items()})


if __name__ == '__main__':
    main()
