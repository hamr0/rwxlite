"""Round 9b: unsure -> mechanical letter. Reuses abstain.py's honest LOVO preds (v3 tuning truth only; no exam, no gate truth).
  python3 train/fallback.py r8soft     (writes data/train/fallback-<tag>.json, prints markdown)
Rules for rows below the bar (conf = max calibrated p): ASK -> ask; MECH -> mechanical letter; MECH-THEN-ASK -> mechanical letter if
mech >= model letter (r<w<x, mech at least as strict), else ask. Every row lands in exactly one of right / loose / tight / asked."""
import sys, json
from abstain import *
THRS = [None] + THR

def cell(pred, truth, mech, conf, thr, rule):
    n = len(truth); below = np.zeros(n, bool) if thr is None else conf < thr
    final = pred.copy(); asked = np.zeros(n, bool)
    if rule == 'MECH': final = np.where(below, mech, pred)
    elif rule == 'ASK': asked = below
    else:
        use = below & (mech >= pred); final = np.where(use, mech, pred); asked = below & ~use
    ans = ~asked; right = ans & (final == truth); loose = ans & (final < truth); tight = ans & (final > truth)
    assert right.sum() + loose.sum() + tight.sum() + asked.sum() == n == 5716 and not (right & loose).any()
    a = int(ans.sum()); r, l, t, k = (int(x.sum()) for x in (right, loose, tight, asked))
    pc = lambda x, d: round(100 * x / d, 2) if d else None
    return {'answered': a, 'answeredPct': pc(a, n), 'asked': k, 'askedPct': pc(k, n), 'right': r, 'rightPct': pc(r, a), 'loose': l, 'loosePct': pc(l, a),
            'tight': t, 'tightPct': pc(t, a), 'rightPctAll': pc(r, n), 'loosePctAll': pc(l, n), 'tightPctAll': pc(t, n),
            'askWouldBeRight': int((asked & (pred == truth)).sum()), 'askWouldBeLoose': int((asked & (pred < truth)).sum()),
            'askWouldBeTight': int((asked & (pred > truth)).sum()), 'final': final, 'asked_mask': asked}

def run(tag):
    extend_grids()
    va, ev = load_split('val'), load_split('v3eval')
    Pva, Pev = np.load(os.path.join(OUT, f'probs-{tag}-val.npy')).astype(float), np.load(os.path.join(OUT, f'probs-{tag}-v3eval.npy')).astype(float)
    T = temp_fit(Pva, va.y.values); tu = Tuner(ev, temp_apply(Pev, T))
    pa, pb, *_ = lovo_preds(tu); conf = tu.P.max(1); truth = tu.truth; mech = tu.mech; tiers = tu.tier
    out = {'T': round(T, 3), 'n': len(truth), 'mechanical': {k: v for k, v in cell(mech, truth, mech, conf, None, 'ASK').items() if k not in ('final', 'asked_mask')}, 'a': {}, 'b': {}, 'tier': {}}
    for mode, pred in (('a', pa), ('b', pb)):
        for rule in ('ASK', 'MECH', 'MECH-THEN-ASK'):
            for t in THRS:
                c = cell(pred, truth, mech, conf, t, rule); key = 'none' if t is None else str(t)
                if rule != 'ASK' and t in (0.9, 0.95):
                    fin, ask = c['final'], c['asked_mask']; d = {}
                    for tn in sorted(set(tiers)):
                        m = tiers == tn; d[tn] = {'n': int(m.sum()), 'loose': int((~ask & m & (fin < truth)).sum()), 'asked': int((ask & m).sum())}
                    out['tier'][f'{mode}|{rule}|{key}'] = d
                out[mode].setdefault(rule, {})[key] = {k: v for k, v in c.items() if k not in ('final', 'asked_mask')}
    return out

def md(o):
    for mode, nm in (('a', 'mode (a) mechanical + cuts'), ('b', 'mode (b) guarded standalone')):
        print(f'\n{nm}\n| rule | bar | answered | asked (right/loose/tight if answered) | right | too loose | too tight |\n|---|---|---|---|---|---|---|')
        for rule in ('ASK', 'MECH', 'MECH-THEN-ASK'):
            for k, c in o[mode][rule].items():
                if rule != 'ASK' and k == 'none': continue
                print(f"| {rule} | {k} | {c['answered']} ({c['answeredPct']}%) | {c['asked']} ({c['askedPct']}%; {c['askWouldBeRight']}/{c['askWouldBeLoose']}/{c['askWouldBeTight']}) | {c['right']} ({c['rightPct']}%) | {c['loose']} ({c['loosePct']}%) | {c['tight']} ({c['tightPct']}%) |")
    print('\ntier too-loose'); [print(k, v) for k, v in o['tier'].items()]

if __name__ == '__main__':
    tag = sys.argv[1]; o = run(tag); json.dump(o, open(os.path.join(OUT, f'fallback-{tag}.json'), 'w'), indent=1); md(o)
