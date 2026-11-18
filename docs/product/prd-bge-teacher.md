# PRD: bge-base as a teacher for MiniLM (round 14)

Status: draft 2026-11-18. Part of the rwxlite PRD (`docs/product/prd.md`). Background and facts: `docs/wiki/findings.md`, section "2026-11-18".

## 1. Goal

Find out whether model size is what holds rwxlite back on unseen vendors. If it is, get that gain into the small shipped model by distillation, keeping 23 MB int8 and about 17-20 ms per operation.

## 2. Why

- R13 (MiniLM, 22.7M parameters) scores about 97% on validation, which holds rows like its training data.
- On unseen vendors it scores about 90% (rwxmap exam #6, mode a: 1,434 / 1,588 = 90.3%).
- There are two possible causes. Either the model is too small to generalize, or new vendors differ from the training data and only more varied data fixes that.
- Past gains came from labels (the round 13 relabel), not from loss changes. The R13-L3 too-loose penalty did not help: val too loose 78 vs 74 for R13, and more too tight.
- Model size has never been tested.

## 3. Plan

1. **Train bge-base.** Model: BAAI/bge-base-en-v1.5 (about 109M parameters, 12 layers, hidden size 768). Data: the round 13 data. Recipe: the R13 recipe unchanged (soft targets, `--alpha 0.7`, 1 epoch, batch size 32, learning rate 5e-5, max_len 128, seed 1). Only the base model changes.
2. **Compare with R13.** Use the round 13 validation set (4,180 rows) and rwxmap's real decision rule (mode a, `LOWER_MIN_P` 0.90, rwxmap's replay script as used in `poc/cutoff-r13`). Each model uses its own temperature, fitted on val by the same procedure that produced R13's T 0.991463. R13 itself stays at its shipped T. Also report mode b at confidence 85 and standalone argmax, as information only.
3. **Distill (only if step 2 passes).** Train a MiniLM student (all-MiniLM-L6-v2) whose soft targets are the bge-base teacher's probabilities, mixed with the hard label as in the recipe. The exact mix is fixed in that step's own prereg, before training. Then compare the student with R13 using the same rule.
4. **Add exam rows (later, separate round).** Add exam #5 and #6 rows as training data. A scored exam may be training data only.
5. **Judge.** A fresh exam #7, shared with rwxmap, is the only ship judge.

## 4. The "better" rule (pre-registered, fixed before training)

A candidate counts as better than R13 only if, on validation through rwxmap mode a at 0.90, both hold:

- too loose is no higher than R13's, and
- right is at least 1 percentage point higher than R13's (about 42 of 4,180 rows).

R13's reference on val at 0.90, from rwxmap's cut sweep (`docs/wiki/findings.md`, cut table): 3,938 right / 87 too loose / 155 too tight. Step 2 recomputes this with the same script. If the recomputed numbers differ, use them and say so.

If bge-base fails the rule: stop. Size is not the bottleneck, and there is no distillation.

This PRD's commit is the prereg. The rule cannot change after training starts.

## 5. Server and resource rules

Home server: ahassan@192.168.178.180. Use the sandbox `~/rwxlite-train` only and touch nothing else there.

Facts measured 2026-11-18: 4 CPU cores, 15 GB RAM (about 12 GB free), no GPU, load about 0.1. Other services run on it (for example immich).

Rules:

- Run at lowest priority: `nice -n 19` and `ionice -c3`.
- Use `--threads 3`, so one core is always free.
- One training at a time.
- Own run directory: `~/rwxlite-train/r14-bge/`.
- Resume from checkpoints.
- Use `nohup` like earlier rounds (the user's systemd linger is off).
- Watch memory. If free memory drops under 2 GB, stop and re-plan.
- Leave no background process after the run finishes.

Estimate: R13 took about 50 minutes on 4 threads. bge-base is about 8 times the compute per row, so about 9-12 hours on 3 low-priority threads. This is an estimate; measure it from the first checkpoint.

## 6. Code changes needed

Each change is its own small commit, reviewed by the usual /self-review then /branch-review.

- `train/finetune.py` gets a `--base` argument. The default is all-MiniLM-L6-v2, so the R13 recipe is unchanged when it is not passed. (Today `BASE` is hard-coded.)
- Step 3 needs a way to train on teacher probabilities.
- No change to `src/` (the shipped Node code) is expected for steps 1-2.
- bge-base is expected to use the same uncased BERT WordPiece vocabulary as MiniLM. Verify this in step 1 by comparing the vocab files. If they differ, record it. It matters only if bge-base itself were shipped.

## 7. Non-goals

- Shipping bge-base itself (too big and slow by default; maybe later as an option).
- ModernBERT (its different tokenizer would need a new Node port).
- Pruning (little gain on CPU for a model this small).
- New loss penalties.
- Any exam data in this round.
- Any Jev or paid calls.

## 8. Status

Draft 2026-11-18. Next: the `--base` change, then the step-1 training run.

2026-11-18 step 2: **FAIL** under section 4 (val, mode a, 0.90): too loose 94 vs R13's 87, right 3,944 vs 3,938 (+6 rows, +0.14 pp, needs +1 pp). Per section 3: stop; no distillation. Details in `docs/wiki/findings.md` (2026-11-18 Round 14 step 1-2).

## 9. Step 3 addendum: distillation (pre-registered 2026-11-18, before any student training)

**Why.** Step 2 FAILED the section 4 rule (mode a, 0.90: too loose 94 vs 87, right +6 rows). That verdict stands and is not edited. On 2026-11-18 the user decided to run distillation anyway, because a 5-point mode-b sweep on val (information, outside the step-2 rule; table in `docs/wiki/findings.md`, "2026-11-18: Mode-b sweep") showed r14-bge better than R13 at every confidence: right is higher and too loose is equal or lower at 95, 90, 85, 80 and 75. Val is the selection set, so this alone proves nothing; it is the reason to test whether a MiniLM student can inherit the gain, and exam #7 stays the ship judge.

**Recipe (fixed now).** Teacher: the r14-bge checkpoint (`ckpt-r14-bge/final`), run over the round 13 `train.parquet` (same text column, max_len 128), softmax probabilities at T = 1, float32, row order = train.parquet, with the sha256 of train.parquet recorded beside them. Student: all-MiniLM-L6-v2, the R13 recipe unchanged except that the per-row soft target is the teacher's probability vector instead of `common.soft_targets()`: loss = 0.7 * soft CE + 0.3 * hard CE (`--alpha 0.7`), 1 epoch, batch size 32, learning rate 5e-5, max_len 128, seed 1, x_weight 1.0. Code: `train/teacher_probs.py` and `train/finetune.py --teacher PATH.npy`. Server rules are section 5 (nice 19, ionice idle, 3 threads, one job at a time, memory watch), run dir `~/rwxlite-train/r14-student/`.

**Student rule (fixed now, before any training).** The student passes only if, on val (4,180 rows), against R13-b1 (R13 torch fp32 batch-1 path, the same scoring path the student is scored on; produced by `m1/r14-compare.py` and `m1/r14-compare.mjs`), ALL hold:

- (a) mode b at confidence 85: too loose <= 70 AND right > 3,901;
- (b) mode b at confidence 90: too loose <= 46 AND right > 3,824;
- (c) mode a at 0.90: too loose <= 86.

R13-b1 references: mode b 85 = 3,901 / 70 / 209; mode b 90 = 3,824 / 46 / 310; mode a 0.90 = 3,941 / 86 / 153 (right / too loose / too tight).

The student temperature is fitted on val by the same `temp_fit` procedure as R13 and r14-bge. If the student fails any of (a)-(c): stop, R13 stays. If it passes: it is a candidate only, nothing is shipped or decided on val; exam #7 (fresh, shared with rwxmap) is the ship judge (section 3, step 5).
