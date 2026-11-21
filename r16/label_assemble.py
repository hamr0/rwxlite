"""Round 16 labelling: join the three opinions (mechanical, R13 mode a, bge r15 teacher) for dev + pick, count the cascade tiers, and write the Sonnet batches,
the worker brief, the Opus re-check input for the old confident disagreements and the R13 suggestions file for rwxmap. Labels NO row.
  data/r16/scratch/venv/bin/python -I r16/label_assemble.py [--no-holdout]
Inputs (data/r16/): labels/work/{ops,mech}.jsonl, labels/work/r13/r13-modea.jsonl, pick/bge-rating-v2.parquet, pick/new-300k-v2.csv.gz, dev-en/dev-ops-v2.csv.gz,
  review/confident.csv.gz, ../r15/labels/final-labels-r15-d141-tight.parquet; rwxmap (read only) BRIEF-v4.md, BRIEF-v4-addendum-D141.md, poc/d141-pass/LABEL-PROMPT.md at 54355e1/709e25a.
Outputs: labels/opinions-r16.{parquet,csv.gz}, labels/opinions-report.json, labels/disagree-sample-400.csv (holdout, pick rows only, excluded from the batches, as r15),
  labels/sonnet/in/chunk-NNN.csv (pick, 500 rows, sorted by op_id) + dev-NNN.csv (dev, never trained on), labels/sonnet/BRIEF.md, labels/opus-recheck-755/{in,current}.csv,
  review/r13-suggestions-for-rwxmap.csv, labels/sonnet/manifest.json.
bge: letter = argmax of the r15 teacher probabilities (temperature does not change the argmax; ties go to the tighter class, as r15/label_assemble.py)."""
import argparse, csv, gzip, hashlib, json, os, random, subprocess, sys
import numpy as np, pandas as pd
csv.field_size_limit(10**9)
ap = argparse.ArgumentParser(); ap.add_argument('--no-holdout', action='store_true'); a = ap.parse_args()
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); D = os.path.join(ROOT, 'data', 'r16'); L = os.path.join(D, 'labels'); W = os.path.join(L, 'work')
RWXMAP = '/home/hamr/PycharmProjects/rwxmap'
CH = 500; RK = {'r': 0, 'w': 1, 'x': 2}; LET = np.array(['r', 'w', 'x'])
rd = lambda f: [json.loads(l) for l in open(f) if l.strip()]
nl = lambda s: s.replace('\r\n', '\n').replace('\r', '\n')            # r15 batch rule: CRLF -> LF, description cut at 1500 characters
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
ops = pd.DataFrame(rd(os.path.join(W, 'ops.jsonl'))); mech = pd.DataFrame(rd(os.path.join(W, 'mech.jsonl'))); r13 = pd.DataFrame(rd(os.path.join(W, 'r13', 'r13-modea.jsonl')))
assert len(ops) == 304475 and list(ops.op_id) == list(mech.op_id) == list(r13.op_id), 'op_id order differs'
assert r13.error.notna().sum() == 0 and r13.p_r.notna().all()
meta = pd.concat([pd.read_csv(os.path.join(D, 'dev-en', 'dev-ops-v2.csv.gz'), usecols=['op_id', 'source', 'vendor_id', 'vendor_kind', 'spec_sha256']).assign(part='dev'),
                  pd.read_csv(os.path.join(D, 'pick', 'new-300k-v2.csv.gz'), usecols=['op_id', 'source', 'vendor_id', 'vendor_kind', 'spec_sha256']).assign(part='pick')]).set_index('op_id')
assert meta.index.is_unique
rt = pd.read_parquet(os.path.join(D, 'pick', 'bge-rating-v2.parquet')).set_index('op_id'); assert rt.index.is_unique and set(rt.index) == set(ops.op_id)
d = ops.copy()
for c in ('source', 'vendor_id', 'vendor_kind', 'spec_sha256', 'part'): d[c] = meta.loc[d.op_id, c].values
assert ((d.part.values == 'dev') == (rt.loc[d.op_id, 'part'].values == 'dev')).all(), 'dev/pick split differs from the rating'
for c in 'rwx': d[f'bge_p_{c}'] = rt.loc[d.op_id, f'pT_{c}'].values; d[f'bge_raw_p_{c}'] = rt.loc[d.op_id, f'p1_{c}'].values
d['bge_letter'] = rt.loc[d.op_id, 'bge_letter'].values; d['bge_conf'] = rt.loc[d.op_id, 'ptop_T'].values
P = d[['bge_raw_p_r', 'bge_raw_p_w', 'bge_raw_p_x']].values; assert (LET[2 - np.argmax(P[:, ::-1], axis=1)] == d.bge_letter.values).all(), 'bge_letter is not the argmax (tie -> tighter)'
d['r13_letter_modea'] = r13.r13_letter_modea.values; d['r13_sent'] = r13.r13_sent.values; d['r13_rule'] = r13.r13_rule.values
for c in 'rwx': d[f'r13_p_{c}'] = r13[f'p_{c}'].values
d['mech_letter'] = mech.mech_letter.values; d['mech_rule'] = mech.mech_rule.values; d['mech_review'] = mech.mech_review.values
assert (d.mech_letter.values == rt.loc[d.op_id, 'mech_letter'].values).all() and (d.mech_rule.values == rt.loc[d.op_id, 'mech_rule'].values).all()
d['mech_lean'] = (mech.mech_letter + ' ' + mech.mech_rule).values
d['agree_all'] = (d.bge_letter == d.r13_letter_modea) & (d.r13_letter_modea == d.mech_letter)
d['disagreement_type'] = np.where(d.agree_all, '', 'bge_' + d.bge_letter + '_r13_' + d.r13_letter_modea + '_mech_' + d.mech_letter)
# holdout: 400 contested pick rows, stratified by type, seed 1 (r15/label_assemble.py sampler). Not sent to Sonnet; the blind review labels them later.
pk = d[d.part == 'pick']; vc = pk.disagreement_type[pk.disagreement_type != ''].value_counts(); types = sorted(vc.index)
d['holdout'] = False
if not a.no_holdout:
    rng = random.Random(1); quota = {}; left = 400; rem = {t: int(vc[t]) for t in types}; active = list(types)
    while active and left > 0:
        share = max(1, left // len(active)); nxt = []
        for t in list(active):
            take = min(share, rem[t] - quota.get(t, 0), left); quota[t] = quota.get(t, 0) + take; left -= take
            if quota[t] < rem[t]: nxt.append(t)
        if left > 0 and len(nxt) == len(active) and share == 1: break
        active = nxt
    sel = []
    for t in types:
        idx = list(pk.index[pk.disagreement_type == t]); rng.shuffle(idx); sel += idx[:quota.get(t, 0)]
    d.loc[sel, 'holdout'] = True
d['batch'] = np.where(d.agree_all, 'agree3', np.where(d.holdout, 'holdout', np.where(d.part == 'dev', 'dev_sonnet', 'sonnet')))
d.to_parquet(os.path.join(L, 'opinions-r16.parquet'), index=False)
d.drop(columns=['bge_conf', 'spec_sha256']).to_csv(os.path.join(L, 'opinions-r16.csv.gz'), index=False, compression='gzip')
# ---- report
def counts(g):
    n = len(g); c = g[~g.agree_all]
    return {'rows': n, 'agree3': int(g.agree_all.sum()), 'contested': int(len(c)), 'contested_pct': round(100 * len(c) / n, 2)}
rep = {'rows': len(d), 'dev': counts(d[d.part == 'dev']), 'pick': counts(d[d.part == 'pick']), 'all': counts(d)}
rep['letters'] = {k: {c: int((d[col] == c).sum()) for c in 'rwx'} for k, col in (('bge', 'bge_letter'), ('r13', 'r13_letter_modea'), ('mech', 'mech_letter'))}
rep['pairwise_agreement'] = {f'{p}_{q}': float((d[x] == d[y]).mean()) for p, q, x, y in (('bge', 'r13', 'bge_letter', 'r13_letter_modea'), ('bge', 'mech', 'bge_letter', 'mech_letter'), ('r13', 'mech', 'r13_letter_modea', 'mech_letter'))}
rep['r13_sent_rows'] = int(d.r13_sent.sum())
C = d[~d.agree_all]
rep['contested_by_type'] = {k: int(v) for k, v in C.disagreement_type.value_counts().items()}
rep['contested_by_type_pick'] = {k: int(v) for k, v in C[C.part == 'pick'].disagreement_type.value_counts().items()}
rep['contested_by_mech_rule_top20'] = {k: int(v) for k, v in C.mech_rule.value_counts().head(20).items()}
rep['contested_by_mech_letter'] = {k: int(v) for k, v in C.mech_letter.value_counts().items()}
rep['contested_by_method'] = {k: int(v) for k, v in C.method.str.upper().value_counts().items()}
rep['contested_by_vendor_kind'] = {k: counts(g) for k, g in d.groupby('vendor_kind')}
rep['batch_counts'] = {k: int(v) for k, v in d.batch.value_counts().items()}
n_sonnet = int((d.batch == 'sonnet').sum()); n_dev = int((d.batch == 'dev_sonnet').sum())
R15_UNSURE = 3595 / 24633
rep['r15_reference'] = {'contested_rate': 25033 / 200000, 'sonnet_rows': 24633, 'sonnet_unsure': 3595, 'sonnet_unsure_rate': R15_UNSURE, 'pilot_unsure_rate_planned': 0.21}
rep['expected_opus_rows'] = {'pick_sonnet_rows': n_sonnet, 'dev_rows': n_dev, 'at_r15_unsure_rate_14.6pct': round((n_sonnet + n_dev) * R15_UNSURE), 'at_pilot_rate_21pct': round((n_sonnet + n_dev) * 0.21)}
# ---- Sonnet batches
cols = ['op_id', 'method', 'path', 'summary', 'description']
def out_rows(g):
    return [[r.op_id, r.method, r.path, nl(r.summary), nl(r.description)[:1500]] for r in g.sort_values('op_id').itertuples(index=False)]
def write_csv(fn, header, rows):
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    with open(fn, 'w', newline='', encoding='utf-8') as f: w = csv.writer(f); w.writerow(header); w.writerows(rows)
SI = os.path.join(L, 'sonnet', 'in'); os.makedirs(SI, exist_ok=True)
for f in os.listdir(SI):
    if f.endswith('.csv'): os.remove(os.path.join(SI, f))     # the batches are regenerated from scratch; nothing else lives here
R = out_rows(d[d.batch == 'sonnet']); nch = 0
for i in range(0, len(R), CH): write_csv(os.path.join(SI, f'chunk-{i // CH:03d}.csv'), cols, R[i:i + CH]); nch += 1
RD = out_rows(d[d.batch == 'dev_sonnet']); ndev = 0
for i in range(0, len(RD), CH): write_csv(os.path.join(SI, f'dev-{i // CH:03d}.csv'), cols, RD[i:i + CH]); ndev += 1
assert sum(len(list(csv.DictReader(open(os.path.join(SI, f), newline='', encoding='utf-8')))) for f in os.listdir(SI)) == n_sonnet + n_dev
if not a.no_holdout:
    s = d[d.holdout][['op_id', 'method', 'path', 'summary', 'description', 'disagreement_type', 'bge_letter', 'bge_p_r', 'bge_p_w', 'bge_p_x', 'r13_letter_modea', 'r13_p_r', 'r13_p_w', 'r13_p_x', 'mech_letter', 'mech_lean', 'source', 'vendor_kind']].copy()
    s['description'] = s.description.str.slice(0, 1500); s.sort_values(['disagreement_type', 'op_id']).to_csv(os.path.join(L, 'disagree-sample-400.csv'), index=False)
rep['sonnet_batches'] = {'chunk_files': nch, 'rows_per_chunk': CH, 'last_chunk_rows': len(R) - CH * (nch - 1), 'pick_rows': len(R), 'dev_files': ndev, 'dev_rows': len(RD), 'holdout_rows': int(d.holdout.sum())}
# ---- brief (ruling first). Verbatim files from rwxmap, read only.
BR = RWXMAP + '/data/relabel-v4-2026-11-05/'; src = {'BRIEF-v4.md': BR + 'BRIEF-v4.md', 'BRIEF-v4-addendum-D141.md': BR + 'BRIEF-v4-addendum-D141.md', 'LABEL-PROMPT.md': RWXMAP + '/poc/d141-pass/LABEL-PROMPT.md', 'c-lowers.txt': RWXMAP + '/poc/d141-pass/c-lowers.txt'}
shas = {k: sha(v) for k, v in src.items()}; head = subprocess.run(['git', '-C', RWXMAP, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
pins = {'BRIEF-v4.md': 'ff164d934b57cb1b86118aba9edb258440437fcc72c7d4f9a1f0af7accdcd918'}
assert shas['BRIEF-v4-addendum-D141.md'] == pins['BRIEF-v4.md'], 'addendum changed since the prereg pin 54355e1'
rm = lambda p: open(p, encoding='utf-8').read().rstrip('\n')
v4 = rm(src['BRIEF-v4.md']); v4 = v4[v4.index('## The brief, verbatim'):]
add = rm(src['BRIEF-v4-addendum-D141.md']); lp = rm(src['LABEL-PROMPT.md'])
lp_rules = lp[lp.index('## D141 first'):lp.index('## Output')].rstrip()
brief = f"""# Round 16 Sonnet labeller brief (rwxlite)

You are one blind labeller. Read this whole file first. You get ONE input file; write ONE output file. The RULINGS below come first and outrank everything after them,
including BRIEF-v4 where they conflict. (Round 15 lesson: Sonnet under-applied D141 until the ruling went first.)

## YOUR TASK

- Input: `data/r16/labels/sonnet/in/<NAME>.csv` (<NAME> is `chunk-NNN` or `dev-NNN`; the main session tells you which). Columns: op_id,method,path,summary,description. Up to 500 rows.
- Output: `data/r16/labels/sonnet/out/<NAME>.csv` (same name as the input file), header `op_id,letter,confidence,reason`, one line per input row, same order, no row skipped, no extras.
  - letter: r, w or x. confidence: EXACTLY sure, likely or unsure (no other word). reason: under 15 words, your own words for THIS row, no commas (use ;), name the clause (e.g. `ii plain create`, `D141a login returns token`).
  - unsure = the row could genuinely be either of two letters after applying every rule below; then also pick the TIGHTER letter. Use sure/likely only when the rules decide it.
- Label every row yourself by reading it. Do NOT write or run any script, regex, classifier or program to label. Write the output file with a plain file write of the lines you decided.
- Blindness: open ONLY your input file and write ONLY your output file. Do not open, list, grep or search anything else in the repository (no code, no other data, no labels, no git history).
  You must not see any classifier output or earlier label. If a row lacks context, label from the row alone and lower the confidence.
- Leave no background process. Use your own scratch directory only if you need one.
- After writing, check: line count = input rows + 1, every letter in r/w/x, every confidence in sure/likely/unsure, op_ids equal the input op_ids in order.

## RULINGS (D136, D137, D141; read first, they outrank the brief)

Standard: BRIEF-v4 (below) with D136, D137 and the D141 addendum. rwxmap's pipeline is the single label truth. Classes stay r < w < x (x is the tightest).

- D136: restarting, stopping, starting or pausing a server, service or instance (it can be started again) = w. Stopping a job where the work done is lost = x.
- D137: granting or widening who can do what (roles, permissions, membership, ACL, policy, sharing, new accounts that can log in) = x. Narrowing access = w. A set/replace that does not say which = x.
- Tighten-only merge rule (shared with rwxmap, agreed 2026-11-19): D141 only moves a letter UP (r to w, r to x, w to x). Never lower a row because of D141. The only D141 lowering is family (c) below, in the narrow form of the agreed (c) rule.
  If you are unsure whether a D141 point applies, take the tighter letter and mark unsure.

{lp_rules.replace('## D141 first: one letter per family', '### D141 one letter per family (rwxmap labeller prompt 709e25a, restated; where it conflicts with the addendum, the addendum wins)')}

### Agreed (c) rule (rwxlite and rwxmap, 2026-11-19): "plain group update = w" is NARROW
Only an update of the group object itself (PUT/PATCH on `.../groups/{{id}}`, details only) is w, and only when the text has no member, role, permission, owner, admin, access, grant, policy or acl words.
Everything else stays x or follows BRIEF-v4: creates (`POST /groups`) are NOT (c); sub-resources under a group (members, calendar, policies, permissions, roles) are NOT (c); a SCIM Groups PATCH that can change members stays x;
any text with member/role/permission words stays x.

## D141 ADDENDUM, VERBATIM (rwxmap 54355e1, `BRIEF-v4-addendum-D141.md`, sha256 {shas['BRIEF-v4-addendum-D141.md']})

{add}

## BRIEF-v4, VERBATIM (rwxmap `BRIEF-v4.md`, sha256 {shas['BRIEF-v4.md']}; the output-format paragraph at its end is replaced by YOUR TASK above)

{v4[:v4.rindex('Output format:')].rstrip()}
"""
bp = os.path.join(L, 'sonnet', 'BRIEF.md'); open(bp, 'w', encoding='utf-8').write(brief)
rep['brief'] = {'path': 'data/r16/labels/sonnet/BRIEF.md', 'sha256': sha(bp), 'rwxmap_head_when_read': head, 'rwxmap_files_sha256': shas,
                'sources': ['rwxmap data/relabel-v4-2026-11-05/BRIEF-v4.md (blob unchanged since c756a28)', 'rwxmap data/relabel-v4-2026-11-05/BRIEF-v4-addendum-D141.md (54355e1)', 'rwxmap poc/d141-pass/LABEL-PROMPT.md (709e25a)', 'rwxmap poc/d141-pass/c-lowers.txt (agreed (c) rule)']}
# ---- Opus re-check of the 755 old confident disagreements: only the r15 source rows are ours; the r13 rows go to rwxmap as suggestions
cf = pd.read_csv(os.path.join(D, 'review', 'confident.csv.gz')); assert len(cf) == 755
c15 = cf[cf.src == 'r15']; c13 = cf[cf.src == 'r13']; assert len(c15) == 396 and len(c13) == 359 and c15.op_id.notna().all()
fl = pd.read_parquet(os.path.join(ROOT, 'data', 'r15', 'labels', 'final-labels-r15-d141-tight.parquet')).set_index('op_id'); assert c15.op_id.isin(fl.index).all()
x = fl.loc[c15.op_id.values].reset_index(); x = x.sort_values('op_id')
OD = os.path.join(L, 'opus-recheck-755'); os.makedirs(OD, exist_ok=True)
write_csv(os.path.join(OD, 'in.csv'), cols, [[r.op_id, r.method, r.path, nl(r.summary if isinstance(r.summary, str) else ''), nl(r.description if isinstance(r.description, str) else '')[:1500]] for r in x.itertuples(index=False)])
x[['op_id', 'label', 'tier', 'weight', 'label_source_letters', 'disagreement_type']].merge(c15[['op_id', 'p_top_T136', 't_letter', 'pair', 'is_access', 'ruling_hint']], on='op_id').to_csv(os.path.join(OD, 'current.csv'), index=False)
sg = c13[['id', 'provider', 'method', 'path', 'operationId', 'text', 'label', 'mech', 'rule', 't1_letter', 't_letter', 'p_top_T1', 'p_top_T136', 'pair', 'is_access', 'ruling_hint', 'status']].rename(columns={'id': 'r13_row_id', 'label': 'r13_label', 't_letter': 'bge_letter_T136', 't1_letter': 'bge_letter_T1'})
sg.to_csv(os.path.join(D, 'review', 'r13-suggestions-for-rwxmap.csv'), index=False)
rep['opus_recheck_755'] = {'r15_rows_in_in_csv': len(x), 'r13_rows_to_rwxmap': len(sg), 'r15_pair': {k: int(v) for k, v in c15.pair.value_counts().items()}, 'r13_pair': {k: int(v) for k, v in c13.pair.value_counts().items()}}
json.dump(rep, open(os.path.join(L, 'opinions-report.json'), 'w'), indent=1)
print(json.dumps({k: rep[k] for k in ('dev', 'pick', 'all', 'letters', 'pairwise_agreement', 'batch_counts', 'expected_opus_rows', 'sonnet_batches', 'opus_recheck_755')}, indent=1)); print(json.dumps(rep['contested_by_type'], indent=1))
