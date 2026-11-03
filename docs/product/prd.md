# rwxlite — PRD

Status: contract, round 6 signed off; M0 exam NO-GO (too loose); fresh exam NO-GO by one row (5 vs 4 too-loose rows); next step open. Date: 2026-11-03.

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

## Open questions

- **After the M0 NO-GO (2026-11-03).** Options: (1) round 9, a targeted retrain on the two failure shapes (POST creates that move money, start jobs or restore data; credential PUT/PATCH), then a fresh exam; (2) make "ask at p" part of the product and pre-register it as the go/no-go on a fresh exam; (3) accept and move to M1. Any fresh exam needs vendors never used in training; the exam vendors are burned and the remaining locked vendors belong to rwxmap's pre-registered split, so the vendors are agreed with rwxmap first. **Chosen: option 2** (see "Option 2"); the round-9 retrain is skipped. Open: the fresh-exam vendors (asked of rwxmap), and whether bareguard prompts on x (decides what too-tight costs).

- **Which small encoder.** all-MiniLM-L6-v2 first, bge-small-en-v1.5 second, TF-IDF + LR as baseline; the bars decide.
- **Model string.** What exact string rwxlite returns in `{p, model}`, and how it is versioned. rwxmap records the model string on every moved verdict (D88), so it must change whenever the weights change.
- **Distribution form.** npm package with the ONNX file, or a separate download. Decided in M1.
