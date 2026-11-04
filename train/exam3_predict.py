"""Exam #3 predict (pre-registration: docs/wiki/exam-prereg-exam3.md). NEVER opens a truth file.
  node m0/exam3-inputs.mjs <ops.csv> <work-dir>
  python3 train/exam3_predict.py <work-dir> [--smoke]   # -> <work-dir>/predictions-<model>.csv for the four model files in exam3_common.MODELS
Refuses to run if any model file or vocab.txt differs from the frozen sha256 in exam3_common.py.
"""
import sys, os, json, csv, time
import numpy as np
import exam_score as E
import exam_fresh as F
from common import ORDER, LABELS, TIER, fmt_text
from tune_cuts import guarded
import exam3_common as C

def main():
    wd = sys.argv[1]; hashes = C.check_hashes()
    rows = [json.loads(l) for l in open(os.path.join(wd, 'inputs.jsonl')) if l.strip()]
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(os.path.join(C.ROOT, 'data', 'train', 'ckpt-r8soft', 'final'))   # same vocab.txt as r10 (sha checked above)
    texts = [r['text'] for r in rows]
    # the Node text path (src/text.js) must equal Python fmt_text, once QUERY->GET and the credential-set alias are applied
    bad = [r['id'] for r in rows if fmt_text({**r, 'method': 'GET' if r['method'] == 'QUERY' else r['method'], 'rule': {'credential-set': 'cant-undo-verb'}.get(r['rule'], r['rule'])}) != r['text']]
    if bad: raise SystemExit(f'text path mismatch Node vs Python on {len(bad)} rows, first {bad[:5]}')
    ids = tok(texts, truncation=True, max_length=C.MAXLEN)['input_ids']
    mech = np.array([ORDER[r['class']] for r in rows]); meta = {'n': len(rows), 'hashes': hashes, 'smoke': '--smoke' in sys.argv, 'time_s': {}}
    for name, (path, _, T) in C.MODELS.items():
        t0 = time.time(); P = C.probs(path, ids, T); meta['time_s'][name] = round(time.time() - t0, 1); conf = P.max(1)
        pa = E.mode_a(rows, P); pb = guarded(P, E.MARGIN); Cf = F.configs(pa, pb, mech, conf)
        with open(os.path.join(wd, f'predictions-{name}.csv'), 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['id', 'provider', 'method', 'path', 'mech', 'mech_rule', 'tier', 'a_letter', 'b_letter', 'move', 'p_r', 'p_w', 'p_x', 'max_p', *F.CONFIGS])
            for i, r in enumerate(rows):
                mv = 'lowering' if pa[i] < mech[i] else 'raise' if pa[i] > mech[i] else 'keep'
                w.writerow([r['id'], r['provider'], r['method'], r['path'], r['class'], r['rule'], TIER.get(r['jev_tier'], 'none'), LABELS[pa[i]], LABELS[pb[i]], mv,
                            *[f'{P[i, k]:.6f}' for k in range(3)], f'{conf[i]:.6f}', *[('ask' if Cf[k][1][i] else LABELS[Cf[k][0][i]]) for k in F.CONFIGS]])
        print(f'{name}: predicted {len(rows)} rows in {meta["time_s"][name]}s, T={T}')
    json.dump(meta, open(os.path.join(wd, 'predict-meta.json'), 'w'), indent=1)
    print('truth never opened')

if __name__ == '__main__': main()
