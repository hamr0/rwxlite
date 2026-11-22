"""Round 16 small runs: score one model's dev logits (docs/product/prereg-r16-small-runs.md section 5). Deterministic; no randomness, no network.
  python3 r16/score_dev.py --pred dev-logits.csv --name NAME (--T 1.3832 | --val-pred val-logits.csv) --out OUT.json [--rows-out ROWS.csv] [--vs OTHER-ROWS.csv] [--tree data/r16/scratch/rwxmap-1c25be1]
--pred / --val-pred : csv op_id,l_r,l_w,l_x from r16/predict_dev.py (PyTorch fp32, batch 1). --T fixes the temperature (base models keep their own: 0.4.0 student 1.3832, r15 teacher 1.362087); --val-pred fits T on val (bounded minimiser of val NLL on [0.3, 5], as m1/r14-compare.py temp_fit).
Dev = data/r16/labels/final/final-labels-r16-dev-v2.parquet (4,475 rows, label = v2; prior_label = v1, before D143). Subset (b) = r16/dev-subset-b-ids.txt (frozen, 3,286 rows, sha256 asserted).
Mode a = rwxmap secondPass at LOWER_MIN_P = --cut (0.90): the REAL secondpass.js when --tree is given (node r16/secondpass_real.mjs), else the replica of r15/r15_holdout_score.py; the replica is always computed and its disagreement count reported.
Scoring: exact; too loose = predicted letter lower than truth (r < w < x); too tight = higher. Reported for mode a (primary), standalone argmax, mechanical alone, on (a) all dev and (b) the subset.
D143 readout (rwxmap request): too-tight rate on POST create rows, truth before D143 (dev v1 = prior_label) vs after (v2 label); POST create rows = method POST and the first word of operationId or of summary (camelCase split, lower case) in CREATE_WORDS;
also the 9 rows rwxmap's D143 dev answers touched (label_source == rwxmap). Exclusive create of --out."""
import argparse, collections, csv, hashlib, json, math, os, re, subprocess, sys, tempfile
import numpy as np, pandas as pd
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); P = lambda *a: os.path.join(R, *a)
RK = {'r': 0, 'w': 1, 'x': 2}; FLOOR = 1e-15; L3 = 'rwx'
CREATE_WORDS = {'create', 'add', 'new', 'make', 'insert', 'register', 'book', 'reserve', 'schedule', 'submit', 'place'}
SHA = {'dev': 'ef5955787e88e5d4b4ceeaaf93de35026c678c67b86d51e710b275a7534e6e69', 'mech': '0600957b7c581bed19e81c8db0bfb2cce4f288621836c69905ed02a8db869fe4', 'subset': '10375671d69e3a71b793bccb638bef9ccf78eea8c8c72d0446279b437d401997',
       'val': 'c54ee4612f6c93ac4ac800c8ef08c6fd2c1b415184a28d483401fd067c14d949',
       'dev3': 'b268b074c2225993e8f4dc146ea2d2672a8226f1932e20d27c1d9dfb507bceb5'}   # dev3 = final-labels-r16-dev-v3.parquet (prereg section 14)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()

def softmax(L, T):
    z = L / T; z = z - z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)
def temp_fit(L, y):   # golden-section minimum of the val NLL on [0.3, 5] (deterministic; same optimum as scipy minimize_scalar bounded to about 1e-5)
    f = lambda T: -np.log(np.clip(softmax(L, T)[np.arange(len(y)), y], 1e-300, 1)).mean()
    lo, hi, g = 0.3, 5.0, (math.sqrt(5) - 1) / 2; c, d = hi - g * (hi - lo), lo + g * (hi - lo); fc, fd = f(c), f(d)
    for _ in range(80):
        if fc < fd: hi, d, fd = d, c, fc; c = hi - g * (hi - lo); fc = f(c)
        else: lo, c, fc = c, d, fd; d = lo + g * (hi - lo); fd = f(d)
    return (lo + hi) / 2
def read_answer(p):   # replica of the rwxlite engine + rwxmap readAnswer on (r,w,x) at T (as r15/r15_holdout_score.py)
    pr, pw, px = p; pc = pw + px
    z = np.log([max(1 - pc, FLOOR), max(pc - px, FLOOR), max(px, FLOOR)]); z = np.exp(z - z.max()); pr, pw, px = z / z.sum(); pc = pw + px; pr2 = 1 - pc; pw2 = pc - px
    if px >= pw2 and px >= pr2: return 'x', px
    return ('w', pw2) if pw2 >= pr2 else ('r', pr2)
def mode_a(M, rule, review, p, cut):
    if review not in ('loose', 'tight'): return M
    Lt, q = read_answer(p)
    if Lt == M: return M
    if RK[Lt] > RK[M]: return Lt
    if rule != 'credential-set' and q >= cut: return Lt
    return 'x'
def tally(pred, truth):
    c = collections.Counter(); conf = collections.Counter()
    for p, t in zip(pred, truth):
        c['exact' if p == t else ('loose' if RK[p] < RK[t] else 'tight')] += 1; conf[t + '>' + p] += 1
    n = len(pred); o = {'n': n}
    for k in ('exact', 'loose', 'tight'): o[k] = c[k]; o[k + '_pct'] = round(100 * c[k] / n, 3) if n else None
    o['confusion_truth_to_pred'] = {k: conf[k] for k in sorted(conf)}; return o
def words(s):
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', str(s or '')); s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s); return re.sub(r'[^a-z0-9]+', ' ', s.lower()).split()
def is_post_create(r):
    if r.method.upper() != 'POST': return False
    return any(w[:1] and w[0] in CREATE_WORDS for w in (words(r.operationId), words(r.summary)))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--pred', required=True); ap.add_argument('--name', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--T', type=float); ap.add_argument('--val-pred'); ap.add_argument('--cut', type=float, default=0.90); ap.add_argument('--tree'); ap.add_argument('--rows-out'); ap.add_argument('--vs')
    ap.add_argument('--dev-set', choices=['v2', 'v3'], default='v2', help='v3 = final-labels-r16-dev-v3 (62 rwxmap-unsure answers applied; prereg section 14): same rows and order, label = v3, prior_label still v1 for the D143 readout, plus an information block on the 62 rows')
    ap.add_argument('--dev', default=None); ap.add_argument('--mech', default=P('data/r16/labels/work/mech.jsonl')); ap.add_argument('--subset', default=P('r16/dev-subset-b-ids.txt'))
    a = ap.parse_args(); V3 = a.dev_set == 'v3'; a.dev = a.dev or P('data/r16/labels/final/final-labels-r16-dev-' + a.dev_set + '.parquet'); SHA['dev'] = SHA['dev3'] if V3 else SHA['dev']; assert (a.T is None) != (a.val_pred is None), 'give exactly one of --T and --val-pred'
    for k, p in (('dev', a.dev), ('mech', a.mech), ('subset', a.subset)): assert sha(p) == SHA[k], f'{k} file sha256 differs from the preregistered one'
    dev = pd.read_parquet(a.dev).fillna(''); assert len(dev) == 4475 and dev.op_id.is_unique
    mech = {}; 
    for l in open(a.mech, encoding='utf-8'):
        r = json.loads(l); mech[r['op_id']] = r
    sub = set(open(a.subset).read().split()); assert len(sub) == 3286 and sub <= set(dev.op_id)
    pr = pd.read_csv(a.pred, dtype={'op_id': str}); assert list(pr.op_id) == list(dev.op_id), 'prediction rows/order differ from the dev file'
    L = pr[['l_r', 'l_w', 'l_x']].to_numpy(np.float64); assert np.isfinite(L).all()
    if a.T is None:
        assert sha(P('data/round15/val.parquet')) == SHA['val']; v = pd.read_parquet(P('data/round15/val.parquet')); vp = pd.read_csv(a.val_pred, dtype={'op_id': str}); assert list(vp.op_id) == list(v.id)
        T = temp_fit(vp[['l_r', 'l_w', 'l_x']].to_numpy(np.float64), v.y.to_numpy()); T_how = 'fitted on val (4,180 rows, batch 1)'
    else: T, T_how = a.T, 'fixed by the caller'
    PT = softmax(L, T); stand = ['rwx'[i] for i in PT.argmax(1)]
    M = [mech[i]['mech_letter'] for i in dev.op_id]; assert M == list(dev.mech_letter), 'mech.jsonl letters differ from the dev file'
    rep = [mode_a(mech[i]['mech_letter'], mech[i]['mech_rule'], mech[i]['mech_review'], PT[k], a.cut) for k, i in enumerate(dev.op_id)]
    src, ma, agree = 'replica', rep, None
    if a.tree:
        with tempfile.TemporaryDirectory() as tmp:
            fo, fp, fl = (os.path.join(tmp, n) for n in ('ops.jsonl', 'p.jsonl', 'out.jsonl'))
            with open(fo, 'w', encoding='utf-8') as f:
                for r in dev.itertuples(index=False): f.write(json.dumps(dict(op_id=r.op_id, method=r.method, path=r.path, operationId=r.operationId, summary=r.summary, description=r.description), ensure_ascii=False) + '\n')
            with open(fp, 'w') as f:
                for i, p in zip(dev.op_id, PT): f.write(json.dumps(dict(op_id=i, p=[float(x) for x in p])) + '\n')
            subprocess.run(['node', P('r16/secondpass_real.mjs'), '--tree', os.path.abspath(a.tree), '--ops', fo, '--p', fp, '--out', fl], check=True)
            real = [json.loads(l) for l in open(fl)]; assert [r['op_id'] for r in real] == list(dev.op_id) and [r['mech'] for r in real] == M
            ma = [r['letter'] for r in real]; src = 'real secondpass.js (' + os.path.basename(os.path.normpath(a.tree)) + ')'; agree = int(sum(x == y for x, y in zip(ma, rep)))
    t2, t1 = list(dev.label), list(dev.prior_label); assert V3 or sum(x != y for x, y in zip(t1, t2)) == 7
    pc = np.array([is_post_create(r) for r in dev.itertuples(index=False)]); d9 = (dev.d143_touched if V3 else dev.label_source == 'rwxmap').to_numpy(); assert d9.sum() == 9
    u62 = dev.unsure62.to_numpy() if V3 else np.zeros(len(dev), bool); assert u62.sum() == (62 if V3 else 0)
    insub = dev.op_id.isin(sub).to_numpy(); V = {'mode_a': ma, 'standalone': stand, 'mechanical': M}
    def block(mask):
        m = np.where(mask)[0]; sel = lambda x: [x[i] for i in m]; o = {'n': int(len(m))}
        for k, v in V.items(): o[k] = tally(sel(v), sel(t2))
        o['d143_post_create'] = {'rule': 'POST and first word of operationId or summary in ' + ','.join(sorted(CREATE_WORDS)), 'n': int(pc[m].sum())}; o['d143_rwxmap_touched_9'] = {'n': int(d9[m].sum())}
        for nm, flag in (('d143_post_create', pc), ('d143_rwxmap_touched_9', d9)):
            mm = [i for i in m if flag[i]]
            for k in ('mode_a', 'standalone'):
                b, af = tally([V[k][i] for i in mm], [t1[i] for i in mm]), tally([V[k][i] for i in mm], [t2[i] for i in mm])
                o[nm][k] = {'before_D143_v1': {x: b[x] for x in ('exact', 'loose', 'tight', 'tight_pct')}, 'after_D143_v2': {x: af[x] for x in ('exact', 'loose', 'tight', 'tight_pct')}}
        if V3: o['unsure62_info'] = {'n': int(u62[m].sum()), **{k: tally([V[k][i] for i in m if u62[i]], [t2[i] for i in m if u62[i]]) for k in ('mode_a', 'standalone', 'mechanical')}}
        return o
    res = {'name': a.name, 'dev_set': a.dev_set, 'T': T, 'T_how': T_how, 'cut': a.cut, 'mode_a_source': src, 'replica_agrees_rows': agree, 'file_sha256': {'dev': SHA['dev'], 'mech': SHA['mech'], 'subset': SHA['subset'], 'pred': sha(a.pred), 'val_pred': sha(a.val_pred) if a.val_pred else None, 'score_dev.py': sha(__file__)},
           'all_4475': block(np.ones(len(dev), bool)), 'subset_b_3286': block(insub)}
    if a.vs:   # paired counts of mode a on both scopes against another run's --rows-out file
        o = pd.read_csv(a.vs, dtype=str); assert list(o.op_id) == list(dev.op_id); ov = list(o.mode_a); res['paired_vs'] = {'file': a.vs}
        for sc, mask in (('all_4475', np.ones(len(dev), bool)), ('subset_b_3286', insub)):
            bt = wr = 0
            for i in np.where(mask)[0]:
                ds, dr = (ma[i] == t2[i]), (ov[i] == t2[i]); bt += ds and not dr; wr += dr and not ds
            res['paired_vs'][sc] = {'this_right_other_wrong': int(bt), 'other_right_this_wrong': int(wr)}
    if a.rows_out: pd.DataFrame({'op_id': dev.op_id, 'mode_a': ma, 'standalone': stand, 'mechanical': M, 'truth_v2': t2, 'truth_v1': t1, 'in_subset_b': insub, 'post_create': pc}).to_csv(a.rows_out, index=False)
    if os.path.exists(a.out): sys.exit(a.out + ' exists')
    json.dump(res, open(a.out, 'x'), indent=1); print(json.dumps({k: res[k] for k in ('name', 'T', 'mode_a_source', 'replica_agrees_rows')})); 
    for sc in ('all_4475', 'subset_b_3286'): print(sc, {k: (res[sc][k]['exact_pct'], res[sc][k]['loose_pct'], res[sc][k]['tight_pct']) for k in V})
