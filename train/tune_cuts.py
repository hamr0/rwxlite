"""Tune the TF-IDF baseline's OWN cuts for mode (a) and a guarded argmax for mode (b), leave-one-vendor-out
on the v3 tuning truth under the PRD global-budget rule (max exact s.t. TOTAL too-loose <= mechanical's).
Honest LOVO: for each held-out vendor the cuts are picked on the other vendors only.
Calibration (temperature) is fit on the val split (round-6 targets), never on v3.
Run: python3 train/tune_cuts.py            (cuts + calibration + latency breakdown; writes data/train/tune-cuts-results.json)
     python3 train/tune_cuts.py --lighter  (also fit lighter vectoriser variants; slow, n_jobs=2)
     python3 train/tune_cuts.py --tag r6full  (same procedure on a fine-tuned model's saved probs: data/train/probs-<tag>-{val,v3eval}.npy;
                                               writes tune-cuts-<tag>-results.json; no latency/baseline pickle)"""
import sys, os, json, time, pickle
import numpy as np, scipy.sparse as sp
from scipy.optimize import minimize_scalar
from common import *

A_GRID = [0, 0.02, 0.03, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]   # lower: isX=p(x) < cut
RC_GRID = [0, 0.02, 0.03, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8]       # POST r cut on changes
B_GRID = [0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 1.01]   # raise-wx: p(x) >= cut
C_GRID = [0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 1.01]   # raise-get: changes >= cut
M_GRID = [0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]                 # mode (b) guard margin
ORD = np.array([0, 1, 2])

def tally(pred, truth, vidx, nv):
    """per-vendor (n, exact, loose) as an array (nv, 3)"""
    e = np.bincount(vidx, weights=(pred == truth), minlength=nv)
    l = np.bincount(vidx, weights=(pred < truth), minlength=nv)
    n = np.bincount(vidx, minlength=nv)
    return np.stack([n, e, l], 1)

def temp_fit(Pva, y):
    L = np.log(np.clip(Pva, 1e-12, 1))
    def nll(T):
        z = L / T; z -= z.max(1, keepdims=True); lp = z - np.log(np.exp(z).sum(1, keepdims=True))
        return -lp[np.arange(len(y)), y].mean()
    return minimize_scalar(nll, bounds=(0.3, 5), method='bounded').x

def temp_apply(P, T):
    z = np.log(np.clip(P, 1e-12, 1)) / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)

def guarded(P, m):
    """mode (b): argmax, but a lower class must beat the best higher class by margin > m, else step up."""
    pred = P.argmax(1).copy()
    for _ in range(2):
        for i in range(len(pred)):
            k = pred[i]
            if k < 2:
                j = k + 1 + P[i, k + 1:].argmax()
                if P[i, k] - P[i, j] <= m: pred[i] = j
    return pred

class Tuner:
    def __init__(self, df, P):
        self.df, self.P = df, P
        self.truth = np.array([ORDER[x] for x in df.truth.values])
        self.mech = np.array([ORDER[x] for x in df.mech.values])
        self.vendors = sorted(df.vendor.unique()); self.vidx = np.array([self.vendors.index(v) for v in df.vendor.values]); self.nv = len(self.vendors)
        self.tier = df.tier.values; self.isdel = (df.method == 'DELETE').values
        cred = np.array([cred_hit(r) for r in df[['method', 'operationId', 'summary', 'path']].to_dict('records')])
        self.cred = cred
        px, pw = P[:, 2], P[:, 1]; self.px, self.ch = px, pw + px
        self.post = (df.method == 'POST').values
        self.tab()
    def apply_cred(self, pred): return np.where(self.cred, 2, pred)
    def tab(self):
        df, T, mech = self.df, self.tier, self.mech
        sel = lambda t: T == t
        self.mask = {t: sel(t) for t in ['lower', 'raise-wx', 'raise-get']}
        self.mask['none'] = sel('none')
        def tl(pred, m): return tally(self.apply_cred(pred)[m], self.truth[m], self.vidx[m], self.nv)
        m = self.mask['lower']; base = mech
        self.low = np.zeros((len(A_GRID), len(RC_GRID), self.nv, 3))
        for i, a in enumerate(A_GRID):
            for j, rc in enumerate(RC_GRID):
                pred = np.where(m & (mech == 2) & (self.px < a), np.where(self.post & (self.ch < rc), 0, 1), mech)
                self.low[i, j] = tl(pred, m)
        m = self.mask['raise-wx']
        self.wx = np.array([tl(np.where((mech == 1) & (self.px >= b), 2, mech), m) for b in B_GRID])
        m = self.mask['raise-get']
        self.get = np.array([tl(np.where((mech == 0) & (self.ch >= c), 1, mech), m) for c in C_GRID])
        self.fixD = tl(mech, self.mask['none'] & self.isdel); self.fixO = tl(mech, self.mask['none'] & ~self.isdel)
        self.mechT = tally(mech, self.truth, self.vidx, self.nv)
    def pick(self, vs):
        mechL = self.mechT[vs, 2].sum(); fix = self.fixD[vs].sum(0) + self.fixO[vs].sum(0)
        lo = self.low[:, :, vs].sum(2); wx = self.wx[:, vs].sum(1); gt = self.get[:, vs].sum(1)
        # total over grid: exact and loose
        E = lo[:, :, None, None, 1] + wx[None, None, :, None, 1] + gt[None, None, None, :, 1] + fix[1]
        L = lo[:, :, None, None, 2] + wx[None, None, :, None, 2] + gt[None, None, None, :, 2] + fix[2]
        E = np.where(L <= mechL, E, -1)
        best = E.max()
        cand = np.argwhere(E == best); Ls = [L[tuple(c)] for c in cand]; c = cand[int(np.argmin(Ls))]   # tie: lowest too-loose
        return tuple(c), best, L[tuple(c)]
    def cuts(self, c): return {'lower': A_GRID[c[0]], 'rcut': RC_GRID[c[1]], 'raise-wx': B_GRID[c[2]], 'raise-get': C_GRID[c[3]]}
    def lovo_a(self):
        parts = {k: np.zeros(3) for k in ['lower', 'raise-wx', 'raise-get', 'none-DELETE', 'none-other']}; chosen = []
        for v in range(self.nv):
            vs = [x for x in range(self.nv) if x != v]; c, _, _ = self.pick(vs); chosen.append(self.cuts(c))
            parts['lower'] += self.low[c[0], c[1], v]; parts['raise-wx'] += self.wx[c[2], v]; parts['raise-get'] += self.get[c[3], v]
            parts['none-DELETE'] += self.fixD[v]; parts['none-other'] += self.fixO[v]
        return parts, chosen
    def all_data_a(self):
        c, E, L = self.pick(list(range(self.nv))); return self.cuts(c), c
    # ---- mode (b)
    def lovo_b(self, gridP=None):
        P = self.P; pre = [guarded(P, m) for m in M_GRID]
        tabs = np.array([tally(p, self.truth, self.vidx, self.nv) for p in pre])  # (M, nv, 3)
        isdel = self.isdel; byd = np.array([[tally(p[sel], self.truth[sel], self.vidx[sel], self.nv) for sel in (isdel, ~isdel)] for p in pre])
        tiers = {t: np.array([tally(p[self.mask[t]], self.truth[self.mask[t]], self.vidx[self.mask[t]], self.nv) for p in pre]) for t in self.mask}
        tot = np.zeros(3); dl = np.zeros((2, 3)); tt = {t: np.zeros(3) for t in tiers}; chosen = []
        for v in range(self.nv):
            vs = [x for x in range(self.nv) if x != v]; mechL = self.mechT[vs, 2].sum()
            ok = [(tabs[k][vs, 1].sum(), -tabs[k][vs, 2].sum(), k) for k in range(len(M_GRID)) if tabs[k][vs, 2].sum() <= mechL]
            k = max(ok)[2]; chosen.append(M_GRID[k]); tot += tabs[k][v]; dl += byd[k][:, v]
            for t in tt: tt[t] += tiers[t][k][v]
        return tot, dl, tt, chosen, pre, tabs

def fin(a):
    n, e, l = (float(x) for x in a); return {'n': int(n), 'exact': round(100*e/n, 1), 'loose': round(100*l/n, 1), 'looseRows': int(round(l)), 'tight': round(100*(n-e-l)/n, 1)} if n else {'n': 0}

def report(name, tu):
    parts, chosen = tu.lovo_a()
    tot = sum(parts.values()); nd = parts['lower'] + parts['raise-wx'] + parts['raise-get'] + parts['none-other']
    rng = {k: [min(c[k] for c in chosen), max(c[k] for c in chosen)] for k in chosen[0]}
    med = {k: float(np.median([c[k] for c in chosen])) for k in chosen[0]}
    allc, _ = tu.all_data_a()
    out = {'overall': fin(tot), 'DELETE': fin(parts['none-DELETE']), 'nonDELETE': fin(nd), 'tiers': {k: fin(v) for k, v in parts.items()}, 'cutRange': rng, 'medianCuts': med, 'cutsOnAllData': allc, 'perFold': chosen}
    tot_b, dl, tt, chosen_b, pre, tabs = tu.lovo_b()
    ndel_b = dl[1]
    outb = {'overall': fin(tot_b), 'DELETE': fin(dl[0]), 'nonDELETE': fin(dl[1]), 'tiers': {t: fin(v) for t, v in tt.items()}, 'marginRange': [min(chosen_b), max(chosen_b)], 'marginPerFold': chosen_b,
            'marginSweepAllData': {str(m): fin(tabs[k].sum(0)) for k, m in enumerate(M_GRID)}}
    plain = guarded(tu.P, -1); outb['unguardedArgmax_inSample'] = fin(tally(plain, tu.truth, tu.vidx, tu.nv).sum(0))
    return {'mode_a': out, 'mode_b_guarded': outb}

def show(name, r):
    a, b = r['mode_a'], r['mode_b_guarded']
    f = lambda d: f"{d['exact']} / {d['loose']} / {d['tight']} (loose rows {d['looseRows']})"
    print(f'=== {name}')
    print(f" mode (a) LOVO  all {f(a['overall'])}  nonDEL {f(a['nonDELETE'])}  DEL {f(a['DELETE'])}")
    for k, v in a['tiers'].items(): print(f"   {k:12s} n={v['n']:5d} {f(v)}")
    print(f"   cut ranges {a['cutRange']}\n   median {a['medianCuts']}\n   on all data {a['cutsOnAllData']}")
    print(f" mode (b) guarded LOVO all {f(b['overall'])}  nonDEL {f(b['nonDELETE'])}  DEL {f(b['DELETE'])}  margin range {b['marginRange']}")
    for k, v in b['tiers'].items(): print(f"   {k:12s} n={v['n']:5d} {f(v)}")
    print('   unguarded argmax (+mech not used):', f(b['unguardedArgmax_inSample']))

def latency(wv, cv, clf, texts):
    def tm(f):
        t = time.perf_counter()
        for s in texts: f(s)
        return round((time.perf_counter() - t) / len(texts) * 1000, 2)
    feat = lambda s: sp.hstack([wv.transform(s), cv.transform(s)]).tocsr()
    W = clf.coef_.T.copy(); b = clf.intercept_
    def fast(s):
        z = feat([s]) @ W + b; z = np.exp(z - z.max()); return z / z.sum()
    x0 = feat([texts[0]])
    return {'word_vectoriser_ms': tm(lambda s: wv.transform([s])), 'char_vectoriser_ms': tm(lambda s: cv.transform([s])), 'sklearn_predict_proba_ms': tm(lambda s: clf.predict_proba(x0)),
            'full_sklearn_ms': tm(lambda s: clf.predict_proba(feat([s]))), 'full_fast_matvec_ms': tm(fast)}

def lighter(tr, va, ev, tu_base):
    """Lighter vectoriser setups: fit on train, report val acc, v3 mode (a) LOVO, single-op latency."""
    from sklearn.feature_extraction.text import TfidfVectorizer, HashingVectorizer, TfidfTransformer
    from sklearn.linear_model import LogisticRegression
    tp = r'[A-Za-z0-9_]+'
    cfgs = {
        'word12+char35_cap100k': lambda: (TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=100000, sublinear_tf=True, token_pattern=tp), TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), min_df=3, max_features=100000, sublinear_tf=True)),
        'word12+char34_cap50k': lambda: (TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000, sublinear_tf=True, token_pattern=tp), TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 4), min_df=3, max_features=50000, sublinear_tf=True)),
        'word12_only_cap100k': lambda: (TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=100000, sublinear_tf=True, token_pattern=tp), None),
    }
    res = {}
    for name, mk in cfgs.items():
        wv, cv = mk(); t0 = time.time()
        Xs = [wv.fit_transform(tr.text)] + ([cv.fit_transform(tr.text)] if cv is not None else [])
        feat = (lambda s: sp.hstack([wv.transform(s), cv.transform(s)]).tocsr()) if cv is not None else (lambda s: wv.transform(s))
        clf = LogisticRegression(C=10, max_iter=300, n_jobs=2).fit(sp.hstack(Xs).tocsr(), tr.y.values)
        Pva, Pev = clf.predict_proba(feat(va.text)), clf.predict_proba(feat(ev.text))
        acc = (Pva.argmax(1) == va.y.values).mean()
        class W_: pass
        r = report(name, Tuner(ev, Pev))
        Wm = clf.coef_.T.copy(); b = clf.intercept_
        texts = list(ev.text.values[:300]); t = time.perf_counter()
        for s in texts:
            z = feat([s]) @ Wm + b
        ms = (time.perf_counter() - t) / len(texts) * 1000
        res[name] = {'val_acc': round(acc*100, 2), 'fit_s': round(time.time()-t0), 'features': int(Wm.shape[0]), 'single_op_fast_ms': round(ms, 2), 'a_overall': r['mode_a']['overall'], 'a_nonDELETE': r['mode_a']['nonDELETE'], 'b_overall': r['mode_b_guarded']['overall']}
        print(name, json.dumps(res[name]), flush=True)
    return res

if __name__ == '__main__':
    tag = sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else None
    tr, va, ev = (load_split('train') if '--lighter' in sys.argv else None), load_split('val'), load_split('v3eval')
    if tag == 'baseline':   # re-score the cached TF-IDF probs with exact row counts (original grids); writes tune-cuts-baseline-results.json
        z = np.load(os.path.join(OUT, 'baseline-probs.npz')); Pva, Pev = z['va'], z['ev']
    elif tag:
        # a fine-tuned model's p is far more peaked than TF-IDF's: add fine steps near 0 and 1 to every grid (baseline grids unchanged)
        A_GRID[:] = sorted(set(A_GRID + [0.001, 0.005, 0.01])); RC_GRID[:] = sorted(set(RC_GRID + [0.001, 0.005, 0.01]))
        B_GRID[:] = sorted(set(B_GRID + [0.001, 0.005, 0.01, 0.99, 0.995, 0.999])); C_GRID[:] = sorted(set(C_GRID + [0.001, 0.005, 0.01, 0.99, 0.995, 0.999]))
        M_GRID[:] = sorted(set(M_GRID + [0.95, 0.98, 0.99, 0.995, 0.999]))
        Pva, Pev = np.load(os.path.join(OUT, f'probs-{tag}-val.npy')).astype(float), np.load(os.path.join(OUT, f'probs-{tag}-v3eval.npy')).astype(float)
        assert len(Pva) == len(va) and len(Pev) == len(ev)
    else:
        wv, cv, clf = pickle.load(open(os.path.join(OUT, 'baseline.pkl'), 'rb'))
        feat = lambda s: sp.hstack([wv.transform(s), cv.transform(s)]).tocsr()
        cache = os.path.join(OUT, 'baseline-probs.npz')
        if os.path.exists(cache): z = np.load(cache); Pva, Pev = z['va'], z['ev']
        else:
            Pva, Pev = clf.predict_proba(feat(va.text)), clf.predict_proba(feat(ev.text)); np.savez(cache, va=Pva, ev=Pev)
    T = temp_fit(Pva, va.y.values)
    print(f'val acc {(Pva.argmax(1)==va.y.values).mean()*100:.2f}  temperature (fit on val) T={T:.3f}')
    results = {'temperature': round(T, 3)}
    # mechanical reference
    tu = Tuner(ev, Pev); results['mechanical'] = fin(tu.mechT.sum(0))
    print('mechanical', results['mechanical'])
    results['raw'] = report('raw p', tu); show('raw p', results['raw'])
    tuc = Tuner(ev, temp_apply(Pev, T)); results['calibrated'] = report('temperature-calibrated p', tuc); show('temperature-calibrated p', results['calibrated'])
    if not tag:
        results['latency'] = latency(wv, cv, clf, list(ev.text.values[:300])); print(results['latency'])
        if '--lighter' in sys.argv: results['lighter'] = lighter(tr, va, ev, tu)
    json.dump(results, open(os.path.join(OUT, f'tune-cuts-{tag}-results.json' if tag else 'tune-cuts-results.json'), 'w'), indent=1)
