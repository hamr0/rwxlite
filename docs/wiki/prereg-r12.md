# Pre-registration: round 12 (S0 / S1 / S2) vs 0.2.0 on held-out goharbor.io + render.com, 2026-11-05

**Status: FROZEN when committed on branch `dev`, before any of the three trainings has started or finished.** No model of round 12 exists yet, and nothing has been predicted on the held-out rows.
An internal experiment to pick a candidate, **not a release gate**. D135 still needs a fresh exam #5 with vendors no model has seen; nothing here replaces that.

## 1. Question

Does round 12 (label fixes + exam #4 rows + targeted variants) make the model **surer on clear w/r rows without more leaks**, measured on vendors it never saw?

"Surer" = more rows where the model's top letter is right and at or above 0.97, so rwxmap's lower-only second pass can lower them instead of leaving them at x for review. "Leak" = a too-loose row (lowered below the truth). Background: `classifier-training.md` sections 8 to 11.

## 2. Runs (three trainings, one seed each)

| run | training set | what it adds over S0 |
|---|---|---|
| **S0** (control) | round 11 + 103 label fixes + D136 relabels + exam #4 rows of 5 vendors, **no variants** | nothing; isolates the effect of the label fixes and exam #4 rows |
| **S1** | S0 + generated variants **x2** (the 96 `variants-d136` and 1,103 `variants-final` rows), low-weight rows **x1** | generated = **2,322 rows = 2.38%** of 97,613 |
| **S2** | S0 + generated variants **x5**, low-weight rows **x2** | generated = **5,767 rows = 5.71%** of 101,058 |

Weighting is by repetition (ids repeat on purpose), as variant B of round 11 and `classifier-training.md` section 9. 76 variant rows carry `weight_hint low`.
Same base model (`sentence-transformers/all-MiniLM-L6-v2`) and same hyperparameters as round 11 (`holdout-r11.md` "Common recipe": soft targets `--soft` alpha 0.7, batch 32, AdamW weight decay 0.01, warmup 6% then linear decay, max_len 128, `torch.manual_seed(1)`, `--threads 4`). **Each run trains from the base model, not continued from any checkpoint.** The exact command lines are copied into the findings before the first step starts; they do not differ between runs except the train file.
Single runs: there is no variance estimate.

## 3. Data changes (counts)

Built by `m1/r12-assemble.py`, `m1/r12-seeds.py`, `m1/r12-build-final.py` (no training). Source set = round 11 (`data/round11`, untouched).

- **103 Jev-overruled label fixes** (`label-fixes.csv`): 87 train, 16 val. Human truth from `data/r12/jev_overruled.csv`, one-hot, status fresh, tier none.
- **Exam #4 rows in train:** chatwoot, immich, permit, polar, zulip = **1,050 rows** (r 469 / w 354 / x 227). Text asserted equal to `train/common.fmt_text` of the same fields.
- **D136 relabels** (`relabels.csv`, 62 in total). Exam truth copies come from rwxmap `truth-d136.csv` files: exam #4 sha256 `6c35a32f93a307f254c90d1f2b27913b3bffd0f528669c693bd81ab578108c39`, exam #3 sha256 `1a257e4329089855d32ca261c8b28077b5a15345b00ffc76b6bca62ab9fc4c10`.

  | split | rule | change | n |
  |---|---|---|---|
  | holdout | D136-exam-truth | x to w | 2 |
  | train | D136-exam-truth | x to w | 2 (exam #3) |
  | train | D136-restart | x to w | 41 |
  | train | D136-stop-start-pause-resume | x to w | 16 |
  | train | user-override-2026-11-05 | w to x | 1 (codat `ag-033484`) |

  So restart / server-stop x to w is 57 train rows (41 + 16) via the rule, plus 2 train rows via the exam #3 truth copy and 2 holdout rows via the exam truth copy. v3eval is untouched.
- **Generated rows: 1,199 unique** (`generated-unique.jsonl`: 1,103 `variants-final` + 96 `variants-d136`). Labelled to rwxmap `BRIEF-v3.md` with D136 applied; one-sided Jev filter (drop a w/r variant that Jev calls x, keep x variants); **x-evidence carried** into the row text. Drops: 90 `replaced_by_x2`, 2 contrast rows of the overridden seed r12s-0120. Seeds come from training vendors only (726 vendors in each train file). No restart/stop-term variants.
- **Held-out vendors: goharbor.io (203) + render.com (252) = 455 rows** (`holdout.jsonl`, r 246 / w 115 / x 94, D136 truth). They are exam #4 vendors, whole-vendor split, no op-key group spans splits (asserted), and **not in any train file**. Stated openly: they were chosen **after seeing the exam #4 results**, because they hold the harbor stop / render secret-files raise misses. Selection by difficulty, so an optimistic reading of any gain is unwarranted, and the rows were scored before (0.2.0, r11). What stays clean: no round 12 model trains on a row of either vendor, and no code, cut, T rule or text format is tuned on them.

Train / eval sets:

| file | rows | r | w | x | x share | generated |
|---|---|---|---|---|---|---|
| S1/train | 97,613 | 53,901 | 26,669 | 17,043 | 17.46% | 2.38% (2,322) |
| S2/train | 101,058 | 54,531 | 28,494 | 18,033 | 17.84% | 5.71% (5,767) |
| val | 4,180 | 2,435 | 1,145 | 600 | 14.35% | 0 |
| v3eval | 5,716 | 1,000 | 1,644 | 3,072 | 53.74% | 0 |
| holdout | 455 | 246 | 115 | 94 | 20.66% | 0 |

### Data sha256 (`data/round12/final/SHA256SUMS`)

```
406d3df4e3f4605657f9bb68f8a6a9aec56f168897e3fd25e83dfc7e98ebb97c  S1/train.jsonl
80d8238a631fed1d1e12f146d77ff34c57ea972cff31b422ada18e76a69b9cdf  S2/train.jsonl
6447e90888aa642bf64490f90ee95fc239c74d41cee00a44a28bbe50719cd567  val.jsonl
292c5fd831e0c5fedc9f120b9e9bb0a07dd3659f5973a72a16c29942f28efc00  v3eval.jsonl
d972b8e6ed762df1ac07bce3efbeef497d0b6d947d12f59c1a214aab91cdfcfb  holdout.jsonl
61aabce02aadb84f346a629b68c307a3e239a3de855e447ff14cd0e1d7add81f  generated-unique.jsonl
a53d03f4f85c3e87f8591fdd3335276fe0d1d815277d929b2008572fe940ad9e  relabels.csv
2715b8bf5f1546b3510b16c74a810412902bed3209acba8d792cd40535b1ce77  relabel-1b-candidates.csv
5b44bcd13e7ecc44681b9f8d2ae011285fe2328d58d1e5ba16711fea8c2209f2  summary.md
```

**S0 train:** `data/round12/final/S0/train.jsonl` did not exist when this was written. **S0 = S1 minus the `status=generated` rows (97,613 - 2,322 = 95,291 rows), sha256 recorded at launch** (in the findings, before the first step; S0 is built only by that filter, no other change).
Intermediate inputs: `data/round12/SHA256SUMS` (train `84062b23df99d123...`, val `6447e90888aa...`, v3eval `292c5fd831e0...`; holdout `ae9ea2f09ca8...` before the 2 D136 relabels).

## 4. Baselines and scoring path (frozen)

**Baselines.** Published **0.2.0 fp32** (`data/train/ckpt-r8soft/final`, safetensors sha256 `974dff016a03f79868c498dff50fd11c70669e975e7284e881950f11bd6af3ae`; the fp32 ONNX re-exports byte-identical to the shipped `model-fp32.onnx` `8503b655...`) is the baseline that decides. **r11 fp32** (`data/train/...` r11 checkpoint, safetensors sha256 `cf6255a1a73415a20b9e9f3a5d6d2ccd34259c0b71762cb0895043507ff0e62b`) is reported for reference only and is not part of the rule. Note: r11 trained on exam #3 rows, 0.2.0 on neither exam; neither trained on exam #4 rows, so goharbor and render are unseen by both.

Scoring, one path for all models (0.2.0, r11, S0, S1, S2):
1. **p-jsonl on the 455 holdout rows**: PyTorch fp32, CPU, batch 1, max_len 128, class order r, w, x (same as `holdout-r11.md`). Text is the `text` field of `holdout.jsonl` (sha256 above).
2. **T per model**: refit on `val.jsonl` (4,180 rows, sha256 above) with `temp_fit` of `train/tune_cuts.py`, on that model's own val probs from the same batch-1 path. T applied to pIsX / pChanges.
3. Files in rwxmap's shape `{"id","model","pIsX","pChanges"}`; `model` = `rwxlite-r12-NAME+<sha8 of model.safetensors>`.
4. **rwxmap scores.** The p-jsonl goes through rwxmap's real CLI second pass with their replay tool (`poc/replay-r12/replay.mjs`, mode a: lower only at top-letter p >= 0.97, raise needs no cut-off). The truth is `holdout.jsonl` labels (D136). The primary numbers are rwxmap's: **exact / too loose / too tight**. We also report **argmax** and **a_none** (no cut-off) for reference only; they decide nothing.
5. **The 6 named leak rows:** `gate3-0482`, `r9-0543`, `r9-0814`, `r9-0897`, `r9-1109`, `r9-1164`: the top-letter p of each model (and which letter). Caveat: 5 of these 6 seeds have look-alikes among the generated rows in S1/S2, so for S1/S2 this measures fix-on-the-seen-case, not generalisation. S0 and 0.2.0 are the unseen-case reading.
6. **Held-out confidence curve:** exact / too loose / too tight at lower cut-offs **0.90, 0.95, 0.97, 0.99** (rwxmap `replay.mjs --lower-min-p`), per model. 0.97 is the product rule; the others are the check that 0.97 is still honest.

Truth for the 455 rows is opened once, after the p-jsonl sha256s are committed.

## 5. Decision rule (frozen)

A run **wins over 0.2.0** on the held-out 455 rows under the CLI rule (0.97) if **too loose <= 0.2.0's too loose AND exact >= 0.2.0's exact + 3**. Ties do not win.

- Among winners: **fewest too loose, then most exact.**
- If S2 beats S1 only by having more too tight or more leaks, prefer S1.
- Differences of **2 or fewer too-loose rows are noise** (455 rows, a dozen leaks in play). No significance test is run.
- If no run wins, the answer is "no run is shown better than 0.2.0 on these vendors"; nothing is shipped.
- This is an **internal pick, not a release gate.** Release still needs a fresh exam #5 under D135.

## 6. What is not allowed after training starts

No change to data, hyperparameters, the T rule, the cut-off, or the scoring rule. No adding or dropping a run. No re-running for a "better" result. A rerun only for a crash (or a row-join bug), recorded in the findings with the reason. S0 is a control and is kept in the results whatever it shows.

## 7. Exam #5 hygiene

Round 12 trains on **726 vendors** (identical vendor set in S1 and S2; S0 is a subset). The list is generated from the frozen train files, not retyped:

```
python3 -I -c "import json;print('\n'.join(sorted({json.loads(l)['vendor'] for l in open('data/round12/final/S1/train.jsonl')})))" > vendors-r12-train.txt
```

It includes, beyond round 11's: exam #3 vendors clerk, ory, neon, supabase, mux, netbird, novu (already in r11), exam #4 vendors **chatwoot, immich, permit, polar, zulip** (new in r12), and the made-up vendor names of the generated rows (cloudnimbus, orbitdesk, tessellate, ...). **goharbor and render are held out here but are exam #4 vendors, so they are burned for exam #5 as well.** The list file is sent to rwxmap for exclusion from exam #5 (D135). The candidate that is released must be retrained or re-verified on its final data; this prereg does not cover a model trained on the held-out vendors.

## Run order

1. This file committed (data sha256 above). 2. Build `S0/train.jsonl` (filter only), record its sha256 in the findings. 3. Queue S0, S1, S2 on the home server, sequential, from the base model. 4. Copy each `final` back; refit T; run predict (never opens truth); commit the p-jsonl sha256s. 5. rwxmap replays and scores once; we add argmax / a_none, the 6 leak rows and the curve.

## Result

Scored by the rwxmap CLI (rwxmap commit 15bf477), mode a, lowering only at p >= 0.97, on the 455 held-out goharbor+render rows. Right / too loose / too tight:

| Model | Right | Too loose | Too tight |
|---|---|---|---|
| mechanical | 387 | 14 | 54 |
| shipped 0.2.0 (T 0.844) | 425 | 9 | 21 |
| 0.2.0 prereg baseline (refit T 0.9211) | 418 | 9 | 28 |
| S0 | 424 | 9 | 22 |
| S1 | 421 | 9 | 25 |
| S2 | 423 | 9 | 23 |
| r11 | 422 | 10 | 23 |

Prereg error: §4 step 2 refit T for every model, including the 0.2.0 baseline, instead of comparing at the shipped T 0.844 (the project rule: compare candidates at the shipped baseline T). The refit cost 0.2.0 7 exact (425 to 418). By the frozen §5 rule some runs "win" against 418; against the shipped 425 none does.

Verdict: no gain over shipped 0.2.0; 0.2.0 stays. No win is claimed.

Lessons:
- The temperature alone moved 0.2.0 by 7 exact, more than any round 12 training did (1 to 6).
- The variants fixed the seen cases (the harbor leaks they trained on) but opened render's PUT secret-files (2 rows, the same rows r11 got wrong).
- 5 harbor job stops are missed by every model.

Next: calibration (temperature / the 97% line) tuned on existing labelled sets, confirmed once on a fresh exam.
