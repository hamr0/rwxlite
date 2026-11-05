"""Round 11 practice/validation comparison: r11 vs r10 vs shipped 0.2.0 (r8soft). NOT a gate; exam #3 cannot score r11 (it is trained on it).
Imports common.py / tune_cuts.py unchanged. Uses the same metrics as round 10's scoring (common.v3_report: mechanical, a_cuts, a_argmax),
on probs as saved by training (raw, T=1) and temperature-calibrated with each model's own T (r8soft 0.844, r10 0.858, r11 0.843).
  .venv/bin/python train/r11_compare.py [R10_REPO]  -> data/m1-r11/compare.json + printed tables
R10_REPO (default /home/hamr/PycharmProjects/rwxlite) holds the read-only r8soft / r10 probs. r11 and r10 share val/v3eval byte-for-byte; r8soft's v3eval differs in 4 lean rows.
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, load_split, v3_report, mode_a_labels, score, LABELS
from tune_cuts import temp_fit, temp_apply

R = sys.argv[1] if len(sys.argv) > 1 else '/home/hamr/PycharmProjects/rwxlite'
MODELS = {  # name -> (T, val probs, v3eval probs, split dir)
    '0.2.0 (r8soft)': (0.844, f'{R}/data/train/probs-r8soft-val.npy', f'{R}/data/train/probs-r8soft-v3eval.npy', f'{R}/data/train'),
    'r10': (0.858, f'{R}/data/train/r10/probs-r10-val.npy', f'{R}/data/train/r10/probs-r10-v3eval.npy', f'{R}/data/train/r10'),
    'r11': (0.843, os.path.join(ROOT, 'data/train/probs-r11-val.npy'), os.path.join(ROOT, 'data/train/probs-r11-v3eval.npy'), os.path.join(ROOT, 'data/train')),
}
rd = lambda d, n: pd.read_parquet(os.path.join(d, n + '.parquet'))
res = {}
for name, (T, fv, fe, d) in MODELS.items():
    va, ev = rd(d, 'val'), rd(d, 'v3eval'); Pv, Pe = np.load(fv).astype(float), np.load(fe).astype(float)
    r = {'T': T, 'val_n': len(va), 'v3_n': len(ev), 'val_acc_pct': round(100 * float((Pv.argmax(1) == va.y.values).mean()), 2),
         'val_refit_T': round(float(temp_fit(Pv, va.y.values)), 4)}
    for cal in ('raw', 'cal'):
        pv, pe = (Pv, Pe) if cal == 'raw' else (temp_apply(Pv, T), temp_apply(Pe, T))
        r[f'v3eval_{cal}'] = v3_report(ev, pe)
        # val: truth is the round-6 label y (not a truth set); mode (a) on val against y
        yl = np.array([LABELS[i] for i in va.y.values])
        r[f'val_{cal}'] = {k: score(mode_a_labels(va, pv, k2), yl) for k, k2 in (('a_cuts', 'cuts'), ('a_argmax', 'argmax'))} | {'mechanical': score(va.mech.values, yl)}
        nll = -np.log(np.clip(pv[np.arange(len(va)), va.y.values], 1e-12, 1)).mean()
        r[f'val_{cal}']['nll'] = round(float(nll), 4)
    res[name] = r
json.dump(res, open(os.path.join(ROOT, 'data/m1-r11/compare.json'), 'w'), indent=1)
f = lambda s: f"{s['exact']:.1f} / {s['loose']:.1f} / {s['tight']:.1f}"
for cal in ('raw', 'cal'):
    print(f'\n### v3eval ({cal} probs), exact / too loose / too tight %, n=5716')
    print('| config | ' + ' | '.join(res) + ' |'); print('|---|' + '---|' * len(res))
    for cfg in ('mechanical', 'a_cuts', 'a_argmax'): print(f'| {cfg} | ' + ' | '.join(f(res[m][f'v3eval_{cal}'][cfg]['overall']) for m in res) + ' |')
    for cfg in ('a_cuts',):
        for mt in ('PUT', 'PATCH', 'POST', 'GET', 'DELETE'): print(f'| {cfg} {mt} | ' + ' | '.join(f(res[m][f'v3eval_{cal}'][cfg]['method_' + mt]) for m in res) + ' |')
    print(f'\n### val ({cal}), vs round-6 label y (not a truth set), n=4180')
    for cfg in ('mechanical', 'a_cuts', 'a_argmax'): print(f'| {cfg} | ' + ' | '.join(f(res[m][f'val_{cal}'][cfg]) for m in res) + ' |')
    print('| val NLL | ' + ' | '.join(str(res[m][f'val_{cal}']['nll']) for m in res) + ' |')
print('\nval acc %:', {m: res[m]['val_acc_pct'] for m in res}, ' refit T on own val:', {m: res[m]['val_refit_T'] for m in res})
