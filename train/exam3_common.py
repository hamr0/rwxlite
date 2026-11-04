"""Shared by exam3_predict.py and exam3_score.py (docs/wiki/exam-prereg-exam3.md). Imports exam_score / exam_fresh / common / tune_cuts
UNCHANGED (mode_a, cuts, configs, piles); nothing in those files is edited. ONNX runs through onnxruntime on CPU, batch 1 (the shipped
int8 file depends on batch composition, so batch 1 is the reproducible choice).
"""
import os, hashlib, json
import numpy as np
from common import ROOT

M1 = os.path.join(ROOT, 'data', 'm1')          # shipped 0.2.0 files
R10 = os.path.join(ROOT, 'data', 'm1-r10')     # frozen round 10 files
VOCAB_SHA = '07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3'
# name -> (file, sha256 it must have, calibration temperature). Class order r, w, x.
MODELS = {
    'r10-int8pc':   (os.path.join(R10, 'model-int8-pc.onnx'), '093c908d492d07121159287b5beadd3d4d75c403a4cde4f701ac918475be1173', 0.858),
    'r10-fp32':     (os.path.join(R10, 'model-fp32.onnx'),    '8514ddccdafcda28ae468aced91673545c3c1d56201754e89a79dcb10ca61a26', 0.858),
    'v020-int8pc':  (os.path.join(M1, 'model-int8-pc.onnx'),  '8ad0a182b37237adc819bda2c03c01f0cb0e40afc2b20bdacb06193cd62a8844', 0.844),
    'v020-fp32':    (os.path.join(M1, 'model-fp32.onnx'),     '8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b', 0.844),
}
MAXLEN = 128

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def check_hashes():
    """Refuse to run unless every model file and vocab.txt match the frozen hashes."""
    for name, (path, want, _) in MODELS.items():
        got = sha256(path)
        if got != want: raise SystemExit(f'HASH MISMATCH {name}: {path} is {got}, frozen {want}')
    for d in (M1, R10):
        got = sha256(os.path.join(d, 'vocab.txt'))
        if got != VOCAB_SHA: raise SystemExit(f'HASH MISMATCH vocab.txt in {d}: {got}')
    return {n: v[1] for n, v in MODELS.items()}

def probs(path, ids, T):
    """Calibrated (n,3) probabilities from an ONNX file, batch 1."""
    import onnxruntime as ort
    o = ort.SessionOptions(); o.intra_op_num_threads = 4
    s = ort.InferenceSession(path, o, providers=['CPUExecutionProvider'])
    L = np.zeros((len(ids), 3), np.float64)
    for i, x in enumerate(ids):
        a = np.array([x], np.int64)
        L[i] = s.run(['logits'], {'input_ids': a, 'attention_mask': np.ones_like(a), 'token_type_ids': np.zeros_like(a)})[0][0]
    z = L / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)
