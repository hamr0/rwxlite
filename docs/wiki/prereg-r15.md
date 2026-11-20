# Pre-registration: round 15 (new-vendor transfer set; bge-base teacher, MiniLM student), 2026-11-19

**Status: TRAINING SECTION FROZEN 2026-11-19 (user decision: lock the pass bars and start training now; the freeze commit on branch `r15-github-data` precedes the start of the teacher).** Nothing has been trained, predicted or scored. **The pass bars of sections 5.2, 8.1 and the val rule are LOCKED, user 2026-11-19.** The one-base D141 labels (tight file), the data/round15 build and the lean at rwxmap 1c25be1 are frozen. The only open items are marked "fill before exam #7 predictions" (the exam #7 `truth.csv` sha256 and the candidate addendum values of section 8.1; the exam #7 ref, labellers, `ops.csv` and `lean.csv` facts have been received and are recorded in sections 7.2 and 8.1). Amendment 2026-11-19: the ship gate is the fp32 exact model (section 8.1). They affect scoring only, not training, and nothing else here may change. The earlier gate that training waits for the exam #7 ref SHA is lifted by the user (rwxmap: the exam #7 ref makes no mechanical change, the lean equals 1c25be1).
The candidate is a **candidate**. The only thing that can replace shipped rwxlite 0.3.1 (R13) is the frozen rule in section 8, applied once to exam #7. Nothing in this file is a release.
Parent documents: `docs/product/prd-r15-github-data.md` (sections 5-7, 17-18), `docs/product/prd-bge-teacher.md` (round 14, `--base` and `--teacher` code), `docs/wiki/prereg-r13.md` (format, ship rule), `docs/wiki/prereg-exam5.md` (predict/score mechanics).

## 1. Question

Does a MiniLM student distilled from a bge-base teacher that was **retrained on 199,600 cascade-labelled rows from about 21,600 new vendors** close the unseen-vendor gap (about 97% on val, about 90% on unseen vendors) without more leaks, at the same 23 MB int8 size and about 17-20 ms per operation? Round 14 distilled on the same 102,668 rows and gained nothing; round 15 changes the data, not the loss.

## 2. Frozen rules this round honours (project memory)

- **Gate = rwxmap CLI `secondPass`, mode a, `LOWER_MIN_P` 0.90 (D139).** Not `a_none`, not a replica. Replicas are used only for checks and for information.
- ~~**LOCKED, user 2026-11-19: ship gate = exam #7 mode a, int8 at batch 1; no more too-loose answers and no fewer exact answers than 0.3.1/R13 (D135).**~~ **SUPERSEDED 2026-11-19 (amendment, user decision made later the same day; the struck line is kept as written).**
- **LOCKED, user 2026-11-19 (amendment, corrects the line above): the exam #7 SHIP GATE is decided on the fp32 "exact" model (`manifest-exact.json`, `model-fp32.onnx`), through rwxmap's real CLI, mode a, `secondPass` at cut-off 0.90, on the same 1,579 rows, at batch 1.** The rule is D135 as written in rwxmap's exam #7 prereg (rwxmap `docs/wiki/exam-prereg-exam7.md`, commit 9516435, branch exam7-prep): **a-cand too loose <= a-base too loose AND a-cand exact >= a-base exact; a tie passes.** Reason: rwxmap's runtime default downloads the fp32 exact variant (rwxmap `src/modeldownload.js`: the default is `manifest-exact.json`, `small` is int8), so the earlier premise "int8 is what rwxmap runs" was wrong. **int8 at batch 1 is INFORMATION ONLY**: we score it ourselves and it never decides. rwxmap scores fp32 only. Reported with no bar: mech, b85-base, b85-cand, and D133 against mech.
- **Ship rule (D135):** a new model replaces shipped 0.3.1 (R13) only if, on a fresh clean exam, mode a has **no more too-loose and no fewer exact**. Exam #7 is that exam. It is scored once and then burned.
- **Compare at the shipped baseline's T.** Shipped R13 stays at T 0.991463, never refit (refitting the baseline's T moved 7 exact, more than training did).
- **Batch 1** for every scored number (int8 dynamic quantisation with padded batches makes p batch-dependent).
- **Preregister the predict and score code; commit the prediction sha256s before the truth is revealed.**
- **Labels** follow BRIEF-v4 plus the D141 addendum (section 3.4). rwxmap's pipeline is the label truth. Same model plus same brief is one opinion, not an independent labeller (the cascade used Opus for pass 3, residue rows get weight 0.3).
- **Server** (`ahassan@192.168.178.180`, sandbox `~/rwxlite-train` only): nice 19, ionice idle, 3 of 4 threads, one job at a time, nohup, memwatch kills the job under 2 GB MemAvailable, no process left behind. 4 cores, 15 GB RAM, no GPU.
- **Student stays all-MiniLM-L6-v2**, 22.7M parameters, 23 MB int8, about 17-20 ms per operation.
- The 400 holdout rows never enter training.

## 3. Data (fixed)

### 3.1 Inputs and sha256 (computed 2026-11-19 from the files on the laptop)

| file | sha256 |
|---|---|
| `data/round13/train.parquet` (102,668 existing rows, R13's exactly) | `91808a87cf24ac9c70f4d5b8f26fe68341ca9836606ce30a3e86273fce129aa5` |
| `data/round13/val.parquet` (4,180 rows) | `580a1141e6ee416b4ff2b445c749fc95b60bcdbddd04d0bbdd0464196ff840d1` |
| `data/round13/v3eval.parquet` (only the trainer's end report needs it; meaningless) | `7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad` |
| `data/r15/labels/final-labels-r15-d141.parquet` (**final**, 199,600 rows, rwxlite commit cf6232d; never edited by the build) | `d36972fe2f9be2107581fbe30a7a5edecdf7d191418bf03f85c041b7e42e93eb` |
| `data/r15/labels/final-labels-r15-d141-tight.parquet` (**the label file the build reads**, 199,600 rows; the D141 file with its 162 lowers reverted by `r15/r15_revert_lowers.py`; the D141 file above is kept, never edited) | `0937e0a25fef244fd1b0aa1566f61774b88b2f656f202fef4730c34594b37e56` |
| `data/r15/labels/final-labels-r15-d141-tight.csv.gz` (same rows and columns, csv) | `69e1f38f411b913eb96de7afd9d835253fc20057033ab9e9deb2747d5af9e5d2` |
| `data/r15/labels/final-labels-r15.parquet` (pre-D141; superseded, kept only as the source of `label_pre_d141`) | `8e11971ce39f6590519a8dd50c970505455fd0dc50ff33fead40d767dd728a98` |
| `data/r15/labels/d141/merged.csv` (Sonnet blind relabel of the pattern-net candidates, with confidence) | `2436a63db9dfdf9c464133b7b6181ab384d17333e6698858b205cd6a7d5cd990` |
| `data/r15/labels/d141/pass2/out-a.csv`, `out-b.csv` (Opus pass 2 on under-applied rows) | `6ca51a31eb6d2cb411b10bfb60d6cb692fd6757b59e85044d6584fb3120c4ee3`, `931ffc9f53d7dc314fc5c851f98c68b1fced13ac86bc09ac4b81925e7091ffa4` |
| `data/r15/labels/d141/pattern-net.json` (the D141 pattern net) | `0fb223cc1410b3e0e72c8c4db67f31ec7b11d2d48a92ecddb65a3da58e359af0` |
| `data/r15/labels/d141/holdout-review-d141.csv` (**the holdout truth used for all scoring**) | `96a624889bfd0f093e26809550ee4b311212e6b816e7abcb0fb7777c295977bd` |
| `data/r15/labels/d141/holdout-score-d141.json` (D141 reference numbers) | `da62b68074e4ef94e5c052c141e61ac86044d9d5ed561a0e5b727a08cc087219` |
| `data/r15/labels/opinions-report.json` (population weights of the 18 disagreement types) | `d766dbae4b9bf094b18c9ea51ef8bb99fe1cd1c90c2cf2ff2e40c37c19067540` |
| `data/r15/labels/pick-200000-1-opinions.parquet` (three opinions per pick row; bge raw and T-scaled p) | `9f2d416e7cf9e0bd7d1989e405b89d2db0d021123153052b19a15c2b5cef620c` |
| `data/r15/picks/pick-200000-1.csv.gz` | `d266194941318e8f0117067650af61b58da6105257b753c348cf048268c15da1` |
| `data/r15/labels/texts-r15.jsonl` (model input text of all 200,000 pick rows; copy of the scratch `texts.jsonl` made by `r15/label_mech.mjs`) | `4f7955fb897ff1ca48a628df38d8b80aa8b5489f7f93085d027a98e45416a4ab` |
| `data/r15/labels/mech-r15.jsonl` (mechanical letter, rule, review; same run) | `ef3938d15bd81aed423927ce6a429c492e5dede06835275be9f075ad12b46a43` |
| `data/r15/labels/disagree-sample-400.csv` (the 400 holdout rows) | `76dd3fae6ec409855447f3d449fda4fa2f7a5a5d5b543900fd791e84bb194512` |
| `data/r15/labels/claude-review-400.csv` (original blind review, pre-D141; reference only) | `88680a82e66298e726cf63a15cf59280fe78eb1279c267214f79fa0890e449fc` |
| `data/r15/labels/pass4-ambiguity-list.csv` (12,056 flags; input to the D141 pattern net) | `944aedb0d38baa3a88bebb90a73c8d268ae5b81d9d4ba0ffbf2ebea80eadb37c` |
| round 14 teacher probabilities on R13 train (fallback only; `teacher-r14-bge-train.npy`, T=1, fp32, from the server) | `58148602124216a08faaad0a3efa0f1a7bc49be3cfee4da5a6d327ba33c000cc` |
| r14-bge checkpoint `model.safetensors` (server, `r14-bge/data/train/ckpt-r14-bge/final`) | `8bcc187e483715b8f149dc783bf491819a2f6fdbdbbd0732fe15560c1c3a626c` (full sha256, computed on the server 2026-11-19) |

The stored texts of the r15 rows are `src/text.js formatText(state, lean, 1)` with the mechanical lean of rwxmap 1c25be1; existing rows keep their stored text **until the regeneration of section 7.2, which replaces the text of ALL rows before stage A**. The R13 rows (train, val, v3eval) are themselves **replaced by rwxmap's `export-v4-d141`** (TODO, section 3.4).

### 3.2 Build (`r15/r15_assemble.py`, deterministic, no training; output `data/round15/`, gitignored)

`train.parquet` = the 102,668 R13 rows (R13 order) followed by the r15 rows (label-file order). **57 r15 rows are dropped because they share an exact method + path (lower-case) + operationId + summary with a val row** (agree3 56, sonnet 1): val decides the teacher go/no-go (5.2a) and the val floor guard, so no r15 training row may match it; the script asserts that none remains. (10 of the R13 rows also match that key; they are R13's own rows. Re-checked on `export-v4-d141` (f62e1c2): still 10, all 10 labels agree with the val row; no decision needed.) Result: **302,211 rows, 9,445 steps at batch 32.** Columns as R13's plus `src` (r13 / r15), `weight` and `r15_tier`. `val.parquet` and `v3eval.parquet` are copies of R13's (replaced and text-regenerated like train, section 7.2). The script asserts: every input sha256, no holdout id in the output, unique ids, the weight rule of 3.3, label letters and tier counts.

**Regeneration done at 1c25be1 (2026-11-19, `R15_MECH_REF=1c25be1`); the build below is superseded by the FINAL build recorded after the provisional counts (export-v4-d141 at f62e1c2 applied).** r15 rows: 199,543 of 199,543 byte-identical to the stored texts (0 differ; asserted). R13 train rows: 96,364 identical, 6,304 differ (lean prefix only; 3,535 mechanical letters changed). val: 4,026 identical, 154 differ (104 letters changed). v3eval: 4,905 identical, 811 differ (541 letters changed). Re-cleaning the stored R13 description is not idempotent (double unescape, tag strip: it altered 5,627 rows beyond the lean), so for R13, val and v3eval rows `r15_assemble.py` swaps only the lean prefix and keeps the stored tail; r15 rows use the full regenerated text. Provisional hashes of this build (`data/round15/SHA256SUMS`): train.parquet `d472ebb55b41eca512d7357813c6f880852455e750b08cc7f3da75ce8f4c7fa7`, val.parquet `015ccba2d0ee11262fa5248de1b7c9aca45fd20192508a0bac6ebb00ded76894`, v3eval.parquet `831499b6ed627f6f71420659f71d7a3a56a624bc5b78b26f75e504e49290392a`, targets-teacher.npy `1889cf93b236441ede2947c24eb5ed87233e1ce08f22cdb69b076122c9a2bfdf` (unchanged), summary.json `d788cce0ea56849c74d94410f1df838022a003cf6a885f6d912825b274175aa9` (adds `mech_ref` 1c25be1). Counts unchanged: 302,211 rows, 9,445 steps, r15 weight 1.0 = 175,676, 3.0 = 23,867, weight total 349,945.0. The fallback targets are row-order based and unchanged.

**Earlier PROVISIONAL counts and hashes** (built 2026-11-19 with the final D141 label file and today's R13 rows, no text regeneration; every number is rebuilt and re-recorded after `export-v4-d141` and the exam #7 ref arrive):

| | rows | r | w | x |
|---|---|---|---|---|
| R13 rows, final (D141 export f62e1c2; was 55,532 / 22,479 / 24,657) | 102,668 | 55,399 | 22,396 | 24,873 |
| r15 rows (final labels, 57 dropped) | 199,543 | 108,169 | 30,852 | 60,522 |

r15 tiers: agree3 174,911, sonnet 21,037, opus_agree 2,152, strict 1,443. r15 vendors 21,601. 1,330 label rows changed by D141 in the label file. Mean text length: R13 rows 248 characters, r15 rows 156.
Provisional `data/round15/SHA256SUMS`: train.parquet `73b884ff688ec36afe7d65363841aad722c79c9d7b6d07ea9d928ff1705edf0e`, targets-teacher.npy `1889cf93b236441ede2947c24eb5ed87233e1ce08f22cdb69b076122c9a2bfdf`, summary.json `3770284eb230402011fd81dea5a2f9d00b22cb2de37d0f1a42b4348a6db761bd`, val.parquet `580a1141...`, v3eval.parquet `7c0df6fa...` (copies). Fallback targets (provisional): `teacher-fallback-oldbge-train.npy` `1d775b1c43ee7dcdcd2d3edfd19535235da0cdb1edacfb7373cfdec7a3f3925e`.

**FINAL build (2026-11-19; `export-v4-d141` at rwxmap f62e1c2 applied, lean from its columns, `R15_MECH_REF=1c25be1`; section 3.4 item 4 has the inputs).** 302,211 rows (R13 102,668 + r15 199,543), 9,445 steps at batch 32. Weight 1.0 = 175,676 (all r15 rows at 1.0) + R13 102,668; weight 3.0 = 23,867; weight total 349,945.0. Letters per split before (provisional build) and after: train R13 rows r 55,532 / w 22,479 / x 24,657 to 55,399 / 22,396 / 24,873; r15 rows 108,169 / 30,852 / 60,522 unchanged; train all 163,701 / 53,331 / 85,179 to 163,568 / 53,248 / 85,395; val 2,435 / 922 / 823 to 2,432 / 919 / 829; v3eval 1,000 / 1,644 / 3,072 unchanged. `data/round15/SHA256SUMS`: train.parquet `b915e5666a72fa415a427839d82bf40b6c7e31f755cfe5ec6c6755febb27e2a8`, val.parquet `c54ee4612f6c93ac4ac800c8ef08c6fd2c1b415184a28d483401fd067c14d949`, v3eval.parquet `831499b6ed627f6f71420659f71d7a3a56a624bc5b78b26f75e504e49290392a`, targets-teacher.npy `78a2e81a68f66ba63705daaf4a0870bf6301c5c83d0ffd2f300311d997638e05`, summary.json `0cd806bdf0f7b137c81d7dbfedfa6de81172e5b453b13b5199382719114acd81`. Fallback targets rebuilt by `r15/r15_fallback_targets.py`: `teacher-fallback-oldbge-train.npy` unchanged `1d775b1c43ee7dcdcd2d3edfd19535235da0cdb1edacfb7373cfdec7a3f3925e` (row order is unchanged), its `.json` sidecar now `cd81b0e2ce5d18d723fc7b86c85fba1eab26c6618b3db1b31cef0f544c6f2bb8` (records the new train sha). `teacher-r14-bge-train.npy` `58148602...` and its json `686a894c...` untouched.

**One-base merge rule and the TIGHT build (2026-11-19, agreed by rwxlite and rwxmap under the user's existing rulings; this supersedes the FINAL build above and the "tighten-only except the two (c) lowers" proposal for r15).** One rule for both halves: D141 is tighten-only. R13 half (rwxmap's `export-v4-d141`, f62e1c2): raises stay, the 2 D141(c) lowers `ag-069342` and `ag-071594` (Graph externalGroup PATCH, details only) stay, every other lower was already reverted by rwxmap. r15 half: **0 lowers kept**; all 162 r15 rows whose D141 letter was lower than the pre-D141 letter (x to w 139, x to r 21, w to r 2) are reverted to the pre-D141 letter, including `r15-19f736c8f25e0c73` (SCIM Groups PATCH, which can change members, so it stays x). Raises stay. `r15/r15_revert_lowers.py` writes `final-labels-r15-d141-tight.{parquet,csv.gz}` (same columns; a reverted row gets `d141_changed` False and its pre-D141 weight; the candidate, pass-2 and family columns keep their history). New label file counts: r 108,180 / w 30,716 / x 60,704 (D141 file: 108,203 / 30,853 / 60,544); rows D141 changed **1,168** (was 1,330; 1,168 are all raises). File `weight` column: 1.0 = 197,958, 0.3 = 1,642. Build rule 3.3 unchanged: the 162 reverted rows are no longer "changed", so they take the tier rule (agree3 132+13 at 1.0, sonnet and opus_agree 9 at 3.0, strict 8 at 1.0).

**Verified 2026-11-19 before the freeze: `sha256sum -c data/round15/SHA256SUMS` passes on the laptop and the five hashes in the TIGHT build below equal it.**

**TIGHT build** (`R15_MECH_REF=1c25be1`, the same `R15_R13_DIR` / `R15_R13_SHAS` / `R15_LEAN_CSV` / `R15_LEAN_SHA` as the FINAL build; `r15_assemble.py` now reads the tight file and asserts its sha256): 302,211 rows (R13 102,668 + r15 199,543), 9,445 steps at batch 32, 57 val-overlap rows dropped as before. Letters (r / w / x): train R13 rows 55,399 / 22,396 / 24,873 (unchanged); train r15 rows 108,146 / 30,715 / 60,682 (FINAL build 108,169 / 30,852 / 60,522); train all 163,545 / 53,111 / 85,555; val 2,432 / 919 / 829 and v3eval 1,000 / 1,644 / 3,072 (unchanged). r15 row weight 1.0 = **175,829**, 3.0 = **23,714** (by tier: agree3 174,316 / 595, sonnet 76 / 20,961, opus_agree 5 / 2,147, strict 1,432 / 11); r15 weight total 246,971.0; **weight total 349,639.0** (was 349,945.0); the contested rows carry 20.3% of the weight. `data/round15/SHA256SUMS`: train.parquet `16a34b054aef3b6ca5ad084a2395f70596a086b3bf861eb29411066605213a99`, val.parquet `c54ee4612f6c93ac4ac800c8ef08c6fd2c1b415184a28d483401fd067c14d949` (unchanged), v3eval.parquet `831499b6ed627f6f71420659f71d7a3a56a624bc5b78b26f75e504e49290392a` (unchanged), targets-teacher.npy `f2a06092698502d267bbf4e6f8d3aa5468c1b93306c87c6f351c03df9a3ff1ea`, summary.json `4a1c5f00b466126ab937c18e780b46e052b029623f17b7c11038b19eedbc1fb0`. Fallback targets rebuilt: `teacher-fallback-oldbge-train.npy` `1d775b1c43ee7dcdcd2d3edfd19535235da0cdb1edacfb7373cfdec7a3f3925e` (unchanged), its `.json` sidecar `77168d5b5f585a9a61bfb8f83befba805996457d3776c5da51082b6c8a3b9a02` (records the new train sha; argmax agrees with y 97.21%). Lean diff against the regeneration: 0 rows differ in train R13 rows, val and v3eval.

**Holdout:** none of the 162 reverted rows is in the 400-row holdout (0 of 400 overlap; the holdout is also not in the label file at all), so the holdout truth `holdout-review-d141.csv` and its D141 reference numbers do not depend on this change and are not rescored.

**Burned-exam training copies:** the exam 3, exam 4 and fx training copies (36 raises) follow D141 as training data only; their truth files are unchanged.


### 3.3 Targets

| rows | hard label y | soft target (the `--teacher` file) | row weight |
|---|---|---|---|
| R13 rows | R13's (v4) label (to be the `export-v4-d141` label) | `common.soft_targets()` exactly as R13 trained (Jev soft where it exists, one-hot elsewhere; 71,179 of the 102,668 rows are soft today) | 1.0 |
| r15 rows, every tier | the final D141 cascade label | **one-hot of that label** | by the rule below |

**Row-weight rule (the user's, 2026-11-19: "increase weights on previously contested rows x3, because that's where wrong judgements happen"; implemented in `r15/r15_assemble.py` from the label file's columns, the file itself is not edited).** Per r15 row, first match wins:
1. changed by D141 (`d141_changed`, which includes the pass-2 raises) and the **deciding answer was sure or likely: 3.0**, whatever the tier;
2. changed by D141 but the deciding answer was **unsure**: 1.0 (3 x the old 0.3: contested but uncertain);
3. strict tier, not changed by D141 (the residue rule, strictest opinion, uncertain): 1.0;
4. tier sonnet or opus_agree (disputed by the three opinions, settled in pass 2 or 3): **3.0**;
5. agree3 and not changed by D141: 1.0.

R13 rows are 1.0. "Deciding answer" = the Opus pass-2 answer if it raised Sonnet's D141 letter, else Sonnet's (as `r15/label_d141.py`); it is read from `merged.csv` and `pass2/out-*.csv`, and the script cross-checks that the label file's own 0.3 weights agree with it on every changed non-strict row. **Counts (provisional, final label file, 57 val-overlap rows dropped):** r15 weight 1.0: 175,676 rows (agree3 174,171; strict 1,424; sonnet 76; opus_agree 5); weight 3.0: 23,867 rows (sonnet 20,961; opus_agree 2,147; agree3 740; strict 19). R13 rows 1.0: 102,668. **Weight total 349,945.0** (r15 247,277.0, R13 102,668.0). **The contested rows (weight 3.0) carry 20.5% of the total weight** (71,601 of 349,945) though they are 7.9% of the rows (23,867 of 302,211). The old 0.3 weight is gone.
**This x3 is a per-row weight on contested rows. It is not R13-L3's x3 too-loose loss cost** (`--loose_cost`, not used here): the loss stays 0.7 soft CE + 0.3 hard CE with `x_weight 1.0`.

**Choice: agree3 rows get NO soft term from the round 14 bge probabilities.** Reasons: (1) the round 14 bge probabilities are one of the three opinions that made the agree3 label, so using them again as the target is circular (the old teacher teaching its own beliefs to its replacement); (2) bge's blind-review exact rate on disputed rows was 74.8%, and its weak spot (too loose about a third of the time) is exactly where soft copying would carry errors forward; (3) it is the simplest rule: one rule for all 199,600 rows, no extra input file; (4) calibration is not lost, because the teacher is a different object from the label: it still produces soft p for the student (stage B) and its T is fitted on val. Cost: sharper, possibly more confident teacher p on r15-like rows; the go/no-go checks (section 5) measure the leaks directly. The old-teacher soft variant is the fallback (section 5.4), not a candidate to be tried afterwards on exam #7.

Loss for both stages: `0.7 * soft CE + 0.3 * hard CE`, class weights 1/1/1 (`x_weight 1.0`), each row's loss multiplied by its `weight` before the batch mean (batches are not renormalised, so a batch of contested rows has a larger loss; lr and clipping unchanged). With one-hot soft targets this reduces to plain CE on the hard label; for R13 rows it is R13's recipe.

### 3.4 D141 (rwxmap user ruling, 2026-11-19): done, and what is still open

rwxmap's user ruled on the five BRIEF-v4 ambiguities: (a) login, sign-in or refresh returning any token = x; (b) verifying an email, OTP or token, including pure checks, = x; (c) a group update with no members, roles or permissions in the text = w, adding members stays x; (d) changing a callback, webhook or endpoint setting, uploading a signing key, or registering a push token = x; (e) removing members via POST, PUT or PATCH = x, narrowing a role without removing anyone stays w.

1. **Labels follow BRIEF-v4 + the D141 addendum**: rwxmap commit `54355e1`, file `data/relabel-v4-2026-11-05/BRIEF-v4-addendum-D141.md` (sha256 `ff164d934b57cb1b86118aba9edb258440437fcc72c7d4f9a1f0af7accdcd918`, from `git -C ../rwxmap show 54355e1:<path> | sha256sum`, 2026-11-19).
2. **The r15 label file is the D141-revised version** `final-labels-r15-d141.parquet` (section 3.1): Sonnet relabelled the 9,740 pattern-net candidates (net: `pattern-net.json`), Opus pass 2 raised 395 under-applied rows; 1,330 labels changed. **Superseded by the tight file (section 3.2, tighten-only merge): the 162 lowers are reverted, 1,168 labels changed.**
3. **The 400-row holdout review is re-checked under D141** (`holdout-review-d141.csv`, 30 review rows changed) and is the only truth used in scoring. D141 references from `holdout-score-d141.json` (exact / too loose / too tight, weighted to 25,033 rows): old bge 74.0 / 18.4 / 7.6 (pocket 61.6 / 33.9 / 4.4); R13 mode a 56.5 / 8.8 / 34.7 (pocket 32.3 / 0.0 / 67.7); cascade 89.4 / 6.1 / 4.5.
4. **The 102,668 existing rows are replaced by rwxmap's `export-v4-d141`: DONE (2026-11-19).** Delivered at **rwxmap commit `f62e1c2`** (branch exam7-prep; it replaces the first delivery at `cddbe71`, which had no lowers), folder `/home/hamr/PycharmProjects/rwxmap/data/export-v4-d141-2026-11-19/` (read only). sha256: `export-v4-d141.csv` `8d802cf42d56fbcf050102fb854a958696bf59abdeca1a43fe6c88bcdc53034f`, `changed-train.csv` `11e048ff6acb00be10f3461cf9b01ea1266b3a2da7c5992dbf68b8e9356b0ee2`, `changed-val.csv` `f567ea00f7bad0932570570b0811a3f920b25e03cabfd71950166d370b52acfb` (all three verified). Rows 106,848 (train 102,668, val 4,180); columns id, split, label_v4, label_d141, changed, d141_families, d141_confidence, lean_letter, lean_rule, lean_source. **232 changed rows (train 226, val 6)**: r to x 130, w to x 94, r to w 6, and 2 D141(c) lowers x to w (`ag-069342`, `ag-071594`). Merge rule: tighten-only, except the two (c) lowers that pass the agreed test (update of the group object itself, not a create, not a sub-resource, labeller sure/likely, no member/role/permission/owner/admin/access/grant/policy/acl word); every other lower is reverted to the stricter v4 letter (297 lowers not applied). The same rule is the proposal for r15's own D141 lowers (see the findings of 2026-11-19; r15 labels are not changed by this step).
   - **Labels**: `label_v4` equals the stored R13 label for all 106,848 ids (0 mismatches). `label_d141` is applied to train and val by `r15/r15_apply_d141_export.py` (writes `data/round13-d141/{train,val,v3eval}.parquet`, v3eval unchanged; train gets a `d141_changed` column): train.parquet `ae9a44184538e571185479907da4e9ead9211e1d0a6f6b185f34fc7f12341ae7`, val.parquet `bc7bc643ecfdea2ce3bc6d5fb3faa972ca07ae19cc45440f52bcb99412fc3400`, v3eval.parquet `7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad`. The assembler is run with `R15_R13_DIR=data/round13-d141`, those three shas in `R15_R13_SHAS`, `R15_MECH_REF=1c25be1`, `R15_LEAN_CSV=<export-v4-d141.csv>`, `R15_LEAN_SHA=<its sha256>`.
   - **Lean diff**: rwxmap's `lean_letter` + `lean_rule` against the lean prefix stored in `data/round13` (before the regeneration): equal 100,390, rule only differs 2,819, letter differs 3,639 (train 6,304 differ, val 154; same as the regeneration at 1c25be1 found); v3eval 4,905 equal, 270 rule only, 541 letter (all 5,716 v3eval ids are train ids). Against the lean in `data/round15` after the regeneration (train R13 rows, val, v3eval): **0 differences in all three, letter and rule** (so rwxmap's column and our regeneration at 1c25be1 agree on every row). rwxmap's column is nevertheless the source of truth: `r15_assemble.py` writes the prefix and mech letter of the R13 rows, val and v3eval from it (tail kept) and counts any difference to the regeneration in `summary.json` (0).
   - **Soft targets of the 226 changed train rows**: the stored Jev soft target belongs to the old label (all 226 had its argmax different from the new label, 116 of them not one-hot), so the assembler sets them to the one-hot of the new label (226 rows). All other R13 rows keep R13's `soft_targets()` exactly.
   - **The 10 R13 rows that match a val row on the exact key** (method, path lower-case, operationId, summary): still 10, and their labels agree with the matching val row in all 10 (no conflicting label). They stay in training (R13's own rows); no decision needed.
   - **Val references recomputed** (R13, T 0.991463, batch 1, mode a 0.90 through rwxmap's real replay at the sweep-time tree `5e6b9cb^`; `m1/r14-compare.mjs` unchanged, `rwxlite-val/ops.csv` unchanged): only 6 val labels changed (r to x 3, w to x 3), so the old-label reference is reproduced exactly (3,941 / 86 / 153 for the PyTorch fp32 batch-1 model on val.jsonl). Right / too loose / too tight: PyTorch fp32 b1 (the prereg's R13-b1), old val labels 3,941 / 86 / 153, **new D141 val labels 3,939 / 90 / 151**; the same on the regenerated val texts (new lean prefix) new labels 3,938 / 90 / 152; shipped int8 (0.3.1, `984714f0`, onnxruntime batch 1, Python tokenizer) new labels 3,933 / 90 / 157 on either text (old labels: 3,935 / 86 / 159 on the old text, 3,933 / 87 / 160 on the new text); the fp32 b1 is the reference the 5.2a rule was written on. **New val thresholds on R13-b1 (fp32, 3,939 / 90): right >= 3,897 (3,939 - 42) and too loose <= 104 (90 + 14).** **Decision (2026-11-19): the R13-b1 val reference is fp32 batch 1 on the NEW-lean val text against the D141 val labels: 3,938 right / 90 too loose, so right >= 3,896 and too loose <= 104.** The reason: the candidate is scored on the same new-lean text. (The 3,939 / 90 on the old text and its 3,897 are superseded.) The 5.2a numbers in section 5.2 (3,941 / 86 / 153, 3,899, 100) are superseded by these.
   - **Rebuilt `data/round15/`** (302,211 rows, 9,445 steps at batch 32; weights unchanged): see section 3.2.

## 4. Seeds and determinism

One run per stage, no variance estimate. `torch.manual_seed(1)`, `random.seed(1)`, epoch shuffle seed `100 + epoch`, as in rounds 13 and 14 (`train/finetune.py`, unchanged except the new `--row_weight` option, default off, which with all weights 1 gives the same loss as without it; checked numerically 2026-11-19). Dropout is the models' default. Row order is fixed by `train.parquet`. Teacher probabilities (`train/teacher_probs.py`) use batches of 128 sorted by length; padding shifts p by about 1e-6 (as in round 14); every scored number uses batch 1.
Code as launched: sha256 of `train/finetune.py`, `train/common.py`, `train/teacher_probs.py`, `m1/r15-train.sh` go into the findings at launch (sha256 at launch, 2026-11-19: `train/finetune.py` `6e54a3c3d7f3e6fdab527a0935c1a1ad8d7aecd05272d303294f73f1995163ef`, `train/common.py` `061da692d8781a104ca7e47a605983b4cad9d8ddb10ca45f2b55ca2249b3e8d8`, `train/teacher_probs.py` `e49fa9039b51aa93fc7edb0148e6cb095975e8e9173db82f0fa9d4236fd06f62`, `m1/r15-train.sh` `120fece1659c4d928f78cd407f223ae54835731741aa70ccf42d5ad6052b7fdc`; the server copies are verified against these).

## 5. Stage A: the teacher

### 5.1 Training

bge-base-en-v1.5 (`BAAI/bge-base-en-v1.5`, 109.5M parameters, vocabulary identical to MiniLM's), `--base`, round 14 base recipe (alpha 0.7, 1 epoch, batch 32, AdamW lr 5e-5 weight decay 0.01, warmup 6% then linear decay, max_len 128, x_weight 1.0, seed 1) on the 302,268 rows with the targets of section 3.3. Trained from the base model, not from r14-bge. Dir `~/rwxlite-train/r15-teacher/`, tag `r15-teacher`, `--ckpt 250`, `--threads 3`. Command (as in `m1/r15-train.sh teacher`):

```
python train/finetune.py --base BAAI/bge-base-en-v1.5 --teacher data/train/targets-teacher.npy --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 5e-5 --max_len 128 --threads 3 --ckpt 250 --tag r15-teacher
```

**Runtime estimate.** Round 14 measured 351.3 min for 3,209 steps (6.57 s per step, peak RSS about 6.9 GB). The new run has 9,445 steps. R13 rows: 3,209 steps = 351 min. r15 rows: 6,236 steps; their texts are 63% as long (156 vs 248 characters), so about 0.63 x 6.57 s = 4.1 s per step = 430 min. **About 780 min = 13 h; upper bound if length did not help 1,034 min = 17.2 h** (PRD estimate 15-20 h). Measure from the first checkpoint (about 25-30 min at the upper rate); if the projection passes 24 h, stop and re-plan, do not shorten the run silently.
Then `m1/r15-train.sh probs`: teacher softmax (T=1, fp32) over the whole train.parquet, `data/train/teacher-r15-train.npy` plus sidecar json with the train.parquet sha256. Round 14 measured 17.8 rows/s on R13 texts (96 min for 102,668) and the labelling pass 26.5 rows/s on r15 texts (126 min for 199,600): **about 3.7 h**.

### 5.2 Teacher checks before stage B (all frozen now; run once on the final checkpoint)

T for the teacher is fitted on val with `temp_fit` (same procedure as R13 and r14-bge); the holdout argmax does not depend on T.

**(a) Val through rwxmap mode a at 0.90**, with `m1/r14-compare.py` / `m1/r14-compare.mjs` unchanged (rwxmap sweep-time tree, `git archive 5e6b9cb^`, whose `replay.mjs --lower-min-p` is the real rule at 0.90). One run with the three models side by side: `--r14-ckpt` = the round 14 bge, `--student-ckpt` = the new teacher (the script's "student" slot), R13-b1 as always. Val is in-distribution for the R13 rows; this check only guards against damage from the new data. References (round 14, mode a 0.90, right / too loose / too tight): R13-b1 3,941 / 86 / 153; r14-bge 3,944 / 94 / 142 (recomputed by the same run; if they differ the recomputed ones are used and said so; recomputed on the replacement val of `export-v4-d141`, section 3.4 item 4).
LOCKED, user 2026-11-19. Pass: **right >= R13-b1 right - 42 (1 pp of 4,180) AND too loose <= R13-b1 too loose + 14. Recomputed on the D141 val (section 3.4 item 4): R13-b1 on the new-lean val text 3,938 / 90 / 152, so **right >= 3,896 and too loose <= 104** (the earlier 3,899 / 100 are superseded).**

**(b) The 400-row holdout** (`r15/r15_holdout_score.py`, PyTorch fp32 batch 1, the D141 review `holdout-review-d141.csv` (sha256 `96a62488...`), weighted to the 25,033 disputed rows by disagreement type as in `label_holdout_score.py`). The teacher's own argmax letter is scored, against the old-bge reference on the D141 review (bge 74.0 exact / 18.4 too loose / 7.6 too tight; pocket where bge is looser than both others 61.6 / 33.9 / 4.4). Pass, all three (LOCKED, user 2026-11-19):
- **exact >= old-bge exact + 5.0 pp = 79.0**,
- **too loose <= old-bge too loose - 5.5 pp = 12.9**,
- **pocket too loose <= old-bge pocket too loose - 8.0 pp = 25.9**.

Why these numbers: on the same 400 rows, Sonnet alone scored 87.2 / 9.8 and the cascade 92.0 / 3.8. The new teacher saw the cascade labels of the 24,633 non-holdout disputed rows of the same 18 types, so it must clearly beat the old bge on them; a gain under 5 pp (about two standard errors of a 400-row weighted estimate) cannot be told from noise, and a teacher that does not cut too-loose on exactly the rows it was relabelled for has not learned what round 15 is for. The thresholds stay relative to the old-bge reference of the same review file.

**(c) Sanity:** training completed all 9,445 steps with a finite loss, memwatch never fired (or the run resumed from `last.pt` and finished), checkpoint sha256 recorded.

### 5.3 Go / no-go

**GO = (a) and (b) and (c).** One evaluation, no second run chosen for a better result. GO makes the new teacher the stage B teacher. It decides nothing about shipping.

### 5.4 NO-GO: fallback

If any of (a), (b), (c) fails, **the round 14 bge teacher is used** and nothing else about stage B changes: soft targets for every row from `data/round15/teacher-fallback-oldbge-train.npy` (R13 rows from `teacher-r14-bge-train.npy`, r15 rows from `bge_raw_p_*` of the opinions file; built by `r15/r15_fallback_targets.py`, no server time; provisional file sha256 `1d775b1c43ee7dcdcd2d3edfd19535235da0cdb1edacfb7373cfdec7a3f3925e`, rebuilt and re-hashed with the final train.parquet), hard label and row weight from the (revised) cascade. The failure and the numbers go into the findings.

### 5.5 AMENDMENT 2026-11-20: USER OVERRIDE of the teacher go/no-go

**USER OVERRIDE (the user owns this prereg).** The user's words: "it's a pass to me, it's overall better ... why not reuse the big model to train mini". The teacher go/no-go of 5.3 is overridden to **PASS**.
- Numbers (findings 2026-11-20): (a) val mode a 0.90 right 3,929 (bar >= 3,896, pass), too loose **115 against a limit of 104, failed by 11 rows**; (b) holdout 81.8 exact / 10.5 too loose / pocket too loose 15.7 against the old bge 74.0 / 18.4 / 33.9, all three bars passed clearly; (c) sanity passed.
- Section 5.4 (fallback to the old bge targets) is NOT used. The stage B student trains on the NEW r15 teacher's probabilities (`r15-train.sh probs`, then `student`), exactly the section 6 recipe.
- A fallback student (old-bge targets) had been started on the server 2026-11-20 08:03 and was stopped cleanly at 08:22 at step 1,175 of 9,445 (last checkpoint last.pt only, no final model). It is **not a candidate**; its directory is kept, renamed `~/rwxlite-train/r15-student-fallback-stopped/`. Nothing from it is scored or used.
- The stage B student is **the one and only candidate**. The student val floor guard (section 6) and exam #7 (section 8.1) are unchanged. **No exam #7 truth and no exam #7 score had been seen** when this override was made.

### 5.6 USER RULINGS 2026-11-20

Made by the user on 2026-11-20, **before any exam #7 truth or score was seen** (none had been).
1. **The student val floor guard failure (section 6) is WAIVED.** The student scored 3,910 right / 120 too loose / 150 too tight on val mode a 0.90 against a too-loose limit of 104. Reasoning: it is better on new vendors, and a small rise in too loose alongside more exact answers is a trade, not a loss.
2. **The exam #7 ship gate changes from D135 to:** cand exact >= base exact AND cand too-loose % <= base too-loose % + 1.0 percentage point; still the real CLI, fp32 exact, mode a, `secondPass` 0.90, the same 1,579 rows. The D135 text in section 8.1 is struck through, not deleted. rwxmap's amendment: D142, rwxmap commit `728bb16` (branch `exam7-prep`, `docs/wiki/exam-prereg-exam7.md`); in rows: exact no lower and too loose at most floor(0.01 x 1579) = 15 rows higher; too tight reported, not gated.
3. **The current r15 student** (`model.safetensors` sha256 `e431763878ffaec9753b94ef5d26ebe4227eaea432d132637307673f9e2061d9`, T 1.3832182330120317) **is the one and only candidate.** Exam #7 results will also guide round 16.

## 6. Stage B: the student

- **Model and recipe:** all-MiniLM-L6-v2, trained from the base model (no `--init`), R13 / round 14 student recipe unchanged: `--teacher <stage A probs> --alpha 0.7` (0.7 soft CE on the teacher's probabilities + 0.3 hard CE on the label), `--row_weight weight` (rule of 3.3), 1 epoch, batch 32, lr 5e-5, weight decay 0.01, warmup 6%, linear decay, max_len 128, x_weight 1.0, seed 1, `--threads 3`, `--ckpt 250`. No loss change (research and round 13 show mixed results). 9,445 steps. Dir `~/rwxlite-train/r15-student/`, tag `r15-student`:
```
python train/finetune.py --teacher data/train/teacher-r15-train.npy --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 5e-5 --max_len 128 --threads 3 --ckpt 250 --tag r15-student
```
- **One epoch over the larger set** is the only change to the length (3x the steps); no schedule or lr change, because round 13/14 settings were never tuned and tuning on val would be circular.
- **Runtime estimate.** Round 14: 63.1 min for 3,209 steps (1.18 s per step). R13 rows 63 min; r15 rows 6,236 steps x 1.18 s x 0.63 = 77 min. **About 140 min = 2.3 h; upper bound 186 min = 3.1 h.**
- **Whole round on the server:** teacher 13 h (upper 17.2 h) + probs 3.7 h + student 2.3 h (upper 3.1 h) + checks and export under 1 h = **about 20 h, upper bound about 25 h**, strictly one job at a time.
- **Student T**: fitted on val with `temp_fit` on the student's own PyTorch fp32 batch-1 probabilities (R13 and round 14 procedure), then **frozen and written into the findings before exam #7 is touched** (this is the T that goes into the manifest, section 7). **User decision: the student uses its own val-fit T; the baseline R13 stays at its shipped 0.991463, never refit.** The candidate's scores at 0.991463 are reported as information only.
- **No student pass rule on val; the val floor guard is kept (user decision).** The student is one candidate; nothing is picked on val. Val numbers are information, with one guard against wasting the burned exam: if the student's val mode a 0.90 has right < R13-b1 right - 42 or too loose > R13-b1 too loose + 14 (the same floor as 5.2a), it is not taken to exam #7, and the failure is recorded. This guard cannot admit a model; only exam #7 can.

## 7. Export and cost record (`m1/export_r15.py`, `m1/manifest-r15.mjs`; copies of the round 13 scripts, paths and environment variables only)

Student checkpoint to ONNX fp32 and int8 per-channel (`quantize_dynamic`, QInt8, per_channel, reduce_range False), `vocab.txt`, `export-sha.json`, manifests with `textFormat 1` and the frozen T. Environment: `R15_CKPT_SHA` = the student safetensors sha256, `R15_T` = the frozen T. Version string: the next free version; model string `rwxlite-<version>+<sha8 of the int8 file>`; version frozen as 0.4.0 (2026-11-19); the sha8 of the int8 file is known only after export.
Recorded: int8 file size (expected about 23 MB; same architecture as R13's 22.7M parameters), per-operation latency with `m1/bench.mjs` batch 1 on int8-pc (expected about 17-20 ms), Python ORT vs PyTorch parity on every 7th val row and Node vs Python parity (`export_r15.py parity`, `manifest-r15.mjs parity`), as for R13. Argmax differences int8 vs fp32 are information. If size or latency leaves the 22-24 MB / 15-25 ms window, that is a finding, not a gate, but it must be said.

### 7.2 Lean = exam lean (frozen rule, user decision 2026-11-19: "wait and match")

Exam #7 runs through the real rwxmap CLI at **one frozen rwxmap ref**, "the frozen exam #7 rwxmap ref stated in rwxmap's exam #7 pre-registration" (**SHA: 96ebb46, received 2026-11-19; its `src/` differs from 1c25be1 only in `cli.js` and `cli.test.js`, so the mechanical lean is the one of 1c25be1; rwxlite reproduced `lean.csv` byte-identical at 1c25be1, see section 8.1**). **Mechanical text ref = rwxmap 1c25be1**, per rwxmap on 2026-11-19: exam #7's rwxmap ref makes no mechanical change, its lean equals `classifyOperations` at 1c25be1; the only change before exam #7 is D140 (mode b default 85), which does not touch the lean; D141 is deferred to exam #8 in mechanical. The frozen-ref SHA TODO is closed (96ebb46, 2026-11-19); the byte comparison of the exam #7 lean with the lean at 1c25be1 is done and recorded in section 8.1. The same ref produces `lean.csv`, `secondPass` and every mode. If rwxmap's D141 mechanical word list passes its bar, that ref includes it; otherwise its mechanical equals 1c25be1's (0.11.1 `classifyOperations`, the lean of the stored r15 texts).
**Before stage A, the text of ALL training rows (R13 and r15) and of val and v3eval is regenerated with the mechanical lean of that ref**, so training lean = exam lean and the val checks see the same lean. `r15/r15_assemble.py` does this when `R15_MECH_REF=<ref sha>` is set (`R15_RWXMAP` = the rwxmap repo; it extracts `src` and `package.json` at that ref and runs `r15/regen_text.mjs`: the op construction and `formatText(state, lean, 1)` of `r15/label_mech.mjs`; the R13 rows' description is the stored `desc:` segment). Checked 2026-11-19: at 1c25be1 the regeneration reproduces `texts-r15.jsonl` byte for byte on a 2,000-row sample (the full build asserts it on all r15 rows when the ref is 1c25be1). The ref goes into `summary.json` (`mech_ref`) and the findings.
**Gate (revised by the user 2026-11-19): training starts with (1) rwxmap's `export-v4-d141` applied and the data rebuilt; the frozen exam #7 ref SHA is no longer a training gate (rwxmap: no mechanical change, lean equals 1c25be1); it must still be filled and byte-compared before exam #7 predictions.** The label file's own `mech_*` opinions (used only for the cascade) are not touched.

## 8. Scoring

### 8.1 Exam #7 (the decision; D135)

rwxmap exam #7: 6 vendors, 1,579 operations, frozen at rwxmap commit `0c2d623`. **Exam #7 inputs received 2026-11-19 (closed TODOs):**
- Frozen rwxmap ref **96ebb46** (holds the real CLI `secondPass` at `LOWER_MIN_P` 0.90); its `src/` differs from 1c25be1 only in `cli.js` and `cli.test.js`.
- `ops.csv`: rwxmap commit `a1c31bf`, sha256 `abe5e6cd410c72d0bee1b85948ccb12b7d898873f9cb032eb5d27bcd5e447ea3`, 1,579 rows.
- `lean.csv`: sha256 `8334bbe66d1965f79cbd9ad13e17fcabd904c548832d803f7da053c005fc3a70` (r 741 / w 264 / x 574), independently reproduced by rwxlite at 1c25be1 with `r15/regen_text.mjs`: **byte-identical**.
- **Exam #7 truth labellers:** A = Sonnet, B = Opus, blind, BRIEF-v4 + D141 addendum (`54355e1`), rwxmap's user rules every disagreement (the pair is the default, now confirmed).
- **Leak check:** 0 vendor hits for the six vendors; 42 exam operations collide on method+path+summary with generic endpoints of other vendors; no copies.
- **Still open: `truth.csv` sha256 (agreed before scoring).**

**TODO (fill before exam #7 predictions): candidate addendum values rwxmap needs, each exact:**
- [x] rwxlite package version: **0.4.0** (frozen; `package.json` and `package-lock.json` set to 0.4.0 in the commit that adds this line).
- [x] package ref: **the commit that adds this line; see findings** (full hash is reported to rwxmap from `git log`, it cannot be written into the commit that holds it).
- [x] release tag rwxmap would pin: **v0.4.0 if it ships; none created now** (no tag is needed for the local scorer: rwxmap's exam #7 scorer, rwxmap commit 44e3163, is fully local and needs no tag or release; the tag line is closed by that).
- **What rwxmap's local scorer (44e3163) requires, recorded 2026-11-19:** (1) a full rwxlite commit hash in `/home/hamr/PycharmProjects/rwxlite`; at that commit `package.json` must have name `rwxlite` and version `0.4.0` (it says 0.3.1 now, so the version bump must be committed before the hash is sent), and `node_modules` must hold `onnxruntime-node`. (2) A model dir with `manifest-exact.json`, `model-fp32.onnx` and `vocab.txt`; the manifest needs version `0.4.0`, model `rwxlite-0.4.0+<first 8 hex of the model-fp32.onnx sha256>` (the fp32 file's own sha8, not the int8 file's), modelFile `model-fp32.onnx`, and files `{model-fp32.onnx: sha256, vocab.txt: sha256}`. (3) The commit and the model dir must not move or be rewritten after the values are sent. The scorer refuses on any hash or field mismatch, on "rwxlite: off", and on a foreign model string.
- [x] fp32 model string: **`rwxlite-0.4.0+4608f470`** (`rwxlite-0.4.0+<first 8 hex of the sha256 of model-fp32.onnx>`). Convention found in 0.3.1: `modelString(version, sha)` in `src/answerer.js` is `rwxlite-<version>+<sha[0:8]>` of the file the manifest names as `modelFile`; `m1/manifest-r13.mjs` (and `manifest-r15.mjs`) write `manifest-exact.json` from `model-fp32.onnx` and `manifest.json` from `model-int8-pc.onnx`, so 0.3.1 fp32 is `rwxlite-0.3.1+bbe1997d` (sha256 of `data/m1-r13/model-fp32.onnx` starts `bbe1997d`) and int8 is `rwxlite-0.3.1+984714f0`. The two strings differ only in the sha8.
- [x] `model-fp32.onnx` sha256 (data/m1-r15): `4608f4705d652de65adde722dc14868ef2f0898d36f84d18c88524e07ab0bc19`. Model dir: `/home/hamr/PycharmProjects/rwxlite/data/m1-r15` (frozen, never modified again).
- [x] `manifest-exact.json` sha256 (data/m1-r15): `5b3e5b876ea0eda3416ae2115404cae13dd3e699bf4f446e07adb7540771d0f8`.
- [x] `vocab.txt` sha256 (data/m1-r15): `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3`.
- [x] our prereg commit: the commit that adds this line (same commit as the package ref; see findings).

**Exam #7 truth** (labellers recorded above; `truth.csv` sha256 TODO): two blind labellers on BRIEF-v4 + D141 (`54355e1`), no scripts, each file validated, rwxmap's user rules every disagreement, no Jev. None of the exam #7 vendors, aliases, forks or spec repos is in the transfer set (PRD section 4; copy check by rwxmap at commit 1c25be1).

**Models and path (AMENDED 2026-11-19: the gate path is fp32 exact at batch 1; the table is the original, int8 text kept, SUPERSEDED for the gate and read as the information path):**

| | baseline (shipped) | candidate |
|---|---|---|
| model string | ~~`rwxlite-0.3.1+984714f0`~~ int8 (information); **gate: fp32 `rwxlite-0.3.1+bbe1997d`** | ~~`rwxlite-0.4.0+<sha8 of the int8 file>`~~ int8 (information); **gate: fp32 `rwxlite-0.4.0+<sha8 of model-fp32.onnx>`** (version 0.4.0 frozen 2026-11-19: next minor after 0.3.1, new data and teacher; the sha8 is computed at export, section 7, and recorded before predictions) |
| T | 0.991463, **not refit** | frozen student T (section 6) |
| precision, batch | ~~int8-pc (`manifest.json`), batch 1~~ **gate: fp32 (`manifest-exact.json`), batch 1**; int8-pc (`manifest.json`) batch 1 information | ~~int8-pc (`manifest.json`), batch 1~~ **gate: fp32 (`manifest-exact.json`), batch 1**; int8-pc (`manifest.json`) batch 1 information |
| files | `data/m1-r13/` (hashes of `model-fp32.onnx` `bbe1997d...` (gate) and `model-int8-pc.onnx` `984714f0...` (information) as in prereg-exam5; verified before predicting) | `data/m1-r15/` |

~~**User decision: int8 at batch 1 is the primary precision** (what a release ships and what rwxmap runs); round 13 scored fp32 (prereg-exam5), so the fp32 predictions of both models are also produced and reported as information only.~~ **SUPERSEDED 2026-11-19 (user decision, corrects the struck paragraph):** the primary precision is **fp32 exact (`manifest-exact.json`, `model-fp32.onnx`) at batch 1**, because rwxmap's runtime default downloads the fp32 exact variant (rwxmap `src/modeldownload.js`); "int8 is what rwxmap runs" was wrong. int8 at batch 1 (`manifest.json`) is produced and scored by us as **information only** and never decides. This matches round 13 (prereg-exam5, fp32 gate). Batch 1 stays for every scored number.

**Lean check before predicting (new):** regenerate `lean.csv` from `ops.csv` with the frozen ref (`git archive <ref> src package.json`, rwxmap's `classifyOperations`, `poc/mech-v4/lean.mjs` as in prereg-exam5 or the equivalent at that ref) and compare **bytes** and sha256 with rwxmap's `lean.csv` (and its `.sha256`); any difference stops the run. The same check is repeated before scoring, so the lean of training, prediction and rwxmap's secondPass is one thing.

**Predict script:** `m1/exam5-predict.mjs`, unchanged (it reads only `ops.csv` and `lean.csv`, no truth; it checks both sha256 files; contract CSV `id,model,p_is_x,p_changes`, exclusive create), run per model:
```
node m1/exam5-predict.mjs <ops.csv> data/m1-r13 predictions-r13.csv --lean <lean.csv> --manifest manifest.json --expect-model rwxlite-0.3.1+984714f0
node m1/exam5-predict.mjs <ops.csv> data/m1-r15 predictions-r15.csv --lean <same lean.csv> --manifest manifest.json --expect-model <candidate string>
```
(AMENDED 2026-11-19: the two commands above are the **int8 information** runs. The **primary, gate** predictions are the fp32 runs: the same commands with `--manifest manifest-exact.json`, output names `predictions-r13-fp32.csv` and `predictions-r15-fp32.csv`, and `--expect-model` set to the fp32 model strings `rwxlite-0.3.1+bbe1997d` and `rwxlite-0.4.0+<sha8 of model-fp32.onnx>`; rwxmap replays the fp32 files.) The predictions are produced **after training and export, before truth is revealed**; their sha256 (the fp32 files listed first as primary, the int8 files marked information) and those of the two `.lean.csv` files go into **`docs/wiki/exam7-predictions.sha256`** and are committed before rwxmap shares `truth.csv`. Both precisions are hashed and committed before truth. rwxmap replays our CSVs through its CLI and checks they reproduce.

**Decision rule (frozen, then replaced by the user 2026-11-20; see "USER RULINGS 2026-11-20" below).** ~~On the product path, **rwxmap's real CLI `secondPass`, mode a, `LOWER_MIN_P` 0.90 (D139), mechanical v4**, run by rwxmap on both prediction files: the candidate replaces shipped R13 only if it has **no more too-loose AND no fewer exact than R13**. **AMENDED 2026-11-19: this rule is applied to the fp32 exact predictions (`manifest-exact.json`), not int8; int8 never decides.** Equal counts pass; either one worse fails. If it fails, R13 stays and nothing is claimed; no other candidate is tried on exam #7 afterwards. A GO is the user's release decision (release order in project memory), not automatic.~~
**CURRENT RULE (D142, user 2026-11-20):** on the same path (rwxmap's real CLI `secondPass`, fp32 exact via `manifest-exact.json`, mode a, `LOWER_MIN_P` 0.90, mechanical v4, the same 1,579 rows), the candidate passes only if **cand exact >= base exact AND cand too loose - base too loose <= floor(0.01 x 1579) = 15 rows** (base too-loose % + 1.0 percentage point, as an exact integer). Too tight is reported, not gated. int8 never decides. If it fails, R13 stays and nothing is claimed. A GO is still the user's release decision, not automatic. rwxmap's amendment: **D142, rwxmap commit `728bb16`, branch `exam7-prep`, `docs/wiki/exam-prereg-exam7.md`**.

**Information only** (never decides): mode b at confidence 85 and 90 (rwxmap's letters); standalone argmax of both models (our scorer); the same at int8 (the gate is fp32 since the 2026-11-19 amendment); a mode a 0.90 replica (`--mech lean.csv`) listing every row where it differs from rwxmap's letter; too-loose rows by id for both models; the candidate at T 0.991463.
Reported for every cell: exact / too loose / too tight against rwxmap's exam #7 truth (r < w < x; a letter below the truth is too loose).

**Score script:** `m1/exam7-score.py` (new; modelled on `m1/exam5-score.py`; tested on a synthetic 2-row case only, no exam data):
```
python3 -I m1/exam7-score.py --ops <ops.csv> --truth <truth.csv> --truth-sha256 <agreed> --pred-r15 predictions-r15.csv --pred-r13 predictions-r13.csv \
  --sha-list docs/wiki/exam7-predictions.sha256 --model-r15 <string; AMENDED: pass the fp32 files and strings for the gate run, the int8 ones for the information run> --model-r13 rwxlite-0.3.1+984714f0 --sp-r15 <rwxmap a090 letters> --sp-r13 <rwxmap a090 letters> --out results.json \
  [--sp-r15-b85 .. --sp-r15-b90 .. --sp-r13-b85 .. --sp-r13-b90 ..] [--mech lean.csv]
```
It refuses a truth file whose sha256 differs, prediction files that differ from the committed list, ids or order different from ops.csv, a wrong model string, and an existing `--out`. Its verdict uses only the mode a 0.90 product counts. After both sides have scored, **exam #7 is burned** (it may then be training data only).

### 8.2 Val (information only)

`m1/r14-compare.py` / `.mjs` as in section 5.2a, with the student as the third model: R13-b1 vs the stage A teacher vs the student, mode a 0.90 (right / too loose / too tight), mode b at 85 and 90, standalone argmax. The round 14 student rule is not applied. Val is in-distribution for the R13 rows and decides nothing.

### 8.3 The 400 holdout (information only, teacher/student quality on new vendors)

`r15/r15_holdout_score.py` on the student (at its frozen T) and again on the stage A teacher: standalone and mode a 0.90 (replica), all and pocket, beside the stored references (old bge, R13 mode a from rwxmap, mechanical). Against the D141 review `holdout-review-d141.csv` only. For the teacher this is check 5.2b (a gate); for the student it is information. Plumbing test (R13 checkpoint, 2026-11-19): on the D141 review the stored references reproduce 74.0 / 18.4 / 7.6 (bge) and 56.5 / 8.8 / 34.7 (R13 mode a) (the script checks this by the truth file's sha256); the replica of R13 mode a gives 59.5 / 7.6 / 32.9, a small difference to rwxmap's stored letters, so compare the student with the stored R13 reference and read the replica as approximate.

## 9. What is recorded where

- **This file**: the frozen design; the TODO values once known (revised label hashes, exam hashes, version and model strings, student T).
- **`docs/wiki/findings.md`** (section "Round 15"): launch facts (start times, first log lines, code sha256s, peak RSS and lowest MemAvailable), checkpoint sha256s, teacher checks (a)(b)(c) with numbers and the go/no-go outcome, student T, val and holdout tables, export size and latency, exam #7 results and the verdict, the too-loose rows.
- **Server** `~/rwxlite-train/r15-teacher/`, `r15-student/` (logs, `ckpt-*`, `probs-*-val.npy`, `teacher-r15-train.npy` and its json, `memwatch-*.log`); local scratch (not committed) for the compare runs.
- **`docs/wiki/exam7-predictions.sha256`**: the prediction hashes, committed before truth.
- **PRD** (`prd-r15-github-data.md`) status line updated at each step (contract vs findings, both updated).

## 10. Not allowed after the freeze

No change to data, labels, weights, texts (beyond the replacement and regeneration steps of sections 3.4 and 7.2, which happen before training), hyperparameters, thresholds, T rules, cut (0.90), exam, scoring or decision rule. No second teacher or student run chosen for a better result; a rerun only for a crash or a data-join bug, recorded with the reason. A scored exam, gate or holdout is burned: it may be training data only, never tuned on again. Any new relabel from rwxmap after training starts means a new round.

## 11. Run order and open items

1. Wait for the input that still blocks training: (a) rwxmap's `export-v4-d141` is DONE (f62e1c2, section 3.4 item 4, data rebuilt and hashed in section 3.2) and (b) the frozen exam #7 rwxmap ref SHA (section 7.2). Fill the TODOs (addendum sha256, ref, exam inputs), rebuild `data/round15/` with `R15_R13_DIR`, `R15_R13_SHAS`, `R15_MECH_REF`, rebuild the fallback targets, record all new hashes and counts here.
2. **Commit this file and the scripts** (`train/finetune.py` `--row_weight`, `r15/r15_assemble.py`, `r15/r15_fallback_targets.py`, `r15/r15_holdout_score.py`, `m1/r15-train.sh`, `m1/export_r15.py`, `m1/manifest-r15.mjs`, `m1/exam7-score.py`, `r15/r15_apply_d141_export.py`). Freeze.
3. **Gate: (1) and (2) of section 7.2 have arrived and the rebuilt data is hashed here.** User confirms; copy code and data to `~/rwxlite-train/r15-teacher/` (new dir only), start `r15-train.sh teacher`; record start time and first log lines.
4. Copy the teacher checkpoint back; checks 5.2 (a)(b)(c); GO or fallback targets.
5. `probs` (or fallback file), copy to `~/rwxlite-train/r15-student/`, start `r15-train.sh student`.
6. Student checks (8.2, 8.3), T fit and freeze, export, parity, cost record.
7. Predictions on exam #7 ops (AMENDED 2026-11-19: fp32 exact primary, int8 information), both hashed and committed to `docs/wiki/exam7-predictions.sha256`.
8. rwxmap shares `truth.csv`; rwxmap runs mode a 0.90 (and mode b information) on both prediction files; we score once with `m1/exam7-score.py`. Verdict and every too-loose row into the findings; exam #7 is burned.

Remaining open items (amended 2026-11-19): every TODO above that is still unchecked; the numeric teacher thresholds of section 5.2 are LOCKED (user 2026-11-19); the export TODO is done (f62e1c2); still open, all "fill before exam #7 predictions": the exam #7 `truth.csv` sha256 and the eight candidate addendum values of section 8.1 (the exam #7 ref, labellers, `ops.csv` and `lean.csv` are recorded and closed). `r15/r15_apply_d141_export.py` is a new script to commit with the others.
