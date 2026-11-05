"""Shared by exam4_predict.py and exam4_score.py (docs/wiki/exam-prereg-exam4.md). New file; exam3_* are untouched. Imports exam_score /
exam_fresh / common / tune_cuts UNCHANGED. ONNX on CPU, batch 1 (the shipped int8 file depends on batch composition).
Differences from exam3_common: the baseline is the PUBLISHED v0.2.0 release set (data/m1/release, whose manifest-exact.json carries
`rwxlite-0.2.0+8503b655`; exam3 read the stale data/m1/manifest-fp32.json = 0.1.0), and every model string / T is read from the manifest
and checked against the constants below.
"""
import os, hashlib, json
import numpy as np
from common import ROOT

REL020 = os.path.join(ROOT, 'data', 'm1', 'release')   # published v0.2.0 assets
R11 = os.path.join(ROOT, 'data', 'm1-r11')              # candidate r11 build
REAL_DIR = os.path.realpath(os.path.join(ROOT, 'data', 'exam4'))   # the ONLY work-dir a real (non-smoke) run may use
OPS_SHA = 'e9836ff2f9e8288e3721f97506ed666b871a3486f7b781c544b5234a0b5da0b4'      # rwxmap 1a1cc38 data/exam4-2026-11-04/ops.csv
TRUTH_SHA = 'b76c55fb30235726489574c90425c2c53b8343467e2fd918603952d135313c45'    # the only truth the scorer accepts
N_ROWS = 1505
VOCAB_SHA = '07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3'
MAXLEN = 128
# name -> dict(dir, model file, manifest file, model sha256, manifest sha256, expected model string, T)
MODELS = {
    'v020-int8pc': dict(dir=REL020, file='model-int8-pc.onnx', manifest='manifest.json', sha='8ad0a182b37237adc819bda2c03c01f0cb0e40afc2b20bdacb06193cd62a8844',
                        msha='10407b787fae2cadc318780a8c4ad171dc07af1389129c284bfd85c54f6b38bc', model='rwxlite-0.2.0+8ad0a182', T=0.844),
    'v020-fp32':   dict(dir=REL020, file='model-fp32.onnx', manifest='manifest-exact.json', sha='8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b',
                        msha='a484251cd4daf9c6fc7c8d2cb3f4a43f0cbdd6f4447d2c9ff65721a2f767b774', model='rwxlite-0.2.0+8503b655', T=0.844),
    'r11-int8pc':  dict(dir=R11, file='model-int8-pc.onnx', manifest='manifest.json', sha='adc6e6c130f8ba1716fa6b31e1ddce27e4b8eea8c76b336b8c1d53efdf3ea3e2',
                        msha='ff1ed6f12d7e6d237a96be2e600fa0da3438fd9a085801092b453df829cd052c', model='rwxlite-0.3.0+adc6e6c1', T=0.843),
    'r11-fp32':    dict(dir=R11, file='model-fp32.onnx', manifest='manifest-exact.json', sha='252f31811a1a9316cea0c6fd3404f3674c9e253613604fcc46a5832377e43bf6',
                        msha='65e84b7697f725bac41550afd001aefe532ad2dd2ed1ce41ca6a349138244a80', model='rwxlite-0.3.0+252f3181', T=0.843),
}

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def check_models():
    """Refuse to run unless every model file, manifest and vocab.txt match the frozen sha256, the manifest names the file and its sha, the model
    string is rwxlite-<manifest version>+<sha8> and equals the frozen one, and the manifest temperature (0.844 when absent) equals T. -> {name: model string}"""
    out = {}
    for name, m in MODELS.items():
        for fn, want in ((m['file'], m['sha']), (m['manifest'], m['msha']), ('vocab.txt', VOCAB_SHA)):
            got = sha256(os.path.join(m['dir'], fn))
            if got != want: raise SystemExit(f'HASH MISMATCH {name}: {os.path.join(m["dir"], fn)} is {got}, frozen {want}')
        mf = json.load(open(os.path.join(m['dir'], m['manifest'])))
        assert mf['modelFile'] == m['file'] and mf['files'][m['file']] == m['sha'] and mf['files']['vocab.txt'] == VOCAB_SHA, f'{name}: manifest does not match its files'
        ms = f"rwxlite-{mf['version']}+{m['sha'][:8]}"
        assert mf['model'] == ms == m['model'], f'{name}: model string {mf["model"]} / {ms} != frozen {m["model"]}'
        assert float(mf.get('temperature', 0.844)) == m['T'], f'{name}: manifest temperature {mf.get("temperature")} != frozen {m["T"]}'
        out[name] = ms
    return out

def is_real(wd): return os.path.realpath(wd) == REAL_DIR

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
