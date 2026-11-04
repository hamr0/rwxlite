"""Round 11: the 32 credential-set ops (31 distinct) on a checkpoint, torch fp32, same procedure as round 10's cred32 (text via unchanged common.fmt_text,
description omitted). 'raw name' = lean rule sent as `credential-set`; 'guarded' = the src/text.js alias `cant-undo-verb`. Practice/validation only.
  .venv/bin/python train/r11_cred32.py <ckpt_dir> <T>   (reads test/fixtures/credential-set.jsonl)"""
import sys, os, json, numpy as np, torch
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, fmt_text
from transformers import AutoTokenizer, AutoModelForSequenceClassification
ck, T = sys.argv[1], float(sys.argv[2])
rows = [json.loads(l) for l in open(os.path.join(ROOT, 'test/fixtures/credential-set.jsonl'))]
tok = AutoTokenizer.from_pretrained(ck); m = AutoModelForSequenceClassification.from_pretrained(ck).eval(); torch.set_num_threads(4)
def run(rule, T):
    out = []
    for r in rows:
        e = tok(fmt_text({'class': 'x', 'rule': rule, 'method': r['method'], 'path': r['path'], 'operationId': r['operationId'], 'summary': r['summary'], 'description': None}), truncation=True, max_length=128, return_tensors='pt')
        with torch.no_grad(): out.append(torch.softmax(m(**e).logits / T, -1)[0].numpy())
    return np.array(out)
def stat(P):
    am = P.argmax(1)
    return {'argmax r/w/x': '/'.join(str(int((am == k).sum())) for k in range(3)), 'below_x': int((am != 2).sum()),
            'lowerings_p>=0.97': int((P[:, :2].max(1) >= 0.97).sum()), 'isX min': round(float(P[:, 2].min()), 4), 'isX median': round(float(np.median(P[:, 2])), 3)}
print(f'{len(rows)} ops, ckpt {ck}')
for rule, label in (('credential-set', 'raw name'), ('cant-undo-verb', 'guarded')):
    for t in (1.0, T): print(f'{label:9s} T={t}:', json.dumps(stat(run(rule, t))))
