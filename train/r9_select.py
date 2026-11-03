"""Round 9 step 1: seeded blind sample for hand-labelling (BRIEF-v3). Selects by shape only (tier, method, mech letter, r6 label, vendor cap);
no word/regex filter. r8soft probs exist only for val + v3eval rows (not train rows), so selection is seeded random.
Run: python3 train/r9_select.py -> data/r9-hand/{blind.csv,key.csv,README.md}"""
import csv, os, random, collections
import pandas as pd
from common import *

SEED = 20261109; CAP = 40; N_LOWER = 800; N_RAISE = 400
EXAM_LOCKED = {'cloudflare','pagerduty','sentry','auth0','hubspot','zendesk','miro','dropbox','shopify','linear'}
OUTD = os.path.join(ROOT, 'data', 'r9-hand'); os.makedirs(OUTD, exist_ok=True)
opkey = lambda m, p, o: f"{str(m).upper()}|{p}|{o}"
mech = {r['id']: r for r in load_mech()}
pool = pd.concat([load_split('train'), load_split('val')], ignore_index=True)
v3 = load_split('v3eval')

gate_ids = set()
for d in ['2026-11-03', '2026-11-04', '2026-11-06', '2026-11-07']:
    gate_ids |= set(open(os.path.join(ROOT, 'data', 'gate-' + d, 'ids.txt')).read().split())
gate_keys = {opkey(mech[i]['method'], mech[i]['path'], mech[i]['operationId']) for i in gate_ids if i in mech}
v3_ids = set(v3['id']); v3_keys = {opkey(m, p, o) for m, p, o in zip(v3['method'], v3['path'], v3['operationId'])}

stats = collections.Counter(); keep = []
for r in pool.to_dict('records'):
    m = mech[r['id']]
    if m['exam'] or r['vendor'] in EXAM_LOCKED: stats['exam_or_locked'] += 1; continue
    if m['exam_opkey_overlap']: stats['exam_opkey_overlap'] += 1; continue
    k = opkey(r['method'], r['path'], r['operationId'])
    if r['id'] in gate_ids or k in gate_keys: stats['gate_id_or_opkey'] += 1; continue
    if r['id'] in v3_ids or k in v3_keys: stats['v3_tuning_id_or_opkey'] += 1; continue
    r['_k'] = k; r['_m'] = m; keep.append(r)
stats['pool'] = len(pool); stats['eligible'] = len(keep)

lower = [r for r in keep if r['tier'] == 'lower' and r['method'] == 'POST' and r['mech'] == 'x' and r['label'] in ('w', 'r')]
raise_ = [r for r in keep if r['tier'] == 'raise-wx' and r['method'] in ('PUT', 'PATCH') and r['label'] == 'w']
stats['cand_lower'] = len(lower); stats['cand_raise'] = len(raise_)
rng = random.Random(SEED); rng.shuffle(lower); rng.shuffle(raise_)
vc = collections.Counter(); seen = set(); sel = []
def take(cands, n, shape):
    got = 0
    for r in cands:
        if got == n: break
        if vc[r['vendor']] >= CAP or r['_k'] in seen: continue
        vc[r['vendor']] += 1; seen.add(r['_k']); got += 1; sel.append((shape, r))
    assert got == n, (shape, got)
take(lower, N_LOWER, 'lower-post'); take(raise_, N_RAISE, 'raise-wx-putpatch')
rng.shuffle(sel)

# assertions: exclusions hold
for shape, r in sel:
    m = r['_m']
    assert not m['exam'] and not m['exam_opkey_overlap'] and r['vendor'] not in EXAM_LOCKED
    assert r['id'] not in gate_ids and r['_k'] not in gate_keys and r['id'] not in v3_ids and r['_k'] not in v3_keys
assert max(vc.values()) <= CAP and len(sel) == N_LOWER + N_RAISE and len({r['id'] for _, r in sel}) == len(sel)

with open(os.path.join(OUTD, 'blind.csv'), 'w', newline='') as fb, open(os.path.join(OUTD, 'key.csv'), 'w', newline='') as fk:
    wb = csv.writer(fb); wk = csv.writer(fk)
    wb.writerow(['id','provider','method','path','operationId','summary','description'])
    wk.writerow(['id','ag_id','shape','vendor','method','mech','current_label','r8soft_p'])
    for i, (shape, r) in enumerate(sel, 1):
        m = r['_m']; bid = f'r9-{i:04d}'
        wb.writerow([bid, m['provider'], m['method'].upper(), m['path'], m['operationId'] or '', clean(m.get('summary'), 400), clean(m.get('description'), 800)])
        wk.writerow([bid, r['id'], shape, r['vendor'], r['method'], r['mech'], r['label'], ''])

cs = collections.Counter((s, r['method'], r['label']) for s, r in sel)
top = vc.most_common(10)
open(os.path.join(OUTD, 'README.md'), 'w').write(f"""# Round 9 hand-label sample

Purpose: rows to hand-label under BRIEF-v3 for added training weight. Targets the two shapes behind r8soft's too-loose exam rows: lower-tier POST rows the recipe lowered (mechanical x -> w/r) and raise-wx PUT/PATCH rows left at w.
Labellers see only blind.csv. key.csv (shape, vendor, current r6 label) must never be shown to them.

Selection (`train/r9_select.py`, seed {SEED}), by shape only, no word/regex filter:
- {N_LOWER} lower-tier POST rows, mechanical letter x, round-6 label w or r.
- {N_RAISE} raise-wx PUT/PATCH rows, round-6 label w.
- Pool: train.parquet + val.parquet. r8soft probabilities exist only for val and v3eval rows, not train rows, so selection is seeded random (key.csv r8soft_p is empty).
- Vendor cap {CAP} per vendor (first dotted token of provider), across the whole sample; one row per op key (METHOD|path|operationId).
- Final seeded shuffle, ids r9-0001..r9-{len(sel):04d}.

Exclusions (asserted in code): exam vendors/locked vendors and exam_opkey_overlap (already outside training), every id and every op key in gate-2026-11-03/-04/-06/-07 ids.txt, every v3 tuning truth row (id and op key, from v3eval.parquet).
Counts removed from pool of {stats['pool']}: {dict(stats)}

Counts (shape, method, current label): {dict(cs)}
Top vendors: {top}
""")
print(dict(stats)); print(dict(cs)); print(top, len(vc))
