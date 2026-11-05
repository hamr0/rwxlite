"""Round 12: add full description + x_evidence (BRIEF-v3 heuristic) to data/round12/seeds.csv -> seeds-desc.csv. New file only."""
import csv, json, os, re, sys
D = 'data'; OUT = os.path.join(D, 'round12', 'seeds-desc.csv')
assert not os.path.exists(OUT)
def src(s):
    if s == 'exam4': return ('j', os.path.join(D, 'exam4', 'inputs.jsonl'))
    if s == 'exam3': return ('j', os.path.join(D, 'exam3', 'inputs.jsonl'))
    return ('c', os.path.join(D, 'r12', 'replay', s, 'ops.csv'))
cache = {}
def load(s):
    if s not in cache:
        k, f = src(s)
        rows = [json.loads(l) for l in open(f) if l.strip()] if k == 'j' else list(csv.DictReader(open(f, newline='', encoding='utf-8')))
        cache[s] = {r['id']: r for r in rows}
    return cache[s]
KW = re.compile(r'\b(delet\w*|remov\w*|purg\w*|wip\w*|destroy\w*|eras\w*|drop\w*|truncat\w*|clear\w*|revok\w*|expir\w*|invalidat\w*|terminat\w*|kill\w*|rotat\w*|reset\w*|send\w*|sent|deliver\w*|notif\w*|publish\w*|post\w*|invit\w*|email\w*|sms|charg\w*|refund\w*|pay\w*|bill\w*|purchas\w*|order\w*|renew\w*|run\w*|trigger\w*|execut\w*|dispatch\w*|sync\w*|import\w*|rebuild\w*|start\w*|cancel\w*|abort\w*|stop\w*|void\w*|permanent\w*|irreversibl\w*|cannot be undone|register\w*|commit\w*|submit\w*|confirm\w*|broadcast\w*|expos\w*|public\w*)\b', re.I)
def clauses(t):
    out = []
    for s in re.split(r'(?<=[.!?])\s+|\n+', t):
        s = s.strip()
        if s: out.append(s)
    return out
def evidence(r):
    for where in ('summary', 'description'):
        t = r.get(where) or ''
        c = [x for x in clauses(t) if KW.search(x)]
        if c:
            best = min(c, key=len)
            m = KW.search(best)
            if len(best) > 160:   # shortest clause around the keyword
                parts = [p.strip() for p in re.split(r'[;,]', best) if KW.search(p)]
                best = min(parts, key=len) if parts else best
            return best, where
    for where in ('operationId', 'path'):
        if KW.search(r.get(where) or ''): return 'none in text', 'none'
    return 'none in text', 'none'
seeds = list(csv.DictReader(open(os.path.join(D, 'round12', 'seeds.csv'), newline='', encoding='utf-8')))
cols = list(seeds[0].keys()) + ['description', 'x_evidence', 'x_evidence_where']
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(cols)
    for s in seeds:
        r = load(s['set'])[s['id']]
        assert r['provider'] == s['provider'] and r['method'].upper() == s['method'].upper() and r['path'] == s['path'], s['seed_id']
        ev, wh = '', ''
        if s['truth'] == 'x':
            ev, wh = evidence(r)
            if wh == 'none':
                # name-only: does the op name/path itself carry the x verb?
                nm = [k for k in ('operationId', 'path') if KW.search(r.get(k) or '')]
                if nm: wh = nm[0]; ev = (r.get(wh) or '')
        w.writerow([s[c] for c in list(seeds[0].keys())] + [r.get('description') or '', ev, wh])
print('wrote', len(seeds))
