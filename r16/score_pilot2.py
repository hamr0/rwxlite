"""Score the pass-2 pilot (80 unsure pilot rows, r15 rows) against the r15 final labels, and compare with the first-pass pilot letters on the same rows.
  data/r16/scratch/venv/bin/python -I r16/score_pilot2.py
Reads: sonnet2/in/pilot2-000.csv (letter_a, letter_b), sonnet2/out/pilot2-000.csv, pilot/out-pilot-000.csv (first pass), r15/labels/final-labels-r15-d141-tight.csv.gz (the only place the r15 truth is read).
Final letter after pass 2: sure/likely -> pass-2 letter; unsure -> the tighter of the two letters, weight 0.3. Checks the out file format first. Writes nothing."""
import os, sys
import pandas as pd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); L = os.path.join(ROOT, 'data', 'r16', 'labels'); RK = {'r': 0, 'w': 1, 'x': 2}
i = pd.read_csv(os.path.join(L, 'sonnet2', 'in', 'pilot2-000.csv'), dtype=str, keep_default_na=False)
o = pd.read_csv(os.path.join(L, 'sonnet2', 'out', 'pilot2-000.csv'), dtype=str, keep_default_na=False)
assert list(o.columns) == ['op_id', 'letter', 'confidence', 'clause'], list(o.columns)
assert list(o.op_id) == list(i.op_id), 'op_ids differ from the input, or order differs'
assert o.confidence.isin(['sure', 'likely', 'unsure']).all(), 'bad confidence'
assert ((o.letter == i.letter_a) | (o.letter == i.letter_b)).all(), 'a letter is not one of the two candidates'
p1 = pd.read_csv(os.path.join(L, 'pilot', 'out-pilot-000.csv'), dtype=str, keep_default_na=False).set_index('op_id')
fl = pd.read_csv(os.path.join(ROOT, 'data', 'r15', 'labels', 'final-labels-r15-d141-tight.csv.gz'), usecols=['op_id', 'label', 'tier', 'weight'], dtype={'op_id': str, 'label': str}).set_index('op_id')
d = i[['op_id', 'letter_a', 'letter_b']].copy(); d['p2'] = o.letter.values; d['conf'] = o.confidence.values
d['tighter'] = [b for a, b in zip(d.letter_a, d.letter_b)]                       # letter_a < letter_b in r<w<x order, so b is the tighter
d['final'] = [p if c != 'unsure' else t for p, c, t in zip(d.p2, d.conf, d.tighter)]; d['weight'] = (d.conf != 'unsure').map({True: 1.0, False: 0.3})
d['pass1'] = p1.loc[d.op_id, 'letter'].values; d['truth'] = fl.reindex(d.op_id).label.values
assert d.truth.notna().all(), f'{d.truth.isna().sum()} rows missing from the r15 final labels (holdout rows are not in it)'
assert (p1.loc[d.op_id, 'confidence'] == 'unsure').all()
n = len(d); pct = lambda k, m=n: f'{k}/{m} = {100 * k / m:.1f}%'
print('rows', n, '| candidate pairs', d.groupby(['letter_a', 'letter_b']).size().to_dict(), '| pass-2 confidence', d.conf.value_counts().to_dict())
print('truth inside the candidate pair:', pct(int(((d.truth == d.letter_a) | (d.truth == d.letter_b)).sum())), '(ceiling for pass 2)')
print('first pass (unsure letter) right:', pct(int((d.pass1 == d.truth).sum())), '(task note: 67.5%)')
print('pass 2 raw letter right:', pct(int((d.p2 == d.truth).sum())))
print('pass 2 FINAL (unsure -> tighter) right:', pct(int((d.final == d.truth).sum())), '| weight-0.3 rows', int((d.weight < 1).sum()), 'of', n)
for c in ('sure', 'likely', 'unsure'):
    g = d[d.conf == c]
    if len(g): print(f'  conf {c}: {len(g)} rows, pass-2 letter right {pct(int((g.p2 == g.truth).sum()), len(g))}, tighter-letter right {pct(int((g.tighter == g.truth).sum()), len(g))}')
print('always-tighter-of-the-pair right:', pct(int((d.tighter == d.truth).sum())), '(baseline)')
ex = d.final != d.truth; r = d.final.map(RK); t = d.truth.map(RK)
print('final errors: too loose', int((ex & (r < t)).sum()), '| too tight', int((ex & (r > t)).sum()), '| first-pass errors: too loose', int(((d.pass1 != d.truth) & (d.pass1.map(RK) < t)).sum()), '| too tight', int(((d.pass1 != d.truth) & (d.pass1.map(RK) > t)).sum()))
print('moves vs first pass: fixed', int(((d.pass1 != d.truth) & (d.final == d.truth)).sum()), '| broken', int(((d.pass1 == d.truth) & (d.final != d.truth)).sum()))
print(pd.crosstab(d.truth, d.final, rownames=['r15 truth'], colnames=['pass-2 final']))
print('truth tier of the pilot rows:', fl.reindex(d.op_id).tier.value_counts().to_dict())
