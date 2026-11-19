"""Round 15 labelling, step 0: pick csv.gz -> ops jsonl (op_id, method, path, operationId, summary, description), same order as the pick.
  python3 -I r15/label_prep.py data/r15/picks/pick-200000-1.csv.gz OUT_OPS.jsonl"""
import csv, gzip, json, sys
csv.field_size_limit(10**9)
src, out = sys.argv[1:3]
n = 0; seen = set()
with gzip.open(src, 'rt', newline='') as f, open(out, 'w') as o:
    for r in csv.DictReader(f):
        assert r['op_id'] not in seen; seen.add(r['op_id'])
        o.write(json.dumps({k: r[k] for k in ('op_id', 'method', 'path', 'operationId', 'summary', 'description')}, ensure_ascii=False) + '\n'); n += 1
print('rows', n)
