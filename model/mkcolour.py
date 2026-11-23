#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""mkcolour.py PFX OUT.pkl [--move L1,L2,...] [--sets 64] [--ways 5] [--bin NAME] [--simdir DIR]: the ITLB colour lever.

The Elbrus-8SV ITLB is 64 sets (VA bits 12..17) x 5 ways (docs/FACTS.md), so a code page's colour is (VA >> 12) & 63
and more than 5 hot pages of one colour thrash.  Code of the layers in --move (default: jit) is shifted as a whole,
one layer after another, by D pages (= choosing its mapping base modulo 256 KB); the rest keeps its addresses.  D is
chosen to minimise the heat of hot pages beyond the `ways` hottest of their colour.  Prints the overflow before/after.
Use with SIM_LAYOUT=OUT.pkl sim.py ..."""
import sys, os, glob, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R


def opt(a, k, d=None):
    if k in a:
        i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
    return d


a = sys.argv[1:]
binname = opt(a, '--bin'); simdir = opt(a, '--simdir')
move = opt(a, '--move', 'jit').split(',')
SETS = int(opt(a, '--sets', 64)); WAYS = int(opt(a, '--ways', 5))
pfx, out = a[0], a[1]
meta = pickle.load(open(pfx + '.dec.pkl', 'rb')); res = R.Resolver(pfx, binname)
ph = collections.defaultdict(collections.Counter)      # group -> page -> heat; group '' = fixed code
for p in glob.glob('%s.w*.sim.pkl' % (os.path.join(simdir, os.path.basename(pfx)) if simdir else pfx)):
    r = pickle.load(open(p, 'rb'))
    for iid, n in r['execs'].items():
        ad = meta['addr'][iid]; L, _ = res.resolve(ad, meta['syms'][iid])
        ph[L if L in move else ''][ad >> 12] += n


def over(groups):
    col = collections.defaultdict(list)
    for pages in groups:
        for pg, h in pages.items(): col[pg % SETS].append(h)
    return sum(sum(sorted(v, reverse=True)[WAYS:]) for v in col.values())


def shifted(c, d): return {pg + d: h for pg, h in c.items()}


tot = sum(sum(c.values()) for c in ph.values()) or 1
placed = [ph['']]
before = over([ph[''] ] + [ph[g] for g in move])
shift = {}
for g in move:
    d = min(range(SETS), key=lambda d: over(placed + [shifted(ph[g], d)]))
    shift[g] = d; placed.append(shifted(ph[g], d))
after = over(placed)
m = {}
for g, d in shift.items():
    for pg in ph[g]:
        for k in range(16): m[(pg << 4) + k] = ((pg + d) << 4) + k + (1 << 36)
pickle.dump(m, open(out, 'wb'))
print('hot pages: fixed %d %s; shifts %s pages; heat beyond %d/colour %.1f%% -> %.1f%%' % (
    len(ph['']), ' '.join('%s %d' % (g, len(ph[g])) for g in move), ' '.join('%s %+d' % kv for kv in shift.items()),
    WAYS, 100 * before / tot, 100 * after / tot))
