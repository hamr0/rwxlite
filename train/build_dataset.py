"""ROUND-6 recipe (m0/parity.mjs ROUND6 block / m0/gate-score.mjs label2): cuts lower 0.20, raise-wx 0.60, raise-get 0.20; POST x rows
lowered by isX get r if POST-changes p (avg of data/m0/jev-post-changes{,-2}.jsonl) < 0.20 else w; narrow credential rule -> x; DELETE x.
Build train/val/v3-eval sets -> data/train/{train,val,v3eval}.jsonl (+ .parquet).
Run: python3 train/build_dataset.py
Never reads the exam, gate labels-*.csv. Excludes ids in data/gate-2026-11-03/ids.txt.
"""
import csv, json, os, random, sys, collections
import pandas as pd
from common import *

RWXMAP = os.environ.get('RWXMAP_DIR', os.path.abspath(os.path.join(ROOT, '..', 'rwxmap')))
SEED = 20261103
EXAM_LOCKED = {'cloudflare','pagerduty','sentry','auth0','hubspot','zendesk','miro','dropbox','shopify','linear'}
mech = load_mech()
gate_ids = set(open(os.path.join(ROOT, 'data/gate-2026-11-03/ids.txt')).read().split()) | set(open(os.path.join(ROOT, 'data/gate-2026-11-04/ids.txt')).read().split())  # ids.txt only; labels never read
def readj(p): return [json.loads(l) for l in open(p) if l.strip()]
p1 = {x['id']: x['p'] for x in readj(os.path.join(ROOT, 'data/m0/jev-pass1.jsonl')) if not x.get('error')}
p2 = {x['id']: x['p'] for x in readj(os.path.join(ROOT, 'data/m0/jev-pass2.jsonl')) if not x.get('error')}
c1 = {x['id']: x['p'] for x in readj(os.path.join(ROOT, 'data/m0/jev-post-changes.jsonl')) if not x.get('error')}
c2 = {x['id']: x['p'] for x in readj(os.path.join(ROOT, 'data/m0/jev-post-changes-2.jsonl')) if not x.get('error')}
opkey = lambda m, p, o: f"{str(m).upper()}|{p}|{o}"
for r in mech:
    r['pC'] = None if r['id'] not in c1 else ((c1[r['id']] + c2[r['id']]) / 2 if r['id'] in c2 else c1[r['id']])
    r['vendor'] = first_token(r['provider'])
    r['pA'] = p1.get(r['id']); r['pB'] = p2.get(r['id'])
    r['p'] = None if r['pA'] is None else (r['pA'] if r['pB'] is None else (r['pA'] + r['pB']) / 2)
    r['tier'] = TIER.get(r['jev_tier'], 'none')
    r['method'] = str(r['method']).upper()

# ---- v3 truth join (port of m0/parity.mjs --truth v3)
PMAP = {'stripe':'stripe.com','openai':'openai.com','square':'squareup.com','zoom':'zoom.us','meta-whatsapp':'whatsapp.local','spotify':'spotify.com','digitalocean':'digitalocean.com','jira':'jira.local','asana':'asana.com','okta':'okta.local','docusign':'docusign.net','xero':'xero.com'}
truth_rows = []
for t in csv.DictReader(open(os.path.join(RWXMAP, 'data/combined-2026-09-21/labelled.csv'), newline='')): truth_rows.append({**t, 'set': 'combined', 'mp': PMAP.get(t['provider'])})
for t in csv.DictReader(open(os.path.join(RWXMAP, 'data/relabel-buildset-2026-09-23/labelled.csv'), newline='')): truth_rows.append({**t, 'set': 'buildset', 'mp': None})
by_op = collections.defaultdict(list)
for r in mech: by_op[opkey(r['method'], r['path'], r['operationId'])].append(r)
v3 = {}  # mech id -> truth
for t in truth_rows:
    for r in by_op.get(opkey(t['method'], t['path'], t['operationId']), []):
        ok = (r['vendor'] == t['provider']) if t['set'] == 'buildset' else (t['mp'] is not None and r['provider'] == t['mp'])
        if ok and r['id'] not in v3: v3[r['id']] = {'truth': t['truth_class'], 'tset': t['set'], 'tsrc': t['source_set'], 'lowconf': t['confidence'] == 'low'}
v3_ids = set(v3)
v3_keys = {opkey(r['method'], r['path'], r['operationId']) + '|' + r['provider'] for r in mech if r['id'] in v3_ids}

# ---- eligibility
drop = collections.Counter(); keep = []
for r in mech:
    if r['exam'] or r['vendor'] in EXAM_LOCKED: drop['exam_or_locked'] += 1; continue
    if r['exam_opkey_overlap']: drop['exam_opkey_overlap'] += 1; continue
    keep.append(r)
assert not any(r['id'] in gate_ids and False for r in keep)

def label_row(r):
    """returns (label, status) or (None, reason). Round-6 recipe."""
    if r['method'] == 'DELETE': return 'x', 'delete'
    if r['p'] is None: return None, 'not_asked_non_delete'
    t = r['tier']
    if t != 'none' and r['pB'] is not None:
        c = CUTS[t]
        if (r['pA'] >= c) != (r['pB'] >= c): return None, 'wobble_straddle'
    l = tier_move(t, r['class'], r['p'])
    if t == 'lower' and l == 'w' and r['pC'] is not None and r['pC'] < R_CUT: l = 'r'   # POST changes < 0.20 -> r
    if cred_hit(r): return 'x', 'credential'
    return l, ('moved' if l != r['class'] else 'kept')

def row_out(r, label, status):
    return {'id': r['id'], 'text': fmt_text(r), 'label': label, 'y': ORDER[label], 'status': status, 'jev_p': r['p'], 'jev_pC': r['pC'], 'summary': clean(r.get('summary'), 200), 'jev_pA': r['pA'], 'jev_pB': r['pB'],
            'mech': r['class'], 'rule': r['rule'], 'tier': r['tier'], 'method': r['method'], 'provider': r['provider'], 'vendor': r['vendor'],
            'path': r['path'], 'operationId': r['operationId']}

train_pool = []; seen = set(); stats = collections.Counter()
for r in keep:
    if r['id'] in gate_ids: stats['excluded_gate_ids'] += 1; continue
    if r['id'] in v3_ids: stats['excluded_v3_eval'] += 1; continue
    k = (r['provider'], r['method'], r['path'], r['operationId'])
    if k in seen: stats['dup_snapshot'] += 1; continue
    seen.add(k)
    lab, st = label_row(r)
    if lab is None: stats['dropped_' + st] += 1; continue
    train_pool.append(row_out(r, lab, st))

# v3 eval: all joined rows (all snapshots), carrying truth + p for the downstream metrics
v3eval = []
for r in mech:
    if r['id'] not in v3_ids or r['exam'] or r['vendor'] in EXAM_LOCKED or r['exam_opkey_overlap']: continue
    o = row_out(r, r['class'], 'v3eval'); o.update(v3[r['id']]); o['in_gate_ids'] = r['id'] in gate_ids; v3eval.append(o)

# ---- vendor split
vendors = sorted({x['vendor'] for x in train_pool}); rng = random.Random(SEED); rng.shuffle(vendors)
nval = max(1, round(0.10 * len(vendors))); val_v = set(vendors[:nval])
train = [x for x in train_pool if x['vendor'] not in val_v]; val = [x for x in train_pool if x['vendor'] in val_v]
os.makedirs(OUT, exist_ok=True)
for name, rows in [('train', train), ('val', val), ('v3eval', v3eval)]:
    pd.DataFrame(rows).to_parquet(os.path.join(OUT, name + '.parquet'), index=False)
    with open(os.path.join(OUT, name + '.jsonl'), 'w') as f:
        for x in rows: f.write(json.dumps(x) + '\n')
json.dump(sorted(val_v), open(os.path.join(OUT, 'val_vendors.json'), 'w'))
def dist(rows, k): return dict(collections.Counter(x[k] for x in rows).most_common())
summary = {'seed': SEED, 'mechanical_rows': len(mech), 'dropped_before': dict(drop), 'stats': dict(stats), 'train_pool': len(train_pool),
           'vendors_total': len(vendors), 'vendors_val': nval,
           'train': {'n': len(train), 'label': dist(train, 'label'), 'status': dist(train, 'status'), 'tier': dist(train, 'tier'), 'method': dist(train, 'method')},
           'val': {'n': len(val), 'label': dist(val, 'label'), 'status': dist(val, 'status'), 'tier': dist(val, 'tier')},
           'v3eval': {'n': len(v3eval), 'truth': dist(v3eval, 'truth'), 'tier': dist(v3eval, 'tier'), 'in_gate_ids': sum(x['in_gate_ids'] for x in v3eval)}}
json.dump(summary, open(os.path.join(OUT, 'dataset-summary.json'), 'w'), indent=1)
print(json.dumps(summary, indent=1))
