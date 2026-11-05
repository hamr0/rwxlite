"""Held-out-vendor experiment, predict (docs/wiki/holdout-r11.md). NEVER opens a truth file. One path for every model: PyTorch fp32 on CPU, batch 1, max_len 128.
  node m0/exam3-inputs.mjs <heldout-ops.csv> <work-dir>          # the 442 ory.sh + clerk.com rows (see m1/holdout-ops.py), RWXMAP_DIR = rwxmap at 46235ea
  python3 train/holdout_predict.py <work-dir> <val.parquet> --model NAME=DIR [--model NAME=DIR ...] [--tokenizer DIR]
DIR = saved HF model dir (config.json + model.safetensors). T per model = temp_fit on the r10 val split (4,180 rows, same batch-1 torch path), the function of train/tune_cuts.py.
Writes <work-dir>/predictions-NAME.csv (exam3_predict columns), p-NAME.jsonl ({id, model, pIsX, pChanges}, T applied; rwxmap shape) and predict-meta.json (T, sha256 of each model file)."""
import sys, os, json, csv, time, hashlib, argparse
import numpy as np, torch
import pandas as pd
import exam_score as E
import exam_fresh as F
from common import ORDER, LABELS, TIER, fmt_text
from tune_cuts import guarded, temp_fit
from transformers import AutoTokenizer, AutoModelForSequenceClassification
ap = argparse.ArgumentParser(); ap.add_argument('work'); ap.add_argument('val'); ap.add_argument('--model', action='append', required=True)
ap.add_argument('--tokenizer', default=None); ap.add_argument('--threads', type=int, default=4); A = ap.parse_args()
torch.set_num_threads(A.threads); MAXLEN = 128
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
@torch.no_grad()
def logits(model, tok, texts):
    ids = tok(texts, truncation=True, max_length=MAXLEN)['input_ids']; L = np.zeros((len(ids), 3), np.float64)
    for i, x in enumerate(ids):
        a = torch.tensor([x]); L[i] = model(input_ids=a, attention_mask=torch.ones_like(a)).logits[0].double().numpy()
    return L
def softmax(L, T): z = L / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)
rows = [json.loads(l) for l in open(os.path.join(A.work, 'inputs.jsonl')) if l.strip()]
bad = [r['id'] for r in rows if fmt_text({**r, 'method': 'GET' if r['method'] == 'QUERY' else r['method'], 'rule': {'credential-set': 'cant-undo-verb'}.get(r['rule'], r['rule'])}) != r['text']]
if bad: raise SystemExit(f'text path mismatch Node vs Python on {len(bad)} rows')
va = pd.read_parquet(A.val); yv = va.y.values; mech = np.array([ORDER[r['class']] for r in rows]); meta = {'n': len(rows), 'val_rows': len(va), 'models': {}}
for spec in A.model:
    name, d = spec.split('=', 1); tok = AutoTokenizer.from_pretrained(A.tokenizer or d)
    model = AutoModelForSequenceClassification.from_pretrained(d, num_labels=3).eval(); w = sha(os.path.join(d, 'model.safetensors')); t0 = time.time()
    T = float(temp_fit(softmax(logits(model, tok, list(va.text)), 1.0), yv)); L = logits(model, tok, [r['text'] for r in rows]); P = softmax(L, T); conf = P.max(1)
    pa = E.mode_a(rows, P); pb = guarded(P, E.MARGIN); Cf = F.configs(pa, pb, mech, conf)
    with open(os.path.join(A.work, f'predictions-{name}.csv'), 'w', newline='') as f:
        wr = csv.writer(f); wr.writerow(['id', 'provider', 'method', 'path', 'mech', 'mech_rule', 'tier', 'a_letter', 'b_letter', 'move', 'p_r', 'p_w', 'p_x', 'max_p', *F.CONFIGS])
        for i, r in enumerate(rows):
            mv = 'lowering' if pa[i] < mech[i] else 'raise' if pa[i] > mech[i] else 'keep'
            wr.writerow([r['id'], r['provider'], r['method'], r['path'], r['class'], r['rule'], TIER.get(r['jev_tier'], 'none'), LABELS[pa[i]], LABELS[pb[i]], mv,
                         *[f'{P[i, k]:.6f}' for k in range(3)], f'{conf[i]:.6f}', *[('ask' if Cf[k][1][i] else LABELS[Cf[k][0][i]]) for k in F.CONFIGS]])
    pis, pch = P[:, 2], P[:, 1] + P[:, 2]; assert ((0 <= pis) & (pis <= pch) & (pch <= 1)).all()
    with open(os.path.join(A.work, f'p-{name}.jsonl'), 'w') as f:
        for i, r in enumerate(rows): f.write(json.dumps({'id': r['id'], 'model': f'rwxlite-holdout-{name}+{w[:8]}', 'pIsX': float(pis[i]), 'pChanges': float(pch[i])}) + '\n')
    meta['models'][name] = {'dir': d, 'model_safetensors_sha256': w, 'T': round(T, 4), 'time_s': round(time.time() - t0, 1)}; print(name, meta['models'][name], flush=True)
json.dump(meta, open(os.path.join(A.work, 'predict-meta.json'), 'w'), indent=1); print('truth never opened')
