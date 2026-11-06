"""Round 13 data build. Deterministic, no training, no relabelling of our own: labels come from rwxmap's BRIEF-v4 export.
  python3 -I m1/r13-assemble.py            (needs numpy/pandas on sys.path; the script appends ~/.local/lib/python3.14/site-packages)
Reads (all hashes verified first, stop on mismatch):
  rwxmap 95104e3 data/export-v4-gap-2026-11-06/{export-v4.csv,inherit-v4.csv}
  data/v4/rwxlite-w-unique.csv (merge key, label-inventory 9.5), data/round12/final/{S0/train,holdout}.jsonl, data/round12/{val,v3eval}.jsonl,
  data/gate-2026-11-0{3,4,6,7}/{blind,truth,ids}, data/m0/mechanical.jsonl.gz, data/round12/{seeds.csv,final/generated-unique.jsonl}
Writes data/round13/{train,val,v3eval}.{jsonl,parquet}, provenance.csv, summary.json, SHA256SUMS. Text format = train/common.fmt_text (unchanged)."""
import sys, os, csv, json, gzip, hashlib, collections, subprocess
sys.path.append(os.path.expanduser('~/.local/lib/python3.14/site-packages'))
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'train')); sys.path.insert(0, os.path.join(ROOT, 'm1'))
from common import fmt_text, clean, first_token, ORDER, load_mech
from round10_aliases import text_rule
import pandas as pd
csv.field_size_limit(10 ** 9)
D = os.path.join(ROOT, 'data'); OUT = os.path.join(D, 'round13'); os.makedirs(OUT, exist_ok=True)
RWXMAP = '/home/hamr/PycharmProjects/rwxmap'; RCOMMIT = '95104e3'; RDIR = 'data/export-v4-gap-2026-11-06'
SHA = {'export-v4.csv': '0e371db2a3554309dd3cce8cbe287ab4b7d693893589c114146cbe186c58114b', 'inherit-v4.csv': 'e1993a27e2f6287424801b4dc3cfd1c956e727df42f7577c3ee0fe3d68b56ee3'}
def fail(m): sys.exit('FAIL: ' + m)
def sha(b): return hashlib.sha256(b).hexdigest()
def fsha(p): return sha(open(p, 'rb').read())
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
def rcsv(p): return list(csv.DictReader(open(p, newline='')))

# ---- 0. labels: read from the pinned commit, verify hashes
raw = {}
for n, h in SHA.items():
    b = subprocess.run(['git', '-C', RWXMAP, 'show', f'{RCOMMIT}:{RDIR}/{n}'], capture_output=True, check=True).stdout
    if sha(b) != h: fail(f'{n} sha256 {sha(b)} != {h}')
    if fsha(os.path.join(RWXMAP, RDIR, n)) != h: fail(f'working-tree {n} differs')
    raw[n] = b.decode()
import io
export = [r for r in csv.DictReader(io.StringIO(raw['export-v4.csv'], newline='')) if r['set'] == 'rwxlite']
inherit = list(csv.DictReader(io.StringIO(raw['inherit-v4.csv'], newline='')))
WU = os.path.join(D, 'v4', 'rwxlite-w-unique.csv')
if fsha(WU) != 'a40d1f59dc56b31628e1a48cf8b1c99e9159d6dff0b645050079e141d7edd558': fail('rwxlite-w-unique.csv hash')
wu = rcsv(WU)

def mkey(p, m, path, op, s):
    m = (m or '').upper(); m = 'GET' if m == 'QUERY' else m
    return ((p or '').lower(), m, path or '', op or '', ' '.join((s or '').split()).lower())
def okey(r): return mkey(r['provider'], r['method'], r['path'], r['operationId'], '')[:4]
def rk(r): return mkey(r['provider'], r['method'], r['path'], r['operationId'], r['summary'])

exlab = {r['id']: r['label'] for r in export}
if len(exlab) != len(export): fail('duplicate ids in rwxlite export')
V4 = {}          # merge key -> v4 label
surf = {r['your_id'] for r in inherit}
for r in wu:
    if r['your_id'] in surf: continue
    if r['your_id'] not in exlab: fail('w-unique id missing from export: ' + r['your_id'])
    k = mkey(r['provider'], r['method'], r['path'], r['operationId'], r['summary'])
    if k in V4: fail('merge key repeated in w-unique')
    V4[k] = exlab[r['your_id']]
if len(V4) != len(export): fail(f'groups {len(V4)} != export rwxlite rows {len(export)}')
if not set(surf) <= {r['your_id'] for r in wu}: fail('surface ids not all in w-unique')

# ---- 1. inputs
S0 = jl(os.path.join(D, 'round12/final/S0/train.jsonl')); VAL = jl(os.path.join(D, 'round12/val.jsonl'))
V3 = jl(os.path.join(D, 'round12/v3eval.jsonl')); HOLD = jl(os.path.join(D, 'round12/final/holdout.jsonl'))
if (len(S0), len(VAL), len(V3), len(HOLD)) != (95291, 4180, 5716, 455): fail('input sizes')
MECH = {m['id']: m for m in load_mech()}
CORE = list(S0[0].keys())
S0DIST = dict(collections.Counter(r['label'] for r in S0)); S0N = len(S0)
def core(r): return {k: r[k] for k in CORE}
prov = []   # id, source, split, before, after, reason
def src_of(r, split):
    i = r['id']
    for p, n in (('ex3-', 'exam3'), ('ex4-', 'exam4'), ('fx-', 'fresh-exam')):
        if i.startswith(p): return n
    if split == 'val': return 'val'
    if r['status'] == 'delete': return 'delete-mech'
    if r['status'] in ('fresh', 'credential'): return 'hand-or-rule'
    if r['tier'] == 'none': return 'mech-rule'
    return 'jev-soft'
SRC = {r['id']: src_of(r, 'train') for r in S0}; SRC.update({r['id']: src_of(r, 'val') for r in VAL})

def hand(r, label, why):
    """Same hard-target convention as r12-assemble label fixes: one-hot, no Jev p, tier none."""
    r.update(label=label, y=ORDER[label], status='fresh', jev_p=None, jev_pC=None, jev_pA=None, jev_pB=None, tier='none')
    return r

# ---- 2. gates: hand truth
gate_info = {}   # gate number -> list of (opkey, truth, blind row)
GATES = [(1, 'gate-2026-11-03'), (2, 'gate-2026-11-04'), (3, 'gate-2026-11-06'), (4, 'gate-2026-11-07')]
ag_by_ok = collections.defaultdict(list)
for m in MECH.values(): ag_by_ok[okey(m)].append(m)
trk = collections.defaultdict(list)
for r in S0: trk[okey(r)].append(r)
vak = collections.defaultdict(list)
for r in VAL: vak[okey(r)].append(r)
hand_changes = collections.Counter(); gate_new = []; GATED = set(); gate_notes = collections.Counter()
for g, d in GATES:
    truth = {r['id']: r['label'] for r in rcsv(os.path.join(D, d, 'truth.csv'))}
    blind = rcsv(os.path.join(D, d, 'blind.csv'))
    gids = {l.strip() for l in open(os.path.join(D, d, 'ids.txt')) if l.strip()}
    if set(truth) != {b['id'] for b in blind}: fail('gate truth/blind ids')
    for b in blind:
        t = truth[b['id']]; k = okey(b)
        intr, inva = trk.get(k, []), vak.get(k, [])
        for r in intr:
            if r['label'] != t:
                gate_notes[f'gate{g} train {r["label"]}->{t} ({SRC[r["id"]]})'] += 1
                prov.append((r['id'], SRC[r['id']], 'train', r['label'], t, f'gate{g} hand truth over {SRC[r["id"]]}'))
                hand(r, t, 'gate'); GATED.add(r['id'])
        for r in inva:
            if r['label'] != t: gate_notes[f'gate{g} VAL differs from truth {r["label"]} vs {t} (left as is)'] += 1
        if intr or inva: continue
        cands = [m for m in ag_by_ok.get(k, []) if m['id'] in gids]
        if not cands: fail('no mechanical row for gate op ' + b['id'])
        pick = [m for m in cands if (m['summary'], m['description']) == (b['summary'], b['description'])] or cands
        m = pick[0]
        r = {'id': m['id'], 'text': fmt_text(dict(m, rule=text_rule(m['rule']))), 'label': t, 'y': ORDER[t], 'status': 'fresh', 'jev_p': None, 'jev_pC': None,
             'summary': clean(m['summary'], 200), 'jev_pA': None, 'jev_pB': None, 'mech': m['class'], 'rule': m['rule'], 'tier': 'none', 'method': m['method'].upper(),
             'provider': m['provider'], 'vendor': first_token(m['provider']), 'path': m['path'], 'operationId': m['operationId']}
        gate_new.append((g, r)); SRC[r['id']] = f'gate{g}'
        prov.append((r['id'], f'gate{g}', 'train', '', t, f'added: gate{g} hand truth'))

# ---- 3. new rows: holdout, v3eval (truth), gates
NEW = []
for r in HOLD:
    SRC[r['id']] = 'holdout'; NEW.append(core(r))
v3k = collections.defaultdict(set)
for r in V3:
    t = r['truth']
    if t != r['label']: hand_changes['v3eval recipe->truth'] += 1
    n = hand(core(r), t, 'v3eval'); n['status'] = 'fresh'
    SRC[r['id']] = 'v3eval'; NEW.append(n); v3k[rk(r)].add(t)
v3conf = sum(len(v) > 1 for v in v3k.values())
for g, r in gate_new: NEW.append(r)
TRAIN = S0 + NEW
for r in HOLD: prov.append((r['id'], 'holdout', 'train', r['label'], r['label'], 'added: goharbor+render, D136 truth'))
for r in V3: prov.append((r['id'], 'v3eval', 'train', r['label'], r['truth'], 'added: v3eval hand truth' + ('' if r['truth'] == r['label'] else ' (recipe label overridden)')))

# ---- 4. one authoritative label per merge group: hand truth over Jev/mechanical (before v4)
def is_hand(r): return SRC[r['id']] in ('exam3', 'exam4', 'fresh-exam', 'holdout', 'v3eval') or SRC[r['id']].startswith('gate') or SRC[r['id']] == 'hand-or-rule' or r['id'] in GATED
grp = collections.defaultdict(list)
for r in TRAIN: grp[rk(r)].append(r)
repeat_conf = collections.Counter(); resolved = 0
for k, rows in grp.items():
    labs = {r['label'] for r in rows}
    if len(labs) < 2: continue
    h = [r for r in rows if is_hand(r)]
    hl = {r['label'] for r in h}
    if len(hl) == 1 and k not in V4:
        for r in rows:
            if r['label'] not in hl:
                prov.append((r['id'], SRC[r['id']], 'train', r['label'], next(iter(hl)), 'repeat: hand truth over Jev/mech')); hand(r, next(iter(hl)), 'repeat'); resolved += 1
        repeat_conf['resolved to hand'] += 1
    elif k in V4: repeat_conf['settled by v4'] += 1
    else: repeat_conf['unresolved (kept as is)'] += 1

# ---- 5. v4 labels onto whole merge groups
changes = collections.Counter(); by_src = collections.defaultdict(collections.Counter); softneut = 0
def apply_v4(rows, split):
    global softneut
    n = 0
    for r in rows:
        k = rk(r)
        if k not in V4: continue
        n += 1; new = V4[k]; old = r['label']
        if new == old: continue
        was_soft = r['status'] not in ('delete', 'credential') and r['tier'] != 'none' and r['jev_p'] is not None
        if was_soft: softneut += 1
        s = SRC[r['id']]
        changes[(split, f'{old}->{new}')] += 1; by_src[(split, f'{old}->{new}')][s] += 1
        prov.append((r['id'], s, split, old, new, 'v4' + (' (Jev soft target replaced by one-hot)' if was_soft else '')))
        if was_soft or r['status'] != 'delete': pass
        if was_soft: hand(r, new, 'v4')
        else: r['label'] = new; r['y'] = ORDER[new]
    return n
nt = apply_v4(TRAIN, 'train'); nv = apply_v4(VAL, 'val')

# ---- 6. asserts
ids = collections.Counter(r['id'] for r in TRAIN + VAL)
if [i for i, c in ids.items() if c > 1]: fail('duplicate ids')
tk, vk_ = {rk(r) for r in TRAIN}, {rk(r) for r in VAL}
to, vo = {okey(r) for r in TRAIN}, {okey(r) for r in VAL}
if tk & vk_ or to & vo: fail('val operation in train')
for r in TRAIN + VAL:
    if r['label'] not in ORDER or r['y'] != ORDER[r['label']]: fail('label/y ' + r['id'])
# text identical to S0 for every S0 row
s0t = {r['id']: r['text'] for r in S0}
if any(r['text'] != s0t[r['id']] for r in TRAIN[:len(S0)]): fail('text changed')

# ---- 7. write
def wr(name, rows):
    with open(os.path.join(OUT, name + '.jsonl'), 'w') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    pd.DataFrame(rows).to_parquet(os.path.join(OUT, name + '.parquet'), index=False)
wr('train', TRAIN); wr('val', VAL)
with open(os.path.join(OUT, 'v3eval.jsonl'), 'w') as f:        # unchanged copy, only for the trainer's end-of-run report
    for r in V3: f.write(json.dumps(r, ensure_ascii=False) + '\n')
pd.DataFrame(V3).to_parquet(os.path.join(OUT, 'v3eval.parquet'), index=False)
with open(os.path.join(OUT, 'provenance.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'source', 'split', 'label_before', 'label_after', 'reason']); w.writerows(prov)

# ---- 8. report
def dist(rows): c = collections.Counter(r['label'] for r in rows); return {k: c[k] for k in 'rwx'}
s0d = {k: S0DIST[k] for k in 'rwx'}
gen = jl(os.path.join(D, 'round12/final/generated-unique.jsonl')); seeds = {r['seed_id']: r for r in rcsv(os.path.join(D, 'round12/seeds.csv'))}
gl = {g['id']: g for g in gen}; sdiff = collections.Counter()
for r in inherit:
    g = gl.get(r['your_id']); s = seeds[r['variant_of']]
    sl = V4.get(mkey(s['provider'], s['method'], s['path'], s['operationId'], s['summary']), s['truth'])
    sdiff[(g['label'] if g else '?', sl)] += 1
soft_rows = sum(1 for r in TRAIN if r['status'] not in ('delete', 'credential') and r['tier'] != 'none' and r['jev_p'] is not None)
summ = {
    'labels_commit': RCOMMIT, 'sha256': SHA,
    'train_rows': len(TRAIN), 'train_unique_ids': len({r['id'] for r in TRAIN}), 'train_unique_ops_mergekey': len(tk), 'train_unique_ops_opkey': len(to),
    'val_rows': len(VAL), 'val_unique_ops_mergekey': len(vk_),
    's0_dist': s0d, 'train_dist': dist(TRAIN), 'train_dist_s0_rows_after_v4': dist(TRAIN[:S0N]), 'train_dist_added_rows': dist(TRAIN[S0N:]), 'val_dist': dist(VAL), 'added': {'holdout': len(HOLD), 'v3eval': len(V3), 'gate_new_by_gate': dict(collections.Counter(g for g, _ in gate_new))},
    'gate_notes': dict(gate_notes), 'v3eval_recipe_to_truth_changes': hand_changes['v3eval recipe->truth'], 'v3eval_merge_groups_with_conflicting_truth': v3conf,
    'repeat_conflicts': dict(repeat_conf), 'repeat_rows_relabelled': resolved,
    'v4_changes': {f'{a}:{b}': c for (a, b), c in changes.items()}, 'v4_changes_by_source': {f'{a}:{b}': dict(c) for (a, b), c in by_src.items()},
    'v4_rows_in_groups': {'train': nt, 'val': nv}, 'v4_groups': len(V4), 'v4_soft_to_onehot': softneut, 'train_rows_with_jev_soft_target': soft_rows,
    'surface_variants_excluded': len(inherit), 'surface_variant_label_vs_inherited(variant_label,seed_v4)': {f'{a}->{b}': c for (a, b), c in sdiff.items()},
    'generated_variants_in_train': 0,
}
json.dump(summ, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)
names = ['train.jsonl', 'train.parquet', 'val.jsonl', 'val.parquet', 'v3eval.jsonl', 'v3eval.parquet', 'provenance.csv', 'summary.json']
open(os.path.join(OUT, 'SHA256SUMS'), 'w').write(''.join(f'{fsha(os.path.join(OUT, n))}  {n}\n' for n in names))
print(json.dumps(summ, indent=1)); print(open(os.path.join(OUT, 'SHA256SUMS')).read())
