# Round 16 exam #8 candidate addendum (rwxlite 0.5.0)

Written 2026-11-23, after the full student passed the dev floor (prereg `docs/product/prereg-r16-small-runs.md` section 17). Exam #8 is the ship gate; this file only names the candidate. Nothing here is a tag, a push or a publish.

## The eight values for rwxmap's CANDIDATE ADDENDUM

| field | value |
|---|---|
| rwxlite package version | `0.5.0` |
| rwxlite package ref (commit in the rwxlite repo) | `67f732c241227cf7d682f0bf881130a0b8f6732a` (the commit whose tree has the 0.5.0 code: export scripts, `package.json` and `package-lock.json` at 0.5.0; the next commit only adds this file) |
| rwxlite tag / version | `v0.5.0` (NOT created, NOT pushed) |
| model string (fp32) | `rwxlite-0.5.0+82fa50c3` |
| model-fp32.onnx sha256 | `82fa50c394b1ef274e02ae9355bed56a6405fb001bd7694a6dd78acdc574065e` |
| manifest-exact.json sha256 (fp32) | `b576eb72a442d074c669f4cfd92b178ddf571d295d067db0b5e7891b5e67fd8e` |
| vocab.txt sha256 | `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` (same as 0.4.0) |
| rwxlite prereg commit(s) | section 16 `87f501d83d06e1f162866095197c8b9d21a4edfc`; prediction shas `0eb4230de57877de1100359e7e3b346606cd481f`; section 17 `a9eb49a50f0f071e8653d63268959de76a6b09ab` |

Model dir (holds `manifest-exact.json`, `model-fp32.onnx`, `vocab.txt`, plus the int8 files): `/home/hamr/PycharmProjects/rwxlite/data/m1-r16/`

## Other values

- Checkpoint `data/r16/full/student/ckpt-r16-full-student/final`, `model.safetensors` sha256 `699bbf1a50eb51117175c902fe001db32601fb89792a06a67666e34abc0ece0c` (checked by the export).
- Temperature `1.7029162450278692` (the student's val-fitted T, section 17), `textFormat` 1, written in the manifests.
- All five release files (`data/m1-r16/`; `node m1/release-assets.mjs <out-dir> r16` re-checks them):
  - `manifest.json` (int8-pc) `9ecefd18633d01cf71702cff2d49b2d62bdbaf5f20c244d5ea2dc5a8dbc15476`, model string `rwxlite-0.5.0+fac72395`
  - `manifest-exact.json` (fp32) `b576eb72a442d074c669f4cfd92b178ddf571d295d067db0b5e7891b5e67fd8e`
  - `model-int8-pc.onnx` `fac7239505c086e01afbb3c342b743c17242ae1affcfaa51e20f1295c0b2f6e3` (23,126,902 bytes)
  - `model-fp32.onnx` `82fa50c394b1ef274e02ae9355bed56a6405fb001bd7694a6dd78acdc574065e` (90,973,979 bytes)
  - `vocab.txt` `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3`
- Layout equals 0.4.0: same five file names, same manifest fields (`version`, `modelFile`, `model`, `temperature`, `textFormat`, `files`), same loader (`src/answerer.js`, unchanged).
- `data/m1-r15/` (shipped 0.4.0) was not touched; its five files were sha-checked before and after.
- Scripts: `m1/export_r16.py` (env `R16_CKPT_SHA`, `R16_T`), `m1/manifest-r16.mjs`, `m1/release-assets.mjs` `r16` mode. Run order: `export`, `rows`, `parity`, then `node m1/manifest-r16.mjs write 0.5.0` and `parity`.

## Export checks (all passed)

- ONNX fp32 vs PyTorch fp32, batch 1, 598 val rows (every 7th): max |dp| 5.9e-7, 0 letter differences. Int8-pc vs fp32 (information only): max |dp| 0.111, 1 letter difference.
- Node `loadAnswerer` on the new dir, manifest T, batch 1, vs Python ORT p on the same 598 rows: fp32 max |dp| 3.0e-16, int8-pc 2.4e-16, 0 letter differences, 0 text differences.
- Dev-v3, all 4,475 rows, Node fp32 (`manifest-exact.json`), batch 1, text from `mech.jsonl` rebuilt through `formatText` (all 4,475 equal) and `answer()` (equals the runner logits to 2.7e-16): logits vs the PyTorch logits of section 17, max difference 8.2e-6, 0 argmax differences. Scored with `r16/score_dev.py --dev-set v3`, real secondPass (rwxmap 1c25be1), cut 0.90, same T: (b) exact 3,093 / too loose 41 / too tight 152; (a) 4,252 / 50 / 173. The score blocks, including the confusion tables, equal section 17.1 exactly.
- `npm test`: 40 tests, 40 pass, 0 fail, 0 skipped.
