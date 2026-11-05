#!/usr/bin/env python3
"""Round 12 seed list for variants (no training, no model call). Reads data/round12/*.jsonl (from m1/r12-assemble.py), data/r12/replay/*, data/exam4/*,
and rwxmap's replay rows (read-only). Writes data/round12/seeds.csv and seeds-summary.md. Run: .venv/bin/python m1/r12-seeds.py
Quantity the 0.97 lowering rule reads (rwxmap src/secondpass.js readAnswer + LOWER_MIN_P): the TOP-LETTER share of the calibrated 3-way distribution,
p(x)=pIsX, p(w)=pChanges-pIsX, p(r)=1-pChanges; letter = argmax (ties x>w>r); p = that letter's share. A lowering is accepted iff p >= 0.97.
"""
import collections, csv, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
D = os.path.join(REPO, 'data'); OUT = os.path.join(D, 'round12')
RW = os.environ.get('RWXMAP', '/home/hamr/PycharmProjects/rwxmap')
RK = {'r': 0, 'w': 1, 'x': 2}
jl = lambda p: [json.loads(l) for l in open(p) if l.strip()]
rcsv = lambda p: list(csv.DictReader(open(p, newline='', encoding='utf-8')))
vend = lambda p: __import__('re').split(r'[.:]', str(p or '').lower())[0]
V = {s: {r['vendor'] for r in jl(os.path.join(OUT, s + '.jsonl'))} for s in ('train', 'val', 'v3eval', 'holdout')}
BAD = V['holdout'] | V['val'] | V['v3eval']
SETS = {'exam-2026-11-03-fresh': 'fresh', 'gate-2026-11-03': 'gate1', 'gate-2026-11-04': 'gate2', 'gate-2026-11-06': 'gate3', 'gate-2026-11-07': 'gate4', 'r9-hand': 'r9hand'}
def letter(p):
    px = p['pIsX']; pw = p['pChanges'] - px; pr = 1 - p['pChanges']
    if px >= pw and px >= pr: return 'x', px, pr, pw, px
    if pw >= pr: return 'w', pw, pr, pw, px
    return 'r', pr, pr, pw, px
rows = []   # unified
for name, short in SETS.items():
    rp = os.path.join(RW, 'poc', 'replay-r12', 'out', f'rows-{name}.csv'); ops = {r['id']: r for r in rcsv(os.path.join(D, 'r12', 'replay', name, 'ops.csv'))}
    inp = {r['id']: r for r in jl(os.path.join(D, 'r12', 'inputs', short, 'inputs.jsonl'))}; P = {r['id']: r for r in jl(os.path.join(D, 'r12', 'replay', name, 'p-v020-fp32.jsonl'))}
    for r in rcsv(rp):
        rows.append({'set': name, **r, 'operationId': ops[r['id']]['operationId'], 'summary': ops[r['id']]['summary'], 'rule': inp[r['id']]['rule'], 'p': P[r['id']]})
mech4 = {r['id']: r for r in rcsv(os.path.join(RW, 'data', 'exam4-2026-11-04', 'score', 'rows-mech.csv'))}
in4 = {r['id']: r for r in jl(os.path.join(D, 'exam4', 'inputs.jsonl'))}; P4 = {r['id']: r for r in jl(os.path.join(D, 'exam4', 'p-v020-fp32.jsonl'))}
for r in rcsv(os.path.join(RW, 'data', 'exam4-2026-11-04', 'score', 'rows-a-fp32-base.csv')):
    m = mech4[r['id']]; i = in4[r['id']]
    rows.append({'set': 'exam4', **r, 'mech_letter': m['letter'], 'mech_review': m['review'], 'operationId': i['operationId'], 'summary': i['summary'], 'rule': i['rule'], 'p': P4[r['id']]})
for r in rows:
    r['vendor'] = vend(r['provider']); r['ml'], r['p_top'], r['pr'], r['pw'], r['px'] = letter(r['p'])
dropped = collections.Counter()
def ok(r, cat):
    if r['vendor'] in BAD: dropped[(cat, 'heldout/val/v3eval vendor')] += 1; return False
    if r['vendor'] not in V['train']: dropped[(cat, 'vendor not in train')] += 1; return False
    return True
seeds = []; used = set()
def add(r, cat, note):
    k = (r['set'], r['id'])
    if k in used: return
    used.add(k); seeds.append({'set': r['set'], 'id': r['id'], 'provider': r['provider'], 'method': r['method'], 'path': r['path'], 'operationId': r['operationId'], 'summary': r['summary'],
                               'truth': r['truth'], 'model_letter': r['ml'], 'p_top': round(r['p_top'], 4), 'category': cat, 'note': note})
# leak: model moved the letter below truth (evidence rwxlite, letter < truth)
NAMED = {'gate3-0482', 'r9-0543', 'r9-0814', 'r9-0897', 'r9-1109', 'r9-1164'}
leaks = [r for r in rows if r['evidence'] == 'rwxlite' and RK[r['letter']] < RK[r['truth']]]
print('leak candidates', len(leaks), 'named found', sorted(NAMED & {r['id'] for r in leaks}), file=sys.stderr)
for r in leaks:
    if ok(r, 'leak'): add(r, 'leak', f"cli {r['letter']} via model (mech {r['mech_letter']}/{r['mech_review']}, rule {r['rule']}); " + ('rwxmap-named' if r['id'] in NAMED else 'exam4 model-lowered'))
# raise_miss: sent (loose), floor letter w, truth x, evidence floor (not raised)
miss = [r for r in rows if r['evidence'] == 'floor' and r['mech_review'] == 'loose' and r['letter'] == 'w' and r['truth'] == 'x' and r['method'] in ('PUT', 'PATCH')]
for r in miss:
    if ok(r, 'raise_miss'): add(r, 'raise_miss', f"{r['method']} floor w loose, truth x, not raised (rule {r['rule']}; model said {r['ml']} {r['p_top']:.2f})")
# unsure_right: tight, model top letter == truth, lower than mech letter, p_top in [0.80, 0.97)
ur_all = [r for r in rows if r['mech_review'] == 'tight' and r['ml'] == r['truth'] and RK[r['ml']] < RK[r['mech_letter']] and 0.80 <= r['p_top'] < 0.97]
ur = [r for r in ur_all if ok(r, 'unsure_right')]
def stratum(r):
    t = (r['summary'] + ' ' + r['operationId'] + ' ' + r['path']).lower()
    if r['method'] == 'POST' and any(w in t for w in ('search', 'query', 'list', 'find', 'get', 'read', 'fetch', 'lookup', 'filter', 'count', 'check', 'validate')): return 'POST search/read'
    if r['method'] == 'POST' and any(w in t for w in ('update', 'edit', 'modify', 'set', 'patch', 'rename', 'change')): return 'POST update'
    if any(w in t for w in ('archive', 'restore', 'enable', 'disable', 'activate', 'deactivate', 'pause', 'resume', 'cancel', 'start', 'stop', 'publish', 'unpublish', 'close', 'reopen', 'lock', 'unlock')): return f"{r['method']} reversible lifecycle"
    return f"{r['method']} other"
strata = collections.defaultdict(list)
for r in sorted(ur, key=lambda r: (r['set'], r['id'])): r['stratum'] = stratum(r); strata[r['stratum']].append(r)
pick = []; q = {k: list(v) for k, v in sorted(strata.items())}
while len(pick) < 150 and any(q.values()):
    for k in sorted(q):
        if q[k] and len(pick) < 150: pick.append(q[k].pop(0))
for r in pick: add(r, 'unsure_right', f"tight->{r['ml']} at p={r['p_top']:.2f} (mech {r['mech_letter']}); stratum: {r['stratum']}")
with open(os.path.join(OUT, 'seeds.csv'), 'w', newline='') as f:
    cols = ['seed_id', 'set', 'id', 'provider', 'method', 'path', 'operationId', 'summary', 'truth', 'model_letter', 'p_top', 'category', 'note']
    w = csv.DictWriter(f, cols); w.writeheader()
    for i, s in enumerate(seeds, 1): w.writerow({'seed_id': f'r12s-{i:04d}', **s})
cnt = collections.Counter(s['category'] for s in seeds)
L = ['# Round 12 seeds', '', f'Script: `m1/r12-seeds.py`. Total {len(seeds)} seeds -> `seeds.csv`.', '',
     '**0.97 rule quantity** (rwxmap `src/secondpass.js`, `readAnswer` + `LOWER_MIN_P = 0.97`): the **top-letter share** of the calibrated distribution (p(x)=pIsX, p(w)=pChanges-pIsX, p(r)=1-pChanges; letter = argmax, ties x>w>r; p = that letter\'s share). A lowering is accepted iff that share >= 0.97 (not pChanges- or pIsX-based). `p_top` in seeds.csv is this quantity.', '',
     '## Seeds per category', '', '| category | seeds | candidates before vendor filter / cap |', '|---|---|---|',
     f"| leak | {cnt['leak']} | {len(leaks)} |", f"| raise_miss | {cnt['raise_miss']} | {len(miss)} |", f"| unsure_right | {cnt['unsure_right']} | {len(ur_all)} ({len(ur)} after vendor filter, capped 150) |", '',
     '## unsure_right strata (picked / available)', '', '| stratum | picked | available |', '|---|---|---|']
pc = collections.Counter(r['stratum'] for r in pick)
for k in sorted(strata): L.append(f'| {k} | {pc[k]} | {len(strata[k])} |')
L += ['', '## Dropped by vendor filter', '', 'Excluded vendors: holdout (goharbor, render) + every val/v3eval vendor; also dropped if the vendor is not in round12 train.', '', '| category | reason | rows |', '|---|---|---|']
for (c, why), n in sorted(dropped.items()): L.append(f'| {c} | {why} | {n} |')
L += ['', '## Seeds per category per set', '', '| category | set | seeds |', '|---|---|---|']
for (c, st), n in sorted(collections.Counter((s['category'], s['set']) for s in seeds).items()): L.append(f'| {c} | {st} | {n} |')
L += ['', 'Excluded by design: GET floor r with truth w/x (never sent) and settled list rows (no model can fix). Each row is a seed once (priority leak > raise_miss > unsure_right).',
      'unsure_right = mech review tight, model top letter == truth and below the mech letter (the lowering case the 0.97 rule decides), p_top in [0.80, 0.97). Strata are keyword heuristics on summary/operationId/path; round-robin across strata.']
open(os.path.join(OUT, 'seeds-summary.md'), 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
