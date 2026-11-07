# rwxlite — PRD

Status: contract, round 6 signed off; M0 exam NO-GO (too loose); fresh exam NO-GO by one row (5 vs 4 too-loose rows); M1 answerer built and published (0.2.0, npm and GitHub release v0.2.0); round 10 trained, exam #3 NO-GO (loose bar), 0.2.0 stays shipped; round 11 trained, exam #4 NO-GO on both scorers; round 12 (S0/S1/S2) showed no gain over 0.2.0, so 0.2.0 stays shipped; 0.2.1 (answerMany batch-independence fix, same weights) is tagged v0.2.1 and not yet published. Date: 2026-11-05.

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
- The API key is read from the `RWXMAP_JEV_KEY` environment variable, else from `../rwxmap/.env` (gitignored); it is never printed or logged.
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

**Final cuts used on both exams** (r8soft, calibrated with T = 0.844, chosen on all non-exam data): lower 0.30, r cut 0.40, raise-wx 0.15, raise-get 0.05; mode (b) margin 0.6 (findings, "Round 8").

## Round 6 (signed off 2026-11-03)

1. **Two-step lower on POST.** On `floor-post` x rows, x can drop to w OR r. POST rows are also asked the "changes" question (`m0/questions/criteria-changes.mjs`, byte-identical to rwxmap a7bc855; its r letter covers POST). Label rule for a POST x row: if isX p < lower cut, then if changes p < r cut the label is r, else w. The r cut is tuned with the global-budget rule (max exact subject to total too-loose no worse than mechanical), leave-one-vendor-out, on the v3 TUNING truth (the 5,716 joined rows from `m0/parity.mjs --truth v3`). Never on either gate sample or the exam.
2. **Second fresh gate sample (gate-2).** The first sample failed at 90.8% (all too-tight, mostly read-by-POST). After the rule changes, the label gate is measured on a SECOND fresh 600-row sample, same rules as gate-1 (seed 20261104, `data/gate-2026-11-04/`), also excluding every op key in `data/gate-2026-11-03/ids.txt` and all gate-1 rows. Used once.
3. **Credential rule.** A narrow text rule gives x when the operation changes, resets or rotates a credential (password, PIN, passcode, auth key, API key or secret, passphrase), per BRIEF-v3 clause (b). Narrow: creating a token or session for login is NOT covered unless the brief says so. Its effect is measured on the v3 tuning truth (hits, exact gained and lost) and it is applied only if it adds no too-loose and gains net.
4. **Label-gate bar stays 95%.** Not loosened. This is the bar for the training labels (the label gate, passed at 96.5% on gate-2), not for the model. The model's go/no-go bar is separate: see "Go / no-go (module 0)" and, for the fresh exam, "Option 2" / "The flow" (exact >= 91%, too loose <= 0.5%, asked <= 15%).
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

### M0 exam result (2026-11-03): NO-GO

Scored once, pre-registered (f05ec42), scored in 51d8fb4. Model: MiniLM r8soft (soft targets), calibrated, cuts tuned on v3 tuning truth only. 4279 exam rows (cloudflare, pagerduty, sentry); none were seen in training or tuning.

Mode (a), no ask, was the go/no-go: **exact 95.91% passes, too loose 0.84% (36 rows) fails the 0.5% line.** Every other row is reported only.

"Ask at p" = the model answers only when its top probability is at least p; the rest become "ask" (bareguard asks the user). Exact / too loose / too tight are counted on the rows it answers.

| setup | answers itself | asks | exact | too loose | too tight | asks that would have been too loose |
|---|---|---|---|---|---|---|
| mechanical alone (base) | 4279 (100%) | 0 | 3520 (82.26%) | 34 (0.79%) | 725 (16.94%) | — |
| mechanical + Jev (rwxmap) | 4279 (100%) | 0 | 93.0% | 0.5% | 6.5% | — |
| **(a) no ask — go/no-go** | 4279 (100%) | 0 | 4104 (95.91%) | **36 (0.84%)** | 139 (3.25%) | — |
| (a) ask at 0.7 | 4169 (97.4%) | 110 (2.6%) | 4064 (97.48%) | 36 (0.86%) | 69 (1.66%) | 0 |
| (a) ask at 0.9 | 4019 (93.9%) | 260 (6.1%) | 3961 (98.56%) | 21 (0.52%) | 37 (0.92%) | 15 |
| (a) ask at 0.95 | 3861 (90.2%) | 418 (9.8%) | 3812 (98.73%) | 18 (0.47%) | 31 (0.80%) | 18 |
| (b) no ask | 4279 (100%) | 0 | 4088 (95.54%) | 32 (0.75%) | 159 (3.72%) | — |
| (b) ask at 0.7 | 4169 (97.4%) | 110 (2.6%) | 4060 (97.39%) | 32 (0.77%) | 77 (1.85%) | 0 |
| (b) ask at 0.9 | 4019 (93.9%) | 260 (6.1%) | 3965 (98.66%) | 21 (0.52%) | 33 (0.82%) | 11 |
| (b) ask at 0.95 | 3861 (90.2%) | 418 (9.8%) | 3812 (98.73%) | 18 (0.47%) | 31 (0.80%) | 14 |

Where the 36 too-loose rows of (a) no ask are: 30 cloudflare, 4 pagerduty, 2 sentry. 22 are POST creates the mechanical rules called x and the model lowered (top-up, zone subscription, restore database, deletion job); 9 are PUT/PATCH credential updates whose p(x) (0.01 to 0.11) sat under the 0.15 raise cut; 5 others. The model is confident on them (median top p 0.94), so asking at 0.7 catches none and asking at 0.9 to 0.95 catches about half.

#### How to read the ask table

Every exam operation lands in exactly one of four piles:

- **Right**: the model gave the correct letter.
- **Too loose**: the model called it safer than it is. This is the dangerous one.
- **Too tight**: the model called it riskier than it is. Annoying but safe.
- **Asked**: the model stays quiet and the user decides.

The confidence bar only moves rows into the Asked pile. A row is either answered or asked, never both. Raising the bar never adds too-loose rows; it can only move them into Asked.

Mode (a), all 4279 rows:

| bar | right | too loose | too tight | asked | asked = right + loose + tight |
|---|---|---|---|---|---|
| none | 4104 | 36 | 139 | 0 | |
| 70% | 4064 | 36 | 69 | 110 | 40 + **0** + 70 |
| 90% | 3961 | 21 | 37 | 260 | 143 + **15** + 102 |
| 95% | 3812 | 18 | 31 | 418 | 292 + **18** + 108 |

At 70% the 110 asks contain no too-loose rows: all 36 dangerous mistakes are still answered, because the model was more than 70% sure of every one. The 70% bar only removes half the too-tight rows. At 90% to 95% the asks start to catch the dangerous mistakes (15 to 18 of 36), at the cost of asking on 6% to 10% of operations, most of which it would have got right. "Exact" in the table above = right / answered (95%: 3812 / 3861 = 98.7%).

Reading: rwxlite beats mechanical + Jev on exact by about 3 points but is looser than Jev, and as loose as mechanical alone. Asking at 0.95 would clear the 0.5% line, but it was not the pre-registered go/no-go, so it does not count as a pass. The exam is now burned for rwxlite. Next step (spec change) is open; see Open questions.


### Round 9 hand labels (2026-11-03)

To test whether the exam's too-loose rows came from bad training labels, 1,200 training rows of the two failing shapes (seeded random by shape, no word filter, no exam/gate/v3 rows) were labelled blind under BRIEF-v3 by two labellers (98.8% agreement; the stricter letter wins where they differ). Data: `data/r9-hand/` (d20b956).

| shape | rows | hand labels agree with training | training label too loose | training label too tight |
|---|---|---|---|---|
| POST creates (lower tier, mechanical x lowered) | 800 | 774 | 22 | 4 |
| PUT/PATCH updates (raise-wx, label w) | 400 | 390 | 10 | 0 |
| **total** | 1,200 | 1,164 | **32 (2.7%)** | 4 |

The too-loose ones are things like creating a payment, accepting a calendar invite (notifies the organizer), registering a campaign with an outside registry.

Reading: the Jev-recipe training labels are mostly right on these shapes. The exam's 36 too-loose rows (30 cloudflare: billing top-ups, subscriptions, database restores, deletion jobs) are a vendor-specific pattern the corpus barely contains, not a general labelling error; the exam was labelled under the same BRIEF-v3. A retrain with these labels would change about 32 of 87,657 training rows, so it is not expected to move the exam result much.


## Option 2: "unsure" built in (user, 2026-11-03)

After the NO-GO the user chose option 2: the "unsure" rule becomes part of rwxlite and is pre-registered as the go/no-go on a fresh exam. Round 9's retrain is skipped (its hand labels showed the training labels too loose on only 32 of 1,200 rows; kept for the next training).

What happens to an unsure row (top p under the bar). It is never re-asked to rwxlite: the same model gives the same answer.
- **ASK**: the answer is "ask"; bareguard asks the user.
- **MECH**: the mechanical letter stands; nobody is asked.
- **MECH-THEN-ASK**: the mechanical letter stands if it is at least as strict as the model's letter (r < w < x); otherwise "ask".

Measured on the practice rows (v3 tuning truth, 5,716 rows, leave-one-vendor-out; not an exam), mode (a). Right / too loose / too tight are rows with % of answered; asked is % of all rows with what the asks held (right / loose / tight). Every row is in exactly one pile.

| rule | bar | right | too loose | too tight | asked |
|---|---|---|---|---|---|
| mechanical alone | — | 76.3% | 77 (1.3%) | 22.3% | 0 |
| no bar | — | 5303 (92.8%) | 73 (1.28%) | 340 (5.95%) | 0 |
| ASK | 0.7 | 5186 (95.3%) | 65 (1.19%) | 192 (3.5%) | 273 (4.8%) (117/8/148) |
| ASK | 0.9 | 4954 (97.7%) | 38 (0.75%) | 78 (1.5%) | 646 (11.3%) (349/35/262) |
| ASK | 0.95 | 4675 (98.7%) | 24 (0.51%) | 39 (0.8%) | 978 (17.1%) (628/49/301) |
| MECH | 0.9 | 5269 (92.2%) | 96 (1.68%) | 351 (6.1%) | 0 |
| MECH | 0.95 | 5186 (90.7%) | 85 (1.49%) | 445 (7.8%) | 0 |
| MECH-THEN-ASK | 0.9 | 5168 (93.0%) | 39 (0.70%) | 351 (6.3%) | 158 (2.8%) (57/0/101) |
| **MECH-THEN-ASK** | **0.95** | 5050 (91.5%) | **27 (0.49%)** | 445 (8.1%) | **194 (3.4%)** (58/0/136) |

Mode (b) is within a few rows of mode (a) under every rule (findings, "Round 9b").

Reading:
- MECH alone makes things worse: on PUT/PATCH the mechanical letter is often w where the truth is x, so falling back to it adds loose rows.
- MECH-THEN-ASK at 0.95 is the best trade: as few loose rows as ASK at 0.95 (27 vs 24) with a fifth of the asks (3.4% vs 17.1%). Its cost is too-tight rows (8% vs 0.8%), which are safe but may themselves turn into prompts if bareguard asks on x.
- ASK at 0.95 gives the highest accuracy on what it answers but asks on 1 in 6 operations.
- Caveat: on the exam the model's dangerous mistakes were confident (median top p 0.94), so the practice-row gain may not fully transfer. That is what the fresh exam tests.

**Go/no-go for the fresh exam.** First signed off as MECH-THEN-ASK at 0.95; **replaced by the user on 2026-11-03, before any prediction on the fresh exam, by the lowering-flag rule below** (round 9c, measured on practice rows only). The full pre-registration (checkpoint hash, cuts) is committed before scoring.
- Rule: mode (a), LOWER-BAR-ASK at 0.97: when rwxlite lowers the mechanical letter (x to w or r, w to r) it is accepted only if its top p is at least 0.97, otherwise the row is "ask". Raises and keeps are trusted.
- Pass: too loose at most 0.5% of answered rows AND exact at least 91% of answered rows AND asked at most 15% of rows.
- Reported only: no bar; MECH-THEN-ASK at 0.95 (the earlier rule); ask on every lowering; LOWER-BAR-ASK at 0.95 plus MECH-THEN-ASK on non-lowerings; mode (b) no bar; mechanical alone.
- The bar is a user setting in the product; the exam fixes one value so the test is fair.
- Fresh exam: vendors never used in training or tuning, agreed with rwxmap; labelled blind under BRIEF-v3 by two labellers, disagreements ruled by the user; scored once.



### Fresh exam result (2026-11-03): NO-GO by one row

949 ops from coolify, workos, lago, resend (never seen by rwxlite or rwxmap; pinned specs; labels frozen in 312b23a before any prediction). Pre-registered in 0caa381, scored once in 402fea0. Same model as before (r8soft, sha256 974dff01...ae).

Go/no-go (mode a, ask on lowerings under 0.97): **right 92.57% of answered (pass), asked 7.8% (pass), too loose 5 of 875 answered = 0.57% (fail; the line is 0.5%, i.e. 4 rows).**

| setup | right | too loose | too tight | asked (held right/loose/tight) |
|---|---|---|---|---|
| mechanical alone | 736 (77.6%) | 6 (0.63%) | 207 (21.8%) | 0 |
| rwxlite, trust blindly | 870 (91.7%) | 18 (1.90%) | 61 (6.4%) | 0 |
| **rwxlite, ask on lowerings under 0.97 (go/no-go)** | **810 (92.6%)** | **5 (0.57%)** | 60 (6.9%) | **74 (7.8%)** (60/13/1) |
| rwxlite, ask on every lowering | 718 (91.7%) | 5 (0.64%) | 60 (7.7%) | 166 (17.5%) |
| rwxlite, MECH-THEN-ASK 0.95 (earlier rule) | 840 (89.3%) | 6 (0.64%) | 95 (10.1%) | 8 (0.8%) |

What worked: the lowering flag did exactly its job. rwxlite lowered 166 rows; all 13 wrong lowerings were under 0.97 and were asked; all 92 accepted lowerings were right. No lowering caused a too-loose answer.

What failed: the 5 too-loose rows are not lowerings. 3 are PUT/PATCH credential upserts where mechanical says w and rwxlite agreed (workos client-credentials, workos api-key, coolify integration token; truth x by clause b). 2 are logout GETs where mechanical says r and rwxlite raised to w, one step short of x. This is the "confident mistakes / mechanical too loose" floor named under "The flow". Mechanical alone is itself too loose here (6 rows, 0.63%).

Per the rules: the bar is not loosened. Any fix (a credential-upsert or logout rule) needs a new fresh exam. Next step is open.

## The flow (user, 2026-11-03)

**rwxmap is the adapter; rwxlite is only a classifier.** rwxmap imports specs, shapes each operation into Jev's request, calls an engine, applies the rules below, and emits every verdict and flag. rwxlite never sees URLs or specs and never decides to ask. Engines under rwxmap:

| engine | what runs | cost |
|---|---|---|
| mechanical, then rwxlite (default) | mechanical leans first; rwxlite settles the contested rows (Jev's job today) | free, local |
| rwxlite alone | rwxlite labels every operation (mode b) | free, local |
| mechanical, then Jev | today's setup, the paid option if you trust neither | paid per call |

**Two answers in one call.** rwxmap asks rwxlite both Jev questions in one request: isX ("can't be taken back?") and changes ("changes anything?"). From those two: x = isX, w = changes - isX, r = 1 - changes. Same request and answer shape as Jev, so engines stay swappable.

**Lowerings are flagged, not trusted blindly.** Measured on practice rows (round 9c): of r8soft's 73 too-loose rows, 57 are lowerings (x to w or r, w to r); raises were never too loose (61 right, 139 too tight of 200); 16 are keeps where the mechanical letter is itself too loose and rwxlite agreed. So rwxmap highlights every lowering; a lowering is accepted only when rwxlite is at least 97% sure; the rest go to the user, alongside rows rwxmap already marks too tight. Practice-row result: 93.2% right, 21 too loose (0.41% of answered), 6.5% too tight, 9.6% asked (asking on every lowering: 16 too loose but 19.9% asked).

| rule (practice rows, 5,716) | right | too loose | too tight | asked |
|---|---|---|---|---|
| trust rwxlite blindly | 92.8% | 73 | 6.0% | 0% |
| MECH-THEN-ASK at 0.95 (earlier rule) | 91.5% | 27 | 8.1% | 3.4% |
| ask on every lowering | 92.4% | 16 | 7.3% | 19.9% |
| **ask on lowerings under 0.97** | **93.2%** | **21** | 6.5% | **9.6%** |
| lowering under 0.95 asks + MECH-THEN-ASK on the rest | 95.7% | 27 | 3.8% | 8.4% |
| lowering under 0.95 keeps mechanical (no ask) | 89.4% | 27 | 10.2% | 0% |

Silently keeping the mechanical letter instead of asking costs too-tight rows (10% to 25%); asking is better.

**Known limit: confident mistakes are not flagged.** A wrong answer rwxlite is sure about is not marked. The 16 rows where mechanical is too loose and rwxlite agrees are not lowerings, so no lowering rule catches them (the same as Jev today); rwxmap's own "loose" review markers may cover some (to check with rwxmap). Mitigations later: user answers to asks become hand labels for the next manual training round; bareguard policy (later, after the flow is settled).

## Out of scope (whole build)

- Fine-tuning a generative or chat LLM.
- Phone builds, or the Cactus runtime.
- GPU training.
- Replacing rwxmap's mechanical rules.
- Publishing to Hugging Face.
- Non-OpenAPI inputs (for example MCP tool descriptions).
- An automated retraining pipeline.
- The gate's ask/deny decision itself. That is bareguard's job.

### M1 result (2026-11-04)

What was built (`src/`, `m1/`, `test/`, `.github/workflows/ci.yml`):
- `m1/export_onnx.py export` writes the fp32 ONNX graph (inputs `input_ids`, `attention_mask`, `token_type_ids`; output raw `logits` (n,3)) and a plain `vocab.txt`. `m1/variants.py build` writes five more files from it (see the table). Temperature T = 0.844 is applied by the caller, as in `train/exam_score.py`.
- `src/text.js` and `src/tokenizer.js` are Node ports of `fmt_text` and the BERT WordPiece tokenizer, so Node needs no Python and no `transformers`. They match the Python on all 102,781 local texts: 0 text mismatches (5,228 exam rows), 0 token-id mismatches (`node m1/check-corpus.mjs`, exit 0). A 973-row fixture of the same (`test/fixtures/parity.jsonl`) is committed and runs in CI.
- `src/answerer.js`: `loadAnswerer({dir})` reads `manifest.json` (`version`, `modelFile`, sha256 of each file), refuses to start on any sha mismatch, reads the optional manifest `temperature` (finite number > 0, else it throws; absent = 0.844), and returns an `Answerer` with `answer(req)` and `answerMany(reqs)`. Switching the shipped variant is a manifest change (`node m1/manifest.mjs <model-file>`).
- Answer shape: `{model, answers: {isX: {noul}, changes: {noul}}}` where `isX = p(x)` and `changes = p(w) + p(x)`; only the asked questions are returned. The model string is `rwxlite-<version>+<first 8 hex of the weights' sha256>`. rwxlite never returns a letter, a cut or an ask: rwxmap derives `x = isX`, `w = changes - isX`, `r = 1 - changes` and keeps all decisions. There are two shapes, both plain JSON (an `Error` instance serialises as `{}`, so none is returned): success `{model, answers: {...}}` and no answer `{model, error: '<message>'}` with no `answers` key. `answerMany` returns one of the two in every slot (a bad request fails its own slot; a model failure fails every slot); `answer(req)` returns the success object and throws an `Error` with the same message on a no-answer. On either, the caller keeps the mechanical letter.

Proposal for rwxmap's D133: the request needs one field Jev's does not have, `lean: {class, rule}`, the mechanical letter and rule. The model was trained with them as the first words of its input (`lean: x path-verb | POST /v1/...`), so without them the answer is not the one that was scored. rwxmap already has both when it builds the Jev request. Everything else is Jev's shape: `state` (method, path, operationId, summary, description), `model` (ignored, there is one model), `questions` (only the keys are read).

Distribution (superseded by the Decisions below; kept for the install sizes): model files are not bundled in the npm package. The package ships the code, `vocab.txt`'s hash and the manifest format; the weights are downloaded on first use to a cache directory and checked against the manifest's sha256 (fail closed on mismatch). `onnxruntime-node` is an optional dependency. CPU-only, `npm install onnxruntime-node` with `ONNXRUNTIME_NODE_INSTALL=skip` is 294 MB in `node_modules` (all platforms' binaries; the Linux x64 library is 48 MB); with the default install on Linux x64 it also downloads 285 MB of CUDA libraries (566 MB total). rwxmap should install it with the skip variable, or document that.

Quantisation variants, measured on the two burned exams (a precision check, not a new go/no-go). Python side: ONNX Runtime, batch 1, against the saved torch fp32 probabilities. Node side: batch 1, 1 thread, all 949 fresh rows, after 20 warm-up rows, end to end (format, tokenise, run, calibrate). Machine: i7-8665U 1.9 GHz, 8 logical cores, Node 22.22.2, onnxruntime-node 1.31.1, load average about 2 to 3 during the runs. Raw numbers in `data/m1/variants.json` (local).

| Variant | Size | Node p50 / p95 / mean ms | Max / mean abs p vs torch (fresh) | Argmax agree (fresh, 09-22) | Rows across the 0.97 line (fresh, 09-22) |
|---|---|---|---|---|---|
| fp32 | 90.97 MB | 23.4 / 49.0 / 25.9 | 0.000001 / 0 | 949, 4279 | 0, 0 |
| fp16 | 45.59 MB | 24.6 / 50.9 / 27.0 | 0.0008 / 0.00002 | 949, 4279 | 0, 0 |
| int8 default (per-tensor, MatMul + embeddings) | 23.02 MB | 17.2 / 36.6 / 18.8 | 0.417 / 0.0062 | 937, 4241 | 17, 87 |
| int8 per-channel | 23.13 MB | 18.2 / 38.1 / 20.2 | 0.118 / 0.0022 | 943, 4270 | 8, 33 |
| int8 MatMul only | 58.77 MB | 17.2 / 36.9 / 19.0 | 0.458 / 0.0059 | 935, 4238 | 21, 85 |
| int8 per-channel, MatMul only | 58.88 MB | 17.3 / 37.2 / 19.1 | 0.224 / 0.0022 | 945, 4272 | 2, 32 |

Fresh exam re-scored with each file's probabilities under the pre-registered GO/NO-GO rule (lower-bar-ask 0.97, same code, only the probabilities differ):

| Variant | Right | Too loose | Too tight | Asked | Rows whose final letter or ask changed vs fp32 |
|---|---|---|---|---|---|
| fp32 / torch (as registered) | 810 | 5 | 60 | 74 | 0 |
| fp16 | 810 | 5 | 60 | 74 | 0 |
| int8 default | 808 | 5 | 55 | 81 | 15 |
| int8 per-channel | 809 | 5 | 61 | 74 | 7 |
| int8 MatMul only | 805 | 5 | 56 | 83 | 17 |
| int8 per-channel, MatMul only | 810 | 5 | 59 | 75 | 5 |

The 09-22 exam, mode (a) with no bar: fp32 4104 right, 36 too loose, 139 too tight. int8 default 4106 / 45 / 128 (35 rows changed; 9 more too loose); per-channel 4105 / 36 / 138 (18 changed); MatMul only 4101 / 45 / 133 (37); per-channel MatMul only 4102 / 36 / 141 (16); fp16 identical to fp32 (0 changed).

Reading:
- Node and Python agree: for every variant the largest difference between Node's answer and the Python ONNX Runtime's at batch 1 is 1.3e-7 on the fresh rows and 1.4e-7 on the 4,279 older rows. The runtime is not a source of drift; the quantised weights are.
- Default dynamic int8 moves answers a lot (mean 0.006, up to 0.42 in p) and, on the older exam, adds 9 too-loose rows. Per-channel weight scales cut the drift by about 3x at the same size and keep the too-loose count equal to fp32 on both exams (5 and 36). Keeping embeddings in fp32 (MatMul only) does not help by itself and costs 36 MB.
- Dynamic int8 scales each activation tensor per call, so a row's answer depends on its batch mates: the default int8 file changed 15 fresh rows at batch 1 and 13 at batch 32. The differences are the same size as the quantisation drift.
- fp16 reproduces the fp32 decisions exactly (0 rows changed on both exams, max p difference 0.001) at half the size of the fp32 file, but is not faster on this CPU (mean 27.0 ms against 25.9 for fp32).
- D133 asks for at most 20 ms per op on int8, laptop CPU. Mean per-op latency at batch 1 on 1 thread is 18.8 ms (default int8) and 20.2 ms (per-channel), p95 about 37 to 38 ms, p99 about 39 ms. fp32 and fp16 are 26 to 27 mean, so only int8 meets the pin on average, and no variant meets it at p95. Batched, 32 rows per call on default threads, int8 costs 21.8 to 22.4 ms per op here (the machine was shared with other jobs, so treat all latency numbers as upper bounds). Cold load: 0.23 to 0.28 s for the 23 MB files.
- Not decided here: which file ships. The numbers are a precision check on burned exams, not a new go/no-go (fresh exam stays NO-GO by one row; every variant has the same 5 too-loose rows).

Decisions (2026-11-04):
- **Package default model file: int8 per-channel** (rwxmap's own default is the exact fp32 model, per its PRD) (`model-int8-pc.onnx`, sha256 `8ad0a182...`, model string `rwxlite-0.2.0+8ad0a182` at this version). It has the fp32 too-loose counts on both exams (5 and 36) at 23.1 MB.
- **Option "exact": fp32** (`model-fp32.onnx`, 91 MB) for users who want no quantisation drift and do not mind the size.
- **Distribution: GitHub releases on hamr0/rwxlite.** Per release: `manifest.json` (default, int8-pc), `manifest-exact.json` (fp32), `model-int8-pc.onnx`, `model-fp32.onnx`, `vocab.txt`. `node m1/release-assets.mjs` builds that set into `data/m1/release/` and prints the sizes, sha256s and the `gh release upload` command; it uploads nothing. rwxmap downloads on first use, always the latest, from `https://github.com/hamr0/rwxlite/releases/latest/download/<file>`, and caches each model in `<cache>/rwxlite-<semver>+<sha8>/` holding `manifest.json` (`{version, modelFile, model, files: {name: sha256}}`), the model file and `vocab.txt`; every sha256 is checked.
- **Threads:** `loadAnswerer` defaults to `Math.min(4, os.availableParallelism())` intra-op threads (was 1); the `threads` option stays. `m1/bench.mjs` keeps its own default of 1 so old results stay comparable.

Latency by thread count, Node 22, batch 1, end to end per op, ms:

| Machine | File | Threads | Mean | p50 | p95 |
|---|---|---|---|---|---|
| Server i3-8100T (4 cores, quiet) | int8 default | 1 | 15.53 | 14.03 | 31.02 |
| | | 2 | 8.98 | 8.14 | 17.59 |
| | | 4 | 6.20 | 5.46 | 11.11 |
| | int8 per-channel | 1 | 15.52 | 14.03 | 31.02 |
| | | 2 | 9.15 | 8.28 | 17.81 |
| | | 4 | 6.93 | 5.72 | 13.13 |
| | fp32 | 1 | 19.69 | 17.71 | 38.59 |
| | | 2 | 11.50 | 10.40 | 21.95 |
| | | 4 | 7.85 | 7.13 | 13.97 |
| Laptop i7-8665U (background load) | int8 per-channel | 1 | 19.8 to 23.3 | 18.0 to 21.0 | 39 to 46 |

Server: Intel i3-8100T @ 3.10GHz, 4 cores, load average 0.2 to 1.8 during the runs. Laptop: i7-8665U @ 1.90GHz, 8 logical cores, under background load.

The 20 ms pin (D133) is met at p95 with 4 threads on both int8 and fp32 on the server. The laptop numbers swung about 2x with machine load across runs (hence ranges), so read them as upper bounds.

### Decision rules: rwxlite's measured rule and rwxmap's secondPass

rwxlite returns only p. Which rule turns p into a letter is rwxmap's call. This section records the rule rwxlite measured (its steps are kept exact, because the fixture and `test/decision.test.js` use them) and the comparison rwxmap ran against its own. The fresh-exam result for rwxlite's rule (810 right, 5 too loose, 60 too tight, 74 asked of 949) came from one exact rule: `mode_a` (`train/exam_score.py`) and then lower-bar-ask at 0.97 (`GONOGO_lba097` in `train/exam_fresh.py`). In terms of the answer: p(x) = `isX`, p(w)+p(x) = `changes`, p(w) = `changes - isX`, p(r) = `1 - changes`, max p = max(`1 - changes`, `changes - isX`, `isX`). All p are calibrated (softmax of logits / 0.844), which rwxlite already does.

1. **Which rows move at all.** Only rows with a Jev tier: `jev-lower` (tier lower), `jev-raise-wx` (raise-wx), `jev-raise-get` (raise-get). These are the rows rwxmap's `needsJev` sends to Jev today, mapped by `TIER` in `train/common.py`. A row with no tier (jev_tier empty) is never moved by p; only step 3 can still change it. Rows rwxmap does not send (no tier) are still scored by the model in the fixture, so p exists for all of them.
2. **Cut per tier** (m = the mechanical letter; x > w > r):
   - lower: if m = x and `isX < 0.30`, new letter is r when the method is POST and `changes < 0.40`, else w.
   - raise-wx: if m = w and `isX >= 0.15`, new letter is x.
   - raise-get: if m = r and `changes >= 0.05`, new letter is w.
   - Otherwise the letter stays m.
3. **Credential rule** (`cred_hit`, `train/common.py`): if the method is not GET and any of operationId, summary, path matches the regex below, the letter is x, whatever steps 1 and 2 said. Each field is first normalised: camelCase split (`([a-z0-9])([A-Z])` to `\1 \2`), every run of non-alphanumerics to one space, lowercased. The regex source:
   `\b(?:change|reset|rotate|regenerate|renew|revoke|invalidate|expire)\b(?: \w+){0,3}? (?:password|passcode|passphrase|pin|pin code|auth key|authkey|api key|apikey|api secret|secret key|client secret)s?\b(?! (?:polic|rule|requirement|complexity|setting|config))`
4. **DELETE and rows outside the tiers** keep the mechanical letter (the credential rule still applies to non-GET, DELETE included).
5. **The final step (ask).** A lowering is a final letter below the mechanical one. A lowering with max p < 0.97 is asked: in rwxmap's terms, keep the stricter (mechanical) letter and add a review marker. Raises and keeps are trusted as they are. (The scripts count such a row as asked, not answered; its `expected.letter` in the fixture is the lowered letter the rule produced, so rwxmap can see what was withheld.)

**Other rules have no rwxlite numbers.** Argmax, other rows, other cuts, other bars, a different model file: none of them is what scored 810 / 5 / 60 / 74 in rwxlite's own scoring. Those numbers are for the rule above on the int8 per-channel default model (809 / 5 / 61 / 74 there); the 810 / 5 / 60 / 74 figure is the registered torch fp32 run (see the variant table).

**Rule comparison by rwxmap (their commit 466cda1, `poc/d133-rule-compare/readout.txt` in rwxmap).** Same 949 fresh-exam rows and the same int8 per-channel p as the fixture. Asked or undecided rows are scored at the stricter letter. Tuning data for rwxmap, not an exam. rwxlite's rule reproduces `expected` on all 949 rows (0 mismatches).

| Rule | Exact | Too loose | Too tight | Rows sent | Asked / undecided |
|---|---|---|---|---|---|
| Mechanical alone | 736 | 6 | 207 | | |
| rwxlite tier rule (mode a + lower-bar-ask 0.97) | 821 | 5 | 123 | 775 | 74 asked |
| rwxmap secondPass (rows their marker calls loose or tight; argmax over r/w/x; raises always accepted; lowerings need max p >= 0.97; undecided = x + review) | 826 | 6 | 117 | 425 | 99 undecided |

The rules differ on 9 rows. 5 are GET rows only rwxlite's raise-get tier sends: the two workos logouts are truth x (both rules too loose), the other 3 are truth r (rwxlite's rule makes them too tight). The other 4 are PUT/PATCH rows rwxlite's raise-wx tier raises at isX >= 0.15: lago `/invoices/{id}/finalize` is truth x (one fewer leak for rwxlite), the other 3 are truth w.

**rwxmap's ruling (D133).** Keep secondPass. Reasons: a one-row leak difference is noise, and it matches their rulings (settled rows untouched, undecided means x). rwxlite's numbers stay rwxlite's; secondPass will be tested on shared exam #3. Neither rule fixes the 5 real leaks (3 credential PUT/PATCH, 2 logout GETs): the model agrees with mechanical on them (client-credentials w 0.975, `/sso/logout` w 0.969). rwxmap's R1/R2 tuning comes next.

**Parity fixture.** `test/fixtures/decision.jsonl`, made by `.venv/bin/python m1/decision-fixture.py` from the default model's batch-1 p and the pre-registered scripts (imported unchanged; truth is never read). One row per operation, all 949: `{id, method, state (5 fields), lean {class, rule}, jev_tier (null when none), isX, changes, expected {letter, asked}}`. `test/decision.test.js` holds a JS reference of the rule (test only; not exported from `src`) and reproduces `expected` for all 949 rows from those fields alone, so the rule above is complete. Counts: 165 lowerings, 10 raises, 774 keeps, 74 asked. It is a parity and reference file for rwxlite's rule; rwxmap may use it to check its own port of that rule, but it does not have to apply that rule.

### HTTP QUERY read as GET (rwxmap D134, 2026-11-04)

rwxmap ruled QUERY (RFC 10008, safe and idempotent like GET, with a body) as r and sends `state.method = "QUERY"` as-is. The model never saw QUERY in training, so the text step writes QUERY as GET (case-insensitive) before the model reads it; `checkRequest` still accepts any non-empty method string. Measured before the change, on the 383 fresh-exam GET rows relabelled QUERY: argmax changes on 1 row, 1 row crosses the 0.97 line, max |changes diff| 0.33; otherwise stable. Real QUERY training rows can come in a later labelling round; the labelling brief default is QUERY = r by protocol, same as GET.

### Guard: lean rule `credential-set` read as `cant-undo-verb` (rwxmap D131, 2026-11-04; kept: round 10 trained on the alias text)

rwxmap's step-2 rule `credential-set` (class x, PUT/PATCH) is a lean rule name the model never saw. Measured (default int8-pc model, the 32 credential-set ops in `data/m0/mechanical.jsonl.gz`): as `credential-set` argmax w on 12, 3 with max p >= 0.97 (britbox /account/pin, whapi /account/plusCard/pin, circuitsandbox /spaces/{topicId}/pin); as `cant-undo-verb` (a trained x rule) all 32 argmax x, isX >= 0.9996. So `formatText` maps the rule through `LEAN_RULE_ALIASES` before the model reads it (the lean class stays as sent; `checkRequest` still accepts any non-empty rule). Re-measured with the guard: 32 of 32 argmax x, 0 lowerings at p >= 0.97. `node m1/credential-set-file.mjs` writes `test/fixtures/credential-set.jsonl`, the 32 ops with the model's answers before the guard and after it, so rwxmap can check its secondPass floor on identical rows (no test reads it; regenerating it reproduces the same numbers). **Removal condition (updated after round 10):** none for now. Round 10 was trained on the alias text `cant-undo-verb` and never read the name `credential-set` (findings, "The 32 credential-set ops"), so the alias is part of the model's input contract and stays. It would go only if a later round trains on the real name. rwxmap is asked to never lower a credential-set row. Per rwxmap the risk is in mode b only (mode a never sends credential-set rows, they are settled; mode c, Jev, does not take them). Of the 3 lowerings, only britbox /account/pin is a real credential lowering; whapi PUT /account/plusCard/pin was ruled truth w at gate 3 (credential-set's one wrong fire), and circuitsandbox /spaces/{topicId}/pin has the same pinned-item shape (on rwxmap's ledger). The guard can turn those 2 into too-tight x rows, which is safe ('unsure means x').

## Vendor labels: an independent check of our teacher (planned 2026-11-05)

**Goal.** Some API vendors publish their own read/write/permission labels. AWS lists every IAM action with an access level (List, Read, Write, Tagging, Permissions management); GitHub lists, per REST endpoint, the permission area and read or write level a fine-grained token needs. These labels were made by the vendors, not by Jev or by us, so they are an independent opinion on the same operations. Use them to find rows where our teacher (mechanical + Jev) or the model sits below what the vendor implies, which is the dangerous error (too loose).

**Mapping (hints, not labels).**

| Vendor says | Hint |
|---|---|
| AWS List / Read; GitHub read | r |
| AWS Tagging | w |
| AWS Write | not r (w or x) |
| AWS Permissions management | x |
| GitHub write in Administration (and any other clearly admin/secret/credential area found, listed in the findings) | x |

**Steps.**
- A (no spend): join vendor labels to corpus rows; compare with mechanical, Jev, the training label 0.2.0 learned, and 0.2.0's own answer and rwxmap final letter (secondPass replica). Report agreement, and the candidate dangerous mistakes (vendor says x or "not r", we say lower). Scripts in `vendor/`, outputs in `data/vendor/` (gitignored). No training, no Jev or other paid calls.
- B (only if A shows value, needs user approval first): Jev only on the gaps (vendor-labelled rows with no Jev answer), about $1-2.
- C: BRIEF-v3 review of the disagreements, feeding round 13 data. Optional: a ModernBERT-base (149M) size test, judged once on a fresh exam under the D135 bar.

**Safeguards.**
- Exam isolation: rows with an exam flag, `exam_opkey_overlap`, or in any exam/gate/holdout/r9-hand set stay out of training and tuning, and are counted separately in every table.
- Licence: AWS data is MIT (`@fluggo/aws-service-auth-reference`). GitHub docs content licence is reported, not decided. Vendor data is not redistributed in the repo (data/ is gitignored). Azure needs a login and is not done.
- **BRIEF-v3 stays the only label standard.** Vendor labels are evidence that selects rows to review, never truth and never a training label by themselves.

## Modules

Only module 0 is sharp. The rest are sketches.

**M0 — Labels + train + score.** This is the go/no-go. Status 2026-11-03: built and scored, NO-GO twice (exam 1: 36 too loose; fresh exam: 5 too loose, one over the line); next step open. The int8 export was not built, so the scoring below ran in fp32 only.
- Mechanical pass.
- Jev pass.
- Parity, label gate, parity report.
- Train the small encoder.
- Score modes (a) and (b), in fp32 and int8, on the exam (done in fp32 only, on the exam and on the fresh exam; int8 waits for M1).

**M1 — Jev-compatible local answerer.** Status 2026-11-04: built and measured; default int8 per-channel, option fp32, GitHub releases (see "M1 result").
- Export int8 ONNX.
- Run it in Node.
- Accept `{state, model, questions}`, return `{p, model}`.
- Measure size and latency in Node.

**M2 — Wire into rwxmap** (see "The flow": engines, two-question call, lowering flag; rwxmap owns the ask marker).
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
- Licence: Apache-2.0, matching rwxmap (user, 2026-11-03).

## Publishing (user, 2026-11-04)

- rwxlite is published publicly on npm as `rwxlite`, so rwxmap can `import { loadAnswerer } from 'rwxlite'`. The name was free on 2026-11-04 (registry 404).
- The tarball holds only src/, types/, README, LICENSE, CHANGELOG (14 files, 34.8 kB packed and 110.1 kB unpacked by `npm pack --dry-run`, with the entity table). Model files are not in it; they come from GitHub releases (`m1/release-assets.mjs`).
- `publish.yml` is manual (Run workflow), OIDC trusted publishing, no token in CI.
- Done by the user on 2026-11-04: the name is reserved with a placeholder `rwxlite@0.0.1` (`npm view rwxlite version` shows 0.0.1), and the npm Trusted Publisher is configured for hamr0/rwxlite, workflow `publish.yml`.
- The real code ships as the next release version through the `publish.yml` "Run workflow" button (no token). The model files go to the GitHub release via `m1/release-assets.mjs`.
- **Release order (the model files must be on the release before npm has the version):** 1. merge `m1` into `main`; 2. create the GitHub release `v<version>` with the assets from `node m1/release-assets.mjs` (manifest.json, manifest-exact.json, vocab.txt, model-int8-pc.onnx, model-fp32.onnx); 3. then "Run workflow" for `publish.yml`. The workflow enforces step 2: it fails before publishing if the release or any of those five assets is missing, if any asset is zero-size, or if the release's `manifest.json` `version` differs from package.json.

## Round 10 (planned 2026-11-04; trained, exam #3 NO-GO, not released)

User decisions, 2026-11-04 (written before training; round 10 has since been trained and scored, see findings "Round 10 trained" and "Exam #3 result"). rwxmap reports R1 and R2 both FAILED tuning (2026-11-04, the D100 bar for rules that only tighten): every right move was workos (the source vendor); with workos left out neither closed a leak, and each added wrong moves elsewhere (R1 on files.com PATCH /api_key; R2 on okta's sign-out page settings, GET/PUT .../pages/sign-out/customized). So there are **no new rule names**: `credential-set` is the only one to train on, R1/R2 are no longer an open question, and leans are rebuilt from current rwxmap as-is.

**Inputs**
1. **Leans from current rwxmap.** Rebuild the lean class + rule of every training row from today's rwxmap, so the model sees today's rule names. `credential-set` (step 2, PUT/PATCH only, class x, D130/D131, commit 41cdc55, 2026-11-03 17:15) came after the training data was built (`data/train/train.jsonl`, 16:10). `data/m0/mechanical.jsonl.gz` (123,339 ops, regenerated 23:24) already has it on 32 ops; training rows carry 0 (they carry 10 rule names: method, floor-post, method-floor, method-delete, read-verb, cant-undo-verb, modify-verb, read-verb-anywhere, modify-verb-summary, cant-undo-verb-summary). Measured today on those 32 (findings, "Round 10 pre-measure"): the model has never seen the name.
2. **Relabel the leak shapes (truth label only).** Counted with `m1/round10-shapes.py` over train + val + v3eval (87,657 + 4,180 + 5,716 rows):
   - credential replace on PUT/PATCH, last non-parameter path segment in api-key, client-credentials, token, secret, integration-token (singular or plural): **59 rows** (train 44, val 4, v3eval 11), 57 labelled w, 2 x. 58 carry lean `w method-floor`, 1 carries `x cant-undo-verb`; none carries `credential-set` yet (after the rebuild some will; count then). Exam truth is x (clause b).
   - logout / signout / sign-out / end-session / log-off in the path or operationId, any method: **45 rows** (train 39, val 1, v3eval 5): POST 34, DELETE 6, GET 5. Labels: x 39, w 4, r 2; the 5 GET rows are labelled w or r. Truth is x.
   **The leak shapes are workos-specific, not a cross-vendor pattern** (rwxmap, R1/R2 tuning; logout rows at other vendors are already x). So the pattern must NOT relabel anything by itself: every matched row gets a hand/labeller check, and only rows judged x by BRIEF-v3 change. Expect few changes. Known false positives of the patterns: files.com PATCH /api_key (credential pattern) and okta's sign-out page settings, GET/PUT .../pages/sign-out/customized (logout pattern). Pattern hits are candidates in `data/round10/` (gitignored), not final labels. Rows from val/v3eval that are relabelled leave the tuning role: decide below.
3. **Add pending labelled rows.** The burned fresh exam (`data/exam-2026-11-03-fresh`: truth.csv + ops.csv + rulings.csv, 949 rows; all added as training rows with their truth, workos included, which is how the workos shape is learned) and round 9 hand labels (`data/r9-hand`, 1,200 rows). Exam #3 vendors stay untouched (rwxmap's spares: clerk, neon, supabase, mux, netbird, ory, novu). Check that no exam #3 vendor is in either set before merging.
4. **QUERY augmentation.** Copy about 10% of GET rows (train has 42,581; about 4,250 rows), stratified by label and vendor, with method set to QUERY and the same label, so the model learns QUERY behaves like GET. After the retrain, measure GET vs QUERY agreement on held-out rows (argmax changes, rows crossing 0.97) and decide whether to keep the QUERY-to-GET mapping in `src/text.js`. **Decision (user ruling 2026-11-04): the mapping in `src/text.js` STAYS.** A QUERY op gets exactly the GET answer, deterministic. Measured (findings, 2026-11-04 "GET vs QUERY"): dropping it gains no accuracy and adds small p shifts near 0.97. Revisit when real QUERY ops appear in a labelling round. Exam #3 `ops.csv` has 0 QUERY rows, so the choice cannot affect it.

**Order**
1. Rebuild leans from current rwxmap (no R1/R2 names). 2. Hand-check the leak shapes (the pattern finds candidates only; every match is hand checked, and only rows judged x change; R1/R2 failed, so no pattern relabel; files.com PATCH /api_key and okta .../pages/sign-out/customized are known false positives). 3. Merge items 3 and 4. 4. Train on the home server sandbox `~/rwxlite-train` with the same recipe as r8soft (soft targets; reasons to change are stated here if any). 5. Refit T on val. 6. Re-export int8-pc + fp32 and repeat the int8 parity. 7. New model sha and model string (the string must change with the weights).

**Step-1 numbers (2026-11-04, `m1/round10-build.py`; outputs in gitignored `data/round10/`)**
- Lean rebuild: 28 rows change, all `w/method-floor -> x/credential-set` (train 22, val 2, v3eval 4); 0 text-format or path mismatches (old leans reproduce the stored text exactly). Of the 32 `credential-set` ops in the dump, 28 are in the splits.
- Duplicate operations across specs (same vendor token, method, path, operationId): 0 groups split across train/val/v3eval, so no split leak. Within a split: train 1 group, v3eval 316 groups (1,993 removable extra rows; github 150, spotify 86, microsoft 80 groups). Label disagreement inside a group: 0.
- Fresh exam rows: 949 new (workos 269, coolify 321, resend 142, getlago 217; labels r 406, w 328, x 215); no vendor or op overlap with the splits, no exam #3 vendor, 0 `credential-set` leans.
- r9 hand labels: 1,200 rows (train 1,074, val 126); 36 differ from the current label (w->x 32, w->r 4).
- QUERY sample: 4,258 of 42,581 GET train rows (labels r 4,142, w 116), 411 of 555 GET vendors.

**Decisions (2026-11-04)**
1. **r9 overrides apply to TRAIN rows only** (1,074 rows). The 126 val rows keep their current labels.
2. **Hand check has decoys.** `data/round10/handcheck-blind.csv` = the 104 candidates + 30 decoys (134 rows, same columns, shuffled with a fixed seed). Decoys: non-candidate TRAIN rows, 6 each of GET/POST/PUT/PATCH/DELETE, none from a candidate vendor. The private key `handcheck-key.csv` (id, is_decoy, shape, current_label) is never shown to labellers; decoys measure labeller accuracy against current labels. Labellers get only `handcheck-BRIEF.txt` (BRIEF-v3, r/w/x, "Unsure -> x", output `id,label`).
3. **The `credential-set` guard stays for good.** Round 10 trains with the same rewrite `src/text.js` applies: the lean rule `credential-set` is written as `cant-undo-verb` in the model text (`LEAN_RULE_ALIASES`). The one Python copy is `m1/round10_aliases.py`, imported by the assembly; `test/aliases.test.js` asserts it equals the table parsed from `src/text.js`. `train/common.py` is not edited. QUERY copies keep `QUERY` in the text. **Inconsistency to resolve:** `src/text.js` still maps QUERY to GET at inference, while round 10 trains on QUERY text. After round 10, the QUERY-to-GET mapping is measured (GET vs QUERY on held-out rows) and likely removed.
4. **v3eval is reported both raw and deduplicated** (one row per op group, the 316 groups / 1,993 extra rows above). Scoring code comes later.

**Step-4 assembly plan** (final assembly, not built yet)
1. Start from `data/train/train.jsonl`; take leans for every row from `mechanical.jsonl.gz` (joined on id), then apply `round10_aliases.text_rule` to the rule before `fmt_text`; check that the text of unchanged rows is byte-identical.
2. Apply the hand-check relabels (only rows judged x by BRIEF-v3; train rows only for training, val/v3eval relabels do not count toward a pass).
3. Apply r9 overrides to the 1,074 train rows only.
4. Add the 949 fresh rows with their truth and today's leans (aliased).
5. Add the QUERY copies (4,258 GET train rows, method QUERY, same label, `QUERY` kept in text).
6. Assert: no exam #3 vendor, no id duplicates, `credential-set` never appears in a text, alias check passes. Keep val and v3eval as rows (not trained on).

**Hard constraint.** Round 10 must finish BEFORE shared exam #3 is pre-registered. Exam #3's prereg must commit the predict and score code with it (fresh-exam lesson, findings "Note on the fresh exam's pre-registration").

**Open questions**
- The QUERY sample size (10% proposed).
- Whether to keep the val/v3eval split as-is, given that relabelled and added rows touch it. Proposal: keep the vendor split, relabel inside it, and do not use the relabelled val/v3eval rows to claim a pass.

## Round 11 (planned, 2026-11-04)

Exam #3 (rwxmap shared exam, 7 vendors, 1,377 ops; scored once, now burned; both sides agreed it may be used for training) gave r10 a NO-GO on rwxlite's gate: 15 too-loose of 1,226 answered (1.22%, bar 0.5%), essentially the same as 0.2.0 (14). The 15 leaks are mechanical's own leaks that the model agreed with: credential/identity replace (clerk PUT email_address/phone_number, POST remove_password; ory PUT admin/keys/{set}, self-service recovery/verification), billing/subscription (netbird aws marketplace activate, PUT subscription; supabase PATCH billing/addons; clerk PUT beta_features/domain), mux analyze-structure jobs read as r, mux PUT mp4-support, ory GET logouts x2. Round 10's workos-only shape fixes did not generalise. Round 11 trains on the exam's own labels so the model sees these shapes at several vendors.

**Recipe: round 10's, unchanged.** Soft targets, `--alpha 0.7`, 1 epoch, same base (all-MiniLM-L6-v2), `--ckpt 250`, `--threads 4`, tag `r11`. One change to the data only: add the 1,377 exam #3 rows with their truth label at normal weight. **No upweighting**, so any change versus r10 is attributable to the added rows; a weighting variant (x_weight or row repeats on the leak shapes) can follow as its own round. val and v3eval are unchanged (byte-identical to round 10's).

**Inputs**
1. **Base** = round 10's assembled splits (`data/round10/{train,val,v3eval}.jsonl`, sha256-checked against `assembly-sha256.txt`; train 92,864 / val 4,180 / v3eval 5,716).
2. **Added rows**: `ops.csv` (sha256 `fff7afa9...d790`) + `truth.csv` (sha256 `929725d5...b3c0`, header `id,label`) from rwxmap `data/exam3-2026-11-04/`, read in place, 1,377 rows, vendors clerk, neon, supabase, mux, netbird, ory, novu; labels from 2 blind labellers plus user rulings. Ids `ex3-NNNN`.
3. **Leans: rwxmap at 46235ea** (the commit exam #3 was scored with; `src/` is byte-identical to current rwxmap HEAD c2b60d2, and classifying all 1,377 ops with either gives the same output, sha256 `2016c94f...`). This is what round 10's recipe implies ("leans rebuilt from current rwxmap" via `classifyRow`, `m1/round10-classify.mjs`), and it is also the lean the model saw at exam time. Rules go through the shipped alias (`credential-set` is written `cant-undo-verb` in the text, `m1/round10_aliases.py`); text is `train/common.fmt_text`, equal to the shipped `formatText` (checked: the text of all 1,377 rows equals the `text` the model was given at exam time, `data/exam3/inputs.jsonl`). QUERY-to-GET is moot: exam #3 has 0 QUERY ops.
4. **Targets: one-hot.** rwxmap committed no Jev p per row for exam #3 (`score/rows-c-jev.csv` holds Jev's letter and evidence, not p), so the rows are `tier none`, `status fresh`, `jev_p None`: one-hot of the truth, as round 10's 949 fresh-exam rows and round 9's hand rows. Nothing was asked of rwxmap.

**Assembly** (`m1/round11-assemble.py`, deterministic; outputs in gitignored `data/round11/`, sha256 in `assembly-sha256.txt`): base rows untouched, then the 1,377 rows appended to train. Asserts (all must pass): no duplicate ids; no op-key group (vendor token, method with QUERY as GET, path, operationId) spanning splits; exam #3 rows only in train, none in val/v3eval; no exam #3 vendor in val, v3eval or round 10's train; `credential-set` in no text; val, v3eval and round 10's train rows unchanged.

**Gate and order.** Exam #3 is burned: it cannot score round 11 (or anything trained on it). The next gate is a **new exam #4**: vendors TBD with rwxmap (never used in training or in exam #3), prereg with the predict and score code committed before scoring (fresh-exam lesson). **Round 11 must finish BEFORE exam #4's prereg.** Then, as in round 10: refit T on val, re-export int8-pc + fp32, repeat the int8 parity, new model sha and model string.

**Training.** Home server `~/rwxlite-train/r11` (new dir; r10 is never touched), command as round 10: `HF_HOME=~/rwxlite-train/hf-cache nohup ~/rwxlite-train/.venv/bin/python train/finetune.py --epochs 1 --soft --alpha 0.7 --tag r11 --threads 4 --ckpt 250 > data/train/finetune-r11.log 2>&1 &`.

**Caveat.** r11 cannot be judged on exam #3 (trained on it); val/v3eval cannot show the effect either (different vendors). Until exam #4 the only evidence is that val/v3eval do not regress.

**Outcome (2026-11-05).** Exam #4 (the shared exam, scored once) was NO-GO for r11 under both scorers: rwxlite's `a_none` 1447 right against 0.2.0's 1448, and the rwxmap CLI `secondPass` 18 too loose against 16. The prereg named the wrong gate config (`a_none` is not the shipped rule), so the gate number is rwxmap's CLI. Round 12 (S0/S1/S2: label fixes, D136 relabels, exam #4 rows, generated variants) gave no gain over shipped 0.2.0 on the held-out goharbor+render rows (0.2.0 425/9/21 right/loose/tight). 0.2.0 stays shipped. Detail: `docs/wiki/findings.md` (Exam #4 result, Round 12), `docs/wiki/exam-prereg-exam4.md`, `docs/wiki/prereg-r12.md`.

## Round 13 (2026-11-07; R13 did not pass exam #5, 0.2.0 stays, nothing released)

**Status (2026-11-07).** R13 did not pass exam #5 (frozen bar, `docs/wiki/prereg-exam5.md` section 11): it passes the standalone half but fails the product path on exact (1,220 vs 1,272). 0.2.0 stays the shipped model, nothing is released, and exam #5 is burned (training data only). The paragraph below is the status before the exam.

**Status (2026-11-06).** Three candidates were trained on all labelled data under the shared BRIEF-v4 labels; the frozen val pick chose **R13 (plain), T 0.991463**. Only R13 sits exam #5. Exam #5 now waits for rwxmap's mechanical v4 (see Next steps); there is no pool count or vendor list yet. No release, push or PR yet; branch `dev` is unpushed. 0.2.0 stays the shipped model. Contract and numbers: `docs/wiki/prereg-r13.md` (frozen); learnings: `docs/wiki/findings.md` ("Round 13 data built and pre-registered", "Round 13 val pick").

**Decision trail.**
1. **D137 (both users, 2026-11-05/06; BRIEF-v4 lives in rwxmap).** Access grants or widening = x; narrowing stays w; an ambiguous access set/replace is x by doubt; non-access policies stay w. Five seams are x: API key/token create, access-widening toggles, webhooks to outside URLs, creating a login user, adding a member.
2. **Labelling scope.** Only rows labelled w were relabelled (the 29,327 unique w operations), by rwxmap's pipeline: Jev's five factual questions plus a code rule, a blind Sonnet check of every row (including the gap close), user rulings, and a vendor cross-check. Final export: rwxmap `95104e3` (`export-v4-gap`). Our 29,327 w ids came out w 22,727 / x 6,029 / r 1, plus 570 inherited variants.
3. **All-data training.** 102,668 train rows; 6,245 labels changed from S0 (6,244 w to x, 1 w to r). Everything is used for training, including the old exams, gates, holdout and v3eval; no vendor is held out, so there is no internal held-out check. Generated variants are not trained on.
4. **Three candidates, same data and recipe (soft targets, alpha 0.7, 1 epoch).** R13 plain; R13-L3 (too-loose mistakes cost 3x, `train/losscost.py`); R13-L3-t2 (plus text format 2, a versioned access hint in `src/text.js`, manifest `textFormat`; 0.2.0 output is unaffected).
5. **Val pick (frozen rule: fewest too-loose on the product path).** R13 74, R13-L3 78, R13-L3-t2 85 too loose on val (4,180 rows): **R13 picked**. The run had a documented two-run procedural deviation (format-2 val for t2); the prereg was not changed. The label fix did the work; the too-loose penalty and the hint added nothing on the product path.

**Next steps.**
1. **Exam #5 (update 2026-11-06, from rwxmap).** rwxmap's user ruled that exam #5 waits until rwxmap's mechanical v4 is delivered (rwxmap plan steps 2-5: rebuilding the mechanical rules against BRIEF-v4 truth for PUT/PATCH x-extraction, POST, GET, DELETE). Reasons: exam #5 is scored once for both projects, scoring now would burn it on the v3 mechanical that is about to be replaced, and the unseen-vendor pool (vendors unseen in `data/v4/rwxlite-providers.csv`) is too thin for an exam #6. There is no pool count or vendor list yet. When mechanical v4 is ready, rwxmap draws and pre-registers the exam, and mode a runs R13 on top of mechanical v4.
2. Score R13 once. Bar (frozen, unchanged): R13 vs shipped 0.2.0 at T 0.844, both on the same mechanical v4 for the rwxmap path (CLI `secondPass`), plus standalone (model-only, unaffected by mechanical); no more too-loose and no fewer exact on both. R13 was picked on val using the v3 mechanical replica; the pick stands and the exam decides. If not met, 0.2.0 stays.
3. Ship decision (user and rwxmap), then release order per Publishing.

**Open decisions.**
- Whether text format 2 ships in the next release. The code is merged on `dev` but unused unless a manifest sets `textFormat: 2`; R13 (format 1) is the picked candidate.
- The release version number (not chosen; no version has been cut).

## Open questions

- **After the M0 NO-GO (2026-11-03).** Options: (1) round 9, a targeted retrain on the two failure shapes (POST creates that move money, start jobs or restore data; credential PUT/PATCH), then a fresh exam; (2) make "ask at p" part of the product and pre-register it as the go/no-go on a fresh exam; (3) accept and move to M1. Any fresh exam needs vendors never used in training; the exam vendors are burned and the remaining locked vendors belong to rwxmap's pre-registered split, so the vendors are agreed with rwxmap first. **Chosen: option 2** (see "Option 2"); the round-9 retrain is skipped. The fresh exam has since been run (coolify, workos, lago, resend; NO-GO by one row, see "Fresh exam result"). Still open: what to do about the confident non-lowering mistakes (credential upserts, logouts), which needs a new fresh exam with new vendors, and whether bareguard prompts on x (decides what too-tight costs).

- **Which small encoder.** all-MiniLM-L6-v2 first, bge-small-en-v1.5 second, TF-IDF + LR as baseline; the bars decide.
- **Model string.** What exact string rwxlite returns in `{p, model}`, and how it is versioned. rwxmap records the model string on every moved verdict (D88), so it must change whenever the weights change.
- **Distribution form.** Resolved 2026-11-04: code in npm, weights from GitHub releases on hamr0/rwxlite, downloaded by rwxmap on first use (latest), cached per `rwxlite-<semver>+<sha8>/`, sha256-checked. See "M1 result", Decisions.
