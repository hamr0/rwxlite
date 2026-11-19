# PRD: round 15, a large new-vendor transfer set for distillation

Status: collection done, labelling and blind review done, Jev pilot done (2026-11-19); next step needs the user's go (section 16). Part of the rwxlite PRD (`docs/product/prd.md`). Builds on round 14 (`docs/product/prd-bge-teacher.md`, its `--teacher` code). Background and facts: `docs/wiki/findings.md`, section "2026-11-18: Round 15 background".

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

## 5. Labelling: three opinions per row

1. rwxmap's mechanical rules. These also give the lean that every request needs.
2. R13 through rwxmap mode a.
3. The bge-base teacher's probabilities (r14-bge checkpoint).

Rows where all three agree go in as they are.

Disagreements are the risky rows. Claude checks a sample of them against the current label standard (BRIEF-v4 / D137 wider x; rwxmap's pipeline is the label truth). This measures how often the teacher is wrong on new vendors, before training.

Same model plus same brief is one opinion, not independent labellers. No Jev or other paid calls in this first labelling pass (changed on 2026-11-19: see section 15). Using rwxmap on training rows burns nothing; only scored exams are burned.

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

Verdict: Jev did not win, so the fallback in section 15 is the working plan unless the user decides otherwise (section 16).

## 16. Status (2026-11-19)

Collection, copy check, master, picker, labelling, blind review and the Jev pilot are done. Raw downloads are deleted; sheets are kept. Pending: the user's choice between the fallback (bge soft targets, drop the about 11.3k loosest rows) and labelling the disputed rows with Jev anyway; then the preregistered pass rule and the bge retrain. Nothing trained yet.
