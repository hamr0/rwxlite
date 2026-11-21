"""Round 16 Sonnet re-check inputs, same format as labels/sonnet/in/chunk-*.csv (op_id,method,path,summary,description; CRLF->LF, description cut at 1500).
  data/r16/scratch/venv/bin/python -I r16/label_recheck_prep.py
Set A r15recheck: the 396 r15-source rows of review/confident.csv.gz (rows text from labels/opus-recheck-755/in.csv, built by label_assemble.py). Blind: no label or bge letter in the input.
  Side file labels/sonnet-recheck/r15recheck-current.csv (op_id, current r15 label, bge letter) is NOT for the labeller.
Set B holdout400: labels/disagree-sample-400.csv, only the 5 chunk columns (the sheet's opinion columns are dropped, as the normal chunks carry none)."""
import csv, os
import pandas as pd
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'r16'); L = os.path.join(R, 'labels'); O = os.path.join(L, 'sonnet-recheck'); os.makedirs(os.path.join(O, 'in'), exist_ok=True)
COLS = ['op_id', 'method', 'path', 'summary', 'description']; CH = 500
nl = lambda s: s.replace('\r\n', '\n').replace('\r', '\n')
def rows(df): return [[r.op_id, r.method, r.path, nl(r.summary), nl(r.description)[:1500]] for r in df.itertuples(index=False)]
def write(name, rs):
    for i in range(0, len(rs), CH):
        with open(os.path.join(O, 'in', f'{name}-{i // CH:03d}.csv'), 'w', newline='', encoding='utf-8') as f: w = csv.writer(f); w.writerow(COLS); w.writerows(rs[i:i + CH])
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)
c = pd.read_csv(os.path.join(R, 'review', 'confident.csv.gz'), dtype=str, keep_default_na=False); a = c[c.src == 'r15']
assert len(a) == 396 and a.op_id.is_unique, len(a)
src = rd(os.path.join(L, 'opus-recheck-755', 'in.csv')).set_index('op_id', drop=False).rename_axis(None)
A = src.loc[a.op_id.tolist(), COLS].sort_values('op_id'); assert len(A) == 396
a[['op_id', 'label', 't_letter']].rename(columns={'label': 'r15_label', 't_letter': 'bge_letter'}).sort_values('op_id').to_csv(os.path.join(O, 'r15recheck-current.csv'), index=False)
write('r15recheck', rows(A))
B = rd(os.path.join(L, 'disagree-sample-400.csv'))[COLS].sort_values('op_id'); assert len(B) == 400 and B.op_id.is_unique, len(B)
write('holdout400', rows(B)); print('A', len(A), 'B', len(B))
