"""Exam #5 scorer (docs/wiki/prereg-exam5.md). Run ONCE, only after the predictions' sha256s are committed and truth.csv is shared. Standard library only.

  python3 -I m1/exam5-score.py --ops OPS.csv --truth TRUTH.csv --truth-sha256 HEX \
      --pred-r13 predictions-r13.csv --pred-v020 predictions-v020.csv --sha-list docs/wiki/exam5-predictions.sha256 --out results.json \
      [--sp-r13 secondpass-r13.csv --sp-v020 secondpass-v020.csv] [--mech mech-v4.csv]

Definitions are those of m1/r13-valpick.py: letters are ordered r < w < x; a letter BELOW the truth is "too loose", ABOVE is "too tight", equal is "right".
STANDALONE (model only, no mechanical letter, no second pass): letter = argmax of (r, w, x) = (1 - p_changes, p_changes - p_is_x, p_is_x) read from the
prediction CSV exactly as rwxmap derives them (first maximum wins, order r, w, x).
PRODUCT path = rwxmap's real CLI secondPass, mode a, mechanical v4, run by rwxmap. Its per-row final letters come in --sp-* files (columns id,letter; extra columns ignored).
We score those letters against truth with the same definitions. If --mech (id,class,rule,review from rwxmap's mechanical v4) is also given, the script recomputes the
letters with the secondPass replica of m1/r13-valpick.py (lower only at top-letter p >= 0.97, credential-set never lowered) from OUR predictions and reports every row where
the replica differs from rwxmap's letter. That check is information; rwxmap's letters are the product numbers.

FROZEN BAR (docs/wiki/prereg-r13.md section 6): R13 passes only if, on BOTH paths, R13 has no more too-loose AND no fewer exact than shipped 0.2.0 (T 0.844, not refit).
Equal counts pass; any one of the four comparisons worse fails. Without --sp-* the verdict is reported as INCOMPLETE (standalone half only).

Refuses unless: truth sha256 equals --truth-sha256 (agreed with rwxmap before scoring), the prediction files match --sha-list, ids are exactly ops.csv's, in the same
order, in every file, model strings are the ones in the prereg, and --out does not exist (scored once)."""
import sys, os, csv, json, math, hashlib, argparse, collections

RANK = {'r': 0, 'w': 1, 'x': 2}; FLOOR = 1e-15; THR = 0.97
EXPECT = {'r13': 'rwxlite-0.3.1+bbe1997d', 'v020': 'rwxlite-0.2.0+8503b655'}
T = {'r13': 0.991463, 'v020': 0.844}

# ---- replica of rwxmap secondPass, copied from m1/r13-valpick.py (T0 = 1: p given is already calibrated) ----
def read_logits(px, pc):
    ok = all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in (px, pc)) and pc >= px
    if not ok: return None
    return [math.log(max(1 - pc, FLOOR)), math.log(max(pc - px, FLOOR)), math.log(max(px, FLOOR))]
def probs(z):
    m = max(z); e = [math.exp(v - m) for v in z]; t = sum(e); return [v / t for v in e]
def read_answer(z):
    pr, pw, px = probs(z); pc = pw + px; pr2 = 1 - pc; pw2 = pc - px
    if px >= pw2 and px >= pr2: return ('x', px)
    if pw2 >= pr2: return ('w', pw2)
    return ('r', pr2)
def final_letter(M, rule, review, z):
    if review not in ('loose', 'tight'): return M
    if z is None: return M if M == 'x' else 'x'
    Lt, p = read_answer(z)
    if Lt == M: return M
    if RANK[Lt] > RANK[M]: return Lt
    if rule != 'credential-set' and p >= THR: return Lt
    return 'x'

def outcome(f, t):
    d = RANK[f] - RANK[t]; return 'right' if d == 0 else ('loose' if d < 0 else 'tight')
def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def die(m): print('exam5-score: ' + m, file=sys.stderr); sys.exit(1)
def read_csv(p):
    with open(p, newline='', encoding='utf-8') as f: return list(csv.DictReader(f))

ap = argparse.ArgumentParser()
for k in ('ops', 'truth', 'truth-sha256', 'pred-r13', 'pred-v020', 'sha-list', 'out'): ap.add_argument('--' + k, required=True)
for k in ('sp-r13', 'sp-v020', 'mech'): ap.add_argument('--' + k)
a = ap.parse_args()
if os.path.exists(a.out): die(f'{a.out} exists: the exam is scored once')
if sha_file(a.truth) != a.truth_sha256: die(f'truth sha256 {sha_file(a.truth)} != --truth-sha256')

listed = {}
for line in open(a.sha_list, encoding='utf-8'):
    if line.strip(): h, n = line.split(None, 1); listed[os.path.basename(n.strip())] = h
for p in (a.pred_r13, a.pred_v020):
    n = os.path.basename(p)
    if listed.get(n) != sha_file(p): die(f'{n}: sha256 does not match {a.sha_list}')

ops = read_csv(a.ops); ids = [r['id'] for r in ops]
if len(set(ids)) != len(ids): die('duplicate id in ops.csv')
truth_rows = read_csv(a.truth)
if [r['id'] for r in truth_rows] != ids: die('truth.csv ids differ from ops.csv (set or order)')
truth = [r['label'] for r in truth_rows]
if any(t not in RANK for t in truth): die('truth label outside r/w/x')

def load_pred(path, key):
    rows = read_csv(path)
    if [r['id'] for r in rows] != ids: die(f'{path}: ids differ from ops.csv (set or order)')
    P = []
    for r in rows:
        if r['model'] != EXPECT[key]: die(f"{path}: model {r['model']} != {EXPECT[key]}")
        px, pc = float(r['p_is_x']), float(r['p_changes'])
        if not (math.isfinite(px) and math.isfinite(pc) and 0 <= px <= 1 and 0 <= pc <= 1 and pc >= px): die(f"{path}: bad p on {r['id']}")
        P.append((px, pc))
    return P
pred = {'r13': load_pred(a.pred_r13, 'r13'), 'v020': load_pred(a.pred_v020, 'v020')}

def standalone_letter(px, pc):
    v = [1 - pc, pc - px, px]; return 'rwx'[v.index(max(v))]   # list.index = first maximum, order r, w, x
def count(letters):
    c = collections.Counter(outcome(f, t) for f, t in zip(letters, truth))
    return {'exact': c['right'], 'too_loose': c['loose'], 'too_tight': c['tight'], 'n': len(truth)}

res = {'rows': len(ids), 'truth_sha256': a.truth_sha256, 'models': EXPECT, 'T': T, 'standalone': {}, 'product': {}, 'checks': {}}
letters = {}
for k in ('r13', 'v020'):
    letters[k] = [standalone_letter(*p) for p in pred[k]]
    res['standalone'][k] = count(letters[k])
res['standalone_differing_rows'] = [{'id': i, 'truth': t, 'r13': x, 'v020': y} for i, t, x, y in zip(ids, truth, letters['r13'], letters['v020']) if x != y]
res['standalone_too_loose_rows'] = {k: [{'id': i, 'truth': t, 'got': g} for i, t, g in zip(ids, truth, letters[k]) if outcome(g, t) == 'loose'] for k in letters}

def bar(s):
    r, v = s['r13'], s['v020']
    return {'too_loose_ok': r['too_loose'] <= v['too_loose'], 'exact_ok': r['exact'] >= v['exact'],
            'pass': r['too_loose'] <= v['too_loose'] and r['exact'] >= v['exact']}
res['standalone_bar'] = bar(res['standalone'])

sp = {}
if a.sp_r13 and a.sp_v020:
    for k, p in (('r13', a.sp_r13), ('v020', a.sp_v020)):
        rows = read_csv(p)
        if [r['id'] for r in rows] != ids: die(f'{p}: ids differ from ops.csv (set or order)')
        col = 'letter' if 'letter' in rows[0] else None
        if col is None: die(f'{p}: needs a `letter` column')
        sp[k] = [r[col].strip() for r in rows]
        if any(x not in RANK for x in sp[k]): die(f'{p}: letter outside r/w/x')
        res['product'][k] = count(sp[k])
    res['product_bar'] = bar(res['product'])
    res['product_too_loose_rows'] = {k: [{'id': i, 'truth': t, 'got': g} for i, t, g in zip(ids, truth, sp[k]) if outcome(g, t) == 'loose'] for k in sp}
    res['product_differing_rows'] = [{'id': i, 'truth': t, 'r13': x, 'v020': y} for i, t, x, y in zip(ids, truth, sp['r13'], sp['v020']) if x != y]
    if a.mech:
        m = read_csv(a.mech)
        if [r['id'] for r in m] != ids: die(f'{a.mech}: ids differ from ops.csv (set or order)')
        for k in ('r13', 'v020'):
            rep = [final_letter(r['class'], r['rule'], r['review'], read_logits(*pred[k][i])) for i, r in enumerate(m)]
            res['checks'][f'replica_vs_rwxmap_{k}'] = {'differing_rows': [{'id': i, 'replica': x, 'rwxmap': y} for i, x, y in zip(ids, rep, sp[k]) if x != y],
                                                       'replica_counts': count(rep)}
    both = res['standalone_bar']['pass'] and res['product_bar']['pass']
    res['verdict'] = 'GO' if both else 'NO-GO'
else:
    res['verdict'] = 'INCOMPLETE (standalone half only; product path needs --sp-r13 and --sp-v020)'

with open(a.out, 'x', encoding='utf-8') as f: json.dump(res, f, indent=1)
fmt = lambda c: f"{c['exact']:5d} / {c['too_loose']:3d} / {c['too_tight']:4d}"
print('path         model   exact / too loose / too tight')
for path in ('standalone', 'product'):
    for k in res[path]: print(f'{path:<12s} {k:<6s} {fmt(res[path][k])}')
print('standalone bar', res['standalone_bar'])
if 'product_bar' in res: print('product bar   ', res['product_bar'])
for k, v in res['checks'].items(): print(k, 'differing rows:', len(v['differing_rows']))
print('VERDICT:', res['verdict'])
