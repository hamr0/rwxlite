# PRD: round 16, 300k more new-vendor rows, continue from the r15 models

Status (2026-11-20): DRAFT. Nothing collected, labelled, trained or scored. Part of the rwxlite PRD (`docs/product/prd.md`). Builds on round 15 (`docs/product/prd-r15-github-data.md`, `docs/wiki/prereg-r15.md`, `docs/wiki/findings.md` section "Exam #7 result (2026-11-20): GO under D142"). Exam #7 is burned. Round 16 needs a new exam, #8, from rwxmap.

## 1. Goal

Raise accuracy on vendors the model has never seen, and close the leak cluster that round 15 opened (openziti access-policy PUT/PATCH). The model must stay 23 MB int8 and about 17-20 ms per operation. Nothing here is a release; only exam #8 can replace 0.4.0.

## 2. Why (evidence)

- **New vendors gave the gains.** Round 14 trained a bigger teacher on old data: no gain. Round 15 added about 200k rows from about 21,600 new vendors: the teacher lifted the disputed-row holdout from 74.0 to 81.8 exact, and the student passed exam #7 (exact 1432 vs 1431, too loose 66 vs 68, GO under D142).
- **The gain was small on the exam.** Mode a moved by +1 exact. More new vendors is the only lever that has worked.
- **Leaks opened at exam #7 (8, all x to w).** Five are openziti access policies (auth-policies, edge-router-policies PUT, service-edge-router-policies PUT, service-policies PUT). D137 says granting or widening access = x. Others: gitness admin PATCH, connectors, hf jobs expose.
- **The student is over-confident.** Its fitted temperature T is 1.38, against 0.99 for R13. A bigger T means the raw scores had to be flattened a lot. A likely cause is the 0.7 soft-target weight in the loss. The cut-off 0.90 is tuned for a model with T near 1, so this matters.

## 3. Data: how to reach about 300k rows

Facts (rwxlite master sheet, `data/r15/`, not committed):

- Master sheet: 802,196 ops. Round 15 used 200,000. 602,196 are unused.
- Of those 602,196, only 118,812 come from 3,741 vendors that round 15 did not use at all. The rest (about 483k) are more rows from vendors the model has already seen (the picker capped each vendor at a water level of 29).

Plan, in priority order:

1. **All unused new-vendor ops (up to 118,812 from 3,741 vendors).** Free: already collected and filtered. Subject to the exam #8 freeze (section 4), so the real number will be a little lower.
2. **New collection, about 150k rows from vendors in neither the corpus nor the master sheet.** Same sources as round 15 where they still have unseen vendors (GitHub code search, SwaggerHub, API catalogues, cloud catalogues), plus new ones if found. Same filters: template and petstore drop, at least 5 ops per spec, spec and op dedupe, corpus exclusion keys, copy check by rwxmap, 300-op cap per vendor (a lower cap is allowed to buy more vendors).
3. **Filler from the unused master rows of known vendors, only for the gap** (target 0 to about 30k). These add rows but not vendors, so they are the last resort.

Total target: about 300k rows, with at least 70% from vendors the model has never seen. If new collection falls short, ship fewer rows rather than pad with old-vendor rows (decision 2).

Licence: any public licence is fine for collection (user, 2026-11-18). Nothing is published or redistributed; data is never committed; Hugging Face publishing stays out of scope.

## 4. HARD RULE: exam #8 vendor freeze (rwxmap, 2026-11-20)

Never collect, train on or validate on these six vendors:

| vendor | identifiers to exclude |
|---|---|
| gitbook | api.gitbook.com |
| baserow | api.baserow.io |
| looker | looker.com, GitHub org looker-open-source, sdk-codegen Looker 4.0 and 3.1 specs |
| wekan | wekan/wekan, `public/api/wekan.yml` |
| shortcut | shortcut.com, developer.shortcut.com, api.app.shortcut.com, formerly clubhouse.io |
| bitrise | bitrise.io, api-docs.bitrise.io |

How the exclusion works:

- Match by raw token, by registrable domain and by brand alias, always on whole domain labels (so `shortcut` matches shortcut.com, not "keyboard-shortcuts").
- Drop copies wherever they sit: GitHub mirrors and forks, SwaggerHub, APIs.guru, other catalogues, SDK repos that vendor the spec.
- This applies to everything: new collection, the 118,812 unused master ops, the filler, the old 102,668 and r15's 199,600 rows, and val.
- Known leak path: round 15's raw collection held looker (github 81, swaggerhub 78) and wekan (github 14, swaggerhub 3) copies. Round 15's final labels hold none. Check the master sheet again for all six anyway.
- Process: after collecting and BEFORE any labelling or training, send rwxmap the provider/spec list and the ops CSV paths. rwxmap returns a drop list. Drop it before labelling. Collection output is quarantined until then, as in round 15.
- The list is a floor, not the full exam. rwxmap may add vendors; every addition is applied the same way before training. The prereg records the final list and the sha256 of the drop list.

## 5. Labelling (same as round 15)

- Cascade: mechanical rules + R13 (rwxmap mode a) + bge opinions on all rows. Where all three agree, that letter stands. The rest goes to Sonnet. Rows Sonnet marks unsure go to Opus. The leftover takes the strictest letter at a low weight. The ruling text goes FIRST in the labeller prompt (Sonnet under-applied D141 until it did).
- Teacher opinion for pass 1 is the r15 bge teacher (today's checkpoint).
- Standard: BRIEF-v4 with D136, D137 and the D141 addendum. rwxmap's pipeline is the single label truth; we never relabel on our side.
- One merge rule shared with rwxmap: D141 tighten-only. Ask the user only about gaps in the rulings.
- Check the labels: a Sonnet audit of about 300 agreed rows; a fresh blind-reviewed holdout of about 400 disputed rows (never trained on). The r15 holdout rows stay out of training too.
- Jev: not at runtime. Offline only, for disputed training rows, under the $50 cap. It lost to bge and Sonnet in the round 15 pilot, so it is not planned.
- Openziti target: add a dedicated pass on access-policy PUT/PATCH/POST rows (policies that grant or widen access, D137 = x). Count them in the new data first; if there are few, search for more vendors with such resources (policy, role, permission, grant, ACL, access rule).

## 6. Training plan

Both models start from today's r15 checkpoints, not the base checkpoints. Order: bge-base teacher first, then the MiniLM student.

1. **Teacher.** Start from the r15 bge-base teacher. Train on the old rows (the R13 102,668 and the r15 199,600) plus the new rows, at a lower learning rate than round 15.
2. **Student.** Start from the r15 MiniLM student (the 0.4.0 model). Distil from the new teacher on the same mix, lower learning rate.
3. **Row weights.** As round 15: contested rows (Sonnet, Opus-agreed, D141-changed with a sure or likely answer) count x3; rows resting on an unsure answer count x1.
4. **Old rows stay in the mix.** Without them, training on new vendors alone would forget the old ones (the risk behind exam #7's old-vendor val). The exact ratio is decision 4.
5. **Fix confidence BEFORE training.** Measure why T is 1.38 (loss weight, learning rate, label sharpness), pick the fix (decision 1 and 3), and write it into the prereg. No tuning on the exam.
6. **Val.** Val and the holdouts are used for the stop and go/no-go checks only. Val overlap with training is removed as in round 15 (exact match on method + path + operationId + summary).
7. **Lean.** Regenerate all training texts with rwxmap's frozen mechanical lean, as in round 15, and byte-compare against the exam's lean.

Student val guard: a written floor against 0.4.0 on val and the D141 holdout, so a clearly broken student cannot use up exam #8. The teacher has its own go/no-go against the r15 teacher. If the teacher fails, the student distils from the r15 teacher's targets instead (prebuilt).

Time: the teacher needs rows labelled (about 1.5 h per 100k) and then trained. With about 600k rows (102k + 200k + 300k) the training time is NOT yet known; round 15 took about 20 h for 302k rows (at most about 25 h). Estimate for round 16: about 30-40 h for the teacher alone, to be measured on a short run and written into the prereg. If it exceeds the budget, use decision 4's smaller old-row sample.

## 7. Gate

- **Judge: exam #8 from rwxmap** (fresh vendors; its list overlaps the freeze in section 4). Scored once, then burned. A scored exam never tunes anything again; it may be training data only afterwards.
- **Rule: D142.** Candidate exact >= base exact, AND candidate too loose <= base too loose + floor(1% of the exam's rows). Judged on the fp32 exact model (`manifest-exact.json`), through rwxmap's real CLI, mode a, `secondPass` at cut-off 0.90, at batch 1. int8 is information only and never decides.
- **Base = 0.4.0 at its shipped T 1.3832, never refit.** The candidate uses its own val-fit T (or the confidence fix of decision 1).
- **Leak check (information, not gate):** the openziti-style access policy rows must not leak more than at exam #7; report counts.
- **Preregistration:** write the prereg before training (draft `docs/wiki/prereg-r16.md`). It includes the predict and score code, committed before the truth is revealed, and the prediction sha256s committed before truth. Use the real gate (rwxmap CLI secondPass), never a_none or a replica.
- **Truth for exam #8:** rwxmap's process (two blind labellers on BRIEF-v4 + D141, rwxmap's user rules disagreements, no Jev).

### Dev set: fixed unseen-vendor set (2026-11-20)

- **Rule: never trained on; used only to compare small round 16 test runs; exam #8 is the gate.** It is not the ship gate and is never scored for a decision. It is excluded from all round 16 training and from val.
- **What it is:** 182 never-used vendors, 4,039 ops (cap 30 ops per vendor, seeded random 30; median 22), picked whole-vendor by `r16/pick_dev.py`, seed 16 (best of 300 seeded draws on method mix). Files (gitignored): `data/r16/dev/dev-vendors.csv` (for rwxmap's copy check), `dev-ops.csv.gz`, `pick-report.json` (counts, mixes, drop lists, sha256).
- **Never used** means: vendor_key not among the r15 pick's vendors, and not an exact key in R13's seen list or `exclusion-keys.txt`. This reproduces the 118,812 ops from 3,741 vendors. The script also drops (and counts) pool vendors that share an R13 token, a spec hash with the r15 pick or a flagged spec, or an exam #7 alias.
- **Exam #8 freeze applied** (whole label / domain / repo on every vendor field). No pool vendor matched the six names; one look-alike (`title:shortcuter`) was dropped by a substring audit.
- **Finding:** the 118,812 pool ops are not like r15's rows. They were left out because they are mostly non-English (zh 47k, ru 12k, other languages 25k), duplicates (13k), no text (10k), RPC style (19k, Alibaba) or junk domain (3k). Under r15's own switches (English, text, not duplicate, not junk, not RPC) the pool has 0 rows. The dev set therefore allows Latin-script non-English text (lang `other`: French, German, Spanish, Portuguese, Korean and similar) and still excludes dup, junk and RPC rows. Its sources are SwaggerHub and GitHub (plus one konfig vendor); cloud ops are all zh or RPC, so none are in. Method and source mix match this eligible pool, not the full 118,812.
- Access-policy style ops (word match on path, operationId, summary) are rare: 25 ops from 10 vendors in the dev set (0.6%), 93 in the eligible pool. Not forced.

## 8. Server and resource rules

Home server `ahassan@192.168.178.180`, sandbox `~/rwxlite-train` only; touch nothing else. nice 19, ionice -c3, 3 of 4 threads, one job at a time, memwatch kills under 2 GB free. nohup, nothing left running; workers use their own scratch dir and never broad-pkill.

## 9. Non-goals

- Shipping bge-base (the shipped model stays MiniLM).
- New loss penalties; the `--row_weight` and `--x_weight` behaviour stays as round 15 unless the prereg changes it on purpose.
- Jev at runtime.
- Publishing or committing any collected spec, or Hugging Face publishing.
- Relabelling on our side against rwxmap's pipeline.

## 10. Risks

- **Not enough new vendors.** Only 118,812 ops from 3,741 new vendors are in hand; the rest must be collected. Mitigation: smaller 300k target, lower per-vendor cap.
- **Freeze leaks.** Mirror copies of the six vendors hide in catalogues. Mitigation: whole-label matching, rwxmap drop list before labelling.
- **Forgetting.** Training only on new vendors hurts old ones. Mitigation: old rows in the mix, lower learning rate, val guard.
- **Confidence drift.** T moves again. Mitigation: fix before training; base T never refit.
- **Same-family labels.** Labels and exam truth are Claude models reading the same brief; "correct" means agreement with that rulebook.
- **Burned exam #7.** It may be training data only; it can not be a gate.

## 11. Open decisions for the user

Each question has a plain explanation and a recommended answer.

1. **How to fix the model's over-confidence before training (T 1.38).**
   What it means: the model's confidence numbers are used to decide when to trust it. Round 15's student says "I am 99% sure" too often, so we have to flatten the numbers, and that flattening (T) is large. We can fix it at the root or just keep flattening later.
   Options: (a) lower the soft-target weight and lower the learning rate; (b) add a small sharpening or label smoothing step during training; (c) change nothing and refit T after training.
   Recommended: (a), after a short measurement on val showing which cause it is, written into the prereg. Do not refit the baseline's T.

2. **Where the 300k rows come from (new vendors vs unused master rows).**
   What it means: 118,812 rows from 3,741 never-used vendors are ready. The other 483k unused master rows come from vendors the model already knows. New vendors are what helped before.
   Options: (a) all 118k new-vendor rows plus about 180k newly collected rows, with the old-vendor filler as a last resort; (b) all 118k plus 180k from old-vendor master rows, with no new collection; (c) fewer rows, only what new vendors supply.
   Recommended: (a), with at least 70% of rows from never-seen vendors; if collection falls short, go with fewer rows (c) rather than pad.

3. **Soft-target weight (alpha).**
   What it means: each training row has the teacher's soft probabilities (how unsure it is) and the hard letter. Round 15 used 0.7 soft + 0.3 hard. More soft teaches the teacher's shape; more hard makes the student surer. The over-confidence may come from this.
   Options: 0.7/0.3 as before; 0.5/0.5; 0.3/0.7.
   Recommended: 0.5 soft + 0.5 hard for the student, decided together with decision 1 on a val check; the teacher uses hard labels as in r15.

4. **Old rows versus new rows in the mix (and the learning rate).**
   What it means: training on 300k new rows only would make the model forget old vendors; including everything makes training slower (about 600k rows).
   Options: (a) everything: 102k R13 + 200k r15 + 300k new; (b) all new rows plus a random half of the old rows; (c) new rows only.
   Recommended: (a) if the measured time fits about 40 h per model, else (b). Lower learning rate (half of r15's) in either case. (c) is not recommended.

5. **Continue vs start over.** Already decided: continue from today's r15 checkpoints for both models. Not open; recorded so it is not asked again.

6. **Extra pass on access-policy rows (openziti target).**
   What it means: five openziti PUT/PATCH rows were wrongly labelled "write" instead of "dangerous" (D137: granting or widening access = x) after round 15. We could add a dedicated labelling pass and up-weight such rows, but this risks over-training on one vendor.
   Options: (a) dedicated Sonnet/Opus pass on policy/role/permission/grant rows in the new data, same weight rules as r15; (b) (a) plus extra weight x2 on those rows; (c) nothing special.
   Recommended: (a). No extra weight: exam #7 is burned, so we could not tell a real gain from overfitting to openziti.

7. **Per-vendor cap.**
   What it means: a cap on rows per vendor keeps one big vendor from dominating. Round 15 used 300 in collection and a picker level of 29.
   Options: 300 / 100 / 30 per vendor in the final mix.
   Recommended: 300 in collection and a picker level of about 30 for the final mix, so more vendors fit under 300k.

8. **Teacher time budget.**
   What it means: the home server has no graphics card; training the teacher on about 600k rows may take 30-40 h.
   Options: (a) accept up to about 40 h; (b) cut the mix to fit about 25 h (like r15).
   Recommended: (a) if a measured short run supports it, since the user accepted 25 h last time and the gains came from data.

## Collection (GitHub, unfetched r15 candidates) - 2026-11-21

Code: `r16/search.py`, `licences.py`, `fetch.py`, `extract.py` (copies of r15 with paths changed; fetch/extract now take the repos r15 did NOT fetch: not permissive-kept, not fork, not missing), `drive.sh`, `filter_github.py` (r15 rules, exam #8 freeze, new-vendor rule, cap; imports r15 `master.py` and `filter.py` unchanged), `verify_github.py` (audit of the output file). Data (gitignored): `data/r16/ops-r16-github.{csv.gz,parquet}`, `vendors-r16-github.csv`, `collect-report-github.json`, `data/r16/raw/`.

**Why a new search.** r15's `data/r15/raw` (candidates, repos, specs) was deleted on 2026-11-19, so the list of unfetched files no longer existed. The code search was re-run (about 7 h under GitHub's code-search throttle). It was stopped by hand: `openapi.yaml` and `swagger.yaml` are complete, `openapi.json` reached 11,269 bytes, and `swagger.json`, `openapi.yml`, `swagger.yml` were not run. The search is resumable (`r16/search.py`) if more is wanted. Result: 141,366 candidate files in 88,283 repos (r15: 139,871 / 87,363). 23,008 repos are permissive-licence (r15 fetched those); 65,273 repos / 99,089 files were fetched here (99,088 ok, 1 not found). Licence column: GitHub spdx id, `none` when GitHub detects no licence (58,263 of 88,283 repos). No forks appeared (code search skips them). Licence is not a filter.

Stage counts (ops / specs / vendor_keys):

| stage | ops | specs | vendors |
|---|---|---|---|
| extracted (96,928 specs parsed ok; 1,882 invalid) | 1,773,972 | 96,046 | 53,830 |
| template / petstore drop | 1,751,454 | 94,018 | 53,535 |
| spec has at least 5 ops | 1,691,190 | 70,317 | 42,955 |
| exact spec dedupe | 1,425,245 | 59,194 | 42,797 |
| op dedupe (vendor, method, path) | 1,246,604 | 54,185 | 42,797 |
| has text | 1,226,788 | 53,721 | 42,453 |
| junk-domain flag | 1,218,197 | 53,298 | 42,365 |
| language is en (1,007,149 en; 114,991 other; 61,034 zh; 35,023 ru) | 1,007,149 | 46,646 | 37,157 |
| exam #8 freeze | 1,006,577 | 46,627 | 37,145 |
| spec sha in r15 master | 999,430 | 46,244 | 36,900 |
| vendor_key in r15 master | 901,889 | 40,635 | 35,016 |
| registrable domain in master (vendor, servers, contact, logo) | 888,399 | 40,071 | 34,894 |
| R13 tokens | 852,869 | 38,400 | 34,388 |
| r15 exclusion keys | 833,165 | 37,220 | 33,925 |
| exam #7 list | 832,199 | 37,199 | 33,907 |
| rwxmap-flagged specs | 832,178 | 37,197 | 33,906 |
| r16 dev pick | 832,178 | 37,197 | 33,906 |
| near-duplicate of a master spec | 823,262 | 36,309 | 33,152 |
| same method+path+operationId+summary as a master row | 823,262 | 36,309 | 33,152 |
| near-duplicate specs inside this set (primary kept) | 815,128 | 35,812 | 32,725 |
| cap 300 per vendor (seed 16) | **807,949** | 35,810 | **32,725** |

(RPC flag removed nothing: GitHub specs carry no rpc tag. The row-level order is as in the table; the full per-rule counts are in the report.)

Exam #8 freeze: 46 raw specs hit (gitbook 27, shortcut 15, looker 1, plus 3 substring-only look-alikes); 19 specs / 572 ops were still alive at the freeze and were dropped (427 ops own hits, 145 ops one near-duplicate of a dropped spec, `truvera` copy of the docknetwork gitbook spec). Baserow, wekan and bitrise had no hits. Every dropped spec (repo, path, rule) is listed in `collect-report-github.json` under `exam8`. The output file was re-checked with the same matcher: 0 hits, 0 vendors/specs/domains in the r15 master, 0 non-English rows.

Diversity: 32,725 vendors, ops per vendor median 14, mean 24.7, p90 54, 49 vendors at the cap; top 10 vendors 0.4% of ops, top 100 3.5%. Method mix GET 46.6%, POST 33.9%, DELETE 8.3%, PUT 6.3%, PATCH 4.8%. Caution: 21,978 vendors are title-keyed and 5,329 owner-keyed (small hobby/student projects, 652k ops); only 5,418 are real registrable domains (155k ops). Largest same-title families (backend, go, {{title}}, service) are different projects sharing a name (path-set overlap about 0); no family looks like one template copied many times (the `{{title}}` placeholder family is 21 specs / 188 ops). Licences by ops: none 81%, NOASSERTION 10%, AGPL-3.0 5%, GPL-3.0 3%.

## Pick (round 16) - 2026-11-21

> Superseded 2026-11-21 by the v2 pick/dev (section "Cleaning" below): v1 files kept, but 39,477 pick ops and 453 dev ops were copies and were replaced. The numbers in this section are v1.

Code: `r16/pick_round16.py` (dev, pick, replay; seed 16, deterministic, asserts), `r16/rate_prep.py`, `r16/rate_bge.sh` (reuses `r15/label_bge.py`), `r16/rate_report.py`. Data (gitignored): `data/r16/dev-en/`, `data/r16/pick/` (`new-300k.csv.gz`, `old-replay-ids.csv`, `pick-report.json`, `bge-rating.parquet`, `rating-report.md`). Input: `ops-r16-github` (csv.gz sha 8aa27faa...). rwxmap exam #8 drop list sha 75d5fc70...; all 260 specs dropped, 4,680 ops (matches), 803,269 ops left. Text lean = rwxmap 1c25be1 (as r15).

- **Dev set (English, replaces nothing: `data/r16/dev/` kept):** 200 whole vendors, 4,475 ops (cap 30, min 12 pool ops per vendor; best of 1,000 seeded draws on method mix, L1 0.03 vs pool); 140 domain vendors (3,207 ops, 71.7%), 50 title, 10 owner. Never trained on.
- **New pick: 300,000 ops, 32,295 vendors.** (a) all domain-vendor ops: 149,571 ops from 5,249 vendors (300 cap held). (b) hobby fill: 150,429 ops from all 27,046 title/owner vendors, water level 5 (+1 for a seeded subset), so at most 6 per vendor; a 20 cap would give 360,864 ops, more than needed, so spreading over every vendor beat 20 per vendor over fewer. Method mix GET 48.1, POST 34.6, DELETE 7.7, PUT 5.8, PATCH 3.8. Top 10 vendors 1.0%.
- **Old replay: 60,000 rows** (r13 20,383, r15 39,617): 40,349 hard rows (r15 tiers sonnet/opus_agree/strict 24,632; access words 15,709; agree3 weight-3 rows 595; overlaps merged) plus 19,651 seeded random fill (r13 10,620, r15 9,031). 402 of the 755 confident disagreements are in it, flagged; labels unchanged.
- Asserts: no dev vendor/op in the pick, no drop-list spec, exam #8 matcher 0 hits, caps hold.

Rating (r15 bge teacher, 304,475 rows, 2.97 h on the server): p_top >= 0.9 for 93.3% of the new pick at T=1 and 89.1% at T 1.36; unsure (<0.7 at T 1.36) 11,264 (3.8%). bge differs from mech on 41,680 (13.9%), 89% bge-looser, and 36,589 of them are mech rule floor-post (POST read as x, bge says w: 30,326 x->w); DELETE 0. Access rows: 9,583 in the new pick, 8.4% disagree. Proposed Opus list = unsure + disagreements: 47,362 rows (15.8%). Details: `data/r16/pick/rating-report.md`. The floor-post leak is the thing the labelling cascade must judge; no label was set.

## Master list - 2026-11-21

> Rebuilt 2026-11-21 with the v2 pick/dev, language on every row and the new duplicate statuses (section "Cleaning" below). The numbers in this section are the first build (sha `97f88665...`); the finding at the end is explained and fixed there.

One table of every op collected for rounds 13, 15 and 16: `data/master/master-all.{parquet,csv.gz}` (2,696,791 rows, one per `op_id`, exactly one `status`), `master-summary.md`, `master-report.json`. Built by `r16/build_master_all.py` (deterministic; the same parquet sha256 `97f88665...` on two runs). It replays `r16/filter_github.py` stage by stage over `data/r16/raw` so each dropped r16 op carries the stage that removed it (every stage count is asserted equal to `collect-report-github.json`).

- **Status precedence.** r13: `trained_r13`, `r13_val` (the 5,716 v3eval rows are inside train: boolean `r13_v3eval`). r15: `trained_r15` (199,543) > `r15_holdout` (400) > `dropped_val_overlap` (57) > `r16_dev_old_unused` (the earlier non-English dev, 4,039) > `exam8_drop_rwxmap` > `exam8_drop_name` (108) > `rwxmap_flagged_r15` (4,963, rows removed from the master) > `dropped_*` (duplicate, no_text, junk, rpc, non_english) > `unused_clean` / `unused_other`. r16: first removing stage (`dropped_template`, `min5`, `duplicate`, `no_text`, `junk`, `non_english`, `exam8_drop_name`, `known_vendor` with the rule in `status_detail`, `near_dup`, `cap`); kept ops: `exam8_drop_rwxmap` (4,680) > `r16_dev` (4,475) > `r16_pick_new` (300,000) > `unused_*`. `unused_other` = passes the hard rules but has a soft flag (huge_spec, odd_path, lorem, placeholder_text, autogen_opid_only, test_endpoint).
- **Flags.** `r16_old_replay` (60,000, all on trained_r13/trained_r15 rows), `confident_disagreement` (755), `opus_candidate` (r16 pick rows, bge unsure or bge != mech, 47,362 = rating-summary), `key_in_r15_master`, `soft_flag`, `vendor_class`, `vendor_used`.
- **Reconciliation.** r15 802,196 master + 4,963 rwxmap-dropped + 8,812 master-dedupe removals = 815,971 (the four r15 input files; the 23 exact vs 8,789 cross-source split is count-only). r16 1,773,972 raw, 807,949 kept = 4,680 + 4,475 + 300,000 + 498,794 unused. No training row is dev or exam #8 dropped (asserted). r15 raw-collection stages (before the input files) are count-only: r15 raw data was deleted 2026-11-19. Lang is blank for r13 and for r16 ops dropped before the text stage.
- **Headline.** Clean English rows from never-used vendors: **0**. Every vendor with clean unused rows already has a row used (r15 and r16 drew from every eligible vendor). Unused clean English rows: 890,928 from 36,675 vendors (844,354 without op-text copies of r15 rows). By vendor class: `r16_pick_only` 486,232 ops / 21,901 vendors (the nearest thing to new vendors for round 17), `trained_r13_r15` 391,957 / 14,404, `reserved_dev_exam` 12,739 / 370 (off limits).
- **Finding.** The cross-source duplicate rule in `r16/filter_github.py` dropped 0 ops, yet 83,088 ops that reached it match an r15 master row on method+path+operationId+summary (32,918 are in the r16 pick). The statuses record what was done; the flag `key_in_r15_master` marks them.

## Cleaning (round 16 v2: duplicate-op root cause, v2 pick and dev, rating, language) - 2026-11-21

Code: `r16/opkey.py` (the one definition of the op key), `r16/filter_github.py` (rule fixed), `r16/pick_round16_v2.py`, `r16/rate_prep_v2.py`, `r16/rate_bge.sh` (`RATE_DIR`), `r16/rate_report.py` (refactored, v1 report reproduced byte for byte apart from one thousands separator), `r16/rate_report_v2.py`, `r16/build_master_all.py`. Data (gitignored, v1 files kept): `data/r16/pick/new-300k-v2.csv.gz`, `data/r16/dev-en/dev-ops-v2.csv.gz`, `dev-vendors-v2.csv`, `pick-report-v2.json`, `dropped-v2.csv.gz` (every v1 dev/pick op removed, with reason), `added-v2.csv`, `bge-rating-v2.parquet`, `rating-report-v2.md`, `rating-summary-v2.json`.

### 1. Root cause: why the cross-source duplicate rule dropped 0 ops

The rule (`filter_github.py`, "same method+path+operationId+summary as any master row") built its key as `method + "\0" + path + "\0" + operationId + "\0" + summary` and compared `pandas.util.hash_pandas_object` values (master side and r16 side hashed as two separate Series). The collection run used the system python (pandas 3.0.0). In pandas 3.0.0 that hash is wrong for strings that contain a NUL byte: different keys collide, and the same key gets a different hash depending on which other keys are in the Series. So the two hash sets could not overlap.

Proof on the real columns (the committed code, run up to that line, tables dumped to `data/r16/scratch/v2/`): master 802,196 keys gave 9 distinct hash values, the r16 table at that stage (823,262 ops) gave 9 distinct values, 0 in common, and the original expression returned `xd.sum() = 0`. The same comparison with python tuples (method upper, path, operationId, summary) matches **83,088** of the 823,262 ops, and the fixed rule (`opkey.k1`) on the same dumped tables drops 83,088. Dtypes were not the cause (both sides `str`; the r15 master has no nulls in operationId or summary).

Tiny reproduction (`r16/repro_hash_bug.py`):

```
h = lambda l: pd.util.hash_pandas_object(pd.Series(l), index=False).tolist()
h(["GET\0/a\0x", "GET\0/b\0y"])              # pandas 3.0.0: [1576164044250810843, 1576164044250810843]  (two keys, one hash)
h(["GET\0/a\0x", "GET\0/b\0y"])[1]            # 1576164044250810843
h(["GET\0/aaaaaa\0x", "GET\0/b\0y"])[1]       # 17362308838366959468  (same key, other Series, other hash)
```

pandas 3.1.1 (the scratch venv) returns two different, stable hashes (9056232381540259794 for the key in both Series); a key without NUL separators is stable in both versions. So the fault is the NUL separator plus the pandas version, not the data. **Fix at the source:** the key is a python tuple, `r16/opkey.py` (`k1`), used by the filter, the v2 pick and the master build; a set of tuples depends on no hash function. The filter was not re-run (its output feeds v1; the fixed rule is applied on top in v2 and in the master statuses, and the replay in `build_master_all.py` finds the same 83,088 with `opkey.k1`).

### 2. The rule, exact key and normalised key

Exact key K1 = (METHOD upper, path, operationId, summary) is the drop rule. Normalised key K2 = (METHOD upper, path with `{..}` to `{}`, lower case, trailing slash dropped, operationId) is only reported. Known rows = R13 train (102,668), val (4,180), v3eval (5,716, inside train), r15 master (802,196, includes the 199,543 trained r15 rows and the 400 holdout rows); the exam sets of r15 are inside these.

Independent matches (an op can match several sources); v1 pick 300,000 ops and v1 dev 4,475 ops:

| source | pick K1 | pick K2 | dev K1 | dev K2 |
|---|---|---|---|---|
| R13 train | 1,427 | 21,996 | 12 | 337 |
| R13 val | 134 | 3,690 | 0 | 54 |
| R13 v3eval | 35 | 1,255 | 0 | 30 |
| r15 trained | 23,811 | 78,945 | 327 | 1,184 |
| r15 holdout | 31 | 540 | 0 | 4 |
| r15 master (all) | 32,918 | 99,492 | 451 | 1,508 |
| any source (union) | **33,390** | 100,185 | **451** | 1,510 |

K2 finds 66,795 more pick ops (25,043 with a non-empty operationId) and 1,059 more dev ops (370 with operationId) than K1. 20 random K2-only examples are in `pick-report-v2.json` (`norm_only_examples`): same method, path and operationId, but the summaries differ in meaning or language ("Login" vs "ユーザーログイン", "Get dish by ID" vs "Получение данных о блюде", "List observations" vs "List benchmark observations", "Update a class" vs "Update kelas (Super Admin)"). They are generic names (`GET /members listMembers`) from unrelated APIs, not copies. **Decision: K2-only matches are not dropped.**

### 3. Drops from v1, per reason (exact key)

| set | reason | ops |
|---|---|---|
| dev | exact key = a known row (R13 train 12, r15 trained 315, other r15 master 124) | 451 |
| dev | duplicate of another dev op (lowest op_id kept) | 2 |
| pick | exact key = a known row (R13 train 1,427, R13 val 118, r15 holdout 3, r15 trained 22,939, other r15 master 8,903; first source wins) | 33,390 |
| pick | duplicate inside the pick (lowest op_id kept) | 4,984 |
| pick | same key as a dev op (dev wins) | 273 |
| pick | op of a vendor that moved to dev, taken there | 329 |
| pick | other ops of a vendor that moved to dev | 501 |
| | pick total replaced | 39,477 |

Over the whole pool (807,949 kept ops) 83,088 ops match a r15 master row on K1; in the master list the ones not in dev/pick/exam #8 drop list now have status `dropped_op_key_known` (81,654; R13 rows included) and key duplicates of the pick/dev `dropped_op_key_dup` (5,259).

### 4. Refill

- **Dev (v2: 4,475 ops, 214 vendors, v1 was 4,475 / 200).** 4,022 kept; 121 refilled from the same 200 vendors (cap 30; their other clean ops ran out); the other 332 from 14 new vendors (v1 rules: at least 12 clean pool ops, cap 30, about 70% domain vendors, seeded): tmphost.io, boardgameplatform.com, telekom.com, openpanel.com, eluvia.com, mita.finance, negativeone.xyz, safarcollab.com, ai-schedule-manager.com, photomarket.com, heroiclabs.com, overal-x.org, tolabco.com, title:easydocker. Every vendor was already in the pick, so these 14 left the pick (329 of their ops were already rated). By kind: domain 3,332 ops, title 929, owner 214. Method mix GET 47.2, POST 32.4, DELETE 7.9, PUT 6.7, PATCH 5.1 (v1: 47.1 / 33.0 / 7.8 / 6.6 / 4.8).
- **Pick (v2: 300,000 ops, 32,070 vendors, v1 32,295).** 260,523 kept from v1, 39,477 added. Domain vendors first: 0 added (all their clean ops were already in the pick, none left). Hobby fill: 39,477 ops (title 29,213, owner 10,264) from 21,297 vendors by water-filling on the current counts (spread thin, hobby cap 20, seeded +1), level 7 (v1 level 5-6). Candidates: clean unused rows only (kept in the pool, not on the exam #8 drop list, no soft flag, not in v1 dev/pick, not a dev vendor, K1 not known, K1 unique), 418,219 hobby rows available. Domain ops are now 132,772 (44.3%, v1 149,571 = 49.9%), hobby 167,228. Method mix GET 47.7, POST 34.3, DELETE 7.7, PUT 6.0, PATCH 4.2 (v1 48.1 / 34.6 / 7.7 / 5.8 / 3.8). Top 10 vendors 1.0%.
- Asserts (in the script): no pick or dev op shares its exact key with any R13 train/val/v3eval, r15 master (trained, holdout) row; no exact-key duplicate inside the pick or dev or between them; no dev vendor in the pick; no exam #8 drop-list spec; exam #8 matcher 0 hits on every added row; every added op is `unused_clean`; caps hold (domain 300, hobby 20, dev 30). The same exact-key asserts are in `build_master_all.py`.
- Soft-flagged rows already in the v1 pick (6,339) are kept (they are not copies); refills use clean rows only.

### 5. Re-rating (added rows only)

39,601 added ops (dev 124, pick 39,477; ops that moved between dev and pick keep their v1 rating) were scored by the r15 bge teacher (same checkpoint sha d53deafc..., same lean of rwxmap 1c25be1 via `r15/label_mech.mjs`, batch 64, T 1.36) on the server in `~/rwxlite-train/r16-rate-v2/` (nice 19, ionice idle, 3 threads, one job, memwatch 2 GB; free memory 12.9 GB at start, lowest seen 12.0 GB; 20.9 min; nothing left running). Merged with the 264,874 kept v1 ratings into `bge-rating-v2.parquet` (304,475 rows). New pick: p_top >= 0.9 for 92.6% at T=1, 88.0% at T 1.36; unsure (<0.7 at T 1.36) 12,305 (4.1%); bge differs from mech on 43,292 (14.4%). **Proposed Opus list = unsure + disagreements: 49,496 rows (16.5%)**, was 47,362 (15.8%). Details: `data/r16/pick/rating-report-v2.md`. No label was set.

### 6. Language on every row and the non-English pool

`lang` is now filled for every row of the master list (2,696,791); `non_english` is a boolean (lang zh, ru or other); `lang_computed_here` marks the 647,991 rows tagged in this build (r13 rows, r16 ops dropped before the text stage, r15 input-only rows) with `r15/master.py lang_signal` on summary+description, else summary, else operationId, else `unknown` (no letters; 13,467 rows). Nothing was deleted: non-English rows keep their status (for example `dropped_non_english`). Non-English rows: **409,478** (zh 134,777, other 214,952, ru 59,749; the 4,039 earlier non-English dev rows are among `other`). Otherwise clean (status `dropped_non_english`: has text, not a duplicate, not junk, not RPC, HTTP method): **319,149 ops from 12,705 vendors** (r15 108,101, r16 211,048; zh 116,546, ru 49,023, other 153,580). The full table lang x source round x status is in `data/master/master-summary.md`.

### 7. Master list (rebuilt with v2)

`data/master/master-all.{parquet,csv.gz}` (2,696,791 rows, parquet sha256 `b93936e1...`, identical on two runs), `master-summary.md`, `master-report.json`. New statuses `dropped_op_key_known` (81,654) and `dropped_op_key_dup` (5,259); `r16_dev` 4,475, `r16_pick_new` 300,000 (v2 sets); `opus_candidate` flag follows the v2 rating (49,496). Unused clean English rows 804,055 from 33,265 vendors (r16 pick-only 399,490 / 18,480 vendors, trained r13/r15 391,957 / 14,404, reserved dev/exam 12,580 / 363, never used 28 / 18: vendors whose every pick row was a copy). Not done: r15 unused rows were not key-checked against trained rows (the r15 filter already ran its own dedupe), and the filter was not re-run.
