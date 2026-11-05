"""Exam #4 score (pre-registration: docs/wiki/exam-prereg-exam4.md). Opens the truth file ONCE.
  python3 train/exam4_score.py <work-dir> <truth.csv>            # real: work-dir = data/exam4
  python3 train/exam4_score.py <work-dir> <truth.csv> --smoke    # pipeline check on burned rows only
Real run: the truth file's sha256 must equal exam4_common.TRUTH_SHA (hard-coded, no argument can change it) BEFORE it is parsed; the work-dir must be
data/exam4; every inputs.jsonl / predictions-*.csv / p-*.jsonl in it must match docs/wiki/exam-prereg-exam4-predictions.sha256 (committed before truth);
n must be 1505; and it refuses if results.json already exists (score once). Writes results.json and score.log.
--smoke: work-dir must NOT be data/exam4 and its name must contain "smoke"; refuses the real exam #4 truth; the hash check is skipped; writes ONLY
results-smoke.json / score-smoke.log, every line marked SMOKE TEST; it cannot touch the real outputs.
Per model and config: right / too loose / too tight / asked, per vendor and per method, every too-loose row. Gate (D135, mode a fp32, config a_none):
r11-fp32 too loose <= v020-fp32 too loose AND r11-fp32 right >= v020-fp32 right (integer counts, ties pass). Also: D133 bar vs mechanical for each
mode-a model (too loose <= mech's AND right >= mech's + ceil(0.05 n)), the exam #3 rwxlite gate GONOGO_lba097 (info), and the rows where the fp32 models differ.
"""
import sys, os, json, csv, hashlib, math
import numpy as np
import exam_fresh as F
from common import ORDER, LABELS
import exam4_common as C

PRED_SHA = os.path.join(C.ROOT, 'docs', 'wiki', 'exam-prereg-exam4-predictions.sha256')

def main():
    args = [a for a in sys.argv[1:] if a != '--smoke']; smoke = '--smoke' in sys.argv
    if len(args) != 2: raise SystemExit('usage: exam4_score.py <work-dir> <truth.csv> [--smoke]')
    wd, truth_path = args
    got = hashlib.sha256(open(truth_path, 'rb').read()).hexdigest()   # hash only; not parsed until checked
    if smoke:
        if C.is_real(wd) or 'smoke' not in os.path.basename(os.path.realpath(wd)): raise SystemExit('--smoke: work-dir must not be data/exam4 and its name must contain "smoke"')
        if got == C.TRUTH_SHA: raise SystemExit('--smoke: refusing the real exam #4 truth')
        suffix = '-smoke'
    else:
        if got != C.TRUTH_SHA: raise SystemExit(f'TRUTH HASH MISMATCH: {truth_path} is {got}, the only accepted truth is {C.TRUTH_SHA}. Refusing to score.')
        if not C.is_real(wd): raise SystemExit(f'real run: work-dir must be {C.REAL_DIR}')
        if os.path.exists(os.path.join(wd, 'results.json')): raise SystemExit('results.json exists: exam #4 is scored once (rerun only for a crash or row-join bug, by hand, recorded)')
        if not os.path.exists(PRED_SHA): raise SystemExit(f'missing {PRED_SHA}: prediction sha256s must be committed before truth is opened')
        want = {}
        for l in open(PRED_SHA):
            if l.strip(): h, fn = l.split(); want[fn.lstrip('*')] = h
        have = sorted(fn for fn in os.listdir(wd) if fn == 'inputs.jsonl' or fn.startswith('predictions-') or fn.startswith('p-'))
        if sorted(want) != have: raise SystemExit(f'prediction file set differs from {PRED_SHA}: committed {sorted(want)}, on disk {have}')
        for fn in have:
            if C.sha256(os.path.join(wd, fn)) != want[fn]: raise SystemExit(f'{fn} differs from its committed sha256; refusing to score')
        suffix = ''
    tag = '[SMOKE TEST - not a result] ' if smoke else ''
    inp = {}; order = []
    for l in open(os.path.join(wd, 'inputs.jsonl')):
        if l.strip(): r = json.loads(l); inp[r['id']] = r; order.append(r['id'])
    if not smoke: assert order == [f'ex4-{i:04d}' for i in range(1, C.N_ROWS + 1)], 'inputs are not ex4-0001..1505'
    truth = {}
    for r in csv.DictReader(open(truth_path, newline='', encoding='utf-8')):   # the ONLY place truth is opened
        assert r['id'] not in truth, 'duplicate truth id'; truth[r['id']] = r['label']
    assert set(truth) == set(inp) and len(truth) == len(order), 'join is not 1:1'
    assert set(truth.values()) <= set(LABELS)
    y = np.array([ORDER[truth[i]] for i in order]); N = len(order)
    vend = np.array([inp[i]['provider'] for i in order]); meth = np.array([inp[i]['method'] for i in order])
    res = {'smoke': smoke, 'n': N, 'truth_sha256': got, 'truth_dist': {l: int((y == ORDER[l]).sum()) for l in LABELS}, 'models': {}}
    out = [f'{tag}n={N} truth {res["truth_dist"]}']
    f = lambda d: f"right {d['right']} ({d['rightPct']}%)  loose {d['loose']} ({d['loosePct']}%)  tight {d['tight']} ({d['tightPct']}%)  asked {d['asked']} ({d['askedPct']}%)"
    fins = {}
    for name in C.MODELS:
        P = {r['id']: r for r in csv.DictReader(open(os.path.join(wd, f'predictions-{name}.csv')))}
        assert set(P) == set(inp)
        pa = np.array([ORDER[P[i]['a_letter']] for i in order]); mech = np.array([ORDER[P[i]['mech']] for i in order]); conf = np.array([float(P[i]['max_p']) for i in order])
        m = {'configs': {}, 'by_vendor': {}, 'by_method': {}, 'too_loose_rows': {}}
        out.append(f'\n{tag}=== {name} ===')
        for c in F.CONFIGS:
            col = [P[i][c] for i in order]; asked = np.array([v == 'ask' for v in col]); fin = np.array([0 if v == 'ask' else ORDER[v] for v in col])
            if c == 'a_none': fins[name] = fin; assert not asked.any()
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
        m['gonogo_lba097_info'] = {**ok, 'verdict': 'PASS' if all(ok.values()) else 'NO-GO'}
        out.append(f'{tag}GONOGO_lba097 (info, exam #3 rwxlite bars) {m["gonogo_lba097_info"]}')
        for key in ('by_vendor', 'by_method'):
            for c in ('GONOGO_lba097', 'a_none'):
                out.append(f'{tag}--- {c} {key}'); [out.append(f'{tag}  {v:14s} {f(d)}') for v, d in m[key][c].items()]
        for c in ('GONOGO_lba097', 'a_none'):
            out.append(f'{tag}--- too-loose rows, {c}: {len(m["too_loose_rows"][c])}')
            for r in m['too_loose_rows'][c]: out.append(f'{tag}  LOOSE {json.dumps(r)}')
        res['models'][name] = m
    # D133 bar (info): mode a vs mechanical, same rows
    mc = res['models']['r11-fp32']['configs']['mechanical']; need = math.ceil(0.05 * N); res['d133'] = {'mech_right': mc['right'], 'mech_loose': mc['loose'], 'needs_extra_right': need}
    for name in C.MODELS:
        a = res['models'][name]['configs']['a_none']; res['d133'][name] = {'right': a['right'], 'loose': a['loose'], 'pass': a['loose'] <= mc['loose'] and a['right'] >= mc['right'] + need}
    out.append(f'\n{tag}=== D133 mode a vs mechanical (info; mech right {mc["right"]}, loose {mc["loose"]}, needs right >= {mc["right"] + need}) ===')
    for name in C.MODELS: out.append(f'{tag}  {name:12s} {res["d133"][name]}')
    # D135 gate: mode a fp32, config a_none, integer counts, ties pass
    b, c_ = res['models']['v020-fp32']['configs']['a_none'], res['models']['r11-fp32']['configs']['a_none']
    gate = {'base_loose': b['loose'], 'cand_loose': c_['loose'], 'base_right': b['right'], 'cand_right': c_['right'], 'base_tight': b['tight'], 'cand_tight': c_['tight'],
            'loose_ok': c_['loose'] <= b['loose'], 'exact_ok': c_['right'] >= b['right']}
    gate['verdict'] = 'GO' if gate['loose_ok'] and gate['exact_ok'] else 'NO-GO'; res['d135_gate'] = gate
    diff = [i for i, (u, v) in enumerate(zip(fins['v020-fp32'], fins['r11-fp32'])) if u != v]
    res['fp32_diff_rows'] = [{'id': order[k], 'vendor': inp[order[k]]['provider'], 'method': inp[order[k]]['method'], 'path': inp[order[k]]['path'], 'base': LABELS[fins['v020-fp32'][k]], 'cand': LABELS[fins['r11-fp32'][k]], 'truth': LABELS[y[k]]} for k in diff]
    out.append(f'\n{tag}=== D135 GATE (a_none, fp32, r11 vs 0.2.0) ===\n{tag}{json.dumps(gate)}')
    out.append(f'{tag}--- rows where v020-fp32 and r11-fp32 differ: {len(diff)}'); [out.append(f'{tag}  DIFF {json.dumps(r)}') for r in res['fp32_diff_rows']]
    json.dump(res, open(os.path.join(wd, f'results{suffix}.json'), 'x'), indent=1)
    open(os.path.join(wd, f'score{suffix}.log'), 'x').write('\n'.join(out) + '\n'); print('\n'.join(out))

if __name__ == '__main__': main()
