"""Exam #4 predict (pre-registration: docs/wiki/exam-prereg-exam4.md). NEVER opens a truth file.
  node m0/exam4-inputs.mjs <ops.csv> <work-dir>
  python3 train/exam4_predict.py <work-dir> [--smoke]
Real run: <work-dir> must be data/exam4, inputs.jsonl must be the 1505 rows ex4-0001..ex4-1505, and the run refuses if any predictions-*/p-* file
already exists (nothing is overwritten). --smoke: <work-dir> must NOT be data/exam4 and its name must contain "smoke" (a pipeline check on burned
rows, outputs marked smoke in predict-meta.json). Writes predictions-<model>.csv and p-<model>.jsonl for the four models of exam4_common.MODELS.
"""
import sys, os, json, csv, time, glob
import numpy as np
import exam_score as E
import exam_fresh as F
from common import ORDER, LABELS, TIER, fmt_text
from tune_cuts import guarded
import exam4_common as C

def main():
    args = [a for a in sys.argv[1:] if a != '--smoke']; smoke = '--smoke' in sys.argv
    if len(args) != 1: raise SystemExit('usage: exam4_predict.py <work-dir> [--smoke]')
    wd = args[0]
    if smoke:
        if C.is_real(wd) or 'smoke' not in os.path.basename(os.path.realpath(wd)): raise SystemExit('--smoke: work-dir must not be data/exam4 and its name must contain "smoke"')
    elif not C.is_real(wd): raise SystemExit(f'real run: work-dir must be {C.REAL_DIR}')
    old = glob.glob(os.path.join(wd, 'predictions-*.csv')) + glob.glob(os.path.join(wd, 'p-*.jsonl')) + glob.glob(os.path.join(wd, 'predict-meta.json'))
    if old: raise SystemExit(f'refusing to overwrite existing prediction files: {old[:3]}')
    mstr = C.check_models()
    rows = [json.loads(l) for l in open(os.path.join(wd, 'inputs.jsonl')) if l.strip()]
    if not smoke:
        want = [f'ex4-{i:04d}' for i in range(1, C.N_ROWS + 1)]
        if [r['id'] for r in rows] != want: raise SystemExit(f'real run: inputs.jsonl ids are not exactly ex4-0001..ex4-{C.N_ROWS}')
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(os.path.join(C.ROOT, 'data', 'train', 'ckpt-r8soft', 'final'))   # same vocab.txt (sha checked above)
    texts = [r['text'] for r in rows]
    bad = [r['id'] for r in rows if fmt_text({**r, 'method': 'GET' if r['method'] == 'QUERY' else r['method'], 'rule': {'credential-set': 'cant-undo-verb'}.get(r['rule'], r['rule'])}) != r['text']]
    if bad: raise SystemExit(f'text path mismatch Node vs Python on {len(bad)} rows, first {bad[:5]}')
    ids = tok(texts, truncation=True, max_length=C.MAXLEN)['input_ids']
    mech = np.array([ORDER[r['class']] for r in rows]); meta = {'n': len(rows), 'smoke': smoke, 'models': {n: {'sha256': m['sha'], 'manifest_sha256': m['msha'], 'model': mstr[n], 'T': m['T']} for n, m in C.MODELS.items()}, 'time_s': {}}
    for name, m in C.MODELS.items():
        t0 = time.time(); P = C.probs(os.path.join(m['dir'], m['file']), ids, m['T']); meta['time_s'][name] = round(time.time() - t0, 1); conf = P.max(1)
        pa = E.mode_a(rows, P); pb = guarded(P, E.MARGIN); Cf = F.configs(pa, pb, mech, conf)
        with open(os.path.join(wd, f'predictions-{name}.csv'), 'x', newline='') as f:
            w = csv.writer(f); w.writerow(['id', 'provider', 'method', 'path', 'mech', 'mech_rule', 'tier', 'a_letter', 'b_letter', 'move', 'p_r', 'p_w', 'p_x', 'max_p', *F.CONFIGS])
            for i, r in enumerate(rows):
                mv = 'lowering' if pa[i] < mech[i] else 'raise' if pa[i] > mech[i] else 'keep'
                w.writerow([r['id'], r['provider'], r['method'], r['path'], r['class'], r['rule'], TIER.get(r['jev_tier'], 'none'), LABELS[pa[i]], LABELS[pb[i]], mv,
                            *[f'{P[i, k]:.6f}' for k in range(3)], f'{conf[i]:.6f}', *[('ask' if Cf[k][1][i] else LABELS[Cf[k][0][i]]) for k in F.CONFIGS]])
        pis, pch = P[:, 2], P[:, 1] + P[:, 2]
        assert ((0 <= pis) & (pis <= pch) & (pch <= 1)).all(), f'{name}: need 0 <= pIsX <= pChanges <= 1'
        with open(os.path.join(wd, f'p-{name}.jsonl'), 'x') as f:
            for i, r in enumerate(rows): f.write(json.dumps({'id': r['id'], 'model': mstr[name], 'pIsX': float(pis[i]), 'pChanges': float(pch[i])}) + '\n')
        print(f'{name}: predicted {len(rows)} rows in {meta["time_s"][name]}s, T={m["T"]}, {mstr[name]}')
    with open(os.path.join(wd, 'predict-meta.json'), 'x') as f: json.dump(meta, f, indent=1)
    print('truth never opened')

if __name__ == '__main__': main()
