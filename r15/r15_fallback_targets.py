"""Round 15 fallback (docs/wiki/prereg-r15.md section 5, used only if the new teacher fails its go/no-go): soft targets from the ROUND 14 bge teacher for every row of data/round15/train.parquet.
  python3 r15/r15_fallback_targets.py        # writes data/round15/teacher-fallback-oldbge-train.npy (+ .json)
R13 rows = teacher-r14-bge-train.npy (round 14 step 3, T=1, fp32, row order = round 13 train.parquet; its sidecar sha256 is checked), r15 rows = bge_raw_p_* (T=1, the r14-bge checkpoint over the same
text) from pick-200000-1-opinions.parquet joined on op_id. The student then trains exactly as in stage B with --teacher on this file; hard label and row weight are the cascade ones."""
import os, sys, json, hashlib
import numpy as np, pandas as pd
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); D = os.path.join(R, 'data', 'round15')
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
tr = pd.read_parquet(os.path.join(D, 'train.parquet')); side = json.load(open(os.path.join(D, 'teacher-r14-bge-train.npy.json')))
assert side['train_parquet_sha256'] == sha(os.path.join(R, 'data/round13/train.parquet')) and side['rows'] == 102668
old = np.load(os.path.join(D, 'teacher-r14-bge-train.npy')); assert old.shape == (102668, 3)
op = pd.read_parquet(os.path.join(R, 'data/r15/labels/pick-200000-1-opinions.parquet')).set_index('op_id')
new_ids = tr.id[tr.src == 'r15'].values; raw = op.loc[new_ids, ['bge_raw_p_r', 'bge_raw_p_w', 'bge_raw_p_x']].values.astype(np.float32)
assert (tr.src.values[:102668] == 'r13').all() and (tr.src.values[102668:] == 'r15').all() and np.allclose(raw.sum(1), 1, atol=1e-4)
T = np.concatenate([old, raw]).astype(np.float32); assert T.shape == (len(tr), 3)
out = os.path.join(D, 'teacher-fallback-oldbge-train.npy'); np.save(out, T)
json.dump({'train_parquet_sha256': sha(os.path.join(D, 'train.parquet')), 'rows': len(tr), 'argmax_agrees_with_y': float((T.argmax(1) == tr.y.values).mean())}, open(out + '.json', 'w'), indent=1)
print(out, T.shape, sha(out), 'argmax agrees with y', float((T.argmax(1) == tr.y.values).mean()))
