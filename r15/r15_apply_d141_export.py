"""Apply rwxmap's export-v4-d141 labels to the round 13 parquets (docs/wiki/prereg-r15.md section 3.4). Deterministic, stops on any assertion.
  python3 r15/r15_apply_d141_export.py [EXPORT_DIR]      # writes data/round13-d141/{train,val,v3eval}.parquet + SHA256SUMS (gitignored)
Reads data/round13/{train,val,v3eval}.parquet (sha256 asserted) and EXPORT_DIR/export-v4-d141.csv, changed-train.csv, changed-val.csv (sha256 and row counts asserted; default
~/PycharmProjects/rwxmap/data/export-v4-d141-2026-11-19, read-only). Checks label_v4 == the stored round 13 label for every id. train and val: label and y become label_d141, and train gets a `d141_changed` column (0/1)
that r15/r15_assemble.py uses (soft target of a changed row = one-hot of the new label, then drops the column). v3eval is copied unchanged (its labels are its own; only its lean prefix is swapped by the assembler).
The lean prefix is NOT touched here: r15_assemble.py takes it from the export (R15_LEAN_CSV)."""
import os, sys, hashlib
import pandas as pd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
EXP = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/PycharmProjects/rwxmap/data/export-v4-d141-2026-11-19')
SHA = {'export-v4-d141.csv': '8d802cf42d56fbcf050102fb854a958696bf59abdeca1a43fe6c88bcdc53034f', 'changed-train.csv': '11e048ff6acb00be10f3461cf9b01ea1266b3a2da7c5992dbf68b8e9356b0ee2', 'changed-val.csv': 'f567ea00f7bad0932570570b0811a3f920b25e03cabfd71950166d370b52acfb'}
IN = {'train': '91808a87cf24ac9c70f4d5b8f26fe68341ca9836606ce30a3e86273fce129aa5', 'val': '580a1141e6ee416b4ff2b445c749fc95b60bcdbddd04d0bbdd0464196ff840d1', 'v3eval': '7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad'}
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
for n, h in SHA.items(): assert sha(os.path.join(EXP, n)) == h, f'{n} sha256 differs'
for n, h in IN.items(): assert sha(os.path.join(ROOT, 'data/round13', n + '.parquet')) == h, f'round13 {n} sha256 differs'
x = pd.read_csv(os.path.join(EXP, 'export-v4-d141.csv'), keep_default_na=False).set_index('id')
assert len(x) == 106848 and (x.split == 'train').sum() == 102668 and (x.split == 'val').sum() == 4180 and x.changed.sum() == 232
assert len(pd.read_csv(os.path.join(EXP, 'changed-train.csv'))) == 226 and len(pd.read_csv(os.path.join(EXP, 'changed-val.csv'))) == 6
OUT = os.path.join(ROOT, 'data', 'round13-d141'); os.makedirs(OUT, exist_ok=True); Y = {'r': 0, 'w': 1, 'x': 2}
for n in ('train', 'val', 'v3eval'):
    d = pd.read_parquet(os.path.join(ROOT, 'data/round13', n + '.parquet'))
    if n != 'v3eval':
        e = x.loc[d.id]; assert (e.split.values == n).all() and (e.label_v4.values == d.label.values).all(), f'{n}: label_v4 differs from the stored round 13 label'
        assert ((e.label_d141.values != e.label_v4.values) == (e.changed.values == 1)).all()
        d['label'] = e.label_d141.values; d['y'] = d.label.map(Y).astype('int64').values
        if n == 'train': d['d141_changed'] = e.changed.values.astype('int64')
    d.to_parquet(os.path.join(OUT, n + '.parquet'), index=False)
with open(os.path.join(OUT, 'SHA256SUMS'), 'w') as f:
    for n in ('train', 'val', 'v3eval'): f.write(f'{sha(os.path.join(OUT, n + ".parquet"))}  {n}.parquet\n')
print(open(os.path.join(OUT, 'SHA256SUMS')).read())
