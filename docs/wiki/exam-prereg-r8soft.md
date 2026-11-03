# Pre-registration: one-time M0 exam, MiniLM r8soft

Written 2026-11-03, before any exam truth is read by any rwxlite code. The exam
(`~/PycharmProjects/rwxmap/data/exam-2026-09-22/labelled.csv`, D128) is scored
exactly once with the configurations below. Nothing here may be changed after
the results are seen; a rerun is allowed only to fix a crash or a row-join bug,
and must be recorded.

## Model

- Base: sentence-transformers/all-MiniLM-L6-v2 with a 3-way head, fine-tuned as round 8 (soft targets, alpha 0.7), 1 epoch, step 2740.
- Checkpoint: `data/train/ckpt-r8soft/final/`
  - `model.safetensors` sha256 `974dff016a03f79868c498dff50fd11c70669e975e7284e881950f11bd6af3ae`
  - `tokenizer.json` sha256 `79ea220416a57ca8acdf069d71875d5d2ddadef66021aeb6c120a7c546c04344`
  - `config.json` sha256 `cb168cc5ded04c15fb9d3d899445b8f8575d5ba78c189560e8655d69f533df10`
- Code state: rwxlite m0 at f1b8a2b (this file is the next commit).
- Precision: fp32 on CPU, local. (int8 is not part of this scoring.)
- Calibration: temperature T = 0.844 (fit on val, `data/train/tune-cuts-r8soft-results.json`); calibrated p = softmax(log(clip(p, 1e-12, 1)) / T), as `temp_apply` in `train/tune_cuts.py`. Order of classes: r, w, x.

## Input text

`fmt_text` in `train/common.py`, unchanged:
`lean: <mech letter> <mech rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>`
(HTML stripped, whitespace collapsed, operationId cut at 120, summary at 200, description at 400 chars, empty fields omitted). Tokenised with the checkpoint tokenizer, max_len 128, dynamic padding.
Mechanical letter, rule and Jev tier for each exam row come from rwxmap `classifyRow` / `needsJev` (via `node_modules/rwxmap`), run on the exam's method, path, operationId, summary, description only. Exam operations are not deduplicated or filtered: all 4,279 rows are scored.

## Cuts and margin (all fixed, taken from the code's own choice on ALL v3 tuning data, calibrated p)

Verified against `data/train/tune-cuts-r8soft-results.json` (`calibrated.mode_a.cutsOnAllData` and `calibrated.mode_b_guarded.marginSweepAllData`). Not per-fold LOVO values.

Mode (a): mechanical stays in charge; the model makes only the one-step tier moves. With px = p(x), ch = p(w) + p(x):
- lower tier, mechanical x, px < 0.30: POST and ch < 0.40 gives r; every other lowered row gives w.
- raise-wx tier, mechanical w, px >= 0.15: gives x.
- raise-get tier, mechanical r, ch >= 0.05: gives w.
- narrow credential rule (`cred_hit` in `train/common.py`, non-GET, operationId / summary / path): forces x. Applied last, over every row.
- DELETE (tier none, mechanical x) and all other tier-none rows keep the mechanical letter.

Mode (b): standalone guarded argmax, margin 0.6 (`guarded` in `train/tune_cuts.py`, two passes: a lower class must beat the best higher class by more than the margin, else it steps up). No mechanical override, no credential rule. Margin 0.6 is the all-data choice: the largest exact (93.9%) subject to total too-loose (77 rows) no worse than mechanical's 77; margin 0.5 gives 109 loose rows and fails the budget. Per-fold LOVO margins were 0.6 in 18 of 23 folds (0.7 in 4, 0.9 in 1).

## Configurations scored (8)

Mode (a) and mode (b), each with ask threshold none / 0.7 / 0.9 / 0.95. Confidence = max calibrated p over r, w, x (for every row, including DELETE and tier-none rows). A row with confidence < threshold becomes "ask" and is not answered. "none" answers every row.

## GO / NO-GO

Mode (a), ask threshold none: exact >= 91% AND too loose <= 0.5% (PRD, M0 bar; 0.5% of 4,279 is 21 rows, so 21 or fewer too-loose rows passes, 22 fails). Every other configuration is reported for information only; mode (b) has no bar.

## Truth and scoring

- Truth is the `truth_class` column, as `m0/mechanical.mjs --sanity` and rwxmap use it (r < w < x). The `ruled` column is not applied. Rows are joined by `row_id`; the join must be 1:1 over 4,279 rows or the run stops.
- Exact: pred == truth. Too loose: pred < truth in r < w < x order (the guard lets through something it should have held back). Too tight: pred > truth.
- Metrics per configuration, on answered rows: exact / too loose / too tight as % and rows; answered % (and rows); asks (rows) and how many of those asked rows would have been too loose. Reported overall, by method, by tier (lower / raise-wx / raise-get / none), and by provider.
- Reference lines: mechanical alone (re-scored here with the same truth, expected 82.3 / 0.8 / 16.9, 34 loose rows per rwxlite's earlier re-score) and mechanical + Jev (rwxmap, 93.0 / 0.5 / 6.5, overall only; no per-row Jev answers are used or available here).

## Process

1. This file is committed alone.
2. Inputs and predictions are produced by code that never opens the truth column: `m0/exam-inputs.mjs` (reads only row_id, provider, method, path, operationId, summary, description) and `train/exam_score.py predict`. Output `data/exam-r8soft/predictions.csv`.
3. `train/exam_score.py score` joins truth once and writes `data/exam-r8soft/results.json`.
4. Findings entry in `docs/wiki/findings.md`. Any tweak suggested by the results needs a fresh exam, never this one.
