"""Vendor labels step A, part 3: agreement tables and candidate dangerous mistakes. Reads data/vendor/{joined.jsonl,mech.json,logits.jsonl}.
  python3 -I vendor/report.py <vendor-dir>
secondPass replica below is copied from the calibration scratch lib (verified row-for-row against rwxmap's CLI on 9 sets): shipped T 0.844, lowering line p >= 0.97, credential-set never lowered."""
import sys, os, json, math, csv, collections, random
V = sys.argv[1]; T0 = 0.844; THR = 0.97; RANK = {'r': 0, 'w': 1, 'x': 2}; FLOOR = 1e-15
jl = lambda f: [json.loads(l) for l in open(f) if l.strip()]
def read_logits(px, pc):
    p = [max(1 - pc, FLOOR), max(pc - px, FLOOR), max(px, FLOOR)]; return [T0 * math.log(v) for v in p]
def probs(z, T):
    s = [v / T for v in z]; m = max(s); e = [math.exp(v - m) for v in s]; t = sum(e); return [v / t for v in e]
def read_answer(z, T):
    pr, pw, px = probs(z, T); pc = pw + px; pr2 = 1 - pc; pw2 = pc - px
    if px >= pw2 and px >= pr2: return ('x', px)
    if pw2 >= pr2: return ('w', pw2)
    return ('r', pr2)
def final_letter(M, rule, review, z, T, thr):
    if review not in ('loose', 'tight'): return M
    Lt, p = read_answer(z, T)
    if Lt == M: return M
    if RANK[Lt] > RANK[M]: return Lt
    if rule != 'credential-set' and p >= thr: return Lt
    return 'x'
J = jl(os.path.join(V, 'joined.jsonl')); M = json.load(open(os.path.join(V, 'mech.json')))['v']; LG = {x['key']: x['logits'] for x in jl(os.path.join(V, 'logits.jsonl'))}
import hashlib
for j, m in zip(J, M):
    assert j['id'] == m['id']; j['M'] = m['cls']; j['rule'] = m['rule']; j['review'] = m['review']
meta = json.load(open(os.path.join(V, 'predict-meta.json')))
# keys: recompute text hash exactly as predict.py did (text stored? no) -> predict.py wrote j['text'] only in memory; rebuild here
sys.path.append(os.path.expanduser('~/.local/lib/python3.14/site-packages')); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'train'))
from common import fmt_text
for j in J:
    r = {'class': j['M'], 'rule': {'credential-set': 'cant-undo-verb'}.get(j['rule'], j['rule']), 'method': 'GET' if j['method'].upper() == 'QUERY' else j['method'], 'path': j['path'], 'operationId': j['operationId'], 'summary': j['summary'], 'description': j['description']}
    L = LG[hashlib.sha1(fmt_text(r).encode()).hexdigest()]; z = [v for v in L]; P = probs(z, T0)   # logits / T0 softmax = calibrated p
    k = max(range(3), key=lambda i: P[i]); j['top'] = 'rwx'[k]; j['top_p'] = P[k]; j['p'] = P
    zz = read_logits(P[2], P[1] + P[2]); j['final'] = final_letter(j['M'], j['rule'], j['review'], zz, T0, THR)
    j['prot'] = bool(j['protected'] or j['corpus_flags'])
    j['cat'] = 'protected' if j['prot'] else ('v3eval' if j['split'] == 'v3eval' else 'plain')
HINTRANK = {'r': 0, 'w': 1, 'notr': 1, 'x': 2}
def below(letter, hint):  # letter lower than the vendor hint
    if letter is None: return None
    return RANK[letter] < HINTRANK[hint] if hint != 'w' else RANK[letter] < 1
def above(letter, hint):
    if letter is None: return None
    return RANK[letter] > {'r': 0, 'w': 1}[hint] if hint in ('r', 'w') else False
# dedupe: one row per (dedupe_key, protected) group, first row; the full row count is reported alongside
seen = set(); U = []
for j in J:
    k = (j['dedupe_key'], j['prot'])
    if k not in seen: seen.add(k); U.append(j)
for j in J: j['teacher_or_train'] = j['train_label'] or j['v3_label'] or j['teacher']
SRC = ('M', 'teacher', 'train_label', 'top', 'final')
out = []; P = lambda *a: out.append(' '.join(str(x) for x in a))
def pct(a, b): return f'{100 * a / b:.1f}%' if b else '-'
def table(rows, group, title):
    P(f'\n### {title}'); P('| group | rows | unique | letters mech r/w/x | final r/w/x | below hint: mech | teacher | train label | 0.2.0 top | final | above hint: final |'); P('|---|---|---|---|---|---|---|---|---|---|---|')
    G = collections.defaultdict(list)
    for j in rows: G[group(j)].append(j)
    for g in sorted(G, key=str):
        rs = G[g]; h = rs[0]['hint']; u = [j for j in rs]; n = len(u)
        dist = lambda f: '/'.join(str(sum(1 for j in u if j[f] == l)) for l in 'rwx')
        def bl(f):
            xs = [j for j in u if j[f] is not None]; return f"{sum(1 for j in xs if below(j[f], j['hint']))}/{len(xs)}" if h != 'conflict' else '-'
        ab = sum(1 for j in u if above(j['final'], j['hint'])) if h in ('r', 'w') else '-'
        P(f'| {g} | {sum(1 for j in J if group(j) == g and j["cat"] == rs[0]["cat"])} | {n} | {dist("M")} | {dist("final")} | {bl("M")} | {bl("teacher")} | {bl("train_label")} | {bl("top")} | {bl("final")} | {ab} |')
for cat in ('plain', 'v3eval', 'protected'):
    R = [j for j in U if j['cat'] == cat]
    P(f'\n## Category: {cat} ({len(R)} unique rows; {sum(1 for j in J if j["cat"] == cat)} joined rows)')
    P('Counts are unique endpoints (AWS: service+action; GitHub: method+normalised path). Columns "below hint" are n_below/n_with_label (hint r: nothing is below; hint w: letter r; hint notr: letter r; hint x: letter r or w).')
    for src in ('aws', 'github'):
        table([j for j in R if j['source'] == src], lambda j: f"{src}:{j['vendor_level']}" + (f"->{j['hint']}" if src == 'aws' else '') + ('' if src == 'aws' else f"->{j['hint']}{('/' + j['hint_sub']) if j['hint_sub'] else ''}"), f'{src} by vendor level -> hint ({cat})')
        table([j for j in R if j['source'] == src], lambda j: j['hint'], f'{src} by hint class ({cat})')
# candidate dangerous mistakes: hint x/notr, a letter below the hint
def cand(j):
    if j['hint'] not in ('x', 'notr'): return None
    k = []
    if below(j['final'], j['hint']): k.append('final')
    if below(j['train_label'], j['hint']): k.append('train_label')
    if below(j['teacher'], j['hint']): k.append('teacher')
    if below(j['top'], j['hint']): k.append('top')
    if below(j['M'], j['hint']): k.append('mech')
    return k or None
C = [j for j in U if cand(j) and j['cat'] != 'protected']; CP = [j for j in U if cand(j) and j['cat'] == 'protected']
def origin(j):
    if not below(j['final'], j['hint']): return 'only-teacher-or-model-top (final ok)'
    if RANK[j['final']] < RANK[j['M']]: return 'model lowered mech (0.2.0)'
    return 'mech own leak (model did not raise)'
P('\n## Candidate dangerous mistakes (hint x or notr, some letter below the hint); protected rows listed separately')
for name, rows in (('non-protected', C), ('protected (exam/gate/holdout/r9-hand overlap)', CP)):
    P(f'\n### {name}: {len(rows)} unique rows')
    for k in ('final', 'train_label', 'teacher', 'top', 'mech'):
        P(f'- {k} below hint: ' + ', '.join(f'{src}/{h}: {sum(1 for j in rows if j["source"] == src and j["hint"] == h and k in cand(j))}' for src in ('aws', 'github') for h in ('x', 'notr')))
    fin = [j for j in rows if 'final' in cand(j)]
    P('- final below hint, by origin: ' + str(dict(collections.Counter(origin(j) for j in fin))))
    P('- final below hint, hint x only, by origin: ' + str(dict(collections.Counter(origin(j) for j in fin if j['hint'] == 'x'))))
    P('- final below hint with model confident (top_p >= 0.97): ' + str(sum(1 for j in fin if j['top_p'] >= THR)))
P('\n### Top AWS services among non-protected rows with final below hint x/notr')
for s, n in collections.Counter(j['iam_prefix'] for j in C if j['source'] == 'aws' and 'final' in cand(j)).most_common(15): P(f'- {s}: {n}')
P('\n### GitHub areas among non-protected rows with final below hint')
for s, n in collections.Counter(j['vendor_area'] for j in C if j['source'] == 'github' and 'final' in cand(j)).most_common(15): P(f'- {s}: {n}')
# reverse: vendor says r, we say w/x
RV = [j for j in U if j['hint'] == 'r' and j['cat'] != 'protected']
P(f'\n## Reverse: vendor read/list but a letter above r (non-protected, unique): {len(RV)} vendor-r rows')
for k in ('M', 'teacher', 'train_label', 'top', 'final'):
    xs = [j for j in RV if j[k] is not None]; P(f'- {k} above r: ' + ', '.join(f"{src} {sum(1 for j in xs if j['source'] == src and j[k] != 'r')}/{sum(1 for j in xs if j['source'] == src)}" for src in ('aws', 'github')))
P('\n## v3eval rows (hand truth, not used in training): vendor hint vs truth letter, unique endpoints')
VR = [j for j in U if j['cat'] == 'v3eval']
for h in ('r', 'notr', 'x'):
    xs = [j for j in VR if j['hint'] == h]; P(f'- hint {h}: n={len(xs)}; truth r/w/x = ' + '/'.join(str(sum(1 for j in xs if j['v3_label'] == l)) for l in 'rwx') + f'; final r/w/x = ' + '/'.join(str(sum(1 for j in xs if j['final'] == l)) for l in 'rwx'))
# examples
rnd = random.Random(20261105)
def pick(rows, n):
    rows = sorted(rows, key=lambda j: j['id']); rnd.shuffle(rows); seenp = set(); res = []
    for j in rows:
        g = (j['source'], j['iam_prefix'] or j['vendor_area'])
        if g in seenp: continue
        seenp.add(g); res.append(j)
        if len(res) == n: break
    return res
fin = [j for j in C if 'final' in cand(j)]
ex = pick([j for j in fin if origin(j).startswith('model')], 10) + pick([j for j in fin if origin(j).startswith('mech own') and j['hint'] == 'x'], 10) + pick([j for j in C if 'final' not in cand(j) and ('teacher' in cand(j) or 'train_label' in cand(j))], 10)
def row(j): return {'source': j['source'], 'provider': j['provider'], 'method': j['method'], 'path': j['path'], 'operationId': j['operationId'], 'summary': j['summary'][:100], 'vendor_level': j['vendor_level'], 'vendor_area': j['vendor_area'], 'hint': j['hint'],
                    'mech': j['M'], 'rule': j['rule'], 'jev_p': j['jev_p'], 'teacher': j['teacher'], 'train_label': j['train_label'], 'top': j['top'], 'top_p': round(j['top_p'], 3), 'final': j['final'], 'origin': origin(j) if 'final' in (cand(j) or []) else 'teacher/train only', 'split': j['split'], 'id': j['id']}
P('\n## 30 representative examples (10 model lowered, 10 mech own leak with hint x, 10 teacher/train label lower while final is fine)')
P('| # | source | method | path | operationId | summary | vendor | hint | mech | Jev p | teacher | train | 0.2.0 top (p) | final |'); P('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for i, j in enumerate(ex, 1): P(f"| {i} | {j['source']} | {j['method']} | {j['path'][:70]} | {j['operationId'][:40]} | {j['summary'][:60].replace('|', '/')} | {j['vendor_level']} {j['iam_prefix'] or j['vendor_area'][:30]} | {j['hint']} | {j['M']} ({j['rule']}) | {j['jev_p']} | {j['teacher']} | {j['train_label']} | {j['top']} ({j['top_p']:.2f}) | {j['final']} |")
open(os.path.join(V, 'report.md'), 'w').write('\n'.join(out) + '\n')
for name, rows in (('candidates.csv', C + CP), ('examples30.csv', ex), ('reverse-r-vs-wx.csv', [j for j in RV if j['final'] != 'r' or j['teacher'] not in (None, 'r')])):
    rs = [row(j) | {'cat': j['cat'], 'protected_in': ';'.join(j['protected'] + j['corpus_flags'])} for j in rows]
    with open(os.path.join(V, name), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0])); w.writeheader(); w.writerows(rs)
with open(os.path.join(V, 'all-rows.csv'), 'w', newline='') as f:
    rs = [row(j) | {'cat': j['cat'], 'dedupe_key': j['dedupe_key'], 'review': j['review']} for j in J]; w = csv.DictWriter(f, fieldnames=list(rs[0])); w.writeheader(); w.writerows(rs)
print('\n'.join(out))
