"""Exam #8 scorer, rwxlite side (our figures; rwxmap's CLI score is the official one). Run ONCE, only after docs/product/r16-exam8-pred-sha256.txt is committed.
  python3 -I r16/exam8-score.py --out data/r16/exam8/result.json
Refuses unless truth sha256 and every sha in the committed list match, and --out does not exist. Gate D142: exact_cand >= exact_base AND too_loose_cand <= too_loose_base + floor(0.01*n).
Letters ordered r < w < x; below truth = too loose, above = too tight."""
import csv, hashlib, json, sys, os, collections, argparse
RK = {'r': 0, 'w': 1, 'x': 2}
E = '/home/hamr/PycharmProjects/rwxmap/data/exam8-2026-11-23'; O = 'data/r16/exam8'
TRUTH_SHA = '0dfc8b42bd85f336ab7897b902e228e0ec8cca2960f0ffc6b8887dee17e8ac42'
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
if os.path.exists(a.out): sys.exit('exists: scored once')
sh = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
if sh(f'{E}/truth.csv') != TRUTH_SHA: sys.exit('truth sha mismatch')
for line in open('docs/product/r16-exam8-pred-sha256.txt'):
    if line.startswith('#') or not line.strip(): continue
    h, p = line.split(None, 1)
    if sh(p.strip()) != h: sys.exit('sha mismatch ' + p)
rd = lambda p: list(csv.DictReader(open(p, newline='', encoding='utf-8')))
ops = rd(f'{E}/ops.csv'); ids = [r['id'] for r in ops]; n = len(ids)
truth_rows = rd(f'{E}/truth.csv'); assert [r['id'] for r in truth_rows] == ids; T = [r['label'] for r in truth_rows]
lean = rd(f'{E}/lean/lean.csv'); assert [r['id'] for r in lean] == ids
L = {}
for k, nm in (('cand', 'r16'), ('base', 'r15')):
    for mode, f in (('a', f'letters-{nm}-a090.csv'), ('b85', f'letters-{nm}-b85.csv')):
        rows = rd(f'{O}/{f}'); assert [r['id'] for r in rows] == ids; L[(k, mode)] = [r['letter'] for r in rows]
    rows = rd(f'{O}/perrow-{nm}-fp32.csv'); assert [r['id'] for r in rows] == ids; L[(k, 'standalone')] = [r['standalone'] for r in rows]
L[('mech', 'mech')] = [r['lean_letter'] for r in lean]
def cnt(let, sel=None):
    c = collections.Counter(); 
    for i, (f, t) in enumerate(zip(let, T)):
        if sel is not None and i not in sel: continue
        d = RK[f] - RK[t]; c['exact' if d == 0 else ('loose' if d < 0 else 'tight')] += 1
    return {'exact': c['exact'], 'too_loose': c['loose'], 'too_tight': c['tight']}
res = {'n': n, 'truth_dist': dict(collections.Counter(T)), 'scores': {}, 'paired': {}, 'collision_info': {}}
for key, let in L.items(): res['scores']['/'.join(key)] = cnt(let)
for mode in ('a', 'b85', 'standalone'):
    b, c = L[('base', mode)], L[('cand', mode)]
    ok = lambda x, i: x[i] == T[i]
    res['paired'][mode] = {'better': sum(ok(c, i) and not ok(b, i) for i in range(n)), 'worse': sum(ok(b, i) and not ok(c, i) for i in range(n)), 'letters_differ': sum(b[i] != c[i] for i in range(n))}
allow = int(0.01 * n); B = res['scores']['base/a']; C = res['scores']['cand/a']
res['gate'] = {'allowance': allow, 'exact_ok': C['exact'] >= B['exact'], 'loose_ok': C['too_loose'] - B['too_loose'] <= allow, 'loose_diff': C['too_loose'] - B['too_loose']}
res['gate']['verdict'] = 'GO' if res['gate']['exact_ok'] and res['gate']['loose_ok'] else 'NO-GO'
col = set(open('data/r16/scratch/exam8/collision-ops.txt').read().split()); cs = {i for i, x in enumerate(ids) if x in col}; ns = set(range(n)) - cs
res['collision_info'] = {'collision_ops': len(cs), 'with_all': {}, 'only_collision_ops': {}, 'without_collision_ops': {}}
for k in ('base', 'cand'):
    for mode in ('a', 'b85', 'standalone'):
        res['collision_info']['only_collision_ops'][f'{k}/{mode}'] = cnt(L[(k, mode)], cs); res['collision_info']['without_collision_ops'][f'{k}/{mode}'] = cnt(L[(k, mode)], ns)
bb, cc = res['collision_info']['without_collision_ops']['base/a'], res['collision_info']['without_collision_ops']['cand/a']
res['collision_info']['gate_without'] = {'exact_ok': cc['exact'] >= bb['exact'], 'loose_diff': cc['too_loose'] - bb['too_loose'], 'allowance': int(0.01 * len(ns))}
# too-loose breakdown, candidate mode a
rows = []; ba = L[('base', 'a')]; ca = L[('cand', 'a')]; mech = L[('mech', 'mech')]
for i in range(n):
    if RK[ca[i]] < RK[T[i]]:
        rows.append({'id': ids[i], 'vendor': ops[i]['provider'], 'http': ops[i]['method'], 'path': ops[i]['path'], 'summary': ops[i]['summary'][:60], 'rule': lean[i]['lean_rule'], 'mech': mech[i], 'cand': ca[i], 'base': ba[i], 'truth': T[i], 'in_collision_ops': ids[i] in col,
                     'move': 'kept' if ca[i] == mech[i] else ('lowered' if RK[ca[i]] < RK[mech[i]] else 'raised')})
res['cand_loose_rows'] = rows
agg = lambda k: dict(collections.Counter(r[k] for r in rows).most_common())
res['cand_loose_by'] = {k: agg(k) for k in ('vendor', 'http', 'rule', 'move', 'truth')}
res['cand_loose_by']['rule_x_move'] = dict(collections.Counter(f"{r['rule']}|{r['move']}" for r in rows).most_common())
bl = [i for i in range(n) if RK[ba[i]] < RK[T[i]]]
res['base_loose_by'] = {'vendor': dict(collections.Counter(ops[i]['provider'] for i in bl)), 'move': dict(collections.Counter('kept' if ba[i] == mech[i] else ('lowered' if RK[ba[i]] < RK[mech[i]] else 'raised') for i in bl))}
res['cand_loose_vendor_base_vendor'] = None
res['per_vendor'] = {}
for v in sorted({o['provider'] for o in ops}):
    s = {i for i, o in enumerate(ops) if o['provider'] == v}
    res['per_vendor'][v] = {'n': len(s), 'base/a': cnt(ba, s), 'cand/a': cnt(ca, s), 'mech': cnt(mech, s)}
with open(a.out, 'x') as f: json.dump(res, f, indent=1)
print(json.dumps({k: res[k] for k in ('truth_dist', 'scores', 'paired', 'gate', 'collision_info')}, indent=1))
print(json.dumps({k: res[k] for k in ('cand_loose_by', 'base_loose_by', 'per_vendor')}, indent=1))
for r in rows: print(r)
