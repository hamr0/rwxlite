"""Round 15 Jev pilot, step 0: the 400 blind-reviewed rows -> ops jsonl (adds operationId from the pick csv.gz).
  python3 -I r15/jev_pilot_prep.py
Reads data/r15/labels/disagree-sample-400.csv and pick-200000-1-opinions.csv.gz; writes data/r15/labels/jev-pilot-ops.jsonl (gitignored)."""
import csv, gzip, json, sys
csv.field_size_limit(10**9)
L = 'data/r15/labels/'
ids = [r['op_id'] for r in csv.DictReader(open(L + 'disagree-sample-400.csv', newline='', encoding='utf-8'))]
want = set(ids); got = {}
with gzip.open(L + 'pick-200000-1-opinions.csv.gz', 'rt', newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r['op_id'] in want:
            got[r['op_id']] = {k: r[k] for k in ('op_id', 'method', 'path', 'operationId', 'summary', 'description')}
miss = [i for i in ids if i not in got]
if miss: sys.exit(f'missing {len(miss)} ids')
with open(L + 'jev-pilot-ops.jsonl', 'w', encoding='utf-8') as o:
    for i in ids: o.write(json.dumps(got[i], ensure_ascii=False) + '\n')
print('rows', len(ids))
