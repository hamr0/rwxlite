"""Round 14 step 2 (docs/product/prd-bge-teacher.md sections 3-4): R13 vs r14-bge on the round-13 val set (4,180 rows).
Writes the p files (p_is_x = px, p_changes = pw + px, at each model's T), standalone argmax numbers and T fits, then runs
m1/r14-compare.mjs (rwxmap's real second pass: mode a cut sweep, mode b). Nothing in rwxmap or the server is touched.
Run (3 threads is plenty; the batch-1 pass over bge-base takes a few minutes):
  nice -n 19 python3 -I m1/r14-compare.py --work DIR --tree RWXMAP_PRE --r14-ckpt CKPT/final --r14-npy probs-r14-bge-val.npy --r13-npy probs-r13-val.npy
where RWXMAP_PRE is the rwxmap tree at the cut sweep (see the header of m1/r14-compare.mjs) and CKPT/final is the r14-bge checkpoint.
Sources per model: shipped = rwxlite 0.3.1 fp32 predictions csv that rwxmap's sweep used (R13 only, T 0.991463, sha-checked);
b1 = PyTorch fp32 batch 1 from the checkpoint (the way r13-valpick.py got T); npy = finetune.py's saved val probabilities (T=1 softmax,
padded batches of 128, row order = val.parquet = val.jsonl). The primary r14-bge numbers are b1; npy is a cross-check.
T is fitted exactly as r13-valpick.py temp_fit (bounded scalar minimiser of the val NLL on log-probabilities)."""
import sys, os, json, argparse, hashlib, subprocess, collections, csv, site
sys.path.append(site.getusersitepackages())
import numpy as np
from scipy.optimize import minimize_scalar
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--tree', required=True)
ap.add_argument('--r14-ckpt', required=True); ap.add_argument('--r14-npy', required=True); ap.add_argument('--r13-npy', required=True)
ap.add_argument('--student-ckpt'); ap.add_argument('--student-npy')   # optional third model (step 3 distilled student), scored like r14-bge
ap.add_argument('--r13-ckpt', default=os.path.join(R, 'data/round13/models/R13')); ap.add_argument('--val', default=os.path.join(R, 'data/round13/val.jsonl'))
ap.add_argument('--rwxmap-val', default='/home/hamr/PycharmProjects/rwxmap/.claude/scratchpad/rwxlite-val'); ap.add_argument('--threads', type=int, default=3)
a = ap.parse_args(); os.makedirs(a.work, exist_ok=True)
T13 = 0.991463; RANK = {'r': 0, 'w': 1, 'x': 2}; MODEL = 'rwxlite-0.3.1+bbe1997d'   # replay label only; one string per p file
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
val = [json.loads(l) for l in open(a.val) if l.strip()]; ids = [r['id'] for r in val]; y = np.array([r['y'] for r in val]); truth = [r['label'] for r in val]
OPS, TRUTH = f'{a.rwxmap_val}/ops.csv', f'{a.rwxmap_val}/val-truth.csv'
assert sha(OPS) == 'efa3c5d9009757cd24f8ab75c440f7787adab3eea57bf1b8dae80c99b3339413' and sha(TRUTH) == '0281ff33daf43f64629850e4c5425f224c124d5ba5a1b70b53fe371ff5f66ec5'
assert [r['id'] for r in csv.DictReader(open(OPS))] == ids and [r['label'] for r in csv.DictReader(open(TRUTH))] == truth, 'rwxmap val rows differ in id/order/label from val.jsonl'
def temp_fit(P, y):
    L = np.log(np.clip(P, 1e-12, 1))
    def nll(T):
        z = L / T; z -= z.max(1, keepdims=True); lp = z - np.log(np.exp(z).sum(1, keepdims=True)); return -lp[np.arange(len(y)), y].mean()
    return float(minimize_scalar(nll, bounds=(0.3, 5), method='bounded').x)
def softmax(L, T): z = L / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)
def logits_b1(d):
    import torch; from transformers import AutoTokenizer, AutoModelForSequenceClassification
    torch.set_num_threads(a.threads); tok = AutoTokenizer.from_pretrained(d); m = AutoModelForSequenceClassification.from_pretrained(d, num_labels=3).eval()
    ids_ = tok([r['text'] for r in val], truncation=True, max_length=128)['input_ids']; L = np.zeros((len(ids_), 3))
    with torch.no_grad():
        for i, x in enumerate(ids_):
            t = torch.tensor([x]); L[i] = m(input_ids=t, attention_mask=torch.ones_like(t)).logits[0].double().numpy()
    return L
def write_p(name, P):
    with open(os.path.join(a.work, f'p-{name}.jsonl'), 'w') as f:
        for i, r in enumerate(val): f.write(json.dumps({'id': r['id'], 'model': MODEL, 'pIsX': float(P[i, 2]), 'pChanges': float(P[i, 1] + P[i, 2])}) + '\n')
def standalone(P):
    c = collections.Counter(); 
    for k, t in zip(P.argmax(1), truth):
        d = int(k) - RANK[t]; c['right' if d == 0 else ('loose' if d < 0 else 'tight')] += 1
    return dict(right=c['right'], too_loose=c['loose'], too_tight=c['tight'])
meta = {}
# R13: shipped csv (primary, what rwxmap's cut sweep used)
pc = os.path.join(a.rwxmap_val, 'predictions-r13-val.csv'); assert sha(pc) == '6154fe749717a0bade4d4028f87cb196663d3b28d8da01a448d7ef12d1e6cdf0'
rows = {r['id']: r for r in csv.DictReader(open(pc))}; px = np.array([float(rows[i]['p_is_x']) for i in ids]); pch = np.array([float(rows[i]['p_changes']) for i in ids])
Psh = np.stack([1 - pch, pch - px, px], 1); write_p('R13-shipped', Psh); meta['R13-shipped'] = dict(T=T13, standalone=standalone(Psh))
# R13 / r14 from the npy files and from batch-1 checkpoint logits
for tag, npy, ck in (('R13', a.r13_npy, a.r13_ckpt), ('r14', a.r14_npy, a.r14_ckpt)) + ((('student', a.student_npy, a.student_ckpt),) if a.student_ckpt else ()):
    P1 = np.load(npy).astype(np.float64); Tn = T13 if tag == 'R13' else temp_fit(P1, y); Pn = softmax(np.log(np.clip(P1, 1e-12, 1)), Tn)
    write_p(f'{tag}-npy', Pn); meta[f'{tag}-npy'] = dict(T=Tn, T_fitted=tag != 'R13', standalone=standalone(Pn), npy_sha256=sha(npy))
    L = logits_b1(ck); np.save(os.path.join(a.work, f'logits-{tag}-b1.npy'), L)
    Tb = T13 if tag == 'R13' else temp_fit(softmax(L, 1.0), y); Pb = softmax(L, Tb); write_p(f'{tag}-b1', Pb)
    meta[f'{tag}-b1'] = dict(T=Tb, T_fitted=tag != 'R13', T_if_fitted=temp_fit(softmax(L, 1.0), y), standalone=standalone(Pb), ckpt_sha256=sha(os.path.join(ck, 'model.safetensors')),
                             max_abs_dp_vs_npy=float(np.abs(Pb - Pn).max()), argmax_diff_vs_npy=int((Pb.argmax(1) != Pn.argmax(1)).sum()))
meta['R13-npy']['T_if_fitted'] = temp_fit(np.load(a.r13_npy).astype(np.float64), y)
meta['R13-shipped']['max_abs_dp_vs_b1'] = float(np.abs(Psh - softmax(np.load(os.path.join(a.work, 'logits-R13-b1.npy')), T13)).max())
json.dump(meta, open(os.path.join(a.work, 'meta.json'), 'w'), indent=1); print(json.dumps(meta, indent=1))
subprocess.run(['node', os.path.join(R, 'm1/r14-compare.mjs'), '--tree', a.tree, '--ops', OPS, '--truth', TRUTH, '--pdir', a.work, '--out', os.path.join(a.work, 'report.json')], check=True)
