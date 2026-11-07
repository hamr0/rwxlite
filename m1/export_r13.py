"""Exam #5 candidate R13: export data/round13/models/R13 (safetensors) to ONNX fp32 + int8 per-channel (same recipe as m1/export_r11.py),
into data/m1-r13/ (gitignored). Raw logits come out of the graph; T is applied by the caller. Reads no exam data.

  .venv/bin/python m1/export_r13.py export   # model-fp32.onnx, model-int8-pc.onnx, vocab.txt, export-sha.json (checks the safetensors sha256)
  .venv/bin/python m1/export_r13.py rows     # parity-rows.jsonl: every 7th row of data/round13/val.jsonl, ORT batch-1 p at T (fp32 and int8-pc) for node m1/manifest-r13.mjs parity
  .venv/bin/python m1/export_r13.py parity   # torch fp32 vs ORT fp32 (and int8-pc) on the same sample -> parity.json
"""
import sys, os, json, hashlib
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'train'))
from common import ROOT

CKPT = os.path.join(ROOT, 'data', 'round13', 'models', 'R13')
CKPT_SHA = 'd16276d8b0ff93221821e2c3bd107b7d6898a8804bba93c40a2f4b06bbd6b30d'
T = 0.991463
D = os.path.join(ROOT, 'data', 'm1-r13')
FP32, INT8PC, VOCAB = (os.path.join(D, n) for n in ('model-fp32.onnx', 'model-int8-pc.onnx', 'vocab.txt'))
VAL = os.path.join(ROOT, 'data', 'round13', 'val.jsonl')
MAXLEN = 128; STEP = 7

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def export():
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from onnxruntime.quantization import quantize_dynamic, QuantType
    got = sha256(os.path.join(CKPT, 'model.safetensors'))
    assert got == CKPT_SHA, f'R13 safetensors sha256 {got} != {CKPT_SHA}'
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
    out['ckpt model.safetensors'] = {'sha256': got}
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

def sample():
    rows = [json.loads(l) for l in open(VAL) if l.strip()]
    return rows[::STEP]

def softmax(L):
    z = L.astype(np.float64) / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)

def rows():
    from transformers import AutoTokenizer
    rs = sample(); tok = AutoTokenizer.from_pretrained(CKPT)
    ids = tok([r['text'] for r in rs], truncation=True, max_length=MAXLEN)['input_ids']
    pf, p8 = softmax(run(FP32, ids, 1)), softmax(run(INT8PC, ids, 1))
    with open(os.path.join(D, 'parity-rows.jsonl'), 'w') as f:
        for i, r in enumerate(rs):
            f.write(json.dumps({'id': r['id'], 'text': r['text'], 'state': {'method': r['method'], 'path': r['path'], 'operationId': r['operationId'] or '', 'summary': r['summary'] or '',
                                      'description': r['text'].split(' | desc: ', 1)[1] if ' | desc: ' in r['text'] else ''},
                                'lean': {'class': r['mech'], 'rule': r['rule']}, 'p': {'fp32': pf[i].tolist(), 'int8-pc': p8[i].tolist()}}) + '\n')
    print('rows', len(rs))

def parity():
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    rs = sample(); tok = AutoTokenizer.from_pretrained(CKPT); model = AutoModelForSequenceClassification.from_pretrained(CKPT).eval()
    ids = tok([r['text'] for r in rs], truncation=True, max_length=MAXLEN)['input_ids']
    Lt = np.zeros((len(ids), 3), np.float32)
    with torch.no_grad():
        for i, x in enumerate(ids):
            a = torch.tensor([x]); Lt[i] = model(input_ids=a, attention_mask=torch.ones_like(a)).logits[0].numpy()
    Pt = softmax(Lt)
    stat = lambda P, Q: {'max_abs_dp': float(np.abs(P - Q).max()), 'mean_abs_dp': float(np.abs(P - Q).mean()), 'argmax_diffs': int((P.argmax(1) != Q.argmax(1)).sum())}
    res = {'T': T, 'n': len(ids), 'step': STEP}
    Pf = softmax(run(FP32, ids, 1)); res['fp32_ort_vs_torch'] = stat(Pf, Pt)
    res['int8-pc_ort_vs_fp32_ort'] = stat(softmax(run(INT8PC, ids, 1)), Pf)
    json.dump(res, open(os.path.join(D, 'parity.json'), 'w'), indent=1); print(json.dumps(res))

if __name__ == '__main__':
    {'export': export, 'rows': rows, 'parity': parity}[sys.argv[1]]()
