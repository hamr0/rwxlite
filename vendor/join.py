"""Vendor labels step A, part 1: join vendor labels to corpus rows. No network, no spend.
  python3 -I vendor/join.py <service-auth.json> <gh_endpoints.jsonl> <out-dir>
Writes <out-dir>/joined.jsonl (one row per matched corpus row), ops.csv (input for vendor/mech.mjs), join-stats.json.
Vendor data is untrusted: parsed only. Vendor labels are hints, never truth (PRD 'Vendor labels')."""
import sys, os, re, json, csv, gzip, glob, collections
sys.path.append(os.path.expanduser('~/.local/lib/python3.14/site-packages'))  # -I drops user site; numpy lives there
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'train'))
from common import ROOT, load_mech, tier_move, cred_hit, CUTS, R_CUT, TIER, first_token
AWS, GH, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
D = lambda *a: os.path.join(ROOT, 'data', *a)
readj = lambda p: [json.loads(l) for l in open(p) if l.strip()]

# ---------- vendor labels
AWS_HINT = {'List': 'r', 'Read': 'r', 'Tagging': 'w', 'Write': 'notr', 'Permissions management': 'x'}
aws = json.load(open(AWS)); IAM = {s['servicePrefix']: {a['name'].lower(): a['accessLevel'] for a in s['actions']} for s in aws}
IAM_ALL = collections.defaultdict(set)
for p, m in IAM.items():
    for n, l in m.items(): IAM_ALL[n].add((p, l))
ALIAS = {  # corpus service name (spec dir) -> IAM prefix(es); only where the names differ
 'email': ['ses'], 'sesv2': ['ses'], 'pinpoint-email': ['ses'], 'monitoring': ['cloudwatch'], 'apigatewayv2': ['apigateway'], 'models.lex.v2': ['lex'], 'lex-models': ['lex'],
 'runtime.lex': ['lex'], 'runtime.lex.v2': ['lex'], 'elasticloadbalancingv2': ['elasticloadbalancing'], 'eventbridge': ['events'], 'docdb': ['rds'], 'neptune': ['rds'],
 'kinesisanalyticsv2': ['kinesisanalytics'], 'sso-admin': ['sso'], 'amp': ['aps'], 's3control': ['s3'], 's3outposts': ['s3-outposts'], 'alexaforbusiness': ['a4b'], 'location': ['geo'],
 'mturk-requester': ['mechanicalturk'], 'finspace-data': ['finspace-api'], 'application-insights': ['applicationinsights'], 'servicecatalog-appregistry': ['servicecatalog'],
 'opsworkscm': ['opsworks-cm'], 'service-quotas': ['servicequotas'], 'timestream-write': ['timestream'], 'timestream-query': ['timestream'], 'AWSMigrationHub': ['mgh'],
 'iot1click-projects': ['iot1click'], 'iot1click-devices': ['iot1click'], 'iotevents-data': ['iotevents'], 'marketplace-catalog': ['aws-marketplace'], 'meteringmarketplace': ['aws-marketplace'],
 'resourcegroupstaggingapi': ['tag'], 'iot-data': ['iot'], 'iot-jobs-data': ['iot'], 'accessanalyzer': ['access-analyzer'], 'cloudhsmv2': ['cloudhsm'], 'mwaa': ['airflow'],
 'kinesis-video-archived-media': ['kinesisvideo'], 'mediastore-data': ['mediastore'], 'sagemaker-a2i-runtime': ['sagemaker'], 'sagemaker-featurestore-runtime': ['sagemaker'],
 'streams.dynamodb': ['dynamodb'], 'apigatewaymanagementapi': ['execute-api'], 'cloudsearchdomain': ['cloudsearch'], 'migrationhub-config': ['mgh'], 'personalize-events': ['personalize'],
 'connectparticipant': ['connect'], 'sso-oidc': ['sso-oauth']}
def aws_match(r):
    sv = r['api_key'].split(':', 1)[1]; op = re.sub(r'^(GET|POST|PUT|DELETE|PATCH|HEAD)_', '', r['operationId'] or ''); op = re.sub(r'\d{4}_\d{2}_\d{2}$', '', op).rstrip('_').lower()
    for kind, pres in (('direct', [sv]), ('alias', ALIAS.get(sv, []))):
        for p in pres:
            if p in IAM and op in IAM[p]: return kind, p, IAM[p][op]
    c = IAM_ALL.get(op)
    if c:
        lv = {l for _, l in c}
        if len(lv) == 1: return 'global', sorted(c)[0][0], lv.pop()
        return 'ambiguous', None, None
    return None, None, None

NORM = lambda p: re.sub(r'\{[^}]*\}', '{}', p).rstrip('/') or '/'
GH_X_ADMIN = {'Administration'}
GH_X_SECRET = {'Secrets', 'Dependabot secrets', 'Codespaces secrets', 'Agent secrets', 'Organization codespaces secrets', 'Organization dependabot secrets', 'Codespaces user secrets',
               'Git SSH keys', 'GPG keys', 'SSH signing keys', 'Custom organization roles', 'Organization private registries', 'Codespaces lifecycle admin', 'GitHub App installation repository access'}
gh = collections.defaultdict(list)
for e in readj(GH): gh[(e['method'], NORM(e['path']))].append(e)
def gh_hint(es, method):
    accs = {e['access'] for e in es}; areas = sorted({f"{e['scope']}:{e['area']}" for e in es})
    if method == 'GET' and accs != {'read'}: return 'conflict', '+'.join(sorted(accs)), areas, None
    if accs == {'read'}: return 'r', 'read', areas, None
    wa = {e['area'] for e in es if e['access'] != 'read'}
    if wa & GH_X_ADMIN: return 'x', '+'.join(sorted(accs)), areas, 'admin'
    if wa & GH_X_SECRET: return 'x', '+'.join(sorted(accs)), areas, 'secret-key-role'
    return 'notr', '+'.join(sorted(accs)), areas, None

# ---------- corpus + teacher
mech = load_mech()
p1 = {x['id']: x['p'] for x in readj(D('m0', 'jev-pass1.jsonl')) if not x.get('error')}; p2 = {x['id']: x['p'] for x in readj(D('m0', 'jev-pass2.jsonl')) if not x.get('error')}
c1 = {x['id']: x['p'] for x in readj(D('m0', 'jev-post-changes.jsonl')) if not x.get('error')}; c2 = {x['id']: x['p'] for x in readj(D('m0', 'jev-post-changes-2.jsonl')) if not x.get('error')}
def jev(r):
    r['pA'] = p1.get(r['id']); r['pB'] = p2.get(r['id']); r['pC'] = None if r['id'] not in c1 else ((c1[r['id']] + c2[r['id']]) / 2 if r['id'] in c2 else c1[r['id']])
    r['p'] = None if r['pA'] is None else (r['pA'] if r['pB'] is None else (r['pA'] + r['pB']) / 2)
    r['tier'] = TIER.get(r['jev_tier'], 'none'); r['method'] = str(r['method']).upper()
def teacher(r):
    """The round-6 label recipe (train/build_dataset.py label_row), applied to any row; returns (letter or None, status)."""
    if r['method'] == 'DELETE': return 'x', 'delete'
    if r['p'] is None: return None, 'no_jev'
    t = r['tier']
    if t != 'none' and r['pB'] is not None and (r['pA'] >= CUTS[t]) != (r['pB'] >= CUTS[t]): return None, 'wobble_straddle'
    l = tier_move(t, r['class'], r['p'])
    if t == 'lower' and l == 'w' and r['pC'] is not None and r['pC'] < R_CUT: l = 'r'
    if cred_hit(r): return 'x', 'credential'
    return l, ('moved' if l != r['class'] else 'kept')
split = {}
for nm in ('train', 'val', 'v3eval'):
    for x in readj(D('train', nm + '.jsonl')): split[x['id']] = (nm, x['truth'] if nm == 'v3eval' else x['label'], x['status'])  # v3eval: truth = BRIEF-v3-era hand label (label there is mech)
# protected = rows that overlap any exam / gate / holdout / r9-hand set (by provider|method|path; labels never read)
PROT = {}
def addp(src, prov, m, p):
    if prov and m and p: PROT.setdefault((prov, str(m).upper(), p), set()).add(src)
for f in glob.glob(D('**', 'blind.csv'), recursive=True) + glob.glob(D('**', 'ops.csv'), recursive=True):
    if '/vendor/' in f: continue
    src = os.path.relpath(f, D()).split('/')[0] if '/replay/' not in f and '/inputs/' not in f else os.path.relpath(f, D())
    for r in csv.DictReader(open(f, newline='')): addp(os.path.relpath(f, D()), r.get('provider'), r.get('method'), r.get('path'))
for f in glob.glob(D('**', 'inputs.jsonl'), recursive=True):
    if '/vendor/' in f: continue
    for r in readj(f): addp(os.path.relpath(f, D()), r.get('provider'), r.get('method'), r.get('path'))

rows = []; st = collections.Counter(); rowsout = []
for r in mech:
    pv = r['provider']
    if pv == 'amazonaws.com':
        kind, pre, lvl = aws_match(r); src = 'aws'
        if kind is None or kind == 'ambiguous': st[('aws', 'unmatched' if kind is None else 'ambiguous')] += 1; continue
        v = {'source': 'aws', 'match': kind, 'iam_prefix': pre, 'vendor_level': lvl, 'hint': AWS_HINT[lvl], 'hint_sub': None, 'vendor_area': pre, 'dedupe_key': f"aws|{pre}|{(r['operationId'] or '').lower()}"}
    elif pv == 'github.com':
        es = gh.get((r['method'].upper(), NORM(r['path'])))
        if not es: st[('github', 'unmatched')] += 1; continue
        h, lvl, areas, sub = gh_hint(es, r['method'].upper())
        v = {'source': 'github', 'match': 'path', 'iam_prefix': None, 'vendor_level': lvl, 'hint': h, 'hint_sub': sub, 'vendor_area': ';'.join(areas), 'dedupe_key': f"gh|{r['method'].upper()}|{NORM(r['path'])}"}
    else: continue
    jev(r); lab, status = teacher(r); sp = split.get(r['id'], (None, None, None))
    prot = sorted(PROT.get((r['provider'], r['method'].upper(), r['path']), []))
    flags = [k for k in ('exam', 'exam_opkey_overlap') if r.get(k)] + ([f"hand:{r['hand_set']}"] if r.get('hand_set') else []) + ([f"calib:{r['calib_set']}"] if r.get('calib_set') else [])
    o = {'id': r['id'], 'provider': r['provider'], 'api_key': r['api_key'], 'spec_version': r['spec_version'], 'method': r['method'], 'path': r['path'], 'operationId': r['operationId'], 'summary': r.get('summary') or '', 'description': r.get('description') or '',
         'mech_class': r['class'], 'mech_rule': r['rule'], 'jev_tier': r['tier'], 'pA': r['pA'], 'pB': r['pB'], 'pC': r['pC'], 'jev_p': r['p'], 'teacher': lab, 'teacher_status': status,
         'split': sp[0], 'train_label': sp[1] if sp[0] in ('train', 'val') else None, 'v3_label': sp[1] if sp[0] == 'v3eval' else None,
         'protected': prot, 'corpus_flags': flags, **v}
    rowsout.append(o); st[(v['source'], 'matched_' + v['match'])] += 1
with open(os.path.join(OUT, 'joined.jsonl'), 'w') as f:
    for o in rowsout: f.write(json.dumps(o) + '\n')
with open(os.path.join(OUT, 'ops.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'])
    for o in rowsout: w.writerow([o['id'], o['provider'], o['method'], o['path'], o['operationId'], o['summary'], o['description']])
tot = collections.Counter(r['provider'] for r in mech)
stats = {'matched': {f'{a}|{b}': n for (a, b), n in st.items()}, 'corpus_rows': {'aws': tot['amazonaws.com'], 'github': tot['github.com']}, 'joined_rows': len(rowsout),
         'unique_dedupe_keys': dict(collections.Counter(k.split('|')[0] for k in {o['dedupe_key'] for o in rowsout})),
         'gh_vendor_unique_endpoints': len(gh), 'gh_vendor_endpoints_joined': len({o['dedupe_key'] for o in rowsout if o['source'] == 'github'})}
json.dump(stats, open(os.path.join(OUT, 'join-stats.json'), 'w'), indent=1); print(json.dumps(stats, indent=1))
