"""Round 16 teacher training set v2 (new rows + holdout 400 + old replay + rwxmap rulings + exam #7 mistakes). Deterministic, stops on any failed check.
  data/r16/scratch/venv/bin/python -I r16/build_teacher_train.py [--conflicts abort|exclude]
rwxmap's pipeline is the only label truth: rwxmap_letter is applied as given, nothing is relabelled here.
Parts: new (final-labels-r16, D143 booking answers applied), holdout (400, rwxmap letters), replay-r13 / replay-r15 (60k old replay, rwxmap answers applied),
extra-ruled (rwxmap-ruled old rows outside the replay), exam7 (rows the 0.4.0 product path got wrong; label = truth).
Answer files (data/r16/review/rwxmap-r13-answers/), applied in this order to old rows: answers.csv, answers-r15.csv, answers-d143-r13.csv, answers-d143-r15.csv.
Overlap rule: when an id is in an earlier and a later file, the two files' rwxmap_letter must be equal (the `label` column is only the candidate list's stale label); else --conflicts abort (default) stops,
--conflicts exclude drops those ids from the set entirely (neither applied nor kept) and lists them in summary.md.
Exam #8 vendors (gitbook, baserow, looker, wekan, shortcut/clubhouse, bitrise): old rows matching are dropped and counted; any in new/holdout/exam7 stops the build.
Outputs data/r16/train/: teacher-train-v2.{parquet,csv.gz}, SHA256SUMS, summary.md, d143 dev candidates in data/r16/labels/sonnet-recheck/d143-dev-candidates-for-rwxmap.csv."""
import argparse, glob, gzip, hashlib, json, os, re, subprocess, sys, tempfile
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import opkey
ap = argparse.ArgumentParser(); ap.add_argument('--conflicts', choices=['abort', 'exclude'], default='abort'); ap.add_argument('--no-exam7', action='store_true', help='build without the exam #7 rows; output name gets -noexam7'); A = ap.parse_args()
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); D = lambda *a: os.path.join(ROOT, *a)
RA = D('data/r16/review/rwxmap-r13-answers'); OUT = D('data/r16/train'); os.makedirs(OUT, exist_ok=True); NAME = 'teacher-train-v2' + ('-noexam7' if A.no_exam7 else '')
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
Y = {'r': 0, 'w': 1, 'x': 2}
EX8 = re.compile(r'gitbook|baserow|looker|wekan|shortcut|clubhouse|bitrise', re.I)
rd = lambda p, **k: pd.read_csv(p, keep_default_na=False, dtype=str, **k)

# ---- inputs
fin = pd.read_parquet(D('data/r16/labels/final/final-labels-r16.parquet')).fillna(''); assert len(fin) == 299600 and fin.op_id.is_unique
dev = pd.read_parquet(D('data/r16/labels/final/final-labels-r16-dev.parquet')).fillna(''); assert len(dev) == 4475
op = pd.read_parquet(D('data/r16/labels/opinions-r16.parquet')).fillna('').set_index('op_id', drop=False)
mech = pd.DataFrame([json.loads(l) for l in open(D('data/r16/labels/work/mech.jsonl'), encoding='utf-8')]).set_index('op_id'); assert mech.index.is_unique
old = pd.read_parquet(D('data/round15/train.parquet')).set_index('id', drop=False); assert old.id.is_unique and len(old) == 302211
rep = pd.read_csv(D('data/r16/pick/old-replay-ids.csv'), keep_default_na=False); assert len(rep) == 60000 and rep.id.is_unique and rep.id.isin(old.id).all()
assert (rep.label.values == old.loc[rep.id, 'label'].values).all() and (rep.weight.values == old.loc[rep.id, 'weight'].values).all()
ans = {}
for name, key, lab in [('answers.csv', 'r13_row_id', 'r13_label'), ('answers-r15.csv', 'op_id', 'r15_label'), ('answers-d143-r13.csv', 'op_id', 'label'), ('answers-d143-r15.csv', 'op_id', 'label'),
                       ('answers-d143.csv', 'op_id', 'label'), ('answers-h400.csv', 'op_id', None)]:
    a = rd(os.path.join(RA, name)); a = a.rename(columns={key: 'oid'}); assert a.oid.is_unique and a.rwxmap_letter.isin(list(Y)).all()
    if lab: a = a.rename(columns={lab: 'shown'})
    ans[name] = a.set_index('oid', drop=False)
SHAS = {n: sha(os.path.join(RA, n)) for n in ans}
assert [len(ans[n]) for n in ans] == [359, 263, 13, 237, 526, 400], [len(ans[n]) for n in ans]

# ---- A: new rows, D143 booking answers
new = fin.copy(); a = ans['answers-d143.csv']; assert a.index.isin(new.op_id).all()
m = new.op_id.isin(a.index); new['prior_label'] = new.label; new.loc[m, 'label'] = a.loc[new.op_id[m], 'rwxmap_letter'].values; new.loc[m, 'label_source'] = 'rwxmap'; new.loc[m, 'weight'] = 1.0
assert (a.shown.loc[new.op_id[m]].values == new.prior_label[m].values).all(), 'D143 shown label differs from the final label'
chg = {'answers-d143.csv': dict(rows=len(a), applied=int(m.sum()), changed=int((new.label != new.prior_label).sum()))}
new['part'] = 'new'; new['src'] = 'r16'; new['prior_label'] = new.prior_label

# ---- B: holdout 400
h = rd(D('data/r16/labels/disagree-sample-400.csv')); a = ans['answers-h400.csv']; assert len(h) == 400 and set(h.op_id) == set(a.index) and h.op_id.isin(op.index).all() and not set(h.op_id) & set(fin.op_id)
H = op.loc[h.op_id]; hold = pd.DataFrame(dict(op_id=h.op_id.values, label=a.loc[h.op_id, 'rwxmap_letter'].values, label_source='rwxmap', sonnet_confidence='', weight=1.0, part='holdout', bge_letter=H.bge_letter.values,
    r13_letter=H.r13_letter_modea.values, mech_letter=H.mech_letter.values, disagreement_type=H.disagreement_type.values, method=H.method.values, path=H.path.values, operationId=H.operationId.values, summary=H.summary.values,
    description=H.description.values, source=H.source.values, vendor_id=H.vendor_id.values, vendor_kind=H.vendor_kind.values)); hold['src'] = 'r16'; hold['prior_label'] = ''
newall = pd.concat([new, hold], ignore_index=True)
mt = mech.loc[newall.op_id]; newall['text'] = mt.text.values; newall['mech'] = mt.mech_letter.values; newall['rule'] = mt.mech_rule.values
newall['id'] = newall.op_id; newall['y'] = newall.label.map(Y).astype('int64'); newall['provider'] = newall.vendor_id; newall['vendor'] = newall.vendor_id; newall['status'] = 'r16'; newall['tier'] = 'none'; newall['r15_tier'] = ''

# ---- C: old replay + rwxmap rulings
cur = old[['label']].copy(); cur['ruled_by'] = ''; ruled = set(); conflicts = []; per = {}
order = ['answers.csv', 'answers-r15.csv', 'answers-d143-r13.csv', 'answers-d143-r15.csv']
for n in order:
    a = ans[n]; assert a.index.isin(old.index).all(), n + ': ids not in data/round15/train.parquet'
    ch = 0
    for i, r in a.iterrows():
        if i in ruled:
            prev = cur.at[i, 'label']
            if r.rwxmap_letter != prev: conflicts.append((i, n, r.rwxmap_letter, prev)); continue
        if r.shown != old.at[i, 'label'] and i not in ruled and n != 'answers-d143-r15.csv': raise SystemExit(f'{n} {i}: file label {r.shown} != train label {old.at[i, "label"]}')
        ch += r.rwxmap_letter != cur.at[i, 'label']; cur.at[i, 'label'] = r.rwxmap_letter; cur.at[i, 'ruled_by'] = n; ruled.add(i)
    per[n] = dict(rows=len(a), changed=int(ch), sha256=SHAS[n])
cf = pd.DataFrame(conflicts, columns=['id', 'later_file', 'later_file_letter', 'letter_after_earlier_file'])
if len(cf):
    print(cf.to_string())
    if A.conflicts == 'abort': raise SystemExit('STOP: later-file label column disagrees with the earlier file letter (listed above)')
    ruled -= set(cf.id); cur = cur.drop(index=cf.id); skip = set(cf.id)
else: skip = set()
rid = set(rep.id) - skip; extra_ids = sorted(ruled - set(rep.id))
oldrows = old.loc[[i for i in rep.id if i not in skip] + extra_ids].copy()
oldrows['label'] = cur.loc[oldrows.id, 'label'].values; ru = oldrows.id.isin(ruled).values
oldrows['label_source'] = ['rwxmap' if r else 'replay_' + s for r, s in zip(ru, oldrows.src)]
oldrows.loc[ru, 'weight'] = 1.0; oldrows['y'] = oldrows.label.map(Y).astype('int64')
oldrows['part'] = ['extra-ruled' if i not in rid else 'replay-' + s for i, s in zip(oldrows.id, oldrows.src)]
oldrows['prior_label'] = old.loc[oldrows.id, 'label'].values; oldrows['op_id'] = oldrows.id
for c in ('description', 'source', 'vendor_kind', 'sonnet_confidence'): oldrows[c] = ''
ex8 = oldrows.provider.str.contains(EX8) | oldrows.vendor.str.contains(EX8); dropped_ex8 = oldrows[ex8][['id', 'vendor', 'part']]; oldrows = oldrows[~ex8]

# ---- D: exam #7 mistakes (truth from rwxmap, product path mode a at 0.90 = rwxmap's official rows-a-cand)
EXD = os.path.expanduser('~/PycharmProjects/rwxmap/data/exam7-2026-11-19')
assert sha(os.path.join(EXD, 'truth.csv')) == 'af0fe041ff0bc2a372d915b63f2937a9f44a0808d911d821a1a4ffde851783ec'
tr7 = rd(os.path.join(EXD, 'truth.csv')); sc = rd(os.path.join(EXD, 'score', 'rows-a-cand.csv')); ops7 = rd(os.path.join(EXD, 'ops.csv'))
assert len(tr7) == len(sc) == len(ops7) == 1579 and (tr7.id.values == sc.id.values).all() and (ops7.id.values == sc.id.values).all() and (sc.truth.values == tr7.label.values).all()
bad = sc[sc.predicted != sc.truth].id.tolist(); assert len(bad) == 1579 - 1432, len(bad)   # exam #7 a-cand exact 1432 (findings.md)
e = ops7.set_index('id').loc[bad].reset_index(); e['label'] = tr7.set_index('id').loc[bad, 'label'].values
with tempfile.TemporaryDirectory() as tmp:
    fi, fo = os.path.join(tmp, 'in.jsonl'), os.path.join(tmp, 'out.jsonl')
    with open(fi, 'w', encoding='utf-8') as f:
        for r in e.itertuples(index=False): f.write(json.dumps(dict(id=r.id, method=r.method, path=r.path, operationId=r.operationId, summary=r.summary, description=r.description), ensure_ascii=False) + '\n')
    subprocess.run(['node', D('r15/regen_text.mjs'), '--tree', D('data/r16/scratch/rwxmap-1c25be1'), '--in', fi, '--out', fo], check=True, cwd=ROOT)
    o = [json.loads(l) for l in open(fo, encoding='utf-8')]
assert [x['id'] for x in o] == e.id.tolist()
ex = pd.DataFrame(dict(id=e.id, op_id=e.id, text=[x['text'] for x in o], label=e.label, y=e.label.map(Y).astype('int64'), status='exam7', summary=e.summary, mech=[x['class'] for x in o], rule=[x['rule'] for x in o], tier='none',
    method=e.method, provider=e.provider, vendor=e.provider, path=e.path, operationId=e.operationId, src='exam7', weight=1.0, r15_tier='', part='exam7', label_source='exam7', description=e.description,
    source='exam7', vendor_kind='', sonnet_confidence='', prior_label=sc.set_index('id').loc[bad, 'predicted'].values))

if A.no_exam7: ex = ex.iloc[0:0]
# ---- assemble
COLS = ['id', 'text', 'label', 'y', 'status', 'summary', 'mech', 'rule', 'tier', 'method', 'provider', 'vendor', 'path', 'operationId', 'src', 'weight', 'r15_tier',
        'op_id', 'part', 'label_source', 'sonnet_confidence', 'prior_label', 'description', 'source', 'vendor_kind']
parts = [oldrows[oldrows.part == 'replay-r13'], oldrows[oldrows.part == 'replay-r15'], oldrows[oldrows.part == 'extra-ruled'], newall[newall.part == 'new'], newall[newall.part == 'holdout'], ex]
T = pd.concat([p[COLS] for p in parts], ignore_index=True)
for c in ('jev_p', 'jev_pC', 'jev_pA', 'jev_pB'): T[c] = float('nan')
T['weight'] = T.weight.astype('float64')

# ---- checks
assert T.id.is_unique and T.op_id.is_unique, 'duplicate op ids'
assert T.label.isin(list(Y)).all() and (T.weight > 0).all() and (T.text.str.len() > 0).all() and (T.y == T.label.map(Y)).all()
for p in ('new', 'holdout', 'exam7'):
    s = T[T.part == p]; assert not (s.vendor.str.contains(EX8).any() or s.provider.str.contains(EX8).any()), f'exam #8 vendor in {p}'
assert not (T.vendor.str.contains(EX8) | T.provider.str.contains(EX8)).any()
devd = dev.copy(); assert not set(devd.op_id) & set(T.id), 'train/dev id overlap'
kd = set(opkey.k1(devd)); kt = opkey.k1(T.assign(operationId=T.operationId.fillna(''), summary=T.summary.fillna('')))
ov = [k in kd for k in kt]; assert not any(ov), f'{sum(ov)} train rows share an exact opkey with dev'
k2d = set(opkey.k2(devd)); k2ov = sum(k in k2d for k in opkey.k2(T))
T['dup_k1'] = pd.Series(kt).duplicated(keep=False).values
for n, c in per.items(): assert c['rows'] == len(ans[n])
found = {n: int(ans[n].index.isin(T.id).sum()) for n in ans}
for n in ans:
    if n in ('answers-d143.csv', 'answers-h400.csv'): assert found[n] == len(ans[n])
    else: assert found[n] + int(ans[n].index.isin(skip | set(dropped_ex8.id)).sum()) == len(ans[n]), n
# rows with a ruling must carry the (last) rwxmap letter
lastl = {}
for n in order + ['answers-d143.csv', 'answers-h400.csv']:
    for i, r in ans[n].iterrows():
        if i not in skip: lastl[i] = r.rwxmap_letter
rr = T[T.label_source == 'rwxmap']; assert (rr.label.values == [lastl[i] for i in rr.id]).all() and (rr.weight == 1.0).all()
assert len(rr) == len(lastl) - len(set(lastl) & set(dropped_ex8.id)), 'not every ruled row is in the set'
T.drop(columns=['dup_k1']).to_parquet(os.path.join(OUT, NAME + '.parquet'), index=False)
T.drop(columns=['dup_k1']).to_csv(os.path.join(OUT, NAME + '.csv.gz'), index=False, compression=dict(method='gzip', mtime=0))

# ---- D143 dev candidates (dev labels untouched)
t = (devd.path + ' ' + devd.operationId + ' ' + devd.summary).str.lower()
dc = devd[(devd.method == 'POST') & t.str.contains(r'booking|reservation|(?<![a-z])reserve') & (devd.label != 'x')][['op_id', 'method', 'path', 'operationId', 'summary', 'description', 'label']]
dcp = D('data/r16/labels/sonnet-recheck/d143-dev-candidates-for-rwxmap.csv'); dc.to_csv(dcp, index=False); dsha = sha(dcp)

# ---- dev v2: D143 dev answers (old dev file untouched)
da = rd(os.path.join(RA, 'answers-d143-dev.csv')).set_index('op_id', drop=False); DSHA = sha(os.path.join(RA, 'answers-d143-dev.csv'))
assert DSHA == '9364587d81969b6486dad19b3d3f7321735f3d177f44fd3b8a0ad0ea322d7099' and len(da) == 9 and set(da.op_id) == set(dc.op_id) and da.rwxmap_letter.isin(list(Y)).all()
dv2 = dev.copy(); dv2['prior_label'] = dv2.label; mm = dv2.op_id.isin(da.index)
assert (da.label.loc[dv2.op_id[mm]].values == dv2.label[mm].values).all()
dv2.loc[mm, 'label'] = da.rwxmap_letter.loc[dv2.op_id[mm]].values; dv2.loc[mm, 'label_source'] = 'rwxmap'
assert int(mm.sum()) == 9 and int((dv2.label != dv2.prior_label).sum()) == 7 and int(((dv2.prior_label == 'w') & (dv2.label == 'x')).sum()) == 7 and int((dv2.label[mm] == 'w').sum()) == 2, 'expected 7 w->x and 2 stay w'
FD = D('data/r16/labels/final'); dv2.to_parquet(os.path.join(FD, 'final-labels-r16-dev-v2.parquet'), index=False); dv2.to_csv(os.path.join(FD, 'final-labels-r16-dev-v2.csv.gz'), index=False, compression=dict(method='gzip', mtime=0))
keep = [l for l in open(os.path.join(FD, 'SHA256SUMS')).read().splitlines() if 'dev-v2' not in l]
open(os.path.join(FD, 'SHA256SUMS'), 'w').write('\n'.join(keep + [f'{sha(os.path.join(FD, n))}  {n}' for n in ('final-labels-r16-dev-v2.csv.gz', 'final-labels-r16-dev-v2.parquet')]) + '\n')
# ---- summary
def md(d): return '\n'.join(['| ' + ' | '.join(map(str, d.columns)) + ' |', '|' + '---|' * len(d.columns)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in d.itertuples(index=False)])
def tbl(s): return ', '.join(f'{k} {v:,}' for k, v in s.items())
L = ['# Round 16 teacher training set v2', '', f'Rows {len(T):,}. Made by `r16/build_teacher_train.py`. Text = model input text (lean format 1, rwxmap 1c25be1 mechanical); no soft targets here (teacher probabilities come from `train/teacher_probs.py`).', '']
L += ['## By part', '', tbl(T.part.value_counts().reindex(['new', 'holdout', 'replay-r13', 'replay-r15', 'extra-ruled', 'exam7']).fillna(0).astype(int)), '', '## By letter', '', tbl(T.label.value_counts()), '']
L += ['## By label_source', '', tbl(T.label_source.value_counts()), '', '## By weight', '', tbl(T.weight.value_counts().sort_index()) + f'; total {T.weight.sum():,.1f}', '']
L += ['## Letter by part', '', md(T.groupby(['part', 'label']).size().unstack(fill_value=0).reset_index()), '']
L += ['## Answer files', '', '| file | rows | in set | changed vs label before it | sha256 |', '|---|---|---|---|---|']
for n in ans:
    ch_ = per.get(n, chg.get(n, {})).get('changed', '')
    if n == 'answers-h400.csv': ch_ = 'n/a (new rows)'
    L.append(f'| {n} | {len(ans[n])} | {found[n]} | {ch_} | `{SHAS[n]}` |')
L += ['', f'Extra-ruled rows (rwxmap ruled, not in the 60k replay, added as old rows): {len(extra_ids)} (r13 {sum(i.startswith("ag-") for i in extra_ids)}, r15 {sum(not i.startswith("ag-") for i in extra_ids)}).',
      f'Old rows dropped for exam #8 vendor (clubhouse): {len(dropped_ex8)} ({dropped_ex8.part.value_counts().to_dict()}); vendors {sorted(dropped_ex8.vendor.unique())}.',
      f'Overlap conflicts (later file rwxmap_letter != earlier file rwxmap_letter): {len(cf)} ({"excluded from the set" if len(cf) else "none"}).']
if len(cf): L += ['', md(cf)]
L += ['', f'Exam #7: {len(ex)} rows where rwxmap rows-a-cand predicted != truth (1579 - 1432); label = truth (`truth.csv` sha256 af0fe041...); product path (mode a 0.90, the shipped 0.4.0 letter). Letter by prior: ' + tbl(ex.prior_label.value_counts()) + '.',
      f'Checks passed: unique ids; no train/dev overlap by id or exact opkey (method, path, operationId, summary); rows sharing the looser norm key with dev (info): {k2ov}; letters r/w/x; weights > 0; no exam #8 vendor; every ruling applied.',
      f'Exact-opkey duplicates inside the set (info, kept; all in old rows, none in new, holdout or exam7): {int(T.dup_k1.sum())} rows ({T[T.dup_k1].part.value_counts().to_dict()}).',
      f'Dev v2 (`data/r16/labels/final/final-labels-r16-dev-v2.*`, old dev file untouched): answers-d143-dev.csv sha256 `{DSHA}`, 9 rows applied (label_source rwxmap), 7 w to x, 2 stay w; prior_label kept.',
      f'D143 dev candidates: {len(dc)} rows, `data/r16/labels/sonnet-recheck/d143-dev-candidates-for-rwxmap.csv` sha256 `{dsha}` (rule: POST, path+operationId+summary lowercased contains booking, reservation or a word starting reserve, label != x; the word-start form reproduces the 526 pick candidates exactly).']
open(os.path.join(OUT, 'summary.md' if not A.no_exam7 else 'summary-noexam7.md'), 'w').write('\n'.join(L) + '\n')
with open(os.path.join(OUT, 'SHA256SUMS' if not A.no_exam7 else 'SHA256SUMS-noexam7'), 'w') as f:
    for n in (NAME + '.parquet', NAME + '.csv.gz', 'summary.md'): f.write(f'{sha(os.path.join(OUT, n))}  {n}\n')
print('\n'.join(L))
