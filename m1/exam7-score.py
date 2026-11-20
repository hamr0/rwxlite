"""Exam #7 scorer (docs/wiki/prereg-r15.md section 8). Run ONCE, only after the predictions' sha256s are committed and truth.csv is shared. Standard library only.
  python3 -I m1/exam7-score.py --ops OPS.csv --truth TRUTH.csv --truth-sha256 HEX --pred-r15 predictions-r15.csv --pred-r13 predictions-r13.csv --sha-list docs/wiki/exam7-predictions.sha256 \
      --model-r15 STR --model-r13 STR --sp-r15 secondpass-r15-a090.csv --sp-r13 secondpass-r13-a090.csv --out results.json \
      [--sp-r15-b85 F --sp-r15-b90 F --sp-r13-b85 F --sp-r13-b90 F] [--mech lean.csv]
DECISION (D135, frozen in the prereg): the candidate R15 replaces shipped R13 (rwxlite 0.3.1) only if, on the PRODUCT path (rwxmap's real CLI secondPass, mode a, LOWER_MIN_P 0.90 = D139, run by rwxmap on our
prediction CSVs; its per-row letters come in --sp-* files with columns id,letter), R15 has NO MORE too-loose AND NO FEWER exact than R13. Equal counts pass. Nothing else decides.
Information only: standalone argmax (no mechanical letter), mode b at confidence 85 and 90 (--sp-*-b85/-b90), and a replica of mode a at 0.90 (--mech) that lists every row where it differs from rwxmap.
Letters are ordered r < w < x; a letter below the truth is too loose, above is too tight. Refuses unless: truth sha256 equals --truth-sha256, prediction files match --sha-list, ids equal ops.csv's in the same
order in every file, the model strings are the ones given, and --out does not exist (scored once)."""
import sys, os, csv, json, math, hashlib, argparse, collections
RANK = {'r': 0, 'w': 1, 'x': 2}; FLOOR = 1e-15; CUT = 0.90
def read_logits(px, pc):
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
    Lt, p = read_answer(z)
    if Lt == M: return M
    if RANK[Lt] > RANK[M]: return Lt
    if rule != 'credential-set' and p >= CUT: return Lt
    return 'x'
def outcome(f, t):
    d = RANK[f] - RANK[t]; return 'right' if d == 0 else ('loose' if d < 0 else 'tight')
def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def die(m): print('exam7-score: ' + m, file=sys.stderr); sys.exit(1)
def read_csv(p):
    with open(p, newline='', encoding='utf-8') as f: return list(csv.DictReader(f))
ap = argparse.ArgumentParser()
for k in ('ops', 'truth', 'truth-sha256', 'pred-r15', 'pred-r13', 'sha-list', 'model-r15', 'model-r13', 'sp-r15', 'sp-r13', 'out'): ap.add_argument('--' + k, required=True)
for k in ('sp-r15-b85', 'sp-r15-b90', 'sp-r13-b85', 'sp-r13-b90', 'mech'): ap.add_argument('--' + k)
a = ap.parse_args()
if os.path.exists(a.out): die(f'{a.out} exists: the exam is scored once')
if sha_file(a.truth) != a.truth_sha256: die(f'truth sha256 {sha_file(a.truth)} != --truth-sha256')
listed = {}
for line in open(a.sha_list, encoding='utf-8'):
    if line.strip(): h, n = line.split(None, 1); listed[os.path.basename(n.strip())] = h
for p in (a.pred_r15, a.pred_r13):
    if listed.get(os.path.basename(p)) != sha_file(p): die(f'{os.path.basename(p)}: sha256 does not match {a.sha_list}')
ops = read_csv(a.ops); ids = [r['id'] for r in ops]
if len(set(ids)) != len(ids): die('duplicate id in ops.csv')
trows = read_csv(a.truth)
if [r['id'] for r in trows] != ids: die('truth.csv ids differ from ops.csv (set or order)')
truth = [r['label'] for r in trows]
if any(t not in RANK for t in truth): die('truth label outside r/w/x')
EXPECT = {'r15': a.model_r15, 'r13': a.model_r13}
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
pred = {k: load_pred(p, k) for k, p in (('r15', a.pred_r15), ('r13', a.pred_r13))}
def count(letters):
    c = collections.Counter(outcome(f, t) for f, t in zip(letters, truth))
    return {'exact': c['right'], 'too_loose': c['loose'], 'too_tight': c['tight'], 'n': len(truth)}
def load_letters(p):
    rows = read_csv(p)
    if [r['id'] for r in rows] != ids: die(f'{p}: ids differ from ops.csv (set or order)')
    L = [r['letter'].strip() for r in rows]
    if any(x not in RANK for x in L): die(f'{p}: letter outside r/w/x')
    return L
def sa(px, pc):
    v = [1 - pc, pc - px, px]; return 'rwx'[v.index(max(v))]
res = {'rows': len(ids), 'truth_sha256': a.truth_sha256, 'models': EXPECT, 'decision_path': 'product, rwxmap CLI secondPass mode a, LOWER_MIN_P 0.90 (D139)', 'standalone_info': {}, 'product': {}, 'info_mode_b': {}, 'checks': {}}
for k in ('r15', 'r13'): res['standalone_info'][k] = count([sa(*p) for p in pred[k]])
sp = {k: load_letters(p) for k, p in (('r15', a.sp_r15), ('r13', a.sp_r13))}
for k in sp: res['product'][k] = count(sp[k])
for tag in ('b85', 'b90'):
    for k in ('r15', 'r13'):
        f = getattr(a, f'sp_{k}_{tag}')
        if f: res['info_mode_b'].setdefault(tag, {})[k] = count(load_letters(f))
r, b = res['product']['r15'], res['product']['r13']
res['bar'] = {'too_loose_ok': r['too_loose'] <= b['too_loose'], 'exact_ok': r['exact'] >= b['exact'], 'pass': r['too_loose'] <= b['too_loose'] and r['exact'] >= b['exact']}
res['product_too_loose_rows'] = {k: [{'id': i, 'truth': t, 'got': g} for i, t, g in zip(ids, truth, sp[k]) if outcome(g, t) == 'loose'] for k in sp}
res['product_differing_rows'] = [{'id': i, 'truth': t, 'r15': x, 'r13': y} for i, t, x, y in zip(ids, truth, sp['r15'], sp['r13']) if x != y]
if a.mech:
    m = read_csv(a.mech)
    if [r_['id'] for r_ in m] != ids: die(f'{a.mech}: ids differ from ops.csv (set or order)')
    for k in ('r15', 'r13'):
        rep = [final_letter(r_['class'], r_['rule'], r_.get('marker', r_.get('review')), read_logits(*pred[k][i])) for i, r_ in enumerate(m)]
        res['checks'][f'replica_vs_rwxmap_{k}'] = {'differing_rows': [{'id': i, 'replica': x, 'rwxmap': y} for i, x, y in zip(ids, rep, sp[k]) if x != y], 'replica_counts': count(rep)}
res['verdict'] = 'GO (R15 may replace R13; release is still the user\'s decision)' if res['bar']['pass'] else 'NO-GO (R13 stays)'
with open(a.out, 'x', encoding='utf-8') as f: json.dump(res, f, indent=1)
fmt = lambda c: f"{c['exact']:5d} / {c['too_loose']:3d} / {c['too_tight']:4d}"
print('path          model  exact / too loose / too tight')
for k in ('r15', 'r13'): print(f'product a.90  {k:<5s} {fmt(res["product"][k])}')
for k in ('r15', 'r13'): print(f'standalone    {k:<5s} {fmt(res["standalone_info"][k])}   (info)')
for tag, d in res['info_mode_b'].items():
    for k, c in d.items(): print(f'mode {tag}      {k:<5s} {fmt(c)}   (info)')
print('bar', res['bar']);
for k, v in res['checks'].items(): print(k, 'differing rows:', len(v['differing_rows']))
print('VERDICT:', res['verdict'])
