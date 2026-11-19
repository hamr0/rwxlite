# PRD: round 15, a large new-vendor transfer set for distillation

Status: D141 relabel applied to the labels (section 19, 2026-11-19); training waits for rwxmap's export-v4-d141. Before that: collection done, labelling and blind review done, Jev pilot and Sonnet pilot done (2026-11-19); labelling cascade agreed (section 5, 17); next is the preregistered pass rule and mix (section 16). Part of the rwxlite PRD (`docs/product/prd.md`). Builds on round 14 (`docs/product/prd-bge-teacher.md`, its `--teacher` code). Background and facts: `docs/wiki/findings.md`, section "2026-11-18: Round 15 background".

## 1. Goal

Close the unseen-vendor gap. The shipped model scores about 97% on val but about 90% on unseen vendors (rwxmap exam #6, mode a). The plan is to show the small model many more vendors, labelled by the bge-base teacher. It must stay 23 MB int8 and about 17-20 ms per operation.

## 2. Why (evidence)

- **Round 14 result.** bge-base beats R13 in mode b at every confidence on val, but is worse in mode a. A student distilled on the SAME 102,668 rows came out equal to R13. All three clauses of the student rule failed.
- **Research.** Distillation gains come mainly from a large unlabelled transfer set, and they grow with its size.
  - arXiv 2402.14922, "Practical Insights into Knowledge Distillation for Pre-Trained Models".
  - arXiv 1910.01769, "Distilling BERT into Simple Neural Networks with Unlabeled Transfer Data".
  - arXiv 2004.05686, XtremeDistil.
  - Round 14 gave the student no new rows. R13 also already learned from Jev's soft targets, so swapping teachers on the same rows was not expected to change much.
- **Our corpus is narrow.** It has 123,339 operations from 673 providers (`data/m0/mechanical.jsonl.gz`). About 76,000 of them (62%) come from five companies: microsoft.com 33,869, github.com 14,663, amazonaws.com 13,198, azure.com 8,083, googleapis.com 5,992.

## 3. Sources (measured 2026-11-18)

- GitHub code search: about 127,600 files `filename:openapi.yaml` containing "openapi: 3", and about 37,800 files `filename:swagger.yaml` containing `swagger: "2.0"`. JSON and other file names are not counted.
- API Evangelist org: 45,192 public repos (API profiles, many with OpenAPI).
- ToolBench (RapidAPI, about 3,400 services, about 16,000 endpoints) on Hugging Face, for example Maurus/ToolBench.
- No public dataset with r/w/x-style labels was found on Hugging Face or elsewhere (searched 2026-11-18).
- The 2024 GitHub OpenAPI research dataset (Di Lauro, ICWE 2024, about 600k specs): no public download found.

## 4. Rules for the transfer set

- Permissive-licence repos only: MIT, Apache-2.0, BSD-2/3, CC0, ISC, Unlicense. Check the GitHub repo licence field. Training use only, never republished.
- Remove petstore and template copies, tiny specs (fewer than 5 operations), and exact and near duplicates (spec hash, and host+method+path).
- Exclude every provider already in our corpus, every exam #1-#6 vendor, and every exam #7 vendor. The exam #7 vendors are chosen with rwxmap and frozen BEFORE collection starts. Collection does not start until that list is committed. (Same idea as the main PRD: every APIs.guru snapshot of a sampled op key is excluded.)
- Exam #7 exclusion is by vendor name, every brand alias and the vendor's spec repo, plus any fork, mirror or SDK repo that vendors the spec. Matching the provider field alone is not enough, because a GitHub-wide crawl is the likeliest way an exam vendor slips in.
- After collection and before any teacher labelling or training, the full round-15 provider list (with repo URLs) goes to rwxmap. They confirm that no exam #7 vendor got in.
- Every exam #7 shortlist candidate stays out of the transfer set, even if it does not make the final exam. This starts with ringcentral and baserow. rwxmap releases dropped candidates only after exam #7 is frozen.
- Cap each vendor at 300 operations.
- Target: start at 100,000 operations from at least 3,000 new vendors. Grow to 300,000 only if the first round helps.

## 5. Labelling: a cascade (agreed by the user, 2026-11-19)

Cheap and broad passes come first; each more trusted pass only sees the remaining delta. The labelling contract:

- **Pass 1: three cheap opinions on all 200k rows (done).** rwxmap's mechanical rules (these also give the lean every request needs), R13 through rwxmap mode a, and the bge-base teacher (r14-bge checkpoint). The 87.5% where all three agree take that letter, with bge's soft probabilities as targets. A Sonnet audit of 300 agreed rows, stratified by source and letter, checks that agreement means correct. If Sonnet disagrees on more than about 3%, those patterns join the delta.
- **Pass 2: Sonnet on the 25,033 disputed rows.** Its sure and likely answers are final. Sonnet runs as Claude Code subagents in the session, so there is no API bill.
- **Pass 3: Opus labels independently the rows Sonnet marked unsure** (expected about 5,000, i.e. 21% in the pilot). Where Opus and Sonnet agree, that letter is final.
- **Pass 4: the residue** takes the strictest opinion (BRIEF's unsure goes to x) and gets a low training weight. Rows hitting one of the five BRIEF-v4 ambiguities (findings.md, 2026-11-19) go on a short list for rwxmap's user to rule on.
- **Across rounds**, bge is retrained on the cleaned labels and becomes the next round's pass 1, so the delta shrinks each round.
- **Holdout.** The 400 reviewed rows never enter training. Every pass is checked against them.
- **Jev is not in the cascade.** It scored below bge on the pilot (section 15.1).

Label standard is BRIEF-v4 plus D136/D137 (rwxmap's pipeline is the label truth). Same model plus same brief is one opinion, not independent labellers; this is why pass 3 uses a different model (Opus) and why residue rows get low weight. Using rwxmap on training rows burns nothing; only scored exams are burned.

**Cascade result (2026-11-19; `r15/label_final.py`, `r15/label_holdout_score.py`; data not committed).** Final labels: 199,600 rows (200,000 minus the 400 holdout rows). Tiers: agree3 174,967; sonnet 21,038 (sure 13,547 and likely 7,491, less the unsure ones); opus_agree 2,152; strict 1,443 (weight 0.3). Letters overall r 54.7% / w 15.5% / x 29.8% (agreed-only: 59.1 / 9.4 / 31.5). Weight total 198,589.9. Audit of 300 agreed rows: Sonnet same 274, agreed-looser 6 (2.0%, under the 3% limit, so the agreed rows stand), agreed-stricter 20. Holdout (weighted to 25,033 disputed rows, exact / too loose / too tight): cascade 92.0 / 3.8 / 4.2, Sonnet 87.2 / 9.8 / 3.1, bge 74.8 / 17.5 / 7.8; risky pocket cascade 90.9 / 4.7 / 4.4, Sonnet 82.6 / 15.2 / 2.2, bge 62.4 / 33.1 / 4.4. Pass 4 short list: 12,056 flags on 11,496 ops in `pass4-ambiguity-list.csv` (flag only, no label changed). Details: findings.md, 2026-11-19, "Cascade run".

## 6. Training and rule

- Student: all-MiniLM-L6-v2, R13 recipe. Data: our 102,668 labelled rows plus the transfer rows, with the teacher's probabilities as soft targets. The exact mix is fixed in this round's prereg before training.
- The student's pass rule is written and committed before training. It is on val against R13-b1, and at least as strict as round 14's section 9 rule.
- Exam #7 (fresh, shared with rwxmap) is the only ship judge.

## 7. Server and resource rules

Same as `prd-bge-teacher.md` section 5: nice 19, ionice idle, 3 of 4 threads, one job at a time, memwatch at 2 GB free, nohup, nothing left running.

Estimated teacher labelling time: about 1.5 h per 100,000 rows. Round 14 phase 1 measured about 96 min for 102,668 rows.

## 8. Decisions

Agreed by the user on 2026-11-18 (the plan as written above):

- Licence policy: permissive only (MIT, Apache-2.0, BSD-2/3, CC0, ISC, Unlicense), as in section 4.
- Start size: 100,000 operations. Grow to 300,000 only if round 15 helps.

Still pending:

- Exam #7 vendor list. To be agreed with rwxmap. A request was sent to rwxmap on 2026-11-18. Collection does not start until the list is committed (section 4).

## 9. Non-goals

- Shipping bge-base.
- Layer-wise (weight) distillation, for now.
- New loss penalties (research and round 13 show mixed results).
- Jev at runtime. (Changed 2026-11-19: Jev may label disputed training rows offline, once, under the $50 cap; see section 15.)
- Republishing any collected spec.

## 10. Status

Agreed 2026-11-18. Licence policy and start size are decided (section 8). rwxmap agreed on 2026-11-18 to freeze the exam #7 list; their user picks the vendors. There is no shortlist yet (ringcentral and baserow are earlier candidates and need re-checking). Collection is on hold until rwxmap sends the committed exam #7 list.

2026-11-18: raw collection started under quarantine (user decision): download and table building only; no labelling, scoring or training until the exam #7 list is committed and applied.

## 11. Extra sources, licence decision and copy check (2026-11-18)

Extra sources, collected under the same quarantine (download and tables only; each has its own script and output files, all under `data/r15/`, never committed):

- Catalogues (`r15/catalogues.py`, `ops-r15-catalogues.*`): Microsoft PowerPlatformConnectors (MIT), wso2/api-specs (Apache-2.0), konfig-sdks/openapi-examples, Activepieces community pieces (MIT).
- SwaggerHub public registry (`r15/swaggerhub.py`, `ops-r15-swaggerhub.*`): public, published API definitions; latest published version per owner/api; junk titles skipped before fetching; polite rate (about 1.5 requests/s, backoff, Retry-After honoured).
- Cloud catalogues (`r15/cloud.py`, `ops-r15-cloud.*`): Alibaba Cloud (aliyun/aliyun-openapi-meta, Apache-2.0) and Huawei Cloud (huaweicloud-sdk-python-v3, Apache-2.0). Each product or service is its own vendor (`aliyun:<product>`, `huaweicloud:<service>`), so the 300-op cap applies per product. RPC-style Alibaba APIs use the action name as the path; the `api_style` column says rpc or roa.

Same filters as the GitHub pipeline: template/petstore drop, at least 5 ops per spec, spec and op dedupe, corpus exclusion keys, exam #7 exclusion (whole-label matching), 300 ops per vendor. Every output has a `source` column; the `licence` column is filled from the spec's info.license, or `none-stated`.

**Licence decision (user, 2026-11-18).** For round 15 the user dropped the "permissive licences only" rule of section 4 for public API definitions. Reasoning: these are public API descriptions anyone can download, we do not reuse code, and we only label the operations and train on them. Nothing is published or redistributed: data is never committed, and Hugging Face publishing stays out of scope. The `licence` column is kept anyway.

**rwxmap copy check (agreed).** rwxmap reads our `ops-r15*.csv.gz` files in place and flags any spec that shares at least 5 METHOD+path pairs with an exam or reserve spec, where those pairs are also at least 25% of the spec's ops. Normalisation: method uppercased, `{param}` collapsed, path lowercased, trailing slash dropped. Specs at 3 or more pairs, or 15% or more, are reported as near misses. Borderline cases go to rwxmap's user. We drop the flagged `spec_sha256` ids before labelling.

## 12. Final counts per source (2026-11-19)

Operations after each source's own filters, before the master:

| source | ops |
|---|---|
| GitHub | 455k |
| SwaggerHub | 288k |
| catalogues (PowerPlatform, wso2, konfig, Activepieces) | 33k |
| cloud (Alibaba, Huawei) | 40k |

Raw downloads (`data/r15/raw`, 4.7 GB) were deleted on the user's request on 2026-11-19. The per-source sheets (`ops-r15*.csv.gz`, `providers-r15*.csv`) are kept, so the master can be rebuilt from them.

## 13. rwxmap copy check and master sheet

**Copy check result.** rwxmap checked our sheets at its commit 1c25be1. It flagged 318 specs; one more, a GitbookIO spec, was added by hand. That is 319 specs and 4,963 ops dropped. Near misses were kept. No exam copy got through.

**Master sheet** (`r15/master.py`): 802,196 ops from 25,345 vendors. Cross-source dedupe removed 8,789 rows. There are 563 spec groups. Flags are tag, don't drop: a flagged row stays in the sheet with its flag.

**Picker** (`r15/pick.py`): 200,000 ops from 21,604 vendors. Water level 29 (the per-vendor cap that fills the 200,000). Title share 24.8%.

## 14. Labelling and blind review (2026-11-19)

**Labelling** (commit f664afd, `r15/label_*`). Each of the 200,000 picked rows got three opinions: the bge-base teacher (temperature 0.99424), R13 through rwxmap mode a, and rwxmap's mechanical rules. All three agree on 174,967 rows (87.48%). The rest, 25,033 rows in 18 disagreement types, are the disputed rows. Counts per type: `data/r15/labels/opinions-report.json`.

**Blind review.** Claude reviewed 400 disputed rows against BRIEF-v4 without seeing the opinions (about 33 rows per big type; letter, confidence, reason). Results, weighted to the 25,033 by disagreement type (exact / too loose / too tight, %):

| opinion | exact | too loose | too tight |
|---|---|---|---|
| bge | 74.8 | 17.5 | 7.8 |
| R13 mode a | 57.6 | 7.5 | 34.9 |
| mechanical | 20.1 | 10.8 | 69.1 |

On the 175 rows the reviewer was "sure" of, exact: bge 145, R13 113, mechanical 23.

bge's weak spot: when bge is looser than BOTH others (about 11.3k rows: bge_w_r13_x_mech_x 8,239 and bge_r_r13_x_mech_x 3,011), it is too loose about a third of the time.

These 400 rows never enter training. They are the teacher-quality holdout.

## 15. Plan after the review (user decisions, 2026-11-19)

The user approved Jev as a one-time OFFLINE labeller for training data, on disputed rows only. It is never used at runtime. Spend cap for all Jev use: $50.

1. Pilot first, on the 400 reviewed rows: does Jev beat bge? (Result: section 15.1.)
2. If Jev wins: Jev labels the 25,033 disputed rows.
3. Retrain bge-base as the permanent teacher on our 102,668 checked rows plus the 200k round 15 rows. Labels: the three-way consensus where all agree, Jev where they disputed. Server estimate under the gentle rules: about 15-20 h.
4. Distil the MiniLM student from the new bge.
5. The pass rule is preregistered before training. Exam #7 judges.

**Fallback if Jev does not beat bge:** drop the about 11.3k rows where bge is loosest (bge looser than both others) and use bge soft targets for the rest.

### 15.1 Jev pilot result

Jev was run as rwxmap's own mode-c pipeline (commit 1c25be1: mechanical, then the per-tier question for rows in a Jev pile, with rwxmap's thresholds), on the 400 reviewed rows only. 286 rows sit in a pile and got Jev calls; 114 sit in no pile and keep the mechanical letter, as in rwxmap. Scripts: `r15/jev_pilot_prep.py`, `r15/jev_pilot.mjs`, `r15/jev_pilot_score.py`; outputs `data/r15/labels/jev-pilot-400.csv`, `jev-pilot-report.json` (not committed).

Weighted (exact / too loose / too tight, %), then raw exact counts out of the 175 sure rows:

| opinion | weighted exact | too loose | too tight | sure-only exact (of 175) |
|---|---|---|---|---|
| bge | 74.8 | 17.5 | 7.8 | 145 |
| R13 | 57.6 | 7.5 | 34.9 | 113 |
| mechanical | 20.1 | 10.8 | 69.1 | 23 |
| Jev (mode c) | 65.0 | 10.7 | 24.3 | 86 |

Jev does not beat bge on exact (65.0 vs 74.8 weighted; 86 vs 145 sure-only). On the 286 rows where Jev was actually asked, raw exact is bge 195, Jev 168, R13 144, mechanical 73.

On bge's weak spot (the two big types, 66 sampled rows standing for 11,250): bge 62.4 / 33.1 / 4.4, Jev 60.2 / 4.4 / 35.4. Jev is about as exact but swaps too loose for too tight. Small sample; one run (Jev is not repeatable).

Cost: 374 calls, 802,541 input tokens, $0.034 computed from token counts at rwxmap's recorded price (42e-9 per input token); not a vendor invoice. Projection for 25,033 rows: about $3.5 (weighted by type, about 35,000 calls), about $2.1 flat. Both far under the $50 cap.

Verdict: Jev did not win and is dropped from the cascade. The user chose the cascade of section 5 instead of the fallback (section 17).

## 16. Status (2026-11-19)

Collection, copy check, master, picker, labelling, blind review, Jev pilot and Sonnet pilot are done. Raw downloads are deleted; sheets are kept. The user agreed the labelling cascade (section 5). Next: run the Sonnet audit of 300 agreed rows, pass 2 and pass 3; preregister the pass rule and the mix; retrain bge as teacher (102,668 + about 200k rows); distil MiniLM; exam #7 judges. Nothing trained yet.

## 17. Sonnet pilot (2026-11-19)

A Sonnet pilot labelled the same 400 blind-reviewed disputed rows, blind, using BRIEF-v4 + D136/D137 (`data/r15/labels/sonnet-pilot-400.csv`, not committed). Weighted to the 25,033 disputed rows, against the blind review (exact / too loose / too tight, %):

| opinion | exact | too loose | too tight |
|---|---|---|---|
| Sonnet | 87.2 | 9.8 | 3.1 |
| bge | 74.8 | 17.5 | 7.8 |
| Jev | 65.0 | 10.7 | 24.3 |
| R13 mode a | 57.6 | 7.5 | 34.9 |
| mechanical | 20.1 | 10.8 | 69.1 |

In the risky pocket where bge is looser than both R13 and mechanical (11,250 rows): Sonnet 82.6 / 15.2 / 2.2, bge 62.4 / 33.1 / 4.4, Jev 60.2 / 4.4 / 35.4.

On rows the reviewer marked sure, Sonnet's exact rate is 99.6%. Where both were sure, they agreed on 157 of 157. In the pocket, Sonnet sure was right on 33 of 34. Its misses sit mostly on rows Sonnet itself marked unsure, especially "verify code/email" (one of the five BRIEF-v4 ambiguities). So Sonnet's confidence is usable as the pass 2 / pass 3 split.

**Caveat.** The reviewer is also a Claude model with the same brief, so the Sonnet scores are optimistic (same model family plus same brief is not independent). Pass 3 uses Opus and the residue rule for this reason.

## 18. Status (2026-11-19, cascade done)

Passes 1 to 3 and the pass 4 flagging are done; final labels are built (section 5, cascade result). Next: preregister the pass rule and the soft/hard mix, retrain bge as teacher, distil MiniLM, exam #7 judges, and send the pass 4 short list to rwxmap's user. Nothing trained yet.

## 19. D141 relabel (2026-11-19)

The labels follow BRIEF-v4 plus the D141 addendum (rwxmap 54355e1, `BRIEF-v4-addendum-D141.md`); where they conflict the addendum wins. Rulings: (a) login, sign-in or refresh returning any token = x; (b) verifying an email or code, pure checks included = x; (c) group update without members, roles or permissions in the text = w, adding members stays x; (d) changing a callback, webhook or endpoint setting, uploading a signing key, registering a push token = x; (e) removing members via POST/PUT/PATCH = x, narrowing a role without removing anyone stays w.

**How.** `d141/pattern-net.json` (shared with rwxmap) found 9,740 candidates among the 199,600 rows. Sonnet relabelled all blind. Rule: sure/likely takes the new letter; unsure takes the stricter of old and new. `r15/label_d141.py` writes `final-labels-r15-d141.parquet` and `.csv.gz` (new columns d141_candidate, d141_families, d141_changed, label_pre_d141) plus `d141-report.json`. The old `final-labels-r15.*` files are untouched.

**Counts.** 1,274 rows changed (mostly r to x: 885; w to x 191; x to w 161; x to r 26; r to w 9; w to r 2). Letters before r 109,142 / w 30,917 / x 59,541; after r 108,276 / w 30,894 / x 60,430. Changed rows whose new letter came from an unsure Sonnet answer (171) get weight 0.3; weight total 198,589.9 to 198,470.2. Tiers unchanged.

**Holdout.** Opus re-checked the 400 holdout reviews under D141: 30 changed. `r15/label_holdout_score_d141.py` re-scores; the cascade falls from 92.0 / 3.8 / 4.2 to 89.4 / 6.1 / 4.5 (exact / loose / tight), since the opinions predate D141. 33 holdout rows match the net.

**Next.** rwxmap will re-export the other 102,668 rows as export-v4-d141 using the same net (pending their user's go-ahead). Training waits for that export. Data stays under `data/r15/` and is not committed.
