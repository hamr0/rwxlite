#!/usr/bin/env -S python3 -I
"""Build the blind fresh exam ops.csv from four pinned vendor specs.
Run: python3 -I m0/fresh-exam-build.py   (specs parsed only, never executed)
Shuffle: python random.Random(20261110).shuffle over ops in vendor order
(coolify, workos, lago, resend), each in spec document order. ids fx-0001.."""
import csv, gzip, hashlib, json, os, random, re, shutil, sys, collections
import yaml
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
OUT = R + 'data/exam-2026-11-03-fresh/'
# Original download dir (local only). On a fresh clone, rebuild from the committed pinned copies in OUT/specs/.
LOCAL = os.path.isdir(R + 'data/fresh-exam-specs/')
SRC = R + 'data/fresh-exam-specs/' if LOCAL else OUT + 'specs/'
def src(v, fn): return f'{SRC}{v}/{fn}' if LOCAL else f'{SRC}{fn}'
def meta_path(v): return f'{SRC}{v}/META.json' if LOCAL else f'{SRC}{v}.META.json'
SEED = 20261110
V = [('coolify', 'coolify.io', 'coolify.json'), ('workos', 'workos.com', 'workos.yaml'),
     ('lago', 'getlago.com', 'lago.yaml'), ('resend', 'resend.com', 'resend.yaml')]
METHODS = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
def clean(x):
    return re.sub(r'\s+', ' ', x).strip() if isinstance(x, str) else ('' if x is None else str(x))
ops = []; stats = {}
for v, dom, fn in V:
    meta = json.load(open(meta_path(v)))
    raw = open(src(v, fn), 'rb').read()
    if hashlib.sha256(raw).hexdigest() != meta['sha256_of_raw_download']:
        sys.exit(f'SHA MISMATCH {v}')
    spec = json.loads(raw) if fn.endswith('.json') else yaml.safe_load(raw)
    n = 0
    for path, item in spec['paths'].items():
        for m in METHODS:
            if isinstance(item, dict) and m in item and isinstance(item[m], dict):
                o = item[m]
                ops.append(dict(provider=dom, method=m.upper(), path=path, operationId=clean(o.get('operationId')),
                                summary=clean(o.get('summary')), description=clean(o.get('description'))))
                n += 1
    stats[v] = n
    print(v, n, 'meta', meta['ops'])
random.Random(SEED).shuffle(ops)
with open(OUT + 'ops.csv', 'w', newline='') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'])
    for i, o in enumerate(ops, 1):
        w.writerow([f'fx-{i:04d}', o['provider'], o['method'], o['path'], o['operationId'], o['summary'], o['description']])
if LOCAL:  # pin copies only when building from the original downloads
    for v, dom, fn in V:
        shutil.copy(src(v, fn), f'{OUT}specs/{fn}')
        shutil.copy(meta_path(v), f'{OUT}specs/{v}.META.json')
# report
c = collections.Counter((o['provider'], o['method']) for o in ops)
for k in sorted(c): print(k, c[k])
print('total', len(ops))
print('empty desc', sum(1 for o in ops if not o['description']), 'empty summary', sum(1 for o in ops if not o['summary']),
      'empty opId', sum(1 for o in ops if not o['operationId']))
d = collections.Counter((o['provider'], o['operationId']) for o in ops if o['operationId'])
print('dup opIds', [k for k, n in d.items() if n > 1])
keys = set((o['provider'], o['method'], o['path']) for o in ops)
print('dup op keys', len(ops) - len(keys))
MECH = R + 'data/m0/mechanical.jsonl.gz'  # local only (gitignored)
if os.path.exists(MECH):
    hit = 0; mp = set()
    for line in gzip.open(MECH, 'rt'):
        r = json.loads(line); mp.add(r['provider'])
        if (r['provider'], r['method'], r['path']) in keys: hit += 1
    print('overlap op keys with mechanical.jsonl.gz:', hit, '; provider overlap:', sorted(mp & {dom for _, dom, _ in V}))
else:
    print('overlap check skipped: data/m0/mechanical.jsonl.gz not present (local only)')
