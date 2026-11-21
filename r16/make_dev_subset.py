"""Round 16 frozen dev subset (b): dev v2 rows whose K2 key (METHOD, normalised path, operationId; r16/opkey.py k2) matches NO row of any training set that a small run can use.
  data/r16/scratch/venv/bin/python -I r16/make_dev_subset.py          (writes r16/dev-subset-b-ids.txt, sorted op_ids, one per line; prints count and sha256)
'Any training set' = union of teacher-train-v2 (60k replay variant), teacher-train-v2-allold (ALL old rows variant) and data/round15/train.parquet (every row r15 trained on, incl. the exam #8 vendor rows
the builder drops), so the same rows are clean for both arms, for the full runs, and for the 0.4.0 / r15 base. Deterministic; refuses to overwrite a different list."""
import hashlib, os, sys
import pandas as pd
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); sys.path.insert(0, os.path.join(R, 'r16')); import opkey
P = lambda *a: os.path.join(R, *a); cols = ['method', 'path', 'operationId', 'summary']
dev = pd.read_parquet(P('data/r16/labels/final/final-labels-r16-dev-v2.parquet')).fillna(''); assert len(dev) == 4475 and dev.op_id.is_unique
u = set()
for f in ('data/r16/train/teacher-train-v2.parquet', 'data/r16/train/teacher-train-v2-allold.parquet', 'data/round15/train.parquet'): u |= set(opkey.k2(pd.read_parquet(P(f), columns=cols).fillna('')))
keep = sorted(dev.op_id[[k not in u for k in opkey.k2(dev)]]); out = P('r16/dev-subset-b-ids.txt'); txt = '\n'.join(keep) + '\n'
if os.path.exists(out) and open(out).read() != txt: sys.exit('refusing to overwrite a different frozen list')
open(out, 'w').write(txt); print(len(keep), 'rows of', len(dev), 'sha256', hashlib.sha256(txt.encode()).hexdigest())
