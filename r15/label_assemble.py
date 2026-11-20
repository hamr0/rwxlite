"""Round 15 labelling: join the three opinions into data/r15/labels/pick-200000-1-opinions.{parquet,csv.gz}, opinions-report.json and disagree-sample-400.csv.
  python3 -I r15/label_assemble.py --pick data/r15/picks/pick-200000-1.csv.gz --mech mech.jsonl --r13 r13-modea.jsonl --bge-chunks DIR --texts texts.jsonl \
      --runtimes runtimes.json --out data/r15/labels
bge: RAW logits from the server chunks; bge_raw_* = softmax(logits), bge_p_* = softmax(logits / T), T = 0.994240 (the T r14-bge was calibrated with). bge_letter = argmax of the T-scaled
probabilities (tie -> tighter class). Letters r<w<x. No opinion is judged here; this only joins and counts."""
import argparse, csv, gzip, json, os, glob, collections, random, site
site.addsitedir(site.getusersitepackages())
import numpy as np, pandas as pd
csv.field_size_limit(10**9)
ap = argparse.ArgumentParser()
for k in ('pick', 'mech', 'r13', 'bge-chunks', 'texts', 'runtimes', 'out'): ap.add_argument('--' + k, required=True)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
T = 0.994240; LET = np.array(['r', 'w', 'x']); RANK = {'r': 0, 'w': 1, 'x': 2}
rd = lambda f: [json.loads(l) for l in open(f) if l.strip()]
with gzip.open(a.pick, 'rt', newline='') as f: pick = pd.DataFrame(list(csv.DictReader(f)))
base = pick[['op_id', 'method', 'path', 'operationId', 'summary', 'description', 'source', 'vendor_id', 'vendor_kind', 'spec_sha256']].copy()
mech = pd.DataFrame(rd(a.mech)); r13 = pd.DataFrame(rd(a.r13)); texts = rd(a.texts)
assert list(mech.op_id) == list(base.op_id) == list(r13.op_id) == [t['op_id'] for t in texts], 'op_id order differs'
L = np.concatenate([np.load(p) for p in sorted(glob.glob(os.path.join(a.bge_chunks, 'chunk-*.npy')))]).astype(np.float64)
assert L.shape == (len(base), 3), L.shape
def sm(Z):
    Z = Z - Z.max(1, keepdims=True); E = np.exp(Z); return E / E.sum(1, keepdims=True)
raw, sc = sm(L), sm(L / T)
def argmax_tight(P):  # tie -> tighter class (higher rank)
    return LET[2 - np.argmax(P[:, ::-1], axis=1)]
d = base.copy()
for i, c in enumerate('rwx'): d[f'bge_p_{c}'] = sc[:, i]
for i, c in enumerate('rwx'): d[f'bge_raw_p_{c}'] = raw[:, i]
d['bge_letter'] = argmax_tight(sc); d['bge_conf'] = sc.max(1)
d['r13_letter_modea'] = r13.r13_letter_modea.values; d['r13_sent'] = r13.r13_sent.values; d['r13_rule'] = r13.r13_rule.values
for c in 'rwx': d[f'r13_p_{c}'] = r13[f'p_{c}'].values
d['mech_letter'] = mech.mech_letter.values; d['mech_rule'] = mech.mech_rule.values; d['mech_review'] = mech.mech_review.values
d['mech_lean'] = (mech.mech_letter + ' ' + mech.mech_rule).values
d['r13_error'] = r13.error.values
d['agree_all'] = (d.bge_letter == d.r13_letter_modea) & (d.r13_letter_modea == d.mech_letter)
d['disagreement_type'] = np.where(d.agree_all, '', 'bge_' + d.bge_letter + '_r13_' + d.r13_letter_modea + '_mech_' + d.mech_letter)
d.to_parquet(os.path.join(a.out, 'pick-200000-1-opinions.parquet'), index=False)
d.drop(columns=['bge_conf']).to_csv(os.path.join(a.out, 'pick-200000-1-opinions.csv.gz'), index=False, compression='gzip')
# ---- report
n = len(d); O = {'bge': 'bge_letter', 'r13': 'r13_letter_modea', 'mech': 'mech_letter'}
miss = {'bge_missing': int(np.isnan(L).any(1).sum()), 'r13_p_missing': int(d.r13_p_r.isna().sum()), 'r13_errors': int(d.r13_error.notna().sum()), 'mech_missing': int(d.mech_letter.isna().sum())}
rep = {'rows': n, 'bge_T': T, 'coverage': {'rows_labelled': {'bge': n - miss['bge_missing'], 'r13': n - miss['r13_errors'], 'mech': n - miss['mech_missing']}, 'missing': miss,
       'note': 'every row has all three opinions unless a missing count above is non-zero; r13_sent = rows mechanical marked loose/tight (mode a asks R13 only on those; the rest keep the mechanical letter, R13 probabilities for them are stored for information)',
       'r13_sent_rows': int(d.r13_sent.sum())}}
rep['letter_distribution'] = {k: {c: int((d[col] == c).sum()) for c in 'rwx'} for k, col in O.items()}
agree = lambda x, y: float((d[x] == d[y]).mean())
rep['agree_all_rate'] = float(d.agree_all.mean()); rep['agree_all_rows'] = int(d.agree_all.sum())
rep['pairwise_agreement'] = {f'{p}_{q}': agree(O[p], O[q]) for p, q in (('bge', 'r13'), ('bge', 'mech'), ('r13', 'mech'))}
rep['confusion'] = {}
for p, q in (('bge', 'r13'), ('bge', 'mech'), ('r13', 'mech')):
    ct = pd.crosstab(d[O[p]], d[O[q]]).reindex(index=list('rwx'), columns=list('rwx'), fill_value=0)
    rep['confusion'][f'{p}(rows)_vs_{q}(cols)'] = {r: {c: int(ct.loc[r, c]) for c in 'rwx'} for r in 'rwx'}
vc = d.disagreement_type[d.disagreement_type != ''].value_counts()
rep['disagreement_types'] = {k: int(v) for k, v in vc.items()}
def brk(col):
    out = {}
    for k, g in d.groupby(col):
        out[str(k)] = {'rows': int(len(g)), 'agree_all': float(g.agree_all.mean()), 'bge_r13': float((g.bge_letter == g.r13_letter_modea).mean()), 'bge_mech': float((g.bge_letter == g.mech_letter).mean()), 'r13_mech': float((g.r13_letter_modea == g.mech_letter).mean())}
    return out
rep['agreement_by_source'] = brk('source'); rep['agreement_by_vendor_kind'] = brk('vendor_kind')
edges = [0, .4, .5, .6, .7, .8, .9, .95, .99, .999, 1.0000001]
h, _ = np.histogram(d.bge_conf, bins=edges)
rep['bge_confidence_histogram'] = {f'[{edges[i]},{min(edges[i+1], 1)})': int(h[i]) for i in range(len(h))}
rep['bge_confidence_by_agreement'] = {'agree_all_median': float(d.bge_conf[d.agree_all].median()), 'disagree_median': float(d.bge_conf[~d.agree_all].median())}
rep['runtimes'] = json.load(open(a.runtimes))
json.dump(rep, open(os.path.join(a.out, 'opinions-report.json'), 'w'), indent=1)
# ---- disagreement sample: 400 rows, stratified by type (equal share per type, shares a type cannot fill go to the others), seed 1
rng = random.Random(1); types = sorted(vc.index); quota = {}; left = 400; rem = {t: int(vc[t]) for t in types}
active = list(types)
while active and left > 0:
    share = max(1, left // len(active)); nxt = []
    for t in list(active):
        take = min(share, rem[t] - quota.get(t, 0), left)
        quota[t] = quota.get(t, 0) + take; left -= take
        if quota[t] < rem[t]: nxt.append(t)
    if left > 0 and len(nxt) == len(active) and share == 1: break
    active = nxt
pick_idx = []
for t in types:
    idx = list(d.index[d.disagreement_type == t]); rng.shuffle(idx); pick_idx += idx[:quota.get(t, 0)]
s = d.loc[pick_idx, ['op_id', 'method', 'path', 'summary', 'description', 'disagreement_type', 'bge_letter', 'bge_p_r', 'bge_p_w', 'bge_p_x', 'r13_letter_modea', 'r13_p_r', 'r13_p_w', 'r13_p_x', 'mech_letter', 'mech_lean', 'source', 'vendor_kind']].copy()
s['description'] = s.description.str.slice(0, 1500)
s = s.sort_values(['disagreement_type', 'op_id']); s.to_csv(os.path.join(a.out, 'disagree-sample-400.csv'), index=False)
print(json.dumps({k: rep[k] for k in ('rows', 'coverage', 'letter_distribution', 'agree_all_rate', 'pairwise_agreement')}, indent=1)); print('sample', len(s), dict(s.disagreement_type.value_counts()))
