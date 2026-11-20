"""Tighten-only merge rule for the r15 half (docs/wiki/prereg-r15.md section 3.4): every r15 row whose D141 letter is LOWER than its pre-D141 letter reverts to the pre-D141 letter; raises stay.
  python3 r15/r15_revert_lowers.py   # reads data/r15/labels/final-labels-r15-d141.parquet (sha256 asserted), writes final-labels-r15-d141-tight.{parquet,csv.gz} next to it (old file kept)
Same columns as the input. A reverted row gets d141_changed False and its pre-D141 weight (final-labels-r15.parquet); d141_candidate, d141_pass2, d141_pass2_letter, d141_families are kept as history."""
import os, hashlib, pandas as pd
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'r15', 'labels')
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
assert sha(f'{R}/final-labels-r15-d141.parquet') == 'd36972fe2f9be2107581fbe30a7a5edecdf7d191418bf03f85c041b7e42e93eb'
assert sha(f'{R}/final-labels-r15.parquet') == '8e11971ce39f6590519a8dd50c970505455fd0dc50ff33fead40d767dd728a98'
f = pd.read_parquet(f'{R}/final-labels-r15-d141.parquet'); pre = pd.read_parquet(f'{R}/final-labels-r15.parquet').set_index('op_id')
K = {'r': 0, 'w': 1, 'x': 2}; low = f.label.map(K) < f.label_pre_d141.map(K); assert low.sum() == 162 and (f.label_pre_d141.values == pre.loc[f.op_id, 'label'].values).all()
assert 'r15-19f736c8f25e0c73' in set(f.op_id[low]) and f.d141_changed[low].all()
g = f.copy(); g.loc[low, 'label'] = f.label_pre_d141[low]; g.loc[low, 'weight'] = pre.loc[f.op_id[low], 'weight'].values; g.loc[low, 'd141_changed'] = False
assert (g.d141_changed == (g.label != g.label_pre_d141)).all() and g.d141_changed.sum() == f.d141_changed.sum() - 162
g.to_parquet(f'{R}/final-labels-r15-d141-tight.parquet', index=False); g.to_csv(f'{R}/final-labels-r15-d141-tight.csv.gz', index=False)
print(g.label.value_counts().to_dict(), int(g.d141_changed.sum()), g.weight.value_counts().to_dict())
for n in ('parquet', 'csv.gz'): print(sha(f'{R}/final-labels-r15-d141-tight.{n}'), n)
