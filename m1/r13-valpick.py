"""Round 13 step-1 pick on val (docs/wiki/prereg-r13.md section 6). Committed BEFORE any R13 candidate is scored.
For each candidate: PyTorch fp32 CPU, batch 1, max_len 128 -> logits on data/round13/val.jsonl (4,180 rows, v4 labels);
T = temp_fit on those logits (same function as train/tune_cuts.py, copied so this file does not depend on train/common.py);
then rwxmap secondPass replica, mode a, lower only at top-letter p >= 0.97, credential-set never lowered, mechanical letter
from each row's `mech` field. The replica (read_logits/read_answer/final_letter below, with T0 = 1 because p is already at
the candidate's T) is the one that matched rwxmap's real secondPass row for row in the round 12 calibration; the review/rule
columns come from vendor/mech.mjs (rwxmap's classifyOperations, run read-only over val).
Pick rule (frozen): fewest too-loose, then most exact, then R13 (the first candidate named R13, else the first listed).
Also prints the standalone, model-only numbers (argmax of the calibrated p vs the v4 label), for information only.
  python3 -I m1/r13-valpick.py --out DIR NAME=CKPT_DIR [NAME=CKPT_DIR ...] [--fixT NAME=0.844 ...] [--tok DIR]
Order of NAMEs decides the final tie (give R13 first). Needs node and /home/hamr/PycharmProjects/rwxmap (mech.mjs imports it).
Labels are read only from val.jsonl (allowed: val is the selection set)."""
import sys, os, json, csv, math, argparse, subprocess, collections, hashlib, time
import site
sys.path.append(site.getusersitepackages())   # python3 -I drops the user site where numpy/torch live
import numpy as np, torch
from scipy.optimize import minimize_scalar
from transformers import AutoTokenizer, AutoModelForSequenceClassification
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANK = {'r': 0, 'w': 1, 'x': 2}; FLOOR = 1e-15; THR = 0.97; MAXLEN = 128

# ---- replica of rwxmap secondPass (from the round 12 calibration lib.py, T0 = 1: p given is already calibrated) ----
def read_logits(px, pc):
    ok = all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in (px, pc)) and pc >= px
    if not ok: return None
    return [math.log(max(1 - pc, FLOOR)), math.log(max(pc - px, FLOOR)), math.log(max(px, FLOOR))]
def probs(z):
    m = max(z); e = [math.exp(v - m) for v in z]; t = sum(e); return [v / t for v in e]
def read_answer(z):
    pr, pw, px = probs(z); pc = pw + px; pr2 = 1 - pc; pw2 = pc - px
    if px >= pw2 and px >= pr2: return ('x', px)
    if pw2 >= pr2: return ('w', pw2)
    return ('r', pr2)
def final_letter(M, rule, review, z):
    if review not in ('loose', 'tight'): return M
    if z is None: return M if M == 'x' else 'x'
    Lt, p = read_answer(z)
    if Lt == M: return M
    if RANK[Lt] > RANK[M]: return Lt
    if rule != 'credential-set' and p >= THR: return Lt
    return 'x'
def outcome(f, t):
    d = RANK[f] - RANK[t]; return 'right' if d == 0 else ('loose' if d < 0 else 'tight')

def temp_fit(Pva, y):   # copy of train/tune_cuts.py temp_fit
    L = np.log(np.clip(Pva, 1e-12, 1))
    def nll(T):
        z = L / T; z -= z.max(1, keepdims=True); lp = z - np.log(np.exp(z).sum(1, keepdims=True))
        return -lp[np.arange(len(y)), y].mean()
    return minimize_scalar(nll, bounds=(0.3, 5), method='bounded').x
def softmax(L, T): z = L / T; z -= z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)
@torch.no_grad()
def logits(model, tok, texts):
    ids = tok(texts, truncation=True, max_length=MAXLEN)['input_ids']; L = np.zeros((len(ids), 3), np.float64)
    for i, x in enumerate(ids):
        a = torch.tensor([x]); L[i] = model(input_ids=a, attention_mask=torch.ones_like(a)).logits[0].double().numpy()
    return L
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

ap = argparse.ArgumentParser(); ap.add_argument('models', nargs='+'); ap.add_argument('--out', required=True)
ap.add_argument('--fixT', nargs='*', default=[]); ap.add_argument('--tok', default=os.path.join(R, 'data/train/ckpt-r11/final'))
ap.add_argument('--val', default=os.path.join(R, 'data/round13/val.jsonl'))
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); torch.set_num_threads(4)
fixT = {k: float(v) for k, v in (s.split('=') for s in a.fixT)}
val = [json.loads(l) for l in open(a.val) if l.strip()]; y = np.array([r['y'] for r in val]); truth = [r['label'] for r in val]
assert all('rwx'[r['y']] == r['label'] for r in val)
# mechanical review/rule from rwxmap's classifyOperations over the same rows (QUERY read as GET, as the product does)
ops = os.path.join(a.out, 'val-ops.csv')
with open(ops, 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'])
    for r in val: w.writerow([r['id'], r['provider'], 'GET' if r['method'] == 'QUERY' else r['method'], r['path'], r['operationId'] or '', r['summary'] or '', ''])
mj = os.path.join(a.out, 'val-mech.json')
subprocess.run(['node', os.path.join(R, 'vendor/mech.mjs'), json.dumps({'val': ops}), mj], check=True, capture_output=True)
mech = json.load(open(mj))['val']; assert [m['id'] for m in mech] == [r['id'] for r in val]
cls_diff = sum(m['cls'] != r['mech'] for m, r in zip(mech, val))
print(f'val rows {len(val)}; mech.mjs class differs from the val `mech` field on {cls_diff} rows (the `mech` field is used as the mechanical letter)')
mo = collections.Counter(outcome(r['mech'], t) for r, t in zip(val, truth)); print('mechanical alone', dict(mo))
tok = AutoTokenizer.from_pretrained(a.tok); texts = [r['text'] for r in val]; res = []
for spec in a.models:
    name, d = spec.split('=', 1); d = os.path.abspath(d); t0 = time.time()
    model = AutoModelForSequenceClassification.from_pretrained(d, num_labels=3).eval()
    L = logits(model, tok, texts); T = fixT.get(name) or float(temp_fit(softmax(L, 1.0), y)); P = softmax(L, T)
    c = collections.Counter(); 
    for i, r in enumerate(val):
        px, pc = float(P[i, 2]), float(P[i, 1] + P[i, 2]); m = mech[i]
        c[outcome(final_letter(r['mech'], m['rule'], m['review'], read_logits(px, pc)), truth[i])] += 1
    s = collections.Counter(outcome('rwx'[int(k)], t) for k, t in zip(P.argmax(1), truth))
    res.append(dict(name=name, dir=d, safetensors_sha256=sha(os.path.join(d, 'model.safetensors')), T=T, T_fixed=name in fixT,
                    product=dict(exact=c['right'], too_loose=c['loose'], too_tight=c['tight']),
                    standalone=dict(exact=s['right'], too_loose=s['loose'], too_tight=s['tight']), seconds=round(time.time() - t0)))
    np.save(os.path.join(a.out, f'logits-{name}-val.npy'), L); print(json.dumps(res[-1]), flush=True)
best = min(range(len(res)), key=lambda i: (res[i]['product']['too_loose'], -res[i]['product']['exact'], 0 if res[i]['name'] == 'R13' else 1, i))
print('\ncandidate   T        PRODUCT (right/loose/tight)     STANDALONE (right/loose/tight, info only)')
for r in res:
    p, s = r['product'], r['standalone']
    print(f"{r['name']:<11s} {r['T']:.4f}   {p['exact']:5d} / {p['too_loose']:3d} / {p['too_tight']:4d}          {s['exact']:5d} / {s['too_loose']:3d} / {s['too_tight']:4d}")
print(f"PICK (fewest too loose, then most exact, then R13): {res[best]['name']}  T = {res[best]['T']:.6f}")
json.dump(dict(val=a.val, val_sha256=sha(a.val), rows=len(val), pick=res[best]['name'], candidates=res), open(os.path.join(a.out, 'valpick.json'), 'w'), indent=1)
