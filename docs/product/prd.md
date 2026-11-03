# rwxlite — PRD

Status: contract, round 6 signed off. Date: 2026-11-03.

## Problem & goal

rwxmap labels every API operation r, w or x (read, write, execute).

Mechanical rules alone, on the 4279-operation exam (cloudflare, pagerduty, sentry):

| | exact | too loose | too tight |
|---|---|---|---|
| mechanical | 82.3% | 0.8% | 16.9% |
| mechanical + Jev | 93.0% | 0.5% | 6.5% |

A full Jev pass over the exam cost $0.31.

Jev is a hosted model (`api.typesafe.ai/v1/systemone`, model `jev-latest`). rwxmap asks it yes/no questions on three disjoint tier piles and reads back a probability p. Two costs:

- It bills per call.
- It sends spec text (method, path, operationId, summary, description) off the machine.

**Goal.** rwxlite is a small, local, quantized classifier that is a drop-in for Jev. It takes a Jev-shaped request `{state, model, questions}` and returns one-shot JSON `{p, model}` per question. It is free, offline, private and fast.

- Its own repo. Used with rwxmap, and open source on its own.
- Its p doubles as a confidence. A guardrail (bareguard) can turn low confidence into an "ask". API providers can use it to triage rows.
- The model only reports p. The gate decides.

## How it works in plain words

- Mechanical rules run first and stay in charge.
- rwxlite then answers the same three questions Jev answers, on the same piles. It may make only Jev's one-step moves:
  - jev-lower: x to w, on `floor-post` rows (question isX). Round 6: a two-step lower, x can drop to w OR r (see Round 6).
  - jev-raise-wx: w to x, on `method-floor` rows (question isX).
  - jev-raise-get: r to w, on `method` rows with class r (question changes).
- rwxlite tunes its own thresholds (see Thresholds). It does not reuse rwxmap's, because a threshold is valid only for the exact client and model it was swept on.
- The model sees method, path, operationId, summary and description, plus the mechanical letter and rule name (the "leaning"). That is two passes in one model, from one training run. No separate pre-train and fine-tune stages.
- Output is 3-way r/w/x with probabilities. isX = p(x). changes = p(w) + p(x).
- The same output gives a standalone classifier (mode b) for free.

## Decisions (signed off 2026-11-03)

- Mode (a) first: mechanical in charge, rwxlite as the Jev stand-in.
- Mode (b), standalone, is reported in module 0 but has no bar. The user would use it alone later only if it proves good enough. For now they trust mechanical more.
- One model, 3-way output, one training run.
- Quantization: post-training dynamic int8 on the ONNX export. This is the "Cactus idea". Cactus itself (a phone LLM runtime) is not used.
- Runtime: inside rwxmap's Node process, via onnxruntime-node.
- Training: HF transformers + PyTorch on the laptop CPU. Machine has 8 cores, 31 GB RAM, no NVIDIA GPU. No GPU, no cloud.
- Format: ONNX. GGUF / llama.cpp is not used: it targets decoder LLMs, and this is a small encoder classifier.
- Base model candidates, tried in this order: (1) sentence-transformers/all-MiniLM-L6-v2 (22M params), (2) BAAI/bge-small-en-v1.5 (33M). Baseline for comparison: TF-IDF + logistic regression. The pick is a module-0 result against the bars below.
- Size/speed bar unchanged: int8 model at most 100 MB on disk, at most 20 ms per operation on this laptop CPU.
- rwxmap stays untouched. rwxlite reads its data in place and keeps its own copy of the Jev client.

## Labelling (first step inside module 0)

Data is read in place from rwxmap's `data/`, not copied:

- ~123,340 unlabelled operations from 2,529 APIs.guru specs (`data/corpus/apis-guru-ops.csv.gz`).
- ~1,186 hand-labelled rows (`data/corpus/labelled.csv`).
- Calibration data (`data/calibration-2026-09-14`).
- The exam (`data/exam-2026-09-22/labelled.csv`).

### Step 1. Mechanical pass (done)

rwxmap `classifyRow` over all rows. Free. Output `data/m0/mechanical.jsonl.gz`.

### Step 2. Jev pass

rwxlite has its own small Jev client, copied from rwxmap's `src/jev-client.js` (rwxmap does not export it).

**Rows excluded before any paid call (asserted in code):**
- The exam vendors: cloudflare, pagerduty, sentry.
- The 10 locked vendors: auth0, cloudflare, hubspot, zendesk, pagerduty, dropbox, shopify, linear, miro, sentry.
- The 19 rows flagged `exam_opkey_overlap`.

**Per-method question, one question per row:**

| Method | Question | Source file (rwxmap commit a7bc855, copied byte for byte) |
|---|---|---|
| POST | isX | `poc/jev-tiers/criteria-x.mjs` |
| PUT, PATCH | isX | `poc/jev-tiers/criteria-x-raise.mjs` |
| GET | changes | `poc/jev-tiers/criteria-changes.mjs` |
| DELETE | none: skip Jev, keep mechanical x | |
| HEAD, OPTIONS, TRACE, other | none: skip Jev, counts reported | |

- Questions are never taken from rwxmap `src/jev.js` at v0.8.0 or earlier (the shipped raise-wx and raise-get questions were wrong; fixed in a7bc855).
- State sent to Jev is exactly method, path, operationId, summary, description. The mechanical verdict is never sent.
- Jev's answer is read from `answers.<key>.noul`. The response model string is recorded on every answer.

**Wobble.** Jev gives different answers on repeat calls.
- Every row is asked once.
- Only rows with 0.1 <= p <= 0.9 are asked a second time.
- A row whose answer crosses a cut between the two asks is flagged and dropped from training.

**Spend cap: $50 (confirmed by the user).** The pass and the re-ask together stay under it. The labelling script enforces a hard stop below the cap in code (pass 1 + re-ask under $45 in the script's own accounting; price $42 per billion input tokens).

### Step 3. Training set and parity report

- Train on Jev's p for ALL rows that were asked. The mechanical letter and rule name are model input.
- Mechanical/Jev agreement is a REPORT, by rule and by vendor, not a filter. This report is a deliverable in its own right.
- DELETE rows keep the mechanical x as their label.
- Wobble-flagged rows are dropped.

### Step 4. Label quality gate

**Label standard.** BRIEF-v3 (D87 + D98) is the ONLY label standard, for the gate and for tuning. v1 labels (rwxmap `data/corpus/labelled.csv`, `data/calibration-2026-09-14`) are not used for either.

**DELETE.** Stays mechanical x, no Jev call (99.3% exact under v3). Unchanged from Step 2.

**Bar.** Jev-derived labels must be at least 95% exact against BRIEF-v3 truth. The 95% bar is kept. If the gate fails, the cause goes back to the PRD; the bar is not loosened.

**Fresh-sample procedure.** The bar is measured on a fresh sample, not on the older v3 sets (those are tuning data):
1. About 600 non-DELETE rows drawn from our 123k by `m0/gate-sample.mjs` (seeded, deterministic, seed recorded). Frozen in `data/gate-2026-11-03/` and committed.
2. Excluded: the exam vendors (cloudflare, pagerduty, sentry); the 10 locked vendors (rwxmap `docs/logs/pre-registered-split-2026-09-18.md`); the 19 `exam_opkey_overlap` rows; every op already in any v3 truth set (combined-2026-09-21, relabel-buildset-2026-09-23); HEAD, OPTIONS, TRACE and other methods.
3. Stratified: roughly proportional by method across GET/POST/PUT/PATCH, with at least 100 GET and 100 PUT/PATCH; no vendor above 5% of the sample; one row per op key (provider+method+path+operationId).
4. Two blind Claude workers label `blind.csv` under BRIEF-v3 (`data/gate-2026-11-03/BRIEF-v3.md`). They see no mechanical letter, no Jev p. The user rules disputes.
5. The sample is used ONCE, as the label gate. It is never used for tuning, model selection or any repeat scoring.
6. Every APIs.guru snapshot of a sampled op key is excluded from training and tuning (`data/gate-2026-11-03/ids.txt`).

Hand labels outside the exam vendors may also enter training, with extra weight, only if labelled under BRIEF-v3.

**Training before the gate.** Training setup (tooling, features, baselines) proceeds in parallel with labelling. Nothing is scored on the exam until the label gate passes.

### Exam isolation

Exam providers (cloudflare, pagerduty, sentry) are excluded from all training and from threshold tuning. The exam is scored once at the end.

### Thresholds

rwxlite tunes its own thresholds per tier, on BRIEF-v3 truth only, by leave-one-vendor-out on non-exam data. The exam is never used for tuning.

**Rule: global budget.** Maximise exact subject to TOTAL too-loose across all tiers being no worse than mechanical alone. The budget is shared across tiers, not per tier. Judged leave-one-vendor-out.

**Starting cuts** (a starting point for the sweep, not final): lower 0.20, raise-wx 0.60, raise-get 0.20.

## Round 6 (signed off 2026-11-03)

1. **Two-step lower on POST.** On `floor-post` x rows, x can drop to w OR r. POST rows are also asked the "changes" question (`m0/questions/criteria-changes.mjs`, byte-identical to rwxmap a7bc855; its r letter covers POST). Label rule for a POST x row: if isX p < lower cut, then if changes p < r cut the label is r, else w. The r cut is tuned with the global-budget rule (max exact subject to total too-loose no worse than mechanical), leave-one-vendor-out, on the v3 TUNING truth (the 5,716 joined rows from `m0/parity.mjs --truth v3`). Never on either gate sample or the exam.
2. **Second fresh gate sample (gate-2).** The first sample failed at 90.8% (all too-tight, mostly read-by-POST). After the rule changes, the label gate is measured on a SECOND fresh 600-row sample, same rules as gate-1 (seed 20261104, `data/gate-2026-11-04/`), also excluding every op key in `data/gate-2026-11-03/ids.txt` and all gate-1 rows. Used once.
3. **Credential rule.** A narrow text rule gives x when the operation changes, resets or rotates a credential (password, PIN, passcode, auth key, API key or secret, passphrase), per BRIEF-v3 clause (b). Narrow: creating a token or session for login is NOT covered unless the brief says so. Its effect is measured on the v3 tuning truth (hits, exact gained and lost) and it is applied only if it adds no too-loose and gains net.
4. **Bar stays 95%.** Not loosened.
5. **Exam as go/no-go.** The trained model is scored ONCE on rwxmap's 2026-09-22 exam as the M0 go/no-go. rwxmap already scored it with mechanical and with Jev; rwxlite never trained or tuned on it. This happens only after the label gate passes.
6. **Stance.** rwxlite and rwxmap learn from each other, no upper hand. rwxlite may build its own dataset to complement rwxmap's.

## Go / no-go (module 0)

On the 4279-operation exam, with exam providers held out:

- **Mode (a).** Too loose at most 0.5% (hard line, no worse than Jev) AND exact at least 91%.
- **The int8 model** passes the same bar, and is:
  - at most 100 MB on disk,
  - at most 20 ms per operation on this laptop CPU,
  - trained and run with no GPU.
- **Mode (b).** Reported, no bar.
- **Fail** means back to the PRD as a spec change. Never loosen the bar, narrow the input, or shrink scope to pass.

## Out of scope (whole build)

- Fine-tuning a generative or chat LLM.
- Phone builds, or the Cactus runtime.
- GPU training.
- Replacing rwxmap's mechanical rules.
- Publishing to Hugging Face.
- Non-OpenAPI inputs (for example MCP tool descriptions).
- An automated retraining pipeline.
- The gate's ask/deny decision itself. That is bareguard's job.

## Modules

Only module 0 is sharp. The rest are sketches.

**M0 — Labels + train + score.** This is the go/no-go.
- Mechanical pass.
- Jev pass.
- Parity, label gate, parity report.
- Train the small encoder.
- Score modes (a) and (b), in fp32 and int8, on the exam.

**M1 — Jev-compatible local answerer.**
- Export int8 ONNX.
- Run it in Node.
- Accept `{state, model, questions}`, return `{p, model}`.
- Measure size and latency in Node.

**M2 — Wire into rwxmap.**
- Add a local Jev option (for example `--jev local`).
- Re-run rwxmap's numbers with it.

**M3 (maybe) — Standalone mode (b) as a product.**
- Only if its M0 and M2 numbers earn it.

## Resolved (2026-11-03)

- Easy-case bias: train on Jev's p for all rows; agreement is a report, not a filter.
- $50 Jev cap: confirmed.
- Thresholds: rwxlite tunes its own, under the global-budget rule (round 5).
- Round 6: items 1-6 above (two-step POST lower, gate-2, credential rule, bar 95%, exam once, mutual-learning stance).
- Round 5: BRIEF-v3 only; DELETE mechanical; fresh-sample gate used once; model/format decisions recorded above.

## Open questions

- **Which small encoder.** all-MiniLM-L6-v2 first, bge-small-en-v1.5 second, TF-IDF + LR as baseline; the bars decide.
- **Model string.** What exact string rwxlite returns in `{p, model}`, and how it is versioned. rwxmap records the model string on every moved verdict (D88), so it must change whenever the weights change.
- **Licence.** Match rwxmap (Apache 2.0)? Not decided.
- **Distribution form.** npm package with the ONNX file, or a separate download. Decided in M1.
