# Exam #5 leakage check (rwxlite side)

Date: 2026-11-07. Branch `dev`. No model was run and no prediction was made. The exam files were only read; nothing was written in the rwxmap tree.

## 1. Input integrity

Exam inputs: `/home/hamr/PycharmProjects/rwxmap/data/exam5-2026-11-07/ops.csv` (rwxmap commit 23a2b13).

- sha256 of `ops.csv`: `f6e245ed8e6953b8a7170a0bf6b6a371860460fc7206db6a5cbe23fbba1f26ea` = expected value. MATCH.
- 1,443 rows. Per-vendor counts match the brief: frontapp.com 246, planetscale.com 291, paddle.com 126, hookdeck.com 135, fusionauth.io 364, semaphoreui.com 155, weaviate.io 126.

## 2. Verdict per vendor (vendor identity)

Tokens searched, case-insensitive: front, frontapp, api2.frontapp.com, planetscale, api.planetscale.com, paddle, paddlehq, api.paddle.com, sandbox-api.paddle.com, hookdeck, api.hookdeck.com, fusionauth, sandbox.fusionauth.io, semaphore, semaphoreui, weaviate, plus the domains paddle.com, frontapp.com and so on.

| vendor | verdict | evidence |
|---|---|---|
| front (frontapp.com) | CLEAN | No provider/vendor/api_key/alias field anywhere contains `frontapp` or is `front`. The only provider-field hits for "front" are substrings of other products: `amazonaws.com:cloudfront`, `azure.com:frontdoor`, `frontdoor-networkexperiment`, `frontdoor-webapplicationfirewall`, `twilio.com:twilio_frontline_v1` (all incidental). Free-text "front" hits are all incidental, see section 4. |
| planetscale (planetscale.com) | CLEAN (one incidental mention) | No provider-field hit. One free-text hit: the Cloudflare `Create Hyperdrive` description says "For a PlanetScale integration, the Cloudflare account must already be linked to PlanetScale". It is a cross-reference in a Cloudflare op, not a PlanetScale op. It is in `data/exam-r8soft/inputs.jsonl` (a scored exam) and `data/m1/corpus-parity.jsonl` (parity check set). Not in R13 train/val, round10-12, data/train or the m0 mechanical corpus. |
| paddle (paddle.com) | CLEAN | Zero hits for `paddle`, `paddlehq`, `paddle.com` in any provider field, id, path, operationId, summary or description in any file scanned. |
| hookdeck (hookdeck.com) | CLEAN | Zero hits. |
| fusionauth (fusionauth.io) | CLEAN | Zero hits. |
| semaphore (semaphoreui.com) | CLEAN | Zero hits for `semaphore` or `semaphoreui` anywhere. |
| weaviate (weaviate.io) | CLEAN | Zero hits. |

Overall: no exam vendor appears in anything R13 or any earlier model trained or validated on, nor in any earlier exam, gate or holdout.

`data/v4/rwxlite-providers.csv` (902 providers) and `data/round13/vendors-r13-seen.txt` (682 lines): neither lists any of the seven vendors or aliases. The three "front" matches there are the incidental substrings cloudfront, frontdoor and twilio_frontline.

## 3. Method

Scope. Text files under `data/`, `m0/`, `m1/`, `train/`, `vendor/`, `src/`, `test/`, `docs/`, searched with `rg --no-ignore -z` (data is gitignored; gzip read directly). Excluded as non-text: `*.onnx`, `*.safetensors`, `*.pt`, `*.npy`, `*.npz`, `*.pkl`, `*.parquet`. The parquet files in `data/round13` and others are copies of the jsonl files of the same name, which were scanned. (pandas is not installed here so the parquet copies were not opened separately.)

Files covered: round13 and round13-t2 (train, val, v3eval, provenance, val-ops-for-rwxmap), round10, round11, round12 (including final/S0-S2), data/train, m0 mechanical corpus (`mechanical.jsonl.gz`, 123,339 ops, 673 providers), data/v4, data/vendor (ops, all-rows, candidates, joined), exam3, exam3-smoke, exam4, exam4-smoke, exam-2026-11-03-fresh, exam-r8soft, exam-fresh-r8soft, fresh-exam-specs, gate-2026-11-03/04/06/07, holdout, r9-hand, r12 (inputs, replay, mistakes), m1 corpus-parity, plus tokenizer/vocab files (ignored: they hold subword pieces).

Steps:
1. Substring search of all tokens across whole lines (so ids, paths, operationIds, summaries, descriptions, text, provider fields are all covered).
2. For jsonl, a field-level pass on provider, vendor, api_key (and the v4 aliases column) for every token.
3. "front" is split into whole-word and embedded matches (cloudFront, frontend, FrontDoor) and each distinct hit group was read.
4. Op-level overlap (section 5), computed with a throwaway script in the session scratch dir (not committed).

## 4. Incidental hits, classified

Strong tokens (frontapp, planetscale, paddle*, hookdeck, fusionauth, semaphore*, weaviate): only the single PlanetScale-in-Cloudflare description above.

"front" hits, all incidental:
- Embedded in a longer word: CloudFront (amazonaws.com), FrontDoor (azure.com), Frontend (AWS `...FrontendService` X-Amz-Target ops), Frontline (twilio), Hyperdrive/other descriptions.
- Whole word "front" in R13 train: `/dcim/front-port-templates/` and `dcim_front-port-templates_*` ops (netbox.dev 21, netboxdemo.com 15 path/operationId hits; netbox "front ports" are physical cable ports), `front-ports` in v3eval (netbox.dev 2), and one ory.sh summary "OpenID Connect Front- and Back-channel Enabled Logout". Also "front" in descriptions (front-end, front of ...).
- R13 val: three embedded hits, no vendor match.

None refers to Front (frontapp.com) the product.

## 5. Op-level overlap

Keys. Method+path: upper-case method, path lower-cased, `{x}`, `:x`, `<x>` collapsed to `{}`, query dropped, trailing slash dropped. operationId: exact string match. "Generic" = the key occurs in 3 or more distinct training providers; "rare" = in 1-2.

Reference corpus = R13 train, val, v3eval, round13-t2, round12/11/10 train, data/train, m0 mechanical, data/vendor. The result is identical when restricted to R13 train+val+v3eval alone, because they contain everything earlier models saw for these keys.

| vendor | ops | method+path match | of which generic | of which rare | operationId match | generic | rare |
|---|---|---|---|---|---|---|---|
| frontapp.com | 246 | 53 | 27 | 26 | 15 | 0 | 15 |
| planetscale.com | 291 | 11 | 4 | 7 | 18 | 0 | 18 |
| paddle.com | 126 | 30 | 22 | 8 | 14 | 0 | 14 |
| hookdeck.com | 135 | 26 | 17 | 9 | 34 | 11 | 23 |
| fusionauth.io | 364 | 17 | 2 | 15 | 8 | 5 | 3 |
| semaphoreui.com | 155 | 15 | 14 | 1 | 0 | 0 | 0 |
| weaviate.io | 126 | 16 | 5 | 11 | 11 | 2 | 9 |
| total | 1,443 | 168 | 91 | 77 | 100 | 18 | 82 |

Unique exam ops with a method+path or operationId match: 206 of 1,443 (14.3%). Of these, 101 are generic on at least one key. Exam ops matching on all three (method, path, operationId): 20 (1.4%).

Highest single-source overlap per vendor (distinct source provider, number of exam ops sharing method+path / operationId): frontapp: amazonaws.com 14, chatwoot.com 4; fusionauth: meshery.local 5, nexmo.com 3; hookdeck: contract-p.fit 12, airbyte.local 12; paddle: rebilly.com 12, codat.io 8; planetscale: neon.com 8, permit.io 10; semaphoreui: apacta.com 9, no operationId in the spec at all; weaviate: docker.com 5, appveyor.com 4. No source provider overlaps more than 14 ops of any vendor, and none comes near the 126-364 ops a copied spec would produce.

Examples, generic vs coincidental:
- Generic method+path: `GET /health` (17 training providers), `GET /users` (48), `POST /users` (34).
- Semaphore `GET/POST /user/tokens`, `DELETE /user/tokens/{api_token_id}` also appear in cloudflare (route name coincidence); `POST /users/{user_id}/password` in influxdata.com and jellyfin.local.
- Hookdeck triple matches (method, path, operationId) with asana.com, goharbor.io, launchdarkly.com, neon.com, ory.sh, motaword.com, xero.com: `GET /projects listProjects`, `POST /projects createProject`, `GET /events getEvent`, `GET /connections getConnections` (xero.com). These are CRUD names any REST API would pick.
- Front triple matches: `GET /tags list-tags`, `POST /tags create-tag`, `GET /teams list-teams` (coolify.io); `DELETE /drafts/{draft_id} delete-draft`, `GET /messages/{message_id} get-message` (zulip.com). Kebab-case CRUD names, generic.
- Weaviate triple: `GET /namespaces/{namespace_id} getNamespace` (docker.com), one op.
- operationId matches on a different path: frontapp `list-accounts`/`create-account` on `/accounts` (codat.io), paddle `list-customers`, `get-customer` (codat.io; the Paddle and Codat ids share kebab naming), planetscale `list_organizations`, `get_organization`, `list_audit_logs` (permit.io), fusionauth `retrieveApplication`/`createApplication` on `/api/application` (nexmo.com) and `GET/POST /api/application` (meshery.local; FusionAuth uses /api/application, the Meshery path is coincidence).

Reading: this is generic REST naming overlap, spread across many unrelated providers, concentrated in CRUD routes (/accounts, /customers, /projects, /tags, /events, /organizations). It is not a copied spec: no single source provider carries more than a small slice, and no vendor's distinctive routes (e.g. paddle `/transactions/{id}/revise`, fusionauth `/api/user/registration`, weaviate `/v1/batch/objects`, planetscale `/organizations/{o}/databases/{d}/branches/{b}/...`) appear in training under another provider name.

## 6. Conclusion

All seven vendors: CLEAN on provider/vendor identity, with one incidental PlanetScale mention inside a Cloudflare description that is not in R13 training data. Op-level overlap (206/1,443 ops, about half of it on generic routes) is naming coincidence between unrelated APIs, not spec duplication. Nothing here argues against using exam #5 as a clean exam.

Caveat. Overlap is a count, not a label check: a matching key can carry a different letter in training, and this report does not look at labels.
