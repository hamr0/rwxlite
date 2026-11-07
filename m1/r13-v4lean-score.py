"""Score R13 on val with rwxmap's mechanical v4 leans, variants asis / alias (docs/wiki/prereg-exam5.md, 'v4 lean names').
Definitions are m1/r13-valpick.py's: letters r < w < x, below truth = too loose, above = too tight; product path = rwxmap secondPass replica,
mode a, lower only when the top-letter p >= 0.97 on rows rwxmap sends (marker tight or loose), credential-set never lowered, p already at the candidate's T.
The mechanical letter and rule per row are rwxmap's v4 class and rule; the marker column is REQUIRED (the script stops if it is absent or has other values).
Truth is read from val.jsonl (the selection set: allowed). Pick rule (frozen): fewest too loose on the product path, then most right, ties to asis.
  python3 -I m1/r13-v4lean-score.py --val data/round13/val.jsonl --lean <lean.csv> --asis <asis.csv> --alias <alias.csv>"""
import sys, json, csv, math, argparse, collections
RANK = {'r': 0, 'w': 1, 'x': 2}; FLOOR = 1e-15; THR = 0.97
def die(m): print('r13-v4lean-score: ' + m, file=sys.stderr); sys.exit(1)
# ---- replica of rwxmap secondPass, copied from m1/r13-valpick.py ----
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

ap = argparse.ArgumentParser(); ap.add_argument('--val', required=True); ap.add_argument('--lean', required=True)
ap.add_argument('--asis', required=True); ap.add_argument('--alias', required=True); a = ap.parse_args()
val = [json.loads(l) for l in open(a.val) if l.strip()]; truth = {r['id']: r['label'] for r in val}
with open(a.lean, newline='') as f:
    rd = csv.DictReader(f)
    if rd.fieldnames is None or 'marker' not in rd.fieldnames or not {'id', 'class', 'rule'} <= set(rd.fieldnames):
        die(f'lean.csv needs the columns id,class,rule,marker; got {rd.fieldnames}')
    lean = {r['id']: r for r in rd}
if set(lean) != set(truth): die('lean ids differ from val ids')
bad = {r['marker'] for r in lean.values()} - {'settled', 'tight', 'loose'}
if bad: die(f'unknown marker values {bad}')
print(f"v4 leans: {len(lean)} rows; markers {dict(collections.Counter(r['marker'] for r in lean.values()))}")
print('rule names:', dict(collections.Counter(r['rule'] for r in lean.values()).most_common()))

def load(p):
    with open(p, newline='') as f:
        rows = list(csv.DictReader(f))
    if [r['id'] for r in rows] != [r['id'] for r in val]: die(f'{p}: ids/order differ from val')
    return {r['id']: (float(r['p_is_x']), float(r['p_changes'])) for r in rows}
res = {}
for name, p in (('asis', a.asis), ('alias', a.alias)):
    P = load(p); prod = collections.Counter(); sa = collections.Counter()
    for r in val:
        px, pc = P[r['id']]; l = lean[r['id']]; t = truth[r['id']]
        prod[outcome(final_letter(l['class'], l['rule'], l['marker'], read_logits(px, pc)), t)] += 1
        pr = (1 - pc, pc - px, px); sa[outcome('rwx'[pr.index(max(pr))], t)] += 1
    res[name] = dict(product=(prod['right'], prod['loose'], prod['tight']), standalone=(sa['right'], sa['loose'], sa['tight']))
print('\n(right / too loose / too tight)            PRODUCT (mode a, 0.97)        STANDALONE')
print('R13 with the original v3 leans (context)    3776 /  74 /  330          3967 / 162 /   51')
for n in ('asis', 'alias'):
    p, s = res[n]['product'], res[n]['standalone']
    print(f"R13 with v4 leans, {n:<5s}                   {p[0]:4d} / {p[1]:3d} / {p[2]:4d}          {s[0]:4d} / {s[1]:3d} / {s[2]:4d}")
pick = min(('asis', 'alias'), key=lambda n: (res[n]['product'][1], -res[n]['product'][0], 0 if n == 'asis' else 1))
print(f'PICK (fewest too loose on the product path, then most right, ties asis): {pick}')
