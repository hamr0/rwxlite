# Pre-registration: round 16 small comparison runs (2026-11-21)

**Status: written BEFORE any run.** Nothing in this document has been trained or scored except the base 0.4.0 student on dev (section 5.5, no training involved). The commit that contains this file precedes the first training start. No exam is touched: dev is a fixed unseen-vendor set, never exam #8.

Parent documents: `docs/product/prd-r16-vendor-data.md` (sections 6, 7, "Dev set", "Teacher training set v1/v2"), `docs/wiki/prereg-r15.md` (recipe, scorer, server rules), `docs/wiki/findings.md` ("Fine-tuning learnings carried into round 16", "Check 1").

## 1. Questions and user decisions (fixed)

- Continue from the r15 bge teacher; the MiniLM student starts from the r15 student (the 0.4.0 model), not from the base checkpoints. Teacher data `data/r16/train/teacher-train-v2.parquet` (sha256 `9e1f37003cca905ef1cb869fb59bba480abbf0a9f86dce22133b77543e8a1870`), weights in the `weight` column.
- **Q1 (teacher, old-row replay).** The 60k replay as built (20% of the old rows) against ALL old rows (302,211 minus 41 exam #8 vendor rows = 302,170; same rwxmap corrections and weights).
- **Q2 (student soft targets).** The current 0.7 soft CE + 0.3 hard CE on the teacher's T=1 probabilities, against the same loss on a **softened teacher** (section 3.3).
- Dev set `data/r16/labels/final/final-labels-r16-dev-v2.parquet` (4,475 rows, 214 vendors, unweighted, sha256 `ef5955787e88e5d4b4ceeaaf93de35026c678c67b86d51e710b275a7534e6e69`). Scored on (a) all 4,475 rows and (b) the frozen unseen-route subset (section 5.2). **If (a) and (b) disagree on the winner, (b) decides.**
- Decision rule mirrors the ship gate (user 2026-11-20): exact >= base, too loose <= base + 1.0 pp (section 7).
- Server: nice 19, ionice -c3, 3 of 4 threads, one job at a time, memwatch kills under 2 GB free, CPU only, own new directories only. No GPU.

## 2. Inputs (sha256 computed 2026-11-21)

| file | sha256 |
|---|---|
| `data/r16/train/teacher-train-v2.parquet` (360,536 rows) | `9e1f37003cca905ef1cb869fb59bba480abbf0a9f86dce22133b77543e8a1870` |
| `data/r16/train/teacher-train-v2-allold.parquet` (602,317 rows; made by `r16/build_teacher_train.py --old-pool all`, section 3.1) | `b3f2ab0a2784312a7ef8e6c562227db93bf387fb8c696d04e5caf931bb541abf` |
| `data/r16/small/set-A.parquet` (35,999 rows) | `26f102b83d01662da242efcb671e80eda52715ee96465f27336f37840869850e` |
| `data/r16/small/set-B.parquet` (60,177 rows) | `c89a66b5747a5dc3f0ff0e41ec43572ed7fbce4e1e139d19e8d3f1a531ae7d7c` |
| `data/r16/small/manifest.json` (counts, seeds, input shas) | `70d7998d8ba2aa2a0b8a40effa67b15b7354a799859167dfb006d742155cd620` |
| `data/r16/labels/final/final-labels-r16-dev-v2.parquet` | `ef5955787e88e5d4b4ceeaaf93de35026c678c67b86d51e710b275a7534e6e69` |
| `data/r16/labels/work/mech.jsonl` (dev model input text, mechanical letter/rule/review) | `0600957b7c581bed19e81c8db0bfb2cce4f288621836c69905ed02a8db869fe4` |
| `r16/dev-subset-b-ids.txt` (frozen subset (b), 3,286 ids) | `10375671d69e3a71b793bccb638bef9ccf78eea8c8c72d0446279b437d401997` |
| `data/round15/val.parquet` (4,180 rows; used only to fit each candidate's T) | `c54ee4612f6c93ac4ac800c8ef08c6fd2c1b415184a28d483401fd067c14d949` |
| `data/round15/v3eval.parquet` (only `finetune.py`'s end report reads it) | `831499b6ed627f6f71420659f71d7a3a56a624bc5b78b26f75e504e49290392a` |
| r15 bge teacher `model.safetensors` (server `~/rwxlite-train/r15-teacher/data/train/ckpt-r15-teacher/final`; findings.md) | `d53deafc13190f6c4807ca360b0de438828728680ee248abee93ce9d1457b741` |
| r15 student = shipped 0.4.0 `model.safetensors` (`data/round15/models/R15-student`) | `e431763878ffaec9753b94ef5d26ebe4227eaea432d132637307673f9e2061d9` |

## 3. Arms and training sets

### 3.1 The all-old variant

`r16/build_teacher_train.py --old-pool all` reuses the v2 builder unchanged for everything else: it takes ALL old rows of `data/round15/train.parquet` (not only the 60k replay + 394 extra-ruled), applies the same four rwxmap answer files in the same order with the same overlap rule, the same weights (rwxmap-ruled rows 1.0, D143-changed rows 3.0, otherwise the r15 weight), drops exam #8 vendor rows (41 old rows in all: 5 in the replay, 36 outside), and exits right after writing `teacher-train-v2-allold.parquet` (no dev, summary or SHA256SUMS side effects; its sha is in `SHA256SUMS-allold`). Result: 602,317 rows = 302,170 old (replay-r13 20,378, replay-r15 39,617, old-r13 82,249, old-r15 159,926) + new 299,600 + holdout 400 + exam #7 147; letters r 316,234 / w 117,200 / x 168,883; weight total 647,615.3. The v2 file was not rebuilt (its sha above is unchanged); the 60k pool rows are asserted identical (label, weight, text) in both files.

### 3.2 The two small training sets (scale 1/10, same ratios as the full runs; `r16/build_small_runs.py`, seed 16, deterministic, checked by a rebuild)

| | set-A (20% replay arm) | set-B (all-old arm) |
|---|---|---|
| new rows | 29,960 (10% uniform row sample of 299,600) | the same 29,960 |
| old rows | 6,039 = 10% of the 60,389 v2 old rows, stratified by part (replay-r13 2,038, replay-r15 3,962, extra-ruled 39) | 30,217 = those 6,039 + 24,178 random old rows from the rest (10% of 302,170; stratified by r13/r15 source). B contains A |
| total rows / steps at batch 32 | 35,999 / 1,125 | 60,177 / 1,881 |
| letters r / w / x | 17,714 / 8,228 / 10,057 | 31,617 / 11,693 / 16,867 |
| weights 0.3 / 1.0 / 3.0 (rows) | 363 / 33,218 / 2,418 | 363 / 57,396 / 2,418 |
| weight total | 40,580.9 | 64,758.9 |

Left out of both sets (identical in both arms, added in the full runs): the 400 holdout rows and the 147 exam #7 mistake rows. No exam #8 vendor row is in any set. Dev rows share no exact (K1) key with any training row (asserted in the v2 builder); the looser K2 overlap is handled by subset (b) (section 5.2). The only difference between the two Q1 arms is therefore the extra 24,178 random old rows, which is exactly what "ALL old" adds to "20% replay" at this scale (the replay is not random: all hard tiers, access rows and a random remainder, so A is enriched in hard rows, B dilutes them).

### 3.3 Q2: the softened teacher, one concrete variant

Findings, Check 1 (2026-11-20): the r15 teacher's mean top probability is 0.9766 on its own training rows and 0.9762 on unseen val, so the soft targets were not "near one-hot because of in-sample scoring"; the teacher itself is over-confident (val-fitted T **1.36**, exactly 1.362087 on the 4,180-row val) and the student copied it (val-fitted T 1.385, shipped 1.3832; its mean top 0.9749 against the teacher's 0.9762). Hypothesis tested here: giving the student targets that are already calibrated should remove that inherited over-confidence at no cost in accuracy.

**Softened variant (S1):** the teacher's probabilities at T=1 (`train/teacher_probs.py`, unchanged) are divided in log space by the teacher's own val-fitted temperature, `q = softmax(log p / 1.362087)` (`r16/soften_probs.py`; identical to `softmax(logits / 1.362087)` because log p differs from the logits only by a constant). Loss unchanged: `0.7 * soft CE + 0.3 * hard CE` on `q`, row weights as given, alpha untouched. Justification: it is the single fix that findings names first ("dividing the teacher's scores by its val-fitted T"); it changes one number and nothing else; 1.362087 is a measured value, not a tuned one; it is the value that makes the teacher calibrated on val, so a student that matches it should land at a fitted T near 1.0 instead of 1.38. **Caveat, stated now:** the full run will use the NEW teacher's own val-fitted T (recorded when that teacher exists), not 1.362087; the small run tests the idea, not the number. Check 1 also showed in-sample and held-out confidence are equal on val, so out-of-fold teacher scoring is not tested (it would cost 2 to 3 times the teacher time and Check 1 predicts no gain).

**Teacher for the Q2 student runs: the r15 teacher** (unchanged, section 6), scoring set-A at T=1. Reason: Q2 is then independent of Q1, no teacher has to be re-trained first, and the r16 new rows (about 83% of set-A) are rows the r15 teacher has never seen, which is the case where softening should matter most.

### 3.4 Arms

| arm | model | start | training set | soft target | scored against base |
|---|---|---|---|---|---|
| **tA** (Q1) | bge-base teacher | r15 teacher | set-A | none (hard-label weighted CE) | r15 teacher |
| **tB** (Q1) | bge-base teacher | r15 teacher | set-B | none (hard-label weighted CE) | r15 teacher |
| **sS0** (Q2) | MiniLM student | r15 student (0.4.0) | set-A | r15 teacher probs at T=1 | 0.4.0 |
| **sS1** (Q2) | MiniLM student | r15 student (0.4.0) | set-A | the same probs, softened at 1.362087 | 0.4.0 |

The teacher arms have no `--teacher` file: with one-hot soft targets the r15 loss reduced to plain weighted CE, and `finetune.py` without `--teacher` computes exactly that (`hard_i`, then multiplied by `weight`). The r15 teacher also used Jev soft targets on 71k of the R13 rows; the r16 set has no soft targets for old rows (the builder drops them: labels changed since), so the old rows are hard here. This is a deliberate change from r15, the same in every arm.

## 4. Exact commands (training code unchanged since the r15 launch: `train/finetune.py` sha256 `6e54a3c3d7f3e6fdab527a0935c1a1ad8d7aecd05272d303294f73f1995163ef`, `train/common.py` `061da692...`, `train/teacher_probs.py` `e49fa903...`)

Common to every run: `--row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 2e-5 --max_len 128 --threads 3 --ckpt 250`, seed 1, shuffle seeds `100 + epoch`, warmup 6% then linear decay to 0 (fresh schedule, `finetune.py` default). **lr 2e-5 is the findings value (item (c), lower than r15's 5e-5 for a continued model); it is the same in every arm and is not itself tested here.** Row order = `set-X.parquet` order (sorted by id). Wrapped by `r16/small-runs.sh` (copy of the `m1/r15-train.sh` mechanics: nohup-less foreground phase, nice 19, ionice idle, memwatch).

```
# tA / tB   (dir ~/rwxlite-train/r16-small/tA or tB; data/train/train.parquet = set-A / set-B)
python train/finetune.py --base BAAI/bge-base-en-v1.5 --init $R15_TEACHER_FINAL --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 2e-5 --max_len 128 --threads 3 --ckpt 250 --tag r16-tA     # r16-tB
# probsA    (dir .../probsA; data/train/train.parquet = set-A)
python train/teacher_probs.py --ckpt $R15_TEACHER_FINAL --out data/train/teacher-r15-on-setA.npy --threads 3
# soften
python r16/soften_probs.py --in data/train/teacher-r15-on-setA.npy --T 1.362087 --out data/train/teacher-r15-on-setA-soft1362087.npy
# sS0 / sS1 (dir .../sS0, .../sS1; data/train/train.parquet = set-A; the .npy copied next to it)
python train/finetune.py --init $R15_STUDENT_FINAL --teacher data/train/teacher-r15-on-setA.npy  --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 2e-5 --max_len 128 --threads 3 --ckpt 250 --tag r16-sS0
python train/finetune.py --init $R15_STUDENT_FINAL --teacher data/train/teacher-r15-on-setA-soft1362087.npy ... --tag r16-sS1
```

Setup per arm dir (new, empty directories only): `train/{finetune,common,losscost,teacher_probs}.py` and `r16/soften_probs.py` from the repo, `data/train/train.parquet` = the set, `data/train/val.parquet` and `v3eval.parquet` = the two files of section 2; sha256 of every copied file verified against this document before the start.

## 5. Scoring

### 5.1 Code (`r16/predict_dev.py`, `r16/score_dev.py`, `r16/secondpass_real.mjs`; shas in section 10)

1. `predict_dev.py` writes raw logits, PyTorch fp32 CPU, **batch 1**, max_len 128, for dev (text = `mech.jsonl` text, the model input of the r15 holdout scorer) and for val.
2. Each candidate's T = bounded minimiser of the val NLL on [0.3, 5] (`score_dev.py --val-pred`, as `temp_fit` in `m1/r14-compare.py`; checked: it returns 1.38322 for the 0.4.0 student, whose shipped T is 1.3832). **Base models keep their own T, never refitted**: 0.4.0 student 1.3832; r15 teacher 1.362087.
3. Mode a = rwxmap's REAL `secondPass` (tree of rwxmap commit 1c25be1, `LOWER_MIN_P` 0.90, credential-set never lowered) fed pIsX = p(x), pChanges = p(w)+p(x) at the run's T, mechanical verdicts from rwxmap's `classifyOperations`. The Python replica of `r15/r15_holdout_score.py` is computed alongside and its disagreement count is reported (0 of 4,475 for the 0.4.0 student).
4. Exact / too loose (predicted letter lower than truth, order r < w < x) / too tight, as counts and percent. Reported for mode a (**the primary**), standalone argmax (T does not change it) and mechanical alone, on (a) and (b). The decision uses **mode a**. dev truth = v2 labels.

### 5.2 Frozen subset (b)

Rule: dev v2 rows whose K2 key (method upper, path with `{..}` to `{}` lower-cased without trailing slash, operationId; `r16/opkey.py` `k2`) matches no row of any training set a run can use. Instead of one subset per run, ONE subset is frozen against the **union** of `teacher-train-v2`, `teacher-train-v2-allold` and `data/round15/train.parquet`, so the same rows are clean for both Q1 arms, for the full runs and for the 0.4.0 / r15 bases, and the comparison stays paired. Counts: v2 alone leaves 3,361 rows (1,114 overlap, the number in the PRD); the all-old file overlaps 1,189 (union = all-old, since v2 is contained in it); **frozen subset (b) = 3,286 of 4,475 rows**, a conservative subset of every per-run subset (the small sets are samples). `r16/make_dev_subset.py` regenerates it byte for byte and refuses to overwrite a different list.

### 5.3 D143 readout for rwxmap (information, never a decision input)

Too-tight rate (and exact and too loose) on POST create rows with truth **before** D143 (dev v1 = the `prior_label` column) and **after** (dev v2 = `label`; D143 changed 7 dev labels w to x, 2 stay w). POST create rows are picked mechanically from the row's own fields, not from labels: method POST and the first word of the operationId or of the summary (camelCase split, lower case) is one of add, book, create, insert, make, new, place, register, reserve, schedule, submit. That picks 466 of the 4,475 dev rows (319 in subset (b)). Also reported separately: the 9 rows rwxmap's D143 dev answers touched (`label_source == rwxmap`; 5 in subset (b)). Computed for mode a and standalone, in both scopes.

### 5.4 Paired counts

`score_dev.py --vs OTHER-rows.csv` adds "this right, other wrong" / "other right, this wrong" on mode a for (a) and (b), so a difference of a few rows can be read against its discordant count.

### 5.5 Base scores already produced (2026-11-21, laptop, no training; 0.4.0 student, fp32 batch 1, T 1.3832, real secondPass at 0.90)

| scope | n | mode a exact | too loose | too tight | standalone exact / loose / tight | mechanical exact |
|---|---|---|---|---|---|---|
| (a) all dev | 4,475 | 4,216 (94.212%) | 52 (1.162%) | 207 (4.626%) | 4,310 (96.313%) / 123 (2.749%) / 42 (0.939%) | 86.771% |
| (b) subset | 3,286 | 3,066 (93.305%) | 40 (1.217%) | 180 (5.478%) | 3,146 (95.740%) / 106 (3.226%) / 34 (1.035%) | 85.910% |

D143 readout for the 0.4.0 student, mode a. POST create rows: (a) n 466, too tight before 70 (15.02%), after 65 (13.95%); (b) n 319, before 54 (16.93%), after 52 (16.30%). The 9 touched rows: (a) too tight 7 of 9 before, 2 of 9 after (exact 2 to 5, too loose 0 to 2); (b) 5 rows, too tight 4 before, 2 after. Val-fitted T of this run's logits: 1.38322 (matches the shipped 1.3832). Files: logits `data/r16/scratch/small/base-student-dev.csv` sha256 `65965a8896962300295e70393721f6c1b36f7c62cc9acf8520f85786fa8c8c82`, result JSON `base-student-score.json` sha256 `e3ff53790aec0bb948c94c33702775bfbb0775b35a2527fadb9f1ec0b237868e` (a second scoring run is byte-identical).

**The r15 teacher base is NOT produced yet:** its checkpoint is on the server only (no copy found on the laptop). It is needed for the Q1 floor and has to be copied read-only or scored once on the server (open question 1).

## 6. Run order (one job at a time, server phases through `r16/small-runs.sh`)

0. Laptop, before anything: base teacher scored (needs the r15 teacher checkpoint, open question 1), T fixed at 1.362087.
1. **tA** (server). Copy `final` to the laptop; `predict_dev.py` on dev and val; `score_dev.py`.
2. **tB**, same. Q1 decided by section 7 after both are scored.
3. **probsA**, then **soften** (server, same dir).
4. **sS0**, then **sS1**. Scored on the laptop like the teachers (student base 0.4.0, section 5.5).
5. Q2 decided by section 7. The full teacher starts only after the user has seen both decisions (section 9).

No run starts before this document is committed. A failed or killed phase resumes from `last.pt`; a phase that changes any number above is stopped and reported, not patched. One run per arm, no repeats and no variance estimate: single-seed noise is handled by the tie rule below, not hidden.

## 7. Decision rule (written before results)

Applies separately to Q1 (tA, tB against the r15 teacher) and Q2 (sS0, sS1 against 0.4.0); all numbers are mode a, fp32, batch 1, each candidate at its own val-fitted T, each base at its fixed T.

1. **Floor, per arm, on (b)** (this mirrors the D135/D142 ship rule): exact >= base exact AND too loose <= base too loose + floor(1% of 3,286) = base + **32 rows** (1.0 pp). For the 0.4.0 student base this is exact >= 3,066 and too loose <= 72 rows. (On (a) the same rule gives exact >= 4,216 and too loose <= 52 + 44 = 96; (a) is reported, it never overrules (b).)
2. **The winner of a question is the arm that passes the floor with the higher exact on (b).**
3. **Tie** = the two arms' exact on (b) differ by 5 rows or fewer (0.15 pp, about the size single runs can move by noise). Ties are broken in this order: (i) fewer too-loose rows on (b), if the difference is 3 rows or more; (ii) the **default arm**: Q1 the 20% replay (set-A: about 1.7 times cheaper, keeps the weight on new vendors, the plan already approved); Q2 the current 0.7/0.3 on T=1 targets (no change without evidence).
4. If only one arm passes the floor it wins; if neither passes, **no automatic choice**: the result is reported to the user with the numbers of both arms and the default arm is recommended only if its exact on (b) is the higher or tied.
5. (a) and (b) disagree on which arm wins: (b) decides; the disagreement is reported.
6. Information, never decision inputs: standalone argmax numbers, the D143 readout (section 5.3), fitted T (for Q2 the prediction is that sS1 lands clearly below 1.38; a student at T below about 1.1 is "calibrated"), paired counts, the mechanical reference.
7. A candidate that passes the floor on the r15-base is NOT thereby a ship candidate: these runs choose the recipe for the full runs. Only exam #8, once, decides shipping.

## 8. Wall time (estimates; CPU, 3 threads, nice 19, from r15 and round 13/14 timings)

| run | rows | steps | basis | estimate |
|---|---|---|---|---|
| tA | 35,999 | 1,125 | r15 teacher: 9,445 steps in 801.3 min = 5.09 s/step | **about 95 min** + end eval of `finetune.py` about 8 min = **1.7 h** |
| tB | 60,177 | 1,881 | same | 160 min + 8 = **2.8 h** |
| probsA | 35,999 | forward only | 26.5 rows/s measured on r15 texts (labelling pass, same server) | **about 23 min** |
| soften | | | numpy | under 1 min |
| sS0 | 35,999 | 1,125 | round 13 student: 3,209 steps in 63.1 min = 1.18 s/step (the r15 student's own time is not in the logs; r15 texts are shorter, so this is an upper estimate) | about 22 min + eval = **0.5 h** |
| sS1 | 35,999 | 1,125 | same | **0.5 h** |
| **server total** | | | | **about 5.5 h** (6 h with copying and checks) |
| laptop scoring | | | MiniLM batch 1 about 1 min for the 4,475 dev rows on 3 threads (rough, from file times); bge-base about 8 times that, 4,475 + 4,180 rows about 15 min per teacher | tA, tB, base teacher about 45 min; students 5 min |

**Full-size runs would not be a comparison:** one teacher arm on 360,536 rows (the 20% replay) is 11,267 steps = **15.9 h**, and on the all-old set 602,317 rows (18,823 steps) **26.6 h**, i.e. 43 h for the pair, which is more than the full teacher itself. So the small runs use 1/10 of the data with the same ratios.

What the 1/10 scale loses: (1) the absolute level; these runs predict which option wins, not the final score (findings (e)); (2) the effect of volume: 30k new rows with 1,125 steps at lr 2e-5 may move the model less than 300k new rows with 11k steps, so an advantage that needs more steps may not show; (3) a replay-versus-all effect that grows with the number of new-row steps (forgetting) is understated; (4) with the replay at 6k rows the stratified parts are small (39 extra-ruled rows); (5) one seed per arm. What is kept: the new:old ratios 1:0.2 and 1:1.0, the replay's hard-row enrichment, the weights, the recipe, the dev set.

## 9. After the small runs

1. Report to the user: both decisions, the numbers, anything that failed the floor or the tie rule. The user confirms before the full teacher.
2. **Full teacher** (new prereg section or `docs/wiki/prereg-r16.md`): continue from the r15 teacher on `teacher-train-v2.parquet` (Q1 = 20% replay, 11,267 steps, about 16 h) or on `teacher-train-v2-allold.parquet` (about 27 h), plus its own go/no-go against the r15 teacher on val and on the dev set. The 400 holdout rows are in that training file, so they cannot be a check any more (open question 3).
3. **Teacher probabilities** over the full train set (360k rows at 26.5 rows/s = 3.8 h, or 6.3 h for all-old), softened (Q2) with the new teacher's OWN val-fitted T if S1 won.
4. **Full student** from the r15 student, about 3.8 h (7 h all-old), val floor guard against 0.4.0, same dev scoring.
5. **Exam #8 through rwxmap**: scored once, the real CLI, mode a at 0.90, fp32 exact model at batch 1, D142 (exact >= base, too loose <= base + floor(1% of rows)), base 0.4.0 at its shipped T 1.3832, the candidate at its own val-fit T; predict and score code and prediction sha256s committed before the truth is revealed (as r15). Nothing here is a release.

## 10. Code (sha256 at commit time)

| file | sha256 |
|---|---|
| `r16/score_dev.py` | `17c599e34a0a18254800969cd466a113ce0b1d012d07570bbf6421fa07c43496` |
| `r16/predict_dev.py` | `d8a212ea46c846389638e30f426abe0bf85a7f9d7c647eb67790dff596467a76` |
| `r16/secondpass_real.mjs` | `d4a055d8b1b8cfbaa73644b1557a0eefb3e8e693395e409a04e63afb1aeadd38` |
| `r16/make_dev_subset.py` | `d3f46e9d1cbd334d531dd72b368c869162f2c1dff59780b6205794e02e0c17d6` |
| `r16/build_small_runs.py` | `f780cc5668f60b9226a8e39639e1745d60f86880c3035b301d82f6b2ce11cf4d` |
| `r16/soften_probs.py` | `a69a4d3271ef39e5a6298b0a1645c139d5f2ebe3d4be3a050624183ec51908d2` |
| `r16/small-runs.sh` | `876a1b8e9b0664efda8a265a01e347f8631fb58c539fc82ac5eb058702690a79` |
| `r16/build_teacher_train.py` (with `--old-pool`) | `0db2cd91037999ad361830a338778815a9bfd943c9d42fa03a1ff66230549951` |
| `r16/dev-subset-b-ids.txt` | `10375671d69e3a71b793bccb638bef9ccf78eea8c8c72d0446279b437d401997` |

`score_dev.py` asserts the sha256 of the dev file, `mech.jsonl`, the subset list and val before scoring, and records its own sha256 and the prediction file's in every result JSON.

## 11. Open questions for the user (each with a recommended answer; none blocks committing this document)

1. **r15 teacher checkpoint for scoring the Q1 base.** Not on the laptop. Recommended: copy it read-only from `~/rwxlite-train/r15-teacher/.../final` (438 MB, verify sha256 `d53deafc...`) and score it on the laptop; this touches the server only for one read. Alternative: score it on the server (about 30 min of one job slot).
2. **Hard labels for old rows in the teacher.** The r15 teacher used Jev soft targets on 71k R13 rows; r16 uses hard labels for all old rows (labels changed, builder drops the soft columns). Recommended: keep hard, same in every arm.
3. **The 400 holdout rows are in `teacher-train-v2`** (and were the r15 teacher's go/no-go check). Recommended: for the full teacher use the dev set plus val as the check and keep the holdout in training only if the user accepts that the 400 rows can no longer be an unseen check; otherwise train the full teacher on `teacher-train-v2` minus part `holdout` (one filter, no rebuild).
4. **lr 2e-5** is taken from findings and is the same in all arms; it is not tested. Recommended: accept; a single extra arm (tA at 5e-5) costs 1.7 h if the user wants it answered.

## 12. Small runs started (2026-11-21, after the commit of this document; nothing above was changed)

- **Start:** 2026-11-21 22:51:10 (server clock, CEST). Chain `r16/small-runs-all.sh` (tA, tB, probsA, soften, sS0, sS1; each phase starts only after the previous one exited 0, a non-zero exit stops the chain). Server pid of the chain 1670913 (python of tA 1670917; memwatch per phase). All in `~/rwxlite-train/r16-small/<arm>/` (new dirs); the r15-teacher and r15-student dirs were only read.
- **Logs:** `~/rwxlite-train/r16-small/chain.log` (phase start, finish, exit codes), `<arm>/data/train/finetune-r16-<arm>.log` (progress), `<arm>/memwatch-<arm>.log` (lowest MemAvailable). Done markers `done-<phase>`.
- **Layout check:** `finetune.py` and `teacher_probs.py` read `data/train/{train,val,v3eval}.parquet` relative to the parent of their `train/` directory (`common.OUT`), so each arm dir holds its own `train/*.py` and `data/train/train.parquet` (tA, probsA, sS0, sS1 = set-A; tB = set-B). sha256 verified on the server before the start: set-A `26f102b8...`, set-B `c89a66b5...`, val `c54ee461...`, v3eval `831499b6...`, `finetune.py` `6e54a3c3...`, `common.py` `061da692...`, `losscost.py` `15361a92...`, `teacher_probs.py` `e49fa903...`, `soften_probs.py` `a69a4d32...`, `small-runs.sh` `876a1b8e...`; the r15 teacher and student `model.safetensors` match section 2 (`d53deafc...`, `e431763...`). The teacher npy files are copied by the chain from `probsA` into `sS0`/`sS1` `data/train/` before those phases.
- **No soft targets in tA/tB:** they run without `--teacher` and without `--soft`, so `soft` is None, the loss is the weighted hard CE (`hard_i` times `weight`) and `--alpha 0.7` is never used.
- **Measured step rate (tA):** 4.2 s/step (200 steps in 14.1 min; prereg estimate 5.09), memory: python RSS about 6.2 GB, lowest MemAvailable 6.06 GB, load about 3 of 4. New ETAs: tA 80 min + eval about 8 min (done about 00:25), tB 133 min + 8 (about 02:50), probsA about 23, sS0 and sS1 about 22 + 5 each (about 04:00 for the chain).
- **Q1 base (r15 teacher), laptop, fp32 batch 1, T fixed 1.362087, real secondPass at 0.90** (checkpoint copied read-only from the server, `model.safetensors` sha256 `d53deafc...` verified): (a) 4,475 rows: exact 4,243 (94.816%), too loose 50 (1.117%), too tight 182 (4.067%); standalone 97.832 / 1.743 / 0.425. (b) 3,286 rows: exact 3,085 (93.883%), too loose 37 (1.126%), too tight 164 (4.991%); standalone 97.596 / 1.887 / 0.517. Replica agrees on all 4,475 rows. Floor for Q1 on (b): exact >= 3,085 and too loose <= 69. Files: `data/r16/scratch/small/base-teacher-dev.csv` sha256 `b2f7946ba1b0bc247ed45d589a135a9c49ab190e6417acffe5bfa4fc9bc2f49b`, `base-teacher-score.json` sha256 `1c439034b3a37bfdebb4da7c9e2c7b1486a0dd3a0062857c0baacb92d606d6ea`. `r16/small-runs-all.sh` is new (the chain wrapper); `small-runs.sh` is unchanged.

## 13. Results (2026-11-22; sections 1 to 12 unchanged)

Scored once per arm, exactly as section 5 and 7: fp32 PyTorch CPU batch 1 (`r16/predict_dev.py`, system python with torch), each candidate at its own val-fitted T (golden-section on the 4,180-row val), real `secondPass` (rwxmap tree 1c25be1) at 0.90, `r16/score_dev.py` (sha256 `17c599e3...` = section 10; dev, mech and subset shas asserted by the scorer; `predict_dev.py` `d8a212ea...`, `secondpass_real.mjs` `d4a055d8...`, subset list `10375671...` verified equal to section 10 before predicting). The real secondPass and the Python replica agree on all 4,475 rows in every arm. Nothing was re-run, tuned or re-fitted. Prediction and model sha256s were committed BEFORE any score: `docs/product/r16-small-runs-pred-sha256.txt` (students in commit 1d1e3a4, teachers in the next commit). Score JSONs: `docs/product/r16-small-runs-scores/<arm>-score.json`. Checkpoints (gitignored) on the laptop under `data/r16/small/models/<arm>/final`, copied from the server read-only.

| arm | model.safetensors sha256 |
|---|---|
| tA | `0285ca483378beef139b946c3faab4ae728e8dd140ca0c54b00215d5fdcb3c26` |
| tB | `8f97abf057a8c0bab4c00892637b20db10fe9e93873b8ad9adaf311f2e98fb85` |
| sS0 | `2d7477c772faf8414f6ae38c3511c007365796e02b160c2c9a7509918a4198e8` |
| sS1 | `08a23f5124b12550492981bf28f8225d641cec511960d7d28917d764249c06bd` |

### 13.1 Q1 (teachers, against the r15 teacher base, T 1.362087)

Floor on (b): exact >= 3,085 and too loose <= 69. On (a): exact >= 4,243 and too loose <= 94.

| arm | T | (b) exact | (b) loose | (b) tight | (b) floor | (a) exact | (a) loose | (a) tight | (a) floor |
|---|---|---|---|---|---|---|---|---|---|
| base r15 teacher | 1.362087 | 3,085 (93.883%) | 37 | 164 | n/a | 4,243 (94.816%) | 50 | 182 | n/a |
| tA (set-A, 20% replay) | 1.8495 | 3,081 (93.761%) | 33 (1.004%) | 172 (5.234%) | **FAIL** (exact 4 below) | 4,240 (94.749%) | 45 | 190 | FAIL (3 below) |
| tB (set-B, all old) | 1.8896 | 3,064 (93.244%) | 34 (1.035%) | 188 (5.721%) | **FAIL** (exact 21 below) | 4,221 (94.324%) | 45 | 209 | FAIL (22 below) |

Decision (clause 4): **neither arm passes the floor, so there is no automatic winner.** Per the rule the result goes to the user with both arms' numbers. The default arm (tA, the 20% replay) may be recommended only if its exact on (b) is higher or tied: tA 3,081 against tB 3,064, a gap of 17 rows (more than the 5-row tie band), so tA is higher and the rule allows recommending it. tA misses the floor by 4 rows on (b) (3 on (a)), inside single-seed noise but not passing; both arms are too loose well within the limit (33 and 34 against 69). (a) and (b) agree on the ordering.

### 13.2 Q2 (students, against 0.4.0, T 1.3832)

Floor on (b): exact >= 3,066 and too loose <= 72. On (a): exact >= 4,216 and too loose <= 96.

| arm | T | (b) exact | (b) loose | (b) tight | (b) floor | (a) exact | (a) loose | (a) tight | (a) floor |
|---|---|---|---|---|---|---|---|---|---|
| base 0.4.0 | 1.3832 | 3,066 (93.305%) | 40 | 180 | n/a | 4,216 (94.212%) | 52 | 207 | n/a |
| sS0 (T=1 targets) | 1.4875 | 3,069 (93.396%) | 36 (1.096%) | 181 (5.508%) | PASS | 4,217 (94.235%) | 47 (1.050%) | 211 (4.715%) | PASS |
| sS1 (softened at 1.362087) | 1.1900 | 3,068 (93.366%) | 37 (1.126%) | 181 (5.508%) | PASS | 4,216 (94.212%) | 48 (1.073%) | 211 (4.715%) | PASS (exactly on the floor) |

Decision: both pass the floor. Clause 2 would take the higher exact on (b), but the two differ by 1 row, inside the tie band (clause 3, 5 rows or fewer). Tie-break (i): the too-loose difference is 1 row (36 against 37), under the 3-row threshold, so it does not apply. Tie-break (ii): the default arm. **Winner Q2: sS0 (the current 0.7/0.3 on T=1 targets), decided by clause 3 (ii).** (a) agrees (4,217 against 4,216, also a tie). Softening the targets gave no measurable accuracy gain.

### 13.3 Information only (decide nothing)

Standalone argmax, (b) exact / loose / tight (T does not change it): base teacher 97.596% / 1.887% / 0.517%; tA 3,199 (97.352%) / 53 / 34; tB 3,197 (97.292%) / 50 / 39; base 0.4.0 95.740% / 3.226% / 1.035%; sS0 3,154 (95.983%) / 89 (2.708%) / 43; sS1 3,152 (95.922%) / 93 (2.830%) / 41. On (a): tA 4,370 / 64 / 41; tB 4,370 / 62 / 43; sS0 4,319 / 104 / 52; sS1 4,317 / 108 / 50. The teachers' standalone exact on (b) is slightly below the base teacher's (97.35 / 97.29 against 97.60); the students' is slightly above 0.4.0's (95.98 / 95.92 against 95.74) with more standalone too-loose rows than the teachers.

Fitted T (val): tA 1.8495, tB 1.8896 (both far above the r15 teacher's 1.362, so the continued teachers are more over-confident, not less); sS0 1.4875; **sS1 1.1900**. The section 7 prediction held: sS1 lands clearly below 1.38 and below sS0 (1.49), and nearer 1.0, but it is just above the "calibrated" line of about 1.1. This calibration did not turn into dev accuracy.

D143 POST-create readout, mode a, too tight before D143 (dev v1) / after (dev v2), (b) n 319 | (a) n 466: base 0.4.0 54 (16.93%) / 52 (16.30%) | 70 (15.02%) / 65 (13.95%); base teacher not recorded in section 12 (the file `data/r16/scratch/small/base-teacher-score.json` holds it); tA 54 (16.93%) / 51 (15.99%) | 68 (14.59%) / 61 (13.09%); tB 61 (19.12%) / 58 (18.18%) | 77 (16.52%) / 70 (15.02%); sS0 60 (18.81%) / 57 (17.87%) | 78 (16.74%) / 72 (15.45%); sS1 59 (18.50%) / 56 (17.55%) | 77 (16.52%) / 71 (15.24%). The 9 rwxmap-touched rows (5 in (b)): after D143 too tight 2 of 9 in every arm (2 of 5 in (b)); before D143 9 of 9 (tA, tB) and 8 of 9 (sS0, sS1). The D143 relabel lowers too tight by about 1 pp in every arm; no arm fixes the POST-create too-tight problem (13 to 18% on (b)).

Paired against the base on (b) (mode a; this right, base wrong / base right, this wrong): tA 12 / 16; tB 12 / 33; sS0 16 / 13; sS1 14 / 12. On (a): tA 17 / 20; tB 18 / 40; sS0 18 / 17; sS1 16 / 16. So tB is clearly worse than the base teacher (net minus 21 on (b)), tA is within noise below it (net minus 4), and the students are within noise of 0.4.0.

Train loss (mean of the logged per-25-step values; per-step values are noisy and the arms use different losses, so only same-model arms are comparable): tA 0.108, tB 0.080 (last ten logged 0.108 and 0.071); sS0 0.148, sS1 0.210 (sS1's soft cross-entropy has a higher floor because its targets are softer). Training time: tA 91.0 min, tB 153.4 min, sS0 16.0 min, sS1 15.8 min. Finetune end-of-run val accuracy: tA 94.50, tB 94.74, sS0 94.45, sS1 94.43.

### 13.4 Surprises and consequences

1. Neither teacher arm clears the floor against the r15 teacher: continuing the teacher on the r16 mix at lr 2e-5 did not improve it on unseen-route dev (b), and adding all old rows (tB) was worse than the 20% replay (tA), the opposite of the "dilution" worry. This is a result for the user (clause 4), not for an automatic pick; the user decides whether the full teacher is still worth about 16 h, what to change, or whether to keep the r15 teacher.
2. The tie-band is what decides Q2: the softened-target student is statistically indistinguishable from the plain one on accuracy, though it is much better calibrated (T 1.19 against 1.49).
3. The fitted T of both continued teachers rose to about 1.85 to 1.89 (from 1.36); the full teacher's soft targets, if used, would need that new T, not 1.362087.
4. Section 7.7 stands: nothing here is a ship candidate; only exam #8, once, decides shipping.
