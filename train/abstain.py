"""Round 8: confidence / abstain evaluation (the bareguard "ask" evidence). Honest LOVO, same cuts/margins as tune_cuts.py.
  python3 train/abstain.py r6full r8soft       (writes data/train/abstain-<tag>.json, prints markdown tables)
Confidence = max of the temperature-calibrated p (T fit on val). Rows with confidence < threshold abstain ("ask"); the rest are answered.
Mode (b): guarded argmax with the per-fold LOVO margin. Mode (a): mechanical + one-step tier moves at the per-fold LOVO own cuts.
Band variant (mode a): abstain when the row's tier-relevant p (lower/raise-wx: p(x); raise-get: p(w)+p(x)) is within +-0.1 of its cut;
'moved' = only rows the cuts move (spec), 'any' = any in-tier row near the cut."""
import sys, json
from tune_cuts import *
THR = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]

def lovo_preds(tu):
    """per-row LOVO predictions (int 0..2) for mode (a) and (b), plus the row's tier p / cut / moved flag for mode (a)."""
    n = len(tu.truth); pa = np.zeros(n, int); pb = np.zeros(n, int); tp = np.full(n, np.nan); cut = np.full(n, np.nan); moved = np.zeros(n, bool)
    mech = tu.mech; T = tu.tier; px, ch = tu.px, tu.ch
    pre = [guarded(tu.P, m) for m in M_GRID]; tabs = np.array([tally(p, tu.truth, tu.vidx, tu.nv) for p in pre])
    for v in range(tu.nv):
        vs = [x for x in range(tu.nv) if x != v]; rows = tu.vidx == v
        c, _, _ = tu.pick(vs); k = tu.cuts(c); mechL = tu.mechT[vs, 2].sum()
        pred = mech.copy()
        low = (T == 'lower') & (mech == 2) & (px < k['lower']); pred = np.where(low, np.where(tu.post & (ch < k['rcut']), 0, 1), pred)
        wx = (T == 'raise-wx') & (mech == 1) & (px >= k['raise-wx']); pred = np.where(wx, 2, pred)
        gt = (T == 'raise-get') & (mech == 0) & (ch >= k['raise-get']); pred = np.where(gt, 1, pred)
        pred = tu.apply_cred(pred); pa[rows] = pred[rows]
        moved[rows] = (pred != mech)[rows]
        for t, p, cu in (('lower', px, k['lower']), ('raise-wx', px, k['raise-wx']), ('raise-get', ch, k['raise-get'])):
            m = rows & (T == t); tp[m] = p[m]; cut[m] = cu
        ok = [(tabs[j][vs, 1].sum(), -tabs[j][vs, 2].sum(), j) for j in range(len(M_GRID)) if tabs[j][vs, 2].sum() <= mechL]
        j = max(ok)[2]; pb[rows] = pre[j][rows]
    return pa, pb, tp, cut, moved

def row(pred, truth, ans):
    n = len(truth); a = ans.sum()
    if a == 0: return {'cover': 0.0, 'exact': None, 'loose': 0, 'tight': 0, 'abst': int(n), 'abstLoose': int((pred < truth).sum())}
    p, t = pred[ans], truth[ans]
    return {'cover': round(100 * a / n, 1), 'exact': round(100 * (p == t).mean(), 1), 'loose': int((p < t).sum()), 'tight': int((p > t).sum()), 'abst': int(n - a),
            'abstLoose': int((pred[~ans] < truth[~ans]).sum())}

def run(tag):
    extend_grids()
    va, ev = load_split('val'), load_split('v3eval')
    Pva, Pev = np.load(os.path.join(OUT, f'probs-{tag}-val.npy')).astype(float), np.load(os.path.join(OUT, f'probs-{tag}-v3eval.npy')).astype(float)
    T = temp_fit(Pva, va.y.values); tu = Tuner(ev, temp_apply(Pev, T))
    pa, pb, tp, cut, moved = lovo_preds(tu); conf = tu.P.max(1); truth = tu.truth
    out = {'T': round(T, 3), 'n': len(truth), 'mechLoose': int((tu.mech < truth).sum()), 'none': {'a': row(pa, truth, np.ones(len(truth), bool)), 'b': row(pb, truth, np.ones(len(truth), bool))}, 'a': {}, 'b': {}}
    for t in THR:
        ans = conf >= t; out['a'][str(t)] = row(pa, truth, ans); out['b'][str(t)] = row(pb, truth, ans)
    near = np.abs(tp - cut) <= 0.1
    out['band_moved'] = row(pa, truth, ~(moved & near)); out["band_any"] = row(pa, truth, ~near)
    return out

def md(tag, o):
    print(f'\n### {tag}  (T={o["T"]}, n={o["n"]}, mechanical too-loose {o["mechLoose"]})')
    for m, nm in (('b', 'mode (b) guarded argmax'), ('a', 'mode (a) own cuts')):
        print(f'\n{nm}, abstain if max calibrated p < threshold\n| thr | answered % | exact % (answered) | too-loose rows | too-tight rows | abstained rows (of which would be too-loose) |\n|---|---|---|---|---|---|')
        r = o['none'][m]; print(f'| none | {r["cover"]} | {r["exact"]} | {r["loose"]} | {r["tight"]} | 0 |')
        for t in THR:
            r = o[m][str(t)]; print(f'| {t} | {r["cover"]} | {r["exact"]} | {r["loose"]} | {r["tight"]} | {r["abst"]} ({r["abstLoose"]}) |')
    for k, nm in (('band_moved', 'mode (a), abstain when moved and p within +-0.1 of cut'), ('band_any', 'mode (a), abstain when any in-tier p within +-0.1 of cut')):
        r = o[k]; print(f'\n{nm}: answered {r["cover"]}%, exact {r["exact"]}, too-loose {r["loose"]}, too-tight {r["tight"]}, abstained {r["abst"]} ({r["abstLoose"]} would be too-loose)')

if __name__ == '__main__':
    for tag in sys.argv[1:]:
        o = run(tag); json.dump(o, open(os.path.join(OUT, f'abstain-{tag}.json'), 'w'), indent=1); md(tag, o)
