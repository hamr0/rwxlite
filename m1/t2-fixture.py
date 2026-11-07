"""Writes test/fixtures/text2.jsonl: Python fmt_text format 1 and 2 on corpus rows (hinted and unhinted) plus probes, for test/text.test.js.
Deterministic (fixed seed). Run: python3 -I m1/t2-fixture.py"""
import sys, os, json, gzip, random
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path[:0] = [os.path.expanduser('~/.local/lib/python3.14/site-packages'), os.path.join(ROOT, 'train')]
import common
with gzip.open(os.path.join(ROOT, 'data', 'm0', 'mechanical.jsonl.gz'), 'rt', encoding='utf-8') as f:
    rows = [json.loads(l) for l in f if l.strip()]
for r in rows:
    if r['rule'] == 'credential-set': r['rule'] = 'cant-undo-verb'
    if r['method'].upper() == 'QUERY': r['method'] = 'GET'
hinted = [r for r in rows if common.access_hint(r)]; plain = [r for r in rows if not common.access_hint(r)]
rng = random.Random(20261106)
pick = rng.sample(hinted, 400) + rng.sample(plain, 400)
out = []
for r in pick:
    out.append({'state': {k: r.get(k) for k in ('method', 'path', 'operationId', 'summary', 'description')}, 'lean': {'class': r['class'], 'rule': r['rule']},
                't1': common.fmt_text(r, 1), 't2': common.fmt_text(r, 2)})
with open(os.path.join(ROOT, 'test', 'fixtures', 'text2.jsonl'), 'w', encoding='utf-8') as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False) + '\n')
print(len(out), 'rows,', sum(o['t1'] != o['t2'] for o in out), 'hinted')
