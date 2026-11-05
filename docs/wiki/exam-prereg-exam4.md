# Pre-registration: shared clean exam #4, rwxlite side (D135 next-model gate), candidate r11

**Status: DRAFT until committed; FROZEN when this file and the code listed below are committed, before any prediction exists.** Nothing has been predicted on exam #4:
no model was run on its ops, `truth.csv` was not opened or looked for, and the code below was tested only on exam #3 data (burned) and on its own refusals.
rwxmap's side is `docs/wiki/exam-prereg-exam4.md` in rwxmap, commit `5f48f16` (draft; it freezes when its CANDIDATE ADDENDUM is filled from section 3 here and its truth sha256 is written in).

The exam answers one question (D135): may r11 replace 0.2.0 as the model rwxmap ships? Two models, same rows, no tuning on exam #4.

**Run order:** this prereg + code committed -> addendum agreed with rwxmap -> inputs + predict (no truth) -> prediction-file sha256s committed -> truth shared -> score once.

## 1. Inputs

- rwxmap commit `1a1cc38` (inputs frozen), `data/exam4-2026-11-04/ops.csv`, sha256 `e9836ff2f9e8288e3721f97506ed666b871a3486f7b781c544b5234a0b5da0b4` (verified at that commit with `git show 1a1cc38:data/exam4-2026-11-04/ops.csv | sha256sum`), 1505 operations, ids `ex4-0001` .. `ex4-1505`, plus `sources.json` (specs are each vendor's own official OpenAPI).
- Vendors (provider: rows): permit.io 263, immich.app 279, polar.sh 190, goharbor.io 203, zulip.com 161, chatwoot.com 157, render.com 252 = 1505.
- Leakage check is rwxmap's (provider/vendor fields and registrable domains, `poc/exam4-shortlist/`); it cannot show a vendor's text was never in rwxlite's data under another name. Round 11 trained on exam #3 rows; none of these seven vendors is among them.
- `inputs.jsonl` is built from `ops.csv` by the shipped text path, reading no truth:

```
mkdir -p /tmp/rwxmap-exam4 && git -C /home/hamr/PycharmProjects/rwxmap archive <RWXMAP_REF> src package.json | tar -x -C /tmp/rwxmap-exam4
RWXMAP_DIR=/tmp/rwxmap-exam4 RWXMAP_REF=<RWXMAP_REF> node m0/exam4-inputs.mjs \
  /home/hamr/PycharmProjects/rwxmap/data/exam4-2026-11-04/ops.csv data/exam4
```

  `<RWXMAP_REF>` = the rwxmap commit that holds the filled addendum (the same one passed to rwxmap's `--rwxmap-ref`); written to `data/exam4/rwxmap-ref.txt`. `m0/exam4-inputs.mjs` is a guarded wrapper around the unchanged `m0/exam3-inputs.mjs` (rwxmap `classifyRow`/`needsJev`, model text from `src/text.js` `formatText`, QUERY read as GET, `credential-set` read as `cant-undo-verb`). It refuses unless the `ops.csv` sha256 is the one above, the out-dir is `data/exam4`, and `inputs.jsonl` does not exist yet.

## 2. Models

Class order r, w, x; confidence = max calibrated p; batch 1 (the int8 file's p depends on batch neighbours; 0.2.1 fixes `answerMany`, the Python path is batch 1 either way). Model strings and T are read from the manifests and checked against this table by `train/exam4_common.py` before any run.

Baseline = the published v0.2.0 release set (tag `v0.2.0`, commit `6c47fec6734e666462164025674b55e8323d5b86`; local copy `data/m1/release/`, which equals the GitHub release assets and rwxmap's baseline table). Note: exam #3 read the stale `data/m1/manifest-fp32.json` (version 0.1.0, string `rwxlite-0.1.0+8503b655`); exam #4 uses the release `manifest-exact.json` (`rwxlite-0.2.0+8503b655`), which is what rwxmap checks.

| file | 0.2.0 baseline sha256 | r11 candidate sha256 |
|---|---|---|
| manifest.json (int8-pc) | `10407b787fae2cadc318780a8c4ad171dc07af1389129c284bfd85c54f6b38bc` | `ff1ed6f12d7e6d237a96be2e600fa0da3438fd9a085801092b453df829cd052c` |
| manifest-exact.json (fp32) | `a484251cd4daf9c6fc7c8d2cb3f4a43f0cbdd6f4447d2c9ff65721a2f767b774` | `65e84b7697f725bac41550afd001aefe532ad2dd2ed1ce41ca6a349138244a80` |
| model-int8-pc.onnx | `8ad0a182b37237adc819bda2c03c01f0cb0e40afc2b20bdacb06193cd62a8844` | `adc6e6c130f8ba1716fa6b31e1ddce27e4b8eea8c76b336b8c1d53efdf3ea3e2` |
| model-fp32.onnx | `8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b` | `252f31811a1a9316cea0c6fd3404f3674c9e253613604fcc46a5832377e43bf6` |
| vocab.txt | `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` | `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` |

These five files are the "five" rwxmap's scorer hashes per model (two manifests, two models, vocab). Files: baseline `data/m1/release/`, candidate `data/m1-r11/` (`data/` is gitignored; copied by path).

| name | model string | T | role |
|---|---|---|---|
| `v020-fp32` | `rwxlite-0.2.0+8503b655` | 0.844 | baseline, **gate** (mode a, rwxmap's default) |
| `r11-fp32` | `rwxlite-0.3.0+252f3181` | 0.843 | candidate, **gate** |
| `v020-int8pc` | `rwxlite-0.2.0+8ad0a182` | 0.844 | information |
| `r11-int8pc` | `rwxlite-0.3.0+adc6e6c1` | 0.843 | information |

- r11 training checkpoint `model.safetensors` sha256 `cf6255a1a73415a20b9e9f3a5d6d2ccd34259c0b71762cb0895043507ff0e62b` (`data/m1-r11/export-sha.json`); T 0.843 is r11's val refit and is carried in both r11 manifests (`temperature`); 0.2.0 manifests carry none (0.844 default).
- **PLACEHOLDER FLAG.** The r11 model strings and manifest hashes carry version `0.3.0`, written into the manifests as a placeholder before a release version was decided. The `+sha8` parts are fixed by the model files and cannot change. If the version changes (e.g. to 0.2.2), the two r11 manifests are regenerated, their sha256s and both model strings change, and this table, section 3 and rwxmap's addendum must be re-agreed BEFORE any prediction. `package.json` on `dev` is `0.2.1`; a candidate package ref must have `package.json` version equal to the manifests' version (`loadAnswerer` builds the model string from `manifest.version`, rwxmap's package range comes from the tag's minor line).

## 3. Candidate package ref and tag (PROPOSED, nothing created)

Not yet existing; to be fixed with rwxmap when its CANDIDATE ADDENDUM is filled. Proposal:
- rwxlite package ref: a commit on `dev` (to be created by the user, not by this change) whose `src/` equals `dev` at `95b83c5` (0.2.1 fix + manifest `temperature`), with `package.json` version `0.3.0` and the CHANGELOG updated. **pending until that commit exists.**
- tag rwxmap would pin: `v0.3.0` (**PROPOSED, not created**; rwxmap scores with `RWXLITE_TAG` changed to it in a scratch copy, so no tag is needed for the exam itself).
- manifest/model hashes and strings: section 2, unless the version changes (flag above).
- rwxmap's command (its prereg): `--cand-ref <ref> --cand-tag v0.3.0 --cand-models /home/hamr/PycharmProjects/rwxlite/data/m1-r11` with the five `--cand-file` hashes from the r11 column above, `--cand-model-fp32 rwxlite-0.3.0+252f3181 --cand-model-int8 rwxlite-0.3.0+adc6e6c1`.

## 4. Predict (no truth)

```
RWXMAP_DIR=... RWXMAP_REF=... node m0/exam4-inputs.mjs <ops.csv> data/exam4          # section 1
(cd train && ../.venv/bin/python exam4_predict.py ../data/exam4)
node m0/exam4-parity.mjs data/exam4
(cd data/exam4 && sha256sum inputs.jsonl predictions-*.csv p-*.jsonl) > docs/wiki/exam-prereg-exam4-predictions.sha256   # committed BEFORE truth
```

- `train/exam4_predict.py`: refuses unless all five files per model match section 2 (including manifests and the model strings), checks Node text equals Python `fmt_text`, requires `inputs.jsonl` = exactly `ex4-0001..ex4-1505`, runs onnxruntime CPU batch 1, never opens truth, opens outputs with exclusive create (refuses to overwrite). `--smoke` works only in a directory named `*smoke*` that is not `data/exam4`.
- Outputs in `data/exam4/`: `inputs.jsonl`, `predictions-{v020,r11}-{fp32,int8pc}.csv` (all `exam_fresh.CONFIGS` incl. `GONOGO_lba097`, `a_none`, `mechanical`), `p-<name>.jsonl` (rwxmap parity shape: `id, model, pIsX, pChanges`, T applied), `predict-meta.json`, `rwxmap-ref.txt`, `ops-sha256.txt`.
- `m0/exam4-parity.mjs data/exam4` (rwxlite's own `loadAnswerer` check, model string equal, max |dp| <= 1e-6, reads no truth) must exit 0.
- The sha256 of every file above is committed to `docs/wiki/exam-prereg-exam4-predictions.sha256` and to this file ("Predictions frozen") before truth is opened; the scorer verifies them.

## 5. Scoring

Truth: rwxmap commit `fcc1ae8`, `truth.csv`, 1505 rows, sha256 **`b76c55fb30235726489574c90425c2c53b8343467e2fd918603952d135313c45`** (hard-coded in `train/exam4_common.py` as the only accepted truth). rwxlite has NOT seen it.

```
.venv/bin/python train/exam4_score.py data/exam4 <path-to-truth.csv>
```

- Refuses unless the truth file's sha256 equals the constant (no command-line override, no `--smoke` bypass: `--smoke` refuses the real truth and the real work-dir), the prediction files match the committed sha256 list, ids are `ex4-0001..1505`, the join is 1:1, and `results.json` does not exist yet (scored once). Smoke writes only `results-smoke.json` / `score-smoke.log`.
- Configs and cuts identical to exam #3 (`exam_score.mode_a`, `exam_fresh.configs/piles`; mode a: lower 0.30, r cut 0.40, raise-wx 0.15, raise-get 0.05, narrow credential rule forces x last; margin 0.6). Reported for all four models: `GONOGO_lba097`, `a_none` (mode a, never asks), `mechanical`, and the rest of `CONFIGS`. Per config right / too loose / too tight / asked; per vendor and per method for `GONOGO_lba097` and `a_none`; every too-loose row listed with its type (`loweredWrongly`, `keepMechLoose`, `raiseStillLoose`); the rows where `v020-fp32` and `r11-fp32` differ in `a_none`.
- Denominator for the gate: all 1505 rows (`a_none` asks nothing, asserted). Letters as rwxmap: argmax of x = pIsX, w = pChanges - pIsX, r = 1 - pChanges. rwxmap scores the same rows with its real CLI and reports beside ours; the two scorers can differ on int8 near cut-offs (rwxmap D133 parity finding), which is why int8 is information only.

## 6. Decision rule

**D135 gate (user ruling 2026-11-04, "better or same, no regression"; same as rwxmap's prereg), mode a fp32, `a_none`, integer counts on 1505 rows:** r11 replaces 0.2.0 only if `r11-fp32 too loose <= v020-fp32 too loose` AND `r11-fp32 exact >= v020-fp32 exact`. A tie on either passes that half. Too tight is reported beside it and is not part of it. rwxmap's scorer and ours must agree on the verdict; a disagreement stops the exam until explained (not decided by picking one).

Reported, not gating: D133 mode a bar vs mechanical for all four models (too loose <= mech's AND exact >= mech's + 76 rows, ceil(0.05 x 1505)); `GONOGO_lba097` with exam #3's rwxlite bars (too loose <= 0.5% of answered, exact >= 91%, asked <= 15%); b95 and mode c only on rwxmap's side.

- **GO:** rwxlite tells rwxmap the gate passed on both scorers; the user rules (D135). If the user releases: bump `package.json`/manifests to the agreed version, rebuild the release assets with `m1/release-assets.mjs`, tag, publish; the shipped manifests must hash-match section 2 or the exam is not about the shipped model. Findings entry with numbers and too-loose rows.
- **NO-GO:** 0.2.0 stays pinned in rwxmap; r11 is not released. Findings entry with numbers, too-loose rows and the differing rows. No fix on these rows.
- **Noise caveat (as exam #3):** this is a paired comparison on 1505 rows with about a dozen to two dozen leaks in play. A one- or two-row gap is inside reader and labeller noise (labels are model labellers plus the user's ruling, not ground truth) and is decided by the written rule (ties pass), not by a significance test. A GO is not proof of improvement; a NO-GO by one row is not proof of regression. Exam #3 had r10 at 15 too loose vs 13 for 0.2.0 fp32 with 47 rows differing.

## 7. Not allowed once predictions exist

- Any change of model file, manifest, T, cut, config, margin, text format, tokenizer, batch size, onnxruntime settings, code logic or the gate. No re-running predict to "see if it changes" (the scripts refuse to overwrite; deleting outputs to get around that is a breach).
- Opening, copying, diffing or searching `truth.csv` (or any labeller file) before the prediction sha256s are committed; scoring against any truth whose sha256 differs; editing the scorer's truth constant after predictions exist.
- Scoring more than once. A rerun only for a crash or a row-join bug, recorded in the findings with the reason, same predictions.
- Choosing the candidate, T, config or gate after seeing any number; adding or dropping a model; reading int8 as the gate.
- Anything a result suggests (a cut, a rule, a retrain) needs a new exam with new vendors. After both sides have scored, exam #4 is burned (rwxmap's burn rule) and may be used for training.

## Frozen code (committed with this file)

`m0/exam4-inputs.mjs` (wraps unchanged `m0/exam3-inputs.mjs`), `train/exam4_common.py`, `train/exam4_predict.py`, `train/exam4_score.py`, `m0/exam4-parity.mjs`. Imported unchanged: `train/exam_score.py`, `train/exam_fresh.py`, `train/common.py`, `train/tune_cuts.py`. Hardening vs exam #3 (ledger items): the truth sha256 is a constant in code, not an argument; `--smoke` cannot touch real outputs (separate work-dir rule, separate file names, refuses the real truth/ops); predict and score never overwrite; model strings come from the published v0.2.0 manifests (the stale 0.1.0 string is gone). Tested only on exam #3 data in `data/exam4-smoke/` (gitignored): inputs equal `data/exam3/inputs.jsonl` byte for byte, four models predicted (model strings as in section 2), the score pipeline ran under `--smoke`, and the real-mode refusals (wrong truth sha, wrong work-dir, existing outputs, wrong ops sha) fired.

## Predictions frozen

Commit `3ce3332`, file `docs/wiki/exam-prereg-exam4-predictions.sha256`:

```
048a666591d910194d6fc67350d025bbdef6eb86638285c7ca5ced672f35903a  inputs.jsonl
4de119d114375bce135a31943907e0063595a38c23532379799333bf89b65d95  predictions-r11-fp32.csv
d5ef9d607ef3927cbb269e87e240bc148aab2227b879e89a6a3bfed63ed84d1c  predictions-r11-int8pc.csv
ad0a78330292e1dc04a0ee8a561c1bbb9ffdc12e9bb13e336ff8c7910b79885e  predictions-v020-fp32.csv
bb2f8741400f42ef1540a02a8e6aaf2892262df29b16e92ab1d866e54ef791e2  predictions-v020-int8pc.csv
c4e0a0a3328ef3a3be76efd8795c432864222d7b8b406967244e59d145ce6074  p-r11-fp32.jsonl
1de7bb7872fcb4d9216e19f0cd04605a33cfd4c2342de1b27d3ad6e5b87d7a15  p-r11-int8pc.jsonl
bb205199c04791a31f30183b6146cbe85a9a375afc4282eb2cff961eaeed2d07  p-v020-fp32.jsonl
56cc74f7d00c4711317e1533425f55f6a2cfc46ec036fcce694bca7d782466cc  p-v020-int8pc.jsonl
```

## Result (2026-11-05)

Scored once, `train/exam4_score.py` exit 0. Truth sha256 verified `b76c55fb...3c45`; rwxmap ref `9f58894`. Truth and our score output are kept in gitignored `data/exam4/` (`truth.csv`, `score.out`).

Our scorer, `a_none` (offline mode a, never asks), fp32, right / too loose / too tight:

| run | right | too loose | too tight |
|---|---|---|---|
| 0.2.0 fp32 | 1448 | 24 | 33 |
| r11 fp32 | 1447 | 22 | 36 |
| mechanical | 1262 | 21 | 222 |

int8 (info): 0.2.0 1450/24/31, r11 1447/23/35. `GONOGO_lba097` (info): v020-fp32 1378/9/33, asked 85; r11-fp32 1384/10/36, asked 75.

Our D135 on `a_none`: loose ok, exact 1447 < 1448, **NO-GO**. 17 fp32 rows differ: the candidate is right on 8 the base missed and wrong on 9 the base had; loose: base 3 (ex4-0183, ex4-1303, ex4-1505), candidate 1 (ex4-0365).

rwxmap's scorer (real CLI `secondPass` at `9f58894`, exit 0): mechanical 1262/21/222 (identical to ours). Base 0.2.0 fp32 1391 right / 16 too loose / 98 too tight (sent 602, raised 6, lowered 125, kept 369, undecided 102 scored x). Candidate r11 1393/18/94 (raised 5, lowered 130, kept 376, undecided 91). D135: loose 18 > 16 FAIL, exact 1393 >= 1391 OK, **NO-GO**. D133 vs mechanical passes for all four in rwxmap's run. 12 fp32 rows differ in their run; the candidate's new leaks are ex4-0813 (permit POST .../envs/{env_id}/copy), ex4-1115 and ex4-1318 (render PUT .../secret-files, truth x); it fixes ex4-0335 (harbor PUT /system/purgeaudit).

Verdict: both scorers NO-GO, for opposite reasons. Agreed with rwxmap: a model's score belongs to the rule it ships with, so the D135 gate number is rwxmap's CLI. 0.2.0 stays; the v0.3.0 tag (`77e6bb4`) is a candidate that was not released. Exam #4 is burned for both sides (may now be used for training).

Prereg error, stated plainly: this prereg named `a_none` as the gate config. `a_none` is not the shipped second pass (it sends every row to the model, uses tier cuts, never asks or reviews), so its numbers are not the product's. Next exam: the gate config is rwxmap's CLI `secondPass` (or replay the p-jsonl through rwxmap's CLI).
