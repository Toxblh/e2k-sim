#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""decode.py PFX [--jobs N]: PFX.code (id vaddr size hex sym) -> PFX.dec.pkl (per-id static info for sim.py).

Each run of contiguous wide instructions is disassembled by an e2k objdump at its own address, then parsed by
e2kdis.py into ops with read/write sets, latency classes, memory ops and control transfer.

Environment:
  E2K_ROOT     e2k sysroot that holds usr/bin/objdump (e2k binutils); default ~/e2k-root
  E2K_OBJDUMP  objdump binary (default $E2K_ROOT/usr/bin/objdump)
  E2K_QEMU     qemu-e2k used to run that objdump on a non-e2k host (default: qemu-e2k in PATH);
               set E2K_QEMU= (empty) on an e2k host to run objdump natively
  SIM_DECCACHE decode cache directory, shared by runs: (vaddr, bytes) -> description (default ~/.cache/e2k-sim/deccache)
"""
import os, re, sys, glob, pickle, subprocess, tempfile, collections, shutil
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2kdis as D

ROOT = os.path.expanduser(os.environ.get('E2K_ROOT', '~/e2k-root'))
OBJDUMP = os.environ.get('E2K_OBJDUMP', ROOT + '/usr/bin/objdump')
QEMU = os.environ.get('E2K_QEMU', shutil.which('qemu-e2k') or 'qemu-e2k')
CACHE = os.path.expanduser(os.environ.get('SIM_DECCACHE', '~/.cache/e2k-sim/deccache'))


def load_code(pfx):
    ins = {}
    for l in open(pfx + '.code'):
        f = l.split()
        if len(f) < 4: continue
        ins[int(f[0])] = (int(f[1], 16), int(f[2]), bytes.fromhex(f[3]), f[4] if len(f) > 4 else '-')
    return ins


def runs_of(ins):
    """Group ids into runs of contiguous code; a vaddr seen with several byte versions goes to separate runs."""
    byaddr = collections.defaultdict(list)
    for i, (va, sz, b, s) in ins.items():
        byaddr[va].append(i)
    gens = collections.defaultdict(list)       # generation -> sorted (va, id)
    for va, ids in byaddr.items():
        for g, i in enumerate(sorted(ids)):
            gens[g].append((va, i))
    runs = []
    for g, lst in gens.items():
        lst.sort()
        cur = []
        for va, i in lst:
            if cur and (cur[-1][0] + ins[cur[-1][1]][1] != va or len(cur) >= 4000):
                runs.append(cur); cur = []
            cur.append((va, i))
        if cur: runs.append(cur)
    return runs


def dis_run(args):
    run, blobs = args
    va0 = run[0][0]
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        f.write(b''.join(blobs)); fn = f.name
    try:
        cmd = [OBJDUMP, '-D', '-b', 'binary', '-m', 'elbrus-v5:64', '--adjust-vma=0x%x' % va0, fn]
        if QEMU: cmd = [QEMU, '-L', ROOT] + cmd
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
    finally:
        os.unlink(fn)
    cmds = D.parse_listing(out)
    res = {}
    byva = {c.addr: c for c in cmds}
    for va, i in run:
        c = byva.get(va)
        res[i] = static_of(c) if c is not None else None
    return res


def regkey(name):
    """'r3' -> ('r', 3); 'b5' -> ('b', 5); 'g16' -> ('g', 16); specials -> ('s', name)."""
    if name[0] in 'rbg' and name[1:].isdigit():
        return (name[0], int(name[1:]))
    return ('s', name)


def static_of(c):
    """Compact static description of one wide command."""
    ops = []
    loads, stores = [], []
    ctl = None            # ('ct'|'call', ctpr, cond) or ('ibranch', None, cond)
    preps = []            # (ctpr, kind) kind: disp|movtd|ret
    nops = 0
    for o in c.ops:
        if o.kind in ('ct', 'call'):
            ctl = (o.kind, o.ctpr_r, o.cond, [(p, h) for p, h in o.pred_reads])
            continue
        if o.kind == 'ibranch':
            ctl = ('ibranch', -1, o.cond, [(p, h) for p, h in o.pred_reads])
            continue
        if o.kind == 'disp':
            preps.append((o.ctpr_w, 'disp')); continue
        if o.kind == 'ret':
            preps.append((3, 'ret')); continue
        if o.kind == 'misc':
            continue
        if o.kind == 'logic':
            ops.append(dict(k='logic', ch=-1, pk='logic', reads=[], writes=[], pr=[(p, h) for p, h in o.pred_reads],
                            pw=list(o.pred_writes), name='plogic'))
            continue
        if 'movtd' in o.flags:
            preps.append((o.ctpr_w, 'movtd'))
        d = dict(k='alu', ch=o.ch, pk=o.pk, name=o.name, sm=o.sm,
                 reads=[(regkey(r), w, u) for r, w, u in o.reads],
                 writes=[(regkey(r), w) for r, w in o.writes],
                 pr=[(p, h) for p, h in o.pred_reads], pw=list(o.pred_writes),
                 apb='apb' in o.flags)
        if o.pk == 'load' or (o.pk == 'apb' and o.name.startswith(('ldaa', 'mova'))):
            d['mem'] = 'ld'
            loads.append(len(ops))
        elif o.pk == 'store' or (o.pk == 'apb' and o.name.startswith('staa')):
            d['mem'] = 'st'
            stores.append(len(ops))
        ops.append(d)
    wsz = setbn = None; rot = False
    for l in c.lines:
        m = re.search(r'setwd wsz = 0x([0-9a-f]+)', l)
        if m: wsz = int(m.group(1), 16)
        m = re.search(r'setbn rbs = 0x([0-9a-f]+), rsz = 0x([0-9a-f]+), rcur = 0x([0-9a-f]+)', l)
        if m: setbn = tuple(int(x, 16) for x in m.groups())
        if l.startswith('abn') and 'abnf=1' in l or l.startswith('abn') and 'abnt=1' in l: rot = True
    return dict(addr=c.addr, size=c.size, nop=c.nop, ops=ops, loads=loads, stores=stores, ctl=ctl, preps=preps,
                hwloop='hwloop' in c.flags, nalu=sum(1 for o in ops if o['k'] == 'alu'), wsz=wsz, setbn=setbn, rot=rot)


def main():
    pfx = sys.argv[1]
    jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else (os.cpu_count() or 4)
    ins = load_code(pfx)
    # decode cache shared by runs: (vaddr, bytes) -> static description (CACHE/*.pkl, one file per run)
    cdir = CACHE; os.makedirs(cdir, exist_ok=True)
    cache = {}
    for f in glob.glob(cdir + '/*.pkl'):
        try: cache.update(pickle.load(open(f, 'rb')))
        except Exception: pass
    pre = {}
    for i, (va, sz, b, s) in list(ins.items()):
        k = (va, b[:sz])
        if k in cache: pre[i] = cache[k]
    todo = {i: v for i, v in ins.items() if i not in pre}
    runs = runs_of(todo)
    work = [(r, [ins[i][2][:ins[i][1]] for va, i in r]) for r in runs]
    work.sort(key=lambda w: -len(w[0]))
    dec = {}
    with ProcessPoolExecutor(jobs) as ex:
        for res in ex.map(dis_run, work, chunksize=1):
            dec.update(res)
    newc = {(ins[i][0], ins[i][2][:ins[i][1]]): v for i, v in dec.items() if v is not None}
    pickle.dump(newc, open('%s/%s.pkl' % (cdir, os.path.basename(pfx) + '-%d' % os.getpid()), 'wb'))
    dec.update(pre)
    syms = {i: ins[i][3] for i in ins}
    bad = sum(1 for v in dec.values() if v is None)
    pickle.dump(dict(dec=dec, syms=syms, addr={i: ins[i][0] for i in ins}), open(pfx + '.dec.pkl', 'wb'))
    print('ids %d runs %d undecoded %d cached %d' % (len(ins), len(runs), bad, len(pre)))


if __name__ == '__main__':
    main()
