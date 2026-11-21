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
