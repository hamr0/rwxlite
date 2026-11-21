"""Round 16 Q2 (docs/product/prereg-r16-small-runs.md): teacher probabilities (T=1, train/teacher_probs.py) -> softened soft targets softmax(log p / T), rows and order unchanged.
  python3 r16/soften_probs.py --in teacher-A-probs.npy --T 1.362087 --out teacher-A-soft1362.npy
log p = logits - logsumexp, so softmax(log p / T) = softmax(logits / T) exactly. float64 inside, float32 out, sidecar json with the input sha256."""
import argparse, hashlib, json
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--T', type=float, required=True); ap.add_argument('--out', required=True); a = ap.parse_args()
p = np.load(a.inp).astype(np.float64); z = np.log(np.clip(p, 1e-12, 1)) / a.T; z -= z.max(1, keepdims=True); q = np.exp(z); q /= q.sum(1, keepdims=True)
np.save(a.out, q.astype(np.float32)); sha = lambda f: hashlib.sha256(open(f, 'rb').read()).hexdigest()
json.dump({'in': a.inp, 'in_sha256': sha(a.inp), 'T': a.T, 'rows': len(q), 'out_sha256': sha(a.out), 'mean_top_in': float(p.max(1).mean()), 'mean_top_out': float(q.max(1).mean()), 'argmax_changed': int((p.argmax(1) != q.argmax(1)).sum())}, open(a.out + '.json', 'w'), indent=1)
print('rows', len(q), 'mean top', round(float(p.max(1).mean()), 4), '->', round(float(q.max(1).mean()), 4))
