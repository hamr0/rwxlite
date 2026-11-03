# rwxlite — PRD

Status: contract, round 4 signed off. Date: 2026-11-03.

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
  - jev-lower: x to w, on `floor-post` rows (question isX).
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
- Quantization: int8 ONNX. This is the "Cactus idea". Cactus itself (a phone LLM runtime) is not used.
- Runtime: inside rwxmap's Node process, via ONNX.
- Training: Python on CPU. Machine has 8 cores, 31 GB RAM, no NVIDIA GPU.
- Base model: a small text encoder (MiniLM-class). The exact choice is a module-0 run, not a decision.
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

Jev-derived labels must be at least 95% correct against the non-exam hand labels (`hand_set` and `calib_set` joins). Hand labels outside the exam vendors also enter training, with extra weight. If the gate fails, the cause goes back to the PRD; the bar is not loosened.

### Exam isolation

Exam providers (cloudflare, pagerduty, sentry) are excluded from all training and from threshold tuning. The exam is scored once at the end.

### Thresholds

rwxlite tunes its own thresholds per tier, by leave-one-vendor-out on non-exam data. The exam is never used for tuning.

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
- Thresholds: rwxlite tunes its own.

## Open questions

- **Which small encoder.** The first run decides.
- **Model string.** What exact string rwxlite returns in `{p, model}`, and how it is versioned. rwxmap records the model string on every moved verdict (D88), so it must change whenever the weights change.
- **Licence.** Match rwxmap (Apache 2.0)? Not decided.
- **Distribution form.** npm package with the ONNX file, or a separate download. Decided in M1.
