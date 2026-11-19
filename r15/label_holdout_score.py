"""Round 15: score the cascade, Sonnet alone and bge on the 400 blind-reviewed holdout rows, weighted to the 25,033 disputed rows by disagreement_type.
  python3 -I r15/label_holdout_score.py
Cascade rule: Sonnet pilot letter if sure/likely; else Opus (opus/out/holdout-unsure.csv) if it agrees; else the stricter of the two.
Truth = claude-review-400.csv. Pocket = bge_w_r13_x_mech_x + bge_r_r13_x_mech_x (bge looser than both). Merges its result into final-labels-report.json."""
import csv, json, collections
csv.field_size_limit(10**9)
L = 'data/r15/labels/'
RK = {'r': 0, 'w': 1, 'x': 2}
rd = lambda f: {r['op_id']: r for r in csv.DictReader(open(L + f, newline='', encoding='utf-8'))}
S, R, P, O = rd('disagree-sample-400.csv'), rd('claude-review-400.csv'), rd('sonnet-pilot-400.csv'), rd('opus/out/holdout-unsure.csv')
pop = json.load(open(L + 'opinions-report.json'))['disagreement_types']
assert set(S) == set(R) == set(P) and len(S) == 400
unsure = {i for i, r in P.items() if r['confidence'] == 'unsure'}
assert set(O) == unsure, (len(O), len(unsure), len(set(O) ^ unsure))
n = collections.Counter(r['disagreement_type'] for r in S.values())
W = {t: pop[t] / n[t] for t in n}
def cascade(i):
    s = P[i]['letter']
    if i not in unsure: return s
    o = O[i]['letter']
    return s if o == s else max(s, o, key=RK.get)
OPS = {'cascade': cascade, 'sonnet': lambda i: P[i]['letter'], 'bge': lambda i: S[i]['bge_letter']}
def score(ids, f):
    c = collections.Counter(); tot = 0.0
    for i in ids:
        p, t = f(i), R[i]['letter']
        c['exact' if p == t else ('loose' if RK[p] < RK[t] else 'tight')] += W[S[i]['disagreement_type']]; tot += W[S[i]['disagreement_type']]
    return {k: round(100 * c[k] / tot, 1) for k in ('exact', 'loose', 'tight')}
pocket = [i for i in S if S[i]['disagreement_type'] in ('bge_w_r13_x_mech_x', 'bge_r_r13_x_mech_x')]
exp = {'all': {'cascade': (92.0, 3.8, 4.2), 'sonnet': (87.2, 9.8, 3.1), 'bge': (74.8, 17.5, 7.8)}, 'pocket': {'cascade': (90.9, 4.7, 4.4), 'sonnet': (82.6, 15.2, 2.2), 'bge': (62.4, 33.1, 4.4)}}
res = {'weighted_to_rows': round(sum(W[S[i]['disagreement_type']] for i in S)), 'sample_rows': 400, 'pocket_sample_rows': len(pocket)}
for name, ids in (('all', list(S)), ('pocket', pocket)):
    res[name] = {}
    for op, f in OPS.items():
        r = score(ids, f); e = exp[name][op]
        res[name][op] = {**r, 'expected': dict(zip(('exact', 'loose', 'tight'), e)), 'matches_expected': (r['exact'], r['loose'], r['tight']) == e}
rep = json.load(open(L + 'final-labels-report.json')); rep['holdout_scores'] = res
json.dump(rep, open(L + 'final-labels-report.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
