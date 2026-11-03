# data/gate-2026-11-06 — gate-3 sample for rwxmap F2 (credential-change words exam), blind

## Purpose

800 operations drawn from the 123k APIs.guru ops (`data/m0/mechanical.jsonl.gz`) as the exam set for rwxmap's F2
(credential-change words). This is an rwxmap exam, NOT an rwxlite exam: rwxlite's MiniLM was trained on these rows, so
scoring rwxlite on them would be contaminated.

**Used ONCE.** Never used for tuning, threshold sweeps, model selection or repeated scoring.

## Files

- `blind.csv`: id, provider, method, path, operationId, summary, description. 800 rows, ids gate3-0001..0800 assigned after one seeded shuffle of all 800, so credential-stratum rows are indistinguishable from general rows.
- `part.csv`: id,part (cred|general). This is the KEY saying which part a row is in. **Labellers must never see part.csv.**
- `ids.txt`: 1067 `ag-` row ids = the 800 sampled rows PLUS every APIs.guru snapshot sharing their op key (provider+method+path+operationId). Training exclusion list.
- `providers.txt`: sorted provider list (257).
- `BRIEF-v3.md`: byte copy of gate-2's.

## Draw

Seed 20261106 (mulberry32), one rng stream: shuffle of the credential pool, shuffle of the general pool, then the final shuffle of all 800. Reproduce: `node m0/gate-sample.mjs --gate 3`.
Unit = op key (provider+method+path+operationId); one row per op key (first snapshot's text).

Eligibility (both parts): exclude op keys in data/gate-2026-11-03/ids.txt and data/gate-2026-11-04/ids.txt (any snapshot); ops in rwxmap combined-2026-09-21 and relabel-buildset-2026-09-23; exam / exam_opkey_overlap rows; HEAD/OPTIONS/TRACE; DELETE; and by whole domain label (split on "." and ":") okta docusign xero klaviyo cloudflare pagerduty sentry auth0 hubspot zendesk miro dropbox shopify linear hubapi.

Part 1, credential stratum (200): method in POST/PUT/PATCH AND the string (path + " " + operationId + " " + summary; description NOT used) matches, case-insensitive:

    /password|passcode|\bpin\b|secret|credential|key|token|certificate|session/i

PUT+PATCH drawn first, up to 100 (got 100), then POST to fill to 200. Vendor cap 10 per vendor across the stratum.

Part 2, general (600), drawn after and never sharing an op key with Part 1: GET 325 / POST 175 / PUT 50 / PATCH 50, vendor cap 30. Vendor = first dotted token of provider.

## Exclusion counts (op keys)

Total 97275. by-name 694; exam/exam_opkey_overlap 19; prior gates 1200; v3 truth 3113; DELETE 8929; HEAD/OPTIONS/TRACE/other 201. Eligible 83119.

## Pool sizes

Credential-eligible: POST 1851, PUT 304, PATCH 141. General pool (eligible minus stratum draw): GET 44957, POST 27492, PUT 5219, PATCH 5251.

## Counts

Credential part:

| method | n |
|---|---|
| POST | 100 |
| PATCH | 32 |
| PUT | 68 |

General part:

| method | n |
|---|---|
| GET | 325 |
| POST | 175 |
| PATCH | 50 |
| PUT | 50 |

Top vendors, credential: amazonaws 10, apisetu 10, azure 10, googleapis 10, microsoft 10, jira 6, visualstudio 5, citrixonline 4.
Top vendors, general: amazonaws 30, azure 30, googleapis 30, microsoft 30, autotask 24, github 12, vtex 11, netbox 10.

## Amendment: hubapi.com dropped by name (rwxmap lock check 2026-11-03)

rwxmap's lock check on this gate found hubapi.com in the draw: hubapi.com is HubSpot, a burned x20 exam vendor. `hubapi` was added to the by-name exclusion list (the "whole domain label" list above includes it). Minimal fix, as with gate-2's xero: every row whose provider had the domain label hubapi (2) was replaced in place, same part and same method stratum, same rules (credential: regex, same method as the replaced row so PUT+PATCH-first logic is preserved, vendor cap 10; general: vendor cap 30), from a second seeded shuffle (seed 20261107, mulberry32) excluding every op key already in gate-1/2/3. All other rows and their gate3- ids are unchanged. blind.csv, part.csv, ids.txt and providers.txt were rewritten. The Draw/Pool/Exclusion counts above describe the original draw; the Counts tables and Top vendors are final.
Replaced ids: gate3-0127, gate3-0207.

## Vendor-clean line for scoring

Exclude providers whose whole domain label is in: adyen appcenter atlassian azure box clearblade dracoon gitea github gitlab jira keycloak linode microsoft netbox notion openai slack trello twilio vercel whatsapp xero zoom.
