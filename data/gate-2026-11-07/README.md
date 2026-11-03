# data/gate-2026-11-07 — gate-4 sample for rwxmap (general + write stratum), blind

## Purpose

800 operations drawn from the 123k APIs.guru ops (`data/m0/mechanical.jsonl.gz`) as an rwxmap exam set: 600 general rows plus a 200-row write stratum. This is an rwxmap exam, NOT an rwxlite exam: rwxlite's MiniLM was trained on these rows, so scoring rwxlite on them would be contaminated.

**Used ONCE.** Never used for tuning, threshold sweeps, model selection or repeated scoring.

## Files

- `blind.csv`: id, provider, method, path, operationId, summary, description. 800 rows, ids gate4-0001..0800 assigned after one seeded shuffle of all 800, so write-stratum rows are indistinguishable from general rows.
- `part.csv`: id,part (write|general). This is the KEY saying which part a row is in. **Labellers must never see part.csv.**
- `ids.txt`: 988 `ag-` row ids = the 800 sampled rows PLUS every APIs.guru snapshot sharing their op key (provider+method+path+operationId). Training exclusion list.
- `providers.txt`: sorted provider list (250).
- `BRIEF-v3.md`: byte copy of gate-3's (unchanged).

## Draw

**Seed 20261107** (mulberry32), one rng stream: shuffle of the write pool, shuffle of the general pool, then the final shuffle of all 800. Reproduce: `node m0/gate-sample.mjs --gate 4`.
Unit = op key (provider+method+path+operationId); one row per op key (first snapshot's text).

Eligibility (both parts): exclude op keys in data/gate-2026-11-03, -04 and -06 ids.txt (gates 1-3, any snapshot); ops in rwxmap combined-2026-09-21 and relabel-buildset-2026-09-23; exam / exam_opkey_overlap rows; HEAD/OPTIONS/TRACE; DELETE; and by whole domain label (split on "." and ":") okta docusign xero klaviyo cloudflare pagerduty sentry auth0 hubspot zendesk miro dropbox shopify linear hubapi.

Part 1, write stratum (200): POST 100 / PUT 50 / PATCH 50, pure seeded random draw over eligible POST/PUT/PATCH ops. NO word or regex filter of any kind. Vendor cap 10 per vendor across the stratum.

Part 2, general (600), drawn after and never sharing an op key with Part 1: GET 325 / POST 175 / PUT 50 / PATCH 50, vendor cap 30. Vendor = first dotted token of provider.

## Exclusion counts (op keys)

Total 97275. by-name 773; exam/exam_opkey_overlap 19; prior gates 2000; v3 truth 3113; DELETE 8917; HEAD/OPTIONS/TRACE/other 201. Eligible 82252. (Counts are sequential, in that order.)

Assertions run in code on the final 800 (all passed): {"rows":800,"unique_op_keys":800,"burned_name_rows":0,"prior_gate_rows":0,"truth_rows":0,"exam_rows":0,"delete_or_other":0,"write_in_general_overlap":0}.

By-name drops (provider [matched label]: op keys): docusign.net [docusign]: 393; hubapi.com [hubapi]: 79; okta.local [okta]: 19; xero.com [xero]: 282. hubapi.com is HubSpot. No other alias domain of a locked or exam vendor exists in the provider list (checked for the 10 locked names, okta/docusign/xero/klaviyo, hubapi, zdassets, zopim, and substring matches).

## Pool sizes

Write-eligible: POST 27292, PUT 5164, PATCH 5196. General pool (eligible minus stratum draw): GET 44600, POST 27192, PUT 5114, PATCH 5146.

## Counts

Write part:

| method | n |
|---|---|
| PUT | 50 |
| POST | 100 |
| PATCH | 50 |

General part:

| method | n |
|---|---|
| GET | 325 |
| POST | 175 |
| PUT | 50 |
| PATCH | 50 |

Top vendors, write: amazonaws 10, autotask 10, azure 10, googleapis 10, microsoft 10, netbox 10, adyen 5, kubernetes 5.
Top vendors, general: amazonaws 30, autotask 30, azure 30, googleapis 30, microsoft 30, kubernetes 12, vtex 11, github 9.

## Status

Unlabelled. Labelling is a separate step.
