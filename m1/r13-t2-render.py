"""R13-L3-t2 data: re-render data/round13 train/val/v3eval text in text format 2 into data/round13-t2/. Labels, targets and every
other field are identical; only 'text' differs, and only on rows train/common.access_hint flags: 'hint: access' is inserted as the
second segment, right after 'lean: <letter> <rule>'. Deterministic, no training. Checks: removing the inserted segment gives the
old text; every other field equal. Writes {train,val,v3eval}.{jsonl,parquet}, SHA256SUMS and summary.json.
Run: python3 -I m1/r13-t2-render.py   (pandas/pyarrow come from the user site, added to sys.path below)."""
import sys, os, json, hashlib, collections, csv
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path[:0] = [os.path.expanduser('~/.local/lib/python3.14/site-packages'), os.path.join(ROOT, 'train')]
import pandas as pd
import common
SRC, OUT = os.path.join(ROOT, 'data', 'round13'), os.path.join(ROOT, 'data', 'round13-t2')
os.makedirs(OUT, exist_ok=True)
SEG = ' | hint: access'
stats = {}
for name in ('train', 'val', 'v3eval'):
    rows = [json.loads(l) for l in open(os.path.join(SRC, name + '.jsonl'), encoding='utf-8')]
    new = []; c = collections.Counter(); byl = collections.Counter()
    for r in rows:
        head, sep, rest = r['text'].partition(' | ')
        assert sep and head.startswith('lean: ') and 'hint: access' not in head, r['id']
        h = common.access_hint(r)
        t2 = head + SEG + sep + rest if h else r['text']
        if h:
            assert t2.replace(SEG, '', 1) == r['text']
            c['hinted'] += 1; byl[r['label']] += 1
        d = dict(r); d['text'] = t2; new.append(d)
    assert all({k: v for k, v in a.items() if k != 'text'} == {k: v for k, v in b.items() if k != 'text'} for a, b in zip(rows, new))
    with open(os.path.join(OUT, name + '.jsonl'), 'w', encoding='utf-8') as f:
        for r in new: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    pd.DataFrame(new).to_parquet(os.path.join(OUT, name + '.parquet'), index=False)
    stats[name] = {'rows': len(rows), 'hinted': c['hinted'], 'hinted_by_label': {k: byl[k] for k in 'rwx'}}
    print(name, stats[name])
json.dump({'format': 2, 'source': 'data/round13', 'stats': stats}, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)
names = ['train.jsonl', 'train.parquet', 'val.jsonl', 'val.parquet', 'v3eval.jsonl', 'v3eval.parquet', 'summary.json']
with open(os.path.join(OUT, 'SHA256SUMS'), 'w') as f:
    for n in names: f.write(hashlib.sha256(open(os.path.join(OUT, n), 'rb').read()).hexdigest() + '  ' + n + '\n')
print(open(os.path.join(OUT, 'SHA256SUMS')).read())
