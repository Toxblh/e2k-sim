#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""e2k-v5 objdump listing -> wide commands -> operations with reads/writes.

Parses the text listing GNU objdump (binutils with e2k support, as shipped with e2k Linux distributions)
prints for elbrus-v5 code, so it covers every operation objdump knows, including qp and APB ones.
Register latencies (reg_lat) are our own measurements on Elbrus-8SV (producer/consumer class x lane
stands, see docs/FACTS.md).  Marks in comments:
  M  measured on Elbrus-8SV,  A  assumed (not measured).
"""
import re
from dataclasses import dataclass, field

HDR = re.compile(r'^\s*([0-9a-f]+):\t([0-9a-f ]+)\s*$')
ALU = re.compile(r'^([a-z_0-9]+),([0-5])(,sm)?\s*(.*)$')
COND = re.compile(r'\s\?\s+(~?)(%pred(\d+)|%pcnt\d+|#\w+|%[a-z]+\d*)(.*)$')

# ---------------------------------------------------------------- operands
REG = re.compile(r'%(?:q?p?|d|x)?(r|g|b\[)(\d+)\]?$')


def reg_of(t):
    """'%dr3' -> ('r3', width) ; width 32/64/128.  None for non-registers."""
    t = t.strip()
    m = re.match(r'^%(qp|d|x|)(r|g)(\d+)$', t)
    if m:
        w = {'qp': 128, 'd': 64, 'x': 80, '': 32}[m.group(1)]
        return (m.group(2) + m.group(3), w)
    m = re.match(r'^%(qp|d|x|)b\[(\d+)\]$', t)
    if m:
        w = {'qp': 128, 'd': 64, 'x': 80, '': 32}[m.group(1)]
        return ('b' + m.group(2), w)
    return None


def lit_halves(t):
    t = t.strip()
    if t.startswith('_f64') or t.startswith('_lit64'): return 4
    if t.startswith('_f32') or t.startswith('_lit32'): return 2
    if t.startswith('_f16') or t.startswith('_lit16'): return 1
    return 0


def lit_value(t):
    m = re.search(r'0x([0-9a-f]+)', t)
    if not m: return None
    v = int(m.group(1), 16)
    if t.strip().startswith('_f16s') and v & 0x8000: v -= 1 << 16
    if t.strip().startswith('_f32s') and v & 0x80000000: v -= 1 << 32
    return v


# ---------------------------------------------------------------- classes
APB = ('ldaa', 'staa', 'aau', 'movab', 'movah', 'movaw', 'movad', 'movaq', 'apb', 'incr', 'bap', 'eap')
INT32 = {'adds', 'subs', 'ands', 'andns', 'ors', 'orns', 'xors', 'xorns', 'shls', 'shrs', 'sars', 'scls', 'scrs',
         'getfs', 'merges', 'insfs', 'muls', 'umulx', 'smulx', 'sdivs', 'udivs', 'lzcnts', 'popcnts', 'fstois',
         'fstoistr', 'fdtois', 'fdtoistr'}


def classify(name):
    """Producer kind and the use class of the operation's inputs."""
    n = name
    if n.startswith(APB): return 'apb', 'int'
    if n.startswith('ld'): return 'load', 'int'
    if n.startswith('st'): return 'store', 'int'
    if n in ('adds_fw', 'subs_fw') or n.endswith('_fw'): return 'fw', 'int'
    if n.startswith('fdiv') or n.startswith('qpfdiv'): return ('fdivs' if n.endswith('s') else 'fdivd'), 'fp'
    if n.startswith('cmp') or n.startswith('fcmp') or n.startswith('cctop') or n.startswith('pcmp') and False:
        return 'cmp', ('fp' if n.startswith('f') else 'int')
    if n.startswith('qpf') or n.startswith('pf'): return 'qpfp', 'fp'
    if n.startswith('qp'):
        return 'qp', 'qp'
    if n.startswith('p') and n not in ('popcntd', 'popcnts'):
        return 'qp', 'qp'            # 64-bit packed ops run in the vector unit: pandd/pshufb -> addd 4 (M)
    if n.startswith('f') and 'toi' in n and 'toif' not in n: return 'fp2int', 'fp'
    if n.startswith('f') or n.startswith('isto') or n.startswith('idto'):
        return 'fp', ('mul' if n.startswith('i') else 'fp')
    if any(k in n for k in ('mul', 'div', 'mod')): return 'mul', 'mul'
    if '_' in n and not n.startswith('plog'): return 'comb', 'int'      # add_addd, shl_adds ... (A latency)
    if n in ('rrd', 'rrs', 'getsp'): return 'sreg', 'int'     # rrd %ip / getsp -> addd: 2 (M)
    if n in INT32: return 'int32', 'int'
    return 'int', 'int'


def reg_lat(pk, use, rd_width, other_lane, cons_name=''):
    """Cycles from producer command to a consumer that does not stall.
    use: int | fp | mul | qp | st (stored value) | addr.  M unless noted."""
    st = use == 'st'
    if pk == 'int' or pk == 'apb':
        if use == 'qp': return 1
        return 1 if st else (2 if other_lane else 1)
    if pk == 'int32':
        if rd_width == 32 or cons_name == 'sxt' or cons_name in INT32:
            return 1 if st else (2 if other_lane else 1)
        return 4
    if pk == 'load':
        return 3 if st else (4 if other_lane else 3)
    if pk == 'mul': return {'int': 6, 'addr': 6, 'fp': 5, 'mul': 4, 'st': 4, 'qp': 6}[use]
    if pk == 'fp':
        if other_lane and not st: return 6
        return {'int': 6, 'addr': 6, 'fp': 4, 'mul': 5, 'st': 4, 'qp': 6}[use]
    if pk == 'fp2int': return 6
    if pk == 'fw': return 2 if (rd_width == 32 or cons_name.startswith('cctop')) else 4
    if pk == 'fdivd': return 16
    if pk == 'fdivs': return 13
    if pk == 'qp':                       # qp/packed int ops: 1 own lane, 4 other lane; -> scalar consumer 4 (M)
        if use == 'qp': return 4 if other_lane else 1
        if st: return 3 if other_lane else 1   # qpxor -> std value: 1 own lane, 3 other (M)
        return 4
    if pk == 'qpfp': return 6 if other_lane else 4
    if pk == 'sreg': return 3 if (other_lane and not st) else 2   # other lane +1: A
    if pk == 'comb': return 4 if other_lane else 2      # add_addd/shl_adds -> addd: 2 own lane, 4 other (M)
    return 1


# ---------------------------------------------------------------- data
@dataclass
class Op:
    idx: int
    cmd: int                 # index of the command in the listing
    kind: str                # alu | logic | ct | call | ibranch | disp | ret | misc
    name: str
    ch: int = -1
    sm: bool = False
    pk: str = 'int'
    use: str = 'int'
    reads: list = field(default_factory=list)     # (regname, width, use)
    writes: list = field(default_factory=list)    # (regname, width)
    pred_reads: list = field(default_factory=list)  # (pred, how) how: rlp|mrg|elp|ct
    pred_writes: list = field(default_factory=list)
    lit: int = 0             # literal 16-bit halves
    lits: list = field(default_factory=list)   # (text, halves): equal literals share a syllable
    mem: tuple = None        # ('ld'|'st', base, disp, size) base None if unknown
    ctpr_r: int = -1         # ct/call: ctpr read
    ctpr_w: int = -1         # disp/return/movtd: ctpr prepared
    cond: bool = False       # conditional transfer
    elp: int = 0             # logic: ELP syllables used
    clp: int = 0             # logic: CLP syllables used
    flags: set = field(default_factory=set)      # apb, loop, qp, unknown, barrier
    text: str = ''


@dataclass
class Cmd:
    idx: int
    addr: int
    size: int
    nop: int = 0
    lines: list = field(default_factory=list)
    ops: list = field(default_factory=list)
    flags: set = field(default_factory=set)
    target: int = None       # ibranch target / disp targets in cs0
    disp_targets: list = field(default_factory=list)


def parse_listing(text):
    cmds = []
    cur = None
    for line in text.splitlines():
        m = HDR.match(line)
        if m:
            nb = len(m.group(2).split())
            cur = Cmd(len(cmds), int(m.group(1), 16), nb)
            cmds.append(cur)
            continue
        if cur is None: continue
        s = line.strip()
        if not s or s.startswith('Disassembly') or s.endswith('>:') or 'file format' in s: continue
        cur.lines.append(s)
    for c in cmds: parse_cmd(c)
    return cmds


MEMSIZE = {'b': 1, 'h': 2, 'w': 4, 'd': 8, 'q': 16}


def split_args(a):
    return [x.strip() for x in a.split(',')] if a.strip() else []


def parse_cmd(c):
    ops = []
    logic_lines = []

    def new(kind, name, **kw):
        o = Op(idx=-1, cmd=c.idx, kind=kind, name=name, **kw)
        ops.append(o)
        return o

    for s in c.lines:
        cond_neg, cond_p, cond_other = False, -1, None
        mc = COND.search(' ' + s)
        body = s
        if mc:
            body = (' ' + s)[:mc.start()].strip()
            cond_neg = mc.group(1) == '~'
            if mc.group(3): cond_p = int(mc.group(3))
            else: cond_other = mc.group(2)
        if s.startswith('nop'):
            p = s.split()
            c.nop = int(p[1]) if len(p) > 1 else 0
            continue
        if s.startswith('ipd') or s.startswith('loop_mode'):
            if s.startswith('loop_mode'): c.flags.add('hwloop')
            continue
        if s.startswith('pass') or s.startswith('landp') or s.startswith('andp') or s.startswith('movep'):
            logic_lines.append(s)
            continue
        if s.startswith(('alc', 'abn', 'abp', 'abg', 'bap', 'eap')):
            c.flags.add('rot' if s.startswith(('abn', 'abp', 'abg')) else 'hwloop')
            continue
        m = re.match(r'^(ct|call)\s+%ctpr(\d)', s)
        if m:
            o = new(m.group(1), m.group(1), ctpr_r=int(m.group(2)), cond=bool(mc))
            if cond_p >= 0: o.pred_reads.append((cond_p, 'ct'))
            if cond_other: o.flags.add('loopcond')
            o.text = s
            continue
        m = re.match(r'^ibranch\s+0x([0-9a-f]+)', s)
        if m:
            o = new('ibranch', 'ibranch', cond=bool(mc))
            c.target = int(m.group(1), 16)
            if cond_p >= 0: o.pred_reads.append((cond_p, 'ct'))
            if cond_other: o.flags.add('loopcond')
            o.text = s
            continue
        m = re.match(r'^(disp|ldisp)\s+%ctpr(\d),\s*0x([0-9a-f]+)', s)
        if m:
            new('disp', m.group(1), ctpr_w=int(m.group(2)), text=s)
            c.disp_targets.append(int(m.group(3), 16))
            continue
        m = re.match(r'^sdisp\s+%ctpr(\d)', s)
        if m:
            new('disp', 'sdisp', ctpr_w=int(m.group(1)), text=s)
            continue
        if s.startswith('return'):
            new('ret', 'return', ctpr_w=3, text=s)
            continue
        if s.startswith(('setwd', 'setbn', 'setbp', 'settr', 'vfrpsz')):
            if any(p.name == 'setwd' for p in ops): continue     # one CS1 syllable holds them all
            o = new('misc', 'setwd', text=s)
            o.flags.add('pin0')
            continue
        if s.startswith('wait'):
            o = new('misc', 'wait', text=s)
            o.flags.add('barrier')
            continue
        m = ALU.match(body)
        if not m:
            o = new('misc', s.split()[0], text=s)
            o.flags.add('unknown')
            continue
        name, ch, sm, args = m.group(1), int(m.group(2)), bool(m.group(3)), m.group(4)
        args = re.sub(r',\s*mas\s*=\s*0x[0-9a-f]+', '', args)
        a = split_args(args)
        o = new('alu', name, ch=ch, sm=sm, text=s)
        o.pk, o.use = classify(name)
        if o.pk == 'apb': o.flags.add('apb')
        if name.startswith('qp'): o.flags.add('qp')
        elif name.startswith('p') and name not in ('popcntd', 'popcnts'): o.flags.add('p64')
        if cond_p >= 0: o.pred_reads.append((cond_p, 'rlp'))
        if cond_other: o.flags.add('loopcond')
        # destination
        dst = None
        if o.pk == 'store':
            srcs = a
        elif a:
            dst, srcs = a[-1], a[:-1]
            if dst.lstrip('~').startswith('%pred') and name.startswith('merge'):
                o.pred_reads.append((int(re.sub(r'\D', '', dst)), 'mrg'))
                dst, srcs = srcs[-1], srcs[:-1]
        else:
            srcs = []
        if dst is not None:
            if dst.startswith('%pred'): o.pred_writes.append(int(dst[5:]))
            elif dst.startswith('%ctpr'):
                o.ctpr_w = int(dst[5:]); o.flags.add('movtd')
            else:
                r = reg_of(dst)
                if r: o.writes.append(r)
                elif dst.startswith('%') and not dst.startswith('%empty'):
                    o.writes.append((dst[1:], 64))       # special registers (%lsr, ...)
        for k, t in enumerate(srcs):
            h = lit_halves(t)
            if h:
                o.lit += h
                o.lits.append((t.strip(), h))
            r = reg_of(t)
            if r:
                use = o.use
                if o.pk in ('load', 'store'): use = 'addr'
                if o.pk == 'store' and k == len(srcs) - 1: use = 'st'
                o.reads.append((r[0], r[1], use))
            elif t.startswith('%') and not t.startswith('%empty') and not t.startswith('%pred'):
                o.reads.append((t[1:], 64, 'int'))
        if o.pk in ('load', 'store'):
            addr = srcs[:2] if o.pk == 'load' else srcs[:2]
            regs = [reg_of(x) for x in addr if reg_of(x)]
            lits = [lit_value(x) for x in addr if not reg_of(x)]
            size = MEMSIZE.get(name[2:3], 8) if name[2:3] in MEMSIZE else 8
            if name.startswith(('ldgd', 'stgd', 'ldcs', 'stcs', 'ldds', 'stds', 'ldes', 'stes', 'ldfs', 'stfs', 'ldgs', 'stgs', 'ldss', 'stss')):
                size = 8
            if len(regs) == 1 and len(lits) == 1 and lits[0] is not None:
                o.mem = ('ld' if o.pk == 'load' else 'st', regs[0][0], lits[0], size)
            else:
                o.mem = ('ld' if o.pk == 'load' else 'st', None, None, size)
    # predicate logic of the command: one op per %pred written
    if logic_lines:
        elp = {}        # @pK (0..3) -> (pred, neg)
        clp = {}        # @pK (4..6) -> list of inputs @p
        outs = []
        for s in logic_lines:
            m = re.match(r'^pass\s+(~?)%pred(\d+),\s*@p(\d)', s)
            if m: elp[int(m.group(3))] = int(m.group(2)); continue
            m = re.match(r'^pass\s+@p(\d),\s*%pred(\d+)', s)
            if m: outs.append((int(m.group(1)), int(m.group(2)))); continue
            m = re.match(r'^(landp|andp|movep)\s+(.*)$', s)
            if m:
                ps = [int(x) for x in re.findall(r'@p(\d)', m.group(2))]
                clp[ps[-1]] = ps[:-1]
                continue
            m = re.match(r'^pass\s+(~?)%(pcnt|pred)(\d+)', s)
            if m: c.flags.add('hwloop')

        def leaves(p, seen):
            if p in elp: return {elp[p]}, set()
            if p in clp:
                if p in seen: return set(), set()
                seen = seen | {p}
                ins, cl = set(), {p}
                for q in clp[p]:
                    i2, c2 = leaves(q, seen)
                    ins |= i2; cl |= c2
                return ins, cl
            return set(), set()
        # the whole PLS of the command stays one unit (CLP outputs are shared)
        allin, allcl = set(), set()
        for p, pr in outs:
            ins, cl = leaves(p, frozenset())
            allin |= ins; allcl |= cl
        o = new('logic', 'plogic', text='; '.join(logic_lines))
        o.pred_writes.extend(pr for _, pr in outs)
        for q in sorted(set(elp.values())): o.pred_reads.append((q, 'elp'))
        o.elp, o.clp = len(set(elp.values())), len(clp)
    c.ops = ops
    for o in ops:
        if 'apb' in o.flags: c.flags.add('apb')
        if 'qp' in o.flags: c.flags.add('qp')
        if 'unknown' in o.flags: c.flags.add('unknown')
    if any(o.kind in ('ct', 'call', 'ibranch') for o in ops): c.flags.add('transfer')


def cycles_of(c):
    return 1 + c.nop
