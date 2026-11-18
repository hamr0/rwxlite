# PRD: round 15, a large new-vendor transfer set for distillation

Status: agreed 2026-11-18, collection on hold. Part of the rwxlite PRD (`docs/product/prd.md`). Builds on round 14 (`docs/product/prd-bge-teacher.md`, its `--teacher` code). Background and facts: `docs/wiki/findings.md`, section "2026-11-18: Round 15 background".

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

Same model plus same brief is one opinion, not independent labellers. No Jev or other paid calls. Using rwxmap on training rows burns nothing; only scored exams are burned.

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
- Jev labelling.
- Republishing any collected spec.

## 10. Status

Agreed 2026-11-18. Licence policy and start size are decided (section 8). rwxmap agreed on 2026-11-18 to freeze the exam #7 list; their user picks the vendors. There is no shortlist yet (ringcentral and baserow are earlier candidates and need re-checking). Collection is on hold until rwxmap sends the committed exam #7 list.
