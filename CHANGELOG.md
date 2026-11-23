# Changelog

All notable changes to rwxlite are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] - 2026-11-23

Round 16 (R16) is the new default model.

- New default weights, trained on 360,536 labelled operations: about 300,000 new ones from about 32,000 vendors the earlier models never saw, about 60,000 re-used from earlier sets, and a few hundred more (rows rwxmap re-ruled, exam #7's mistakes, check rows). A teacher is distilled into the MiniLM student. Calibration temperature is 1.7029 (it was 1.3832), so the probabilities change and a decision cut tuned on 0.4.x values does not carry over. Callers should re-check their cut.
- Model strings: `rwxlite-0.5.0+fac72395` (int8, the default `manifest.json`) and `rwxlite-0.5.0+82fa50c3` (fp32, `manifest-exact.json`).
- Measured once on exam #8 (1,821 operations from 6 APIs no model had seen, official numbers from rwxmap's own CLI), right / too loose / too tight: mode a (rules plus model at the 0.90 cut) 1,653 / 60 / 108 against 0.4.0 at 1,631 / 65 / 125. Verdict GO under D142. These are the fp32 model's figures; the int8 default was not scored on this exam. Exam #8 is now used up: no tuning or gating on it again.
- The API is unchanged. Text format 1 is kept; the manifest keys are the same as in 0.4.0.
- The model files are not in the npm package. They are on the GitHub release `v0.5.0`: `manifest.json`, `manifest-exact.json`, `model-int8-pc.onnx`, `model-fp32.onnx` and `vocab.txt`.

### Added
- `m1/release-assets.mjs` has an `r16` mode, and `m1/export_r16.py` and `m1/manifest-r16.mjs` export the R16 model, with the same checks as the `r15` mode.
- Round 16 research tooling: data collection, labelling, teacher and student training scripts, pre-registrations and recorded results. None of this ships in the npm package.

### Changed
- README and `docs/wiki/guide.md` are updated to 0.5.0 (badge, exam #8 results, the `v0.5.0` download, 0.5.0 sha256 values, worked examples re-run on the int8 model, calibration temperature note, training-set description).

## [0.4.0] - 2026-11-20

Round 15 (R15) is the new default model.

- New default weights, trained on 302,211 labelled operations that include about 21,600 vendors the earlier models never saw (round 15 data, one label base). A bge teacher is distilled into the MiniLM student. Calibration temperature is 1.3832 (it was 0.991463), so the probabilities change and a decision cut tuned on 0.3.x values does not carry over. Callers should re-check their cut.
- Model strings: `rwxlite-0.4.0+470708b0` (int8, the default `manifest.json`) and `rwxlite-0.4.0+4608f470` (fp32, `manifest-exact.json`).
- Measured once on exam #7 (1,579 operations, official numbers from rwxmap's own CLI), right / too loose / too tight: mode a (rules plus model at the 0.90 cut) 1432 / 66 / 81 against 0.3.1 at 1431 / 68 / 80; mode b85 1449 / 39 / 91 against 1447 / 54 / 78. Verdict GO under D142. Exam #7 is now used up: no tuning or gating on it again.
- The API is unchanged. Text format 1 is kept; the manifest keys are the same as in 0.3.1. rwxmap adopts this release by its own decision; nothing here changes what rwxmap runs until it does.

### Added
- `m1/release-assets.mjs` has an `r15` mode (`node m1/release-assets.mjs [out-dir] r15 [--skip-version-check]`): copies the five R15 files byte for byte from `data/m1-r15/`, checks each sha256, and checks package.json's version equals the manifests' version.
- 0.4.0 integration tests for the R15 model strings and answers.
- Training tooling: `train/finetune.py` takes `--row_weight` (a per-row loss weight column), `--teacher` (soft targets from a teacher model, for distillation) and `--base` (the starting model, default all-MiniLM-L6-v2, recipe unchanged); a teacher-probabilities script; `m1/export_r15.py`, `m1/manifest-r15.mjs`, `m1/r15-train.sh`, and the exam #7 scoring and round 14 comparison scripts. Round 15 data pipelines (GitHub, SwaggerHub, cloud and catalogue sources), labelling scripts, pre-registrations and recorded results are in the repo. None of this ships in the npm package.

### Changed
- README and `docs/wiki/guide.md` are updated to 0.4.0 (badge, worked examples re-run on the int8 model, calibration temperature note); the PRD and `docs/wiki/findings.md` record round 14 (bge-base teacher, closed) and round 15.
- README: the "How well it does" section shows one test, rwxmap's exam #7 (modes a and b, rules only; 1,579 operations from 6 APIs no model had seen); exams #5 and #6 stay in `docs/wiki/findings.md`. The README opens with an ASCII logo.

## [0.3.1] - 2026-11-07

Round 13 (R13) is the new default model.

- New default weights, trained on about 102,700 labelled operations (round 13 data). Labels follow the widened x: giving or widening access is x, narrowing is w, an unclear access change is x by doubt. Creating keys or tokens, access-widening toggles, webhooks to outside URLs, creating a login user and adding a member are x.
- Calibration temperature is 0.991463 (it was 0.844). The probabilities change, so a decision cut that was tuned on 0.2.x values does not carry over. Callers should re-check their cut.
- Model strings: `rwxlite-0.3.1+984714f0` (int8, the default `manifest.json`) and `rwxlite-0.3.1+bbe1997d` (fp32, `manifest-exact.json`).
- Measured on exam #5 (1,443 operations from 7 vendors no model had seen), right / too loose / too tight: on its own, int8 1,280 / 64 / 99 and fp32 1,283 / 64 / 96; with rwxmap at its 0.90 cut, 1,269 / 40 / 134 (fp32, the model rwxmap runs; int8 at that cut was not measured).
- The API is unchanged. The manifest keys `temperature` and `textFormat` are additive. Text format 2 is shipped switched off: no published model uses it. rwxmap adopts this release by its own decision; nothing here changes what rwxmap runs until it does.

### Added
- `docs/wiki/guide.md`: a guide for calling rwxlite directly (the request shape, why every request needs a lean, loading the model, reading the answer). The README is shorter and links to it with absolute links so they work on npm, and its example uses a lean rule the model was trained on.
- Exam #5 tooling and records (pre-registration, frozen inputs and prediction sha256s, leakage check, recorded result: R13 did not clear the standalone pass bar on exact; the numbers are in the note above, and whether to run R13 is rwxmap's call), and round 13 training and val-pick scripts. Vendor-label scripts (github parser, join, mechanical and predict) for an independent check of the teacher labels. None of this ships in the npm package.
- Manifest `textFormat` (1 or 2, default 1; anything else throws). `loadAnswerer` reads it via the new `manifestTextFormat`, validated by `checkTextFormat`. Format 2 is format 1 plus one `hint: access` segment right after the lean, on operations that `accessHint(state)` flags (grants or widens access, creates a key or token, webhook to an outside URL, creates a login user, adds a member). `formatText(state, lean, format)` takes the format (default 1); `accessHint`, `checkTextFormat` and `manifestTextFormat` are exported. Output for 0.2.0 manifests (no `textFormat`) is unchanged byte for byte. No shipped model uses format 2; whether it ships is undecided (PRD, Round 13).
- Round 10 model build (`data/m1-r10`, int8-pc `093c908d`, fp32 `8514ddcc`, T 0.858), not released (exam #3 NO-GO; 0.2.0 stays the published model). Manifests built by `m1/manifest-r10.mjs`, the release set by `m1/release-assets.mjs data/m1-r10/release r10`.
- `m1/release-assets.mjs` has an `r13` mode (`node m1/release-assets.mjs [out-dir] r13 [--skip-version-check]`): copies the five R13 files byte for byte, checks each sha256 against the exam #5 values, and checks package.json's version equals the manifests' version.
- `train/exam3_predict.py` writes one JSONL per model (`id`, `model`, `pIsX`, `pChanges`, T applied) for parity checks against `loadAnswerer`.

### Changed
- `loadAnswerer` reads the calibration `temperature` from the manifest (finite number > 0, else it throws); a manifest without it uses 0.844, so 0.2.0 manifests behave as before. `calibrated(L, T)` and `new Answerer({..., temperature})` take it; `checkTemperature` and `manifestTemperature` are exported.
- `package.json`: the `author` field is removed and the `description` is rewritten in plain words (a small local classifier that says whether an API operation reads, writes or can't be taken back).

## [0.2.1] - 2026-11-05

Fixes `answerMany` batch-dependence. The model weights are unchanged byte for byte, but release v0.2.1 carries them with manifests that say version 0.2.1, so the model string is `rwxlite-0.2.1+<sha8>` (int8 `+8ad0a182`, fp32 `+8503b655`) because it comes from `manifest.version`; consumers pinned to release v0.2.0 (for example rwxmap) keep `rwxlite-0.2.0+<sha8>`.

### Fixed
- `answerMany` runs one row per `session.run`, so an answer no longer depends on its batch neighbours: fp32 is identical, and int8 (dynamic quantisation takes its activation scale over the whole padded batch) gives the same answer for a row whatever it is batched with. Measured by rwxmap on exam #3: fp32 identical on every row; int8 mode a 1192/15/170 -> 1189/16/172.

## [0.2.0] - 2026-11-04

M1: a local, Jev-shaped answerer in Node. Package default model file: int8 per-channel; option "exact": fp32. rwxmap's own default is the exact fp32 model.

### Added
- Round 10 plan (PRD, "Round 10 (planned)"): rebuild leans from current rwxmap, hand-check two leak shapes (credential replace PUT/PATCH, 59 candidate rows; logout, 45 candidate rows; the pattern only finds candidates, and only rows judged x by BRIEF-v3 change; R1/R2 failed, so no pattern relabel; the known false positives files.com PATCH /api_key and okta .../pages/sign-out/customized stay as they are), add the fresh-exam and round 9 labels, QUERY augmentation. `m1/round10-shapes.py` counts the shapes. Measured: the shipped model on the 32 `credential-set` ops (a rule name it never saw) lowers 12 of 32 below x, 3 at p >= 0.97 (findings). No training yet.
- Publish workflow (`.github/workflows/publish.yml`, manual, npm trusted publishing, adopter type-check gate, and a release-before-publish gate: it fails unless GitHub release `v<version>` carries `manifest.json`, `manifest-exact.json`, `vocab.txt` and both models, no asset is zero-size, and `manifest.json`'s version equals `package.json`'s); package public as `rwxlite` (`private` removed, `files` = src, types, README, LICENSE, CHANGELOG; `prepack` builds the types). Models stay on GitHub releases.
- `answerMany` slots are plain JSON data, `{model, answers}` or `{model, error}`; `answer()` still throws on no answer. Tests cover the JSON round trip, p in [0,1], and `changes >= isX` at extreme logits.
- `test/fixtures/decision.jsonl` and `test/decision.test.js`: 949 fresh-exam ops (isX, changes, expected `{letter, asked}`) reproduce the written decision rule exactly (mode a tier cuts, credential rule, lowering asked under max p 0.97).
- `test/fixtures/credential-set.jsonl`: the 32 `credential-set` ops with the model's answers before the guard (x 20, w 12, 3 lowerings at max p >= 0.97) and after it (x 32, 0 lowerings), for rwxmap's `secondPass` floor check on identical rows.
- README badge row (CI, version, classifier, license).
- `m1/release-assets.mjs`: builds the GitHub release set (`manifest.json`, `manifest-exact.json`, `model-int8-pc.onnx`, `model-fp32.onnx`, `vocab.txt`) into `data/m1/release/`, recomputes every sha256, prints the `gh release upload` command; uploads nothing.
- `src/`: `loadAnswerer`, `Answerer` (`answer`, `answerMany`), `checkRequest`, `calibrated`, `modelString`, plus Node ports of the text format and the BERT tokenizer (0 mismatches: token ids on 102,781 texts, text format on 5,228). Request is Jev's `{state, model, questions}` plus `lean: {class, rule}` (proposed for D133); answer is `{model, answers: {isX: {noul}, changes: {noul}}}`. Bad input throws, a bad slot in `answerMany` is isolated, a model failure fails every slot, files are sha256-checked against `manifest.json`.
- `m1/`: ONNX export (`export_onnx.py`), quantisation variants and their comparison on both burned exams (`variants.py`), manifest writer (`manifest.mjs`), Node benchmark (`bench.mjs`), corpus parity check (`check-corpus.mjs`).
- Tests (`npm test`, hermetic, no model needed; one integration test runs the real model when `data/m1` has it) and `.github/workflows/ci.yml` (typecheck, build:types, test).
- `types/` generated by `npm run build:types`; `exports` and `engines` (node >= 22) in `package.json`.

### Changed
- The text step reads lean rule `credential-set` (rwxmap D131) as `cant-undo-verb` (temporary guard until round 10 trains on the name); on its 32 ops: argmax x on 32 of 32, 0 lowerings at p >= 0.97 (was 12 w, 3).
- The text step reads HTTP `QUERY` (RFC 10008, rwxmap D134) as `GET`; measured on 383 fresh-exam GET rows relabelled QUERY: 1 argmax change, 1 row across 0.97.
- `clean()` now ports Python `html.unescape` exactly: the full HTML5 entity table (generated `src/entities.js`, `m1/gen-entities.py`), names without `;` with longest-prefix matching, invalid numeric references. Fixture `test/fixtures/unescape.jsonl` (`m1/make-unescape-fixture.py`).
- `loadAnswerer` default `threads` is now `Math.min(4, os.availableParallelism())` (was 1). The bench default stays 1.
- `m1/manifest.mjs` defaults to `model-int8-pc.onnx`; `data/m1/manifest.json` points at it.
- `rwxmap` is no longer an npm dependency; `m0/mechanical.mjs` and `m0/exam-inputs.mjs` load it from `../rwxmap` or `$RWXMAP_DIR`.
- `m0/fresh-exam-build.py` is now executable in git (mode 100755).

### Measured
- fp32 ONNX matches torch to 1e-6; default int8 (23.0 MB) changes 12 of 949 fresh-exam decisions' argmax and moves up to 0.42 in p; per-channel int8 (23.1 MB) cuts that about 3x; fp16 (45.6 MB) changes nothing. Node mean latency at batch 1, 1 thread: 18.8 ms int8, 25.9 ms fp32. Threads on a quiet 4-core i3-8100T, batch 1: int8 per-channel 15.5 / 9.2 / 6.9 ms mean at 1 / 2 / 4 threads (p95 31.0 / 17.8 / 13.1); fp32 at 4 threads 7.9. Details in the PRD ("M1 result") and `docs/wiki/findings.md`.
- Docs: PRD decision-rule section now records rwxmap's rule comparison (466cda1, secondPass kept, D133) next to rwxlite's measured rule; README no longer says rwxmap must apply it.

## [0.1.0] - 2026-11-03

Module 0 (M0): a research release. It measures whether a small local classifier
can say whether an API operation reads (r), writes (w) or can't be taken back (x).
**No model is shipped in this release.** Weights stay local; the int8 export and
the Node runtime are M1. Both exams below were NO-GO.

### Added
- Mechanical pass over all APIs.guru operations (rwxmap's `classifyRow`), about
  123,340 operations from 2,529 specs (`m0/mechanical.mjs`).
- Jev labelling pipeline: per-method questions, resumable, hard spend guard under
  the $50 cap (`m0/jev-label.mjs`, `m0/run-step2.sh`, `m0/questions/`). Includes the
  POST "changes" pass, two-step lowering of POST rows and a narrow credential rule.
- Label gates, each used once on a blind 600-row sample with two labellers and a
  95% bar. Gate-1 failed at 90.8% (all too tight, mostly reads labelled as POST).
  Gate-2, after the rule changes, passed at 96.5% (`m0/gate-sample.mjs`,
  `m0/gate-score.mjs`, `m0/parity.mjs`, `data/gate-*`).
- Training pipeline in `train/`: TF-IDF + logistic regression baseline, MiniLM
  (all-MiniLM-L6-v2) first run and r6 with own-cut tuning, then r8 soft targets
  with temperature calibration (T = 0.844) and cuts tuned leave-one-vendor-out.
- Measurements on practice rows (5,716 v3 tuning rows, not exams): round 8 abstain
  evaluation, round 9b fallback-to-mechanical (ASK, MECH, MECH-THEN-ASK), and round
  9c lowering flag (accept a lowering only at p >= 0.97: 93.2% right, 0.41% too
  loose, 9.6% asked).
- Round 9 hand labels: 1,200 training rows of the two failing shapes labelled
  blind by two labellers (98.8% agreement). Training labels were too loose on 32
  rows (2.7%); the retrain was skipped.
- One-time exam on rwxmap's 2026-09-22 exam (4,279 rows: cloudflare, pagerduty,
  sentry): **NO-GO**. Exact 95.91% passes; too loose 0.84% (36 rows) fails the
  0.5% line.
- Fresh exam on coolify, workos, lago and resend (949 ops, pinned specs, labels
  frozen before any prediction, pre-registered): **NO-GO by one row**. 92.57% right
  (pass), 7.8% asked (pass), 5 too loose = 0.57% (fail; the line is 0.5%, 4 rows).
  The lowering flag worked (no lowering was too loose); the 5 misses are 3
  credential upserts and 2 logout GETs raised one step short of x.
- Gate 3 and gate 4 samples, labels and rulings built for rwxmap (F2 and
  take-backs exams).
- PRD flow: rwxmap adapter, three engines, the two-question call and the lowering
  flag, with the fresh-exam rule set to LOWER-BAR-ASK at 0.97.
- Apache-2.0 licence, README, secret-scanning config that skips vendor spec
  copies, and `.gitignore` entries for local `.claude/` and `.litectx/`.
- Docs: PRD contract, `docs/wiki/findings.md`, classifier-training wiki and the
  two exam pre-registrations.

### Changed
- README abstain row now follows the contract rule.
- Exam pre-registration addendum: code not pinned, rule switched after labels
  were seen. PRD label-gate bar wording clarified.

### Fixed
- `m0/fresh-exam-build.py` now runs directly and on a fresh clone: `env -S`
  shebang, repo root taken from the script path instead of a hardcoded home dir,
  rebuild from the committed pinned specs (sha256-checked) when the local download
  dir is absent, and the corpus-overlap check is skipped without the local corpus.
  Output `ops.csv` is byte-identical either way.
- Dropped a dead line in `train/exam_fresh.py`.
