# How rwxlite's classifier is trained and how it answers

Plain-English notes, written 2026-11-03. Some parts describe the plan rather than what's built: the int8 export and the JSON wrapper are M1 work, and the call shape is a proposal agreed in principle with rwxmap. What exists today is the fp32 model (MiniLM r8soft, trained with soft targets), scored on two exams; both missed the go/no-go. The contract is in docs/product/prd.md, and measured results are in findings.md.

## Part 1: How training works

This is **supervised fine-tuning for text classification**, also known as **knowledge distillation**: a big, slow teacher (Jev plus the mechanical rules) teaches a small, fast student.

### 1. Start from a model that already reads English
MiniLM (sentence-transformers/all-MiniLM-L6-v2) was already trained by its makers on a huge amount of text. It turns a sentence into numbers that capture meaning, so "remove a user" and "delete an account" come out close together. It has about 22 million adjustable numbers, called **weights**, but it knows nothing about r/w/x yet.

We bolt a tiny new part on top, called a **classification head**. It takes the model's reading of the text and turns it into three scores, one each for r, w and x. The head starts out random.

### 2. Show it an example
Each training row is one operation turned into a line of text, with the "leaning" (the mechanical letter and rule) first so it is never cut off:

```
lean: x floor-post | POST /v1/payment_intents | op: createPaymentIntent | sum: Create a payment | desc: ...
```

The model reads it and makes a guess, for example r 10%, w 60%, x 30%.

### 3. How it "knows what is right"
It doesn't know. We tell it. Every row carries the answer from the round-6 recipe, meaning the mechanical rules plus Jev's moves. That answer is the **label**. The model can only become as good as the labels it copies, which is why the labels were first checked against human-labelled fresh samples. Gate-2 passed at 96.5% exact.

From round 8 the target is soft rather than a single letter. Where Jev gave a probability (for example "70% chance this is x"), the row's target is that spread over r, w and x, built from the stored Jev answers (`soft_targets()` in `train/common.py`). Rows with no Jev answer (DELETE, credential rule, rows outside the Jev piles) keep a one-hot target. The loss mixes both: 0.7 x soft cross-entropy + 0.3 x hard cross-entropy against the round-6 letter. Hard labels had pushed p(x) on PUT/PATCH rows to about 0, so no threshold could ever raise the true-x ones; soft targets fixed most of that (too-loose rows 108 to 73 on the practice rows).

### 4. Measure how wrong the guess was
A formula called the **loss** (cross-entropy) compares the guess with the label:
- If the label is x and the model gave x only 30%, the loss is large.
- If it gave x 95%, the loss is small.

### 5. Change the weights
This step is the actual learning:
- **Backpropagation** works out, for each of the 22 million weights, whether nudging it up or down would have made the loss smaller, and by how much.
- **Gradient descent** then moves each weight a tiny step in the helpful direction. The size of the step is set by the **learning rate**.

Each single step is tiny on purpose, so one example can't wreck what the model already knows.

### 6. Repeat
- **A batch:** the model sees about 32 rows at once, averages their losses, and does one weight update. That's one **step**.
- **An epoch:** one pass over all the training rows (87,657 rows is about 2,740 steps).
- **What we ran:** 1 epoch (2,740 steps, about 50 minutes on the home server). More passes risk memorizing the rows instead of learning the pattern.

### 7. Check on rows it has never seen
About 10% of vendors are held out of training. After training, we score the model on them:
- **If it does well,** it has learned the pattern.
- **If it does well on training rows but badly on held-out vendors,** it has memorized, which is called **overfitting**.

The final test is a single, one-time score on rwxmap's 2026-09-22 exam (ruling D128). It was run on 2026-11-03 and was a NO-GO: 95.9% exact, but 0.84% too loose against a 0.5% line. A second, fresh exam (949 operations from coolify, workos, lago and resend, scored once with the ask rule below) was also a NO-GO, by one row: 5 too-loose answers (0.57%) against a line of 4. See findings.md.

### 8. Shrink it
*Planned (M1), not built yet: every number above and in findings.md is the fp32 model (90.9 MB, about 22-28 ms per operation).* After training, each weight is stored as an 8-bit number instead of a 32-bit one. That's **post-training dynamic int8 quantization**, the Cactus-like part:
- **Size:** about 90 MB down to about 23 MB.
- **Speed:** faster on a CPU.
- **Accuracy:** usually drops only slightly, and we measure that.

The model ships as one ONNX file, run in-process by onnxruntime-node, with no server and no GPU. GGUF/llama.cpp is not used, because it targets chat-style models.

### "Two passes in one model"
Because the mechanical letter is part of the input, the model can learn two things:
- **Agreeing is usually right:** when mechanical says r on a GET, r is almost always correct, so it learns to agree.
- **When to overrule:** when mechanical says x on a POST but the text reads like `/search`, it learns to move to r.

Nobody writes those rules by hand. The model finds them by having its weights nudged across thousands of examples where the labels did exactly that.

### What kind of training this isn't
- **Not training from scratch.** We start from a model that already reads English.
- **Not chat-model fine-tuning.** It never writes sentences, it only picks among three answers.
- **Not reinforcement learning.** There's no trial-and-error with rewards, only "here's the right answer, adjust".

A simpler **baseline** is trained alongside it: TF-IDF word counts plus logistic regression. It's tiny and fast, and if it clears the bar it's a valid option.

## Part 2: How it answers — Jev's three shapes, JSON only

### The three shapes
| Tier | Method | Question | Answer key | What p means |
|---|---|---|---|---|
| lower | POST | "is this x?" (full version, criteria-x.mjs) | `isX` | chance it's x |
| raise-wx | PUT/PATCH | "is this x?" (x-only version, criteria-x-raise.mjs) | `isX` | chance it's x |
| raise-get | GET | "does this change anything?" (criteria-changes.mjs) | `changes` | chance it's w or x |

Round 6 adds a fourth use: on POST, the `changes` question decides whether a row lowered from x lands on w or r (the two-step lower).

The model doesn't need a separate brain for each shape. It always produces three probabilities, r, w and x, and every shape is just arithmetic on them:
- `isX` = p(x)
- `changes` = p(w) + p(x)

So one model, one file, and one pass answers every shape.

### Turning probabilities into answers, and when to ask
The model only reports three probabilities. Three steps sit between those and a verdict, all measured but not yet built into a product (they live in `train/tune_cuts.py`, `train/exam_score.py`, `train/lowerflag.py` and `train/fallback.py`):

- **Calibration.** The raw probabilities are over-confident, so they are divided by a temperature (T = 0.844 for r8soft, fitted on held-out vendors) before use.
- **Cuts (mode a).** Mechanical stays in charge and the model only makes Jev's one-step moves on the contested rows, at cuts tuned on practice rows only: lower 0.30, POST lowered rows go to r when p(w) + p(x) is under 0.40 (else w), raise-wx 0.15, raise-get 0.05. A narrow credential rule forces x.
- **Lowering flag (the ask rule).** When the model moves a letter down (x to w or r, w to r) it is trusted only if its top probability is at least 0.97; otherwise the row is "ask". Raises and keeps are trusted. On the practice rows 57 of the 73 too-loose answers were lowerings, which is why the flag targets them. Earlier ask rules (ask under a confidence bar, fall back to the mechanical letter, a mix) were measured and are in findings.md.

rwxlite itself never decides to ask. It returns probabilities, and rwxmap applies the rule and emits the flag (PRD, "The flow"). Confident mistakes that are not lowerings, for example credential updates the mechanical rules already call too safe, are not caught by any of this; that is what failed the fresh exam.

### JSON only
The model itself outputs just three numbers. A small Node wrapper (M1) turns those into Jev's exact JSON format, so rwxmap sees no difference:

```json
// request (same as Jev's)
{ "state": { "method": "POST", "path": "/v1/search", "operationId": "search",
             "summary": "Search records", "description": "" },
  "model": "rwxlite-0.2.0",
  "questions": { "isX": "<the a7bc855 question text>" } }

// answer (same shape as Jev's)
{ "answers": { "isX": { "noul": 0.04 } },
  "model": "rwxlite-0.2.0+<weights-hash>" }
```

There's no free text, no explanations and no chat, which also makes it fast and predictable.

Two differences from Jev:
- **No network:** it runs inside rwxmap's own process, in milliseconds.
- **The question text is checked, not read:** the wrapper confirms it's one of the three known questions. If the wording doesn't match what the model was trained on, the wrapper refuses instead of guessing.
- **The state stays 5 fields:** the wrapper computes the mechanical letter and rule itself, via rwxmap's classifyRow, so rwxmap's src/jev.js only swaps the client.

### Standalone use (mode b, outside rwxmap)
```json
{ "letter": "r", "p": { "r": 0.91, "w": 0.07, "x": 0.02 }, "model": "rwxlite-0.2.0+<hash>" }
```
That's the form API providers or guardrails like bareguard would use. A low top probability becomes the "ask a human" signal, and the threshold for that is the caller's choice. For lowerings the measured threshold is 0.97 (see above); a plain confidence bar alone only caught about half the dangerous mistakes on the first exam. Exact field names are settled in M1 with rwxmap.

## Part 3: Rounds, exams and preregs — what we've been doing

### 1. What rwxlite answers
For every API operation (say `GET /users` or `DELETE /users/{id}`) we want one letter:
- **r**: only reads, safe.
- **w**: changes something, but you can undo it.
- **x**: dangerous or irreversible.

There are three ways to get that letter:
1. **The mechanical rule.** Look at the HTTP method: GET gives r, DELETE gives x, and so on. It is free, but it misses things, for example `GET /logout` is a GET yet it changes something.
2. **Jev.** The big model. It is good, but not free.
3. **rwxlite.** Small, free, runs locally, and learned by copying Jev's answers.

The goal: rwxlite beats the mechanical rule, for free, so Jev isn't needed.

### 2. Rounds
A **round** is one training attempt with a new set of examples.
- **0.2.0** is the published model.
- **r10** is round 10: more examples, and cleaner ones.
- **r11** is r10's examples plus the 1,377 exam #3 operations with their correct answers.

### 3. Exams
A training score proves little, because the model has already seen those rows. It is like memorising the homework and then being graded on the homework.

An **exam** uses vendors the model never saw. Two labellers answer each operation blind, and the answers they agree on are the answer key.

Each answer lands in one of three outcomes:
- **Right.**
- **Too loose:** the model said safe, but it was dangerous. This is the bad one.
- **Too tight:** the model said dangerous, but it was safe. Annoying, not harmful.

A model may also "ask" (abstain) instead of answering.

### 4. Prereg (pre-registration)
Before anyone sees the answer key, we commit in writing which models are tested, how they are scored, and what counts as passing. It is like writing "I'll be happy with 8/10" before the test.

The predictions are frozen too: we commit their sha256 (a fingerprint of the file) before the answer key is opened. Think of it as answers in a sealed envelope. Nobody can tweak them after seeing the key.

### 5. The held-out experiment (A/B/C)
Details are in docs/wiki/holdout-r11.md. The question: does adding exam rows to training help on unseen vendors, or does the model just memorise them?

1. We hid two vendors, ory and clerk (442 operations).
2. We trained three versions: **A** (new rows, used normally), **B** (new rows counted 5 times), **C** (continue from 0.2.0 on the new rows plus a sample of old ones).
3. We tested all of them on the 442 hidden operations, using exam #3's answer key.

Result (GONOGO_lba097):

| Model | Right | Too loose |
|---|---|---|
| 0.2.0 | 340 | 7 |
| A | 338 | 7 |
| B | 347 | 7 |
| C | 343 | 7 |
| r10 | 337 | 9 |

All five were NO-GO. The same 7 too-loose rows showed up for 0.2.0, A, B and C, for example ory `GET /self-service/logout` and `GET /oauth2/sessions/logout`.

Lesson: more of the same data nudges accuracy up, but it doesn't fix the dangerous mistakes.

### 6. Exam #4
Seven new vendors, 1,505 operations, one question: is r11 better than 0.2.0?

The gate (rwxmap's D135): r11 replaces 0.2.0 only if it has no more too-loose answers and no fewer exact ones (mode a, fp32). Ties pass. The prereg is docs/wiki/exam-prereg-exam4.md.

### 7. Where we stand against the goal
On the 442 held-out operations, when the model must always answer (a_none):
- **Mechanical:** 336 right, 9 too loose.
- **0.2.0:** 383 right, 15 too loose.

So rwxlite gets more right than the mechanical rule, but makes more dangerous mistakes. That is the gap.

If the model is allowed to ask (GONOGO_lba097), it makes only 7 too-loose mistakes, but it hands 51 operations back.

## Training on the home server

Sandbox: `ahassan@192.168.178.180:~/rwxlite-train/` (Fedora, 4-core i3-8100T, CPU only, venv at `.venv`, torch CPU, transformers 5.0.0). Nothing outside that dir is touched. Only `train/*.py` and `data/train/{train,val,v3eval}.parquet` are copied there (no exam, gate labels, keys or .env).

- Check: `ssh ahassan@192.168.178.180 'tail -3 ~/rwxlite-train/data/train/finetune-r6full.log'`
- Resume (re-run, it loads `ckpt-r6full/last.pt`): `ssh ahassan@192.168.178.180 'cd ~/rwxlite-train && HF_HOME=~/rwxlite-train/hf-cache setsid nohup .venv/bin/python train/finetune.py --epochs 1 --tag r6full --threads 4 --ckpt 250 > data/train/finetune-r6full.log 2>&1 < /dev/null &'`
- Stop: `ssh ahassan@192.168.178.180 'kill $(cat ~/rwxlite-train/r6full.pid)'`
- Pull results: `rsync -a 'ahassan@192.168.178.180:rwxlite-train/data/train/{finetune-r6full*,probs-r6full*,ckpt-r6full}' data/train/`

Speed: about 1 step/s on the server (2740 steps, ETA about 45 min).
