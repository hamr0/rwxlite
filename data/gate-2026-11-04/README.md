# data/gate-2026-11-04 — fresh BRIEF-v3 label-gate sample (blind)

## What this is

600 operations drawn from the 123k APIs.guru ops (`data/m0/mechanical.jsonl.gz`) to measure the 95% label gate
(PRD, Step 4) on data nobody has labelled or trained on. Two blind labellers (Claude workers) label `blind.csv`
under `BRIEF-v3.md` (this directory; byte-identical copy of rwxmap `data/relabel-2026-09-22/BRIEF-v3.md`,
rwxmap commit 4143b6d26d69e9177f15f4913c3613a0a361724c, the last commit touching it). The user rules disputes.

**Used ONCE.** This sample is the label gate and nothing else. It is never used for tuning, threshold sweeps, model
selection or any repeated scoring. After the gate it is burned. Nothing is scored on the exam until the gate passes.

## Files

- `blind.csv`: id, provider, method, path, operationId, summary, description. Shuffled order. No mechanical letter, no Jev p, no class hint of any kind.
- `ids.txt`: 740 `ag-` row ids = the 600 sampled rows PLUS every APIs.guru snapshot sharing their
  op key (provider+method+path+operationId). This is the training exclusion list: none of these may enter training or tuning.
- `BRIEF-v3.md`: the only label standard.
- Truth comes from the labellers later. There is no key here.

## Draw

- Seed: 20261104 (mulberry32; sort op keys, one Fisher-Yates shuffle, take in order subject to quotas). `node m0/gate-sample.mjs --gate 2` reproduces these files byte for byte.
- Unit = op key (provider+method+path+operationId); one row per op key (first snapshot's text).
- Quotas (GET/POST/PUT/PATCH): GET 325, POST 175, PUT 50, PATCH 50. Proportional to availability, with at least 100 GET and 100 PUT+PATCH.
- Vendor cap: 30 rows per vendor (5% of 600); vendor = first dotted token of provider.

## Exclusions (op keys)

Total op keys: 97275 (from 123339 rows). Excluded, in order: exam vendors (cloudflare, pagerduty, sentry) 0;
the other 7 locked vendors (auth0, hubspot, zendesk, dropbox, shopify, linear, miro) 0; exam_opkey_overlap 19;
already in a v3 truth set (combined-2026-09-21, relabel-buildset-2026-09-23) 3723; already in gate-1 (any snapshot of an op key in data/gate-2026-11-03/ids.txt) 600; DELETE 8935; HEAD/OPTIONS/TRACE/other 201.
Eligible: 83797.

## Amendment: burned-exam vendors excluded by name (rwxmap lock check)

rwxmap's lock check on this gate found xero.com in the draw: xero was an exam vendor in rwxmap `data/exam-2026-09-17`
(with okta and docusign). rwxmap's rule is that a draw excludes prior exam vendors BY NAME, not only by row. The first
draw only excluded exam rows/op keys and cloudflare/pagerduty/sentry by first token, so xero.com (1 row) slipped in.

Fix (minimal): the original seeded draw above is unchanged; every row whose provider has a whole domain label (split on
`.` and `:`) in the burned/locked name list is dropped, and only those slots are redrawn: 1 rows. Each new row takes
the freed id/position, comes from a second seeded shuffle (seed 20261105, mulberry32, sorted op keys) of the by-name-eligible pool, same
method stratum (POST 1), same 30-row vendor cap, same exclusions as above
(including gate-1). All other 599 rows and ids are unchanged. ids.txt and providers.txt are rewritten.
Names excluded: okta, docusign, xero, klaviyo, cloudflare, pagerduty, sentry, auth0, hubspot, zendesk, miro, dropbox, shopify, linear. Burned exam vendors: okta, docusign, xero (exam-2026-09-17); auth0, hubspot, klaviyo, miro, zendesk
(exam-2026-09-20); cloudflare, pagerduty, sentry (exam-2026-09-22). Locked only: dropbox, shopify, linear.
Replaced ids: gate2-0216 (all were xero.com, replaced in place).

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
| azure | 30 |
| googleapis | 30 |
| microsoft | 30 |
| autotask | 29 |
| twilio | 14 |
| vtex | 12 |
| zuora | 12 |
| loket | 9 |
| mist | 8 |
| bunq | 7 |
| linode | 7 |
| xtrf | 7 |
| apideck | 6 |
| gerermesaffaires | 6 |

(218 vendors in all.)

## Status: USED (scored once, 2026-11-03)

Labelled by two blind workers, A and B (`labels-A.csv`, `labels-B.csv`), high/low confidence only. A and B agreed on 590 of 600 (98.3%). The user ruled the 10
disputes (`rulings.csv`). `truth.csv` = agreed label, else the ruling (600 rows, no "?").
`node m0/gate-score.mjs --gate 2026-11-04` scored the gate once; result in `score.json` (verdict PASS, 96.5% exact at the round-6 recipe, too-loose 4 vs mechanical 7).
This sample is now BURNED: no tuning, sweeps, model selection or re-scoring on it.
