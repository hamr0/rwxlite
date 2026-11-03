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

def fmt_text(r):
    """One compact string. The leaning (mechanical letter + rule) goes FIRST so truncation never cuts it.
    Format: 'lean: <letter> <rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>'
    HTML stripped, whitespace collapsed; summary cut at 200 chars, description at 400 chars, empty fields omitted."""
    parts = [f"lean: {r['class']} {r['rule']}", f"{str(r['method']).upper()} {r['path']}"]
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
