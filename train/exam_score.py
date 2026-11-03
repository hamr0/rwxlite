"""One-time M0 exam, MiniLM r8soft (pre-registered in docs/wiki/exam-prereg-r8soft.md).
  node m0/exam-inputs.mjs                 # inputs only, truth columns never read
  python3 train/exam_score.py predict     # CPU inference -> data/exam-r8soft/predictions.csv; never opens the truth column
  python3 train/exam_score.py score       # joins truth ONCE -> data/exam-r8soft/results.json
"""
import sys, os, json, csv, time
import numpy as np
from common import *
from tune_cuts import temp_apply, guarded

EX = os.path.join(ROOT, 'data', 'exam-r8soft')
CKPT = os.path.join(OUT, 'ckpt-r8soft', 'final')
T = 0.844
CUT = {'lower': 0.30, 'rcut': 0.40, 'raise-wx': 0.15, 'raise-get': 0.05}
MARGIN = 0.6
THR = [None, 0.7, 0.9, 0.95]
MAXLEN = 128
TRUTH_FILE = os.path.join(os.environ.get('RWXMAP_DIR', os.path.abspath(os.path.join(ROOT, '..', 'rwxmap'))), 'data', 'exam-2026-09-22', 'labelled.csv')

def load_inputs():
    return [json.loads(l) for l in open(os.path.join(EX, 'inputs.jsonl')) if l.strip()]

def infer(texts):
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    torch.set_num_threads(8)
    tok = AutoTokenizer.from_pretrained(CKPT); model = AutoModelForSequenceClassification.from_pretrained(CKPT).eval()
    E = tok(texts, truncation=True, max_length=MAXLEN)['input_ids']
    order = sorted(range(len(E)), key=lambda i: len(E[i])); P = np.zeros((len(E), 3), dtype=np.float32)
    with torch.no_grad():
        for i in range(0, len(order), 128):
            ids = order[i:i + 128]; L = max(len(E[j]) for j in ids)
            x = torch.zeros(len(ids), L, dtype=torch.long); m = torch.zeros(len(ids), L, dtype=torch.long)
            for k, j in enumerate(ids): x[k, :len(E[j])] = torch.tensor(E[j]); m[k, :len(E[j])] = 1
            P[ids] = torch.softmax(model(input_ids=x, attention_mask=m).logits, -1).numpy()
    return P

def mode_a(rows, P):
    """tune_cuts.py / abstain.py mode (a) at the all-data cuts; P calibrated (n,3)."""
    px, ch = P[:, 2], P[:, 1] + P[:, 2]; out = []
    for i, r in enumerate(rows):
        m = ORDER[r['class']]; t = TIER.get(r['jev_tier'], 'none')
        if t == 'lower' and m == 2 and px[i] < CUT['lower']: m = 0 if (r['method'] == 'POST' and ch[i] < CUT['rcut']) else 1
        elif t == 'raise-wx' and m == 1 and px[i] >= CUT['raise-wx']: m = 2
        elif t == 'raise-get' and m == 0 and ch[i] >= CUT['raise-get']: m = 1
        if cred_hit(r): m = 2
        out.append(m)
    return np.array(out)

def predict():
    rows = load_inputs(); assert len(rows) == 4279, len(rows)
    texts = [fmt_text(r) for r in rows]
    t0 = time.time(); Praw = infer(texts); sec = time.time() - t0
    P = temp_apply(Praw.astype(float), T); conf = P.max(1)
    a = mode_a(rows, P); b = guarded(P, MARGIN)
    cols = {}
    for nm, pr in (('a', a), ('b', b)):
        for t in THR:
            cols[f'{nm}_{"none" if t is None else t}'] = [LABELS[k] if (t is None or conf[i] >= t) else 'ask' for i, k in enumerate(pr)]
    with open(os.path.join(EX, 'predictions.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['id', *cols, 'max_p', 'p_r', 'p_w', 'p_x'])
        for i, r in enumerate(rows): w.writerow([r['id'], *[cols[c][i] for c in cols], f'{conf[i]:.6f}', *[f'{P[i, k]:.6f}' for k in range(3)]])
    print(f'predicted {len(rows)} rows in {sec:.1f}s ({sec / len(rows) * 1000:.2f} ms/op batched), truth never opened')

def score():
    P = {r['id']: r for r in csv.DictReader(open(os.path.join(EX, 'predictions.csv')))}
    inp = {r['id']: r for r in load_inputs()}
    truth = {}
    for r in csv.DictReader(open(TRUTH_FILE, newline='', encoding='utf-8')):   # the ONLY place the truth column is opened
        assert r['row_id'] not in truth, 'duplicate truth id'; truth[r['row_id']] = r['truth_class']
    assert set(truth) == set(P) == set(inp) and len(truth) == 4279, 'row join is not 1:1 over 4279'
    assert set(truth.values()) <= set(LABELS), set(truth.values())
    ids = [r['id'] for r in load_inputs()]
    y = np.array([ORDER[truth[i]] for i in ids])
    meth = np.array([inp[i]['method'] for i in ids]); tier = np.array([TIER.get(inp[i]['jev_tier'], 'none') for i in ids]); prov = np.array([inp[i]['provider'] for i in ids])
    rule = np.array([inp[i]['class'] + '/' + inp[i]['rule'] for i in ids])
    mech = np.array([ORDER[inp[i]['class']] for i in ids])
    def stats(pred_ans, pred_full, m):
        pr, tr, pf = pred_ans[m], y[m], pred_full[m]; ans = pr >= 0; na = int(ans.sum()); n = int(m.sum())
        d = {'n': n, 'answered': na, 'answered_pct': round(100 * na / n, 1) if n else None, 'asked': n - na, 'asked_would_be_loose': int(((~ans) & (pf < tr)).sum()),
             'exact': int((pr[ans] == tr[ans]).sum()), 'loose': int((pr[ans] < tr[ans]).sum()), 'tight': int((pr[ans] > tr[ans]).sum())}
        for k in ('exact', 'loose', 'tight'): d[k + '_pct'] = round(100 * d[k] / na, 2) if na else None
        return d
    res = {'truth_file': TRUTH_FILE, 'n': len(ids), 'T': T, 'cuts': CUT, 'margin': MARGIN, 'mechanical': {}, 'configs': {}}
    allsel = np.ones(len(ids), bool)
    groups = {'method': meth, 'tier': tier, 'provider': prov, 'rule': rule}
    def block(pred_ans, pred_full):
        d = {'overall': stats(pred_ans, pred_full, allsel)}
        for g, arr in groups.items(): d['by_' + g] = {v: stats(pred_ans, pred_full, arr == v) for v in sorted(set(arr))}
        return d
    res['mechanical'] = block(mech, mech)
    cols = [c for c in next(iter(P.values())) if c[:2] in ('a_', 'b_')]
    for c in cols:
        full_col = 'a_none' if c.startswith('a_') else 'b_none'
        pa = np.array([-1 if P[i][c] == 'ask' else ORDER[P[i][c]] for i in ids]); pf = np.array([ORDER[P[i][full_col]] for i in ids])
        res['configs'][c] = block(pa, pf)
    # too-loose rows of the go/no-go config, for the findings
    pa = np.array([ORDER[P[i]['a_none']] for i in ids]); pb = np.array([ORDER[P[i]['b_none']] for i in ids])
    def loose_rows(pred):
        out = []
        for k in np.where(pred < y)[0]:
            r = inp[ids[k]]; out.append({'id': ids[k], 'provider': r['provider'], 'method': r['method'], 'path': r['path'], 'operationId': r['operationId'], 'summary': (r['summary'] or '')[:120], 'mech': r['class'] + '/' + r['rule'], 'tier': TIER.get(r['jev_tier'], 'none'),
                                'pred': LABELS[pred[k]], 'truth': LABELS[y[k]], 'max_p': float(P[ids[k]]['max_p']), 'p': [float(P[ids[k]][q]) for q in ('p_r', 'p_w', 'p_x')]})
        return out
    res['loose_rows_a_none'] = loose_rows(pa); res['loose_rows_b_none'] = loose_rows(pb)
    # confusion matrices (truth rows x pred cols)
    for nm, pr in (('a_none', pa), ('b_none', pb), ('mechanical', mech)):
        res.setdefault('confusion', {})[nm] = [[int(((y == t) & (pr == q)).sum()) for q in range(3)] for t in range(3)]
    res['truth_dist'] = {l: int((y == ORDER[l]).sum()) for l in LABELS}
    # go / no-go
    g = res['configs']['a_none']['overall']
    res['go_no_go'] = {'exact_pct': g['exact_pct'], 'loose_pct': g['loose_pct'], 'loose_rows': g['loose'], 'bar_exact': 91.0, 'bar_loose': 0.5, 'pass_exact': g['exact_pct'] >= 91.0, 'pass_loose': g['loose_pct'] <= 0.5}
    res['go_no_go']['verdict'] = 'GO' if res['go_no_go']['pass_exact'] and res['go_no_go']['pass_loose'] else 'NO-GO'
    json.dump(res, open(os.path.join(EX, 'results.json'), 'w'), indent=1)
    f = lambda d: f"answered {d['answered_pct']}% ({d['answered']}/{d['n']})  exact {d['exact_pct']}% ({d['exact']})  loose {d['loose_pct']}% ({d['loose']})  tight {d['tight_pct']}% ({d['tight']})  asked {d['asked']} (would-be-loose {d['asked_would_be_loose']})"
    print('mechanical          ', f(res['mechanical']['overall']))
    for c in res['configs']: print(f'{c:20s}', f(res['configs'][c]['overall']))
    for g_ in ('method', 'tier'):
        for c in ('a_none', 'b_none'):
            print(f'--- {c} by {g_}')
            for v, d in res['configs'][c]['by_' + g_].items(): print(f'  {v:10s}', f(d))
    print('GO/NO-GO', json.dumps(res['go_no_go']))

if __name__ == '__main__':
    {'predict': predict, 'score': score}[sys.argv[1]]()
