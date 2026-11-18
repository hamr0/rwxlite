"""Round 14 step 3: run a trained checkpoint over train.parquet and save softmax probabilities at T=1.
  python3 train/teacher_probs.py --ckpt data/train/ckpt-r14-bge/final --out data/train/teacher-r14-bge-train.npy --threads 3
Same text column and max_len 128 as finetune.py. Output float32 (rows, 3), row order = train.parquet; a sidecar <out>.json holds the sha256 of train.parquet.
Batches of 128 sorted by length (padding shifts p by about 1e-6)."""
import argparse, os, json, hashlib, time
import numpy as np, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from common import *
ap = argparse.ArgumentParser()
ap.add_argument('--ckpt', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--max_len', type=int, default=128); ap.add_argument('--threads', type=int, default=3); ap.add_argument('--bs', type=int, default=128)
a = ap.parse_args()
torch.set_num_threads(a.threads)
tok = AutoTokenizer.from_pretrained(a.ckpt); model = AutoModelForSequenceClassification.from_pretrained(a.ckpt).eval()
tr = load_split('train'); E = tok(list(tr.text), truncation=True, max_length=a.max_len)['input_ids']
order = sorted(range(len(E)), key=lambda i: len(E[i])); P = np.zeros((len(E), 3), dtype=np.float32); t0 = time.time()
with torch.no_grad():
    for k, i in enumerate(range(0, len(order), a.bs)):
        ids = order[i:i + a.bs]; L = max(len(E[j]) for j in ids)
        x = torch.zeros(len(ids), L, dtype=torch.long); m = torch.zeros(len(ids), L, dtype=torch.long)
        for r, j in enumerate(ids): x[r, :len(E[j])] = torch.tensor(E[j]); m[r, :len(E[j])] = 1
        P[ids] = torch.softmax(model(input_ids=x, attention_mask=m).logits, -1).numpy()
        if k % 20 == 0:
            done = i + len(ids); el = time.time() - t0
            print(f'rows {done}/{len(E)} {done/el:.1f} rows/s elapsed {el/60:.1f}m eta {(len(E)-done)/(done/el)/60:.1f}m', flush=True)
np.save(a.out, P)
sha = hashlib.sha256(open(os.path.join(OUT, 'train.parquet'), 'rb').read()).hexdigest()
json.dump({'train_parquet_sha256': sha, 'rows': int(len(E)), 'ckpt': a.ckpt, 'max_len': a.max_len, 'dtype': 'float32', 'temperature': 1.0,
           'argmax_agrees_with_y': float((P.argmax(1) == tr.y.values).mean())}, open(a.out + '.json', 'w'), indent=1)
print('saved', a.out, P.shape, 'sha256 train.parquet', sha, flush=True)
