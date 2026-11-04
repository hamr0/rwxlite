"""M1: compare ONNX quantisation variants against the torch fp32 reference on both exams.

  .venv/bin/python m1/variants.py build     # writes data/m1/model-<variant>.onnx (model-int8.onnx and model-fp32.onnx already exist)
  .venv/bin/python m1/variants.py eval      # probs at batch 1 and batch 32 -> data/m1/probs-<variant>-b<k>-<exam>.npy, parity + rescoring -> data/m1/variants-py.json
  (node m1/bench.mjs --variants then adds Node latency and merges everything into data/m1/variants.json)

Why batch 1 AND batch 32: dynamic int8 quantises each activation tensor with ONE scale computed at run time over the
whole padded batch, so a row's probabilities depend on which other rows share its batch. That is checked, not assumed.

Rescoring reuses train/exam_fresh.py (configs, piles) and train/exam_score.py (mode_a) unchanged; only the probabilities differ.
Truth is read here once per exam, as exam_fresh.score / exam_score.score do, because rescoring needs it.
"""
import sys, os, json, csv
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'train'))
import exam_score as E
import exam_fresh as F
from common import ROOT, ORDER, LABELS, TIER, fmt_text
from tune_cuts import guarded
import export_onnx as X

M1 = X.M1
FILES = {'fp32': 'model-fp32.onnx', 'int8-default': 'model-int8.onnx', 'int8-pc': 'model-int8-pc.onnx', 'int8-mm': 'model-int8-mm.onnx',
         'int8-pc-mm': 'model-int8-pc-mm.onnx', 'fp16': 'model-fp16.onnx'}
EXAMS = {'exam-2026-09-22': 'exam-2026-09-22', 'exam-2026-11-03-fresh': 'exam-2026-11-03-fresh'}

def build():
    from onnxruntime.quantization import quantize_dynamic, QuantType
    q = lambda out, **kw: quantize_dynamic(X.FP32, os.path.join(M1, out), weight_type=QuantType.QInt8, **kw)
    q('model-int8-pc.onnx', per_channel=True, reduce_range=False)                         # (1)
    q('model-int8-mm.onnx', op_types_to_quantize=['MatMul'])                               # (2) embeddings Gather + pooler/classifier Gemm stay fp32
    q('model-int8-pc-mm.onnx', per_channel=True, reduce_range=False, op_types_to_quantize=['MatMul'])  # (3)
    import onnx
    from onnxruntime.transformers.float16 import convert_float_to_float16
    onnx.save(convert_float_to_float16(onnx.load(X.FP32), keep_io_types=True), os.path.join(M1, 'model-fp16.onnx'))  # (4)
    for k, f in FILES.items(): print(f'{k:12s} {f:24s} {os.path.getsize(os.path.join(M1, f)) / 1e6:7.2f} MB')

def run(path, ids, batch):
    import onnxruntime as ort
    o = ort.SessionOptions(); o.intra_op_num_threads = 4
    s = ort.InferenceSession(path, o, providers=['CPUExecutionProvider'])
    L = np.zeros((len(ids), 3), np.float32)
    for i in range(0, len(ids), batch):
        part = ids[i:i + batch]; w = max(len(x) for x in part)
        a = np.zeros((len(part), w), np.int64); m = np.zeros_like(a)
        for k, x in enumerate(part): a[k, :len(x)] = x; m[k, :len(x)] = 1
        L[i:i + batch] = s.run(['logits'], {'input_ids': a, 'attention_mask': m, 'token_type_ids': np.zeros_like(a)})[0]
    z = L / X.T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)

def truth_fresh():
    t = {}
    for r in csv.DictReader(open(F.TRUTH, newline='', encoding='utf-8')): t[r['id']] = ORDER[r['label']]
    return t

def truth_old():
    t = {}
    for r in csv.DictReader(open(E.TRUTH_FILE, newline='', encoding='utf-8')): t[r['row_id']] = ORDER[r['truth_class']]
    return t

def rescore_fresh(P, rows, y):
    """LOWER-BAR-ASK 0.97 (exam_fresh GONOGO_lba097) on probabilities P -> (final, asked, piles)."""
    pa = E.mode_a(rows, P); pb = guarded(P, E.MARGIN); mech = np.array([ORDER[r['class']] for r in rows]); conf = P.max(1)
    fin, asked = F.configs(pa, pb, mech, conf)['GONOGO_lba097']
    d = F.piles(fin, asked, pa, y)
    return fin, asked, {k: d[k] for k in ('answered', 'right', 'loose', 'tight', 'asked', 'rightPct', 'loosePct', 'askedPct')}

def rescore_old(P, rows, y):
    """mode (a), no bar (a_none): exact / loose / tight."""
    pa = E.mode_a(rows, P)
    return pa, {'right': int((pa == y).sum()), 'loose': int((pa < y).sum()), 'tight': int((pa > y).sum()), 'n': len(y)}

def metrics(P, Pt):
    flips = int(((P.max(1) >= 0.97) != (Pt.max(1) >= 0.97)).sum())
    return {'max_abs_p_vs_torch': float(np.abs(P - Pt).max()), 'mean_abs_p_vs_torch': float(np.abs(P - Pt).mean()),
            'argmax_agree': int((P.argmax(1) == Pt.argmax(1)).sum()), 'n': len(P), 'maxp_097_side_flips': flips}

def evaluate():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(X.CKPT)
    inputs = {}
    for ex in EXAMS:
        rows = [json.loads(l) for l in open(X.INPUTS[ex]) if l.strip()]
        inputs[ex] = (rows, tok([fmt_text(r) for r in rows], truncation=True, max_length=X.MAXLEN)['input_ids'], np.load(os.path.join(M1, f'probs-torch-{ex}.npy')).astype(np.float64))
    yf = truth_fresh(); yo = truth_old()
    y = {'exam-2026-11-03-fresh': np.array([yf[r['id']] for r in inputs['exam-2026-11-03-fresh'][0]]),
         'exam-2026-09-22': np.array([yo[r['id']] for r in inputs['exam-2026-09-22'][0]])}
    ref = {}
    for ex, (rows, _, Pt) in inputs.items():
        ref[ex] = rescore_fresh(Pt, rows, y[ex]) if ex.endswith('fresh') else rescore_old(Pt, rows, y[ex])
    out = {'reference_torch_fp32': {ex: ref[ex][-1] for ex in ref}, 'variants': {}}
    for name, f in FILES.items():
        path = os.path.join(M1, f); v = {'file': f, 'size_mb': round(os.path.getsize(path) / 1e6, 2), 'sha256': X.sha256(path)}
        for batch in (1, 32):
            b = {}
            for ex, (rows, ids, Pt) in inputs.items():
                P = run(path, ids, batch).astype(np.float64)
                np.save(os.path.join(M1, f'probs-{name}-b{batch}-{ex}.npy'), P.astype(np.float32))
                m = metrics(P, Pt)
                if ex.endswith('fresh'):
                    fin, asked, d = rescore_fresh(P, rows, y[ex])
                    m['lba097'] = d; m['rows_changed_vs_torch'] = int(((fin != ref[ex][0]) | (asked != ref[ex][1])).sum())
                else:
                    pa, d = rescore_old(P, rows, y[ex]); m['mode_a_no_bar'] = d; m['rows_changed_vs_torch'] = int((pa != ref[ex][0]).sum())
                b[ex] = m
            v[f'batch{batch}'] = b
            print(name, f'batch{batch}', json.dumps({ex: {k: m[k] for k in ('max_abs_p_vs_torch', 'argmax_agree', 'maxp_097_side_flips', 'rows_changed_vs_torch')} for ex, m in b.items()}), flush=True)
        out['variants'][name] = v
    json.dump(out, open(os.path.join(M1, 'variants-py.json'), 'w'), indent=1)

if __name__ == '__main__':
    {'build': build, 'eval': evaluate}[sys.argv[1]]()
