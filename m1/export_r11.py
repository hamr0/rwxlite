"""Round 11: export ckpt-r11/final to ONNX fp32 + int8 per-channel (same recipe as m1/export_onnx.py + m1/variants.py), WITHOUT touching data/m1.

  .venv/bin/python m1/export_r11.py export   # data/m1-r11/model-fp32.onnx, model-int8-pc.onnx, vocab.txt, export-sha.json
  .venv/bin/python m1/export_r11.py parity   # fp32 ONNX / int8-pc ONNX vs torch fp32 on val + v3eval (practice sets) -> data/m1-r11/parity.json

Raw logits come out of the graph; T is applied by the caller. Prints sha256 of every file. No exam rows are read.
"""
import sys, os, json, hashlib
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'train'))
from common import ROOT, OUT

CKPT = os.path.join(OUT, 'ckpt-r11', 'final')
D = os.path.join(ROOT, 'data', 'm1-r11')
FP32, INT8PC, VOCAB = (os.path.join(D, n) for n in ('model-fp32.onnx', 'model-int8-pc.onnx', 'vocab.txt'))
MAXLEN = 128

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def export():
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from onnxruntime.quantization import quantize_dynamic, QuantType
    os.makedirs(D, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(CKPT)
    model = AutoModelForSequenceClassification.from_pretrained(CKPT).eval()
    enc = tok(['lean: x path-verb | POST /v1/charges | op: createCharge'], return_tensors='pt')

    class Wrap(torch.nn.Module):
        def __init__(s, m): super().__init__(); s.m = m
        def forward(s, input_ids, attention_mask, token_type_ids):
            return s.m(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids).logits

    torch.onnx.export(Wrap(model), (enc['input_ids'], enc['attention_mask'], enc['token_type_ids']), FP32,
                      input_names=['input_ids', 'attention_mask', 'token_type_ids'], output_names=['logits'],
                      dynamic_axes={k: {0: 'batch', 1: 'seq'} for k in ('input_ids', 'attention_mask', 'token_type_ids')} | {'logits': {0: 'batch'}},
                      opset_version=17, dynamo=False)
    quantize_dynamic(FP32, INT8PC, weight_type=QuantType.QInt8, per_channel=True, reduce_range=False)
    vocab = json.load(open(os.path.join(CKPT, 'tokenizer.json')))['model']['vocab']
    inv = sorted(vocab.items(), key=lambda kv: kv[1]); assert [i for _, i in inv] == list(range(len(inv)))
    with open(VOCAB, 'w', encoding='utf-8') as f: f.write('\n'.join(w for w, _ in inv) + '\n')
    out = {os.path.basename(p): {'bytes': os.path.getsize(p), 'sha256': sha256(p)} for p in (FP32, INT8PC, VOCAB)}
    out['ckpt model.safetensors'] = {'sha256': sha256(os.path.join(CKPT, 'model.safetensors'))}
    json.dump(out, open(os.path.join(D, 'export-sha.json'), 'w'), indent=1)
    for k, v in out.items(): print(f'{k:24s}', v)

def run(path, ids, batch=1):
    import onnxruntime as ort
    o = ort.SessionOptions(); o.intra_op_num_threads = 4
    s = ort.InferenceSession(path, o, providers=['CPUExecutionProvider'])
    L = np.zeros((len(ids), 3), np.float32)
    for i in range(0, len(ids), batch):
        part = ids[i:i + batch]; w = max(len(x) for x in part)
        a = np.zeros((len(part), w), np.int64); m = np.zeros_like(a)
        for k, x in enumerate(part): a[k, :len(x)] = x; m[k, :len(x)] = 1
        L[i:i + batch] = s.run(['logits'], {'input_ids': a, 'attention_mask': m, 'token_type_ids': np.zeros_like(a)})[0]
    return L

def parity():
    import torch, pandas as pd
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    T = float(sys.argv[2]) if len(sys.argv) > 2 else 0.843
    tok = AutoTokenizer.from_pretrained(CKPT); model = AutoModelForSequenceClassification.from_pretrained(CKPT).eval()
    sm = lambda L: (lambda z: np.exp(z - z.max(1, keepdims=True)) / np.exp(z - z.max(1, keepdims=True)).sum(1, keepdims=True))(L / T)
    res = {'T': T, 'sets': {}}
    for name in ('val', 'v3eval'):
        df = pd.read_parquet(os.path.join(ROOT, 'data', 'train', f'{name}.parquet'))
        ids = tok(list(df.text), truncation=True, max_length=MAXLEN)['input_ids']
        Lt = np.zeros((len(ids), 3), np.float32)
        with torch.no_grad():
            for i in range(0, len(ids), 64):
                e = tok.pad({'input_ids': ids[i:i + 64]}, return_tensors='pt'); Lt[i:i + 64] = model(**e).logits.numpy()
        Pt = sm(Lt); d = {'n': len(ids)}; Pf = None
        stat = lambda P, Q: {'max_abs_dp': float(np.abs(P - Q).max()), 'mean_abs_dp': float(np.abs(P - Q).mean()),
                             'argmax_diffs': int((P.argmax(1) != Q.argmax(1)).sum()), 'crossings_097': int(((P.max(1) >= 0.97) != (Q.max(1) >= 0.97)).sum())}
        for tag, path in (('fp32', FP32), ('int8-pc', INT8PC)):
            P = sm(run(path, ids, 1))
            d[tag + '_vs_torch'] = stat(P, Pt)
            if tag == 'fp32': Pf = P
            else: d['int8-pc_vs_fp32'] = stat(P, Pf)
        res['sets'][name] = d; print(name, json.dumps(d))
    json.dump(res, open(os.path.join(D, 'parity.json'), 'w'), indent=1)

if __name__ == '__main__':
    {'export': export, 'parity': parity}[sys.argv[1]]()
