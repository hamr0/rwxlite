#!/usr/bin/env python3
"""Round 10, step 1 (prep only; no training, no Jev, no network). Run: python3 m1/round10-build.py [--data DIR]
DIR defaults to the main repo's gitignored data dir; outputs go to DIR/round10/. See docs/product/prd.md "Round 10".
A  rebuild leans (class + rule) of train/val/v3eval rows from data/m0/mechanical.jsonl.gz (joined on id, as build_dataset.py)
B  duplicate operations across specs (same vendor token, method, path, operationId) and split leaks
C  leak-shape candidates (cred-replace, logout) for hand check: candidates (with label+lean) and blind file
D  extra rows: 949 fresh-exam rows + 1,200 r9 hand rows (counts, overlap, vendors, exam #3 vendor check)
E  QUERY sample: ~10% of GET train rows, stratified by label x vendor, fixed seed
Nothing here relabels or writes a training file. Pre-registered train/exam_*.py and train/common.py are imported, not edited."""
import argparse, collections, csv, gzip, json, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'train'))
from common import fmt_text, clean, first_token, ORDER   # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--data', default='/home/hamr/PycharmProjects/rwxlite/data'); a = ap.parse_args()
D = a.data; OUT = os.path.join(D, 'round10'); os.makedirs(OUT, exist_ok=True)
SEED = 20261110
EXAM3 = {'clerk', 'neon', 'supabase', 'mux', 'netbird', 'ory', 'novu'}
summary = {}
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
def csvr(p): return list(csv.DictReader(open(p, newline='')))
def csvw(p, header, rows):
    with open(p, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
def fail(msg): print('FAIL: ' + msg, file=sys.stderr); sys.exit(1)

splits = {s: jl(os.path.join(D, 'train', s + '.jsonl')) for s in ('train', 'val', 'v3eval')}
for s, rows in splits.items(): print(s, len(rows))
mech = {}
with gzip.open(os.path.join(D, 'm0', 'mechanical.jsonl.gz'), 'rt') as f:
    for l in f:
        if l.strip(): r = json.loads(l); mech[r['id']] = r
print('mechanical rows', len(mech))

# ---- exam #3 vendor guard (everywhere: splits, mech rows used, fresh, r9)
def guard(name, providers):
    bad = sorted({first_token(p) for p in providers} & EXAM3)
    if bad: fail(f'exam #3 vendor in {name}: {bad}')
    print(f'exam3 guard ok: {name}')
for s, rows in splits.items(): guard(s, [r['provider'] for r in rows])

# ================= A. lean rebuild
A = {'unjoined': {}, 'joined': {}, 'changed': {}, 'class_changed': {}, 'rule_changed': {}, 'gain_credential_set': {}, 'text_format_mismatch': {}, 'path_mismatch': {}}
trans = collections.Counter(); trans_split = collections.defaultdict(collections.Counter); changed_rows = []; new_lean = {}
for s, rows in splits.items():
    nj = nu = nc = ncc = nrc = ngain = nfmt = npm = 0
    for r in rows:
        m = mech.get(r['id'])
        if m is None: nu += 1; continue
        nj += 1
        if (str(m['method']).upper(), m['path'], m['operationId']) != (r['method'], r['path'], r['operationId']): npm += 1
        old = {**m, 'class': r['mech'], 'rule': r['rule']}   # old lean on the current op text: must reproduce the stored text exactly
        if fmt_text(old) != r['text']: nfmt += 1
        new_lean[r['id']] = (m['class'], m['rule'])
        if (m['class'], m['rule']) != (r['mech'], r['rule']):
            nc += 1; ncc += m['class'] != r['mech']; nrc += m['rule'] != r['rule']; ngain += m['rule'] == 'credential-set'
            t = f"{r['mech']}/{r['rule']} -> {m['class']}/{m['rule']}"; trans[t] += 1; trans_split[t][s] += 1
            changed_rows.append([r['id'], s, r['provider'], r['method'], r['path'], r['mech'], r['rule'], m['class'], m['rule'], r['label']])
    for k, v in zip(A, (nu, nj, nc, ncc, nrc, ngain, nfmt, npm)): A[k][s] = v
csvw(os.path.join(OUT, 'lean-changes.csv'), ['id', 'split', 'provider', 'method', 'path', 'old_class', 'old_rule', 'new_class', 'new_rule', 'label'], changed_rows)
cs_total = sum(1 for m in mech.values() if m['rule'] == 'credential-set')
summary['A'] = {**A, 'transitions': dict(trans.most_common()), 'transitions_by_split': {t: dict(c) for t, c in trans_split.items()},
                'credential_set_in_dump': cs_total, 'credential_set_in_splits': sum(1 for v in new_lean.values() if v[1] == 'credential-set'),
                'rows_credential_set_by_split_label': {}}
cs_ids = {i for i, v in new_lean.items() if v[1] == 'credential-set'}
summary['A']['credential_set_rows'] = [[s, r['id'], r['method'], r['path'], r['label']] for s, rows in splits.items() for r in rows if r['id'] in cs_ids]

# ================= B. duplicates across specs
def okey(r): return (first_token(r['provider']), r['method'], r['path'], r['operationId'] or '')
groups = collections.defaultdict(list)
for s, rows in splits.items():
    for r in rows: groups[okey(r)].append((s, r))
dup = {k: v for k, v in groups.items() if len(v) > 1}
split_leak = {k: v for k, v in dup.items() if len({s for s, _ in v}) > 1}
lab_dis = {k: v for k, v in dup.items() if len({r['label'] for _, r in v}) > 1}
pairs = collections.Counter(tuple(sorted({s for s, _ in v})) for v in split_leak.values())
rows_in = lambda g: sum(len(v) for v in g.values())
within = collections.Counter(s for v in dup.values() for s in {x for x, _ in v} if sum(1 for x, _ in v if x == s) > 1)
extra_within = collections.Counter(); ex_groups = []
for k, v in dup.items():
    for s in {x for x, _ in v}:
        n = sum(1 for x, _ in v if x == s)
        if n > 1: extra_within[s] += n - 1
summary['B'] = {'groups': len(dup), 'rows_in_groups': rows_in(dup), 'extra_rows_beyond_first': rows_in(dup) - len(dup),
                'groups_split_across_splits': len(split_leak), 'rows_in_split_groups': rows_in(split_leak), 'split_pairs': {'+'.join(k): c for k, c in pairs.items()},
                'groups_with_same_split_dups': dict(within), 'removable_rows_within_split': dict(extra_within),
                'groups_label_disagree': len(lab_dis), 'rows_in_label_disagree': rows_in(lab_dis),
                'split_leak_rows_by_split': dict(collections.Counter(s for v in split_leak.values() for s, _ in v)),
                'dup_vendor_top': collections.Counter(k[0] for k in dup).most_common(10)}
csvw(os.path.join(OUT, 'dup-groups-split-leak.csv'), ['vendor', 'method', 'path', 'operationId', 'splits', 'providers', 'labels', 'ids'],
     [[*k, '+'.join(s for s, _ in v), '|'.join(r['provider'] for _, r in v), '|'.join(r['label'] for _, r in v), '|'.join(r['id'] for _, r in v)] for k, v in split_leak.items()])

# ================= C. leak-shape candidates (shape code is exec'd from m1/round10-shapes.py so the 59/45 counts cannot drift)
src = open(os.path.join(HERE, 'round10-shapes.py')).read().split("os.makedirs('data/round10'")[0].replace('os.chdir(ROOT)', '')
ns = {'__file__': os.path.join(HERE, 'round10-shapes.py')}; exec(compile(src, 'round10-shapes.py', 'exec'), ns)
def cdesc(i): return clean(mech[i].get('description'), 400)
cand = []   # (shape, split, row)
for s, rows in splits.items():
    for r in rows:
        for sh in ns['shapes'](r): cand.append((sh, s, r))
ids_c = []; seen = set()
for sh, s, r in cand:
    if r['id'] not in seen: seen.add(r['id']); ids_c.append(r['id'])
shape_of = collections.defaultdict(list)
for sh, s, r in cand: shape_of[r['id']].append(sh)
rows_c = []; blind = []
byid = {r['id']: (s, r) for s, rows in splits.items() for r in rows}
for i in ids_c:
    s, r = byid[i]; m = mech[i]
    rows_c.append([i, s, r['provider'], r['method'], r['path'], r['operationId'], clean(m.get('summary'), 200), cdesc(i), r['label'], f"{new_lean[i][0]} {new_lean[i][1]}", f"{r['mech']} {r['rule']}", '+'.join(shape_of[i])])
    blind.append([i, r['provider'], r['method'], r['path'], r['operationId'], clean(m.get('summary'), 200), cdesc(i)])
csvw(os.path.join(OUT, 'handcheck-candidates.csv'), ['id', 'split', 'provider', 'method', 'path', 'operationId', 'summary', 'description', 'current_label', 'lean_current_rwxmap', 'lean_in_training', 'shape'], rows_c)
# decoys: 30 non-candidate TRAIN rows, 6 per method (GET/POST/PUT/PATCH/DELETE), fixed seed, vendors outside the candidates' where possible
cand_vendors = {first_token(byid[i][1]['provider']) for i in ids_c}
drng = random.Random(SEED + 1); decoys = []
for meth in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
    pool = sorted((r['id'] for r in splits['train'] if r['method'] == meth and r['id'] not in seen), key=str)
    far = [i for i in pool if first_token(byid[i][1]['provider']) not in cand_vendors]
    pick = drng.sample(far, min(6, len(far)))
    if len(pick) < 6: pick += drng.sample([i for i in pool if i not in pick], 6 - len(pick))
    decoys += pick
key_rows = [[i, 0, '+'.join(shape_of[i]), byid[i][1]['label']] for i in ids_c]
for i in decoys:
    r = byid[i][1]; m = mech[i]
    blind.append([i, r['provider'], r['method'], r['path'], r['operationId'], clean(m.get('summary'), 200), cdesc(i)])
    key_rows.append([i, 1, '', r['label']])
decoy_far = sum(1 for i in decoys if first_token(byid[i][1]['provider']) not in cand_vendors)
random.Random(SEED).shuffle(blind)
csvw(os.path.join(OUT, 'handcheck-blind.csv'), ['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'], blind)
csvw(os.path.join(OUT, 'handcheck-key.csv'), ['id', 'is_decoy', 'shape', 'current_label'], sorted(key_rows))   # private; labellers never see it. handcheck-BRIEF.txt is hand-written
cnt = collections.Counter((sh, s) for sh, s, _ in cand)
summary['C'] = {'candidate_hits': dict(collections.Counter(sh for sh, _, _ in cand)), 'unique_rows': len(ids_c), 'by_shape_split': {f'{a_}/{b_}': c for (a_, b_), c in cnt.items()},
                'decoys': len(decoys), 'decoy_methods': dict(collections.Counter(byid[i][1]['method'] for i in decoys)), 'decoys_other_vendor': decoy_far, 'decoy_labels': dict(collections.Counter(byid[i][1]['label'] for i in decoys)), 'blind_rows': len(blind),
                'brief_exists': os.path.exists(os.path.join(D, 'gate-2026-11-03', 'BRIEF-v3.md'))}

# ================= D. extra rows
def classify(rows):
    p = subprocess.run(['node', os.path.join(HERE, 'round10-classify.mjs')], input=json.dumps(rows), capture_output=True, text=True)
    if p.returncode: fail('classify: ' + p.stderr[-500:])
    return json.loads(p.stdout)
# sanity: current-rwxmap classifyRow reproduces the dump on 3000 training rows (so it is a valid lean source for rows not in the dump)
samp = random.Random(1).sample(list(mech.values()), 3000)
cls = classify([{k: m.get(k) or '' for k in ('method', 'path', 'operationId', 'summary', 'description')} for m in samp])
agree = sum(1 for m, c in zip(samp, cls) if (m['class'], m['rule']) == (c['class'], c['rule']))
fx_ops = csvr(os.path.join(D, 'exam-2026-11-03-fresh', 'ops.csv')); fx_truth = {r['id']: r['label'] for r in csvr(os.path.join(D, 'exam-2026-11-03-fresh', 'truth.csv'))}
fx_A = {r['id']: r['label'] for r in csvr(os.path.join(D, 'exam-2026-11-03-fresh', 'labels-A.csv'))}; fx_B = {r['id']: r['label'] for r in csvr(os.path.join(D, 'exam-2026-11-03-fresh', 'labels-B.csv'))}
fx_rul = {r['id']: r['ruling'] for r in csvr(os.path.join(D, 'exam-2026-11-03-fresh', 'rulings.csv'))}
bad = [i for i in fx_truth if (fx_truth[i] != fx_rul[i] if i in fx_rul else (fx_A[i] != fx_B[i] or fx_truth[i] != fx_A[i]))]
if bad or len(fx_ops) != 949 or len(fx_truth) != 949 or not set(fx_truth.values()) <= set('rwx'): fail(f'fresh truth inconsistent {bad[:5]}')
guard('fresh', [r['provider'] for r in fx_ops])
fx_cls = classify([{k: r[k] for k in ('method', 'path', 'operationId', 'summary', 'description')} for r in fx_ops])
fx_old = {x['id']: (x['class'], x['rule']) for x in jl(os.path.join(D, 'exam-fresh-r8soft', 'inputs.jsonl'))}
fx_lean_changed = sum(1 for r, c in zip(fx_ops, fx_cls) if fx_old[r['id']] != (c['class'], c['rule']))
fx_cs = sum(1 for c in fx_cls if c['rule'] == 'credential-set')
key = {r['id']: r for r in csvr(os.path.join(D, 'r9-hand', 'key.csv'))}; blind9 = {r['id']: r for r in csvr(os.path.join(D, 'r9-hand', 'blind.csv'))}
r9A = {r['id']: r['label'] for r in csvr(os.path.join(D, 'r9-hand', 'labels-A.csv'))}; r9B = {r['id']: r['label'] for r in csvr(os.path.join(D, 'r9-hand', 'labels-B.csv'))}
if not (len(key) == len(r9A) == len(r9B) == 1200) or not set(r9A.values()) | set(r9B.values()) <= set('rwx'): fail('r9 labels malformed')
r9 = {i: max(r9A[i], r9B[i], key=lambda l: ORDER[l]) for i in key}   # stricter of A and B (README)
guard('r9', [blind9[i]['provider'] for i in blind9])
agid = {key[i]['ag_id']: i for i in key}
in_split = {i: s for s, rows in splits.items() for r in rows for i in [r['id']] if i in agid}
r9_cur = {agid[ai]: byid[ai][1]['label'] for ai in agid if ai in byid}
r9_lab_diff = sum(1 for i in key if i in r9_cur and r9_cur[i] != r9[i])
fx_vendors = collections.Counter(first_token(r['provider']) for r in fx_ops)
train_vendors = {first_token(r['provider']) for s in ('train', 'val') for r in splits[s]}
fx_ids_op = {(first_token(r['provider']), r['method'], r['path']) for r in fx_ops}
all_ops = {(first_token(r['provider']), r['method'], r['path']) for rows in splits.values() for r in rows}
summary['D'] = {'classify_sanity_agree_of_3000': agree,
    'fresh': {'n': len(fx_ops), 'label': dict(collections.Counter(fx_truth.values())), 'vendors': dict(fx_vendors), 'vendors_also_in_train_or_val': sorted(set(fx_vendors) & train_vendors),
              'opkey_overlap_with_splits': len(fx_ids_op & all_ops), 'lean_source': 'current rwxmap classifyRow (not in dump)', 'lean_differs_from_exam_time_inputs': fx_lean_changed, 'credential_set_rows': fx_cs,
              'rule_dist_now': dict(collections.Counter(c['rule'] for c in fx_cls).most_common()), 'lean_x_label_w_or_r': sum(1 for c, r in zip(fx_cls, fx_ops) if c['class'] == 'x' and fx_truth[r['id']] != 'x')},
    'r9': {'n': len(key), 'label_final': dict(collections.Counter(r9.values())), 'A_B_agree': sum(1 for i in key if r9A[i] == r9B[i]), 'all_ids_in_current_splits': sum(1 for ai in agid if ai in byid),
           'overlap_by_split': dict(collections.Counter(in_split.values())), 'differs_from_current_label': r9_lab_diff,
           'diff_transitions': dict(collections.Counter(f'{r9_cur[i]}->{r9[i]}' for i in key if i in r9_cur and r9_cur[i] != r9[i])),
           'vendors_n': len({key[i]['vendor'] for i in key}), 'vendor_top': collections.Counter(key[i]['vendor'] for i in key).most_common(8)}}
csvw(os.path.join(OUT, 'extra-fresh.csv'), ['id', 'provider', 'method', 'path', 'operationId', 'label', 'lean_class', 'lean_rule'], [[r['id'], r['provider'], r['method'], r['path'], r['operationId'], fx_truth[r['id']], c['class'], c['rule']] for r, c in zip(fx_ops, fx_cls)])
csvw(os.path.join(OUT, 'extra-r9.csv'), ['r9_id', 'ag_id', 'split', 'vendor', 'method', 'current_label', 'hand_label', 'A', 'B'], [[i, key[i]['ag_id'], in_split.get(key[i]['ag_id'], ''), key[i]['vendor'], key[i]['method'], r9_cur.get(i, ''), r9[i], r9A[i], r9B[i]] for i in key])

# ================= E. QUERY sample (GET train rows only)
gets = [r for r in splits['train'] if r['method'] == 'GET']
strata = collections.defaultdict(list)
for r in gets: strata[(r['label'], r['vendor'])].append(r['id'])
target = round(0.10 * len(gets)); rng = random.Random(SEED)
alloc = {k: int(0.1 * len(v)) for k, v in strata.items()}
rem = sorted(strata, key=lambda k: (-(0.1 * len(strata[k]) - alloc[k]), rng.random()))
for k in rem[:target - sum(alloc.values())]: alloc[k] += 1
picked = []
for k in sorted(strata): picked += rng.sample(sorted(strata[k]), alloc[k])
picked.sort(); open(os.path.join(OUT, 'query-sample.txt'), 'w').write('\n'.join(picked) + '\n')
lab = {r['id']: r for r in gets}
summary['E'] = {'get_train_rows': len(gets), 'target': target, 'picked': len(picked), 'label': dict(collections.Counter(lab[i]['label'] for i in picked)), 'label_of_get_train': dict(collections.Counter(r['label'] for r in gets)),
                'vendors_covered': len({lab[i]['vendor'] for i in picked}), 'vendors_in_get_train': len({r['vendor'] for r in gets}), 'strata': len(strata), 'strata_with_pick': sum(1 for v in alloc.values() if v)}
json.dump(summary, open(os.path.join(OUT, 'round10-prep-summary.json'), 'w'), indent=1)
print(json.dumps(summary, indent=1))
