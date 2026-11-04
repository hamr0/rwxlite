# Pre-registration: shared exam #3, MiniLM round 10 (r10)

**Status: FROZEN, 2026-11-04.** This file is committed alone, with the code listed below, before any prediction exists. Until this commit nothing about
exam #3 had been built or predicted on: `truth.csv` for exam #3 does not exist in this repo and no model had been run on any of its vendors.
Round 10 (training, T refit, exports, parity) finished before this prereg (PRD, "Round 10", hard constraint). The rwxlite build ref is `fe374c0`
(0.3.0); the commits after it are docs only.

**Run order:** this prereg commit -> inputs + predict (no truth) -> prediction-file sha256s committed -> truth shared by rwxmap -> score once.
A rerun only for a crash or a row-join bug.

## Vendors

clerk, neon, supabase, mux, netbird, ory, novu (rwxmap's spares; untouched by every rwxlite training, tuning and exam set; checked: 0 rows with
these names in the r10 train, val or v3eval provider/vendor columns, 92,864 / 4,180 / 5,716 rows, and the round-10 assembly asserts `no_exam3_vendor`). Final list (all seven kept) and row counts, from rwxmap's `ops.csv`: clerk.com 263, neon.com 193, supabase.com 170, mux.com 192, netbird.io 231, ory.sh 179, novu.co 149; total 1377 rows. Methods: GET 574, POST 401, DELETE 197, PATCH 105, PUT 99, HEAD 1.

- `ops.csv`: `/home/hamr/PycharmProjects/rwxmap/data/exam3-2026-11-04/ops.csv`, sha256 `fff7afa983c7fc85e2073e5662c4c317c69e37a1dd92a04c7e5dc04ecf43d790`, rwxmap commit `93dc59c`.
- `truth.csv`: held by rwxmap, sha256 `929725d51397098b6f45d86a5a551e7f0c095875557a944c02e08930efdab3c0`; shared only after this prereg is committed.

## Frozen code (committed with this file, before any prediction)

- `m0/exam3-inputs.mjs <ops.csv> <work-dir>`: lean from rwxmap `classifyRow` / `needsJev` (rwxmap HEAD sha is written to `rwxmap-head.txt`; the pinned sha is rwxmap `46235eab7043fe69a4fea18e0ad77678a82123cb`, branch `feat/d133-rwxlite-engines`), and the model text from the shipped path `src/text.js` `formatText` (QUERY read as GET; `ops.csv` has no QUERY rows, `credential-set` read as `cant-undo-verb`). Reads no truth.
- `train/exam3_predict.py <work-dir>`: refuses to run unless every model file and `vocab.txt` matches the sha256 below; checks the Node text equals Python `fmt_text`; runs onnxruntime CPU, batch 1; never opens truth. Also writes the parity files `p-<model>.jsonl` (see "Parity file").
- `m0/exam3-parity.mjs <work-dir>`: checks those parity files against `loadAnswerer` (model string equal, max |dp| <= 1e-6) on the same rows.
- `train/exam3_score.py <work-dir> <truth.csv> <expected-sha256>`: hashes `truth.csv` and refuses to run unless it equals the sha256 rwxmap committed with its prereg (`--smoke` may skip the check); opens truth once; 1:1 join or it stops.
- Unchanged and imported: `train/exam_score.py` (`mode_a`, cuts, margin), `train/exam_fresh.py` (`configs`, `piles`), `train/common.py`, `train/tune_cuts.py` (`guarded`).
- Why Python scoring and not the Node answerer: rwxlite returns p only and never decides a letter; the cuts, tiers and pile logic that produced every earlier number live in the Python files above. The Node side supplies the exact shipped input text. Node and Python onnxruntime agree to 1e-7 on the same file (findings, "M1") and the r10 files are re-checked below.

## Models (frozen)

| name | file | sha256 | T |
|---|---|---|---|
| r10-int8pc (candidate default, `rwxlite-0.3.0+093c908d`) | `data/m1-r10/model-int8-pc.onnx` | `093c908d492d07121159287b5beadd3d4d75c403a4cde4f701ac918475be1173` | 0.858 |
| r10-fp32 (`rwxlite-0.3.0+8514ddcc`) | `data/m1-r10/model-fp32.onnx` | `8514ddccdafcda28ae468aced91673545c3c1d56201754e89a79dcb10ca61a26` | 0.858 |
| v020-int8pc (shipped 0.2.0, `rwxlite-0.2.0+8ad0a182`) | `data/m1/model-int8-pc.onnx` | `8ad0a182b37237adc819bda2c03c01f0cb0e40afc2b20bdacb06193cd62a8844` | 0.844 |
| v020-fp32 | `data/m1/model-fp32.onnx` | `8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b` | 0.844 |

- r10 checkpoint `data/train/ckpt-r10/final/model.safetensors` sha256 `28e5830356b84f3fada311811f6f382363a5fc37f5060e117f952575c5767512` (1 epoch, 2,902 steps, soft targets, same recipe as r8soft; val accuracy 97.32%).
- `vocab.txt` sha256 `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` for both (identical).
- r10 T = 0.858 (refit on the r10 val split, `temp_fit` in `train/tune_cuts.py`, 4,180 rows, raw 0.85775; the same function gives 0.8440 for r8soft on its val). The 0.3.0 build of `loadAnswerer` reads `temperature` from the manifest (0.844 when absent), so r10's manifests carry 0.858 and the Node answerer and the Python exam code apply the same T.
- Class order r, w, x; confidence = max calibrated p.

## Configs scored

All configs of `exam_fresh.CONFIGS` for every model above, with the cuts of the fresh exam (mode (a): lower 0.30, r cut 0.40, raise-wx 0.15, raise-get 0.05, narrow credential rule forces x last; mode (b): guarded argmax, margin 0.6). Per config: right / too loose / too tight / asked (summing to n), per vendor and per method; every too-loose row listed with its type (lowered wrongly, mechanical kept and loose, raise still loose). The rwxlite gate config is `GONOGO_lba097` (LOWER-BAR-ASK at 0.97); see "Gates".

## Gates

Two gates, both reported side by side, neither replacing the other.

- **rwxlite gate**: `GONOGO_lba097` on r10 int8-pc (the candidate default); r10 fp32 reported beside it. Too loose <= 0.5% of answered rows (set by Jev; the fresh exam failed it at 5/875 = 0.57%). The denominator is the answered rows of the gate config, as on the fresh exam. Secondary bars of the fresh exam (exact >= 91% of answered, asked <= 15% of all) are reported with it. v020 is reported beside r10 as the comparison, not a second chance.
- **rwxmap gate**: the D133 bars, scored by rwxmap's real `secondPass` / CLI loading r10 through `loadAnswerer({dir, threads})` from this branch's 0.3.0 build, on fp32 (rwxmap's default); int8-pc beside it. rwxmap also scores, on the same rows and reported beside ours: mechanical alone; mode a (mechanical then rwxlite r10; fp32 gate, int8-pc beside); mode b at confidence 95; mode c (mechanical then Jev). rwxmap's prereg is committed at `46235eab7043fe69a4fea18e0ad77678a82123cb` (branch `feat/d133-rwxlite-engines`): `docs/wiki/exam-prereg-exam3.md`, scorer `data/exam3-2026-11-04/score/` (in rwxmap).
- Letter for rwxmap: argmax of x = pIsX, w = pChanges - pIsX, r = 1 - pChanges.

## Parity file

`train/exam3_predict.py` writes `p-<model>.jsonl` per model (r10-fp32, r10-int8pc, and v020-fp32, v020-int8pc for reference): one line per row, keyed by the `id` of the shared `ops.csv`:
`{"id": "...", "model": "rwxlite-<semver>+<sha8>", "pIsX": p, "pChanges": p}`. T is applied (final probabilities). The script asserts `0 <= pIsX <= pChanges <= 1` and that `model` is exactly the string `loadAnswerer` reports for that model dir (rwxlite-0.3.0+093c908d, rwxlite-0.3.0+8514ddcc for r10). rwxmap compares its own `loadAnswerer` p's against this file at 1e-6 (max |dp| over both fields) and the model string by equality; any difference stops the exam until explained. `m0/exam3-parity.mjs` is rwxlite's own run of the same check.

## Delivery to rwxmap

- r10 files go by local path (`data/m1-r10/`: `manifest.json`, `manifest-exact.json`, `model-int8-pc.onnx`, `model-fp32.onnx`, `vocab.txt`), not through a pre-release. `data/` is gitignored, so they are copied from that directory.
- rwxmap installs the 0.3.0 build from this branch's git ref or a local `npm pack` tarball, and sha256-checks every file against the list rwxlite sends and the sha8 in each model string.
- `data/m1-r10/` stays unchanged until both sides have scored. The manifests are written once for 0.3.0 and not regenerated.

## What counts as a rerun

Only a crash or a row-join bug, recorded in the findings with the reason. No change of model, T, cuts, config, code logic or text format after any prediction exists. Anything a result suggests needs a new exam with new vendors.

## Process

1. This file and the code above are committed together (build ref `fe374c0`); rwxmap's section filled in; nothing predicted yet.
2. rwxmap supplies `ops.csv` (blind: id, provider, method, path, operationId, summary, description) and `truth.csv` (id, label) as agreed below. rwxlite never opens `truth.csv` before step 4.
3. `node m0/exam3-inputs.mjs ops.csv work/` then `python3 train/exam3_predict.py work/`.
4. Prediction-file sha256s are committed to this file ("Predictions frozen"). Then rwxmap shares `truth.csv`, and `python3 train/exam3_score.py work/ truth.csv 929725d51397098b6f45d86a5a551e7f0c095875557a944c02e08930efdab3c0`, once. Findings entry with the numbers and the too-loose rows.

## Truth source and rwxmap side

Ruled by rwxmap's user (2026-11-04):
- **Truth**: built by rwxmap from each vendor's official OpenAPI spec (not APIs.guru), repeated endpoints deduped. At least two blind labellers per row using BRIEF-v3 verbatim; rwxmap's user rules disagreements (as on the fresh exam).
- **Custody**: rwxmap holds `truth.csv`. rwxmap commits the ops file and the sha256 of `truth.csv` with its prereg. Truth is not opened for scoring until both preregs are committed; then it is shared with rwxlite, and `exam3_score.py` verifies its sha256 against rwxmap's committed hash before joining.
- **Vendors**: the seven above, final (see "Vendors").
- **Delivery**: see "Delivery to rwxmap".
- **rwxmap scoring**: same rows, reported beside ours (see "Gates").

Known fact (rwxmap, 2026-11-04): rwxmap's `NEVER_LOWER_RULES` blocks any lowering of a `credential-set` verdict regardless of the model, proved on rwxlite's earlier p's for the 32 credential-set ops (12 argmax w, 3 at p >= 0.97, 0 lowered). rwxlite's text alias (`credential-set` -> `cant-undo-verb`, `src/text.js`) is a second, independent guard that rwxlite needs when used alone, and r10 was trained on the alias text, so it stays.

Labelling (rwxmap, 2026-11-04): two blind labellers per row, BRIEF-v3 verbatim. Labellers A and B agreed on 1370 of 1377 rows (99.5%); rwxmap's user ruled the other 7. A scripted labeller-A pass on mux was rejected and mux was relabelled.

Secondary bars (exact >= 91% of answered, asked <= 15% of all) are reported with the rwxlite gate, as written under "Gates".

## Predictions frozen (2026-11-04)

Produced after the prereg commit `1cef41cbb9c1c529a0c14980b4e3a7b12f043955`, from rwxmap clone at `46235eab7043fe69a4fea18e0ad77678a82123cb` (`ops.csv` sha256 verified `fff7afa9...d790`), rwxlite build ref `fe374c0`, without truth. `data/exam3/`, 1377 rows, real run (not `--smoke`). `rwxmap-head.txt` = `46235eab7043fe69a4fea18e0ad77678a82123cb`.

Parity (`node m0/exam3-parity.mjs data/exam3`, exit 0): model strings equal, n=1377, max |dp| <= 1e-6 required:
- r10-int8pc `rwxlite-0.3.0+093c908d`: max |dp| 2.220e-16 OK
- r10-fp32 `rwxlite-0.3.0+8514ddcc`: max |dp| 2.220e-16 OK
- v020-int8pc `rwxlite-0.2.0+8ad0a182`: max |dp| 2.220e-16 OK
- v020-fp32 `rwxlite-0.1.0+8503b655`: max |dp| 2.220e-16 OK

sha256 of every file in `data/exam3/`:

```
25ac102d2493e9a8342ac0c82e8492a91d06a425d6d9865b5ebfac9545d1f50e  inputs.jsonl
1790edb8fce4e8ecd792fe99a1336394d2a4aa21e18d37d976c996cfaa9e4882  rwxmap-head.txt
fb374d424c7011570d39a6b124e30ac3f3ba746fa90895bbd24b15776bb2d2ab  p-r10-fp32.jsonl
bfb3cd9141d4d3191f5ac72291f900319014f6d38cf035da83bc7ea12479102e  p-r10-int8pc.jsonl
cc16eede63676c71f8ae0e40a1286b735493d2fd62199a7dd75d23a0aa32f95e  p-v020-fp32.jsonl
2521154d7822e23f3ff34e1ddc9d38e7d27c7dcec0a64716c9dbe4f2b55d5c8b  p-v020-int8pc.jsonl
09f369887ed71c7bddc8cc0b27a605154c349b66a1cf78cfa4e9a2719e712520  predictions-r10-fp32.csv
f5b6c46864edeedc1c7e465849531b71c5575a6dd917b846151943a3ba2af063  predictions-r10-int8pc.csv
a116a572132c0c29b88192e5afa8078474da512c69102cded5283978df08313d  predictions-v020-fp32.csv
ea1c4a3a5683ad49fcecf6d67564bdae58f3660dbd18b1975d5d38ec243f3fb6  predictions-v020-int8pc.csv
493a47d664e91c7bce6d87f4f1d78b826b492960cc5c7ca6d5b9b2eb4dd600fc  predict-meta.json
```

Next: rwxmap shares `truth.csv` (sha256 `929725d5...b3c0`); score once.
