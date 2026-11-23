#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""apps.py [--top N] [--bin NAME] PFX [BASE_PFX...]

Whole-run summary from sampled windows (the token-cheap readout: where / what / why).
The model's cycles per wide instruction over the counted instructions of all windows of PFX (PFX.w*.sim.pkl),
times the run's total wide instructions (qemu count, PFX.info "total_insns"), gives G cycles of the whole run;
every symbol's and layer's cycles are scaled by the same factor (total instructions / counted instructions).
With BASE_PFX runs (another build, input or model variant): per layer and symbol the change in G cycles.
--main: scale by the main thread's instructions (vcpu0) instead of all threads.
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R

CAUSES = R.CAUSES


def total_insns(pfx, main_only=False):
    for l in open(pfx + '.info'):
        if l.startswith('total_insns'):
            f = l.split()
            return int(f[3]) if main_only else int(f[1])
    return None


def run_figs(pfx, binname=None, main_only=False):
    by, ins, n = R.aggregate(pfx, binname)
    tot = total_insns(pfx, main_only)
    k = tot / max(n, 1)
    cyc = sum(sum(v) for v in by.values()) * k
    lay = collections.defaultdict(lambda: [0.0] * len(CAUSES))
    sym = {}
    for (l, name), v in by.items():
        for c in range(len(CAUSES)):
            lay[l][c] += v[c] * k
        sym[(l, name)] = [x * k for x in v]
    return dict(cyc=cyc, insns=tot, counted=n, lay=lay, sym=sym)


def top_causes(v, nn=3):
    s = sum(v)
    st = sorted(((v[c], CAUSES[c]) for c in range(1, len(CAUSES)) if v[c]), reverse=True)[:nn]
    return ' '.join('%s:%.0f' % (n, 100 * x / s) for x, n in st)


def main():
    a = sys.argv[1:]
    top = 10
    binname = None
    main_only = False
    if '--top' in a:
        i = a.index('--top'); top = int(a[i + 1]); del a[i:i + 2]
    if '--bin' in a:
        i = a.index('--bin'); binname = a[i + 1]; del a[i:i + 2]
    if '--main' in a:
        a.remove('--main'); main_only = True
    if not a:
        print(__doc__); sys.exit(1)
    pfx, bases = a[0], a[1:]
    f = run_figs(pfx, binname, main_only)
    B = [(b, run_figs(b, binname, main_only)) for b in bases]
    nm = os.path.basename
    print('%s: %.3f G wide insns, %.3f G cycles (model), IPC %.3f, windows cover %.2f %% of the run' % (
        nm(pfx), f['insns'] / 1e9, f['cyc'] / 1e9, f['insns'] / f['cyc'], 100.0 * f['counted'] / f['insns']))
    for b, g in B:
        print('  vs %s: %.3f G cycles (%+.1f %%)' % (nm(b), g['cyc'] / 1e9, 100 * (f['cyc'] / g['cyc'] - 1)))
    print('\nWHERE: layers (G cycles, %% of run, issue share, top stall causes as %% of the layer)%s' %
          ''.join('   d.vs %s' % nm(b) for b, _ in B))
    for l, v in sorted(f['lay'].items(), key=lambda kv: -sum(kv[1])):
        s = sum(v)
        dd = ''.join('   %+8.3f' % ((s - sum(g['lay'].get(l, [0]))) / 1e9) for b, g in B)
        print('  %-10s %8.3f %5.1f%%  issue %3.0f%%  %-30s%s' % (l, s / 1e9, 100 * s / f['cyc'], 100 * v[0] / s, top_causes(v), dd))
    tot = [sum(v[c] for v in f['lay'].values()) for c in range(len(CAUSES))]
    print('\nWHAT: cycles by cause (% of run)')
    print('  ' + '  '.join('%s %.1f' % (CAUSES[c], 100 * tot[c] / f['cyc']) for c in range(len(CAUSES)) if tot[c] / f['cyc'] > 0.001))
    print('\nWHY: top %d symbols (G cycles, %% of run, stall causes as %% of the symbol, dominant reason)' % top)
    print('  %-10s %8s %5s  %-26s %-8s %s' % ('layer', 'G cyc', '%', 'stalls', 'why', 'symbol' + ''.join('   d.' + nm(b) for b, _ in B)))
    for (l, name), v in sorted(f['sym'].items(), key=lambda kv: -sum(kv[1]))[:top]:
        s = sum(v)
        dd = ''.join('   %+.4f' % ((s - sum(g['sym'].get((l, name), [0]))) / 1e9) for b, g in B)
        print('  %-10s %8.4f %5.1f  %-26s %-8s %s%s' % (l, s / 1e9, 100 * s / f['cyc'], top_causes(v), R.why_of(v), name[:50], dd))
    for b, g in B:
        print('\nCHANGE vs %s: biggest symbol changes (G cycles)' % nm(b))
        ch = collections.Counter()
        for k in set(f['sym']) | set(g['sym']):
            ch[k] += (sum(f['sym'].get(k, [0])) - sum(g['sym'].get(k, [0]))) / 1e9
        for k, v in sorted(ch.items(), key=lambda kv: -abs(kv[1]))[:top]:
            print('  %+9.4f  %-10s %s' % (v, k[0], k[1][:70]))


if __name__ == '__main__':
    main()
