"""Round 12: build data/round12/variants-final.jsonl + summary (new files only)."""
import json, csv, re, statistics, collections
D = 'data/round12/'
rj = lambda p: [json.loads(l) for l in open(D + p) if l.strip()]
seeds = {r['seed_id']: r for r in csv.DictReader(open(D + 'seeds-desc.csv'))}
x2 = rj('variants-x2.jsonl'); kept = rj('variants-kept.jsonl')
jev = {r['id']: r for r in rj('jev-x2.jsonl') if r.get('p') is not None}
log = []
x2seeds = {r['seed_id'] for r in x2}
out = []
def row(r, source, jp, wh=None, rel=None):
    return dict(seed_id=r['seed_id'], kind=r['kind'], provider=r['provider'], method=r['method'], path=r['path'],
                operationId=r['operationId'], summary=r['summary'], description=r.get('description'), label=r['label'],
                source=source, jev_p=jp, weight_hint=wh, relabel=rel)
ov = next(r for r in csv.DictReader(open(D + 'user-label-overrides.csv')))
oseed = [s for s, r in seeds.items() if r['id'] == ov['source_id']][0]
for r in kept:
    if r['kind'] == 'surface' and r['label'] == 'x' and r['seed_id'] in x2seeds:
        log.append(('replaced_by_x2', r['batch'], r)); continue
    wh = 'low' if (r['batch'] == 'b3' and r['kind'] == 'contrast') else None
    rel = None
    if r['seed_id'] == oseed:
        if r['kind'] == 'surface': r = dict(r, label='x'); rel = 'user-2026-11-05'
        else: log.append(('contrast_of_overridden_seed_now_x', r['batch'], r)); continue
    out.append(row(r, r['batch'], r.get('jev_p'), wh, rel))
for i, r in enumerate(x2):
    a = jev[f'x2:{i+1}']
    if r['label'] == 'w' and a['p'] >= 0.5: log.append(('x2_w_contrast_jev_x', 'x2', r)); continue
    out.append(row(r, 'x2', a['p']))
pat = re.compile(r'restart|start|stop|pause|resume|suspend', re.I)
fin = []
for r in out:
    if pat.search(' '.join(str(r[k]) for k in ('path', 'operationId', 'summary', 'description'))): log.append(('restart_stop_term', r['source'], r))
    else: fin.append(r)
open(D + 'variants-final.jsonl', 'w').write('\n'.join(json.dumps(r) for r in fin) + '\n')
c = collections.Counter((r['source'], r['kind'], r['label']) for r in fin)
n = len(fin); nx = sum(r['label'] == 'x' for r in fin)
per = collections.Counter(r['seed_id'] for r in fin); v = sorted(per.values())
lc = collections.Counter(l[0] for l in log)
L = [f'# variants-final summary\n', f'Rows: {n}. x share: {nx}/{n} = {100*nx/n:.1f}%. Seeds covered: {len(per)}.',
     f'Rows per seed: min {v[0]}, median {statistics.median(v)}, max {v[-1]}.\n', '## source x kind x label', '| source | kind | label | n |', '|---|---|---|---|']
L += [f'| {s} | {k} | {l} | {m} |' for (s, k, l), m in sorted(c.items())]
L += ['', '## label totals'] + [f'- {l}: {sum(m for (s,k,ll),m in c.items() if ll==l)}' for l in 'rwx']
L += ['', f'weight_hint low: {sum(r["weight_hint"]=="low" for r in fin)}; relabel user-2026-11-05: {sum(bool(r["relabel"]) for r in fin)} (seed {oseed})',
      '', '## drop log (counts)'] + [f'- {k}: {m}' for k, m in lc.items()]
L += ['', '## drop log (rows)', '| reason | src | seed | kind | label | method | path | summary |', '|---|---|---|---|---|---|---|---|']
L += [f"| {a} | {b} | {r['seed_id']} | {r['kind']} | {r['label']} | {r['method']} | {r['path']} | {r.get('summary')} |" for a, b, r in log if a != 'replaced_by_x2']
L += ['', f'replaced_by_x2 rows (first-round surface x of x2 seeds) are not listed individually: {lc["replaced_by_x2"]} rows across {len({r["seed_id"] for a,b,r in log if a=="replaced_by_x2"})} seeds.',
      f'Restart/stop-term exclusions: {lc.get("restart_stop_term",0)}.']
open(D + 'variants-final-summary.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L[:40])); print(dict(lc))
