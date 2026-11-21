"""Check a labeller output file against its input: same op_ids in the same order, header op_id,letter,confidence,reason, letter in r/w/x, confidence in sure/likely/unsure.
  python3 -I r16/label_check_out.py IN.csv OUT.csv   (stdlib only; exit 1 on any problem)"""
import csv, sys
csv.field_size_limit(10**9)
ids = [r['op_id'] for r in csv.DictReader(open(sys.argv[1], newline='', encoding='utf-8'))]
with open(sys.argv[2], newline='', encoding='utf-8') as f: rows = list(csv.reader(f))
bad = []
if not rows or rows[0] != ['op_id', 'letter', 'confidence', 'reason']: bad.append(f'header {rows[0] if rows else None}')
body = rows[1:]
if len(body) != len(ids): bad.append(f'rows {len(body)} != input {len(ids)}')
for n, (i, r) in enumerate(zip(ids, body), 2):
    if len(r) != 4: bad.append(f'line {n}: {len(r)} fields'); continue
    if r[0] != i: bad.append(f'line {n}: op_id {r[0]} != {i}')
    if r[1] not in ('r', 'w', 'x'): bad.append(f'line {n}: letter {r[1]!r}')
    if r[2] not in ('sure', 'likely', 'unsure'): bad.append(f'line {n}: confidence {r[2]!r}')
    if not r[3].strip(): bad.append(f'line {n}: empty reason')
print('OK' if not bad else 'PROBLEMS'); [print(' ', b) for b in bad[:30]]; sys.exit(1 if bad else 0)
