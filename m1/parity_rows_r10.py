"""Round 10 Node parity input: the burned fresh-exam rows (already scored, and in r10 training: parity only, not a result).
Writes data/m1-r10/parity-rows.jsonl {state, lean, p:{int8-pc, fp32}} with Python ORT batch-1 probabilities at T=0.844 and the
Node text path (credential-set -> cant-undo-verb alias, as src/text.js)."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'train'))
import export_r10 as X
from common import ROOT, fmt_text
from transformers import AutoTokenizer
rows = [json.loads(l) for l in open(os.path.join(ROOT, 'data', 'exam-fresh-r8soft', 'inputs.jsonl')) if l.strip()]
tok = AutoTokenizer.from_pretrained(X.CKPT)
texts = [fmt_text({**r, 'rule': {'credential-set': 'cant-undo-verb'}.get(r['rule'], r['rule'])}) for r in rows]
ids = tok(texts, truncation=True, max_length=128)['input_ids']
T = 0.844
def P(path):
    z = X.run(path, ids, 1) / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)
p8, pf = P(X.INT8PC), P(X.FP32)
with open(os.path.join(X.D, 'parity-rows.jsonl'), 'w') as f:
    for i, r in enumerate(rows):
        f.write(json.dumps({'state': {k: r[k] for k in ('method', 'path', 'operationId', 'summary', 'description')}, 'lean': {'class': r['class'], 'rule': r['rule']},
                            'p': {'int8-pc': p8[i].tolist(), 'fp32': pf[i].tolist()}}) + '\n')
print('rows', len(rows))
