"""Round 16 small runs: raw logits of one checkpoint on the dev set or on val, PyTorch fp32, CPU, batch 1, max_len 128 (the r15 scorer path). Temperature is applied later by r16/score_dev.py.
  python3 r16/predict_dev.py --ckpt DIR --set dev|val --out OUT.csv [--threads 3]
dev text = the model input text of r16/labels/work/mech.jsonl (sha256 asserted; lean format 1, rwxmap 1c25be1 mechanical); val text = data/round15/val.parquet (sha256 asserted, 4,180 rows).
Output csv: op_id,l_r,l_w,l_x (repr of the float64 logits) in dev-file order / val order; exclusive create."""
import argparse, csv, hashlib, json, os
import numpy as np, pandas as pd, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
R = '/home/hamr/PycharmProjects/rwxlite'; P = lambda *a: os.path.join(R, *a)
ap = argparse.ArgumentParser(); ap.add_argument('--ckpt', required=True); ap.add_argument('--set', choices=['dev', 'val'], required=True); ap.add_argument('--out', required=True); ap.add_argument('--threads', type=int, default=3)
a = ap.parse_args(); torch.set_num_threads(a.threads); sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
dev = pd.read_parquet(P('data/r16/labels/final/final-labels-r16-dev-v2.parquet')); tx = {}
for l in open(P('data/r16/scratch/lean/dev-text-ecee4f1.jsonl'), encoding='utf-8'):
    r = json.loads(l); tx[r['id']] = r['text']
ids, texts = list(dev.op_id), [tx[i] for i in dev.op_id]
tok = AutoTokenizer.from_pretrained(a.ckpt); model = AutoModelForSequenceClassification.from_pretrained(a.ckpt).eval()
with torch.no_grad(), open(a.out, 'x', newline='') as f:
    w = csv.writer(f); w.writerow(['op_id', 'l_r', 'l_w', 'l_x'])
    for i, t in zip(ids, texts):
        x = torch.tensor([tok(t, truncation=True, max_length=128)['input_ids']]); lg = model(input_ids=x, attention_mask=torch.ones_like(x)).logits[0].double().numpy()
        w.writerow([i] + [repr(float(v)) for v in lg])
print('wrote', a.out, len(ids), 'rows sha256', sha(a.out))
