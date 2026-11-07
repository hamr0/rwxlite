"""Shared helpers for the m0 training pipeline."""
import re, html, json, gzip, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'data', 'train')
LABELS = ['r', 'w', 'x']
ORDER = {'r': 0, 'w': 1, 'x': 2}
# PRD starting cuts
CUTS = {'lower': 0.20, 'raise-wx': 0.60, 'raise-get': 0.20}
TIER = {'jev-lower': 'lower', 'jev-raise-wx': 'raise-wx', 'jev-raise-get': 'raise-get'}

def first_token(provider):
    return re.split(r'[.:]', str(provider or '').lower())[0]

def clean(s, n):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))
    return re.sub(r'\s+', ' ', s).strip()[:n]

# ---- Text format 2: format 1 plus the access hint (mirrors src/text.js accessHint; parity is tested) ----
# The hint marks operations that BRIEF-v4 / rwxmap D137 calls "access" (x, not w): grants or widens access (IAM, ACL,
# resource/bucket/key policies, role bindings, permission assignments, shares, invites, deploy keys), creates an API
# key/token, flips an access-widening toggle, registers a webhook/subscription to an outside URL, creates a login user,
# or adds a member to a team/org/project/group. It reads ONLY the operation's own method, path, operationId and summary
# (never the caller, never the lean). The description is not read: the round 13 data files do not carry it, and the
# hint must be reproducible from the stored fields. DELETE is never hinted (stays mechanical x). Text is normalised
# first (tags stripped, camelCase split, lower-case, non-alphanumerics to one space), so every pattern is plain ASCII.
def _hnorm(t):
    t = re.sub(r'<[^>]+>', ' ', str(t or ''))
    t = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', t)
    t = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', t)
    return re.sub(r'[^a-z0-9]+', ' ', t.lower()).strip()

_HVERB_READ = r"(?:get|list|describe|read|retrieve|fetch|check|validate|test|search|count|export|view|show|find|query|lookup|download|batch get|is|has)"
_HVERB_OUT = r"(?:remove|delete|revoke|detach|unassign|unshare|disable|deny|block|leave|decline|reject|cancel|withdraw|disassociate|deregister|unlink|clear|expire|list|get|describe|read|retrieve|fetch|check|validate|test|search|count|export|view|show|find|query|lookup|download|batch get|is|has|verify|reset|resend|rotate|refresh|login|log in|sign in|logout|log out|sign out|authenticate)"
_HVERB_MUT = r"(?:attach|add|set|put|grant|assign|invite|share|bind|update|modify|change|create|enable|replace|authorize|authorise|allow|upsert|patch|edit|register|link|transfer|promote|accept|apply|configure|reset|import|copy)"
_HHTTP = r"^(?:(?:get|post|put|patch) )?"
_H_READ = re.compile(r"^" + _HVERB_READ + r"\b")
_H_OUT = re.compile(_HHTTP + _HVERB_OUT + r"\b")
_H_MUT = re.compile(r"^" + _HVERB_MUT + r"\b")
_H_NARROWV = re.compile(r"^(remove|delete|revoke|detach|unassign|unshare|disable|deny|block|leave|decline|reject|cancel|withdraw|disassociate|deregister|unlink|clear|expire)\b")
# non-access "policies" and settings that must never count as access
_H_NONACC = re.compile(r"\b(autoscal\w*|scaling|lifecycle|life cycle|retention|routing|routes?|backup|maintenance|cach\w*|refund|returns?|cancell?ation|escalation|sla|sampling|retry|rate limit\w*|throttl\w*|dunning|pricing|billing|tax|shipping|ttl|expir\w*|compliance|alert\w*|notification|schedul\w*)\b")
_H_CORE = re.compile(r"\b(iam|acls?|permissions?|grants?|principals?|access control|shar\w+|invit\w+|collaborators?|deploy keys?|ssh keys?|roles?)\b")
# 1. grants / widens access
_H_GRANT = re.compile(r"\b(iam|acls?|access control|permissions?|role bindings?|role assign\w*|assign\w* roles?|bind\w* roles?|(?<!pod )bindings?|grants?|share|sharing|invit\w+|collaborators?|deploy keys?|ssh keys?|authori[sz]ed keys?|(iam|resource|bucket|key|trust|queue|topic|repository|vault|registry|secret|security|sharing|authorization|access|network) polic(?:y|ies)|principals?|entitlements?|privileges?|access (?:levels?|rights?|lists?|rules?|grants?)|member (?:roles?|permissions?|access)|team (?:permissions?|access))\b")
# 2. API key / token create
_H_CREATE = re.compile(_HHTTP + r"(create|generate|issue|new|add|mint|provision|make|request|regenerate|rotate)\b")
_H_KEYOBJ = re.compile(r"\b(api ?keys?|apikeys?|access ?keys?|secret (?:access )?keys?|(?:personal )?access tokens?|api tokens?|auth(?:entication)? tokens?|bearer tokens?|service tokens?|app(?:lication)? passwords?|passwords? credentials?|client secrets?|service account keys?|service specific credentials?|tokens?|add password|application passwords?)\b")
_H_KEYNOT = re.compile(r"\b(login|log in|sign ?in|authenticate|refresh|oauth|exchange|introspect|verify|validate|revoke|csrf|one time|otp|presigned|pre signed|session token|id token|reset|forgot|recover|encryption keys?|kms|customer managed|two factor|2fa|qr|audit copy|verification|polic(?:y|ies)|invoices?|experiments?|snippets?|quer(?:y|ies)|sub ?accounts?|issuance|key pair|key pairs|keypair|public keys?|license keys?|sort keys?|partition keys?|key vault|keystore|key store|primary keys?|foreign keys?|cache keys?|feature flags?|object keys?|tag keys?|key values?|master keys?|data keys?|grant tokens?)\b")
_H_SETVERB = re.compile(_HHTTP + r"(enable|set|put|update|replace|import)\b")
_H_KEYWORD = re.compile(r"\b(api ?keys?|access ?keys?|tokens?)\b")
_H_PASSWORD = re.compile(r"\b(add|create) password\b")
# 3. access-widening toggle
_H_WID = re.compile(r"\b(public access|publicly (?:accessible|readable|writable|visible)|make public|set public|public (?:links?|urls?|sharing|visibility|read|write|network access|endpoint)|anonymous (?:access|users?|sign ?ins?|login)|guest (?:access|users?|sharing)|external (?:sharing|access|users?|collaborat\w+)|allow (?:external|public|guest|anonymous|all|any)\w*|open (?:registration|signups?|to)|self ?(?:registration|signup|service sign ?up)|signups?|sign ups?|enable (?:public|remote|external|guest|ssh|sftp|ftp|telnet|rdp|console|serial console|link sharing|sharing|sso bypass|access|cross account|cross region access|direct access)|disable (?:mfa|2fa|two ?factor|multi ?factor|authentication|password|ssl|tls|login protection|ip restrictions?|require\w*|verification)|public access blocks?|(?<!message )visibility(?! timeout)|is public|link sharing|share link|remote access)\b")
_H_WIDMUT = re.compile(_HHTTP + r"(enable|disable|allow|set|put|update|modify|change|make|open|turn|toggle|configure|replace|edit|share|publish|expose|switch)\b")
_H_LISTGET = re.compile(_HHTTP + r"(list|get|describe)\b")
_H_WIDNOT = re.compile(r"expir|message visibility|visibility timeout")
# 4. webhook / subscription to an outside URL
_H_HOOK = re.compile(r"\b(web ?hooks?|(?<!lifecycle )(?<!life cycle )(?<!pre receive )hooks?|event subscriptions?|callbacks?(?: urls?)?|notification (?:urls?|endpoints?|channels?|subscriptions?|destinations?|hooks?|targets?)|event (?:destinations?|endpoints?|targets?|hooks?)|api destinations?|push (?:notifications?|channels?)|http endpoints?|endpoint urls?)\b")
_H_HOOKMUT = re.compile(_HHTTP + r"(create|add|register|set|update|configure|enable|subscribe|put|replace|edit|modify|change|insert|new|install|connect|watch|test)\b")
_H_HOOKNOT = re.compile(r"verification|lifecycle|life cycle|signing|alerts?\b")
_H_TEST = re.compile(_HHTTP + r"test\b")
# 5. create a login-capable user
_H_MOD = r"(?:(?:a|an|the|new|another|one|more|auth|app|admin|sub|api|team|org|organization|workspace|tenant|local|portal|system|bulk|multiple|single|batch|additional|full|normal|login) ){0,3}"
_H_USERNOUN = re.compile(r"^" + _H_MOD + r"(users?|login profiles?|administrators?|admins?|service accounts?|employees?|user accounts?|sub ?users?)(?= *$| (?:account|with|and|using|via|by)\b)(?! (to|for|in|on|from|as|into|of|groups?|pools?|profiles?|preferences?|attributes?|settings?|roles?|sessions?|tokens?|keys?|policy|policies|permissions?|mappings?|import|export|id|ids|name|names)\b)( |$)")
_H_USERMUT = re.compile(_HHTTP + r"(create|add|new|register|provision|invite|import|signup|sign up|admin create|bulk create|batch create|insert)\b")
_H_USERPATH = re.compile(r"/(users|admins|administrators)/?(?![\s\S])")
_H_USERNOT = re.compile(r"\b(import|export|search|query|lookup|list|find|verify|check|reset|sessions?|tokens?)\b")
# 6. add a member to a team / org / project / group
_H_MEMBOBJ = re.compile(r"\b(members?|users?|collaborators?|participants?|memberships?|admins?|owners?|people|persons?|principals?)\b")
_H_CONT = re.compile(r"\b(teams?|orgs?|organi[sz]ations?|projects?|groups?|workspaces?|spaces?|channels?|tenants?|companies|company|repos?|repositor\w+|boards?|rooms?|clusters?|domains?)\b")
_H_MEMBMUT = re.compile(_HHTTP + r"(add|create|invite|assign|join|enroll|insert|attach|batch add|bulk add)\b")
_H_MEMBNOT = re.compile(r"\b(role|roles|permissions?|settings?|count|stats|tag|tags|mentions?|notes?|comments?|attachments?)\b")
_H_MEMBGRP = re.compile(r"\b(users?|members?) groups?\b|\bgroups?\b.*\bgroups?\b")
_H_MEMBER = re.compile(r"\bmembers?\b")
_H_MEMBNOT2 = re.compile(r"\b(tags?|attachments?|comments?)\b")
_H_MEMBPATH = re.compile(r"/(teams?|orgs?|organi[sz]ations?|projects?|groups?|workspaces?|spaces?|channels?|tenants?|companies|boards?|rooms?|repos?)/[^/]+/(members?|team_members|users?|collaborators?|memberships?|participants?|admins?|people)(/\{[^/]*\}|/\$ref)?/?(?![\s\S])|/members/\$ref(?![\s\S])|/(members|memberships|collaborators)/?(?![\s\S])")
_H_MEMBREAD = re.compile(r"^(?:get )?(list|get|describe|read|search|query|check|count|export|update|set|replace)\b")
_H_PATHPARAM = re.compile(r"\{[^}]*\}")

def access_hint(r):
    """True when the operation's own method/path/operationId/summary say it grants or widens access (see the block above)."""
    m = str(r['method']).upper()
    if m == 'DELETE': return False
    m = 'GET' if m == 'QUERY' else m
    path = str(r['path'])
    opid = re.sub(r'^(GET|POST|PUT|PATCH|DELETE)_', '', str(r.get('operationId') or ''))
    summ = str(r.get('summary') or '')
    leads = [_hnorm(opid), _hnorm(summ)]                     # whole operationId, summary
    leads2 = [_hnorm(opid.split('.')[-1]), _hnorm(summ)]     # operationId after its last '.', summary
    t = _hnorm(opid + ' ' + summ + ' ' + path)               # what the grant test reads
    t2 = _hnorm(opid + ' ' + summ + ' ' + _H_PATHPARAM.sub('', re.sub(r'#[^\n]*', '', path)))   # path without {params} and #fragments
    any2 = lambda rx: any(rx.match(x) for x in leads2)
    out2 = any2(_H_OUT)
    segs = [s for s in path.split('/') if s and not s.startswith('{') and not s.startswith('#')]
    lastseg = _hnorm(segs[-1]) if segs else ''
    has_mut = any(_H_MUT.match(x) for x in leads)
    has_read = any(_H_READ.match(x) for x in leads) and not has_mut
    # 1. grants / widens access
    if m in ('POST', 'PUT', 'PATCH', 'GET') and _H_GRANT.search(t) and not (_H_NONACC.search(t) and not _H_CORE.search(t)) \
            and not any(_H_NARROWV.match(x) for x in leads):
        if m == 'GET':
            if has_mut: return True
        elif not has_read:
            if has_mut or (m in ('PUT', 'PATCH') and _H_GRANT.search(lastseg)): return True
    # 2. API key / token create
    if any2(_H_CREATE) and not out2 and not _H_KEYNOT.search(t2):
        if not (_H_SETVERB.match(leads2[0]) and not _H_KEYWORD.search(t2)):
            if _H_KEYOBJ.search(t2) or (re.search(r"\bpasswords?\b", t2) and _H_PASSWORD.search(t2)): return True
    # 3. access-widening toggle
    if any2(_H_WIDMUT) and not _H_LISTGET.match(leads2[0]) and not _H_WIDNOT.search(t2) and _H_WID.search(t2): return True
    # 4. webhook / subscription to an outside URL
    if any2(_H_HOOKMUT) and not out2 and not _H_TEST.match(leads2[0]) and not _H_HOOKNOT.search(t2) and _H_HOOK.search(t2): return True
    # 5. creating a login user
    if not out2:
        for x in leads2:
            mm = _H_USERMUT.match(x)
            if mm and _H_USERNOUN.search(x[mm.end():].strip()): return True
        if m == 'POST' and _H_USERPATH.search(path.split('?')[0]) and not _H_OUT.match(leads2[0]) and not _H_USERNOT.search(t2): return True
    # 6. adding a member to a team / org / project / group
    if not out2:
        for x in leads2:
            mm = _H_MEMBMUT.match(x)
            if mm:
                rest = x[mm.end():].strip(); head = ' '.join(rest.split()[:5])
                if _H_MEMBOBJ.search(head) and not _H_MEMBGRP.search(head) and (_H_CONT.search(rest) or _H_CONT.search(_hnorm(path))) and not _H_MEMBNOT.search(head): return True
                if _H_MEMBER.search(head) and not _H_MEMBNOT2.search(head) and _H_CONT.search(_hnorm(path)): return True
        if m in ('POST', 'PUT') and _H_MEMBPATH.search(path.split('?')[0]) and not _H_MEMBREAD.match(leads2[0]): return True
    return False

def fmt_text(r, format=1):
    """One compact string. The leaning (mechanical letter + rule) goes FIRST so truncation never cuts it.
    Format 1: 'lean: <letter> <rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>'
    Format 2: format 1 with the segment 'hint: access' inserted right after the lean segment, only on hinted operations:
    'lean: <letter> <rule> | hint: access | <METHOD> <path> | ...'. Unhinted rows are byte-identical to format 1.
    HTML stripped, whitespace collapsed; summary cut at 200 chars, description at 400 chars, empty fields omitted."""
    if format not in (1, 2): raise ValueError(f'text format must be 1 or 2, got {format!r}')
    parts = [f"lean: {r['class']} {r['rule']}"]
    if format == 2 and access_hint(r): parts.append('hint: access')
    parts.append(f"{str(r['method']).upper()} {r['path']}")
    if r.get('operationId'): parts.append('op: ' + clean(r['operationId'], 120))
    if clean(r.get('summary'), 1): parts.append('sum: ' + clean(r['summary'], 200))
    if clean(r.get('description'), 1): parts.append('desc: ' + clean(r['description'], 400))
    return ' | '.join(parts)

R_CUT = 0.20
import re as _re
def _norm(s): return _re.sub(r'[^A-Za-z0-9]+', ' ', _re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', str(s or ''))).lower()
_NOUN = r'(?:password|passcode|passphrase|pin|pin code|auth key|authkey|api key|apikey|api secret|secret key|client secret)s?'
_CRED = _re.compile(r'\b(?:change|reset|rotate|regenerate|renew|revoke|invalidate|expire)\b(?: \w+){0,3}? ' + _NOUN + r'\b(?! (?:polic|rule|requirement|complexity|setting|config))')
def cred_hit(r):
    """Round-6 narrow credential rule (parity.mjs CRED.narrow): non-GET, fields operationId/summary/path."""
    return str(r['method']).upper() != 'GET' and any(_CRED.search(_norm(r.get(f))) for f in ('operationId', 'summary', 'path'))

def tier_move(tier, letter, p, cuts=CUTS):
    """Jev one-step move at cuts; p is Jev's p (isX or changes)."""
    if tier == 'lower': return 'w' if p < cuts['lower'] and letter == 'x' else letter
    if tier == 'raise-wx': return 'x' if p >= cuts['raise-wx'] and letter == 'w' else letter
    if tier == 'raise-get': return 'w' if p >= cuts['raise-get'] and letter == 'r' else letter
    return letter

def load_mech():
    with gzip.open(os.path.join(ROOT, 'data', 'm0', 'mechanical.jsonl.gz'), 'rt') as f:
        return [json.loads(l) for l in f if l.strip()]

import numpy as np
def load_split(name):
    import pandas as pd
    return pd.read_parquet(os.path.join(OUT, name + '.parquet'))

def mode_a_labels(df, P, variant):
    """Round-6 Mode (a): lower tier moves to r if p(changes)=p(w)+p(x)<0.20 else w; narrow credential rule forces x. Mechanical stays in charge; the model only makes Jev's one-step moves on pile rows.
    variant 'cuts': move when model p crosses the PRD starting cuts (lower: p(x)<0.20; raise-wx: p(x)>=0.60; raise-get: p(w)+p(x)>=0.20).
    variant 'argmax': move when the model's argmax agrees with the move (lower: argmax!=x; raise-wx: argmax==x; raise-get: argmax!=r)."""
    out = []; am = P.argmax(1); meth, opid, summ, pth = df['method'].values, df['operationId'].values, df['summary'].values, df['path'].values
    for i, (m, t) in enumerate(zip(df['mech'].values, df['tier'].values)):
        px, pw = P[i, 2], P[i, 1]
        if variant == 'cuts':
            if t == 'lower' and m == 'x' and px < CUTS['lower']: m = 'r' if (pw + px) < R_CUT else 'w'
            elif t == 'raise-wx' and m == 'w' and px >= CUTS['raise-wx']: m = 'x'
            elif t == 'raise-get' and m == 'r' and (pw + px) >= CUTS['raise-get']: m = 'w'
        else:
            a = LABELS[am[i]]
            if t == 'lower' and m == 'x' and a != 'x': m = a
            elif t == 'raise-wx' and m == 'w' and a == 'x': m = 'x'
            elif t == 'raise-get' and m == 'r' and a != 'r': m = 'w'
        if cred_hit({'method': meth[i], 'operationId': opid[i], 'summary': summ[i], 'path': pth[i]}): m = 'x'
        out.append(m)
    return np.array(out)

def score(pred, truth):
    pred = np.asarray(pred); truth = np.asarray(truth); n = len(truth)
    if n == 0: return {'n': 0}
    po = np.array([ORDER[x] for x in pred]); to = np.array([ORDER[x] for x in truth])
    return {'n': n, 'exact': round(100*(po==to).mean(), 1), 'loose': round(100*(po<to).mean(), 1), 'tight': round(100*(po>to).mean(), 1)}

def v3_report(df, P):
    """Metrics on the v3 truth set for mechanical, mode (a) cuts/argmax and mode (b)."""
    truth = df['truth'].values
    preds = {'mechanical': df['mech'].values, 'a_cuts': mode_a_labels(df, P, 'cuts'), 'a_argmax': mode_a_labels(df, P, 'argmax'),
             'b_argmax': np.array([LABELS[i] for i in P.argmax(1)])}
    rep = {}
    isdel = (df['method'] == 'DELETE').values
    for name, pr in preds.items():
        d = {'overall': score(pr, truth), 'DELETE': score(pr[isdel], truth[isdel]), 'nonDELETE': score(pr[~isdel], truth[~isdel])}
        for m in ['GET','POST','PUT','PATCH','DELETE']:
            s = (df['method'] == m).values
            if s.any(): d['method_' + m] = score(pr[s], truth[s])
        for t in ['lower','raise-wx','raise-get','none']:
            s = (df['tier'] == t).values
            if s.any(): d['tier_' + t] = score(pr[s], truth[s])
        rep[name] = d
    return rep

def print_report(rep):
    for name, d in rep.items():
        print(f'--- {name}')
        for k, v in d.items(): print(f'  {k:16s} n={v["n"]:5d} exact {v.get("exact")}  loose {v.get("loose")}  tight {v.get("tight")}')

def soft_targets(df):
    """Round 8: 3-way (r,w,x) target distribution per row from stored Jev probabilities. (n,3) float32.
    lower/raise-wx tiers (isX asked): p(x)=isX. POST rows with POST-changes p c: p(r)=(1-isX)(1-c), p(w)=(1-isX)c (c missing -> all non-x mass to w).
    PUT/PATCH: p(w)=1-isX. raise-get (GET, changes asked): p(r)=1-ch, p(w)=ch (hard label x -> p(x)=ch, p(r)=1-ch).
    DELETE, credential rows, tier none and rows without Jev p: one-hot of the round-6 label."""
    T = np.zeros((len(df), 3), dtype=np.float32)
    cols = {c: df[c].values for c in ['y', 'status', 'tier', 'method', 'jev_p', 'jev_pC']}
    for i in range(len(df)):
        y, st, t, m, p, c = (cols[k][i] for k in ['y', 'status', 'tier', 'method', 'jev_p', 'jev_pC'])
        if st in ('delete', 'credential') or t == 'none' or p is None or p != p:
            T[i, y] = 1; continue
        p = float(p)
        if t in ('lower', 'raise-wx'):
            T[i, 2] = p; rest = 1 - p
            if m == 'POST' and c is not None and c == c: T[i, 0] = rest * (1 - c); T[i, 1] = rest * c
            else: T[i, 1] = rest
        elif t == 'raise-get':
            T[i, 0] = 1 - p; T[i, 2 if y == 2 else 1] = p
        else: T[i, y] = 1
    return T
