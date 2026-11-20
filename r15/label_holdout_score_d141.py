"""Round 15: re-score the holdout against the D141 review (d141/holdout-review-d141.csv) instead of claude-review-400.csv.
  python3 r15/label_holdout_score_d141.py
Same weights and opinions as label_holdout_score.py (bge, R13, mech, Jev, Sonnet, cascade). The opinions predate D141, so new misses on D141 families are expected.
Also counts holdout rows matching pattern-net.json per family (no scoring on them: circular). Writes d141/holdout-score-d141.json and adds 'holdout_scores_d141' to d141-report.json."""
import csv, json, collections, re
import pandas as pd
csv.field_size_limit(10**9)
L = 'data/r15/labels/'
RK = {'r': 0, 'w': 1, 'x': 2}
rd = lambda f: {r['op_id']: r for r in csv.DictReader(open(L + f, newline='', encoding='utf-8'))}
S, R0, R, P, O, J = (rd(f) for f in ('disagree-sample-400.csv', 'claude-review-400.csv', 'd141/holdout-review-d141.csv', 'sonnet-pilot-400.csv', 'opus/out/holdout-unsure.csv', 'jev-pilot-400.csv'))
pop = json.load(open(L + 'opinions-report.json'))['disagreement_types']
assert set(S) == set(R) == set(R0) == set(P) == set(J) and len(S) == 400
unsure = {i for i, r in P.items() if r['confidence'] == 'unsure'}
assert set(O) == unsure
n = collections.Counter(r['disagreement_type'] for r in S.values())
W = {t: pop[t] / n[t] for t in n}
def cascade(i):
    s = P[i]['letter']
    if i not in unsure: return s
    o = O[i]['letter']
    return s if o == s else max(s, o, key=RK.get)
assert all(r['jev_letter'] in RK for r in J.values())
OPS = {'cascade': cascade, 'sonnet': lambda i: P[i]['letter'], 'jev': lambda i: J[i]['jev_letter'], 'bge': lambda i: S[i]['bge_letter'],
       'r13': lambda i: S[i]['r13_letter_modea'], 'mech': lambda i: S[i]['mech_letter']}
def score(ids, f, T):
    c = collections.Counter(); tot = 0.0
    for i in ids:
        p, t = f(i), T[i]['letter']
        w = W[S[i]['disagreement_type']]
        c['exact' if p == t else ('loose' if RK[p] < RK[t] else 'tight')] += w; tot += w
    return {k: round(100 * c[k] / tot, 1) for k in ('exact', 'loose', 'tight')}
pocket = [i for i in S if S[i]['disagreement_type'] in ('bge_w_r13_x_mech_x', 'bge_r_r13_x_mech_x')]
res = {'weighted_to_rows': round(sum(W[S[i]['disagreement_type']] for i in S)), 'sample_rows': 400, 'pocket_sample_rows': len(pocket),
       'review_rows_changed_by_d141': sum(R[i]['letter'] != R0[i]['letter'] for i in S)}
for name, ids in (('all', list(S)), ('pocket', pocket)):
    res[name] = {op: {'d141': score(ids, f, R), 'pre_d141': score(ids, f, R0)} for op, f in OPS.items()}
# net matches in the holdout (text field per pattern-net.json; operationId from the opinions file)
net = json.load(open(L + 'd141/pattern-net.json'))
pick = pd.read_parquet(L + 'pick-200000-1-opinions.parquet', columns=['op_id', 'method', 'path', 'operationId', 'summary', 'description']).set_index('op_id')
fm = collections.Counter(); rows = 0
for i in S:
    r = pick.loc[i]
    t = ' '.join(['' if x is None else str(x) for x in (r.method, r.path, r.operationId, r.summary)] + [('' if r.description is None else str(r.description))[:600]]).lower()
    hit = [k for k, p in net['families'].items() if re.search(p, t)]
    rows += bool(hit)
    for k in hit: fm[k] += 1
res['net_matches'] = {'rows_matching_any': rows, 'by_family': dict(sorted(fm.items()))}
json.dump(res, open(L + 'd141/holdout-score-d141.json', 'w'), indent=1)
rep = json.load(open(L + 'd141-report.json')); rep['holdout_scores_d141'] = res
json.dump(rep, open(L + 'd141-report.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
