#!/usr/bin/env python3
"""Write the 442 held-out rows (provider ory.sh, clerk.com) of rwxmap's exam #3 ops.csv, sha256-checked, header and every other column unchanged. Never opens truth.
python3 -I m1/holdout-ops.py <ops.csv> <out.csv> <heldout-ids.txt>"""
import csv, hashlib, sys
ops, out, ids = sys.argv[1:4]
assert hashlib.sha256(open(ops, 'rb').read()).hexdigest() == 'fff7afa983c7fc85e2073e5662c4c317c69e37a1dd92a04c7e5dc04ecf43d790', 'ops.csv sha256'
want = set(open(ids).read().split()); R = list(csv.DictReader(open(ops, newline='', encoding='utf-8')))
keep = [r for r in R if r['provider'] in ('ory.sh', 'clerk.com')]
assert {r['id'] for r in keep} == want and len(keep) == 442, 'held-out ids differ from the assembly'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(R[0])); w.writeheader(); w.writerows(keep)
print(len(keep), 'rows')
