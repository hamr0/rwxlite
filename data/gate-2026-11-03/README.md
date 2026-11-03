# data/gate-2026-11-03 — fresh BRIEF-v3 label-gate sample (blind)

## What this is

600 operations drawn from the 123k APIs.guru ops (`data/m0/mechanical.jsonl.gz`) to measure the 95% label gate
(PRD, Step 4) on data nobody has labelled or trained on. Two blind labellers (Claude workers) label `blind.csv`
under `BRIEF-v3.md` (this directory; byte-identical copy of rwxmap `data/relabel-2026-09-22/BRIEF-v3.md`,
rwxmap commit 4143b6d26d69e9177f15f4913c3613a0a361724c, the last commit touching it). The user rules disputes.

**Used ONCE.** This sample is the label gate and nothing else. It is never used for tuning, threshold sweeps, model
selection or any repeated scoring. After the gate it is burned. Nothing is scored on the exam until the gate passes.

## Files

- `blind.csv`: id, provider, method, path, operationId, summary, description. Shuffled order. No mechanical letter, no Jev p, no class hint of any kind.
- `ids.txt`: 741 `ag-` row ids = the 600 sampled rows PLUS every APIs.guru snapshot sharing their
  op key (provider+method+path+operationId). This is the training exclusion list: none of these may enter training or tuning.
- `BRIEF-v3.md`: the only label standard.
- Truth comes from the labellers later. There is no key here.

## Draw

- Seed: 20261103 (mulberry32; sort op keys, one Fisher-Yates shuffle, take in order subject to quotas). `node m0/gate-sample.mjs` reproduces these files byte for byte.
- Unit = op key (provider+method+path+operationId); one row per op key (first snapshot's text).
- Quotas (GET/POST/PUT/PATCH): GET 325, POST 175, PUT 50, PATCH 50. Proportional to availability, with at least 100 GET and 100 PUT+PATCH.
- Vendor cap: 30 rows per vendor (5% of 600); vendor = first dotted token of provider.

## Exclusions (op keys)

Total op keys: 97275 (from 123339 rows). Excluded, in order: exam vendors (cloudflare, pagerduty, sentry) 0;
the other 7 locked vendors (auth0, hubspot, zendesk, dropbox, shopify, linear, miro) 0; exam_opkey_overlap 19;
already in a v3 truth set (combined-2026-09-21, relabel-buildset-2026-09-23) 3723; DELETE 8935; HEAD/OPTIONS/TRACE/other 201.
Eligible: 84397.

## Counts

| method | n |
|---|---|
| GET | 325 |
| POST | 175 |
| PATCH | 50 |
| PUT | 50 |

| vendor | n |
|---|---|
| amazonaws | 30 |
| autotask | 30 |
| azure | 30 |
| googleapis | 30 |
| microsoft | 30 |
| twilio | 12 |
| github | 9 |
| loket | 9 |
| netbox | 9 |
| geodesystems | 7 |
| sportsdata | 7 |
| atlassian | 6 |
| kubernetes | 6 |
| plaid | 6 |
| vtex | 6 |

(227 vendors in all.)

## Status: USED (scored once, 2026-11-03)

Labelled by two blind workers, A and B (`labels-A.csv`, `labels-B.csv`). Labellers used high/medium/low confidence
(the brief says high/low only); labels are unaffected. A and B agreed on 588 of 600 (98%). The user ruled the 12
disputes (`rulings.csv`). `truth.csv` = agreed label, else the ruling (600 rows, no "?").
`m0/gate-score.mjs` scored the gate once; result in `score.json` (verdict FAIL, 90.8% exact at the PRD cuts).
This sample is now BURNED: no tuning, sweeps, model selection or re-scoring on it.
