"""Round 15 Jev pilot, scoring: four opinions vs the blind review of 400 disputed rows, weighted to the population by disagreement_type.
  python3 -I r15/jev_pilot_score.py
Inputs (data/r15/labels/): disagree-sample-400.csv, claude-review-400.csv, jev-pilot-raw.jsonl (r15/jev_pilot.mjs), opinions-report.json.
Outputs: jev-pilot-400.csv, jev-pilot-report.json. Too loose = letter below the review (r<w<x); too tight = above."""
import csv, json, collections
csv.field_size_limit(10**9)
L = 'data/r15/labels/'
RK = {'r': 0, 'w': 1, 'x': 2}
S = {r['op_id']: r for r in csv.DictReader(open(L + 'disagree-sample-400.csv', newline='', encoding='utf-8'))}
R = {r['op_id']: r for r in csv.DictReader(open(L + 'claude-review-400.csv', newline='', encoding='utf-8'))}
J = {j['op_id']: j for j in map(json.loads, open(L + 'jev-pilot-raw.jsonl'))}
pop = json.load(open(L + 'opinions-report.json'))['disagreement_types']
assert set(S) == set(R) == set(J) and len(S) == 400
ncnt = collections.Counter(r['disagreement_type'] for r in S.values())
W = {t: pop[t] / n for t, n in ncnt.items()}
OPS = ['bge', 'r13', 'mech', 'jev']
def letter(op, i):
    return {'bge': S[i]['bge_letter'], 'r13': S[i]['r13_letter_modea'], 'mech': S[i]['mech_letter'], 'jev': J[i]['jev_letter']}[op]
rows = []
for i in S:
    t = R[i]['letter']
    d = {'op_id': i, 'disagreement_type': S[i]['disagreement_type'], 'review_letter': t, 'review_conf': R[i]['confidence'], 'weight': round(W[S[i]['disagreement_type']], 4)}
    for op in OPS: d[op + '_letter'] = letter(op, i)
    d.update(jev_tier=J[i]['tier'] or '', jev_called=J[i]['called'], jev_p_first=J[i]['p_first'] if J[i]['p_first'] is not None else '', jev_p_changes=J[i]['p_changes'] if J[i]['p_changes'] is not None else '', jev_model=J[i]['model'] or '', jev_move=J[i]['jev_move'], jev_tok_in=J[i]['tok_in'], jev_calls=J[i]['calls'])
    rows.append(d)
with open(L + 'jev-pilot-400.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def kind(p, t): return 'exact' if p == t else ('loose' if RK[p] < RK[t] else 'tight')
def score(sel, op, weighted):
    c = {'exact': 0.0, 'loose': 0.0, 'tight': 0.0}; tot = 0.0
    for d in sel:
        wt = d['weight'] if weighted else 1.0
        c[kind(d[op + '_letter'], d['review_letter'])] += wt; tot += wt
    return {'n': len(sel), **{k: (round(100 * v / tot, 1) if tot else None) for k, v in c.items()}} if weighted is not None else None
def raw(sel, op):
    c = collections.Counter(kind(d[op + '_letter'], d['review_letter']) for d in sel)
    return {'n': len(sel), 'exact': c['exact'], 'loose': c['loose'], 'tight': c['tight']}
sure = [d for d in rows if d['review_conf'] == 'sure']
called = [d for d in rows if d['jev_called']]
rep = {'letters': sorted({d['review_letter'] for d in rows}), 'review_conf': dict(collections.Counter(d['review_conf'] for d in rows)),
       'sample_by_type': dict(ncnt), 'population_by_type': pop,
       'all': {op: {'weighted_pct': score(rows, op, True), 'raw': raw(rows, op)} for op in OPS},
       'sure_only': {op: {'weighted_pct': score(sure, op, True), 'raw': raw(sure, op)} for op in OPS},
       'jev_called_rows_only': {op: {'raw': raw(called, op)} for op in OPS},
       'by_type': {t: {'n': n, 'pop': pop[t], **{op: raw([d for d in rows if d['disagreement_type'] == t], op) for op in OPS}} for t, n in sorted(ncnt.items(), key=lambda x: -pop[x[0]])}}
pair = [d for d in rows if d['disagreement_type'] in ('bge_w_r13_x_mech_x', 'bge_r_r13_x_mech_x')]
rep['bge_looser_than_both_two_big_types'] = {'rows_pop': pop['bge_w_r13_x_mech_x'] + pop['bge_r_r13_x_mech_x'], 'n_sample': len(pair), **{op: {'weighted_pct': score(pair, op, True), 'raw': raw(pair, op)} for op in OPS}}
rep['jev_pipeline'] = {'rows_in_a_tier': len(called), 'rows_no_tier_keep_mech': 400 - len(called), 'tiers': dict(collections.Counter(d['jev_tier'] or 'none' for d in rows)), 'moves': dict(collections.Counter(d['jev_move'] for d in rows)), 'models': sorted({d['jev_model'] for d in rows if d['jev_model']})}
# cost
tin = sum(J[i]['tok_in'] for i in J); tout = sum(J[i]['tok_out'] for i in J); calls = sum(J[i]['calls'] for i in J); fail = sum(J[i]['failed'] for i in J)
PRICE = 42 / 1e9
cost = tin * PRICE
by = collections.defaultdict(lambda: [0, 0, 0])
for d in rows:
    b = by[d['disagreement_type']]; b[0] += 1; b[1] += J[d['op_id']]['tok_in']; b[2] += J[d['op_id']]['calls']
proj_cost = sum(pop[t] * (b[1] / b[0]) * PRICE for t, b in by.items()); proj_calls = sum(pop[t] * (b[2] / b[0]) for t, b in by.items())
rep['cost'] = {'calls': calls, 'failed_calls': fail, 'input_tokens': tin, 'output_tokens': tout, 'price_per_input_token_usd': PRICE, 'price_source': 'computed from response token counts at 42e-9 per input token (rwxmap jev-learnings, as m0/jev-label.mjs); output not billed; not a vendor invoice',
                'pilot_usd': round(cost, 4), 'usd_per_row': round(cost / 400, 6),
                'projection_25033_weighted_by_type': {'rows': sum(pop.values()), 'calls': round(proj_calls), 'usd': round(proj_cost, 2)},
                'projection_25033_flat': {'usd': round(cost / 400 * sum(pop.values()), 2)}, 'note': 'a few smoke calls before the run (about 4 calls, under $0.001) are not in the pilot total'}
json.dump(rep, open(L + 'jev-pilot-report.json', 'w'), indent=1)
pr = lambda x: print(json.dumps(x))
print('letters', rep['letters'], rep['review_conf'])
for k in ('all', 'sure_only'):
    print(k)
    for op in OPS: print(' ', op, rep[k][op]['weighted_pct'], rep[k][op]['raw'])
print('jev called only')
for op in OPS: print(' ', op, rep['jev_called_rows_only'][op]['raw'])
for t, v in rep['by_type'].items():
    if v['pop'] > 1000: print(t, v['n'], v['pop']); [print('   ', op, v[op]) for op in OPS]
pr(rep['bge_looser_than_both_two_big_types']); pr(rep['jev_pipeline']); pr(rep['cost'])
