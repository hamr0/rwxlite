#!/usr/bin/env python3
"""Held-out-vendor experiment assembly (docs/wiki/holdout-r11.md). No network, no training.
Run: python3 -I m1/holdout-assemble.py --r11 DIR --out DIR     (DIR for --r11 = output of m1/round11-assemble.py, sha-checked below)
r11 train = r10 train (92,864 rows) + 1,377 exam #3 rows. new5 = the exam #3 rows of neon, supabase, mux, netbird, novu (935 rows); ory + clerk (442) are dropped.
Writes OUT/{A,B,C}/{train,val,v3eval}.parquet, OUT/heldout-ids.txt, OUT/holdout-summary.json, OUT/holdout-sha256.txt. Deterministic (seed 1).
 A: r10 train + new5 (x1).          B: A + 4 extra copies of each new5 row (new5 x5 by duplication; ids repeat on purpose).
 C: new5 + 10,000 old train rows sampled stratified by (label, vendor): proportional allocation, >=1 row per non-empty stratum, largest-remainder rounding, per-stratum random.Random(1)."""
import argparse, collections, hashlib, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'train'))
sys.path.append(os.path.join(os.path.expanduser('~'), '.local', 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))
import pandas as pd
ap = argparse.ArgumentParser(); ap.add_argument('--r11', required=True); ap.add_argument('--out', required=True); A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
R11_SHA = {'train.jsonl': '766948c49bf1da609e92efb6b0d6ee5cc79a8ff1d5c68938f73c0259d2c95355', 'val.jsonl': 'b854024e09637b1b50681fa5accc52fa62b67c7d212e356525f0bb691891e0a5', 'v3eval.jsonl': '292c5fd831e0c5fedc9f120b9e9bb0a07dd3659f5973a72a16c29942f28efc00'}
HELD, NEW5 = {'ory', 'clerk'}, {'neon', 'supabase', 'mux', 'netbird', 'novu'}
N_OLD, N_R10, N_E3, DUP = 10000, 92864, 1377, 5
def fail(m): print('FAIL: ' + m, file=sys.stderr); sys.exit(1)
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
for n, h in R11_SHA.items():
    if sha(os.path.join(A.r11, n)) != h: fail(n + ' sha mismatch')
tr = [json.loads(l) for l in open(os.path.join(A.r11, 'train.jsonl')) if l.strip()]
if len(tr) != N_R10 + N_E3: fail('r11 train size')
old, e3 = tr[:N_R10], tr[N_R10:]
if not all(r['id'].startswith('ex3-') for r in e3) or any(r['id'].startswith('ex3-') for r in old): fail('old/exam3 split by id prefix')
new5 = [r for r in e3 if r['vendor'] in NEW5]; held = [r for r in e3 if r['vendor'] in HELD]
if len(new5) != 935 or len(held) != 442 or len(new5) + len(held) != N_E3: fail(f'counts new5 {len(new5)} held {len(held)}')
if {r['vendor'] for r in old} & (NEW5 | HELD): fail('exam3 vendor in old train')
# C: stratified old sample
st = collections.defaultdict(list)
for r in old: st[(r['label'], r['vendor'])].append(r)
keys = sorted(st); tot = len(old); raw = {k: N_OLD * len(st[k]) / tot for k in keys}
alloc = {k: max(1, int(raw[k])) for k in keys}
while sum(alloc.values()) != N_OLD:   # largest-remainder adjust (add) or trim the most over-allocated strata
    if sum(alloc.values()) < N_OLD: k = max((k for k in keys if alloc[k] < len(st[k])), key=lambda k: raw[k] - alloc[k])
    else: k = max((k for k in keys if alloc[k] > 1), key=lambda k: alloc[k] - raw[k])
    alloc[k] += 1 if sum(alloc.values()) < N_OLD else -1
samp = []
for k in keys: samp += random.Random(f'1|{k[0]}|{k[1]}').sample(st[k], alloc[k])
if len(samp) != N_OLD or len({r['id'] for r in samp}) != N_OLD: fail('C sample')
variants = {'A': old + new5, 'B': old + new5 * DUP, 'C': new5 + samp}
hid = {h['id'] for h in held}
for v, rows in variants.items():
    d = os.path.join(A.out, v); os.makedirs(d, exist_ok=True)
    if {r['vendor'] for r in rows} & HELD or any(r['id'] in hid for r in rows): fail(v + ' contains a held-out vendor/id')
    pd.DataFrame(rows).to_parquet(os.path.join(d, 'train.parquet'), index=False)
    for s in ('val', 'v3eval'):   # unchanged r10 splits (parquet = round10's: byte-identical to r10/r11 server copies)
        pd.read_parquet(os.path.join(A.r11, s + '.parquet')).to_parquet(os.path.join(d, s + '.parquet'), index=False)
open(os.path.join(A.out, 'heldout-ids.txt'), 'w').write('\n'.join(r['id'] for r in held) + '\n')
lab = lambda rows: dict(sorted(collections.Counter(r['label'] for r in rows).items()))
S = {'rows': {v: len(r) for v, r in variants.items()}, 'old_train': N_R10, 'new5': len(new5), 'heldout': len(held), 'new5_by_vendor': dict(collections.Counter(r['vendor'] for r in new5)),
     'heldout_by_vendor': dict(collections.Counter(r['vendor'] for r in held)), 'new5_labels': lab(new5), 'heldout_labels': lab(held), 'old_labels': lab(old), 'C_old_sample_labels': lab(samp),
     'C_strata': len(keys), 'C_vendors_in_sample': len({r['vendor'] for r in samp}), 'C_vendors_in_old': len({r['vendor'] for r in old}), 'C_new5_share_pct': round(100 * len(new5) / (len(new5) + N_OLD), 2),
     'A_new5_share_pct': round(100 * len(new5) / len(variants['A']), 2), 'B_new5_share_pct': round(100 * 5 * len(new5) / len(variants['B']), 2), 'input_sha256': R11_SHA}
json.dump(S, open(os.path.join(A.out, 'holdout-summary.json'), 'w'), indent=1, sort_keys=True)
names = sorted(os.path.join(v, f'{s}.parquet') for v in variants for s in ('train', 'val', 'v3eval')) + ['heldout-ids.txt', 'holdout-summary.json']
with open(os.path.join(A.out, 'holdout-sha256.txt'), 'w') as f:
    for n in names: f.write(f'{sha(os.path.join(A.out, n))}  {n}\n')
print(json.dumps(S, indent=1, sort_keys=True)); print(open(os.path.join(A.out, 'holdout-sha256.txt')).read())
