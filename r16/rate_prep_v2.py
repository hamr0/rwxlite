"""Round 16 v2 rating, step 0: only the ops added in v2 (data/r16/pick/added-v2.csv) -> ops jsonl (op_id, method, path, operationId, summary, description).
  python3 -I r16/rate_prep_v2.py OUT_OPS.jsonl   (stdlib only; same fields as r16/rate_prep.py). Ops that stayed from v1 keep their v1 rating."""
import csv, gzip, json, os, sys
csv.field_size_limit(10**9)
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'r16')
added = {r['op_id'] for r in csv.DictReader(open(os.path.join(D, 'pick', 'added-v2.csv'), newline=''))}
n = 0; seen = set()
with open(sys.argv[1], 'w') as o:
    for f in ('dev-en/dev-ops-v2.csv.gz', 'pick/new-300k-v2.csv.gz'):
        with gzip.open(os.path.join(D, f), 'rt', newline='') as fh:
            for r in csv.DictReader(fh):
                if r['op_id'] not in added:
                    continue
                assert r['op_id'] not in seen; seen.add(r['op_id'])
                o.write(json.dumps({k: r[k] for k in ('op_id', 'method', 'path', 'operationId', 'summary', 'description')}, ensure_ascii=False) + '\n'); n += 1
assert seen == added, (len(seen), len(added))
print('rows', n)
