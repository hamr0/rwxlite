"""Round 16 small comparison runs: build the two training sets (docs/product/prereg-r16-small-runs.md section 3). Deterministic (seed 16), no training.
  data/r16/scratch/venv/bin/python -I r16/build_small_runs.py
Inputs (sha256 asserted): data/r16/train/teacher-train-v2.parquet, data/r16/train/teacher-train-v2-allold.parquet (build_teacher_train.py --old-pool all).
Scale 1/10 of the full runs, same ratios. Exam #7 mistakes and the 400 holdout rows are left out of both sets (same in both arms; the full runs add them).
  NEW      = 10% uniform row sample of the 299,600 new rows (all weights/labels as in v2).
  A-pool   = v2 old rows (replay-r13, replay-r15, extra-ruled; 60,389) ; A-old = 10% of it, stratified by part.
  B-pool   = ALL old rows (allold file); B-old = A-old + a 10% stratified sample of the remaining old rows so that |B-old| = round(0.1 * all old). So B contains A (nested): the only difference is the extra random old rows.
  set-A = NEW + A-old (20%-replay arm) ; set-B = NEW + B-old (all-old arm). Row order = sorted by id; train.parquet for finetune.py is a copy of the set."""
import hashlib, json, os, sys
import pandas as pd
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); P = lambda *a: os.path.join(R, *a)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest(); SEED = 16; FRAC = 0.1
V2, AL = P('data/r16/train/teacher-train-v2.parquet'), P('data/r16/train/teacher-train-v2-allold.parquet')
assert sha(V2) == '9e1f37003cca905ef1cb869fb59bba480abbf0a9f86dce22133b77543e8a1870'
v2 = pd.read_parquet(V2); al = pd.read_parquet(AL); OUT = P('data/r16/small'); os.makedirs(OUT, exist_ok=True)
new = v2[v2.part == 'new'].sort_values('id'); assert len(new) == 299600
apool = v2[v2.part.isin(['replay-r13', 'replay-r15', 'extra-ruled'])].sort_values('id')
old_all = al[al.part.str.startswith('replay-') | al.part.str.startswith('old-')].sort_values('id')
assert set(apool.id) <= set(old_all.id) and not set(old_all.id) & set(new.id)
cmp = ['label', 'weight', 'text']; m = apool.set_index('id')[cmp].join(old_all.set_index('id')[cmp], rsuffix='_all'); assert all((m[c] == m[c + '_all']).all() for c in cmp), 'pool rows differ between v2 and allold'
strat = lambda df, key, n_from: pd.concat([g.sample(frac=FRAC, random_state=SEED) for _, g in df.groupby(key, sort=True)])
newS = new.sample(frac=FRAC, random_state=SEED)
aold = strat(apool, 'part', None)
rest = old_all[~old_all.id.isin(apool.id)]; n_b = round(FRAC * len(old_all)) - len(aold)
bx = rest.groupby('src', sort=True, group_keys=False).apply(lambda g: g.sample(n=round(n_b * len(g) / len(rest)), random_state=SEED))
if len(bx) != n_b: bx = pd.concat([bx, rest[~rest.id.isin(bx.id)].sample(n=n_b - len(bx), random_state=SEED)]) if len(bx) < n_b else bx.sample(n=n_b, random_state=SEED)
bold = pd.concat([aold, bx]); assert len(bold) == round(FRAC * len(old_all)) and bold.id.is_unique and set(aold.id) <= set(bold.id)
info = {'seed': SEED, 'frac': FRAC, 'inputs': {'teacher-train-v2.parquet': sha(V2), 'teacher-train-v2-allold.parquet': sha(AL)}, 'new_pool': len(new), 'a_pool': len(apool), 'all_old_pool': len(old_all)}
for name, old in [('A', aold), ('B', bold)]:
    S = pd.concat([newS, old]).sort_values('id').reset_index(drop=True); assert S.id.is_unique and S.weight.gt(0).all() and S.y.isin([0, 1, 2]).all() and not S.part.isin(['holdout', 'exam7']).any()
    p = P('data/r16/small', f'set-{name}.parquet'); S.to_parquet(p, index=False)
    info['set-' + name] = {'rows': len(S), 'new': len(newS), 'old': len(old), 'weight_total': round(float(S.weight.sum()), 1), 'steps_bs32': -(-len(S) // 32), 'letters': S.label.value_counts().to_dict(), 'parts': S.part.value_counts().to_dict(),
                           'weights': {str(k): int(v) for k, v in S.weight.value_counts().sort_index().items()}, 'vendors': int(S.vendor.nunique()), 'sha256': sha(p)}
json.dump(info, open(P('data/r16/small/manifest.json'), 'w'), indent=1, default=str); print(json.dumps(info, indent=1, default=str))
open(P('data/r16/small/SHA256SUMS'), 'w').write(''.join(f'{sha(P("data/r16/small", f))}  {f}\n' for f in ('set-A.parquet', 'set-B.parquet', 'manifest.json')))
