# Label inventory (for the shared BRIEF-v4 relabel plan with rwxmap)

Written 2026-11-05 on branch `dev`. Read-only inventory: no label, data file or model was changed, no paid call, no home-server access. Every count below was computed from the files under `data/` (gitignored, so numbers can only be re-derived on this machine) and checked against `docs/product/prd.md` ("PRD") and `docs/wiki/findings.md` ("findings"). Where a fact comes from a document, the source is in brackets. Where two sources disagree, both are given.

## 1. Plain-English summary

- rwxlite has **no single label source**. Almost every training row is labelled by a **recipe**: rwxmap's mechanical rule (method floor: GET = r, PUT/PATCH = w, POST = x, DELETE = x, plus word rules) and, on the rows where it could be wrong, the hosted model **Jev** (`jev-1.14.0`) answering one yes/no question per row. Jev's probability moves the label or becomes a soft training target. A small slice of rows has **hand labels under BRIEF-v3**: two blind labellers (Claude worker sessions, not humans) per row, with the user ruling disputes. [PRD "Labelling", "Round 9 hand labels"; findings "M0 step 3", "Gate-3"]
- **Everything is BRIEF-v3** (rwxmap D87 + D98; D136 added for restart/stop/start/pause = w). There is no BRIEF-v4 data yet. The only older standard in the data is rwxmap's v1 labels (1,152 `hand_set` + 549 `calib_set` flags in `data/m0/mechanical.jsonl.gz`), used once in a failed gate report and then dropped. [PRD "Step 4"; findings "M0 step 3b"]
- **The ~95k round-12 training rows (95,291) break down as**: 75,483 (79.2%) trained on Jev's soft probability (71,225 original rows + 4,258 QUERY copies of GET rows); 15,212 (16.0%) mechanical-only one-hot (8,548 DELETE = x, 6,598 mechanical word-rule rows where no Jev cut applies (Jev may have an answer stored, but it is not used), 66 narrow credential-rule rows); 4,596 (4.8%) hand/BRIEF-v3 one-hot (949 fresh exam + 1,377 exam #3 + 1,050 exam #4 + 1,073 round-9 hand rows + 87 label fixes + 56 D136 relabels + 4 user rulings). Generated (Haiku) variants add nothing to this base; they exist only in S1 (+2,322 rows) and S2 (+5,767 rows) and none of those models shipped. 0.2.0's set (87,657 rows) is 82.6% Jev-soft and 17.4% mechanical-only, with **zero** hand-labelled rows. Details and definitions in section 5.
- **Burned sets** (scored once, can never be tuned on): the 2026-09-22 exam (rwxmap's), gate-1, gate-2, the fresh exam (949), exam #3 (1,377), exam #4 (1,505), gate-3, gate-4. Several of them were later **used for training** (fresh exam from round 10; exam #3 from round 11; 5 of exam #4's 7 vendors from round 12; gate-3, gate-4 and round-9 rows are in the training pool with Jev/mechanical labels and only 95 + 8 of their labels were corrected). So a relabel plan must treat "burned" and "in training" as separate questions (section 4).
- **BRIEF-v4 access-rule estimate (scoping only, no label changed)**: across all distinct operations we hold (104,855), a deliberately broad pattern flags about **5,400** operations currently labelled w or r, and a narrower pattern about **1,030**. In the 95,291-row round-12 training set the figures are 4,670 and 936. Hits are concentrated in Microsoft Graph and AWS (narrow: 574 of 1,033 are `microsoft`, 147 are `amazonaws`). Section 7. The broad number contains a lot of noise; the narrow one still includes some false positives.

## 2. Who or what produced the labels

| Source | What it is | BRIEF version | Where it enters |
|---|---|---|---|
| **Mechanical** | rwxmap `classifyRow` run over all 123,339 APIs.guru operations (673 providers; 97,275 distinct op keys), output `data/m0/mechanical.jsonl.gz` (regenerated 2026-11-04 so it already carries the `credential-set` rule). Letters: method floor + word rules (`read-verb`, `cant-undo-verb`, `modify-verb`, ...). DELETE is x. [PRD "Step 1"; findings "M0 step 1"] | v3 rules | Training: the hard label wherever Jev did not move it, plus the "lean" letter in every input text |
| **Jev** | Hosted model `jev-1.14.0` (rwxmap's client copied; key never printed). One question per row by method, sent method/path/operationId/summary/description only, never the mechanical letter. Questions are the byte-copied rwxmap criteria files in `m0/questions/` (rwxmap commit a7bc855): `criteria-x.mjs` (isX) for POST, `criteria-x-raise.mjs` (isX) for PUT/PATCH, `criteria-changes.mjs` (changes) for GET and for the second POST question. DELETE and HEAD/OPTIONS/TRACE are never asked. [PRD "Step 2", "Round 6"] | v3 (criteria follow D87/D98) | Training: moves the label across a cut and supplies the soft target |
| **Hand labels, "blind labellers"** | Two blind labellers (Claude worker sessions, each with its own scratch dir) label `blind.csv` under `BRIEF-v3.md` with no mechanical letter and no Jev p. Agreement 98 to 98.8%. Disagreements ruled by the user (gates, fresh exam); for round-9 rows there was no ruling and the stricter letter (r < w < x) wins. [PRD "Step 4", "Round 9"; findings "Gate-3"; each set's README] | v3 | Gates, fresh exam, r9-hand, round-10 hand check |
| **rwxmap truth files** | Exams #3 and #4 were labelled on rwxmap's side (two blind labellers plus user rulings), shared as `truth.csv`; D136 later produced `truth-d136.csv` (restart/stop/start/pause x to w). rwxlite reads them in place from rwxmap's `data/exam3-2026-11-04/` and `data/exam4-2026-11-04/` and keeps no truth file of its own for exam #3. [prereg-r12.md section 3; holdout-r11.md; exam-prereg-exam4.md] | v3 + D136 | Exam scoring; training rows `ex3-`, `ex4-` |
| **v3 truth (v3eval)** | rwxmap's two tuning files joined to our operations: `combined-2026-09-21` (6,557 rows, nine blind labellers + rulings) and `relabel-buildset-2026-09-23` (1,819 rows, 13 vendors). Single labeller per row, 410 rows flagged low confidence. Source mix inside `v3eval`: buildset 3,726 rows, provider-corpus 1,380, burned exam 2026-09-17 610. [findings "M0 step 3b"; `data/round12/v3eval.jsonl` fields `tset`, `tsrc`, `lowconf`] | v3 | Tuning/practice set, never trained on |
| **User overrides** | Round 10: 5 rulings (`data/round10/rulings.csv`; 4 hit train rows). Round 12: `data/round12/user-label-overrides.csv` (1 row, codat POST billCreditNotes w to x, 2026-11-05) and `label-fixes.csv` `decided_by user`. [PRD "Round 10"; prereg-r12.md] | v3 | Training one-hot rows |
| **Haiku generated variants** | Haiku writes 5 surface variants (made-up vendor, path, operationId, wording; seed's label kept) and up to 2 contrast variants (one small change, different letter) per seed, told to follow BRIEF-v3 word for word. One-sided Jev filter (drop a w/r variant Jev calls x; keep x). [classifier-training.md "Labelling generated variants"; prereg-r12.md section 3] | v3 + D136 | S1/S2 only |
| **Vendor hints** (AWS IAM access level, GitHub fine-grained permission) | Hints that pick rows for review, not labels. [findings "Vendor labels, step A"; PRD "Vendor labels"] | none (not BRIEF) | Not used in any training or exam |
| **rwxmap v1 labels** | `labelled.csv` hand labels + calibration-2026-09-14, BRIEF v1. Flags `hand_set` 1,152 / `calib_set` 549 in the mechanical dump. [findings "M0 step 3b"] | **v1** | Only the failed first parity report; not a standard |

Important caveat for the relabel plan: "human truth" in this repo means **Claude workers under a written brief, ruled by the user**. The memory fact "same model plus same brief is one opinion" applies to all of them. Gates 3 and 4, and the fresh exam, round 9 and the round 10 hand check, were labelled this way.

## 3. Inventory of every labelled or label-bearing set

Counts: rows; distinct operations by provider+method+path+operationId; distinct provider+method+path; providers (distinct `provider` strings); vendors (first dotted token of the provider). "r / w / x" are the label shipped in that file (for gates, exams, r9-hand and v3eval the human truth; for training files the training label). Rounds overlap heavily: each training set contains the previous one.

| set | path(s) | rows | distinct ops (provider+method+path+opId) | distinct provider+method+path | providers | vendors | r / w / x |
|---|---|---|---|---|---|---|---|
| train-r8soft(0.2.0) | `data/train/train.jsonl` | 87,657 | 87,657 | 86,483 | 605 | 597 | 47,841 / 24,161 / 15,655 |
| train-r10 | `data/round10/train.jsonl` | 92,864 | 92,864 | 91,677 | 609 | 601 | 52,394 / 24,574 / 15,896 |
| train-r11 | `data/round11/train.jsonl` | 94,241 | 94,241 | 93,054 | 616 | 608 | 53,002 / 25,011 / 16,228 |
| train-r12-S0 | `data/round12/train.jsonl (= data/round12/final/S0/train.jsonl before D136 relabels)` | 95,291 | 95,291 | 94,104 | 621 | 613 | 53,481 / 25,449 / 16,361 |
| val-r12 | `data/round12/val.jsonl (r10/r11: val.jsonl)` | 4,180 | 4,180 | 4,178 | 67 | 66 | 2,435 / 1,145 / 600 |
| v3eval (truth) | `data/round12/v3eval.jsonl (same file in r10, r11)` | 5,716 | 3,723 | 3,721 | 23 | 23 | 1,080 / 2,761 / 1,875 |
| holdout-r12 (goharbor+render) | `data/round12/holdout.jsonl` | 455 | 455 | 455 | 2 | 2 | 246 / 113 / 96 |
| generated variants (unique) | `data/round12/final/generated-unique.jsonl` | 1,199 | 1,082 | 1,080 | 138 | 134 | 210 / 615 / 374 |
| fresh exam 2026-11-03 (fx) | `data/exam-2026-11-03-fresh/{ops,truth}.csv` | 949 | 949 | 949 | 4 | 4 | 406 / 328 / 215 |
| gate-1 (11-03) | `data/gate-2026-11-03/` | 600 | 600 | 600 | 227 | 227 | 368 / 194 / 38 |
| gate-2 (11-04) | `data/gate-2026-11-04/` | 600 | 600 | 600 | 219 | 218 | 353 / 204 / 43 |
| gate-3 (11-06) | `data/gate-2026-11-06/` | 800 | 800 | 797 | 257 | 255 | 384 / 352 / 64 |
| gate-4 (11-07) | `data/gate-2026-11-07/` | 800 | 800 | 800 | 250 | 248 | 399 / 347 / 54 |
| r9-hand (stricter of A/B) | `data/r9-hand/` | 1,200 | 1,200 | 1,200 | 247 | 245 | 202 / 966 / 32 |
| exam #3 (ex3, labels from S0 train) | `data/exam3/inputs.jsonl (no truth file in rwxlite; labels read from the ex3- rows of round 11/12 train)` | 1,377 | 1,377 | 1,377 | 7 | 7 | 608 / 439 / 330 |
| exam #4 (ex4, truth.csv pre-D136) | `data/exam4/{inputs.jsonl,truth.csv}` | 1,505 | 1,505 | 1,505 | 7 | 7 | 715 / 467 / 323 |
| exam 2026-09-22 (x22, NO labels here) | `data/exam-r8soft/inputs.jsonl (inputs only; truth lives in rwxmap)` | 4,279 | 4,279 | 4,279 | 3 | 3 | not in rwxlite |
| train-r12-S1 | `data/round12/final/S1/train.jsonl` | 97,613 | 96,335 | 95,142 | 738 | 726 | 53,901 / 26,669 / 17,043 |
| train-r12-S2 | `data/round12/final/S2/train.jsonl` | 101,058 | 96,335 | 95,142 | 738 | 726 | 54,531 / 28,494 / 18,033 |

Notes:
- 0.2.0 = the published model = `r8soft` (checkpoint sha256 `974dff01...`, trained on `data/train/train.jsonl`, 87,657 rows). [findings "Round 8"; exam-prereg-r8soft.md; "Vendor labels step A"]
- The `holdout` word is used twice. `data/round12/holdout.jsonl` is goharbor + render (455 rows, held out of S0/S1/S2). `data/holdout/` holds checkpoints of the earlier round-11 experiment that held out ory.sh + clerk.com (442 rows of exam #3), see `docs/wiki/holdout-r11.md`.
- `v3eval` has 5,716 rows but only 3,723 distinct operations because several spec snapshots of the same operation are kept; the scoring code reports it raw and deduplicated. [PRD "Round 10", decision 4]
- Providers/vendors counts for the exams are tiny on purpose: whole vendors were drawn, never rows. The gates are 600 to 800 rows spread across about 220 to 255 vendors, one row per op key. [gate READMEs]
- Row counts of files not in the table: `data/exam3-smoke` (949 rows) and `data/exam4-smoke` (1,377 rows) are smoke-run inputs and prediction files (no labels, copies of exam inputs); `data/exam-fresh-r8soft` is the 949-row fresh exam's inputs and predictions; `data/exam-r8soft` is the 4,279-row 2026-09-22 exam's inputs and predictions (truth stays in rwxmap, rwxlite never trained on it). `data/fresh-exam-specs` holds source OpenAPI specs and a shortlist of candidate vendors, no labels. `data/m1*`, `data/train/ckpt-*`, `data/round12/models`, `data/holdout/ckpt-*` are models and probability arrays, not labels.

## 4. Per-set provenance, burn status and model use

Model rounds: **0.2.0 = r8soft**; **r10** (unreleased); **r11** (unreleased); **r12 S0 / S1 / S2** (trained, none shipped; 0.2.0 stays). [PRD "Round 10", "Round 11"; findings "Exam #3", "Exam #4", "Round 12"]

### 4.1 Training sets (built per round)

| Set | Rows | Label producer | Used by | Notes / source |
|---|---|---|---|---|
| `data/train/train.jsonl` (+ `.parquet`, `val` 4,180, `v3eval` 5,716 built together) | 87,657 | Mechanical letter, moved by Jev at the round-6 cuts (lower 0.20, POST second question r cut 0.20, raise-wx 0.60, raise-get 0.20); DELETE = mechanical x; narrow credential rule (66 rows). Soft targets from Jev p. Excluded: exam vendors, 10 locked vendors, the 19 `exam_opkey_overlap` rows, every id in gate-1/gate-2 `ids.txt` (1,481), the 5,716 v3 rows, 23,790 duplicate snapshots, 295 wobble rows, 201 non-asked non-DELETE rows | **0.2.0 (r8soft)**; also base of r10, r11, r12 | [findings "M0 step 4"; PRD "Round 6"] |
| `data/round10/train.jsonl` | 92,864 | r8soft set + 949 fresh-exam rows (`fx-`, hand truth) + 4,258 QUERY copies of GET rows (`-q`, label of the parent, Jev soft) + lean rebuilt from current rwxmap (28 rows get `credential-set`, written as `cant-undo-verb` in text) + round-9 hand labels applied to 1,074 train rows + 4 user rulings (hand check of 104 candidate + 30 decoy rows by labellers A/B) | **r10** | [PRD "Round 10"; `data/round10/assembly-summary.json`] |
| `data/round11/train.jsonl` | 94,241 | r10 + 1,377 exam #3 rows (`ex3-`, rwxmap truth, one-hot) | **r11** | [PRD "Round 11"; `data/round11/assembly-summary.json`] |
| `data/round12/train.jsonl` and `data/round12/final/S0/train.jsonl` | 95,291 | r11 + 87 label fixes (human truth from gate-3, gate-4 that overruled Jev, one-hot) + 1,050 exam #4 rows (chatwoot, immich, permit, polar, zulip) + D136 relabels (60 train rows; the 2 exam #3 ones are inside the 1,377). The two files differ only by the D136 relabels | **r12 S0** (control) | [prereg-r12.md section 3; `data/round12/assembly-summary.json`] |
| `data/round12/final/S1/train.jsonl` | 97,613 | S0 + 2,322 generated rows (1,199 unique, mostly x2 repeats) | **r12 S1** | [prereg-r12.md] |
| `data/round12/final/S2/train.jsonl` | 101,058 | S0 + 5,767 generated rows (x5 repeats of the same 1,199) | **r12 S2** | [prereg-r12.md] |
| `data/round12/variants-*.jsonl`, `final/generated-unique.jsonl` | b1 248, b2 287, b3 273, b4 301, x2 97, d136 96, kept 1,098, dropped 11, final 1,103; unique generated 1,199 (r 210 / w 615 / x 374) | Haiku under BRIEF-v3 (+D136); seeds are 166 real rows from burned sets, picked by `m1/r12-seeds.py` (182 seeds: 6 leak, 26 raise-miss, 150 unsure-right, training vendors only); Jev one-sided check (`jev-variants.jsonl` 1,095 asks, $0.111; `jev-x2.jsonl` 97 asks, $0.006) | S1, S2 | `variants-final-summary.md`; `seeds-summary.md` |
| `data/round12/val.jsonl` | 4,180 | Same Jev recipe as train, 66 vendors, plus 16 label fixes (round 12) | Temperature (T) fit and no-regression check; not trained on | r8soft T = 0.844 fit on val |

### 4.2 Practice and held-out sets

| Set | Rows | Label producer | Status | Notes |
|---|---|---|---|---|
| `v3eval.jsonl` (all rounds, byte-identical) | 5,716 | rwxmap v3 truth (section 2); `label` field in the file is the training recipe's label, `truth` the human one | **Tuning set**, never trained on. Cuts, abstain table, LOVO all tuned here, so it is in-sample-ish for the recipe. Not a pass claim | 23 vendors; github, microsoft etc. still in train under other operations |
| `data/round12/holdout.jsonl` | 455 (goharbor 203, render 252) | rwxmap exam #4 truth with D136 applied (2 rows moved x to w) | **Burned for model comparison**: scored on 0.2.0, r11, S0, S1, S2. Not in any train file. Chosen after seeing exam #4 results (selection by difficulty) | [prereg-r12.md; findings "Round 12"] |

### 4.3 Gates (label-quality gates, each used once)

| Set | Rows | Labels | Burn status | Trained on? |
|---|---|---|---|---|
| `gate-2026-11-03` (gate-1) | 600 | 2 blind labellers (588/600 agree), 12 ruled by user. BRIEF-v3. Labels A/B, rulings, truth in the dir | Burned. Label gate FAILED 90.8% (bar 95%) [findings "Fresh v3 gate"] | No: its 741 ids (every snapshot of each op key) are excluded from all training (0 shared ids with any train file). 23 of its rows appear in `r12/jev_overruled.csv` (mining only) |
| `gate-2026-11-04` (gate-2) | 600 | same method | Burned. Label gate PASSED 96.5% [findings "Gate-2 scored"] | No (740 ids excluded; 0 shared) |
| `gate-2026-11-06` (gate-3) | 800 (200 credential-word stratum + 600 general; `part.csv` is the key) | Labellers agreed 785/800, user ruled 15. Truth: credential stratum r 19 / w 149 / x 32 [findings "Gate-3"] | Burned for **both** projects (drawn for rwxmap's F2 exam) | **Yes, indirectly**: 738 of its 1,067 ids are in 0.2.0's training pool (drawn after training data was built) with Jev/mechanical labels; 50 labels corrected in r12 as fixes (45 train + 5 val) |
| `gate-2026-11-07` (gate-4) | 800 (200 write stratum, no word filter + 600 general) | same method | Burned for both projects | **Yes, indirectly**: 741 of 988 ids in training; 45 corrected fixes (42 train + 3 val) |

Gate-1 and gate-2 are the only sets with the strongest isolation (zero id overlap with training). Gate-1/-2 truth was still used to pick generated-variant **seeds** (gate-2026-11-03: 3 raise-miss + 16 unsure-right seeds; gate-2026-11-04: 1 + 12), so S1/S2 saw rewrites of those rows' shape, not the rows. [`data/round12/seeds-summary.md`]

### 4.4 Exams

| Set | Rows | Labels | Burn status | Trained on? |
|---|---|---|---|---|
| 2026-09-22 exam (`data/exam-r8soft/inputs.jsonl`) | 4,279 (cloudflare, pagerduty, sentry) | rwxmap's labels, not in rwxlite | Burned: M0 go/no-go, scored once on r8soft: NO-GO by the letter of the bar [findings "One-time exam: r8soft"] | Never |
| `exam-2026-11-03-fresh` | 949 (coolify 321, workos 269, getlago 217, resend 142) | 2 blind labellers, 934/949 agree, 15 ruled by user. BRIEF-v3 | Burned: scored once on r8soft, NO-GO by one row (5 loose vs limit 4) [findings "Fresh exam"] | r10, r11, r12 (all `fx-` rows, one-hot) |
| exam #3 (`data/exam3`) | 1,377 (clerk, neon, supabase, mux, netbird, ory, novu) | rwxmap truth (2 blind labellers + rulings), D136: 2 rows x to w | Burned: r10 and 0.2.0 scored, both NO-GO (15 and 14 loose) [findings "Exam #3 result"] | r11, r12 (one-hot); also the held-out ory+clerk experiment (442 rows) |
| exam #4 (`data/exam4`) | 1,505 (permit 263, immich 279, polar 190, goharbor 203, zulip 161, chatwoot 157, render 252) | rwxmap truth; `truth-d136.csv` for the restart cases | Burned: r11 and 0.2.0 scored, r11 NO-GO on both scorers [findings "Exam #4 result"] | 1,050 rows of 5 vendors in r12; goharbor + render (455) held out |

### 4.5 Hand-label and review sets

| Set | Rows | Labels | Use |
|---|---|---|---|
| `data/r9-hand` | 1,200 (800 lower-tier POST, 400 raise-wx PUT/PATCH; seeded random, vendor cap 40, no word filter) | A/B blind under BRIEF-v3, 1,186/1,200 agree, stricter letter wins, no ruling. Hand mix r 202 / w 966 / x 32. Against the Jev-recipe label: 32 too loose (22 + 10), 4 too tight | **Training**: 1,074 train rows one-hot since r10 (126 val rows keep old labels). Also scored as a replay set for rwxmap in round 12 (`data/r12/replay`) |
| `data/round10/` hand check | 134 (104 pattern candidates + 30 decoys) | labels A/B (`labels-A.csv`, `labels-B.csv`); only rows judged x changed; 5 ruled | 4 train relabels in r10+ (the fifth is a val/v3eval row, left alone) |
| `data/round12/label-fixes.csv` | 103 (train 87, val 16) | Human truth from `data/r12/jev_overruled.csv`, one-hot, status `fresh`, tier none. By source set: gate3 50, gate4 45, r9hand 8. Changes: x to w 50, w to x 30, x to r 13, w to r 5, r to w 3, r to x 2 | r12 S0/S1/S2 |
| `data/round12/user-label-overrides.csv` | 1 | codat POST billCreditNotes, w to x, 2026-11-05, user | r12 (1 train relabel) and one seed |
| `data/round12/final/relabels.csv` | 62 (train 60, holdout 2) | D136: restart x to w 41, stop/start/pause/resume 16, exam truth copy 2 + 2 holdout, user override 1 | S0/S1/S2 |
| `data/round12/final/relabel-1b-candidates.csv` | 649 candidate rows (train: unclear 360, keep-x 225, w 57; val: unclear 5, keep-x 2) | Candidates for D136 rule 1b (server/service/container/app/db/VM restart/stop/start/pause/resume, x to w). Each got a decision with a reason; only the 57 judged w were relabelled (= the 41 + 16 in `relabels.csv`); keep-x and unclear rows were left | Decision list; the 57 are in S0/S1/S2 |
| `data/r12/jev_overruled.csv`, `mistakes.csv`, `summary.md` | 383 rows where human truth beat Jev's letter (exam3 127, exam4 77, gate3 52, gate4 47, r9hand 36, gate1 23, gate2 21; 283 too tight, 100 too loose); 1,231 mistake rows for 0.2.0 by rule | Derived from existing truth, no new labels | Mining; source of the label fixes and variant seeds |

### 4.6 Jev passes (`data/m0/jev-*.jsonl`)

Every answer comes from model `jev-1.14.0`, 0 errors in all files. [findings "M0 step 3", "Two-step POST lower"]

| File | Rows (unique ids) | Question and method split | Cost |
|---|---|---|---|
| `jev-smoke.jsonl` | 30 | smoke: 10 changes GET, 10 isX POST, 5 PUT, 5 PATCH | ~$0 |
| `jev-pass1.jsonl` | 109,844 | isX on POST 34,800, PUT 7,540, PATCH 7,734 (`criteria-x` for POST, `criteria-x-raise` for PUT/PATCH); changes on GET 59,770. 673 providers | $9.97 |
| `jev-pass2.jsonl` | 14,188 | re-ask of rows with first p in 0.1..0.9 (wobble): POST 12,038, PUT 1,374, PATCH 352, GET 424. p is averaged over the two asks | $1.48 |
| `jev-post-changes-smoke.jsonl` | 20 | changes on POST (smoke) | ~$0 |
| `jev-post-changes.jsonl` | 34,800 | changes question (`criteria-changes`) on every non-DELETE POST row, to split lowered POST x into r or w | $3.11 |
| `jev-post-changes-2.jsonl` | 2,981 | re-ask of POST changes p in 0.1..0.9 | $0.27 |

Cumulative recorded spend for the training passes $14.83 of the $45 stop / $50 cap. The Jev passes are **teacher answers, not labels**: they only become labels through the cuts above. Jev's p is stored per row (`jev_p`, `jev_pA`, `jev_pB`, `jev_pC`) in every training file. Jev's x is precise (about 93%) but misses about half of real x (47.8% recall), so it errs toward w. [classifier-training.md]

### 4.7 Other files that carry labels or label hints

- `data/vendor/` (21,536 rows; AWS 12,602 + GitHub 8,934 joined to IAM access levels / fine-grained permissions): hints only, `candidates.csv` 1,153 review rows, `examples30.csv` 30. 12,414 of the rows are in 0.2.0's training pool and 1,293 in v3eval. No labels were changed. [findings "Vendor labels, step A"]
- `data/m0/parity-report*.json`: reports (Jev vs mechanical, vs v1 and v3 truth), not labels.
- `data/round10/` also holds `shapes-*.csv` (83 pattern candidates for the workos-style credential and logout shapes) and `dup-groups-split-leak.csv` (0 leaking groups); `data/round12/seeds*.csv` (182 seeds).

## 5. How the training rows were labelled, in plain words

**Step 0, every row gets a mechanical letter.** rwxmap's rules decide r, w or x from the HTTP method and a few words. GET is r, PUT/PATCH is w, POST is x, DELETE is x, then word lists nudge some rows. [PRD "Step 1"]

**Step 1, Jev is asked where the mechanical letter is most likely wrong.** The three "piles": **raise-get** (GET rows mechanical calls r; Jev answers "does this change anything?", p at or above 0.20 raises to w), **raise-wx** (PUT/PATCH rows mechanical calls w; Jev answers "is it x-level?", p at or above 0.60 raises to x), **lower** (POST rows mechanical calls x; if Jev's isX p is under 0.20 the row drops to w, or to r if the second "changes" p is under 0.20). Wobbly rows (two asks on opposite sides of a cut) were dropped (295). DELETE and credential-rule rows skip Jev. [PRD "Round 6"; findings "M0 step 4"]

**Step 2, the training target.** Each row's hard label is the letter above. Since round 8 the model is trained on a mix: 0.7 x a soft target built from Jev's probabilities plus 0.3 x the hard label. Soft targets exist only for rows with a Jev p in a pile; DELETE, credential-rule rows, "tier none" rows and every hand-labelled or generated row use the one-hot of their label (`soft_targets()` in `train/common.py`).

**0.2.0 (r8soft), 87,657 rows**

| Component | Rows | Share | Target | Hard label comes from |
|---|---|---|---|---|
| Jev soft, tier lower (POST x rows) | 20,067 | 22.9% | soft | Jev moved 15,143 (to w or r); 4,924 stayed x (mechanical floor) |
| Jev soft, tier raise-get (GET) | 42,581 | 48.6% | soft | 1,266 raised r to w by Jev; 41,315 stayed r (mechanical floor) |
| Jev soft, tier raise-wx (PUT/PATCH) | 9,768 | 11.1% | soft | 148 raised w to x by Jev; 9,620 stayed w (mechanical floor) |
| DELETE | 8,548 | 9.8% | one-hot | mechanical x, no Jev call |
| Mechanical word-rule rows, tier none | 6,627 | 7.6% | one-hot | mechanical letter (read-verb 2,579, cant-undo-verb 1,929, modify-verb 1,831, other 288) |
| Narrow credential rule | 66 | 0.1% | one-hot | rule gives x |
| **Hand-labelled** | **0** | 0% | | |

So in 0.2.0, Jev changed the letter on 16,557 rows (18.9%) and gave a soft target to 72,416 (82.6%); the rest is mechanical. (The 66 credential-rule rows sit across tiers: lower 35, raise-wx 13, none 18; they are counted only in their own line.)

**Round 12 S0, 95,291 rows (the "~95k")**

| Component | Rows | Share | Target | Hard label comes from |
|---|---|---|---|---|
| Jev soft, tier lower | 19,229 | 20.2% | soft | Jev moved 14,396; 4,833 stayed x |
| Jev soft, tier raise-get | 42,575 | 44.7% | soft | Jev raised 1,260; 41,315 stayed r |
| Jev soft, tier raise-wx | 9,421 | 9.9% | soft | Jev raised 146; 9,275 stayed w |
| QUERY copies of GET rows | 4,258 | 4.5% | soft | parent's label (4,142 r, 116 w) |
| **Subtotal Jev soft** | **75,483** | **79.2%** | | |
| DELETE | 8,548 | 9.0% | one-hot | mechanical x |
| Mechanical word-rule rows, tier none | 6,598 | 6.9% | one-hot | mechanical letter |
| Narrow credential rule | 66 | 0.1% | one-hot | rule |
| **Subtotal mechanical-only** | **15,212** | **16.0%** | | |
| Round-9 hand rows (BRIEF-v3, A/B stricter) | 1,073 | 1.1% | one-hot | hand label (28 of 1,074 differ from the Jev-recipe label) |
| Fresh exam (4 vendors) | 949 | 1.0% | one-hot | hand truth |
| Exam #3 (7 vendors) | 1,377 | 1.4% | one-hot | rwxmap truth |
| Exam #4 (5 vendors) | 1,050 | 1.1% | one-hot | rwxmap truth |
| Label fixes (gate-3/-4 truth overruled Jev) | 87 | 0.1% | one-hot | human truth |
| D136 relabels (restart/stop/start/pause = w) + 1 user override | 56 | 0.1% | one-hot | D136 ruling |
| User rulings (round-10 hand check) | 4 | 0.0% | one-hot | user |
| **Subtotal hand / ruled** | **4,596** | **4.8%** | | |
| Generated variants (S0) | 0 | 0% | | |

Counts are by ids and `status`/`tier` fields in `data/round12/final/S0/train.jsonl`; categories were assigned in the order generated, exam #4, #3, fresh, QUERY copy, label fix, D136, user ruling, r9-hand, DELETE, credential, tier none, Jev soft. Hard-label letters: the mechanical letter stands for 55,423 + 15,212 = 70,635 rows (74.1%); Jev changed the letter on 15,802 (16.6%); hand/ruled one-hot 4,596 (4.8%); QUERY copies 4,258 (4.5%). S1 adds 2,322 generated rows (2.38% of 97,613) and S2 adds 5,767 (5.71% of 101,058), all one-hot, `status generated`, label from the seed (surface variants) or Haiku (contrast variants). [`data/round12/final/summary.md`]

Data-quirk worth knowing for a relabel: after round 10 the `status` field value `credential` marks 1,078 more rows than the 66 credential-rule rows: the 1,074 round-9 hand rows and 4 user-ruled rows were stamped `credential` to force the one-hot path. Any filter on `status == credential` in rounds 10+ catches them.

## 6. Overlap between sets

By **id**: gate-1 and gate-2 `ids.txt` share 0 ids with 0.2.0's train, with r12 train, with val or with v3eval. Gate-3 shares 738 ids with train and 58 with val; gate-4 shares 741 with train and 57 with val; r9-hand shares 1,074 with train and 126 with val; none of the gates or r9-hand shares an id with v3eval. The vendor files share 12,414 ids with train and 1,293 with v3eval. [computed against `ids.txt`, `data/r9-hand/key.csv`, `data/vendor/ops.csv`]

By **provider+method+path** (distinct keys in common; the diagonal is each set's own distinct-key count in brackets):

| shared provider+method+path with: | train 0.2.0 | train r12 S0 | val-r12 | v3eval | holdout-r12 | generated variants | fresh exam 2026-11-03 | gate-1 | gate-2 | gate-3 | gate-4 | r9-hand | exam #3 | exam #4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train 0.2.0 (86,483) | - | 86483 | 0 | 11 | 0 | 7 | 0 | 11 | 10 | 735 | 741 | 1074 | 0 | 0 |
| train r12 S0 (94,104) | 86483 | - | 0 | 11 | 0 | 42 | 949 | 11 | 10 | 735 | 741 | 1074 | 1377 | 1050 |
| val-r12 (4,178) | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 | 58 | 57 | 126 | 0 | 0 |
| v3eval (3,721) | 11 | 11 | 0 | - | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| holdout-r12 (455) | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 455 |
| generated variants (1,080) | 7 | 42 | 0 | 0 | 0 | - | 14 | 4 | 1 | 6 | 2 | 0 | 0 | 21 |
| fresh exam 2026-11-03 (949) | 0 | 949 | 0 | 0 | 0 | 14 | - | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| gate-1 (600) | 11 | 11 | 0 | 1 | 0 | 4 | 0 | - | 1 | 0 | 0 | 0 | 0 | 0 |
| gate-2 (600) | 10 | 10 | 0 | 0 | 0 | 1 | 0 | 1 | - | 0 | 1 | 0 | 0 | 0 |
| gate-3 (797) | 735 | 735 | 58 | 0 | 0 | 6 | 0 | 0 | 0 | - | 1 | 1 | 0 | 0 |
| gate-4 (800) | 741 | 741 | 57 | 0 | 0 | 2 | 0 | 0 | 1 | 1 | - | 0 | 0 | 0 |
| r9-hand (1,200) | 1074 | 1074 | 126 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | - | 0 | 0 |
| exam #3 (1,377) | 0 | 1377 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 |
| exam #4 (1,505) | 0 | 1050 | 0 | 0 | 455 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - |

Reading it:
- gate-3, gate-4 and r9-hand sit almost wholly inside the training pool (735 of 797, 741 of 800, 1,074 of 1,200). They are labelled twice, once by the Jev recipe in training and once by hand; the hand labels are the more trustworthy copy and only 95 + 8 disagreements were written back as label fixes (the rest agreed).
- Exam #3 and the fresh exam sit wholly inside r11/r12 and r10/r11/r12 train respectively; exam #4 is split 1,050 train / 455 holdout with 0 shared keys between those halves.
- Gate-1/-2 share 10 to 11 provider+method+path keys with training even though they share 0 ids: same path and method under a different operationId, so the id exclusion held but the key does not strictly. The same applies to 11 keys shared between v3eval and train.
- Generated variants share 42 keys with r12 train and 21 with exam #4 (made-up vendors can collide on common paths like `/v1/...`); it is path coincidence, not leakage of the original rows.
- By vendor: the fresh exam, exam #3 and exam #4 have 0 vendor tokens in common with the original `ag-` training vendors (they are new vendors); gates and r9-hand share about 90% of their vendors with training (206 of 227, 194 of 218, 230 of 255, 228 of 248 and 220 of 245 vendors for gate-1, -2, -3, -4 and r9-hand).

## 7. BRIEF-v4 access rule: how many rows could it plausibly change?

**This is an estimate for scoping. It is not a relabel. No label was changed, and the patterns are keyword heuristics that will produce both false positives and misses.**

Rule being scoped: rows currently labelled **w (or r)** whose operation **grants or widens access, or is an ambiguous set/replace of access**: IAM, resource, bucket and key policies; role and permission assignments and bindings; ACLs; share and invite grants; deploy and SSH keys; `setIamPolicy`-style calls. Non-access "policies" (autoscaling, lifecycle, retention, routing and so on) are excluded. Rows already labelled x are excluded because the rule cannot change them (counts of access-term x rows are not part of the hit counts below).

Method. Text = operationId + summary + path (broad also uses the description), camelCase split, lower-cased, punctuation to spaces. Rows with label w or r only. Hits are counted on the label in each file (human truth for gates, exams, r9-hand and v3eval; training label elsewhere).

- **BROAD**: any "strong" access term (iam, acl, permission, role assignment/binding, binding, grant, share/sharing, invite, collaborator, deploy key, ssh key, authorized key, iam/resource/bucket/key/trust/queue/topic/repository/vault/registry/secret/security/authorization/access/network policy, principal, entitlement, privilege, allowlist/whitelist, access level/rights/list/rules, member role/permission, team access) or "weak" term (policy, role, member, membership, access, scope, trust, assume, visibility, owner, ownership). Not DELETE/HEAD/OPTIONS. GET only if its operationId or summary leads with a changing verb (this catches AWS `GET_AttachGroupPolicy`-style query twins). Read-verb-led operations (get, list, describe, search...) dropped unless a changing verb leads. Dropped when a non-access word (autoscaling, lifecycle, retention, routing, backup, cache, refund, escalation, sla, retry, rate limit, billing, tax, schedule, notification, expiry...) is present and no core access word (iam, acl, permission, grant, principal, share, invite, collaborator, deploy/ssh key, role) is present.
- **NARROW**: strong terms only (the list above minus the weak ones), POST/PUT/PATCH (or GET with a changing lead verb), a changing lead verb (attach, add, set, put, grant, assign, invite, share, bind, update, modify, change, create, enable, replace, authorize, allow, upsert, edit, register, link, transfer, promote, accept, apply, configure, reset, import, copy), or PUT/PATCH on a path whose last non-parameter segment is an access noun. Excluded: removing/narrowing verbs (remove, delete, revoke, detach, unassign, unshare, disable, deny, block, cancel, withdraw, disassociate, deregister, unlink, clear, expire), read-verb-led operations, and the same non-access word list.

Regexes used (Python `re`, applied to the normalised text):

```
STRONG=re.compile(r"\b(iam|acls?|access control|access polic\w+|permissions?|role assign\w*|assign\w* roles?|role bindings?|bind\w* roles?|bindings?|grants?|granted|granting|share[sd]?|sharing|invit\w+|collaborators?|deploy keys?|ssh keys?|authori[sz]ed keys?|(iam|resource|bucket|key|trust|queue|topic|repository|vault|registry|secret|security|sharing|authorization|access|network|ip|firewall) polic(?:y|ies)|principals?|entitlements?|privileges?|allow ?lists?|whitelist\w*|access (?:levels?|rights?|lists?|rules?|grants?)|member (?:roles?|permissions?|access)|team (?:members?|access|permissions?))\b")
WEAK=re.compile(r"\b(polic(?:y|ies)|roles?|members?|membership|access|scopes?|trust|assum\w*|visibility|owners?|ownership)\b")
NONACC=re.compile(r"\b(autoscal\w*|scaling|lifecycle|life cycle|retention|routing|routes?|backup|maintenance|cach\w*|refund|returns?|cancell?ation|escalation|sla|sampling|retry|rate limit\w*|throttl\w*|dunning|pricing|billing|tax|shipping|ttl|expir\w*|compliance|alert\w*|notification|schedul\w*)\b")
STRONGCORE=re.compile(r"\b(iam|acls?|permissions?|grants?|principals?|access control|shar\w+|invit\w+|collaborators?|deploy keys?|ssh keys?|roles?)\b")
MUT=re.compile(r"^(attach|add|set|put|grant|assign|invite|share|bind|update|modify|change|create|enable|replace|authorize|authorise|allow|upsert|patch|edit|register|link|transfer|promote|accept|apply|configure|reset|import|copy)\b")
READ=re.compile(r"^(get|list|describe|read|retrieve|fetch|check|validate|test|search|count|export|view|show|find|query|lookup|download|batch get|is|has)\b")
NARROWV=re.compile(r"^(remove|delete|revoke|detach|unassign|unshare|disable|deny|block|leave|decline|reject|cancel|withdraw|disassociate|deregister|unlink|clear|expire)\b")
NSTRONG=re.compile(r"\b(iam|acls?|access control|permissions?|role bindings?|role assign\w*|assign\w* roles?|bind\w* roles?|bindings?|grants?|share[sd]?|sharing|invit\w+|collaborators?|deploy keys?|ssh keys?|authori[sz]ed keys?|(iam|resource|bucket|key|trust|queue|topic|repository|vault|registry|secret|security|sharing|authorization|access|network) polic(?:y|ies)|principals?|entitlements?|privileges?|access (?:levels?|rights?|lists?|rules?|grants?)|member (?:roles?|permissions?|access)|team (?:permissions?|access))\b")
# text = normalised opId / summary / path (camelCase split, lower-case, punctuation to spaces)
def leads(r):
    o=re.sub(r'^(GET|POST|PUT|PATCH|DELETE)_','',r['opid'] or '')
    return [norm(o),norm(r['summary'])]
```

### Counts per set (rows currently w or r)

"Hits (rows)" counts rows in that file; "distinct ops" counts provider+method+path+operationId. Training sets nest (r10 contains the 0.2.0 set, and so on), so do not add rows across them. The last line counts each distinct operation once across everything (human-truth sets first, then v3eval, holdout, r12 train, val; generated variants and the unlabelled 2026-09-22 exam excluded).

| set | rows | w+r rows | BROAD hits (rows) | BROAD distinct ops | NARROW hits (rows) | NARROW distinct ops | NARROW of which w / r |
|---|---|---|---|---|---|---|---|
| train-r8soft(0.2.0) | 87,657 | 72,002 | 4,409 | 4,409 | 887 | 887 | 882 / 5 |
| train-r10 | 92,864 | 76,968 | 4,478 | 4,478 | 911 | 911 | 906 / 5 |
| train-r11 | 94,241 | 78,013 | 4,541 | 4,541 | 922 | 922 | 917 / 5 |
| train-r12-S0 | 95,291 | 78,930 | 4,670 | 4,670 | 936 | 936 | 931 / 5 |
| val-r12 | 4,180 | 3,580 | 132 | 132 | 24 | 24 | 23 / 1 |
| v3eval (truth) | 5,716 | 3,841 | 1,264 | 512 | 165 | 62 | 165 / 0 |
| holdout-r12 (goharbor+render) | 455 | 359 | 17 | 17 | 1 | 1 | 1 / 0 |
| generated variants (unique) | 1,199 | 825 | 24 | 24 | 11 | 11 | 11 / 0 |
| fresh exam 2026-11-03 (fx) | 949 | 734 | 65 | 65 | 23 | 23 | 23 / 0 |
| gate-1 (11-03) | 600 | 562 | 26 | 26 | 7 | 7 | 7 / 0 |
| gate-2 (11-04) | 600 | 557 | 31 | 31 | 3 | 3 | 3 / 0 |
| gate-3 (11-06) | 800 | 736 | 60 | 60 | 3 | 3 | 3 / 0 |
| gate-4 (11-07) | 800 | 746 | 42 | 42 | 1 | 1 | 1 / 0 |
| r9-hand (stricter of A/B) | 1,200 | 1,168 | 143 | 143 | 18 | 18 | 18 / 0 |
| exam #3 (ex3, labels from S0 train) | 1,377 | 1,047 | 65 | 65 | 11 | 11 | 11 / 0 |
| exam #4 (ex4, truth.csv pre-D136) | 1,505 | 1,182 | 139 | 139 | 16 | 16 | 16 / 0 |
| UNION (distinct ops, human truth first) | 104,855 | 86,705 | 5,394 | 5,394 | 1,033 | 1,033 | 1,027 / 6 |

Reading the numbers:
- **Round-12 train (95,291 rows): broad 4,670 (5.9% of its 78,930 w/r rows), narrow 936 (1.2%).** 0.2.0's set: 4,409 and 887. These are the rows a BRIEF-v4 access rule might touch, ordered by how likely they are to change: narrow first.
- Nearly all narrow hits are labelled **w** (1,027 of 1,033 distinct ops), matching the idea that the access rule would push w to x. The 6 r hits are false positives (five Azure Data Share `ShareSubscriptions_*` list calls and one Kubernetes admission-policy binding), so in practice the narrow estimate is a w to x estimate. The AWS query-protocol `GET_<Action>` twins (e.g. `GET_AddPermission`) that findings flags as a routing problem are caught as GET hits (20 in the narrow set, 133 in the broad set) and are labelled w in training (findings "Vendor labels, step A").
- **Concentration**: narrow, by vendor: microsoft 574, amazonaws 147, github 30, azure 27, googleapis 18, twilio 17, kubernetes 16, workos 11. Broad: microsoft 1,739, amazonaws 941, googleapis 429, azure 287, github 210, atlassian 134. Methods in the narrow set: POST 460, PATCH 377, PUT 175, GET 20, QUERY 1 (a training copy of a GET row with the method renamed).
- **Noise**: Microsoft Graph "Update the navigation property ..." PATCH rows are matched by their path (`roleAssignments`, `accessPackageAssignments`) whether or not they truly grant access; AWS rows like `SetPermission` and `PutResourcePolicy` are clear hits. Expect the narrow count to be too high by some tens of percent on Graph and the broad count to be too high by a large factor. The count of true BRIEF-v4 changes cannot be known until someone labels a sample under the new rule.
- On the **held-out and exam sets** the figures are small (holdout 1 narrow, exam #4 16, exam #3 11, fresh exam 23, gate-3 3, gate-4 1), so any BRIEF-v4 effect on a re-scored exam would come from a handful of rows, except v3eval where 62 distinct narrow operations (165 rows) carry the label w.
- Rows are not unique across sets in the training family, so "how many labels would change" for a v4 relabel of the whole corpus is closest to the union line: about 1,030 (narrow) to 5,400 (broad) of 86,705 w/r operations. The 123k mechanical corpus has 97,275 distinct op keys; operations dropped from training (duplicates, wobble rows, non-asked methods) and the 4,279-row 2026-09-22 exam (no labels here) are not scanned.

### 20 example rows, BROAD (seeded sample, at most 2 per vendor, from the union above)

| # | set | id | provider | method | path | operationId / summary | label now |
|---|---|---|---|---|---|---|---|
| 1 | train-r12-S0 | ag-009511 | amazonaws.com | POST | `/#X-Amz-Target=Lightsail_20161128.AttachDisk` | AttachDisk | w |
| 2 | fresh exam 2026-11-03 | fx-0086 | workos.com | PUT | `/authorization/groups/{group_id}/role_assignments` | AuthorizationGroupRoleAssignmentsController_replaceGroupRol... | w |
| 3 | train-r12-S0 | ag-011610 | amazonaws.com | POST | `/#Action=CreateDBSecurityGroup` | POST_CreateDBSecurityGroup | w |
| 4 | train-r12-S0 | ag-027768 | azure.com | PUT | `/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Mi...` | ExtendedDatabaseBlobAuditingPolicies_CreateOrUpdate | w |
| 5 | train-r12-S0 | ag-064224 | jira.local | POST | `/api/2/universal_avatar/type/{type}/owner/{owningObjectId}/avatar` |  | w |
| 6 | r9-hand | r9-0620 | netboxdemo.com | POST | `/dcim/rack-roles/` | dcim_rack-roles_create | w |
| 7 | train-r12-S0 | ag-095284 | microsoft.com | PATCH | `/privilegedAccess/{privilegedAccess-id}/resources/{governanceResource-id}/roleA...` | privilegedAccess.resources.UpdateRoleAssignmentRequests | w |
| 8 | train-r12-S0 | ag-076208 | microsoft.com | PATCH | `/policies/authenticationFlowsPolicy` | policies.UpdateAuthenticationFlowsPolicy | w |
| 9 | train-r12-S0 | ag-019256 | autotask.net | POST | `/V1.0/Contracts/{parentId}/ExclusionRoles` | ContractExclusionRolesChild_CreateEntity | w |
| 10 | val-r12 | ag-065567 | kubernetes.io | PATCH | `/apis/rbac.authorization.k8s.io/v1/clusterrolebindings/{name}` | patchRbacAuthorizationV1ClusterRoleBinding | w |
| 11 | train-r12-S0 | ag-019058 | autotask.net | POST | `/V1.0/ContractExclusionRoles/query` | ContractExclusionRoles_Query | r |
| 12 | train-r12-S0 | ag-116682 | trello.com | PUT | `/members/{idMember}/fullName` | updateMembersFullNameByIdMember | w |
| 13 | v3eval | ag-116532 | trello.com | PUT | `/boards/{idBoard}/myPrefs/showSidebarMembers` | updateBoardsMyPrefsShowSidebarMembersByIdBoard | w |
| 14 | v3eval | ag-040827 | github.com | PATCH | `/repositories/{repository_id}/environments/{environment_name}/variables/{name}` | actions/update-environment-variable | w |
| 15 | v3eval | ag-054832 | gitlab.com | POST | `/v3/groups/{id}/members` | postV3GroupsIdMembers | w |
| 16 | train-r12-S0 | ag-036910 | elmah.io | POST | `/v3/heartbeats/{logId}/{id}` | Heartbeats_Create | w |
| 17 | gate-3 | gate3-0286 | mist.com | POST | `/api/v1/sites/{site_id}/devices/{device_id}/vc` | createSiteVirtualChassis | w |
| 18 | train-r12-S0 | ag-059983 | googleapis.com | POST | `/v1beta1/{resource}:setIamPolicy` | privateca.projects.locations.reusableConfigs.setIamPolicy | w |
| 19 | train-r12-S0 | ag-057116 | googleapis.com | POST | `/projects/{project}/global/licenses/{resource}/setIamPolicy` | compute.licenses.setIamPolicy | w |
| 20 | train-r12-S0 | ag-025909 | azure.com | PUT | `/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Mi...` | FirewallPolicyRuleGroups_CreateOrUpdate | w |

### 20 example rows, NARROW (same method)

| # | set | id | provider | method | path | operationId / summary | label now |
|---|---|---|---|---|---|---|---|
| 1 | val-r12 | ag-065176 | kubernetes.io | POST | `/apis/admissionregistration.k8s.io/v1alpha1/validatingadmissionpolicybindings` | createAdmissionregistrationV1alpha1ValidatingAdmissionPolic... | r |
| 2 | val-r12 | ag-000145 | adafruit.com | POST | `/{username}/{type}/{type_id}/acl` | createPermission | w |
| 3 | train-r12-S0 | ag-076918 | microsoft.com | POST | `/servicePrincipals/{servicePrincipal-id}/appRoleAssignedTo` | servicePrincipals.CreateAppRoleAssignedTo | w |
| 4 | train-r12-S0 | ag-086852 | microsoft.com | POST | `/governanceRoleAssignmentRequests` | governanceRoleAssignmentRequests.governanceRoleAssignmentRe... | w |
| 5 | train-r12-S0 | ag-011445 | amazonaws.com | POST | `/accounts/{AwsAccountId}/data-sources/{DataSourceId}/permissions` | UpdateDataSourcePermissions | w |
| 6 | train-r12-S0 | ag-008201 | amazonaws.com | POST | `/#Action=PutUserPermissionsBoundary` | POST_PutUserPermissionsBoundary | w |
| 7 | train-r12-S0 | ag-040863 | github.com | PUT | `/teams/{team_id}/projects/{project_id}` | teams/add-or-update-project-permissions-legacy | w |
| 8 | train-r12-S0 | ag-032967 | clickmeter.com | PUT | `/account/guests/{guestId}/{type}/permissions/patch` | Account_PatchPermissions | w |
| 9 | train-r12-S0 | ag-037801 | fecru.local | PUT | `/rest-service-fecru/admin/permission-schemes/{name}/users` | addPermissionSchemeUser | w |
| 10 | train-r12-S0 | ag-057167 | googleapis.com | PATCH | `/projects/{project}/global/securityPolicies/{securityPolicy}` | compute.securityPolicies.patch | w |
| 11 | val-r12 | ag-065513 | kubernetes.io | PUT | `/apis/networking.k8s.io/v1/namespaces/{namespace}/networkpolicies/{name}/status` | replaceNetworkingV1NamespacedNetworkPolicyStatus | w |
| 12 | train-r12-S0 | ag-122254 | xtrf.eu | PUT | `/v2/jobs/{jobId}/files/sharedWorkFiles/share` | shareAsWorkFiles | w |
| 13 | train-r12-S0 | ag-064135 | jira.local | PUT | `/api/2/permissionscheme/{permissionSchemeId}/attribute/{key}` | setSchemeAttribute | w |
| 14 | fresh exam 2026-11-03 | fx-0117 | workos.com | POST | `/authorization/organizations/{organizationId}/roles/{slug}/permissions` | AuthorizationOrganizationRolePermissionsController_addPermi... | w |
| 15 | v3eval | ag-016731 | appcenter.ms | PATCH | `/v0.1/apps/{owner_name}/{app_name}/invitations/{user_email}` | appInvitations_updatePermissions | w |
| 16 | train-r12-S0 | ag-033820 | configcat.com | POST | `/v1/products/{productId}/permissions` | create-permission-group | w |
| 17 | exam #4 | ex4-0409 | immich.app | PUT | `/albums/{id}/users` | addUsersToAlbum | w |
| 18 | train-r12-S0 | ag-017924 | atlassian.com | PUT | `/rest/api/3/permissionscheme/{schemeId}` | updatePermissionScheme | w |
| 19 | v3eval | ag-017979 | atlassian.com | PUT | `/rest/api/3/project/{projectKeyOrId}/permissionscheme` | assignPermissionScheme | w |
| 20 | train-r12-S0 | ag-040867 | github.com | PUT | `/teams/{team_id}/repos/{owner}/{repo}` | teams/add-or-update-repo-permissions-legacy | w |

## 8. Notes and risks for the relabel plan

1. **Which rows can be relabelled cheaply.** Roughly 79% of training rows have no human label at all, only a Jev-derived soft target and a mechanical or Jev hard label. A BRIEF-v4 relabel of those rows is a "re-judge with a new rule" job, not a correction of a human label. The 4,596 hand/ruled rows are where a v4 disagreement is most meaningful.
2. **Burned sets cannot be re-tuned on, but their labels may be re-read.** If rwxmap re-labels the exams or gates under v4, the old scores stay valid for the old standard only. Gate-3, gate-4, the fresh exam, exam #3 and exam #4 rows are partly in training, so a v4 relabel of them changes training data and the held-out comparison at once. Keep the gate-1/gate-2 separation (0 shared ids) if a clean v4 check is wanted, and the goharbor + render holdout (455 rows) if the same model comparison must be repeatable.
3. **Truth for exam #3 and #4 lives in rwxmap**, not here; rwxlite keeps copies only as training rows (`ex3-`, `ex4-`) and in `data/exam4/truth.csv`. Any v4 relabel must be done on rwxmap's files and mirrored.
4. **Same brief, same model family.** All labelling in section 2 except Jev was done by Claude workers under one brief; their agreement figures (98 to 98.8%) show consistency, not independence.
5. **Duplicate snapshots.** v3eval repeats operations (5,716 rows, 3,723 distinct); the training sets are de-duplicated by provider+method+path+operationId. Count distinct operations when sizing v4 work.
6. **Noticed and not changed.** `data/round12/train.jsonl` and `final/S0/train.jsonl` have the same 95,291 ids but differ in the D136/user relabels (about 56 rows by `status`); findings says the S0 file's sha256 is not recorded in the repo. The narrow and broad patterns above are heuristics: false positives are visible in the example tables (for example Kubernetes admission and network policies, Azure Data Share list calls, Microsoft Graph `Update the navigation property` PATCH rows).

## 9. BRIEF-v4 w-row sizing (2026-11-05, read-only; no label changed)

Answers rwxmap's four sizing questions. Counts come from `data/` (gitignored), recomputed from the files; nothing was written except `data/v4/`. "Labelled w" means: the `label` field of the file (for training files that is the hard label used in training, i.e. the argmax of the one-hot or the letter the soft target is mixed with; for v3eval, gates, exams and r9-hand it is the human truth). v3eval's recipe label (1,644 w) is not counted; its truth (2,761 w) is.

**Merge key** = provider (lower-case) + method (QUERY folded into GET) + path + operationId + summary text (whitespace-collapsed, lower-case). Description is not in the key. Model-input-text merging would give about the same number (provider+method+path alone: 29,003).

### 9.1 Rows labelled w, before and after merging

Counted files (copies skipped: `round12/train.jsonl` pre-D136 copy, `round12/holdout.jsonl` pre-D136 copy, `round12/eval` which is the goharbor+render slice of exam #4, v3eval recipe labels, `r12/replay/*` and parquet copies, all checked identical to the originals). Training rounds nest (0.2.0 within r10 within r11 within S0 within S1 within S2), so the raw sum is inflated.

| set | rows | w rows | Jev soft | mechanical | hand/ruled | generated | unique w ops |
|---|---|---|---|---|---|---|---|
| train 0.2.0 (r8soft) | 87,657 | 24,161 | 22,267 | 1,894 | 0 | 0 | 24,161 |
| train r10 | 92,864 | 24,574 | 21,498 | 1,894 | 1,182 | 0 | 24,458 |
| train r11 | 94,241 | 25,011 | 21,498 | 1,894 | 1,619 | 0 | 24,895 |
| train r12 S0 | 95,291 | 25,449 | 21,477 | 1,891 | 2,081 | 0 | 25,333 |
| train r12 S1 | 97,613 | 26,669 | 21,477 | 1,891 | 2,081 | 1,220 | 25,948 |
| train r12 S2 | 101,058 | 28,494 | 21,477 | 1,891 | 2,081 | 3,045 | 25,948 |
| val r10/r11 (identical) | 4,180 | 1,153 | 1,086 | 67 | 0 | 0 | 1,153 |
| val r12 | 4,180 | 1,145 | 1,075 | 67 | 3 | 0 | 1,145 |
| v3eval (human truth) | 5,716 | 2,761 | 0 | 0 | 2,761 | 0 | 1,719 |
| holdout goharbor+render (final) | 455 | 115 | 0 | 0 | 115 | 0 | 115 |
| gate-1 / gate-2 | 600 / 600 | 194 / 204 | 0 | 0 | 398 | 0 | 194 / 204 |
| gate-3 / gate-4 | 800 / 800 | 352 / 347 | 0 | 0 | 699 | 0 | 352 / 347 |
| fresh exam 2026-11-03 | 949 | 328 | 0 | 0 | 328 | 0 | 328 |
| r9-hand | 1,200 | 966 | 0 | 0 | 966 | 0 | 966 |
| exam #3 (labels from S0) | 1,377 | 439 | 0 | 0 | 439 | 0 | 439 |
| exam #4 (truth.csv, pre-D136) | 1,505 | 467 | 0 | 0 | 467 | 0 | 467 |
| r10 hand check (A/B stricter) | 134 | 71 | 0 | 0 | 71 | 0 | 62 |
| generated variants (unique) | 1,199 | 615 | 0 | 0 | 0 | 615 | 615 |

- **Before merging:** 163,515 w rows summed over 20 counted files (592,419 rows). That sum counts the same row many times (every round contains the one before; exams, gates and r9-hand are also inside S0 as hand rows).
- **After merging (merge key above):** **29,396 unique operations have at least one w label.** Using one authoritative label per operation (S0 final, then holdout, val r12, hand/truth sets, exam #4, hand check, generated, older rounds last): **29,327 unique w operations** (of 101,806 unique operations in all counted sets). The 69 ever-w ops that are not w today: 66 were w only in 0.2.0/r10/r11/val and relabelled later (fixes, D136, rulings), 9 current-file conflicts (w versus x, mostly exam #4 truth.csv before D136 and a gate row against a generated variant); none w against r.
- **By label source of the 29,327 (best-trust occurrence):** Jev soft 21,673 (73.9%), hand/ruled 5,121 (17.5%), mechanical 1,920 (6.5%), generated variants 613 (2.1%). 29,327 minus 613 = 28,714 are real APIs.guru/vendor operations.
- **Jev soft detail in S0 (25,449 w rows):** POST lowered x to w by Jev 10,826; PUT/PATCH kept w by the mechanical floor 9,275; GET raised r to w 1,260; QUERY copies of raised GETs 116 (folded into their GET by the merge key); mechanical word rules 1,891; hand/ruled 2,081 (r9-hand 853, exam #3 439, exam #4 354, fresh exam 330, D136 55, gate label fixes 50).
- Details per set also in `data/v4/w-sizing-per-set.json`. Mechanical letters over all 123,339 APIs.guru operations in `data/m0/mechanical.jsonl.gz` carry 17,312 w, of which 3,304 never appear in any counted set (not labelled sets, so not counted).

### 9.2 Generated variants

- w rows that are generated variants: **615 unique** (`generated-unique.jsonl`: 570 surface, 45 contrast; 76 from the D136 batch, 539 from the main batch). In the training files they are repeated: **S1 has 1,220 w variant rows, S2 has 3,045** (S1/S2 duplicate each variant by weight; 615 distinct texts). Of the 1,199 unique variants, 615 w / 374 x / 210 r.
- They derive from **160 distinct source rows** (seeds), out of the 182 seeds in `data/round12/seeds.csv`. Seed rows come from burned sets: fresh exam 51, r9-hand 31, exam #4 26, gate-1 19, gate-2 13, gate-3 12, gate-4 8. Seed truth: 116 w, 29 r, 15 x (so some w variants are contrast variants of an r or x seed, or the other way). By seed category: 145 unsure_right, 14 raise_miss, 1 leak. 2 of the 615 w variants also match a gate row with a different label (counted in the 9 conflicts above), leaving 613 authoritative.

### 9.3 Labels older than BRIEF-v3

**None as w, and no v1 label is used as a training or evaluation label anywhere.** The only v1 material: (a) `labelled.csv` / calibration-2026-09-14 flags (`hand_set` 1,152, `calib_set` 549) on the mechanical dump, flags only, no v1 letters stored; 815 of the flagged ids sit in the training files but carry recipe labels. (b) `v3eval` (the combined-2026-09-21 slice): rwxmap kept the **v1 label where it was r** and relabelled every non-r row under v3, so **1,013 r rows in `data/round12/v3eval.jsonl` (also in `round10/` and `round11/`) are v1-origin r labels** (724 provider-corpus-2026-09-16, 289 exam-2026-09-17); 0 w and 0 x are v1. The buildset slice (3,726 rows) is fully v3. These 1,013 rows are r and stand under v4.

### 9.4 Pilot candidates and widened narrow-pattern count

Narrow pattern, widened (regexes in the worker scratch `v4pat.py`, keyword heuristics, expect false positives): the old access-grant pattern (section 7) plus five new x categories: API key/token create; toggles that widen access (public access, visibility, external or guest access, MFA or auth off, serial console); webhooks/subscriptions to an outside URL; creating a user who can log in; adding a member to a team/org/project/group. Applied to w-labelled unique operations only (29,327).

| category | unique w ops hit | by source Jev / hand / mech / generated |
|---|---|---|
| access grants/widening (section 7 narrow) | 1,037 | 829 / 145 / 52 / 11 |
| webhook/subscription to outside URL | 235 | 132 / 78 / 24 / 1 |
| add member to team/org/project/group | 170 | 101 / 48 / 21 / 0 |
| create login-capable user | 134 | 80 / 45 / 9 / 0 |
| API key/token create | 134 | 69 / 58 / 4 / 3 |
| widening toggle | 27 | 16 / 5 / 6 / 0 |
| **any category (deduplicated, 27 ops hit two)** | **1,710** | 1,217 / 369 / 109 / 15 |

The section 7 narrow count was 1,027 w (1,033 incl. 6 r) on a slightly different population; on today's 29,327 w ops it is 1,037. **Widened: 1,710 w ops (5.8% of w), of which 673 are new beyond the old pattern.** Unmerged, 9,476 w rows across all files hit a pattern.

Pilot export: **`data/v4/pilot-candidates.jsonl`**, 60 Microsoft Graph + 60 AWS w rows. Fields: id, provider, service_family, method, path, operationId, summary, description (89 of 120 have one), current_label (w), label_source, sets, in_exam_gate_holdout, in_v3eval_or_r9hand, matched_categories, same_op_ids. All 120 are rows in no exam, gate, holdout, v3eval or r9-hand set (checked by provider+method+path against all of those and the 2026-09-22 exam inputs); max 3 per service family (Graph: first path segment, 30 families; AWS: APIs.guru service, 41 families). Candidate pool before sampling: Graph 630 w hits (618 clean), AWS 225 (220 clean). Selection is seeded (20261105), round-robin over categories so the rarer new categories are represented: Graph 23 access / 24 member / 6 key / 3 webhook / 3 user / 1 toggle; AWS 14 access / 12 webhook / 11 user / 9 member / 9 toggle / 8 key (a row can match two).
