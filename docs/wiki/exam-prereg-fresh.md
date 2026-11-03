# Pre-registration: fresh exam 2026-11-03, MiniLM r8soft (LOWER-BAR-ASK 0.97)

Written 2026-11-03, before `data/exam-2026-11-03-fresh/truth.csv` is opened by any rwxlite code. The exam
(949 operations: coolify.io 321, workos.com 269, getlago.com 217, resend.com 142; `data/exam-2026-11-03-fresh/ops.csv`,
labels frozen in `truth.csv`) is scored exactly once with the configurations below. Nothing here may be changed
after the results are seen. A rerun is allowed only to fix a crash or a row-join bug and must be recorded.
No prediction of any kind has been made on these rows at the time of writing.

## Model

- Base MiniLM-L6-v2 with 3-way head, round 8 soft targets (r8soft), fp32, CPU.
- Checkpoint `data/train/ckpt-r8soft/final/`, `model.safetensors` sha256
  `974dff016a03f79868c498dff50fd11c70669e975e7284e881950f11bd6af3ae` (verified identical to the previous exam).
- Calibration: temperature T = 0.844 (`data/train/tune-cuts-r8soft-results.json`), `temp_apply` in `train/tune_cuts.py`. Class order r, w, x.
- Confidence = max calibrated p.

## Input

`fmt_text` in `train/common.py`, unchanged:
`lean: <mech letter> <mech rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>`
(HTML stripped, whitespace collapsed, operationId cut at 120, summary 200, description 400; empty fields omitted; tokenizer max_len 128).
Mechanical letter, rule and Jev tier per row: rwxmap `classifyRow` / `needsJev` via `m0/exam-inputs.mjs` (run in fresh mode) over method, path,
operationId, summary, description of ops.csv. All 949 rows are scored, no filtering.

## Cuts (fixed; all-data choice from the tuning results, verified against `tune-cuts-r8soft-results.json` `calibrated.mode_a.cutsOnAllData`)

Mode (a), `mode_a` in `train/exam_score.py`: lower 0.30, r cut 0.40 (POST lowered rows go to r when p(w)+p(x) < 0.40, else w), raise-wx 0.15,
raise-get 0.05, narrow credential rule forces x (applied last), DELETE and tier-none rows keep the mechanical letter.
Mode (b): guarded argmax, margin 0.6.

## Definitions

Order r < w < x. With mechanical letter M and mode (a) letter A: LOWERING = A < M; RAISE = A > M; KEEP = A = M.
Four piles, every row in exactly one: right, too loose (answer stricter-ranked below truth), too tight, asked. They must sum to 949.
Percentages of answered rows for right / too loose / too tight; asked is % of all 949 rows; also each pile as % of all rows.

## GO / NO-GO

Mode (a), **LOWER-BAR-ASK at 0.97**, as rule 5 in `train/lowerflag.py`: a lowering is accepted only if max calibrated p >= 0.97, otherwise "ask". Raises and keeps are trusted.
**PASS** = too loose <= 0.5% of answered rows AND exact >= 91% of answered rows AND asked <= 15% of all rows. Otherwise NO-GO.

## Reported only (no bar)

1. mode (a), no bar (`a_none`)
2. MECH-THEN-ASK at 0.95 (`train/fallback.py` `cell`)
3. ask on every lowering (rule 3, FLAG-ALL-LOWER)
4. LOWER-BAR-ASK at 0.95 + MECH-THEN-ASK@0.95 on non-lowerings (rule 6 at 0.95)
5. LOWER-BAR-ASK at 0.95 and at 0.99
6. mode (b), no bar
7. mechanical alone

## Metrics

For each configuration: the four piles; what the asks held (would-have-been right / loose / tight, judged on the unasked mode (a) letter);
lowering / raise / keep counts with right / loose / tight (mode (a) letter, no bar); per vendor and per method breakdown of the GO/NO-GO config;
the remaining too-loose rows of the GO/NO-GO config listed by type: lowered wrongly (accepted lowering, still loose), mechanical letter kept and loose (keep), raise still loose.
Truth = `truth.csv` label (r/w/x), joined by id, 1:1 over 949 rows or the run stops.

## Process

1. This file is committed alone.
2. `node m0/exam-inputs.mjs fresh` then `python3 train/exam_fresh.py predict` (never opens truth.csv) -> `data/exam-fresh-r8soft/predictions.csv`.
3. `python3 train/exam_fresh.py score` joins truth once -> `results.json`, `score.log`.
4. Findings entry; any tweak suggested by the results needs yet another fresh exam.


## Addendum (2026-11-03, after scoring; the rules above are unchanged)

Two facts a reader of this pre-registration should know, from /self-review:
- This file pinned the model (sha256), calibration and cuts, but not the code. `train/exam_fresh.py` and the fresh mode of `m0/exam-inputs.mjs` were first committed in the scoring commit 402fea0, together with the predictions, 2 minutes after this file (0caa381). So "scored once with this code" cannot be checked from git alone; it rests on the commit order and the worker's report. From now on a pre-registration commits the predict and score code with it, before any prediction.
- The go/no-go rule was changed from MECH-THEN-ASK 0.95 to LOWER-BAR-ASK 0.97 by the user after the exam labels and the 15 rulings were frozen (312b23a), so after the user had seen the answer labels, but before any model or mechanical prediction on these rows existed. The change was decided on practice rows only (round 9c). The result (NO-GO by one row) is the same under both rules: MECH-THEN-ASK 0.95 scored 6 too loose (0.64%).
