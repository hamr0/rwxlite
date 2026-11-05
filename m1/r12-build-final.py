#!/usr/bin/env python3
"""Round 12 final build (no training, no network). Writes NEW files only into data/round12/final/ (gitignored).
Run from repo root: RWXMAP_DIR=/home/hamr/PycharmProjects/rwxmap .venv/bin/python m1/r12-build-final.py
Inputs (read-only): data/round12/{train,val,v3eval,holdout}.jsonl, variants-final.jsonl, variants-d136.jsonl (optional),
  rwxmap exam3/exam4 truth-d136.csv (sha256 pinned).
 1a. exam #3/#4 rows in train+holdout: label := truth-d136 (restart/stop-server are w, D136).
 1b. train/val (not v3eval, not exam rows): server/service/container/app/db/VM restart/stop/start/pause/resume x -> w
     (restart is w with no exception; clause f only keeps job/run stops with lost work at x). Conservative; unclear listed.
 1c. user override ag-033484 (codat.io POST push/billCreditNotes) w -> x.
 2.  variants -> round-11 row format (lean from rwxmap classifyRow via m1/round10-classify.mjs, text via train/common.fmt_text).
 3.  S1 = train + variants x2 (low x1); S2 = train + variants x5 (low x2). 4. SHA256SUMS + summary.md.
"""
import collections, csv, hashlib, json, os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'train')); sys.path.insert(0, HERE)
from common import fmt_text, clean, first_token, ORDER   # noqa: E402
from round10_aliases import text_rule                    # noqa: E402
SRC = os.path.join(REPO, 'data', 'round12'); OUT = os.environ.get('R12_FINAL_OUT') or os.path.join(SRC, 'final')
RWXMAP = os.environ.get('RWXMAP_DIR', '/home/hamr/PycharmProjects/rwxmap')
D136 = {'ex4': (os.path.join(RWXMAP, 'data/exam4-2026-11-04/truth-d136.csv'), '6c35a32f93a307f254c90d1f2b27913b3bffd0f528669c693bd81ab578108c39'),
        'ex3': (os.path.join(RWXMAP, 'data/exam3-2026-11-04/truth-d136.csv'), '1a257e4329089855d32ca261c8b28077b5a15345b00ffc76b6bca62ab9fc4c10')}
def fail(m): print('FAIL: ' + m, file=sys.stderr); sys.exit(1)
jl = lambda p: [json.loads(l) for l in open(p) if l.strip()]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
if os.path.exists(OUT) and os.listdir(OUT): fail(OUT + ' exists and is not empty (never overwrite)')
os.makedirs(os.path.join(OUT, 'S1')); os.makedirs(os.path.join(OUT, 'S2'))
base = {s: jl(os.path.join(SRC, s + '.jsonl')) for s in ('train', 'val', 'v3eval', 'holdout')}
base_sha = {s: sha(os.path.join(SRC, s + '.jsonl')) for s in base}
rows = {s: [dict(r) for r in base[s]] for s in base}
relabels = []   # id, split, provider, method, path, old, new, rule
def relabel(split, r, new, rule):
    relabels.append({'id': r['id'], 'split': split, 'provider': r['provider'], 'method': r['method'], 'path': r['path'], 'old': r['label'], 'new': new, 'rule': rule})
    r.update(label=new, y=ORDER[new], status='fresh', jev_p=None, jev_pC=None, jev_pA=None, jev_pB=None, tier='none')

# ---- 1a
d136 = {}
for k, (p, h) in D136.items():
    if sha(p) != h: fail('sha mismatch ' + p)
    d136.update({r['id']: r['label'] for r in csv.DictReader(open(p, newline=''))})
for s in ('train', 'holdout'):
    for r in rows[s]:
        if r['id'].startswith(('ex3-', 'ex4-')):
            if r['id'] not in d136: fail('no d136 truth for ' + r['id'])
            if d136[r['id']] != r['label']: relabel(s, r, d136[r['id']], 'D136-exam-truth')
for s in ('val', 'v3eval'):
    if any(r['id'].startswith(('ex3-', 'ex4-')) for r in rows[s]): fail('exam row in ' + s)

# ---- 1c
ov = [r for r in rows['train'] if r['id'] == 'ag-033484']
if len(ov) != 1 or (ov[0]['provider'], ov[0]['method'], ov[0]['path'], ov[0]['label']) != ('codat.io', 'POST', '/companies/{companyId}/connections/{connectionId}/push/billCreditNotes', 'w'): fail('ag-033484 not as expected')
relabel('train', ov[0], 'x', 'user-override-2026-11-05')
put = [r for r in rows['train'] if r['id'] == 'ag-033485'][0]
if put['label'] != 'w' or put['method'] != 'PUT': fail('ag-033485 not w PUT')

# ---- 1b
def norm(s): return re.sub(r'[^a-z0-9]+', ' ', re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', str(s or '')).lower()).strip()
ACT = r'(?:restart|reboot|stop|start|pause|resume|power (?:on|off)|shut ?down)(?:s|ed|ing)?'
SENT = re.compile(r'^(?:use this \w+ to |send an? |submit an? )?(?:the |this |an? )?(?:operation |api |endpoint |call |request )?(?:to |that )?(?:(?:forcefully |immediately |gracefully |manually )?)(?:' + ACT + r')\b')
SERVER = re.compile(r'\b(server|servers|service|services|container|containers|app|apps|application|applications|web app|database|databases|db|instance|instances|vm|vms|virtual machine|virtual machines|machine|machines|node|nodes|cluster|clusters|broker|brokers|host|hosts|daemon|replica|replicas|environment|signalr)\b')
JOBISH = re.compile(r'\b(job|jobs|run|runs|task|tasks|pipeline|build|builds|transcription|recording|broadcast|broadcasts|flow|flows|trigger|triggers|canary|session|sessions|migration|import|importation|export|chaos|simulation|test|query|process|workflow|execution|sync|backup|batch|scan|campaign|stream|streaming|capturing|capture|rollout|resize|maintenance|incident|discoverer|multiplex|channel|channels|schedule|human loop|loop|model|exec|charge|contract|conversation|auction|crawl|analysis|index|indexer|scheduler|worker|logging|log|upgrade|refresh|review|activity|orientation|estimate|sharing|share|replicating|pcap|diagnostics|paid|entitlement|external|stack|rolling|actions|package|packages|upgrad\w*)\b')
def first_sentences(r):
    t = clean(r.get('summary'), 200)
    d = r['text'].split('desc: ', 1)[1] if 'desc: ' in r['text'] else ''
    return [x for x in (t, re.split(r'(?<=[.!?])\s', d.strip())[0] if d else '') if x]
MANUAL_W = {'ag-004777': 'restart of db instance', 'ag-005987': 'restart of instances', 'ag-006468': 'restart of app server', 'ag-011788': 'restart of db cluster',
            'ag-028615': 'restart of worker machine', 'ag-029214': 'restart of worker machine', 'ag-009190': 'start of application', 'ag-012843': 'start of notebook instance',
            'ag-014139': 'start of server', 'ag-063911': 'stop of application (shutdown)', 'ag-119781': 'start of vm'}   # reviewed by hand: sentence/opId clearly names a server-ish target
MANUAL = {k: ('w', v, '') for k, v in MANUAL_W.items()}
MANUAL.update({'ag-001691': ('unclear', 'amplify manual deployment start: deployment, not server', ''), 'ag-001959': ('unclear', 'deployment', ''), 'ag-027489': ('unclear', 'restart of a code package, not clearly a server/service', '')})
def decide(r):
    if r['id'] in MANUAL: return MANUAL[r['id']]
    sents = [norm(x) for x in first_sentences(r)]
    tail = norm(re.split(r'[/:#$=.]', r['path'].rstrip('/'))[-1] if r['path'] else '') + ' | ' + norm(re.split(r'[.]', r.get('operationId') or '')[-1])
    verb = next((s for s in sents if SENT.match(s)), None)
    tailhit = re.search(r'(?:^|\| )(?:force )?(restart|reboot|stop|start|pause|resume|poweroff|power off|power on|shutdown)\b', tail)
    if not verb and not tailhit: return None
    if not verb: return ('unclear', 'action only in path/operationId, sentence does not lead with it', '')
    obj = SENT.sub('', verb).strip()
    isrestart = bool(re.search(r'(restart|reboot)', SENT.match(verb).group(0)))
    if not tailhit: return ('unclear', 'sentence leads with the verb but path/operationId does not name the action', obj[:60])
    head = obj
    j, sv = JOBISH.search(head), SERVER.search(head)
    if j:
        return ('keep-x', 'job/run/task-like target, not a server/service operation', obj[:60])
    if sv: return ('w', ('restart' if isrestart else 'stop/start/pause/resume') + ' of ' + sv.group(1), obj[:60])
    return ('unclear', 'target not recognisably server/service/container/app/db/VM', obj[:60])
cand = []
for s in ('train', 'val'):
    for r in rows[s]:
        if r['label'] != 'x' or r['id'].startswith(('ex3-', 'ex4-')) or r['id'] == 'ag-033484': continue
        d = decide(r)
        if d: cand.append((s, r, d))
for s, r, (dec, why, obj) in cand:
    if dec == 'w': relabel(s, r, 'w', 'D136-restart' if why.startswith('restart') else 'D136-stop-start-pause-resume')
with open(os.path.join(OUT, 'relabel-1b-candidates.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'split', 'provider', 'method', 'path', 'decision', 'reason', 'object', 'summary'])
    for s, r, (dec, why, obj) in cand: w.writerow([r['id'], s, r['provider'], r['method'], r['path'], dec, why, obj, r['summary']])
with open(os.path.join(OUT, 'relabels.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, list(relabels[0])); w.writeheader(); w.writerows(relabels)
chg = {x['id'] for x in relabels}
for s in ('train', 'val', 'holdout'):
    for a, b in zip(base[s], rows[s]):
        if a != b:
            if a['id'] not in chg: fail('unlogged change ' + a['id'])
            if {k for k in a if a[k] != b[k]} - {'label', 'y', 'status', 'jev_p', 'jev_pC', 'jev_pA', 'jev_pB', 'tier'}: fail('unexpected field change ' + a['id'])
if rows['v3eval'] != base['v3eval']: fail('v3eval changed')
v3_cands = sum(1 for r in base['v3eval'] if r['label'] == 'x' and (decide(r) or ('',))[0] == 'w')

# ---- 2 variants
vfiles = [('variants-final.jsonl', 'variants-final')]
d136v = os.path.join(SRC, 'variants-d136.jsonl')
if os.path.exists(d136v): vfiles.append(('variants-d136.jsonl', 'variants-d136'))
vrows = [(tag, r) for fn, tag in vfiles for r in jl(os.path.join(SRC, fn))]
inp = [{k: v.get(k) for k in ('method', 'path', 'operationId', 'summary', 'description')} for _, v in vrows]
p = subprocess.run(['node', os.path.join(HERE, 'round10-classify.mjs')], input=json.dumps(inp), capture_output=True, text=True, env={**os.environ, 'RWXMAP_DIR': RWXMAP})
if p.returncode: fail('classify: ' + p.stderr[-400:])
cls = json.loads(p.stdout)
gen = []; seq = collections.Counter()
for (tag, v), c in zip(vrows, cls):
    seq[tag] += 1
    lean = {'class': c['class'], 'rule': text_rule(c['rule']), 'method': v['method'], 'path': v['path'], 'operationId': v.get('operationId'), 'summary': v.get('summary'), 'description': v.get('description')}
    if v['label'] not in ORDER: fail('bad variant label')
    gen.append({'id': f"gen-{tag.split('-')[1]}-{seq[tag]:04d}", 'text': fmt_text(lean), 'label': v['label'], 'y': ORDER[v['label']], 'status': 'generated', 'jev_p': None, 'jev_pC': None,
                'summary': clean(v.get('summary'), 200), 'jev_pA': None, 'jev_pB': None, 'mech': c['class'], 'rule': c['rule'], 'tier': 'none', 'method': v['method'].upper(),
                'provider': v['provider'], 'vendor': first_token(v['provider']), 'path': v['path'], 'operationId': v.get('operationId') or '',
                'source': tag + ':' + str(v.get('source')), 'seed_id': v.get('seed_id'), 'kind': v.get('kind'), 'weight_hint': v.get('weight_hint')})
heldvend = {r['vendor'] for s in ('val', 'v3eval', 'holdout') for r in rows[s]} | {'goharbor', 'render'}
bad = [g for g in gen if g['vendor'] in heldvend]
if bad: fail('generated rows with held-out vendor: %s' % collections.Counter(g['vendor'] for g in bad))
htxt = {r['text'] for s in ('val', 'v3eval', 'holdout') for r in rows[s]}
dup = [g for g in gen if g['text'] in htxt]
if dup: fail('%d generated rows duplicate val/v3eval/holdout text, e.g. %s' % (len(dup), dup[0]['text'][:120]))
allids = [r['id'] for s in rows for r in rows[s]] + [g['id'] for g in gen]
if len(set(allids)) != len(allids): fail('duplicate ids overall')

# ---- 3 write
def build(mult, low):
    out = list(rows['train'])
    for g in gen:
        out.append(g)
        for i in range(1, low if g['weight_hint'] == 'low' else mult): out.append(dict(g, id=f"{g['id']}_rep{i}"))
    return out
def write(path, rs):
    with open(path, 'w') as f:
        for x in rs: f.write(json.dumps(x) + '\n')
S = {'S1': build(2, 1), 'S2': build(5, 2)}
for k, rs in S.items(): write(os.path.join(OUT, k, 'train.jsonl'), rs)
write(os.path.join(OUT, 'val.jsonl'), rows['val']); write(os.path.join(OUT, 'holdout.jsonl'), rows['holdout'])
shutil.copyfile(os.path.join(SRC, 'v3eval.jsonl'), os.path.join(OUT, 'v3eval.jsonl'))
write(os.path.join(OUT, 'generated-unique.jsonl'), gen)
if sha(os.path.join(OUT, 'v3eval.jsonl')) != base_sha['v3eval']: fail('v3eval copy differs')
for s in base:
    if sha(os.path.join(SRC, s + '.jsonl')) != base_sha[s]: fail('source file changed ' + s)

# ---- 4 summary
lab = lambda rs: dict(sorted(collections.Counter(r['label'] for r in rs).items()))
xs = lambda rs: '%.2f%%' % (100 * sum(r['label'] == 'x' for r in rs) / len(rs))
srcof = lambda r: r['source'].split(':')[0] if r['status'] == 'generated' else 'exam4' if r['id'].startswith('ex4-') else 'exam3' if r['id'].startswith('ex3-') else 'r11'
rc = collections.Counter((x['split'], x['rule'], x['old'] + '->' + x['new']) for x in relabels)
L = ['# round12 final build', '', 'Source jsonl sha256 (unchanged): ' + ', '.join(f'{s} {h[:12]}' for s, h in base_sha.items()),
     f"variants-d136.jsonl included: {'YES' if os.path.exists(d136v) else 'NO (absent at build time)'}; generated unique rows: {len(gen)} " + str(dict(collections.Counter(g['source'].split(':')[0] for g in gen))),
     'Lean for generated rows: rwxmap classifyRow at ' + RWXMAP + ', text via fmt_text.', '', '## relabels (relabels.csv)', '| split | rule | change | n |', '|---|---|---|---|']
L += [f'| {s} | {r} | {c} | {n} |' for (s, r, c), n in sorted(rc.items())]
L += ['', f'total relabels: {len(relabels)}; v3eval untouched ({v3_cands} v3eval rows would match rule 1b, left as is)', '', '## counts per file', '| file | rows | r | w | x | x share | generated share |', '|---|---|---|---|---|---|---|']
files = {'S1/train': S['S1'], 'S2/train': S['S2'], 'val': rows['val'], 'v3eval': rows['v3eval'], 'holdout': rows['holdout']}
for k, rs in files.items():
    l = lab(rs); g = sum(r['status'] == 'generated' for r in rs)
    L.append(f"| {k} | {len(rs)} | {l.get('r',0)} | {l.get('w',0)} | {l.get('x',0)} | {xs(rs)} | {100*g/len(rs):.2f}% ({g}) |")
L += ['', f"x share of base train before relabels: {xs(base['train'])}, after: {xs(rows['train'])}; val before {xs(base['val'])}, after {xs(rows['val'])}; holdout before {xs(base['holdout'])}, after {xs(rows['holdout'])}", '',
      '## source x label', '| file | source | n | r | w | x |', '|---|---|---|---|---|---|']
for k, rs in files.items():
    whole = k in ('val', 'v3eval', 'holdout')
    for sname in sorted({'all' if whole else srcof(r) for r in rs}):
        sub = rs if whole else [r for r in rs if srcof(r) == sname]; l = lab(sub)
        L.append(f"| {k} | {sname} | {len(sub)} | {l.get('r',0)} | {l.get('w',0)} | {l.get('x',0)} |")
L += ['', '## 1b candidate decisions', str(dict(collections.Counter(f'{s}/{d[0]}' for s, r, d in cand))), 'Full list with reasons: relabel-1b-candidates.csv']
open(os.path.join(OUT, 'summary.md'), 'w').write('\n'.join(L) + '\n')
names = ['S1/train.jsonl', 'S2/train.jsonl', 'val.jsonl', 'v3eval.jsonl', 'holdout.jsonl', 'generated-unique.jsonl', 'relabels.csv', 'relabel-1b-candidates.csv', 'summary.md']
open(os.path.join(OUT, 'SHA256SUMS'), 'w').write(''.join(f'{sha(os.path.join(OUT, n))}  {n}\n' for n in names))
print('\n'.join(L))
