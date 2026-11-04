"""Exam #3 score (pre-registration: docs/wiki/exam-prereg-exam3.md). Opens the truth file ONCE.
  python3 train/exam3_score.py <work-dir> <truth.csv> [--smoke]    # truth.csv: id,label (r|w|x)
Per model file (r10 and 0.2.0, int8-pc and fp32) and per config: exact / too loose / too tight / asked, per vendor and per method, and
every too-loose row. Gate numbers are the GONOGO_lba097 config until the prereg's rwxmap section fixes the gate config.
--smoke labels every line SMOKE TEST (a pipeline check on already-burned rows, not a result).
"""
import sys, os, json, csv
import numpy as np
import exam_fresh as F
from common import ORDER, LABELS

def main():
    wd, truth_path = sys.argv[1], sys.argv[2]; smoke = '--smoke' in sys.argv
    tag = '[SMOKE TEST - not a result] ' if smoke else ''
    inp = {}; order = []
    for l in open(os.path.join(wd, 'inputs.jsonl')):
        if l.strip(): r = json.loads(l); inp[r['id']] = r; order.append(r['id'])
    truth = {}
    for r in csv.DictReader(open(truth_path, newline='', encoding='utf-8')):   # the ONLY place truth is opened
        assert r['id'] not in truth, 'duplicate truth id'; truth[r['id']] = r['label']
    assert set(truth) == set(inp) and len(truth) == len(order), 'join is not 1:1'
    assert set(truth.values()) <= set(LABELS)
    y = np.array([ORDER[truth[i]] for i in order]); N = len(order)
    vend = np.array([inp[i]['provider'] for i in order]); meth = np.array([inp[i]['method'] for i in order])
    res = {'smoke': smoke, 'n': N, 'truth_dist': {l: int((y == ORDER[l]).sum()) for l in LABELS}, 'models': {}}
    out = [f'{tag}n={N} truth {res["truth_dist"]}']
    f = lambda d: f"right {d['right']} ({d['rightPct']}%)  loose {d['loose']} ({d['loosePct']}%)  tight {d['tight']} ({d['tightPct']}%)  asked {d['asked']} ({d['askedPct']}%)"
    for name in ('r10-int8pc', 'r10-fp32', 'v020-int8pc', 'v020-fp32'):
        P = {r['id']: r for r in csv.DictReader(open(os.path.join(wd, f'predictions-{name}.csv')))}
        assert set(P) == set(inp)
        pa = np.array([ORDER[P[i]['a_letter']] for i in order]); mech = np.array([ORDER[P[i]['mech']] for i in order]); conf = np.array([float(P[i]['max_p']) for i in order])
        m = {'configs': {}, 'by_vendor': {}, 'by_method': {}, 'too_loose_rows': {}}
        out.append(f'\n{tag}=== {name} ===')
        for c in F.CONFIGS:
            col = [P[i][c] for i in order]; asked = np.array([v == 'ask' for v in col]); fin = np.array([0 if v == 'ask' else ORDER[v] for v in col])
            m['configs'][c] = F.piles(fin, asked, pa, y)
            m['by_vendor'][c] = {v: F.piles(fin, asked, pa, y, vend == v) for v in sorted(set(vend))}
            m['by_method'][c] = {v: F.piles(fin, asked, pa, y, meth == v) for v in sorted(set(meth))}
            rows = []
            for k in np.where(~asked & (fin < y))[0]:
                r = inp[order[k]]; typ = 'loweredWrongly' if fin[k] < mech[k] else 'keepMechLoose' if fin[k] == mech[k] else 'raiseStillLoose'
                rows.append({'id': order[k], 'type': typ, 'vendor': r['provider'], 'method': r['method'], 'path': r['path'], 'operationId': r['operationId'], 'mech': LABELS[mech[k]],
                             'mech_rule': r['class'] + '/' + r['rule'], 'model': LABELS[fin[k]], 'max_p': round(float(conf[k]), 4), 'p': [float(P[order[k]][q]) for q in ('p_r', 'p_w', 'p_x')], 'truth': LABELS[y[k]]})
            m['too_loose_rows'][c] = rows
            out.append(f'{tag}{c:18s} {f(m["configs"][c])}')
        g = m['configs']['GONOGO_lba097']; ok = {'loose_le_0.5pct': g['loosePct'] <= 0.5, 'exact_ge_91pct': g['rightPct'] >= 91.0, 'asked_le_15pct': g['askedPct'] <= 15.0}
        m['gonogo_lba097'] = {**ok, 'verdict': 'PASS' if all(ok.values()) else 'NO-GO'}
        out.append(f'{tag}GONOGO_lba097 {m["gonogo_lba097"]}')
        for key in ('by_vendor', 'by_method'):
            for c in ('GONOGO_lba097', 'a_none'):
                out.append(f'{tag}--- {c} {key}'); [out.append(f'{tag}  {v:14s} {f(d)}') for v, d in m[key][c].items()]
        for c in ('GONOGO_lba097', 'a_none'):
            out.append(f'{tag}--- too-loose rows, {c}: {len(m["too_loose_rows"][c])}')
            for r in m['too_loose_rows'][c]: out.append(f'{tag}  LOOSE {json.dumps(r)}')
        res['models'][name] = m
    json.dump(res, open(os.path.join(wd, 'results.json'), 'w'), indent=1)
    open(os.path.join(wd, 'score.log'), 'w').write('\n'.join(out) + '\n'); print('\n'.join(out))

if __name__ == '__main__': main()
