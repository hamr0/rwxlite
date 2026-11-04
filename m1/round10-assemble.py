#!/usr/bin/env python3
"""Round 10, step 4: final assembly of the training data (no training, no network). Run: python3 -I m1/round10-assemble.py [--data DIR]
Reads DIR/train/{train,val,v3eval}.jsonl (never overwritten), DIR/m0/mechanical.jsonl.gz and the DIR/round10 inputs; writes DIR/round10/{train,val,v3eval}.{jsonl,parquet},
assembly-summary.json, assembly-rows.csv (id,split,source,orig_status) and assembly-sha256.txt. Deterministic. Plan: docs/product/prd.md "Round 10", step-4 plan.
Status choice: soft_targets() makes a row one-hot when status in ('delete','credential'); hand-labelled rows get status 'credential' (the only fit besides delete),
original status is kept in assembly-rows.csv. Fresh rows have jev_p None and tier 'none' -> one-hot with status 'fresh'."""
import argparse, collections, csv, gzip, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'train')); sys.path.insert(0, HERE)
import site
sys.path.append(os.path.join(os.path.expanduser('~'), '.local', 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))   # -I drops user site; numpy/pandas live there
import numpy as np, pandas as pd
from common import fmt_text, clean, first_token, ORDER, soft_targets   # noqa: E402
from round10_aliases import text_rule, check as alias_check            # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--data', default='/home/hamr/PycharmProjects/rwxlite/data'); D = ap.parse_args().data
IN = os.path.join(D, 'train'); R10 = os.path.join(D, 'round10'); os.makedirs(R10, exist_ok=True)
EXAM3 = {'clerk', 'neon', 'supabase', 'mux', 'netbird', 'ory', 'novu'}
ONEHOT_STATUS = 'credential'
def fail(m): print('FAIL: ' + m, file=sys.stderr); sys.exit(1)
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
def csvr(p): return list(csv.DictReader(open(p, newline='')))
alias_check()

old = {s: jl(os.path.join(IN, s + '.jsonl')) for s in ('train', 'val', 'v3eval')}
mech = {}
with gzip.open(os.path.join(D, 'm0', 'mechanical.jsonl.gz'), 'rt') as f:
    for l in f:
        if l.strip(): r = json.loads(l); mech[r['id']] = r
hc_key = {r['id']: r for r in csvr(os.path.join(R10, 'handcheck-key.csv'))}
labA = {r['id']: r['label'] for r in csvr(os.path.join(R10, 'labels-A.csv'))}
labB = {r['id']: r['label'] for r in csvr(os.path.join(R10, 'labels-B.csv'))}
ruling = {r['id']: r['label'] for r in csvr(os.path.join(R10, 'rulings.csv'))}
if set(labA) != set(hc_key) or labA != labB: fail('hand-check labels A/B differ or miss ids')
if not set(ruling) <= set(labA): fail('ruling id outside hand-check set')
hand = {i: ruling.get(i, labA[i]) for i in labA if i in ruling or labA[i] != None}
extra_r9 = csvr(os.path.join(R10, 'extra-r9.csv')); extra_fresh = csvr(os.path.join(R10, 'extra-fresh.csv'))
fresh_ops = {r['id']: r for r in csvr(os.path.join(D, 'exam-2026-11-03-fresh', 'ops.csv'))}
qids = [l.strip() for l in open(os.path.join(R10, 'query-sample.txt')) if l.strip()]
if len(set(qids)) != len(qids): fail('query-sample duplicate ids')

source = {}      # id -> source tags for rows touched
counts = collections.defaultdict(lambda: collections.Counter())
def rebuild(r, split):
    """New lean + text from mechanical. Returns new row (copy)."""
    m = mech[r['id']]; n = dict(r)
    n['mech'], n['rule'] = m['class'], m['rule']
    n['text'] = fmt_text({**m, 'rule': text_rule(m['rule'])})
    if (n['mech'], n['rule']) == (r['mech'], r['rule']) and n['text'] != r['text']: fail('unchanged lean but text differs ' + r['id'])
    return n
def relabel(n, label, how):
    n['label'], n['y'], n['status'] = label, ORDER[label], ONEHOT_STATUS

new = {s: [rebuild(r, s) for r in old[s]] for s in old}
for s in new:
    for r, o in zip(new[s], old[s]):
        if (r['mech'], r['rule']) != (o['mech'], o['rule']): counts['lean_rebuilt'][s] += 1
# hand-check: only the ruled rows change label (the other 129 equal their current label; asserted)
byid = {r['id']: (s, i) for s in new for i, r in enumerate(new[s])}
orig_status = {}
for i, lab in sorted(hand.items()):
    s, k = byid[i]; r = new[s][k]
    if i in ruling:
        if lab == r['label']: fail('ruling equals current label ' + i)
        orig_status[i] = r['status']; counts['relabelled_ruling'][s] += 1; counts['relabelled_ruling_' + f"{r['label']}->{lab}"][s] += 1
        if s == 'v3eval': r['truth'] = lab           # v3eval: truth correction (label there is the mechanical class)
        else: relabel(r, lab, 'ruling')
        source[i] = 'ruling'
    elif lab != r['label']: fail(f'agreed label differs from current without ruling: {i}')
# r9 overrides: TRAIN rows only, one-hot hard labels; ruling wins on overlap
tr_ids = {r['id']: r for r in new['train']}
for e in extra_r9:
    i = e['ag_id']
    if i in tr_ids:
        r = tr_ids[i]; counts['r9_train_rows']['n'] += 1
        if i in ruling: counts['r9_skipped_ruling']['n'] += 1; continue
        orig_status[i] = r['status']
        if e['hand_label'] != r['label']: counts['relabelled_r9']['train'] += 1; counts['relabelled_r9_' + f"{r['label']}->{e['hand_label']}"]['train'] += 1
        relabel(r, e['hand_label'], 'r9'); source[i] = 'r9'
    else: counts['r9_not_overridden']['val' if i in byid and byid[i][0] == 'val' else 'other'] += 1
# fresh rows
fresh = []
for e in extra_fresh:
    o = fresh_ops[e['id']]
    if (o['provider'], o['method'], o['path'], o['operationId']) != (e['provider'], e['method'], e['path'], e['operationId']): fail('fresh ops/extra mismatch ' + e['id'])
    lean = {'class': e['lean_class'], 'rule': text_rule(e['lean_rule']), 'method': e['method'], 'path': e['path'], 'operationId': e['operationId'], 'summary': o['summary'], 'description': o['description']}
    fresh.append({'id': e['id'], 'text': fmt_text(lean), 'label': e['label'], 'y': ORDER[e['label']], 'status': 'fresh', 'jev_p': None, 'jev_pC': None, 'summary': clean(o['summary'], 200),
                  'jev_pA': None, 'jev_pB': None, 'mech': e['lean_class'], 'rule': e['lean_rule'], 'tier': 'none', 'method': e['method'].upper(), 'provider': e['provider'],
                  'vendor': first_token(e['provider']), 'path': e['path'], 'operationId': e['operationId']})
    source[e['id']] = 'fresh'
# QUERY copies of the final train rows
queries = []
for i in qids:
    r = tr_ids.get(i)
    if r is None or r['method'] != 'GET': fail('query id not a GET train row ' + i)
    m = mech[i]; q = dict(r); q['id'] = i + '-q'; q['method'] = 'QUERY'
    q['text'] = fmt_text({**m, 'class': r['mech'], 'rule': text_rule(r['rule']), 'method': 'QUERY'})
    queries.append(q); source[q['id']] = 'query'
final = {'train': new['train'] + fresh + queries, 'val': new['val'], 'v3eval': new['v3eval']}

# ---- assertions
allrows = [(s, r) for s in final for r in final[s]]
bad = sorted({r['vendor'] for _, r in allrows} & EXAM3) + sorted({first_token(r['provider']) for _, r in allrows} & EXAM3)
if bad: fail(f'exam #3 vendor present {bad}')
ids = collections.Counter(r['id'] for _, r in allrows)
dups = [i for i, c in ids.items() if c > 1]
if dups: fail(f'duplicate ids {dups[:5]}')
okey = lambda r: (first_token(r['provider']), 'GET' if r['method'] == 'QUERY' else r['method'], r['path'], r['operationId'] or '')
spl = collections.defaultdict(set)
for s, r in allrows: spl[okey(r)].add(s)
leaks = [k for k, v in spl.items() if len(v) > 1]
if leaks: fail(f'op-key groups span splits: {len(leaks)} e.g. {leaks[:3]}')
if any('credential-set' in r['text'] for _, r in allrows): fail('credential-set in a text')
if any(r['label'] not in ORDER or r['y'] != ORDER[r['label']] for _, r in allrows): fail('label/y inconsistent')
# val / v3eval diff vs old
diff = {}
for s in ('val', 'v3eval'):
    fc = collections.Counter(); rows_changed = 0
    for n, o in zip(final[s], old[s]):
        ch = [k for k in n if n[k] != o[k]]
        if n.keys() != o.keys(): fail('schema change')
        rows_changed += bool(ch); fc.update(ch)
    diff[s] = {'rows_changed': rows_changed, 'rows': len(old[s]), 'fields': dict(fc)}
    allowed = {'mech', 'rule', 'text', 'label', 'y', 'status', 'truth'}
    if set(fc) - allowed: fail('unexpected val/v3eval field change ' + str(fc))
# train old rows unchanged beyond lean/ruling/r9
tdiff = collections.Counter()
for n, o in zip(final['train'][:len(old['train'])], old['train']): tdiff.update(k for k in n if n[k] != o[k])

# ---- write
def jdump(s):
    with open(os.path.join(R10, s + '.jsonl'), 'w') as f:
        for x in final[s]: f.write(json.dumps(x) + '\n')
    pd.DataFrame(final[s]).to_parquet(os.path.join(R10, s + '.parquet'), index=False)
for s in final: jdump(s)
with open(os.path.join(R10, 'assembly-rows.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'split', 'source', 'orig_status'])
    for s in final:
        for r in final[s]:
            if r['id'] in source: w.writerow([r['id'], s, source[r['id']], orig_status.get(r['id'], '')])

# ---- summary
old_label = {x['id']: x['label'] for x in old['train']}
def lab(rows): return dict(sorted(collections.Counter(r['label'] for r in rows).items()))
def softcount(rows):
    T = soft_targets(pd.DataFrame(rows)); oh = int((T.max(1) == 1.0).sum()); return {'one_hot': oh, 'soft': len(rows) - oh}
src_rows = collections.defaultdict(list)
for r in final['train']: src_rows[source.get(r['id'], 'orig')].append(r)
summary = {
  'before': {s: len(old[s]) for s in old}, 'after': {s: len(final[s]) for s in final},
  'label_before': {s: lab(old[s]) for s in old}, 'label_after': {s: lab(final[s]) for s in final},
  'v3eval_truth_before': dict(sorted(collections.Counter(r['truth'] for r in old['v3eval']).items())), 'v3eval_truth_after': dict(sorted(collections.Counter(r['truth'] for r in final['v3eval']).items())),
  'train_rows_added_by_source': {'fresh': len(fresh), 'query': len(queries)},
  'train_label_mix_by_source': {k: lab(v) for k, v in src_rows.items()},
  'lean_rebuilt_rows': dict(counts['lean_rebuilt']),
  'relabelled': {'ruling': dict(counts['relabelled_ruling']), 'ruling_transitions': {k[len('relabelled_ruling_'):]: dict(v) for k, v in counts.items() if k.startswith('relabelled_ruling_')},
                 'r9_train': dict(counts['relabelled_r9']), 'r9_transitions': {k[len('relabelled_r9_'):]: dict(v) for k, v in counts.items() if k.startswith('relabelled_r9_')},
                 'ruled_ids_by_split': {i: byid[i][0] for i in sorted(ruling)}},
  'r9': {'overridden_train_rows': sum(1 for v in source.values() if v == 'r9'), 'train_rows_matched': counts['r9_train_rows']['n'], 'skipped_ruling_overlap': counts['r9_skipped_ruling']['n'], 'val_untouched': dict(counts['r9_not_overridden'])},
  'handcheck': {'rows': len(hand), 'ruled': len(ruling), 'unchanged': len(hand) - len(ruling)},
  'query_copies': {'n': len(queries), 'label': lab(queries), 'source_label_changed_by_relabel': sum(1 for q in queries if q['label'] != old_label[q['id'][:-2]])},
  'soft_vs_onehot': {'train_before': softcount(old['train']), 'train_after': softcount(final['train']), 'train_after_by_source': {k: softcount(v) for k, v in src_rows.items()}, 'val_after': softcount(final['val'])},
  'val_v3eval_diff_vs_old': diff, 'train_orig_rows_field_diff_counts': dict(tdiff),
  'asserts': {'no_exam3_vendor': True, 'no_duplicate_ids': True, 'no_opkey_group_spans_splits': True, 'credential_set_not_in_any_text': True, 'alias_check': True},
  'ids_total': len(ids), 'status_values_after_train': dict(collections.Counter(r['status'] for r in final['train'])),
}
json.dump(summary, open(os.path.join(R10, 'assembly-summary.json'), 'w'), indent=1, sort_keys=True)
names = [s + e for s in ('train', 'val', 'v3eval') for e in ('.jsonl', '.parquet')] + ['assembly-summary.json', 'assembly-rows.csv']
with open(os.path.join(R10, 'assembly-sha256.txt'), 'w') as f:
    for n in names: f.write(f"{hashlib.sha256(open(os.path.join(R10, n), 'rb').read()).hexdigest()}  {n}\n")
print(json.dumps(summary, indent=1, sort_keys=True)); print(open(os.path.join(R10, 'assembly-sha256.txt')).read())
