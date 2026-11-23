"""Round 15 (docs/wiki/prereg-r15.md section 3): build the teacher/student training set. Deterministic, no training, stops on any assertion.
  The final set (the one SHA256SUMS and the prereg record) needs the 5 env vars of prereg-r15.md section 3.4; the plain `python3 r15/r15_assemble.py` builds the PROVISIONAL set and overwrites data/round15/ (gitignored, OUT is fixed):
  R15_R13_DIR=data/round13-d141 R15_R13_SHAS=train=ae9a44184538e571185479907da4e9ead9211e1d0a6f6b185f34fc7f12341ae7,val=bc7bc643ecfdea2ce3bc6d5fb3faa972ca07ae19cc45440f52bcb99412fc3400,v3eval=7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad \
  R15_MECH_REF=1c25be1 R15_LEAN_CSV=<export-v4-d141.csv> R15_LEAN_SHA=8d802cf42d56fbcf050102fb854a958696bf59abdeca1a43fe6c88bcdc53034f python3 r15/r15_assemble.py
Inputs (sha256 are asserted against the prereg values): data/round13/{train,val,v3eval}.parquet (R13 rows, unchanged), data/r15/labels/final-labels-r15-d141-tight.parquet (199,600 cascade rows after the D141 relabel; never edited here),
data/r15/labels/texts-r15.jsonl (model input text of every pick row; src/text.js formatText format 1 with rwxmap's mechanical lean), data/r15/labels/mech-r15.jsonl (mech letter and rule),
data/r15/labels/disagree-sample-400.csv (the holdout: must NOT be in the output).
Outputs: train.parquet (R13 rows first, in R13 order, then the 199,600 r15 rows in final-labels order), val.parquet and v3eval.parquet (copies), targets-teacher.npy (float32 (N,3):
R13 rows = common.soft_targets() exactly as R13 trained, r15 rows = one-hot of the cascade label), SHA256SUMS, summary.json."""
import os, sys, json, hashlib
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'train'))
from common import soft_targets, ROOT
SHA = {'data/round13/train.parquet': '91808a87cf24ac9c70f4d5b8f26fe68341ca9836606ce30a3e86273fce129aa5', 'data/round13/val.parquet': '580a1141e6ee416b4ff2b445c749fc95b60bcdbddd04d0bbdd0464196ff840d1',
       'data/round13/v3eval.parquet': '7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad', 'data/r15/labels/final-labels-r15-d141-tight.parquet': '0937e0a25fef244fd1b0aa1566f61774b88b2f656f202fef4730c34594b37e56',
       'data/r15/labels/d141/merged.csv': '2436a63db9dfdf9c464133b7b6181ab384d17333e6698858b205cd6a7d5cd990', 'data/r15/labels/d141/pass2/out-a.csv': '6ca51a31eb6d2cb411b10bfb60d6cb692fd6757b59e85044d6584fb3120c4ee3', 'data/r15/labels/d141/pass2/out-b.csv': '931ffc9f53d7dc314fc5c851f98c68b1fced13ac86bc09ac4b81925e7091ffa4',
       'data/r15/labels/texts-r15.jsonl': '4f7955fb897ff1ca48a628df38d8b80aa8b5489f7f93085d027a98e45416a4ab', 'data/r15/labels/mech-r15.jsonl': 'ef3938d15bd81aed423927ce6a429c492e5dede06835275be9f075ad12b46a43',
       'data/r15/labels/disagree-sample-400.csv': '76dd3fae6ec409855447f3d449fda4fa2f7a5a5d5b543900fd791e84bb194512'}
# The label file is final (D141 applied, rwxlite cf6232d). The 102,668 R13 rows were replaced by rwxmap's export-v4-d141 (DONE 2026-11-19, prereg section 3.4); the final build runs with
#   R15_R13_DIR=<dir holding train.parquet, val.parquet, v3eval.parquet> R15_R13_SHAS=train=<sha>,val=<sha>,v3eval=<sha>   (same columns, same row count and order as round 13's)
# and the round 13 shas above are replaced by those. Without these env vars the output is the PROVISIONAL set (round 13 rows as stored), not the shipped one.
R13DIR = os.environ.get('R15_R13_DIR', 'data/round13')
if 'R15_R13_DIR' in os.environ:
    for kv in os.environ['R15_R13_SHAS'].split(','):
        k, v = kv.split('='); SHA.pop(f'data/round13/{k}.parquet', None); SHA[f'{R13DIR}/{k}.parquet'] = v
LAB = 'data/r15/labels/final-labels-r15-d141-tight.parquet'   # tighten-only merge: the 162 D141 lowers reverted by r15/r15_revert_lowers.py
# export-v4-d141 hook (2026-11-19): R15_LEAN_CSV=<export-v4-d141.csv> R15_LEAN_SHA=<its sha256>: for the R13 train rows, val and v3eval, the lean prefix (and mech letter) is written from the export's lean_letter + lean_rule
# (rwxmap is the source of truth; tail kept); any difference to the regenerated prefix is counted in summary.json. A `d141_changed` column in the R13 train parquet (written by r15/r15_apply_d141_export.py) marks rows whose label D141 changed:
# their soft target is the one-hot of the new label (the stored Jev soft target belongs to the old label), and the column is dropped here.
LEANCSV = os.environ.get('R15_LEAN_CSV'); LEAN = None; LEAN_DIFF = {}
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
for p, h in SHA.items(): assert sha(os.path.join(ROOT, p)) == h, f'{p} sha256 differs from the prereg'
if LEANCSV:
    assert sha(LEANCSV) == os.environ['R15_LEAN_SHA'], 'R15_LEAN_CSV sha256 differs from R15_LEAN_SHA'
    LEAN = pd.read_csv(LEANCSV, keep_default_na=False).set_index('id'); assert LEAN.index.is_unique
D = lambda *a: os.path.join(ROOT, *a); OUT = D('data', 'round15'); os.makedirs(OUT, exist_ok=True)
tr13 = pd.read_parquet(D(R13DIR, 'train.parquet')); assert tr13.index.equals(pd.RangeIndex(len(tr13))) and len(tr13) == 102668
d141_chg = tr13.pop('d141_changed').values.astype(bool) if 'd141_changed' in tr13.columns else np.zeros(len(tr13), bool)
fin = pd.read_parquet(D(LAB)); assert len(fin) == 199600 and fin.op_id.is_unique
hold = set(pd.read_csv(D('data/r15/labels/disagree-sample-400.csv')).op_id); assert len(hold) == 400 and not (hold & set(fin.op_id))
text = {}; mech = {}
for l in open(D('data/r15/labels/texts-r15.jsonl'), encoding='utf-8'):
    r = json.loads(l); text[r['op_id']] = r['text']
for l in open(D('data/r15/labels/mech-r15.jsonl'), encoding='utf-8'):
    r = json.loads(l); mech[r['op_id']] = r
assert len(text) == len(mech) == 200000 and set(fin.op_id) <= set(text) and not (set(fin.op_id) & set(tr13.id))
assert all(mech[i]['text'] == text[i] for i in fin.op_id), 'texts-r15.jsonl differs from mech-r15.jsonl text'
Y = {'r': 0, 'w': 1, 'x': 2}; assert set(fin.label) <= set(Y) and set(fin.tier) == {'agree3', 'sonnet', 'opus_agree', 'strict'}
# ---- row weights (prereg section 3.3; the user's rule 2026-11-19: x3 on previously contested rows, where wrong judgements happen; uncertain ones are lifted from 0.3 to 1.0 = 3 x 0.3) ----
# The label file's own `weight` is 0.3 on strict-tier rows and on D141-changed rows whose deciding answer was unsure (label_d141.py); it is read only to cross-check, never edited.
RKo = {'r': 0, 'w': 1, 'x': 2}
mg = pd.read_csv(D('data/r15/labels/d141/merged.csv'), keep_default_na=False).set_index('op_id'); p2c = {}
import csv; csv.field_size_limit(10**9)
for f in ('out-a.csv', 'out-b.csv'):
    for r in csv.DictReader(open(D('data/r15/labels/d141/pass2', f), newline='', encoding='utf-8')): p2c[r['op_id']] = r
def deciding_conf(i):   # confidence of the answer that decided a D141-changed row (as r15/label_d141.py conf_src): Opus pass 2 if it raised Sonnet's letter, else Sonnet's
    n = mg.loc[i, 'new']; p = p2c.get(i)
    return p['confidence'] if p and RKo[p['letter']] > RKo[n] else mg.loc[i, 'confidence']
def row_weight(r):
    if r.d141_changed:
        return 1.0 if deciding_conf(r.op_id) == 'unsure' else 3.0      # changed by D141 (incl. pass-2 raises): unsure answer 1.0, sure/likely 3.0, whatever the tier
    if r.tier == 'strict': return 1.0                                 # residue rule: the strictest opinion, uncertain
    return 3.0 if r.tier in ('sonnet', 'opus_agree') else 1.0          # contested rows 3.0; agree3 not changed by D141 1.0
fin['row_weight'] = [row_weight(r) for r in fin.itertuples(index=False)]
nc = fin[fin.d141_changed & (fin.tier != 'strict')]; assert ((nc.weight < 1) == (nc.row_weight == 1.0)).all(), 'label file weight and the deciding-confidence rule disagree on a changed non-strict row'
assert set(fin.row_weight.unique()) == {1.0, 3.0} and set(fin.weight.unique()) == {1.0, 0.3}
new = pd.DataFrame({'id': fin.op_id.values, 'text': [text[i] for i in fin.op_id], 'label': fin.label.values, 'y': fin.label.map(Y).astype('int64').values, 'status': 'r15', 'jev_p': np.nan, 'jev_pC': np.nan,
                    'summary': fin.summary.values, 'jev_pA': np.nan, 'jev_pB': np.nan, 'mech': [mech[i]['mech_letter'] for i in fin.op_id], 'rule': [mech[i]['mech_rule'] for i in fin.op_id], 'tier': 'none',
                    'method': fin.method.values, 'provider': fin.vendor_id.values, 'vendor': fin.vendor_id.values, 'path': fin.path.values, 'operationId': fin.operationId.values})
new['src'] = 'r15'; new['weight'] = fin.row_weight.astype('float64').values; new['r15_tier'] = fin.tier.values
old = tr13.copy(); old['src'] = 'r13'; old['weight'] = 1.0; old['r15_tier'] = ''
# val decides the teacher go/no-go (5.2a) and the val floor guard, so no training row may share an exact method + path(lower) + operationId + summary with a val row: such r15 rows are dropped.
key = lambda d: list(zip(d.method.str.upper(), d.path.str.lower(), d.operationId.fillna(''), d.summary.fillna('')))
val0 = pd.read_parquet(D(R13DIR, 'val.parquet')); VK = set(key(val0))
dropv = np.array([k in VK for k in key(new)]); dropped_val_overlap = new.loc[dropv, ['id', 'r15_tier', 'weight']].copy(); new = new[~dropv].reset_index(drop=True)
train = pd.concat([old, new[old.columns]], ignore_index=True); assert train.id.is_unique
r13_val_overlap = int(sum(k in VK for k in key(old)))
assert not any(k in VK for k in key(new)), 'an r15 row still matches val'
NROWS = len(train); assert NROWS == len(old) + len(fin) - int(dropv.sum())
T13 = soft_targets(tr13); T13[d141_chg] = np.eye(3, dtype=np.float32)[tr13.y.values[d141_chg]]
T = np.concatenate([T13, np.eye(3, dtype=np.float32)[new.y.values]]).astype(np.float32); assert T.shape == (len(train), 3) and np.allclose(T.sum(1), 1, atol=1e-5)
# ---- Regeneration (prereg section 7.2, DONE 2026-11-19 at R15_MECH_REF=1c25be1): R15_MECH_REF=<rwxmap git sha of the frozen exam #7 ref> regenerates the text of ALL train rows and the val/v3eval rows with that ref's
# mechanical lean (lean = exam lean). Unset = texts exactly as stored (R13 rows) and as texts-r15.jsonl (rwxmap 1c25be1 mechanical). Needs the rwxmap repo at R15_RWXMAP (default ~/PycharmProjects/rwxmap).
REF = os.environ.get('R15_MECH_REF'); regen = {'mech_ref': None}
def regen_texts(df, desc):
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tree = os.path.join(tmp, 'tree'); os.makedirs(tree)
        ar = subprocess.run(['git', '-C', RWXMAP, 'archive', REF, 'src', 'package.json'], capture_output=True, check=True); subprocess.run(['tar', '-x', '-C', tree], input=ar.stdout, check=True)
        fi, fo = os.path.join(tmp, 'in.jsonl'), os.path.join(tmp, 'out.jsonl')
        with open(fi, 'w', encoding='utf-8') as f:
            for r, dsc in zip(df.itertuples(index=False), desc): f.write(json.dumps({'id': r.id, 'method': r.method, 'path': r.path, 'operationId': r.operationId or '', 'summary': r.summary or '', 'description': dsc}, ensure_ascii=False) + '\n')
        subprocess.run(['node', os.path.join(ROOT, 'r15', 'regen_text.mjs'), '--tree', tree, '--in', fi, '--out', fo], check=True)
        o = [json.loads(l) for l in open(fo, encoding='utf-8')]
    assert [x['id'] for x in o] == list(df.id); return o
ALIAS = {'credential-set': 'cant-undo-verb'}
def lean_from_export(df, name, mask=None):
    """Write the lean prefix and mech letter from the export (tail kept); count how many rows differ from the regenerated prefix. mask: only these rows (train: the R13 rows)."""
    mask = np.ones(len(df), bool) if mask is None else mask; assert df.id[mask].isin(LEAN.index).all(), f'{name}: ids missing in the export'
    L = LEAN.loc[df.id[mask]]; old_t = list(df.text); new_t = list(old_t); idx = np.flatnonzero(mask)   # plain lists: element assignment on the Arrow-backed column is O(n) each
    for k, i in enumerate(idx): new_t[i] = f'lean: {L.lean_letter.values[k]} {L.lean_rule.values[k]} | ' + old_t[i].split(' | ', 1)[1]
    assert (df.rule.values[mask] == L.lean_rule.values).sum() + sum(ALIAS.get(a) == b for a, b in zip(df.rule.values[mask], L.lean_rule.values) if a != b) == mask.sum(), f'{name}: rule column differs from lean_rule beyond the alias'
    LEAN_DIFF[name] = {'rows': int(mask.sum()), 'prefix_differs_from_regen': sum(x != y for x, y in zip(new_t, old_t)), 'mech_letter_differs_from_regen': int((df.mech.values[mask] != L.lean_letter.values).sum())}
    mech = list(df.mech); [mech.__setitem__(i, c) for i, c in zip(idx, L.lean_letter.values)]; df['text'] = new_t; df['mech'] = mech
def stored_desc(text): return text.split(' | desc: ', 1)[1].rstrip() if ' | desc: ' in text else ''
if REF:
    RWXMAP = os.environ.get('R15_RWXMAP', os.path.expanduser('~/PycharmProjects/rwxmap'))
    fdesc = dict(zip(fin.op_id, fin.description.fillna('')))
    o = regen_texts(train, [fdesc[i] if sr == 'r15' else stored_desc(t) for i, sr, t in zip(train.id, train.src, train.text)])
    if REF.startswith('1c25be1'):
        assert all(x['text'] == text[x['id']] for x in o[len(old):]), 'regeneration at 1c25be1 does not reproduce texts-r15.jsonl'
    keep = lambda old_t, x: x['text'] if x is None else x['text'].split(' | ', 1)[0] + ' | ' + old_t.split(' | ', 1)[1]   # R13/val/v3eval: re-cleaning the stored (already cleaned) description is not idempotent (double unescape, tag strip): swap ONLY the lean prefix, keep the stored tail
    train['text'] = [x['text'] if sr == 'r15' else keep(t, x) for x, sr, t in zip(o, train.src, train.text)]; train['mech'] = [x['class'] for x in o]; train['rule'] = [x['rule'] for x in o]; regen['mech_ref'] = REF
    if LEAN is not None: lean_from_export(train, 'train_r13_rows', (train.src == 'r13').values)
train.to_parquet(os.path.join(OUT, 'train.parquet'), index=False); np.save(os.path.join(OUT, 'targets-teacher.npy'), T)
for n in ('val', 'v3eval'):
    d = pd.read_parquet(D(R13DIR, n + '.parquet'))
    if REF:
        o = regen_texts(d, [stored_desc(t) for t in d.text]); d['text'] = [keep(t, x) for x, t in zip(o, d.text)]; d['mech'] = [x['class'] for x in o]; d['rule'] = [x['rule'] for x in o]
        if LEAN is not None: lean_from_export(d, n)
    d.to_parquet(os.path.join(OUT, n + '.parquet'), index=False)
val = pd.read_parquet(os.path.join(OUT, 'val.parquet'))
key = lambda d: set(zip(d.method.str.upper(), d.path.str.lower(), d.operationId.fillna(''), d.summary.fillna('')))
VK = key(val)
summ = {'rows': len(train), 'r13_rows': len(old), 'r15_rows': len(new), 'r15_rows_dropped_val_overlap': int(dropv.sum()), 'dropped_val_overlap_by_tier': dropped_val_overlap.r15_tier.value_counts().to_dict(), 'r13_rows_matching_val_key_info': r13_val_overlap, 'steps_bs32': -(-len(train) // 32), 'letters': {s: train[train.src == s].label.value_counts().to_dict() for s in ('r13', 'r15')},
        'r15_tiers': new.r15_tier.value_counts().to_dict(), 'weight_total': float(train.weight.sum()), 'r15_weight_total': float(new.weight.sum()), 'r15_weight_counts': {str(k): int(v) for k, v in new.weight.value_counts().sort_index().items()}, 'r15_weight_by_tier': {t: {str(k): int(v) for k, v in g.weight.value_counts().sort_index().items()} for t, g in new.groupby('r15_tier')}, 'r15_changed_rows': int(fin.d141_changed.sum()), 'contested_weight_share': float(new.weight[new.weight == 3.0].sum() / train.weight.sum()), 'r13_soft_rows_not_onehot': int((T[:len(old)].max(1) < 0.9999).sum()),
        'r15_vendors': int(new.vendor.nunique()), 'mean_text_chars': {'r13': float(old.text.str.len().mean()), 'r15': float(new.text.str.len().mean())},
        'val_rows': len(val), 'r15_val_op_key_overlap_rows_info': int(sum(k in VK for k in zip(new.method.str.upper(), new.path.str.lower(), new.operationId.fillna(''), new.summary.fillna('')))),
        'holdout_in_train': 0, 'd141_changed_r13_rows_onehot': int(d141_chg.sum()), 'lean_csv': LEANCSV and {'sha256': os.environ['R15_LEAN_SHA'], 'diff_vs_regen': LEAN_DIFF}, **regen}
json.dump(summ, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1); print(json.dumps(summ, indent=1))
with open(os.path.join(OUT, 'SHA256SUMS'), 'w') as f:
    for n in ('train.parquet', 'val.parquet', 'v3eval.parquet', 'targets-teacher.npy', 'summary.json'): f.write(f'{sha(os.path.join(OUT, n))}  {n}\n')
print(open(os.path.join(OUT, 'SHA256SUMS')).read())
