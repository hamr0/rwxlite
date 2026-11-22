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
ap = argparse.ArgumentParser(); ap.add_argument('--conflicts', choices=['abort', 'exclude'], default='abort'); ap.add_argument('--no-exam7', action='store_true', help='build without the exam #7 rows; output name gets -noexam7')
ap.add_argument('--v3', action='store_true', help='teacher-train-v3 + dev-v3 (prereg-r16-small-runs.md section 14): rebuild v2 in memory (asserted equal to the v2 file), apply rwxmap unsure answers (answers-train.csv, weight 1.0) and the Sonnet-sure x3 weight; writes only v3 files + summary-v3.md + SHA256SUMS-v3, leaves every v2 output untouched')
ap.add_argument('--old-pool', choices=['replay', 'all'], default='replay', help="'all' = ALL 302,211 old rows (minus exam #8 vendors) instead of the 60k replay + extra-ruled, same rwxmap rulings and weights; writes only <name>-allold.parquet + SHA256SUMS-allold and exits before the dev/summary part (prereg-r16-small-runs.md)"); A = ap.parse_args()
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); D = lambda *a: os.path.join(ROOT, *a)
RA = D('data/r16/review/rwxmap-r13-answers'); OUT = D('data/r16/train'); os.makedirs(OUT, exist_ok=True); NAME = ('teacher-train-v3' if A.v3 else 'teacher-train-v2') + ('-noexam7' if A.no_exam7 else '') + ('-allold' if A.old_pool == 'all' else '')
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
new['weight_reason'] = ''; dch = (new.label != new.prior_label).values; new.loc[dch, 'weight'] = 3.0; new.loc[dch, 'weight_reason'] = 'd143_new'   # user ruling: rows a D143 file changed get weight 3 (r15 D141 precedent)
assert (a.shown.loc[new.op_id[m]].values == new.prior_label[m].values).all(), 'D143 shown label differs from the final label'
chg = {'answers-d143.csv': dict(rows=len(a), applied=int(m.sum()), changed=int((new.label != new.prior_label).sum()))}
new['part'] = 'new'; new['src'] = 'r16'; new['prior_label'] = new.prior_label

# ---- B: holdout 400
h = rd(D('data/r16/labels/disagree-sample-400.csv')); a = ans['answers-h400.csv']; assert len(h) == 400 and set(h.op_id) == set(a.index) and h.op_id.isin(op.index).all() and not set(h.op_id) & set(fin.op_id)
H = op.loc[h.op_id]; hold = pd.DataFrame(dict(op_id=h.op_id.values, label=a.loc[h.op_id, 'rwxmap_letter'].values, label_source='rwxmap', sonnet_confidence='', weight=1.0, part='holdout', bge_letter=H.bge_letter.values,
    r13_letter=H.r13_letter_modea.values, mech_letter=H.mech_letter.values, disagreement_type=H.disagreement_type.values, method=H.method.values, path=H.path.values, operationId=H.operationId.values, summary=H.summary.values,
    description=H.description.values, source=H.source.values, vendor_id=H.vendor_id.values, vendor_kind=H.vendor_kind.values)); hold['src'] = 'r16'; hold['weight_reason'] = ''; hold['prior_label'] = ''
newall = pd.concat([new, hold], ignore_index=True)
mt = mech.loc[newall.op_id]; newall['text'] = mt.text.values; newall['mech'] = mt.mech_letter.values; newall['rule'] = mt.mech_rule.values
newall['id'] = newall.op_id; newall['y'] = newall.label.map(Y).astype('int64'); newall['provider'] = newall.vendor_id; newall['vendor'] = newall.vendor_id; newall['status'] = 'r16'; newall['tier'] = 'none'; newall['r15_tier'] = ''

# ---- C: old replay + rwxmap rulings
d143chg = {}; cur = old[['label']].copy(); cur['ruled_by'] = ''; ruled = set(); conflicts = []; per = {}
order = ['answers.csv', 'answers-r15.csv', 'answers-d143-r13.csv', 'answers-d143-r15.csv']
for n in order:
    a = ans[n]; assert a.index.isin(old.index).all(), n + ': ids not in data/round15/train.parquet'
    ch = 0
    for i, r in a.iterrows():
        if i in ruled:
            prev = cur.at[i, 'label']
            if r.rwxmap_letter != prev: conflicts.append((i, n, r.rwxmap_letter, prev)); continue
        if r.shown != old.at[i, 'label'] and i not in ruled and n != 'answers-d143-r15.csv': raise SystemExit(f'{n} {i}: file label {r.shown} != train label {old.at[i, "label"]}')
        if n.startswith('answers-d143') and r.rwxmap_letter != cur.at[i, 'label']: d143chg[i] = n
        ch += r.rwxmap_letter != cur.at[i, 'label']; cur.at[i, 'label'] = r.rwxmap_letter; cur.at[i, 'ruled_by'] = n; ruled.add(i)
    per[n] = dict(rows=len(a), changed=int(ch), sha256=SHAS[n])
cf = pd.DataFrame(conflicts, columns=['id', 'later_file', 'later_file_letter', 'letter_after_earlier_file'])
if len(cf):
    print(cf.to_string())
    if A.conflicts == 'abort': raise SystemExit('STOP: later-file label column disagrees with the earlier file letter (listed above)')
    ruled -= set(cf.id); cur = cur.drop(index=cf.id); skip = set(cf.id)
else: skip = set()
rid = set(rep.id) - skip; extra_ids = sorted(ruled - set(rep.id))
oldrows = old.loc[[i for i in old.index if i not in skip] if A.old_pool == 'all' else [i for i in rep.id if i not in skip] + extra_ids].copy()
oldrows['label'] = cur.loc[oldrows.id, 'label'].values; ru = oldrows.id.isin(ruled).values
oldrows['label_source'] = ['rwxmap' if r else 'replay_' + s for r, s in zip(ru, oldrows.src)]
oldrows.loc[ru, 'weight'] = 1.0; oldrows['weight_reason'] = ['r15_weight' if w == 3.0 and not r else '' for w, r in zip(oldrows.weight, ru)]
for i, n in d143chg.items():
    if i in oldrows.index: oldrows.at[i, 'weight'] = 3.0; oldrows.at[i, 'weight_reason'] = 'd143_' + n.split('-')[-1].split('.')[0]
oldrows['y'] = oldrows.label.map(Y).astype('int64')
oldrows['part'] = [('old-' if A.old_pool == 'all' else 'extra-ruled') if i not in rid else 'replay-' + s for i, s in zip(oldrows.id, oldrows.src)]
if A.old_pool == 'all': oldrows['part'] = [p if p.startswith('replay-') else p + oldrows.at[i, 'src'] for p, i in zip(oldrows.part, oldrows.id)]
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
    method=e.method, provider=e.provider, vendor=e.provider, path=e.path, operationId=e.operationId, src='exam7', weight=3.0, weight_reason='exam7', r15_tier='', part='exam7', label_source='exam7', description=e.description,
    source='exam7', vendor_kind='', sonnet_confidence='', prior_label=sc.set_index('id').loc[bad, 'predicted'].values))

if A.no_exam7: ex = ex.iloc[0:0]
# ---- assemble
COLS = ['id', 'text', 'label', 'y', 'status', 'summary', 'mech', 'rule', 'tier', 'method', 'provider', 'vendor', 'path', 'operationId', 'src', 'weight', 'r15_tier',
        'op_id', 'weight_reason', 'part', 'label_source', 'sonnet_confidence', 'prior_label', 'description', 'source', 'vendor_kind']
parts = [oldrows[oldrows.part == 'replay-r13'], oldrows[oldrows.part == 'replay-r15'], oldrows[oldrows.part == 'extra-ruled'], newall[newall.part == 'new'], newall[newall.part == 'holdout'], ex]
if A.old_pool == 'all': parts = [oldrows, newall[newall.part == 'new'], newall[newall.part == 'holdout'], ex]
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
rr = T[T.label_source == 'rwxmap']; assert (rr.label.values == [lastl[i] for i in rr.id]).all() and (rr.weight == rr.weight_reason.map(lambda x: 3.0 if x.startswith('d143') else 1.0)).all()
assert len(rr) == len(lastl) - len(set(lastl) & set(dropped_ex8.id)), 'not every ruled row is in the set'

# ---- v3 (section 14): the v2 set rebuilt above must equal the v2 file; then rwxmap unsure answers + Sonnet-sure x3 weight; dev v3. Writes v3 files only and exits.
if A.v3:
    assert not A.no_exam7 and A.old_pool == 'replay'
    v2 = pd.read_parquet(os.path.join(OUT, 'teacher-train-v2.parquet')); assert sha(os.path.join(OUT, 'teacher-train-v2.parquet')) == '9e1f37003cca905ef1cb869fb59bba480abbf0a9f86dce22133b77543e8a1870'
    assert v2.drop(columns=['dup_k1'], errors='ignore').equals(T.drop(columns=['dup_k1'])), 'rebuilt v2 differs from the v2 file'
    UP = D('data/r16/review/rwxmap-unsure'); U = rd(os.path.join(UP, 'answers-train.csv')); DV3 = rd(os.path.join(UP, 'answers-dev-v3.csv'))
    assert sha(os.path.join(UP, 'answers-train.csv')) == '92daa73bc69b9302591b580a26609a029716734f7cf8449bb0f758c28459ffff' and sha(os.path.join(UP, 'answers-dev-v3.csv')) == 'c123b896b56b338c7e16f6704570ed521d6da2d8b5b4ff3286fedc404d505a9c'
    assert len(U) == 3791 and U.op_id.is_unique and len(DV3) == 62 and DV3.op_id.is_unique and U.rwxmap_letter.isin(list(Y)).all() and DV3.rwxmap_letter.isin(list(Y)).all()
    T3 = T.copy(); ix = T3.set_index('op_id', drop=False).index; assert ix.is_unique; assert U.op_id.isin(T3.op_id).all(), 'not all 3,791 unsure rows found'
    mu = T3.op_id.isin(U.op_id).values; uu = U.set_index('op_id'); assert mu.sum() == 3791
    assert ((T3.label_source[mu] == 'sonnet') & (T3.sonnet_confidence[mu] == 'unsure') & (T3.weight[mu] == 0.3)).all(), 'answers-train rows must all be Sonnet-unsure at 0.3'
    assert (uu.sonnet_letter.loc[T3.op_id[mu]].values == T3.label[mu].values).all(), 'answers-train sonnet_letter differs from the v2 label'
    v2_unsure_total = int(((T3.label_source == 'sonnet') & (T3.sonnet_confidence == 'unsure')).sum()); assert v2_unsure_total == 3791
    old_lab = T3.label.copy(); T3.loc[mu, 'label'] = uu.rwxmap_letter.loc[T3.op_id[mu]].values; T3.loc[mu, 'label_source'] = 'rwxmap'; T3.loc[mu, 'weight'] = 1.0   # prior_label kept
    T3['y'] = T3.label.map(Y).astype('int64'); unsure_changed = int((T3.label[mu] != old_lab[mu]).sum())
    ms = ((T3.label_source == 'sonnet') & (T3.sonnet_confidence == 'sure')).values; assert (T3.weight[ms] == 1.0).all() and (T3.weight_reason[ms] == '').all()
    T3.loc[ms, 'weight'] = 3.0; T3.loc[ms, 'weight_reason'] = 'sonnet_sure_x3'; n_sure = int(ms.sum())
    left = T3[(T3.label_source == 'sonnet') & (T3.sonnet_confidence == 'unsure')]; assert len(left) == 0, f'{len(left)} Sonnet-unsure rows left'
    assert (T3.weight.isin([1.0, 3.0])).all()
    # hard checks again on v3
    assert T3.id.is_unique and T3.op_id.is_unique and T3.label.isin(list(Y)).all() and (T3.weight > 0).all() and (T3.text.str.len() > 0).all() and (T3.y == T3.label.map(Y)).all() and len(T3) == len(T)
    assert not (T3.vendor.str.contains(EX8) | T3.provider.str.contains(EX8)).any(), 'exam #8 vendor'
    assert not set(devd.op_id) & set(T3.id), 'train/dev id overlap'
    kd3 = set(opkey.k1(devd)); assert not any(k in kd3 for k in opkey.k1(T3.assign(operationId=T3.operationId.fillna(''), summary=T3.summary.fillna('')))), 'exact opkey overlap with dev'
    for c in ('id', 'text', 'summary', 'method', 'path', 'operationId', 'vendor', 'part', 'src'): assert (T3[c].values == T[c].values).all(), c
    T3.to_parquet(os.path.join(OUT, NAME + '.parquet'), index=False); T3.to_csv(os.path.join(OUT, NAME + '.csv.gz'), index=False, compression=dict(method='gzip', mtime=0))
    # dev v3: from dev-v2; label_source rwxmap for the 62; prior_label (v1, before D143) kept, prior_label_v2 = the v2 label, d143_touched marks the 9 D143 rows, unsure62 marks the 62
    FD = D('data/r16/labels/final'); dv2f = os.path.join(FD, 'final-labels-r16-dev-v2.parquet'); assert sha(dv2f) == 'ef5955787e88e5d4b4ceeaaf93de35026c678c67b86d51e710b275a7534e6e69'
    dv = pd.read_parquet(dv2f).fillna(''); assert len(dv) == 4475 and DV3.op_id.isin(dv.op_id).all(); dd = DV3.set_index('op_id'); m3 = dv.op_id.isin(dd.index).values
    assert (dd.sonnet_letter.loc[dv.op_id[m3]].values == dv.label[m3].values).all() and (dv.label_source[m3] == 'sonnet').all(), 'dev-v3 answers must start from sonnet rows with the dev-v2 label'
    d9ids = set(rd(os.path.join(RA, 'answers-d143-dev.csv')).op_id); assert len(d9ids) == 9 and not d9ids & set(dd.index)
    dv3 = dv.copy(); dv3['prior_label_v2'] = dv.label; dv3['d143_touched'] = dv3.op_id.isin(d9ids); dv3['unsure62'] = m3
    dv3.loc[m3, 'label'] = dd.rwxmap_letter.loc[dv.op_id[m3]].values; dv3.loc[m3, 'label_source'] = 'rwxmap'
    dchg = pd.crosstab(dv.label[m3].values, dv3.label[m3].values); dev_changed = int((dv3.label != dv3.prior_label_v2).sum()); assert dev_changed == int((dd.changed == 'yes').sum()) == 23
    assert dv3.op_id.is_unique and dv3.label.isin(list(Y)).all()
    dv3.to_parquet(os.path.join(FD, 'final-labels-r16-dev-v3.parquet'), index=False); dv3.to_csv(os.path.join(FD, 'final-labels-r16-dev-v3.csv.gz'), index=False, compression=dict(method='gzip', mtime=0))
    keep = [l for l in open(os.path.join(FD, 'SHA256SUMS')).read().splitlines() if 'dev-v3' not in l]
    open(os.path.join(FD, 'SHA256SUMS'), 'w').write('\n'.join(keep + [f'{sha(os.path.join(FD, n))}  {n}' for n in ('final-labels-r16-dev-v3.csv.gz', 'final-labels-r16-dev-v3.parquet')]) + '\n')
    def md(d): return '\n'.join(['| ' + ' | '.join(map(str, d.columns)) + ' |', '|' + '---|' * len(d.columns)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in d.itertuples(index=False)])
    def tbl(s): return ', '.join(f'{k} {v:,}' for k, v in s.items())
    L = ['# Round 16 teacher training set v3', '', f'Rows {len(T3):,}. Made by `r16/build_teacher_train.py --v3`. v2 rebuilt in memory (asserted equal to `teacher-train-v2.parquet` sha256 `9e1f3700...`), then: (1) `data/r16/review/rwxmap-unsure/answers-train.csv` (sha256 `92daa73b...`, 3,791 rows) applied to the 3,791 Sonnet-unsure rows (all found; all were label_source sonnet, unsure, weight 0.3): label = rwxmap_letter, label_source rwxmap, weight 1.0, prior_label kept; {unsure_changed} of them changed letter vs Sonnet; (2) contested rows with label_source sonnet and sonnet_confidence sure: weight 3.0, weight_reason sonnet_sure_x3 ({n_sure:,} rows). Every other v2 weight kept (r15 replay 3.0, d143 3.0, exam7 3.0, likely 1.0). No row is Sonnet-unsure any more (asserted: 0 left).'.replace('{unsure_changed}', str(unsure_changed)).replace('{n_sure:,}', f'{n_sure:,}'), '']
    L += ['## By part', '', tbl(T3.part.value_counts().reindex(['new', 'holdout', 'replay-r13', 'replay-r15', 'extra-ruled', 'exam7']).fillna(0).astype(int)), '', '## By letter', '', tbl(T3.label.value_counts()), f'(v2: {tbl(T.label.value_counts())}; letter changes v2 to v3: {unsure_changed})', '']
    L += ['## By label_source', '', tbl(T3.label_source.value_counts()), '', '## By weight', '', tbl(T3.weight.value_counts().sort_index()) + f'; total {T3.weight.sum():,.1f} (v2 total {T.weight.sum():,.1f})', '']
    L += ['## By weight_reason', '', tbl(T3.weight_reason.replace('', '(none, 1.0 or 3.0 plain)').value_counts()), '', '## Letter by part', '', md(T3.groupby(['part', 'label']).size().unstack(fill_value=0).reset_index()), '', '## The 3,791 unsure rows, Sonnet letter (rows) to rwxmap letter (columns)', '', md(pd.crosstab(old_lab[mu].values, T3.label[mu].values).rename_axis('sonnet').reset_index()), '']
    L += ['## Dev v3', '', f'`final-labels-r16-dev-v3.{{parquet,csv.gz}}` from dev-v2 (sha256 `ef595578...`) plus `answers-dev-v3.csv` (sha256 `c123b896...`, 62 rows, all found, all label_source sonnet with the v2 label; label_source becomes rwxmap): {dev_changed} letters changed vs dev-v2 ({int(((dv.label[m3] == "w").values & (dv3.label[m3] == "x").values).sum())} w to x, {int(((dv.label[m3] == "x").values & (dv3.label[m3] == "w").values).sum())} x to w). Extra columns: prior_label (v1, before D143, unchanged), prior_label_v2, d143_touched (the 9 D143 rows), unsure62. Dev letters v3: {tbl(dv3.label.value_counts())} (v2: {tbl(dv.label.value_counts())}). answers-dev.csv (v1) and answers-dev-v2.csv are superseded and not used.', '']
    L += [f'Checks passed: unique ids; no train/dev overlap by id or exact opkey; no exam #8 vendor; letters r/w/x; weights > 0 (all 1.0 or 3.0); all 3,791 unsure rows found; no Sonnet-unsure row left; text, ids, parts unchanged from v2.']
    open(os.path.join(OUT, 'summary-v3.md'), 'w').write('\n'.join(L) + '\n')
    open(os.path.join(OUT, 'SHA256SUMS-v3'), 'w').write(''.join(f'{sha(os.path.join(OUT, n))}  {n}\n' for n in (NAME + '.parquet', NAME + '.csv.gz', 'summary-v3.md')))
    print('\n'.join(L)); sys.exit(0)
T.drop(columns=['dup_k1']).to_parquet(os.path.join(OUT, NAME + '.parquet'), index=False)
if A.old_pool == 'all':
    open(os.path.join(OUT, 'SHA256SUMS-allold'), 'w').write(f"{sha(os.path.join(OUT, NAME + '.parquet'))}  {NAME}.parquet\n"); print(len(T), T.part.value_counts().to_dict(), T.label.value_counts().to_dict(), f'weight total {T.weight.sum():,.1f}'); sys.exit(0)
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
L += ['## Weight 3.0 by reason (weight 3.0 rows: ' + str(int((T.weight == 3.0).sum())) + ')', '', tbl(T[T.weight == 3.0].weight_reason.value_counts()), '', '## Letter by part', '', md(T.groupby(['part', 'label']).size().unstack(fill_value=0).reset_index()), '']
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
    for n in (NAME + '.parquet', NAME + '.csv.gz', 'summary.md' if not A.no_exam7 else 'summary-noexam7.md'): f.write(f'{sha(os.path.join(OUT, n))}  {n}\n')
print('\n'.join(L))
