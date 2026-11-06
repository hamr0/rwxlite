"""Text format 2 parity: Python train/common.fmt_text (format 1 and 2) must equal Node src/text.js formatText byte for byte.
Rows: data/round13 train+val (class = mech, as trained) and the whole corpus data/m0/mechanical.jsonl.gz. The credential-set
lean rule is aliased to cant-undo-verb first on both sides (the Node side does it itself; the data already carries the alias).
Also checks that format 1 equals the stored text of every round13 row. Run: python3 -I m1/t2-parity.py   (prints the mismatch counts; exit 1 on any)."""
import sys, os, json, gzip, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path[:0] = [os.path.expanduser('~/.local/lib/python3.14/site-packages'), os.path.join(ROOT, 'train')]   # numpy for common.py
import common

def run(name, rows):
    # Node reads HTTP QUERY as GET in the model text (rwxmap D134); Python fmt_text prints the stored method, and the
    # round13 data keeps its QUERY copies as QUERY. So the method token is folded here; the HINT folds it itself on both sides.
    for r in rows:
        if str(r['method']).upper() == 'QUERY': r['method'] = 'GET'
        if r['rule'] == 'credential-set': r['rule'] = 'cant-undo-verb'
    inp = '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n'
    res = subprocess.run(['node', os.path.join(ROOT, 'm1', 't2-parity-node.mjs')], input=inp, capture_output=True, text=True, encoding='utf-8', check=False)
    if res.returncode: sys.exit(res.stderr[-2000:])
    got = [json.loads(l) for l in res.stdout.split('\n') if l]
    assert len(got) == len(rows), (len(got), len(rows))
    bad1 = bad2 = hinted = 0; first = []
    for r, g in zip(rows, got):
        p1, p2 = common.fmt_text(r, 1), common.fmt_text(r, 2)
        if p1 != g['t1']: bad1 += 1; first.append((p1, g['t1']))
        if p2 != g['t2']: bad2 += 1; first.append((p2, g['t2']))
        hinted += p2 != p1
    print(f'{name}: {len(rows)} rows, format 1 mismatches {bad1}, format 2 mismatches {bad2}, hinted {hinted}')
    for a, b in first[:3]: print('  py :', a, '\n  js :', b)
    return bad1 + bad2, hinted

bad = 0
rows = []
for sp in ('train', 'val'):
    for l in open(os.path.join(ROOT, 'data', 'round13', sp + '.jsonl'), encoding='utf-8'):
        d = json.loads(l); d['class'] = d['mech']
        # the data rows do not carry the description; it is the last 'desc: ' segment of the stored text
        d['description'] = d['text'].rsplit(' | desc: ', 1)[1] if ' | desc: ' in d['text'] else None
        rows.append(d)
# The data rows carry no description, so the stored description has already been cleaned and cut once; cleaning it a second time
# can change it (an escaped '&amp;' is unescaped again). So the stored-text check covers everything before the 'desc:' segment.
head = lambda t: t.split(' | desc: ')[0].rstrip().replace('credential-set', 'cant-undo-verb')   # alias; a cut summary can end in a space
stored = sum(head(common.fmt_text({**r, 'description': None}, 1)) != head(r['text']) for r in rows)
print(f'round13 stored text vs fmt_text(format 1), everything before desc: {stored} differ of {len(rows)}')
bad += stored
b, _ = run('round13 train+val', rows); bad += b
with gzip.open(os.path.join(ROOT, 'data', 'm0', 'mechanical.jsonl.gz'), 'rt', encoding='utf-8') as f:
    corpus = [json.loads(l) for l in f if l.strip()]
b, _ = run('corpus mechanical.jsonl.gz', corpus); bad += b
# hand probes: unicode, html, newline, odd methods
probes = [dict(method=m, path=p, operationId=o, summary=s, description=d, **{'class': 'w', 'rule': 'floor-put'}) for m, p, o, s, d in [
    ('PUT', '/İam/policy', 'setIAMPolicy', '<b>Set</b>  İAM policy\r\n', 'x'), ('post', '/a/b/members\n', 'AddMember', 'Add&nbsp;member', None),
    ('QUERY', '/x/permissions', 'getPermissions', 'KKey', ''), ('POST', '/teams/{id}/members/$ref', '', '', ''), ('POST', '/users?x=1', 'Foo.createUser', 'Create user', 'd')]]
b, _ = run('probes', probes); bad += b
sys.exit(1 if bad else 0)
