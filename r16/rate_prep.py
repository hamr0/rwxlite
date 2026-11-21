"""Round 16 rating, step 0: new-300k + dev-en csv.gz -> ops jsonl (op_id, method, path, operationId, summary, description); dev rows first, then the pick.
  python3 -I r16/rate_prep.py OUT_OPS.jsonl   (stdlib only; same fields as r15/label_prep.py)"""
import csv, gzip, json, os, sys
csv.field_size_limit(10**9)
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'r16')
n = 0; seen = set()
with open(sys.argv[1], 'w') as o:
    for f in ('dev-en/dev-ops.csv.gz', 'pick/new-300k.csv.gz'):
        with gzip.open(os.path.join(D, f), 'rt', newline='') as fh:
            for r in csv.DictReader(fh):
                assert r['op_id'] not in seen; seen.add(r['op_id'])
                o.write(json.dumps({k: r[k] for k in ('op_id', 'method', 'path', 'operationId', 'summary', 'description')}, ensure_ascii=False) + '\n'); n += 1
print('rows', n)
