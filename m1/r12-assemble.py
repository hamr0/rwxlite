#!/usr/bin/env python3
"""Round 12 base assembly (no training, no network). Writes NEW files only into data/round12/ (gitignored).
Run from repo root: .venv/bin/python m1/r12-assemble.py
 a. round 11 train/val/v3eval, with wrong labels fixed from data/r12/jev_overruled.csv (matched to round-11 rows by op key
    provider+method+path+operationId; set label=human truth, y, status 'fresh', jev_p* None, tier 'none' = one-hot, as r11 did for exam #3 rows).
    Every change -> label-fixes.csv.
 b. exam #4 (1505 rows, data/exam4/inputs.jsonl + truth.csv): whole vendors goharbor + render -> holdout.jsonl, the other 5 -> train.
    Row schema/text identical to round 11's exam #3 rows (text asserted == fmt_text of the same fields).
 c. train/val/v3eval/holdout.jsonl, assembly-summary.json, SHA256SUMS.
"""
import collections, csv, glob, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'train')); sys.path.insert(0, HERE)
from common import fmt_text, clean, first_token, ORDER   # noqa: E402
from round10_aliases import text_rule                    # noqa: E402
D = os.path.join(REPO, 'data'); R11 = os.path.join(D, 'round11'); OUT = os.path.join(D, 'round12'); os.makedirs(OUT, exist_ok=True)
HOLD = {'goharbor', 'render'}
def fail(m): print('FAIL: ' + m, file=sys.stderr); sys.exit(1)
jl = lambda p: [json.loads(l) for l in open(p) if l.strip()]
rcsv = lambda p: list(csv.DictReader(open(p, newline='', encoding='utf-8')))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
want = dict(l.split()[::-1] for l in open(os.path.join(R11, 'assembly-sha256.txt')) if l.strip())
for s in ('train', 'val', 'v3eval'):
    if sha(os.path.join(R11, s + '.jsonl')) != want[s + '.jsonl']: fail('round11 ' + s + ' sha mismatch')
old = {s: jl(os.path.join(R11, s + '.jsonl')) for s in ('train', 'val', 'v3eval')}
final = {s: [dict(r) for r in old[s]] for s in old}
okey = lambda r: (r['provider'], r['method'].upper(), r['path'], r.get('operationId') or '')

# ---- a. label fixes
prov = {}
for f in glob.glob(os.path.join(D, 'r12', 'replay', '*', 'ops.csv')):
    for r in rcsv(f): prov[r['id']] = r['provider']
idx = collections.defaultdict(list)
for s in final:
    for r in final[s]: idx[okey(r)].append((s, r))
fixes = []; seen = set()
for x in rcsv(os.path.join(D, 'r12', 'jev_overruled.csv')):
    if x['set'] == 'exam4' or x['in_training_with_wrong_label'] != 'True': continue
    if x['id'] not in prov: fail('no provider for ' + x['id'])
    hits = idx.get((prov[x['id']], x['method'].upper(), x['path'], x['operationId'] or ''), [])
    if not hits: fail('in_training but no round11 row: ' + x['id'])
    for s, r in hits:
        if r['id'] in seen: continue
        if r['label'] == x['truth']: continue          # already the human truth (e.g. credential rows)
        seen.add(r['id'])
        fixes.append({'id': r['id'], 'split': s, 'old': r['label'], 'new': x['truth'], 'source': f"{x['set']}:{x['id']} human truth (r12 jev_overruled.csv)"})
        r.update(label=x['truth'], y=ORDER[x['truth']], status='fresh', jev_p=None, jev_pC=None, jev_pA=None, jev_pB=None, tier='none')
with open(os.path.join(OUT, 'label-fixes.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, ['id', 'split', 'old', 'new', 'source']); w.writeheader(); w.writerows(fixes)

# ---- b. exam #4
inp = jl(os.path.join(D, 'exam4', 'inputs.jsonl')); truth = {r['id']: r['label'] for r in rcsv(os.path.join(D, 'exam4', 'truth.csv'))}
if len(inp) != 1505 or set(truth) != {o['id'] for o in inp}: fail('exam4 inputs/truth mismatch')
new = []
for o in inp:
    lean = {'class': o['class'], 'rule': text_rule(o['rule']), 'method': o['method'], 'path': o['path'], 'operationId': o['operationId'], 'summary': o['summary'], 'description': o['description']}
    if fmt_text(lean) != o['text']: fail('text differs for ' + o['id'])
    new.append({'id': o['id'], 'text': o['text'], 'label': truth[o['id']], 'y': ORDER[truth[o['id']]], 'status': 'fresh', 'jev_p': None, 'jev_pC': None, 'summary': clean(o['summary'], 200),
                'jev_pA': None, 'jev_pB': None, 'mech': o['class'], 'rule': o['rule'], 'tier': 'none', 'method': o['method'].upper(), 'provider': o['provider'],
                'vendor': first_token(o['provider']), 'path': o['path'], 'operationId': o['operationId']})
if set(new[0]) != set(old['train'][0]): fail('schema differs')
hold = [r for r in new if r['vendor'] in HOLD]; add = [r for r in new if r['vendor'] not in HOLD]
final['train'] += add; final['holdout'] = hold

# ---- asserts
allrows = [(s, r) for s in final for r in final[s]]
c = collections.Counter(r['id'] for _, r in allrows)
if [i for i, n in c.items() if n > 1]: fail('duplicate ids')
spl = collections.defaultdict(set)
for s, r in allrows: spl[okey(r)].add(s)
if [k for k, v in spl.items() if len(v) > 1]: fail('op-key groups span splits')
vend = {s: {r['vendor'] for r in final[s]} for s in final}
for a in ('train', 'val', 'v3eval'):
    if vend['holdout'] & vend[a]: fail('holdout vendor in ' + a)
if {r['vendor'] for r in hold} != HOLD: fail('holdout vendors')
if any(r['label'] not in ORDER or r['y'] != ORDER[r['label']] for _, r in allrows): fail('label/y')
if any('credential-set' in r['text'] for _, r in allrows): fail('credential-set in text')
for s in ('train', 'val', 'v3eval'):   # only fixed rows differ
    fx = {f['id'] for f in fixes if f['split'] == s}
    base = old[s]
    if [r for r, o in zip(final[s], base) if r != o and r['id'] not in fx]: fail('unexpected change in ' + s)
    if len(final[s]) < len(base): fail('rows lost in ' + s)

# ---- write
for s in final:
    with open(os.path.join(OUT, s + '.jsonl'), 'w') as f:
        for x in final[s]: f.write(json.dumps(x) + '\n')
lab = lambda rows: dict(sorted(collections.Counter(r['label'] for r in rows).items()))
def src(r): return 'exam4' if r['id'].startswith('ex4-') else 'exam3' if r['id'].startswith('ex3-') else 'r11-fixed' if r['id'] in seen else 'r11-base'
summ = {'round11_sha256': {k: v for k, v in want.items() if k.endswith('.jsonl')}, 'counts': {s: len(final[s]) for s in final},
        'label_per_split': {s: lab(final[s]) for s in final},
        'source_per_split': {s: dict(sorted(collections.Counter(src(r) for r in final[s]).items())) for s in final},
        'label_per_split_source': {s: {k: lab([r for r in final[s] if src(r) == k]) for k in sorted({src(r) for r in final[s]})} for s in final},
        'label_fixes': len(fixes), 'label_fixes_by_split': dict(collections.Counter(f['split'] for f in fixes)),
        'label_fixes_by_source_set': dict(collections.Counter(f['source'].split(':')[0] for f in fixes)),
        'label_fixes_by_split_and_set': {f'{s}/{k}': n for (s, k), n in sorted(collections.Counter((f['split'], f['source'].split(':')[0]) for f in fixes).items())},
        'label_fixes_old_to_new': dict(collections.Counter(f"{f['old']}->{f['new']}" for f in fixes)),
        'exam4_added_train': {'rows': len(add), 'by_vendor': dict(collections.Counter(r['vendor'] for r in add)), 'labels': lab(add)},
        'holdout': {'rows': len(hold), 'by_vendor': dict(collections.Counter(r['vendor'] for r in hold)), 'by_vendor_label': {v: lab([r for r in hold if r['vendor'] == v]) for v in sorted(HOLD)}},
        'asserts': ['no duplicate ids', 'no op-key group spans splits', 'holdout vendors disjoint from train/val/v3eval', 'exam4 text == fmt_text (r11 builder)', 'only fixed rows differ from round 11']}
json.dump(summ, open(os.path.join(OUT, 'assembly-summary.json'), 'w'), indent=1, sort_keys=True)
names = [s + '.jsonl' for s in ('train', 'val', 'v3eval', 'holdout')] + ['assembly-summary.json', 'label-fixes.csv']
open(os.path.join(OUT, 'SHA256SUMS'), 'w').write(''.join(f'{sha(os.path.join(OUT, n))}  {n}\n' for n in names))
print(json.dumps(summ, indent=1, sort_keys=True))
