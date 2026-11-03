"""Fresh exam 2026-11-03 (pre-registered: docs/wiki/exam-prereg-fresh.md). Reuses exam_score.py (infer, mode_a, T, cuts) and lowerflag/fallback rules.
  node m0/exam-inputs.mjs fresh
  python3 train/exam_fresh.py predict   # never opens truth.csv
  python3 train/exam_fresh.py score     # joins truth.csv ONCE
"""
import sys, os, json, csv, time
import numpy as np
import exam_score as E
from common import *
from tune_cuts import temp_apply, guarded

EX = os.path.join(ROOT, 'data', 'exam-fresh-r8soft')
TRUTH = os.path.join(ROOT, 'data', 'exam-2026-11-03-fresh', 'truth.csv')
CONFIGS = ['GONOGO_lba097', 'a_none', 'a_mta095', 'a_askalllower', 'a_lba095_mta095', 'a_lba095', 'a_lba099', 'b_none', 'mechanical']

def load_inputs(): return [json.loads(l) for l in open(os.path.join(EX, 'inputs.jsonl')) if l.strip()]

def configs(pa, pb, mech, conf):
    """-> {name: (final int array, asked bool mask)}; rules as train/lowerflag.py (5, 3, 6) and train/fallback.py (MECH-THEN-ASK)."""
    n = len(pa); no = np.zeros(n, bool); low = pa < mech; c = {}
    c['GONOGO_lba097'] = (pa, low & (conf < 0.97)); c['a_none'] = (pa, no)
    below = conf < 0.95; use = below & (mech >= pa); c['a_mta095'] = (np.where(use, mech, pa), below & ~use)
    c['a_askalllower'] = (pa, low)
    ask = low & (conf < 0.95); nl = ~low & (conf < 0.95); use = nl & (mech >= pa); c['a_lba095_mta095'] = (np.where(use, mech, pa), ask | (nl & ~use))
    c['a_lba095'] = (pa, low & (conf < 0.95)); c['a_lba099'] = (pa, low & (conf < 0.99))
    c['b_none'] = (pb, no); c['mechanical'] = (mech, no)
    return c

def predict():
    rows = load_inputs(); assert len(rows) == 949, len(rows)
    t0 = time.time(); Praw = E.infer([fmt_text(r) for r in rows]); sec = time.time() - t0
    P = temp_apply(Praw.astype(float), E.T); conf = P.max(1)
    pa = E.mode_a(rows, P); pb = guarded(P, E.MARGIN); mech = np.array([ORDER[r['class']] for r in rows])
    C = configs(pa, pb, mech, conf)
    with open(os.path.join(EX, 'predictions.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['id', 'provider', 'method', 'mech', 'mech_rule', 'tier', 'a_letter', 'b_letter', 'move', 'p_r', 'p_w', 'p_x', 'max_p', *CONFIGS])
        for i, r in enumerate(rows):
            mv = 'lowering' if pa[i] < mech[i] else 'raise' if pa[i] > mech[i] else 'keep'
            w.writerow([r['id'], r['provider'], r['method'], r['class'], r['rule'], TIER.get(r['jev_tier'], 'none'), LABELS[pa[i]], LABELS[pb[i]], mv,
                        *[f'{P[i, k]:.6f}' for k in range(3)], f'{conf[i]:.6f}', *[('ask' if C[k][1][i] else LABELS[C[k][0][i]]) for k in CONFIGS]])
    print(f'predicted {len(rows)} rows in {sec:.1f}s, truth.csv never opened')

def piles(final, asked, pa, y, m=None):
    m = np.ones(len(y), bool) if m is None else m; ans = m & ~asked; n = int(m.sum()); a = int(ans.sum())
    r = int((ans & (final == y)).sum()); l = int((ans & (final < y)).sum()); t = int((ans & (final > y)).sum()); k = int((m & asked).sum())
    assert r + l + t + k == n
    pc = lambda x, d: round(100 * x / d, 2) if d else None
    return {'n': n, 'answered': a, 'right': r, 'rightPct': pc(r, a), 'rightPctAll': pc(r, n), 'loose': l, 'loosePct': pc(l, a), 'loosePctAll': pc(l, n),
            'tight': t, 'tightPct': pc(t, a), 'tightPctAll': pc(t, n), 'asked': k, 'askedPct': pc(k, n),
            'askRight': int((m & asked & (pa == y)).sum()), 'askLoose': int((m & asked & (pa < y)).sum()), 'askTight': int((m & asked & (pa > y)).sum())}

def score():
    P = {r['id']: r for r in csv.DictReader(open(os.path.join(EX, 'predictions.csv')))}
    inp = {r['id']: r for r in load_inputs()}
    truth = {}
    for r in csv.DictReader(open(TRUTH, newline='', encoding='utf-8')):   # the ONLY place truth is opened
        assert r['id'] not in truth; truth[r['id']] = r['label']
    assert set(truth) == set(P) == set(inp) and len(truth) == 949, 'join not 1:1 over 949'
    assert set(truth.values()) <= set(LABELS)
    ids = [r['id'] for r in load_inputs()]; N = len(ids)
    y = np.array([ORDER[truth[i]] for i in ids]); pa = np.array([ORDER[P[i]['a_letter']] for i in ids]); mech = np.array([ORDER[P[i]['mech']] for i in ids])
    conf = np.array([float(P[i]['max_p']) for i in ids])
    res = {'n': N, 'T': E.T, 'cuts': E.CUT, 'margin': E.MARGIN, 'truth_dist': {l: int((y == ORDER[l]).sum()) for l in LABELS}, 'configs': {}}
    asked = {}
    for c in CONFIGS:
        col = [P[i][c] for i in ids]; asked[c] = np.array([v == 'ask' for v in col]); fin = np.array([0 if v == 'ask' else ORDER[v] for v in col])
        pref = np.array([ORDER[P[i]['b_letter']] for i in ids]) if c.startswith('b_') else pa
        res['configs'][c] = piles(fin, asked[c], pref, y)
        res['configs'][c]['final'] = fin.tolist() if False else None
    # moves (mode a, no bar)
    res['moves'] = {}
    for nm in ('lowering', 'raise', 'keep'):
        m = np.array([P[i]['move'] == nm for i in ids]); res['moves'][nm] = {'n': int(m.sum()), 'right': int((m & (pa == y)).sum()), 'loose': int((m & (pa < y)).sum()), 'tight': int((m & (pa > y)).sum())}
    # GO/NO-GO config breakdowns
    g = np.array([0 if P[i]['GONOGO_lba097'] == 'ask' else ORDER[P[i]['GONOGO_lba097']] for i in ids]); ga = asked['GONOGO_lba097']
    for key, arr in (('by_vendor', np.array([inp[i]['provider'] for i in ids])), ('by_method', np.array([inp[i]['method'] for i in ids])), ('by_tier', np.array([P[i]['tier'] for i in ids])), ('by_move', np.array([P[i]['move'] for i in ids]))):
        res['GONOGO_' + key] = {v: piles(g, ga, pa, y, arr == v) for v in sorted(set(arr))}
    for c in ('a_none', 'mechanical'):
        fin = np.array([ORDER[P[i][c]] for i in ids]); 
        for key, arr in (('by_vendor', np.array([inp[i]['provider'] for i in ids])), ('by_method', np.array([inp[i]['method'] for i in ids]))):
            res[c + '_' + key] = {v: piles(fin, np.zeros(N, bool), pa, y, arr == v) for v in sorted(set(arr))}
    L = np.where(~ga & (g < y))[0]; lt = {'loweredWrongly': 0, 'keepMechLoose': 0, 'raiseStillLoose': 0}; rows = []
    for k in L:
        typ = 'loweredWrongly' if g[k] < mech[k] else 'keepMechLoose' if g[k] == mech[k] else 'raiseStillLoose'; lt[typ] += 1; r = inp[ids[k]]
        rows.append({'id': ids[k], 'type': typ, 'vendor': r['provider'], 'method': r['method'], 'path': r['path'], 'operationId': r['operationId'], 'summary': (r['summary'] or '')[:140], 'mech': LABELS[mech[k]], 'mech_rule': r['class'] + '/' + r['rule'],
                     'model': LABELS[g[k]], 'max_p': conf[k], 'p': [float(P[ids[k]][q]) for q in ('p_r', 'p_w', 'p_x')], 'truth': LABELS[y[k]]})
    res['GONOGO_loose_types'] = lt; res['GONOGO_loose_rows'] = rows
    # other-config loose rows (a_none), for reference
    res['a_none_loose_rows'] = [{'id': ids[k], 'method': inp[ids[k]]['method'], 'path': inp[ids[k]]['path'], 'mech': LABELS[mech[k]], 'model': LABELS[pa[k]], 'max_p': conf[k], 'truth': LABELS[y[k]], 'move': P[ids[k]]['move']} for k in np.where(pa < y)[0]]
    # asked rows held (GO config): list those that would be loose
    res['GONOGO_asked_loose_rows'] = [{'id': ids[k], 'method': inp[ids[k]]['method'], 'path': inp[ids[k]]['path'], 'mech': LABELS[mech[k]], 'model': LABELS[pa[k]], 'max_p': conf[k], 'truth': LABELS[y[k]]} for k in np.where(ga & (pa < y))[0]]
    cc = res['configs']['GONOGO_lba097']
    ok = {'loose_le_0.5pct': cc['loosePct'] <= 0.5, 'exact_ge_91pct': cc['rightPct'] >= 91.0, 'asked_le_15pct': cc['askedPct'] <= 15.0}
    res['go_no_go'] = {**ok, 'verdict': 'PASS' if all(ok.values()) else 'NO-GO', 'right_pct': cc['rightPct'], 'loose_pct': cc['loosePct'], 'loose_rows': cc['loose'], 'asked_pct': cc['askedPct']}
    res['confusion_a_none'] = [[int(((y == t) & (pa == q)).sum()) for q in range(3)] for t in range(3)]
    json.dump(res, open(os.path.join(EX, 'results.json'), 'w'), indent=1)
    f = lambda d: f"right {d['right']} ({d['rightPct']}% ans, {d['rightPctAll']}% all)  loose {d['loose']} ({d['loosePct']}%)  tight {d['tight']} ({d['tightPct']}%)  asked {d['asked']} ({d['askedPct']}%; held R/L/T {d['askRight']}/{d['askLoose']}/{d['askTight']})"
    for c in CONFIGS: print(f'{c:18s}', f(res['configs'][c]))
    print('moves', res['moves']); print('loose types', lt)
    for k in ('by_vendor', 'by_method', 'by_tier', 'by_move'):
        print('--- GONOGO', k); [print(f'  {v:12s}', f(d)) for v, d in res['GONOGO_' + k].items()]
    for r in rows: print('LOOSE', json.dumps(r))
    print('GO/NO-GO', json.dumps(res['go_no_go']))

if __name__ == '__main__':
    {'predict': predict, 'score': score}[sys.argv[1]]()
