# Pre-registration (DRAFT): shared exam #3, MiniLM round 10 (r10)

**Status: DRAFT, written 2026-11-04. Not yet frozen.** It freezes when the "Truth source and rwxmap side" section is filled in with rwxmap and
this file is committed alone with the code listed below. Until then nothing about exam #3 has been built or predicted on:
`truth.csv` for exam #3 does not exist in this repo, `ops.csv` for exam #3 does not exist in this repo, and no model has been run on any
of its vendors. Round 10 (training, T refit, exports, parity) finished before this draft (PRD, "Round 10", hard constraint).

## Vendors

clerk, neon, supabase, mux, netbird, ory, novu (rwxmap's spares; untouched by every rwxlite training, tuning and exam set; checked: 0 rows with
these names in the r10 train, val or v3eval provider/vendor columns, 92,864 / 4,180 / 5,716 rows, and the round-10 assembly asserts `no_exam3_vendor`). Row counts: TBD with rwxmap (from their ops file).

## Frozen code (committed with this file, before any prediction)

- `m0/exam3-inputs.mjs <ops.csv> <work-dir>`: lean from rwxmap `classifyRow` / `needsJev` (rwxmap HEAD sha is written to `rwxmap-head.txt`; the pinned sha is TBD with rwxmap), and the model text from the shipped path `src/text.js` `formatText` (QUERY read as GET, `credential-set` read as `cant-undo-verb`). Reads no truth.
- `train/exam3_predict.py <work-dir>`: refuses to run unless every model file and `vocab.txt` matches the sha256 below; checks the Node text equals Python `fmt_text`; runs onnxruntime CPU, batch 1; never opens truth.
- `train/exam3_score.py <work-dir> <truth.csv>`: opens truth once; 1:1 join or it stops.
- Unchanged and imported: `train/exam_score.py` (`mode_a`, cuts, margin), `train/exam_fresh.py` (`configs`, `piles`), `train/common.py`, `train/tune_cuts.py` (`guarded`).
- Why Python scoring and not the Node answerer: rwxlite returns p only and never decides a letter; the cuts, tiers and pile logic that produced every earlier number live in the Python files above. The Node side supplies the exact shipped input text. Node and Python onnxruntime agree to 1e-7 on the same file (findings, "M1") and the r10 files are re-checked below.

## Models (frozen)

| name | file | sha256 | T |
|---|---|---|---|
| r10-int8pc (candidate default) | `data/m1-r10/model-int8-pc.onnx` | `093c908d492d07121159287b5beadd3d4d75c403a4cde4f701ac918475be1173` | 0.858 |
| r10-fp32 | `data/m1-r10/model-fp32.onnx` | `8514ddccdafcda28ae468aced91673545c3c1d56201754e89a79dcb10ca61a26` | 0.858 |
| v020-int8pc (shipped 0.2.0, `rwxlite-0.2.0+8ad0a182`) | `data/m1/model-int8-pc.onnx` | `8ad0a182b37237adc819bda2c03c01f0cb0e40afc2b20bdacb06193cd62a8844` | 0.844 |
| v020-fp32 | `data/m1/model-fp32.onnx` | `8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b` | 0.844 |

- r10 checkpoint `data/train/ckpt-r10/final/model.safetensors` sha256 `28e5830356b84f3fada311811f6f382363a5fc37f5060e117f952575c5767512` (1 epoch, 2,902 steps, soft targets, same recipe as r8soft; val accuracy 97.32%).
- `vocab.txt` sha256 `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` for both (identical).
- r10 T = 0.858 (refit on the r10 val split, `temp_fit` in `train/tune_cuts.py`, 4,180 rows, raw 0.85775; the same function gives 0.8440 for r8soft on its val). The Node answerer has T = 0.844 compiled in; shipping r10 needs it to read T from the manifest. That is not part of this exam: the exam code applies T itself.
- Class order r, w, x; confidence = max calibrated p.

## Configs scored

All configs of `exam_fresh.CONFIGS` for every model above, with the cuts of the fresh exam (mode (a): lower 0.30, r cut 0.40, raise-wx 0.15, raise-get 0.05, narrow credential rule forces x last; mode (b): guarded argmax, margin 0.6). Per config: right / too loose / too tight / asked (summing to n), per vendor and per method; every too-loose row listed with its type (lowered wrongly, mechanical kept and loose, raise still loose). Which config is THE gate config, and whether rwxmap's own decision rule (secondPass, D133) is scored by rwxmap on our p's: TBD with rwxmap. Default if nothing else is agreed: `GONOGO_lba097` (LOWER-BAR-ASK at 0.97).

## Gate

Too loose <= 0.5% of answered rows (set by Jev; the fresh exam failed it at 5/875 = 0.57%). Confirm the source and the exact denominator (answered rows of the gate config, as on the fresh exam) with rwxmap before freezing. The secondary bars of the fresh exam (exact >= 91% of answered, asked <= 15% of all) are reported with the gate; whether they stay bars is TBD with rwxmap. The gate is judged on r10; v020 is reported beside it and is the comparison, not a second chance.

## What counts as a rerun

Only a crash or a row-join bug, recorded in the findings with the reason. No change of model, T, cuts, config, code logic or text format after any prediction exists. Anything a result suggests needs a new exam with new vendors.

## Process

1. This file and the code above are committed together; rwxmap's section filled in; nothing predicted yet.
2. rwxmap supplies `ops.csv` (blind: id, provider, method, path, operationId, summary, description) and `truth.csv` (id, label) as agreed below. rwxlite never opens `truth.csv` before step 4.
3. `node m0/exam3-inputs.mjs ops.csv work/` then `python3 train/exam3_predict.py work/`.
4. `python3 train/exam3_score.py work/ truth.csv`, once. Findings entry with the numbers and the too-loose rows.

## Truth source and rwxmap side: TBD with rwxmap

Known fact (rwxmap, 2026-11-04): rwxmap's `NEVER_LOWER_RULES` blocks any lowering of a `credential-set` verdict regardless of the model, proved on rwxlite's earlier p's for the 32 credential-set ops (12 argmax w, 3 at p >= 0.97, 0 lowered). rwxlite's text alias (`credential-set` -> `cant-undo-verb`, `src/text.js`) is a second, independent guard that rwxlite needs when used alone; it does not hold up rwxmap's floor.

Open, to be answered by rwxmap; nothing below is filled in on their behalf:
- Who labels exam #3 and how (single labeller, two labellers plus rulings as on the fresh exam)? Is the label BRIEF the same BRIEF-v3 the fresh exam used?
- Truth freeze: when, and who holds `truth.csv` until step 4?
- Final vendor list and row counts; any vendor dropped for size or spec problems before freezing.
- rwxmap HEAD sha for the lean (`classifyRow`), to pin in `rwxmap-head.txt`.
- Gate config (rwxlite default `GONOGO_lba097`, or rwxmap's secondPass over our p's) and denominator for the 0.5%.
- Does rwxmap score its own pipeline on the same rows, and are results reported together?
- Which model files (int8-pc, fp32) count for the gate.
