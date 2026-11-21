"""Round 16 final labels: combine the cascade into one row per op_id (r15/label_final.py rules, pass 2 dropped by user ruling 2026-11-21).
  data/r16/scratch/venv/bin/python -I r16/label_final.py
Rule (r15/label_final.py:48-58): agree3 row (mech + R13 + bge agree) -> the agreed letter, weight 1.0; contested row -> Sonnet's first-pass letter,
weight 1.0 for sure/likely, 0.3 for unsure (r15 gave likely 1.0 too; r15's 0.3 went to Opus-disagreeing rows, here no second pass). Holdout (400) excluded.
Dev rows (part=dev, 4,475) go to a separate file and are never training rows. D141 / tighten-only: no merge step is needed in r16, the Sonnet brief carries
the rulings (BRIEF.md) and nothing is lowered afterwards (r15 needed r15/r15_revert_lowers.py only because its D141 pass ran after the cascade).
Not added here: the 60k old replay, exam #7 mistakes, the 396 r15 re-check rows.
Inputs: data/r16/labels/opinions-r16.parquet, disagree-sample-400.csv, sonnet/out/{chunk,dev}-*.csv.
Outputs (data/r16/labels/final/): final-labels-r16.{parquet,csv.gz} (train, 299,600), final-labels-r16-dev.{parquet,csv.gz} (dev, 4,475), SHA256SUMS, summary.md, report.json."""
import csv, glob, hashlib, json, os
import pandas as pd
csv.field_size_limit(10**9)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); L = os.path.join(ROOT, 'data', 'r16', 'labels'); O = os.path.join(L, 'final'); os.makedirs(O, exist_ok=True)
RK = {'r': 0, 'w': 1, 'x': 2}
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
d = pd.read_parquet(os.path.join(L, 'opinions-r16.parquet')); assert d.op_id.is_unique and len(d) == 304475
hold = set(pd.read_csv(os.path.join(L, 'disagree-sample-400.csv')).op_id); assert len(hold) == 400 and set(d.op_id[d.batch == 'holdout']) == hold
son = {}
for f in sorted(glob.glob(os.path.join(L, 'sonnet', 'out', '*.csv'))):
    for r in csv.DictReader(open(f, newline='', encoding='utf-8')):
        assert r['letter'] in RK and r['confidence'] in ('sure', 'likely', 'unsure') and r['op_id'] not in son; son[r['op_id']] = r
need = set(d.op_id[d.batch.isin(['sonnet', 'dev_sonnet'])]); assert set(son) == need and len(son) == 44983, 'Sonnet outputs differ from the contested non-holdout rows'
recs = []
for r in d[d.batch != 'holdout'].itertuples(index=False):
    if r.agree_all:
        assert r.bge_letter == r.r13_letter_modea == r.mech_letter; lab, src, sl, sc, w = r.bge_letter, 'agree3', '', '', 1.0
    else:
        s = son[r.op_id]; lab, src, sl, sc = s['letter'], 'sonnet', s['letter'], s['confidence']; w = 0.3 if sc == 'unsure' else 1.0
    recs.append(dict(op_id=r.op_id, label=lab, label_source=src, sonnet_confidence=sc, weight=w, part=r.part, bge_letter=r.bge_letter, r13_letter=r.r13_letter_modea, mech_letter=r.mech_letter,
                     disagreement_type=r.disagreement_type, method=r.method, path=r.path, operationId=r.operationId, summary=r.summary, description=r.description, source=r.source, vendor_id=r.vendor_id, vendor_kind=r.vendor_kind))
out = pd.DataFrame(recs); tr = out[out.part == 'pick'].reset_index(drop=True); dv = out[out.part == 'dev'].reset_index(drop=True)
assert len(tr) == 299600 and len(dv) == 4475 and not (set(tr.op_id) & hold) and not (set(tr.op_id) & set(dv.op_id))
for n, g in (('final-labels-r16', tr), ('final-labels-r16-dev', dv)):
    g.to_parquet(os.path.join(O, n + '.parquet'), index=False); g.to_csv(os.path.join(O, n + '.csv.gz'), index=False)
sums = {f: sha(os.path.join(O, f)) for f in sorted(os.listdir(O)) if f.startswith('final-labels')}
open(os.path.join(O, 'SHA256SUMS'), 'w').write(''.join(f'{h}  {f}\n' for f, h in sums.items()))
def tab(g):
    return {'rows': len(g), 'by_letter': g.label.value_counts().to_dict(), 'by_source': g.label_source.value_counts().to_dict(), 'by_weight': {str(k): int(v) for k, v in g.weight.value_counts().items()},
            'sonnet_by_confidence': g[g.label_source == 'sonnet'].sonnet_confidence.value_counts().to_dict(), 'weight_total': round(float(g.weight.sum()), 1),
            'letter_by_source': {s: x.label.value_counts().to_dict() for s, x in g.groupby('label_source')}}
rep = {'train': tab(tr), 'dev': tab(dv), 'holdout_excluded': 400, 'sha256': sums}
json.dump(rep, open(os.path.join(O, 'report.json'), 'w'), indent=1)
def block(t, g):
    r = tab(g); lines = [f'## {t}: {r["rows"]:,} rows', '', f'- By letter: ' + ', '.join(f'{k} {v:,}' for k, v in sorted(r['by_letter'].items())),
                         '- By source: ' + ', '.join(f'{k} {v:,}' for k, v in r['by_source'].items()), '- By weight: ' + ', '.join(f'{k} {v:,}' for k, v in sorted(r['by_weight'].items())) + f' (total {r["weight_total"]:,})',
                         '- Sonnet rows by confidence: ' + ', '.join(f'{k} {v:,}' for k, v in r['sonnet_by_confidence'].items()),
                         '- Letter by source: ' + '; '.join(f'{s}: ' + ', '.join(f'{k} {v:,}' for k, v in sorted(m.items())) for s, m in r['letter_by_source'].items()), '']
    return '\n'.join(lines)
md = ['# Round 16 final labels', '', 'Rule: agree3 rows take the agreed letter (weight 1.0); contested rows take Sonnet first-pass letter (sure/likely 1.0, unsure 0.3). No second pass, no Opus. Holdout (400) excluded. Made by `r16/label_final.py`.', '',
      block('Train (pick)', tr), block('Dev (separate, never trained on)', dv),
      '## Not yet in this file', '', '- 60k old replay, exam #7 mistakes and the 396 r15 re-check rows are added in the next step (pending a user decision); they would be appended as new rows with their own label_source.',
      '- The 400 holdout rows have no truth column yet (blind review pending), so the label check is not scored.', '', '## SHA256', '', *[f'- `{h}`  {f}' for f, h in sums.items()], '']
open(os.path.join(O, 'summary.md'), 'w').write('\n'.join(md)); print('\n'.join(md))
