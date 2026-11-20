"""Round 15 final labels: combine the cascade (PRD section 5) into one row per op_id.
  python3 r15/label_final.py
Inputs (data/r15/labels/): pick-200000-1-opinions.parquet, disagree-sample-400.csv (holdout, excluded), sonnet/out/chunk-*.csv,
  opus/out/unsure-*.csv + missed-a/b.csv, audit/sonnet-audit-300.csv.
Outputs: final-labels-r15.parquet/.csv.gz, pass4-ambiguity-list.csv, final-labels-report.json (holdout scores added by label_holdout_score.py)."""
import csv, glob, json, re, collections
import pandas as pd
csv.field_size_limit(10**9)
L = 'data/r15/labels/'
RK = {'r': 0, 'w': 1, 'x': 2}
def readall(pat):
    out = []
    for f in sorted(glob.glob(L + pat)):
        out += list(csv.DictReader(open(f, newline='', encoding='utf-8')))
    return out
DUP = {}
def uniq(rows, name, stricter_dups=False):
    d = {}
    for r in rows:
        assert r['letter'] in RK, (name, r)
        i = r['op_id']
        if i in d:
            assert stricter_dups, (name, 'duplicate', i)
            DUP.setdefault(i, [d[i]['letter']]).append(r['letter'])
            if RK[r['letter']] > RK[d[i]['letter']]: d[i] = r  # two Opus answers: keep the stricter
        else: d[i] = r
    return d
pick = pd.read_parquet(L + 'pick-200000-1-opinions.parquet')
assert pick.op_id.is_unique and len(pick) == 200000
hold = set(pd.read_csv(L + 'disagree-sample-400.csv').op_id)
assert len(hold) == 400 and hold <= set(pick.op_id)
son = uniq(readall('sonnet/out/chunk-*.csv'), 'sonnet')
opus_files = sorted(glob.glob(L + 'opus/out/unsure-*.csv')) + [L + 'opus/out/missed-a.csv', L + 'opus/out/missed-b.csv']
opus = uniq([r for f in opus_files for r in csv.DictReader(open(f, newline='', encoding='utf-8'))], 'opus', True)
dis = pick[~pick.agree_all & ~pick.op_id.isin(hold)]
cov = {'disputed_non_holdout': len(dis), 'sonnet_rows': len(son), 'sonnet_equals_disputed_nonholdout': set(son) == set(dis.op_id),
       'sonnet_in_holdout': len(set(son) & hold)}
assert cov['sonnet_equals_disputed_nonholdout']
unsure = {i for i, r in son.items() if r['confidence'] == 'unsure'}
cov.update(opus_duplicate_ids=len(DUP), opus_duplicate_conflicts=sum(len(set(v)) > 1 for v in DUP.values()), sonnet_confidence=dict(collections.Counter(r['confidence'] for r in son.values())), sonnet_unsure=len(unsure), opus_rows=len(opus),
           opus_equals_sonnet_unsure=set(opus) == unsure, opus_files=len(opus_files))
assert set(opus) == unsure and len(unsure) == 3595
assert all(r['confidence'] in ('sure', 'likely', 'unsure') for r in son.values())
recs = []
for r in pick.itertuples(index=False):
    i = r.op_id
    if i in hold: continue
    s = o = ''
    if r.agree_all:
        lab, tier, w = r.bge_letter, 'agree3', 1.0
        assert lab == r.r13_letter_modea == r.mech_letter
    else:
        s = son[i]['letter']
        if i not in unsure: lab, tier, w = s, 'sonnet', 1.0
        else:
            o = opus[i]['letter']
            if o == s: lab, tier, w = s, 'opus_agree', 1.0
            else: lab, tier, w = max(s, o, key=RK.get), 'strict', 0.3
    recs.append(dict(op_id=i, label=lab, tier=tier, weight=w, bge_p_r=r.bge_p_r, bge_p_w=r.bge_p_w, bge_p_x=r.bge_p_x,
                     label_source_letters=json.dumps({k: v for k, v in dict(bge=r.bge_letter, r13=r.r13_letter_modea, mech=r.mech_letter, sonnet=s, opus=o).items() if v}),
                     method=r.method, path=r.path, operationId=r.operationId, summary=r.summary, description=r.description,
                     source=r.source, vendor_id=r.vendor_id, vendor_kind=r.vendor_kind, disagreement_type=r.disagreement_type))
out = pd.DataFrame(recs)
assert len(out) == 199600 and out.op_id.is_unique and not (set(out.op_id) & hold)
out.to_parquet(L + 'final-labels-r15.parquet', index=False)
out.to_csv(L + 'final-labels-r15.csv.gz', index=False)
# pass 4 ambiguity list (flag only)
PAT = {
 'verify_code': lambda t: re.search(r'verif', t) and re.search(r'code|otp|e-?mail|token', t),
 'login_session': lambda t: re.search(r'log-?in|sign-?in|session', t),
 'oauth_client': lambda t: re.search(r'oauth.*client|client.*oauth|register', t),
 'device_endpoint': lambda t: re.search(r'device token|push token|endpoint config', t),
 'membership_removal_put': None,
}
def membership(r, t): return r.method == 'PUT' and re.search(r'(remove|delete|revoke|leave|kick|unassign|detach).*(member|user|group|team|role|collaborator)|(member|collaborator).*(remove|delete|revoke)', t)
rows = []
for r in out.itertuples(index=False):
    t = f'{r.path} {r.operationId} {r.summary} {r.description}'.lower()
    for k, f in PAT.items():
        hit = membership(r, t) if f is None else f(t)
        if hit: rows.append(dict(op_id=r.op_id, pattern=k, method=r.method, path=r.path, summary=r.summary, label=r.label, tier=r.tier))
p4 = pd.DataFrame(rows); p4.to_csv(L + 'pass4-ambiguity-list.csv', index=False)
# report
aud = uniq(list(csv.DictReader(open(L + 'audit/sonnet-audit-300.csv', newline='', encoding='utf-8'))), 'audit')
ag = pick.set_index('op_id')
assert len(aud) == 300 and all(ag.loc[i, 'agree_all'] for i in aud)
ac = collections.Counter('same' if a['letter'] == ag.loc[i, 'bge_letter'] else ('agreed_looser' if RK[ag.loc[i, 'bge_letter']] < RK[a['letter']] else 'agreed_stricter') for i, a in aud.items())
mix = lambda s: {k: round(v / len(s), 4) for k, v in s.value_counts().items()}
rep = {'rows': len(out), 'holdout_excluded': len(hold), 'coverage': cov,
       'tier_counts': out.tier.value_counts().to_dict(), 'tier_by_letter': {t: g.label.value_counts().to_dict() for t, g in out.groupby('tier')},
       'letter_counts': out.label.value_counts().to_dict(), 'letter_mix_overall': mix(out.label), 'letter_mix_agreed_only': mix(out[out.tier == 'agree3'].label),
       'weight_total': round(out.weight.sum(), 1), 'weight_by_tier': out.groupby('tier').weight.sum().round(1).to_dict(),
       'audit_300': {**ac, 'agreed_looser_pct': round(100 * ac['agreed_looser'] / 300, 2), 'agreed_stricter_pct': round(100 * ac['agreed_stricter'] / 300, 2)},
       'pass4_list': {'rows': len(p4), 'unique_ops': int(p4.op_id.nunique()), 'by_pattern': p4.pattern.value_counts().to_dict(), 'by_tier': p4.tier.value_counts().to_dict()},
       'note': 'model input text columns are not in the opinions file; training rebuilds it from method, path, operationId, summary, description'}
json.dump(rep, open(L + 'final-labels-report.json', 'w'), indent=1)
print(json.dumps(rep, indent=1))
