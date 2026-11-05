"""Round 12 predict (docs/wiki/prereg-r12.md). NEVER touches label/y/truth columns: holdout.jsonl is read through a whitelist (id,text,provider,method,path,operationId,summary).
Same path as holdout_predict.py: PyTorch fp32 CPU, batch 1, max_len 128, tokenizer of r11, T per model = temp_fit on val.jsonl.
  python3 train/r12_predict.py <out-dir>"""
import sys, os, json, csv, time, hashlib
import numpy as np, torch
sys.path.insert(0, os.path.dirname(__file__))
from common import fmt_text
from tune_cuts import temp_fit
from transformers import AutoTokenizer, AutoModelForSequenceClassification
OUT = sys.argv[1]; R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
torch.set_num_threads(4); MAXLEN = 128
MODELS = [('v020', 'data/train/ckpt-r8soft/final', 'rwxlite-v020-fp32'), ('r11', 'data/train/ckpt-r11/final', 'rwxlite-r11-fp32'),
          ('S0', 'data/round12/models/S0', None), ('S1', 'data/round12/models/S1', None), ('S2', 'data/round12/models/S2', None)]
TOKDIR = os.path.join(R, 'data/train/ckpt-r11/final')
KEEP = ('id', 'text', 'provider', 'method', 'path', 'operationId', 'summary')   # whitelist: no label, y, mech, rule, tier
def read_safe(p): return [{k: r[k] for k in KEEP} for r in map(json.loads, open(p))]
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
@torch.no_grad()
def logits(model, tok, texts):
    ids = tok(texts, truncation=True, max_length=MAXLEN)['input_ids']; L = np.zeros((len(ids), 3), np.float64)
    for i, x in enumerate(ids):
        a = torch.tensor([x]); L[i] = model(input_ids=a, attention_mask=torch.ones_like(a)).logits[0].double().numpy()
    return L
def softmax(L, T): z = L / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)
# val: text + label y are needed to fit T (val is not the holdout; allowed)
va = [json.loads(l) for l in open(os.path.join(R, 'data/round12/final/val.jsonl'))]; vtext = [r['text'] for r in va]; yv = np.array([r['y'] for r in va])
hold = read_safe(os.path.join(R, 'data/round12/final/holdout.jsonl'))
# ops.csv from exam4 source rows (description), text path asserted equal to holdout text
src = {r['id']: r for r in map(json.loads, open(os.path.join(R, 'data/exam4/inputs.jsonl')))}
def fix(r): return {**r, 'method': 'GET' if r['method'] == 'QUERY' else r['method'], 'rule': {'credential-set': 'cant-undo-verb'}.get(r['rule'], r['rule'])}  # as holdout_predict.py
for h in hold:
    s = src[h['id']]; assert fmt_text(fix(s)) == h['text'], h['id']
    assert (s['provider'], s['method'], s['path'], s['operationId']) == (h['provider'], h['method'], h['path'], h['operationId']), h['id']
    h['description'] = s.get('description') or ''
with open(os.path.join(OUT, 'ops.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'])
    for h in hold: w.writerow([h['id'], h['provider'], h['method'], h['path'], h['operationId'], h['summary'] or '', h['description']])
# leak rows
LEAK = ['gate3-0482', 'r9-0543', 'r9-0814', 'r9-0897', 'r9-1109', 'r9-1164']; lk = {}
for p in ('data/r12/inputs/gate3/inputs.jsonl', 'data/r12/inputs/r9hand/inputs.jsonl'):
    for r in map(json.loads, open(os.path.join(R, p))):
        if r['id'] in LEAK: assert fmt_text(fix(r)) == r['text'], r['id']; lk[r['id']] = r['text']
assert sorted(lk) == sorted(LEAK), lk.keys()
meta = {'holdout_rows': len(hold), 'val_rows': len(va), 'tokenizer': 'data/train/ckpt-r11/final', 'models': {}}; leaks = {}
for name, d, label in MODELS:
    d = os.path.join(R, d); tok = AutoTokenizer.from_pretrained(TOKDIR); model = AutoModelForSequenceClassification.from_pretrained(d, num_labels=3).eval()
    w = sha(os.path.join(d, 'model.safetensors')); mstr = f'{label}+{w[:8]}' if label else f'rwxlite-r12-{name}+{w[:8]}'; t0 = time.time()
    T = float(temp_fit(softmax(logits(model, tok, vtext), 1.0), yv)); P = softmax(logits(model, tok, [h['text'] for h in hold]), T)
    pis, pch = P[:, 2], P[:, 1] + P[:, 2]; assert ((0 <= pis) & (pis <= pch) & (pch <= 1 + 1e-12)).all()
    with open(os.path.join(OUT, f'p-{name}.jsonl'), 'w') as f:
        for i, h in enumerate(hold): f.write(json.dumps({'id': h['id'], 'model': mstr, 'pIsX': float(pis[i]), 'pChanges': float(pch[i])}) + '\n')
    PL = softmax(logits(model, tok, [lk[i] for i in LEAK]), T); leaks[name] = {}
    for j, i in enumerate(LEAK):
        k = int(PL[j].argmax()); leaks[name][i] = {'p_r': float(PL[j, 0]), 'p_w': float(PL[j, 1]), 'p_x': float(PL[j, 2]), 'top': 'rwx'[k], 'top_p': float(PL[j, k])}
    meta['models'][name] = {'dir': os.path.relpath(d, R), 'model_string': mstr, 'model_safetensors_sha256': w, 'T': round(T, 4), 'T_full': T, 'time_s': round(time.time() - t0, 1)}; print(name, meta['models'][name], flush=True)
json.dump(leaks, open(os.path.join(OUT, 'leaks-p.json'), 'w'), indent=1); json.dump(meta, open(os.path.join(OUT, 'predict-meta.json'), 'w'), indent=1); print('labels never read for holdout')
