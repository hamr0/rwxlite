"""Round 15 (docs/wiki/prereg-r15.md sections 5 and 7): score one checkpoint on the 400 blind-reviewed holdout rows, weighted to the 25,033 disputed rows by disagreement_type
(same weights and the same 'pocket' as r15/label_holdout_score.py). PyTorch fp32, batch 1, max_len 128, input text = data/r15/labels/texts-r15.jsonl (the text bge and R13 were shown).
  python3 r15/r15_holdout_score.py --ckpt DIR --name NAME [--T 1.0] --truth data/r15/labels/claude-review-400.csv --out OUT.json [--threads 3]
Reports, for the checkpoint: STANDALONE argmax (the teacher's own opinion; T does not change it) and MODE A at 0.90 (replica of rwxmap secondPass as m1/exam5-score.py, lower only at p >= 0.90,
credential-set never lowered, mechanical letter/rule/review from the opinions file) at --T; plus the stored references from the same file: old bge (argmax), R13 mode a (r13_letter_modea) and mechanical.
--truth = data/r15/labels/d141/holdout-review-d141.csv (sha256 96a62488...); the stored references must reproduce 74.0/18.4/7.6 (bge) and 56.5/8.8/34.7 (R13 mode a) (the original review: 74.8/17.5/7.8 and 57.6/7.5/34.9) and the script says so.
Exclusive create of --out (scored once per checkpoint and T)."""
import argparse, csv, json, math, collections, hashlib, os
import numpy as np, pandas as pd, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
csv.field_size_limit(10**9)
ap = argparse.ArgumentParser()
for k in ('ckpt', 'name', 'truth', 'out'): ap.add_argument('--' + k, required=True)
ap.add_argument('--T', type=float, default=1.0); ap.add_argument('--threads', type=int, default=3); ap.add_argument('--cut', type=float, default=0.90)
a = ap.parse_args(); torch.set_num_threads(a.threads)
L = 'data/r15/labels/'; RK = {'r': 0, 'w': 1, 'x': 2}; FLOOR = 1e-15
S = {r['op_id']: r for r in csv.DictReader(open(L + 'disagree-sample-400.csv', newline='', encoding='utf-8'))}
R = {r['op_id']: r for r in csv.DictReader(open(a.truth, newline='', encoding='utf-8'))}
pop = json.load(open(L + 'opinions-report.json'))['disagreement_types']
assert set(S) == set(R) and len(S) == 400
op = pd.read_parquet(L + 'pick-200000-1-opinions.parquet').set_index('op_id').loc[list(S)]
text = {}
for l in open(L + 'texts-r15.jsonl', encoding='utf-8'):
    r = json.loads(l)
    if r['op_id'] in S: text[r['op_id']] = r['text']
assert len(text) == 400
n = collections.Counter(r['disagreement_type'] for r in S.values()); W = {t: pop[t] / n[t] for t in n}
pocket = [i for i in S if S[i]['disagreement_type'] in ('bge_w_r13_x_mech_x', 'bge_r_r13_x_mech_x')]
def score(ids, letters):
    c = collections.Counter(); tot = 0.0
    for i in ids:
        p, t = letters[i], R[i]['letter']; w = W[S[i]['disagreement_type']]
        c['exact' if p == t else ('loose' if RK[p] < RK[t] else 'tight')] += w; tot += w
    return {k: round(100 * c[k] / tot, 1) for k in ('exact', 'loose', 'tight')}
def probs(z):
    m = max(z); e = [math.exp(v - m) for v in z]; t = sum(e); return [v / t for v in e]
def read_answer(P):   # replica of rwxmap readAnswer on (r,w,x) probabilities at T already applied
    pr, pw, px = P; pc = pw + px; pr2 = 1 - pc; pw2 = pc - px
    z = [math.log(max(1 - pc, FLOOR)), math.log(max(pc - px, FLOOR)), math.log(max(px, FLOOR))]; pr, pw, px = probs(z); pc = pw + px; pr2 = 1 - pc; pw2 = pc - px
    if px >= pw2 and px >= pr2: return 'x', px
    return ('w', pw2) if pw2 >= pr2 else ('r', pr2)
def mode_a(M, rule, review, P):
    if review not in ('loose', 'tight'): return M
    Lt, p = read_answer(P)
    if Lt == M: return M
    if RK[Lt] > RK[M]: return Lt
    if rule != 'credential-set' and p >= a.cut: return Lt
    return 'x'
tok = AutoTokenizer.from_pretrained(a.ckpt); model = AutoModelForSequenceClassification.from_pretrained(a.ckpt).eval()
P = {}
with torch.no_grad():
    for i in S:
        x = torch.tensor([tok(text[i], truncation=True, max_length=128)['input_ids']]); lg = model(input_ids=x, attention_mask=torch.ones_like(x)).logits[0].double().numpy()
        z = lg / a.T; z -= z.max(); e = np.exp(z); P[i] = (e / e.sum()).tolist()
stand = {i: 'rwx'[int(np.argmax(P[i]))] for i in S}
ma = {i: mode_a(op.loc[i, 'mech_letter'], op.loc[i, 'mech_rule'], op.loc[i, 'mech_review'], P[i]) for i in S}
refs = {'bge_old_argmax': {i: S[i]['bge_letter'] for i in S}, 'r13_mode_a': {i: op.loc[i, 'r13_letter_modea'] for i in S}, 'mechanical': {i: S[i]['mech_letter'] for i in S}}
res = {'name': a.name, 'ckpt': a.ckpt, 'T': a.T, 'cut': a.cut, 'truth_sha256': hashlib.sha256(open(a.truth, 'rb').read()).hexdigest(), 'weighted_to_rows': round(sum(W[S[i]['disagreement_type']] for i in S)),
       'pocket_sample_rows': len(pocket), 'standalone': {'all': score(list(S), stand), 'pocket': score(pocket, stand)}, 'mode_a': {'all': score(list(S), ma), 'pocket': score(pocket, ma)}, 'refs': {}}
for k, v in refs.items(): res['refs'][k] = {'all': score(list(S), v), 'pocket': score(pocket, v)}
EXPECT = {'88680a82e66298e726cf63a15cf59280fe78eb1279c267214f79fa0890e449fc': ({'exact': 74.8, 'loose': 17.5, 'tight': 7.8}, {'exact': 57.6, 'loose': 7.5, 'tight': 34.9}),      # original review
          '96a624889bfd0f093e26809550ee4b311212e6b816e7abcb0fb7777c295977bd': ({'exact': 74.0, 'loose': 18.4, 'tight': 7.6}, {'exact': 56.5, 'loose': 8.8, 'tight': 34.7})}       # D141 review
e = EXPECT.get(res['truth_sha256']); res['refs_reproduce_stored_numbers'] = None if e is None else (res['refs']['bge_old_argmax']['all'] == e[0] and res['refs']['r13_mode_a']['all'] == e[1])
if os.path.exists(a.out): raise SystemExit(a.out + ' exists')
json.dump(res, open(a.out, 'x'), indent=1); print(json.dumps(res, indent=1))
