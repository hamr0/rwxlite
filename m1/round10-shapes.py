#!/usr/bin/env python3 -I
"""Round 10: count training rows per leak shape and write candidate lists.

Shapes (user decision 2026-11-04, item 2):
  cred-replace : PUT/PATCH whose LAST non-parameter path segment is a credential
                 (api-key, client-credentials, token, secret, integration-token). Exam truth: x (clause b).
  logout       : logout / signout / sign-out / end-session in the path or operationId, any method.
                 Exam truth: x.
Run from the repo root:  python3 -I m1/round10-shapes.py
Reads data/train/{train,val,v3eval}.jsonl; writes data/round10/shapes-<split>.csv (gitignored).
These are CANDIDATES: each matched row still gets a hand/labeller check before any relabel.
"""
import csv, json, os, re, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

def norm(seg):  # api_key, apiKey, api-keys -> api-key
    seg = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', seg).lower().replace('_', '-')
    return seg
CRED = re.compile(r'^(api-keys?|client-credentials?|tokens?|secrets?|integration-tokens?)$')
LOGOUT = re.compile(r'(log-?out|sign-?out|end-?session|log-?off)', re.I)

def last_seg(path):
    segs = [s for s in path.split('?')[0].split('/') if s and not s.startswith('{')]
    return segs[-1] if segs else ''

def shapes(r):
    out = []
    if r['method'] in ('PUT', 'PATCH') and CRED.match(norm(last_seg(r['path']))):
        out.append('cred-replace')
    # path or operationId; split camelCase first so 'userLogout' matches, but not 'Blogout'-style noise
    if LOGOUT.search(r['path']) or LOGOUT.search(re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', r.get('operationId') or '')):
        out.append('logout')
    return out

os.makedirs('data/round10', exist_ok=True)
for split in ('train', 'val', 'v3eval'):
    rows = [json.loads(l) for l in open(f'data/train/{split}.jsonl')]
    cand = []
    for r in rows:
        for s in shapes(r):
            cand.append((s, r))
    print(f'== {split}: {len(rows)} rows, {len(cand)} matches')
    for s in ('cred-replace', 'logout'):
        sub = [r for k, r in cand if k == s]
        print(f'  {s}: {len(sub)}  by label {dict(sorted(Counter(r["label"] for r in sub).items()))}'
              f'  by method {dict(sorted(Counter(r["method"] for r in sub).items()))}')
    with open(f'data/round10/shapes-{split}.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['shape', 'id', 'vendor', 'method', 'path', 'operationId', 'rule', 'mech', 'label', 'summary'])
        for s, r in cand:
            w.writerow([s, r['id'], r['vendor'], r['method'], r['path'], r.get('operationId', ''), r['rule'], r['mech'], r['label'], r['summary']])
