# Pre-registration: held-out-vendor experiment (ory.sh, clerk.com), 2026-11-04

**Status: FROZEN when committed on branch `r11-holdout`, before any of the three trainings has started or finished.** An internal experiment, not a gate.
D135 (the next release decision) still needs a fresh exam #4 with vendors no model has seen; nothing here replaces that.

## Question

Does adding new vendors' labelled rows help on vendors the model has never seen, and which way of adding them works best?

## Held-out vendors, and how they were chosen (stated openly)

Held out: **ory.sh (179 rows) and clerk.com (263 rows)**, 442 rows, from rwxmap's exam #3. They were chosen **after seeing the exam #3 results**: those two vendors
hold 9 of the 15 too-loose leaks and the logout/credential shapes. That is selection by difficulty, so this hold-out is harder than a random one and an
optimistic reading of any gain is unwarranted. It is not a fresh exam: the held-out rows were scored before (by the shipped r10 and 0.2.0 models), and the
held-out *labels* have been seen by people. What stays clean is that no model in this experiment trains on a row of either vendor, and no code, cut, T rule or text
format is tuned on them.

Data (read in place, never copied into git): rwxmap `/home/hamr/PycharmProjects/rwxmap/data/exam3-2026-11-04/` `ops.csv` sha256 `fff7afa983c7fc85e2073e5662c4c317c69e37a1dd92a04c7e5dc04ecf43d790`,
`truth.csv` sha256 `929725d51397098b6f45d86a5a551e7f0c095875557a944c02e08930efdab3c0`. Truth is opened once, by `train/holdout_score.py`, after the prediction files exist.

## Training sets

All variants exclude ory and clerk. **new5** = the exam #3 rows of neon.com 193, supabase.com 170, mux.com 192, netbird.io 231, novu.co 149 = **935 rows**
(labels r 427 / w 290 / x 218; one-hot targets because rwxmap committed no Jev p per exam #3 row, as in round 11). Text built exactly as in round 11
(`m1/round11-assemble.py`: rwxmap classifyRow at `46235eab7043fe69a4fea18e0ad77678a82123cb`, `fmt_text`); these texts equal the exam-time inputs on all 1,377 rows.
r10 train = 92,864 rows (r 52,394 / w 24,574 / x 15,896; 601 vendors). val (4,180) and v3eval (5,716) are r10's, unchanged, identical for all variants.
`m1/holdout-assemble.py` rebuilds everything from round 11's assembly (re-run reproduced round 11's `assembly-sha256.txt` byte for byte) and asserts no ory/clerk vendor or id in any variant.

| variant | init | training rows | notes |
|---|---|---|---|
| **A** | base `sentence-transformers/all-MiniLM-L6-v2` | r10 train + new5 x1 = **93,799** | new5 = 1.00% of rows |
| **B** | base | r10 train + new5 **x5 by duplication** = 92,864 + 4,675 = **97,539** | duplication, not a sample weight: four extra copies of each new5 row (same way QUERY copies were done); ids repeat on purpose; new5 = 4.79% of rows, 3,048 steps |
| **C** | **0.2.0 model** (`data/train/ckpt-r8soft/final`) | new5 x1 + 10,000 old rows = **10,935** | old rows sampled from r10 train stratified by (label, vendor): proportional allocation over the 1,334 non-empty strata, at least 1 row each (all 601 vendors present), largest-remainder rounding, per-stratum `random.Random("1|label|vendor")`; sample labels r 5,576 / w 2,660 / x 1,764; new5 = 8.55%; **LR 2.5e-5 (half of r10's 5e-5)**; 342 steps |

Common recipe (identical to r10/r11): soft targets (`--soft`, alpha 0.7; new5 rows are one-hot), 1 epoch, batch 32, AdamW weight decay 0.01, warmup 6% then linear decay,
max_len 128, `torch.manual_seed(1)`, `--threads 4`, `--ckpt 500`. C starts a fresh optimizer and schedule from the 0.2.0 weights. The only code change to training is the
backward-compatible flag `--init DIR` in `train/finetune.py` (default None = base model; a default run was tested to give byte-identical weights, probs and log lines to the r11 script, see "Checks").
A and B are single runs (one seed each); there is no variance estimate. C's old-row sample is from r10 train, which is a superset of what 0.2.0 trained on (r8 train).

**Baselines, no training, never saw ory or clerk:** 0.2.0 (`data/train/ckpt-r8soft/final`, safetensors sha256 `974dff016a03f79868c498dff50fd11c70669e975e7284e881950f11bd6af3ae`) and r10 (`data/train/ckpt-r10/final`, sha256 `28e5830356b84f3fada311811f6f382363a5fc37f5060e117f952575c5767512`).

## Scoring (frozen here, before any training finishes)

- **One path for all five models: PyTorch fp32 on CPU, batch 1, max_len 128** (`train/holdout_predict.py`). Not the shipped int8 ONNX, because the new models have no export; fp32 torch is the same function the int8 file approximates. Baseline numbers here will therefore differ slightly from exam #3's int8-pc rows; the exam #3 fp32 rows restricted to these 442 are a sanity check, not the comparison.
- Rows: the 442, from `m0/exam3-inputs.mjs` on `m1/holdout-ops.py`'s filtered `ops.csv` (rwxmap at 46235ea); input rows are identical (all 442 fields) to `data/exam3/inputs.jsonl`.
- **T per model**: refit on the r10 val split (4,180 rows) with `temp_fit` of `train/tune_cuts.py`, on that model's own val probs from the same torch batch-1 path. Class order r, w, x.
- Configs and cuts unchanged from exam #3 (`exam_score.mode_a`, `exam_fresh.configs`/`piles`, cuts 0.30/0.40/0.15/0.05, margin 0.6). Scored with `train/holdout_score.py` (a copy of `exam3_score.py` restricted to these rows): **GONOGO_lba097, a_none, mechanical** (all configs are written), per vendor and per method, and every too-loose row listed with its type.
- **Primary comparison: GONOGO_lba097 too-loose count and right count, each model vs 0.2.0**, on all 442 rows (per-vendor beside it). Order: fewer too-loose first, then more right. The A-vs-r10 difference isolates the effect of the new rows (r10 data held fixed); r10-vs-0.2.0 is the effect of the earlier data rounds. With 442 rows and about a dozen leaks in play, a difference of 2 or fewer too-loose rows is called noise; right counts are compared with the same caution. No significance test is run.
- Also written: `p-NAME.jsonl` per model in rwxmap's shape (`{"id", "model", "pIsX", "pChanges"}`, T applied, `model` = `rwxlite-holdout-NAME+<sha8 of model.safetensors>`) so rwxmap can replay mode a later.
- No model, T rule, cut, config or code is changed after predictions exist. A rerun only for a crash or a row-join bug, recorded in the findings.

## Run order

1. This file and the code are committed (with the data sha256s below). 2. Queue A, B, C on the home server (`~/rwxlite-train/r11h-A`, `-B`, `-C`, one sequential nohup'd script). 3. Copy each `ckpt-*/final` back; run predict (never opens truth); commit the prediction-file sha256s. 4. Score once.

```
# inputs (once)
python3 -I m1/holdout-ops.py /home/hamr/PycharmProjects/rwxmap/data/exam3-2026-11-04/ops.csv WORK/ops442.csv DATA/heldout-ids.txt
RWXMAP_DIR=<rwxmap at 46235ea> node m0/exam3-inputs.mjs WORK/ops442.csv WORK
# predict (cwd train/ or PYTHONPATH=train); 0.2.0 and r10 are the baselines
python3 train/holdout_predict.py WORK DATA/A/val.parquet --model v020=<ckpt-r8soft/final> --model r10=<ckpt-r10/final> --model A=<A/final> --model B=<B/final> --model C=<C/final> --tokenizer <ckpt-r8soft/final>
# score, once
python3 train/holdout_score.py WORK <rwxmap truth.csv> 929725d51397098b6f45d86a5a551e7f0c095875557a944c02e08930efdab3c0
```

## Checks done before freezing

- C init = the 0.2.0 model: see the "Init verification" section below (safetensors sha, val probs vs the stored `probs-r8soft-val.npy`, ONNX re-export hash vs the shipped 0.2.0 fp32).
- `--init` default run is identical to the r11 `finetune.py` (see "Default-run identity" below).

## Init verification (C starts from the 0.2.0 model)

`python3 m1/holdout-verify-init.py data/train/ckpt-r8soft/final <val.parquet> data/train/probs-r8soft-val.npy <scratch>` (onnx 1.23.2, torch 2.10.0+cpu):
- `model.safetensors` sha256 `974dff016a03f79868c498dff50fd11c70669e975e7284e881950f11bd6af3ae`; the copy on the server (`r11h-C/init-r8soft/`) has the same sha256.
- **Re-exporting that checkpoint to fp32 ONNX with `m1/export_onnx.py`'s exact call gives sha256 `8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b`, byte-identical to the shipped 0.2.0 `data/m1/model-fp32.onnx`.** (The int8-pc file was not re-quantized; it is derived from this fp32 file.)
- Val probs (batched, as `finetune.py` predicts) vs the stored `probs-r8soft-val.npy`: argmax equal on 4,179 of 4,180 rows; the one outlier (max |dp| 0.97) is a val row whose text changed between the r8 and r10 val splits (2 of 4,180 texts differ).

## Default-run identity of `--init`

`git diff` of `train/finetune.py` is two lines: the flag `--init` (default None) and `from_pretrained(a.init or BASE, ...)`. Test: the r11 script (`git show r11:train/finetune.py`) and the new script, same 2,000-row sample of A's train and 300-row val/v3eval samples, `--epochs 1 --soft --alpha 0.7`, no `--init`: `model.safetensors` sha256 `32edeccdbc838eed12924c2d1ed377b91bec9277b607129f2d6afbdc1e51a14e`, `probs-*-val.npy` `f20a4cfc4440d2ec...`, `probs-*-v3eval.npy` `61e32abe7d71d2a2...` identical in both; the step/loss log lines identical.

## Data sha256 (from `m1/holdout-assemble.py`, deterministic: a second run gave the same file)

Inputs: round 11 `train.jsonl` `766948c49bf1da609e92efb6b0d6ee5cc79a8ff1d5c68938f73c0259d2c95355`, `val.jsonl` `b854024e...` , `v3eval.jsonl` `292c5fd8...` (= `data/round11/assembly-sha256.txt` of the round-11 worktree); exam #3 `ops.csv` / `truth.csv` as above.

```
244bffd69395fabfaadf993ec68287df5d01978c7fc87b146ad5e2e261da1605  A/train.parquet
7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad  A/v3eval.parquet
2ad1581222797c157ff40016de3cc4d647dd2f2f54233ff5f5a9f578f4135549  A/val.parquet
8b73a9dd54df9b002c1e9b69c1ff9726ada9a5ed37ac38ebf112110e2328ba3e  B/train.parquet
7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad  B/v3eval.parquet
2ad1581222797c157ff40016de3cc4d647dd2f2f54233ff5f5a9f578f4135549  B/val.parquet
80cf3869b45355d94c0604d4377abbb82ebc48eaebb8caef65922633720507a5  C/train.parquet
7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad  C/v3eval.parquet
2ad1581222797c157ff40016de3cc4d647dd2f2f54233ff5f5a9f578f4135549  C/val.parquet
99a84d4d50a5a31965467a9b63db8f23b49560aa7d7887dcb8e80c914586e2dc  heldout-ids.txt
9deec3a15d30c840d4c8bb5a8bbc7a7509490f2ab8f515b31982ed1223ff7f45  holdout-summary.json
```

Other frozen files: `data/train/ckpt-r10/final/model.safetensors` `28e5830356b84f3fada311811f6f382363a5fc37f5060e117f952575c5767512`; `ory/clerk` ops file `ops442.csv` is derived by `m1/holdout-ops.py` (ids in `heldout-ids.txt`).

## Server

4 cores (not 8) on the home server, so `--threads 4`; estimated A ~52 min, B ~55 min, C ~6 min. Queue: `m1/holdout-queue.sh` (copied to `~/rwxlite-train/r11h-queue.sh`), logs `~/rwxlite-train/r11h-X/data/train/finetune-r11h-X.log`, pid `~/rwxlite-train/r11h.pid`, results `r11h-X/data/train/ckpt-r11h-X/final`. r10 and r11 directories are not touched.
