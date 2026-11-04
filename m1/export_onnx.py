"""M1: export the r8soft checkpoint to ONNX (fp32), quantize to int8, and check int8 against PyTorch fp32.

  .venv/bin/python m1/export_onnx.py export   # data/m1/model-fp32.onnx, data/m1/model-int8.onnx, data/m1/vocab.txt
  .venv/bin/python m1/export_onnx.py parity   # fp32 torch vs int8 ORT on both exam input sets -> data/m1/parity.json

The ONNX graph outputs RAW logits (n,3) for (r,w,x). Temperature T=0.844 and softmax are applied by the
caller (src/answerer.js), exactly as train/exam_score.py does (temp_apply on softmax == softmax(logits/T)).
"""
import sys, os, json, hashlib, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'train'))
from common import ROOT, OUT, fmt_text, LABELS

CKPT = os.path.join(OUT, 'ckpt-r8soft', 'final')
M1 = os.path.join(ROOT, 'data', 'm1')
FP32 = os.path.join(M1, 'model-fp32.onnx')
INT8 = os.path.join(M1, 'model-int8.onnx')
T = 0.844
MAXLEN = 128
INPUTS = {'exam-2026-09-22': os.path.join(ROOT, 'data', 'exam-r8soft', 'inputs.jsonl'),
          'exam-2026-11-03-fresh': os.path.join(ROOT, 'data', 'exam-fresh-r8soft', 'inputs.jsonl')}

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def export():
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    os.makedirs(M1, exist_ok=True)
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
    from onnxruntime.quantization import quantize_dynamic, QuantType
    quantize_dynamic(FP32, INT8, weight_type=QuantType.QInt8)
    # vocab.txt in id order, for the Node tokenizer
    vocab = json.load(open(os.path.join(CKPT, 'tokenizer.json')))['model']['vocab']
    inv = sorted(vocab.items(), key=lambda kv: kv[1]); assert [i for _, i in inv] == list(range(len(inv)))
    with open(os.path.join(M1, 'vocab.txt'), 'w', encoding='utf-8') as f: f.write('\n'.join(w for w, _ in inv) + '\n')
    for p in (FP32, INT8, os.path.join(M1, 'vocab.txt')):
        print(f'{os.path.basename(p):18s} {os.path.getsize(p) / 1e6:7.2f} MB  sha256 {sha256(p)}')

def softmax_T(L):
    z = L / T; z = z - z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)

def torch_logits(texts):
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    torch.set_num_threads(8)
    tok = AutoTokenizer.from_pretrained(CKPT); model = AutoModelForSequenceClassification.from_pretrained(CKPT).eval()
    out = np.zeros((len(texts), 3), np.float32)
    with torch.no_grad():
        for i in range(0, len(texts), 64):
            e = tok(texts[i:i + 64], truncation=True, max_length=MAXLEN, padding=True, return_tensors='pt')
            out[i:i + 64] = model(**e).logits.numpy()
    return out, tok

def ort_logits(path, texts, tok):
    import onnxruntime as ort
    s = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
    out = np.zeros((len(texts), 3), np.float32)
    for i in range(0, len(texts), 64):
        e = tok(texts[i:i + 64], truncation=True, max_length=MAXLEN, padding=True, return_tensors='np')
        out[i:i + 64] = s.run(['logits'], {k: e[k].astype(np.int64) for k in ('input_ids', 'attention_mask', 'token_type_ids')})[0]
    return out

def parity():
    res = {'T': T, 'int8_sha256': sha256(INT8), 'sets': {}}
    for name, path in INPUTS.items():
        rows = [json.loads(l) for l in open(path) if l.strip()]
        texts = [fmt_text(r) for r in rows]
        Lt, tok = torch_logits(texts)
        L8 = ort_logits(INT8, texts, tok)
        Lf = ort_logits(FP32, texts, tok)
        Pt, P8, Pf = softmax_T(Lt), softmax_T(L8), softmax_T(Lf)
        isx_t, isx_8 = Pt[:, 2], P8[:, 2]; ch_t, ch_8 = Pt[:, 1] + Pt[:, 2], P8[:, 1] + P8[:, 2]
        d = {'n': len(rows),
             'fp32_onnx_vs_torch_max_abs_p': float(np.abs(Pf - Pt).max()),
             'int8_vs_torch_max_abs_p': float(np.abs(P8 - Pt).max()),
             'int8_vs_torch_mean_abs_p': float(np.abs(P8 - Pt).mean()),
             'int8_vs_torch_max_abs_isX': float(np.abs(isx_8 - isx_t).max()),
             'int8_vs_torch_max_abs_changes': float(np.abs(ch_8 - ch_t).max()),
             'argmax_agree': int((P8.argmax(1) == Pt.argmax(1)).sum()),
             # how many rows sit on the other side of the 0.97 lowering-confidence line
             'maxp_097_side_flips': int(((P8.max(1) >= 0.97) != (Pt.max(1) >= 0.97)).sum())}
        res['sets'][name] = d
        np.save(os.path.join(M1, f'probs-int8-{name}.npy'), P8); np.save(os.path.join(M1, f'probs-torch-{name}.npy'), Pt)
        print(name, json.dumps(d))
    json.dump(res, open(os.path.join(M1, 'parity.json'), 'w'), indent=1)

if __name__ == '__main__':
    {'export': export, 'parity': parity}[sys.argv[1]]()
