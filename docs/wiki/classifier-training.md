# How rwxlite's classifier is trained and how it answers

Plain-English notes, written 2026-11-03. Some parts describe the plan rather than what's built: the JSON wrapper is M1 work, and the call shape is a proposal agreed in principle with rwxmap. The contract is in docs/product/prd.md, and measured results are in findings.md.

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
- **Our plan:** 1–2 epochs. More passes risk memorizing the rows instead of learning the pattern.

### 7. Check on rows it has never seen
About 10% of vendors are held out of training. After training, we score the model on them:
- **If it does well,** it has learned the pattern.
- **If it does well on training rows but badly on held-out vendors,** it has memorized, which is called **overfitting**.

The final test is a single, one-time score on rwxmap's 2026-09-22 exam (ruling D128).

### 8. Shrink it
After training, each weight is stored as an 8-bit number instead of a 32-bit one. That's **post-training dynamic int8 quantization**, the Cactus-like part:
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

### JSON only
The model itself outputs just three numbers. A small Node wrapper (M1) turns those into Jev's exact JSON format, so rwxmap sees no difference:

```json
// request (same as Jev's)
{ "state": { "method": "POST", "path": "/v1/search", "operationId": "search",
             "summary": "Search records", "description": "" },
  "model": "rwxlite-0.1.0",
  "questions": { "isX": "<the a7bc855 question text>" } }

// answer (same shape as Jev's)
{ "answers": { "isX": { "noul": 0.04 } },
  "model": "rwxlite-0.1.0+<weights-hash>" }
```

There's no free text, no explanations and no chat, which also makes it fast and predictable.

Two differences from Jev:
- **No network:** it runs inside rwxmap's own process, in milliseconds.
- **The question text is checked, not read:** the wrapper confirms it's one of the three known questions. If the wording doesn't match what the model was trained on, the wrapper refuses instead of guessing.
- **The state stays 5 fields:** the wrapper computes the mechanical letter and rule itself, via rwxmap's classifyRow, so rwxmap's src/jev.js only swaps the client.

### Standalone use (mode b, outside rwxmap)
```json
{ "letter": "r", "p": { "r": 0.91, "w": 0.07, "x": 0.02 }, "model": "rwxlite-0.1.0+<hash>" }
```
That's the form API providers or guardrails like bareguard would use. A low top probability becomes the "ask a human" signal, and the threshold for that is the caller's choice. Exact field names are settled in M1 with rwxmap.

## Training on the home server

Sandbox: `ahassan@192.168.178.180:~/rwxlite-train/` (Fedora, 4-core i3-8100T, CPU only, venv at `.venv`, torch CPU, transformers 5.0.0). Nothing outside that dir is touched. Only `train/*.py` and `data/train/{train,val,v3eval}.parquet` are copied there (no exam, gate labels, keys or .env).

- Check: `ssh ahassan@192.168.178.180 'tail -3 ~/rwxlite-train/data/train/finetune-r6full.log'`
- Resume (re-run, it loads `ckpt-r6full/last.pt`): `ssh ahassan@192.168.178.180 'cd ~/rwxlite-train && HF_HOME=~/rwxlite-train/hf-cache setsid nohup .venv/bin/python train/finetune.py --epochs 1 --tag r6full --threads 4 --ckpt 250 > data/train/finetune-r6full.log 2>&1 < /dev/null &'`
- Stop: `ssh ahassan@192.168.178.180 'kill $(cat ~/rwxlite-train/r6full.pid)'`
- Pull results: `rsync -a 'ahassan@192.168.178.180:rwxlite-train/data/train/{finetune-r6full*,probs-r6full*,ckpt-r6full}' data/train/`

Speed: about 1 step/s on the server (2740 steps, ETA about 45 min).
