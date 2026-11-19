"""Round 15: apply the D141 relabel (rwxmap 54355e1, BRIEF-v4-addendum-D141) to the final labels.
  python3 -I r15/label_d141.py
Reads data/r15/labels/final-labels-r15.parquet and d141/merged.csv (Sonnet blind relabel of the pattern-net candidates; `new` is the applied letter).
Writes final-labels-r15-d141.parquet/.csv.gz and d141-report.json. Never touches final-labels-r15.*.
label = new for candidates; tier unchanged; weight unchanged except changed rows whose new letter came from an unsure Sonnet answer -> 0.3."""
import csv, hashlib, json, collections
import pandas as pd
L = 'data/r15/labels/'
D = L + 'd141/'
src = pd.read_parquet(L + 'final-labels-r15.parquet')
m = pd.read_csv(D + 'merged.csv', keep_default_na=False)
assert len(m) == 9740 and m.op_id.is_unique and set(m.op_id) <= set(src.op_id)
assert m.new.isin(list('rwx')).all() and m.confidence.isin(['sure', 'likely', 'unsure']).all()
RK = {'r': 0, 'w': 1, 'x': 2}
# pass 2: Opus on family a/b/d candidates Sonnet under-applied; final letter = stricter of merged `new` and the pass2 letter
csv.field_size_limit(10**9)
p2 = {}
for f in ('out-a.csv', 'out-b.csv'):
    for r in csv.DictReader(open(D + 'pass2/' + f, newline='', encoding='utf-8')):
        assert r['letter'] in RK and r['op_id'] not in p2, r
        p2[r['op_id']] = r
assert len(p2) == 395 and set(p2) <= set(m.op_id)
m = m.set_index('op_id', drop=False)
m['pass2'] = m.op_id.isin(p2)
m['pass2_letter'] = [p2[i]['letter'] if i in p2 else '' for i in m.op_id]
m['new1'] = m.new
m['new'] = [max(n, p, key=RK.get) if p else n for n, p in zip(m.new, m.pass2_letter)]
m['conf_src'] = [p2[i]['confidence'] if p and RK[p] > RK[n] else c for i, n, p, c in zip(m.op_id, m.new1, m.pass2_letter, m.confidence)]
m['chg'] = m.new != m.label
mm = m
out = src.copy()
out['label_pre_d141'] = out.label
cand = out.op_id.isin(mm.index)
out['d141_candidate'] = cand
out['d141_pass2'] = out.op_id.map(mm.pass2).fillna(False).astype(bool)
out['d141_pass2_letter'] = out.op_id.map(mm.pass2_letter).fillna('')
out['d141_families'] = out.op_id.map(mm.families).fillna('')
out['label'] = [mm.new[i] if c else l for i, c, l in zip(out.op_id, cand, out.label)]
out['d141_changed'] = out.label != out.label_pre_d141
assert (out.d141_changed == out.op_id.map(mm.chg).fillna(False).astype(bool)).all()
assert (m.new1 != m.label).sum() == 1274  # the pre-pass2 result is unchanged
assert (out.loc[cand, 'label_pre_d141'].values == mm.loc[out.op_id[cand], 'label'].values).all()
unsure_chg = out.d141_changed & (out.op_id.map(mm.conf_src) == 'unsure')
out['weight_pre_d141'] = out.weight
out.loc[unsure_chg, 'weight'] = 0.3
out = out.drop(columns='weight_pre_d141')
out.to_parquet(L + 'final-labels-r15-d141.parquet', index=False)
out.to_csv(L + 'final-labels-r15-d141.csv.gz', index=False)
ch = out[out.d141_changed]
fam = collections.Counter()
for f in ch.d141_families:
    for c in f: fam[c] += 1
mix = lambda s: {k: int(v) for k, v in s.value_counts().items()}
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
rep = {'rows': len(out), 'candidates': int(cand.sum()), 'changed': int(len(ch)),
       'changed_by_family_any': dict(sorted(fam.items())),
       'changed_by_family_combo': ch.d141_families.value_counts().to_dict(),
       'candidates_by_family_combo': out[cand].d141_families.value_counts().to_dict(),
       'changed_by_move': {f'{a}->{b}': int(n) for (a, b), n in ch.groupby(['label_pre_d141', 'label']).size().items()},
       'changed_by_family_and_move': {f: {f'{a}->{b}': int(n) for (a, b), n in g.groupby(['label_pre_d141', 'label']).size().items()} for f, g in ch.assign(f=ch.d141_families).groupby('f')},
       'changed_by_tier': ch.tier.value_counts().to_dict(),
       'letter_counts_before': mix(out.label_pre_d141), 'letter_counts_after': mix(out.label),
       'letter_mix_before': {k: round(v / len(out), 4) for k, v in out.label_pre_d141.value_counts().items()},
       'letter_mix_after': {k: round(v / len(out), 4) for k, v in out.label.value_counts().items()},
       'weight_changed_rows': int((out.weight != src.weight).sum()), 'weight_total_before': round(src.weight.sum(), 1), 'weight_total_after': round(out.weight.sum(), 1),
       'unsure_changed_rows': int(unsure_chg.sum()),
       'pass2': {'rows': len(p2), 'letter_raised_vs_sonnet': int((m.new != m.new1).sum()),
                 'raised_by_family': m[m.new != m.new1].families.value_counts().to_dict(),
                 'raised_by_move': {f'{a}->{b}': int(n) for (a, b), n in m[m.new != m.new1].groupby(['new1', 'new']).size().items()},
                 'rows_by_family': m[m.pass2].families.value_counts().to_dict(),
                 'pass2_letter_mix': m[m.pass2].pass2_letter.value_counts().to_dict(),
                 'changed_vs_pre_d141_labels': int((m.pass2 & m.chg).sum()), 'changed_total_after_pass2': int(len(ch)),
                 'changed_by_family_any_after_pass2': dict(sorted(fam.items()))},
       'sha256': {f: sha(L + f) for f in ('final-labels-r15-d141.parquet', 'final-labels-r15-d141.csv.gz')},
       'sha256_unmodified_inputs': {f: sha(L + f) for f in ('final-labels-r15.parquet', 'final-labels-r15.csv.gz')}}
json.dump(rep, open(L + 'd141-report.json', 'w'), indent=1)
print(json.dumps(rep, indent=1))
