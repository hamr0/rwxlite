"""M1: the decision-rule parity fixture for rwxmap.

  .venv/bin/python m1/decision-fixture.py
Writes test/fixtures/decision.jsonl: one row per fresh-exam operation (949):
  {id, method, state (5 fields), lean {class, rule}, jev_tier (as given, may be null), isX, changes, expected {letter, asked}}
where isX = p(x), changes = p(w)+p(x) from the default model's calibrated probabilities, and expected is the
pre-registered rule: exam_score.mode_a, then exam_fresh.configs()['GONOGO_lba097'] (lower-bar-ask at 0.97).
Imports the pre-registered scripts unchanged. Never reads truth.
"""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'train'))
import exam_score as E
import exam_fresh as F
from common import LABELS, ORDER

PROBS = os.path.join(ROOT, 'data', 'm1', 'probs-int8-pc-b1-exam-2026-11-03-fresh.npy')
MODEL = 'int8 per-channel (model-int8-pc.onnx, the default), batch 1, calibrated T=0.844'

rows = F.load_inputs(); assert len(rows) == 949
P = np.load(PROBS).astype(np.float64); assert P.shape == (949, 3)
print(f'model: {MODEL}; probs: {os.path.relpath(PROBS, ROOT)}')
pa = E.mode_a(rows, P); mech = np.array([ORDER[r['class']] for r in rows]); conf = P.max(1)
fin, asked = F.configs(pa, pa, mech, conf)['GONOGO_lba097']
out = os.path.join(ROOT, 'test', 'fixtures', 'decision.jsonl')
with open(out, 'w') as f:
    for i, r in enumerate(rows):
        f.write(json.dumps({
            'id': r['id'], 'method': r['method'],
            'state': {k: r.get(k) for k in ('method', 'path', 'operationId', 'summary', 'description')},
            'lean': {'class': r['class'], 'rule': r['rule']}, 'jev_tier': r['jev_tier'],
            'isX': float(P[i, 2]), 'changes': float(P[i, 1] + P[i, 2]),
            'expected': {'letter': LABELS[fin[i]], 'asked': bool(asked[i])},
        }) + '\n')
low = int((pa < mech).sum()); rai = int((pa > mech).sum()); keep = int((pa == mech).sum())
print(f'wrote {os.path.relpath(out, ROOT)}: {len(rows)} rows; lowerings {low}, raises {rai}, keeps {keep}, asked {int(asked.sum())}')
