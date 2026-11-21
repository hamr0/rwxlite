"""Round 16 labelling, pass 2 (Sonnet, a different question; replaces Opus, user ruling 2026-11-21). Builds the pass-2 inputs from the pass-1 Sonnet outputs. Labels NO row.
  data/r16/scratch/venv/bin/python -I r16/label_pass2_prep.py            # all of data/r16/labels/sonnet/out -> data/r16/labels/sonnet2/in/unsure2-NNN.csv (500 rows each)
  data/r16/scratch/venv/bin/python -I r16/label_pass2_prep.py --pilot    # pilot (r15 rows): data/r16/labels/pilot/{in,out}-pilot-000.csv -> sonnet2/in/pilot2-000.csv
Rows = pass-1 confidence 'unsure' only. Columns: op_id,method,path,summary,description,letter_a,letter_b,clauses.
Candidate letters (the pass-1 letter S and the others bge B, R13 R, mech M; the order and the source of each letter are never shown):
  1. the others' letters that differ from S are counted; the letter with most votes is the challenger; a tie goes to the TIGHTER letter (r < w < x, tighten-only).
  2. if all three others equal S (cannot happen on a contested row, kept for safety): the next-tighter letter (r->w, w->x); if S is x: w.
  letter_a < letter_b always (fixed r<w<x order), so the order carries no information. `clauses` is chosen from the pair and the row text only (never from a model).
Final letter after pass 2 (PRD): sure/likely -> the pass-2 letter; unsure -> the tighter of the two letters, weight 0.3."""
import csv, glob, os, re, sys
import pandas as pd
csv.field_size_limit(10**9)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); L = os.path.join(ROOT, 'data', 'r16', 'labels')
RK = {'r': 0, 'w': 1, 'x': 2}; CH = 500
COLS = ['op_id', 'method', 'path', 'summary', 'description']

def candidates(s, b, r, m):
    cnt = {}
    for o in (b, r, m):
        if o != s: cnt[o] = cnt.get(o, 0) + 1
    if cnt: other = max(cnt, key=lambda k: (cnt[k], RK[k]))      # most votes, tie -> tighter
    else: other = 'w' if s == 'x' else {'r': 'w', 'w': 'x'}[s]
    return tuple(sorted((s, other), key=RK.get))

TOPICS = [  # (regex on method+path+summary+description, clause text); fired by the text only
    (r'\b(login|log in|sign[- ]?in|refresh token|access token|session token|id[- ]?token|authenticate)\b', 'D141(a) login/token refresh that returns a token = x'),
    (r'\b(verify|verification|otp|totp|2fa|mfa|two[- ]factor|sms code|introspect|is (the )?(token|email)|already registered)\b', 'D141(b) verify email/OTP/token, pure checks included = x; 2FA off = x, on = w'),
    (r'\b(password|secret|credential|api[- ]?key|private key|certificate|csr|signing key|p8|fcm|apns)\b', 'D141/D130/D137 store or set a credential, create a key/cert/CSR = x'),
    (r'\b(callback|webhook|endpoint|push token|device token|notification url|destination)\b', 'D141(d) change/activate a callback, webhook destination or endpoint, push credential = x; inbound receiver, name/header edit = w/r'),
    (r'/groups?\b|\bgroup\b', 'D141(c) agreed narrow rule: PUT/PATCH on the group object itself with no member/role/permission/owner/admin/access/grant/policy/acl words = w; creates, sub-resources, member words stay x'),
    (r'\b(remove|removes|delete|deletes|unassign|revoke|kick)\b.{0,40}\b(member|members|user|users|account|accounts)\b', 'D141(e) removing members on POST/PUT/PATCH = x; narrowing a role/permission without removing a member = w'),
    (r'\b(role|roles|permission|permissions|acl|policy|policies|grant|share|sharing|invite|membership|member|members|admin|owner)\b', 'D137 granting or widening who can do what = x; narrowing = w; a set/replace that does not say which = x'),
    (r'\b(restart|reboot|stop|start|pause|resume|suspend|cancel|terminate|kill|abort|job|run|execute|trigger)\b', 'D136 restart/stop/start/pause of a server/service/instance = w; stopping a job where the work is lost = x; running a job = x'),
]
BOUND = {('r', 'w'): 'BRIEF-v4 r/w boundary: r = nothing changes (read, echo, validate, search, calculate, preview, dry-run; also on POST); w = something changes',
         ('w', 'x'): 'BRIEF-v4 w/x boundary, the one test: can a later call put everything back, including what anyone could have done in between? yes = w; no (gone, sent, published, charged, run, access granted) = x',
         ('r', 'x'): 'BRIEF-v4 r/x: decide first whether anything changes (r/w boundary), then whether it can be put back (w/x boundary)'}

def clauses(pair, method, path, summary, desc):
    t = f'{method} {path} {summary} {desc}'.lower(); out = [BOUND[pair]]
    for rx, c in TOPICS:
        if re.search(rx, t) and len(out) < 4: out.append(c)
    return ' | '.join(out)

def build(rows, ops):
    """rows: list of (op_id, s, b, r, m); ops: op_id -> (method, path, summary, description)"""
    res = []
    for oid, s, b, r, m in rows:
        pair = candidates(s, b, r, m); me, pa, su, de = ops[oid]
        res.append([oid, me, pa, su, de, pair[0], pair[1], clauses(pair, me, pa, su, de)])
    return res

def write(fn, rows):
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    with open(fn, 'w', newline='', encoding='utf-8') as f: w = csv.writer(f); w.writerow(COLS + ['letter_a', 'letter_b', 'clauses']); w.writerows(rows)

def rd(fn):
    with open(fn, newline='', encoding='utf-8') as f: return list(csv.DictReader(f))

if '--pilot' in sys.argv:
    i = rd(os.path.join(L, 'pilot', 'in-pilot-000.csv')); o = rd(os.path.join(L, 'pilot', 'out-pilot-000.csv'))
    assert [x['op_id'] for x in i] == [x['op_id'] for x in o]
    op = pd.read_parquet(os.path.join(ROOT, 'data', 'r15', 'labels', 'pick-200000-1-opinions.parquet'), columns=['op_id', 'bge_letter', 'r13_letter_modea', 'mech_letter']).set_index('op_id')
    ops = {x['op_id']: (x['method'], x['path'], x['summary'], x['description']) for x in i}
    un = [x for x in o if x['confidence'] == 'unsure']
    rows = [(x['op_id'], x['letter'], op.at[x['op_id'], 'bge_letter'], op.at[x['op_id'], 'r13_letter_modea'], op.at[x['op_id'], 'mech_letter']) for x in un]
    write(os.path.join(L, 'sonnet2', 'in', 'pilot2-000.csv'), build(rows, ops)); print('pilot2 rows', len(rows))
else:
    op = pd.read_parquet(os.path.join(L, 'opinions-r16.parquet'), columns=['op_id', 'bge_letter', 'r13_letter_modea', 'mech_letter']).set_index('op_id')
    ins = sorted(glob.glob(os.path.join(L, 'sonnet', 'in', '*.csv'))); rows = []; ops = {}
    for f in ins:
        name = os.path.basename(f); of = os.path.join(L, 'sonnet', 'out', name)
        if not os.path.exists(of): sys.exit(f'pass-1 output missing: {name}')
        i = rd(f); o = rd(of); assert [x['op_id'] for x in i] == [x['op_id'] for x in o], name
        for x in i: ops[x['op_id']] = (x['method'], x['path'], x['summary'], x['description'])
        rows += [(x['op_id'], x['letter'], op.at[x['op_id'], 'bge_letter'], op.at[x['op_id'], 'r13_letter_modea'], op.at[x['op_id'], 'mech_letter']) for x in o if x['confidence'] == 'unsure']
    rows.sort(); R = build(rows, ops)
    for k in range(0, len(R), CH): write(os.path.join(L, 'sonnet2', 'in', f'unsure2-{k // CH:03d}.csv'), R[k:k + CH])
    print('unsure rows', len(R), 'files', (len(R) + CH - 1) // CH)
