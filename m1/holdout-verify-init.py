#!/usr/bin/env python3
"""Verify the C init checkpoint is the 0.2.0 model. python3 -I m1/holdout-verify-init.py <ckpt-r8soft/final> <val.parquet> <probs-r8soft-val.npy> <scratch-dir>
1. model.safetensors sha256 is printed; 2. val probs (finetune.py's predict: sorted batches of 128, padded) max |diff| vs the stored probs-r8soft-val.npy;
3. fp32 ONNX re-exported with m1/export_onnx.py's exact call into scratch-dir: sha256 vs the shipped 0.2.0 data/m1/model-fp32.onnx (8503b655...)."""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'train'))
import numpy as np, pandas as pd, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
ck, val, probs, scr = sys.argv[1:5]; os.makedirs(scr, exist_ok=True)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
print('model.safetensors', sha(os.path.join(ck, 'model.safetensors')))
tok = AutoTokenizer.from_pretrained(ck); m = AutoModelForSequenceClassification.from_pretrained(ck, num_labels=3).eval(); torch.set_num_threads(4)
va = pd.read_parquet(val); E = tok(list(va.text), truncation=True, max_length=128)['input_ids']; order = sorted(range(len(E)), key=lambda i: len(E[i])); P = np.zeros((len(E), 3), np.float32)
with torch.no_grad():
    for i in range(0, len(order), 128):
        ids = order[i:i + 128]; L = max(len(E[j]) for j in ids); x = torch.zeros(len(ids), L, dtype=torch.long); a = torch.zeros_like(x)
        for k, j in enumerate(ids): x[k, :len(E[j])] = torch.tensor(E[j]); a[k, :len(E[j])] = 1
        P[ids] = torch.softmax(m(input_ids=x, attention_mask=a).logits, -1).numpy()
S = np.load(probs); print('val rows', len(va), 'max|dp| vs stored', float(np.abs(P - S).max()), 'argmax equal', int((P.argmax(1) == S.argmax(1)).sum()), '/', len(S))
try:
    class Wrap(torch.nn.Module):
        def __init__(s, m): super().__init__(); s.m = m
        def forward(s, input_ids, attention_mask, token_type_ids): return s.m(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids).logits
    enc = tok(['lean: x path-verb | POST /v1/charges | op: createCharge'], return_tensors='pt'); out = os.path.join(scr, 'model-fp32.onnx')
    torch.onnx.export(Wrap(m), (enc['input_ids'], enc['attention_mask'], enc['token_type_ids']), out, input_names=['input_ids', 'attention_mask', 'token_type_ids'], output_names=['logits'],
                      dynamic_axes={k: {0: 'batch', 1: 'seq'} for k in ('input_ids', 'attention_mask', 'token_type_ids')} | {'logits': {0: 'batch'}}, opset_version=17, dynamo=False)
    print('re-exported fp32 onnx', sha(out), '(shipped 0.2.0: 8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b)')
except Exception as e: print('ONNX re-export not run here:', type(e).__name__, str(e)[:80])
