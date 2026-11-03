"""Round 9c: flag the lowerings (user flow). v3 tuning truth only, LOVO preds from abstain.py (r8soft mode a). No exam/gate truth.
  python3 train/lowerflag.py r8soft   (writes data/train/lowerflag-<tag>.json, prints markdown)
Order r<w<x. LOWERING = model<mech, RAISE = model>mech, KEEP = equal. conf = max calibrated p."""
import sys, json
from abstain import *
from fallback import cell

def score(final, asked, pred, truth):
    n = len(truth); ans = ~asked; right = ans & (final == truth); loose = ans & (final < truth); tight = ans & (final > truth)
    assert right.sum() + loose.sum() + tight.sum() + asked.sum() == n == 5716
    a = int(ans.sum()); r, l, t, k = (int(x.sum()) for x in (right, loose, tight, asked)); pc = lambda x, d: round(100 * x / d, 2) if d else None
    return {'right': r, 'rightPct': pc(r, a), 'loose': l, 'loosePct': pc(l, a), 'tight': t, 'tightPct': pc(t, a), 'asked': k, 'askedPct': pc(k, n),
            'askRight': int((asked & (pred == truth)).sum()), 'askLoose': int((asked & (pred < truth)).sum()), 'askTight': int((asked & (pred > truth)).sum())}

def loose_types(final, asked, pred, mech, truth):
    L = ~asked & (final < truth); lowered = L & (final < mech)       # accepted lowering that is still too loose
    mechl = L & (final == mech)                                      # mechanical letter held, too loose, not raised
    return {'loweredWrongly': int(lowered.sum()), 'mechLooseNotRaised': int(mechl.sum()), 'other': int((L & ~lowered & ~mechl).sum())}

def run(tag):
    extend_grids(); va, ev = load_split('val'), load_split('v3eval')
    Pva, Pev = np.load(os.path.join(OUT, f'probs-{tag}-val.npy')).astype(float), np.load(os.path.join(OUT, f'probs-{tag}-v3eval.npy')).astype(float)
    T = temp_fit(Pva, va.y.values); tu = Tuner(ev, temp_apply(Pev, T))
    pa, *_ = lovo_preds(tu); conf = tu.P.max(1); truth = tu.truth; mech = tu.mech; n = len(truth); no = np.zeros(n, bool)
    low, rai, kee = pa < mech, pa > mech, pa == mech
    out = {'T': round(T, 3), 'n': n, 'moves': {}, 'rules': {}}
    for nm, m in (('lowering', low), ('raise', rai), ('keep', kee)):
        out['moves'][nm] = {'n': int(m.sum()), 'right': int((m & (pa == truth)).sum()), 'loose': int((m & (pa < truth)).sum()), 'tight': int((m & (pa > truth)).sum())}
    def add(name, final, asked): out['rules'][name] = {**score(final, asked, pa, truth), 'looseTypes': loose_types(final, asked, pa, mech, truth)}
    add('1 BASE', pa, no)
    c = cell(pa, truth, mech, conf, 0.95, 'MECH-THEN-ASK'); add('2 MECH-THEN-ASK@0.95', c['final'], c['asked_mask'])
    add('3 FLAG-ALL-LOWER', pa, low)
    for t in (0.8, 0.9, 0.95, 0.97, 0.99):
        add(f'4 LOWER-BAR-KEEP@{t}', np.where(low & (conf < t), mech, pa), no)
    for t in (0.8, 0.9, 0.95, 0.97, 0.99): add(f'5 LOWER-BAR-ASK@{t}', pa, low & (conf < t))
    for t in (0.95, 0.99):
        ask = low & (conf < t); nl = ~low & (conf < 0.95); use = nl & (mech >= pa)
        add(f'6 LOWER-BAR-ASK@{t}+MTA@0.95', np.where(use, mech, pa), ask | (nl & ~use))
    return out

def md(o):
    print('moves', o['moves'], '\n| rule | right | too loose | too tight | asked (R/L/T) | loose types |\n|---|---|---|---|---|---|')
    for k, c in o['rules'].items():
        a = o['n'] - c['asked']
        print(f"| {k} | {c['right']} ({c['rightPct']}%) | {c['loose']} ({c['loosePct']}%) | {c['tight']} ({c['tightPct']}%) | {c['asked']} ({c['askedPct']}%; {c['askRight']}/{c['askLoose']}/{c['askTight']}) | {c['looseTypes']} |")

if __name__ == '__main__':
    tag = sys.argv[1]; o = run(tag); json.dump(o, open(os.path.join(OUT, f'lowerflag-{tag}.json'), 'w'), indent=1); md(o)
