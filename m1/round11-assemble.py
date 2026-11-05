#!/usr/bin/env python3
"""Round 11 assembly: round 10's assembled splits + the 1,377 exam #3 rows (train only, one-hot truth, normal weight). No network, no training.
Run: RWXMAP_DIR=<rwxmap at 46235ea> python3 -I m1/round11-assemble.py [--r10 DIR] [--exam3 DIR] [--out DIR]
Reads --r10 (default rwxlite/data/round10: train/val/v3eval.jsonl, sha256-checked against its assembly-sha256.txt) and rwxmap's exam3 ops.csv + truth.csv (sha256-checked, read-only).
Leans: classifyRow of rwxmap at RWXMAP_DIR (m1/round10-classify.mjs), rule aliased by round10_aliases.text_rule, text by train/common.fmt_text (QUERY->GET moot: exam #3 has 0 QUERY ops).
Soft targets: rwxmap committed no Jev p per row for exam #3 (rows-c-jev.csv carries letters only) -> jev_p None, tier 'none', status 'fresh' -> one-hot (as r10's fresh rows).
Writes OUT/{train,val,v3eval}.{jsonl,parquet}, assembly-summary.json, assembly-sha256.txt. Deterministic."""
import argparse, collections, csv, hashlib, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'train')); sys.path.insert(0, HERE)
sys.path.append(os.path.join(os.path.expanduser('~'), '.local', 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))
import pandas as pd
from common import fmt_text, clean, first_token, ORDER, soft_targets   # noqa: E402
from round10_aliases import text_rule, check as alias_check            # noqa: E402
ap = argparse.ArgumentParser()
ap.add_argument('--r10', default='/home/hamr/PycharmProjects/rwxlite/data/round10')
ap.add_argument('--exam3', default='/home/hamr/PycharmProjects/rwxmap/data/exam3-2026-11-04')
ap.add_argument('--out', default=os.path.join(REPO, 'data', 'round11'))
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
EXAM3 = {'clerk', 'neon', 'supabase', 'mux', 'netbird', 'ory', 'novu'}
EXAM3_SHA = {'ops.csv': 'fff7afa983c7fc85e2073e5662c4c317c69e37a1dd92a04c7e5dc04ecf43d790', 'truth.csv': '929725d51397098b6f45d86a5a551e7f0c095875557a944c02e08930efdab3c0'}
def fail(m): print('FAIL: ' + m, file=sys.stderr); sys.exit(1)
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
def csvr(p): return list(csv.DictReader(open(p, newline='')))
alias_check()
for n, h in EXAM3_SHA.items():
    if sha(os.path.join(A.exam3, n)) != h: fail('exam3 ' + n + ' sha mismatch')
want = dict(l.split()[::-1] for l in open(os.path.join(A.r10, 'assembly-sha256.txt')) if l.strip())
for s in ('train', 'val', 'v3eval'):
    if sha(os.path.join(A.r10, s + '.jsonl')) != want[s + '.jsonl']: fail('r10 ' + s + '.jsonl sha mismatch')
old = {s: jl(os.path.join(A.r10, s + '.jsonl')) for s in ('train', 'val', 'v3eval')}
ops = csvr(os.path.join(A.exam3, 'ops.csv')); truth = {r['id']: r['label'] for r in csvr(os.path.join(A.exam3, 'truth.csv'))}
if len(ops) != 1377 or set(truth) != {o['id'] for o in ops} or not set(truth.values()) <= set(ORDER): fail('exam3 ops/truth inconsistent')
rmdir = os.environ.get('RWXMAP_DIR') or fail('set RWXMAP_DIR to rwxmap checkout at 46235ea')
p = subprocess.run(['node', os.path.join(HERE, 'round10-classify.mjs')], input=json.dumps([{k: o[k] for k in ('method', 'path', 'operationId', 'summary', 'description')} for o in ops]),
                   capture_output=True, text=True, env={**os.environ, 'RWXMAP_DIR': rmdir})
if p.returncode: fail('classify: ' + p.stderr[-400:])
cls = json.loads(p.stdout)
if any(o['method'].upper() == 'QUERY' for o in ops): fail('unexpected QUERY op in exam3')
new = []
for o, c in zip(ops, cls):
    lean = {'class': c['class'], 'rule': text_rule(c['rule']), 'method': o['method'], 'path': o['path'], 'operationId': o['operationId'], 'summary': o['summary'], 'description': o['description']}
    new.append({'id': o['id'], 'text': fmt_text(lean), 'label': truth[o['id']], 'y': ORDER[truth[o['id']]], 'status': 'fresh', 'jev_p': None, 'jev_pC': None, 'summary': clean(o['summary'], 200),
                'jev_pA': None, 'jev_pB': None, 'mech': c['class'], 'rule': c['rule'], 'tier': 'none', 'method': o['method'].upper(), 'provider': o['provider'],
                'vendor': first_token(o['provider']), 'path': o['path'], 'operationId': o['operationId']})
final = {'train': old['train'] + new, 'val': old['val'], 'v3eval': old['v3eval']}
# schema of added rows equals schema of existing train rows
if set(new[0]) != set(old['train'][0]): fail(f"schema differs: {set(new[0]) ^ set(old['train'][0])}")
# ---- assertions
allrows = [(s, r) for s in final for r in final[s]]
ids = collections.Counter(r['id'] for _, r in allrows); dups = [i for i, c in ids.items() if c > 1]
if dups: fail(f'duplicate ids {dups[:5]}')
okey = lambda r: (first_token(r['provider']), 'GET' if r['method'] == 'QUERY' else r['method'], r['path'], r['operationId'] or '')
spl = collections.defaultdict(set)
for s, r in allrows: spl[okey(r)].add(s)
leaks = [k for k, v in spl.items() if len(v) > 1]
if leaks: fail(f'op-key groups span splits: {len(leaks)} e.g. {leaks[:3]}')
e3 = {r['id'] for r in new}
if any(r['id'] in e3 for s in ('val', 'v3eval') for r in final[s]): fail('exam3 row outside train')
if {first_token(r['provider']) for s in ('val', 'v3eval') for r in final[s]} & EXAM3: fail('exam3 vendor in val/v3eval')
if {first_token(r['provider']) for r in old['train']} & EXAM3: fail('exam3 vendor already in r10 train')
if any('credential-set' in r['text'] for _, r in allrows): fail('credential-set in a text')
if any(r['label'] not in ORDER or r['y'] != ORDER[r['label']] for _, r in allrows): fail('label/y inconsistent')
for s in ('val', 'v3eval'):
    if final[s] != old[s]: fail(s + ' changed')
if final['train'][:len(old['train'])] != old['train']: fail('r10 train rows changed')
# text vs what the shipped model saw at exam time (data/exam3/inputs.jsonl, rwxlite repo, read-only), when present
inp = '/home/hamr/PycharmProjects/rwxlite/data/exam3/inputs.jsonl'; text_match = None
if os.path.exists(inp):
    seen = {r['id']: r['text'] for r in jl(inp)}; text_match = sum(1 for r in new if seen.get(r['id']) == r['text'])
    if text_match != 1377: fail(f'text differs from exam-time inputs on {1377 - text_match} rows')
# ---- write
for s in final:
    with open(os.path.join(A.out, s + '.jsonl'), 'w') as f:
        for x in final[s]: f.write(json.dumps(x) + '\n')
    pd.DataFrame(final[s]).to_parquet(os.path.join(A.out, s + '.parquet'), index=False)
def lab(rows): return dict(sorted(collections.Counter(r['label'] for r in rows).items()))
T = soft_targets(pd.DataFrame(new))
summary = {'rwxmap_dir': rmdir, 'rwxmap_ref': subprocess.run(['git', '-C', rmdir, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
  'before': {s: len(old[s]) for s in old}, 'after': {s: len(final[s]) for s in final}, 'added': len(new), 'label_before_train': lab(old['train']), 'label_after_train': lab(final['train']),
  'added_label_mix': lab(new), 'added_by_vendor': dict(sorted(collections.Counter(r['vendor'] for r in new).items())), 'added_by_vendor_label': {v: lab([r for r in new if r['vendor'] == v]) for v in sorted(EXAM3)},
  'added_by_method': dict(sorted(collections.Counter(r['method'] for r in new).items())), 'added_lean_class': dict(sorted(collections.Counter(r['mech'] for r in new).items())),
  'added_lean_rule': dict(sorted(collections.Counter(r['rule'] for r in new).items())), 'added_lean_vs_truth_agree': sum(1 for r in new if r['mech'] == r['label']),
  'added_soft_onehot': {'one_hot': int((T.max(1) == 1.0).sum()), 'soft': int((T.max(1) < 1.0).sum())}, 'exam_time_text_identical_rows': text_match,
  'input_sha256': {**{'exam3/' + k: v for k, v in EXAM3_SHA.items()}, **{'r10/' + k: v for k, v in want.items() if k.endswith('.jsonl')}},
  'asserts': {'no_duplicate_ids': True, 'no_opkey_group_spans_splits': True, 'exam3_rows_only_in_train': True, 'no_exam3_vendor_in_val_v3eval_or_r10_train': True, 'credential_set_not_in_any_text': True,
              'val_v3eval_and_r10_train_rows_unchanged': True, 'alias_check': True}, 'ids_total': len(ids)}
json.dump(summary, open(os.path.join(A.out, 'assembly-summary.json'), 'w'), indent=1, sort_keys=True)
names = [s + e for s in ('train', 'val', 'v3eval') for e in ('.jsonl', '.parquet')] + ['assembly-summary.json']
with open(os.path.join(A.out, 'assembly-sha256.txt'), 'w') as f:
    for n in names: f.write(f"{sha(os.path.join(A.out, n))}  {n}\n")
print(json.dumps(summary, indent=1, sort_keys=True)); print(open(os.path.join(A.out, 'assembly-sha256.txt')).read())
