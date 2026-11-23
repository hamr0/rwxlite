# Round 16 exam #8 result (rwxlite figures)

Scored once on 2026-11-23, branch r16-vendor-data. **These are rwxlite's own figures. rwxmap's CLI score (`score.mjs` at rwxmap 474ecb1) is the official one.** Exam #8 is owned by rwxmap; once both sides have scored it is burned.

## Order followed

1. Predictions made (Node answerer, fp32, batch 1, `m1/exam5-predict.mjs`, lean prefix from rwxmap lean.csv at ecee4f1 fed as is).
2. Prediction sha256s committed alone: `37ac8c4` (`docs/product/r16-exam8-pred-sha256.txt`).
3. Only then truth.csv opened; its sha256 checked: `0dfc8b42bd85f336ab7897b902e228e0ec8cca2960f0ffc6b8887dee17e8ac42` (matches).
4. `r16/exam8-score.py` run once (refuses an existing output). Nothing re-run or tuned after the truth was seen.

Inputs verified: ops.csv `7d2be1f3...b428de`, lean.csv `87a6e897...a1502`, candidate model-fp32 `82fa50c3...`, baseline model-fp32 `4608f470...`. Candidate rwxlite-0.5.0+82fa50c3 (T 1.7029), baseline rwxlite-0.4.0+4608f470 (shipped T). Mode a and b85 letters come from the real `src/secondpass.js` of rwxmap ecee4f1 (git archive), cut 0.90 / confidence 85; the real `classifyOperations` reproduced lean.csv with 0 differing rows. Truth classes: r 845, w 406, x 570 (N = 1,821).

## Scores, all 1,821 rows (exact / too loose / too tight; r < w < x)

| mode | base 0.4.0 | cand 0.5.0 | diff exact | diff loose | paired better / worse (cand vs base) |
|---|---|---|---|---|---|
| a, cut 0.90 (GATE) | 1631 / 65 / 125 | 1653 / 60 / 108 | +22 | -5 | 26 / 4 (letters differ on 31) |
| b85 (info) | 1643 / 47 / 131 | 1656 / 44 / 121 | +13 | -3 | 26 / 13 (letters differ on 41) |
| standalone argmax (info) | 1673 / 91 / 57 | 1683 / 86 / 52 | +10 | -5 | 19 / 9 (letters differ on 28) |

Mechanical alone (lean, for reference): 1556 / 73 / 192.

## Gate D142 (rwxmap prereg wording, mode a, fp32, 1,821 rows)

exact_cand >= exact_base AND too_loose_cand <= too_loose_base + floor(0.01 x 1821) = +18.

- exact: 1653 >= 1631: pass (+22).
- too loose: 60 vs 65 + 18 = 83: pass (diff -5).
- **Verdict on rwxlite's numbers: GO.** Too tight is reported, not gated: 108 vs 125.

Per vendor, mode a (exact / too loose / too tight):

| vendor | n | mech | base | cand |
|---|---|---|---|---|
| baserow.io | 488 | 397 / 18 / 73 | 419 / 18 / 51 | 423 / 17 / 48 |
| bitrise.io | 128 | 120 / 4 / 4 | 124 / 2 / 2 | 123 / 3 / 2 |
| gitbook.com | 403 | 356 / 18 / 29 | 366 / 13 / 24 | 371 / 12 / 20 |
| looker.com | 502 | 426 / 25 / 51 | 445 / 25 / 32 | 451 / 22 / 29 |
| shortcut.com | 143 | 126 / 1 / 16 | 141 / 1 / 1 | 142 / 1 / 0 |
| wekan.github.io | 157 | 131 / 7 / 19 | 136 / 6 / 15 | 143 / 5 / 9 |

## Candidate too-loose rows (mode a, 60 rows)

All 60 have truth x (none has truth w). By vendor: looker.com 22, baserow.io 17, gitbook.com 12, wekan.github.io 5, bitrise.io 3, shortcut.com 1. By HTTP method: PATCH 30, GET 12, PUT 11, POST 7. By mechanical rule: method-floor 41, method 12, content-noun 3, floor-post 2, modify-verb 2. What the second pass did: kept 58, lowered 2.

Reading: 58 of 60 are rows where mechanical already said the same too-loose letter and the model agreed (kept); mostly PATCH/PUT updates of configuration, auth or admin objects (method-floor w, truth x) and GET rows with an action in the path (check, callback, preview, pdf, start, stop; rule method, r, truth x). Only 2 are model lowerings (floor-post x lowered to w: baserow POST /api/teams/{team_id}/subjects/, looker POST /scheduled_plans); the baseline lowered the same two and also 4 others. Baseline too-loose by vendor: baserow.io 18, bitrise.io 2, gitbook.com 13, looker.com 25, shortcut.com 1, wekan.github.io 6; by move: {'kept': 59, 'lowered': 6}.

| id | vendor | method | path | rule | mech | base | cand | move |
|---|---|---|---|---|---|---|---|---|
| ex8-0035 | baserow.io | PATCH | `/api/admin/users/{user_id}/` | method-floor | w | w | w | kept |
| ex8-0043 | baserow.io | PATCH | `/api/agent/{agent_id}/configuration/` | method-floor | w | w | w | kept |
| ex8-0063 | baserow.io | PUT | `/api/ai-providers/features/{feature_type}/` | method-floor | w | w | w | kept |
| ex8-0071 | baserow.io | PATCH | `/api/ai-providers/{provider_id}/` | method-floor | w | w | w | kept |
| ex8-0127 | baserow.io | PATCH | `/api/builder/domains/{domain_id}/` | method-floor | w | w | w | kept |
| ex8-0144 | baserow.io | GET | `/api/builder/preview/exchange/{token}/` | method | r | r | r | kept |
| ex8-0181 | baserow.io | PATCH | `/api/database/admin/views/{view_id}/` | method-floor | w | w | w | kept |
| ex8-0207 | baserow.io | PATCH | `/api/database/fields/{field_id}/` | method-floor | w | w | w | kept |
| ex8-0236 | baserow.io | GET | `/api/database/tokens/check/` | method | r | r | r | kept |
| ex8-0338 | baserow.io | GET | `/api/licenses/{id}/check/` | method | r | r | r | kept |
| ex8-0346 | baserow.io | PATCH | `/api/mcp/endpoint/{endpoint_id}/` | method-floor | w | w | w | kept |
| ex8-0384 | baserow.io | GET | `/api/sso/oauth2/callback/{provider_id}/` | method | r | r | r | kept |
| ex8-0396 | baserow.io | POST | `/api/teams/{team_id}/subjects/` | floor-post | x | w | w | lowered |
| ex8-0403 | baserow.io | PATCH | `/api/templates/{slug}/` | method-floor | w | w | w | kept |
| ex8-0420 | baserow.io | PATCH | `/api/user-source/{user_source_id}/` | method-floor | w | w | w | kept |
| ex8-0424 | baserow.io | GET | `/api/user-source/{user_source_uid}/sso/oauth2/openid_connect/callback/` | method | r | r | r | kept |
| ex8-0446 | baserow.io | GET | `/api/webhooks/{webhook_uid}/` | method | r | r | r | kept |
| ex8-0524 | bitrise.io | PATCH | `/apps/{app-slug}/builds/{build-slug}/artifacts/{artifact-slug}` | method-floor | w | w | w | kept |
| ex8-0542 | bitrise.io | PUT | `/apps/{app-slug}/github-app-connection-configuration` | method-floor | w | w | w | kept |
| ex8-0560 | bitrise.io | POST | `/apps/{app-slug}/provisioning-profiles/{provisioning-profile-slug}/uploaded` | content-noun | w | x | w | kept |
| ex8-0706 | gitbook.com | POST | `/orgs/{organizationId}/domains` | modify-verb | w | w | w | kept |
| ex8-0709 | gitbook.com | PATCH | `/orgs/{organizationId}/domains/{emailDomain}` | method-floor | w | w | w | kept |
| ex8-0740 | gitbook.com | PUT | `/orgs/{organizationId}/openapi/{specSlug}` | method-floor | w | w | w | kept |
| ex8-0764 | gitbook.com | PATCH | `/orgs/{organizationId}/sites/{siteId}` | method-floor | w | w | w | kept |
| ex8-0790 | gitbook.com | PATCH | `/orgs/{organizationId}/sites/{siteId}/channels/{siteChannelId}` | method-floor | w | w | w | kept |
| ex8-0795 | gitbook.com | PATCH | `/orgs/{organizationId}/sites/{siteId}/context-connections/{siteContextConnectionId}` | method-floor | w | w | w | kept |
| ex8-0823 | gitbook.com | PATCH | `/orgs/{organizationId}/sites/{siteId}/mcp-servers/{siteMcpServerId}` | method-floor | w | w | w | kept |
| ex8-0837 | gitbook.com | GET | `/orgs/{organizationId}/sites/{siteId}/publishing/preview` | method | r | r | r | kept |
| ex8-0872 | gitbook.com | PATCH | `/orgs/{organizationId}/sites/{siteId}/site-spaces/{siteSpaceId}` | method-floor | w | w | w | kept |
| ex8-0894 | gitbook.com | POST | `/orgs/{organizationId}/storage/upload` | content-noun | w | x | w | kept |
| ex8-0949 | gitbook.com | GET | `/spaces/{spaceId}/change-requests/{changeRequestId}/pdf` | method | r | r | r | kept |
| ex8-0989 | gitbook.com | GET | `/spaces/{spaceId}/pdf` | method | r | r | r | kept |
| ex8-1028 | looker.com | POST | `/alerts` | content-noun | w | w | w | kept |
| ex8-1032 | looker.com | PATCH | `/alerts/{alert_id}` | method-floor | w | w | w | kept |
| ex8-1033 | looker.com | PUT | `/alerts/{alert_id}` | method-floor | w | w | w | kept |
| ex8-1063 | looker.com | PATCH | `/cloud_storage` | method-floor | w | w | w | kept |
| ex8-1079 | looker.com | PATCH | `/connections/{connection_name}` | method-floor | w | w | w | kept |
| ex8-1119 | looker.com | PATCH | `/custom_welcome_email` | method-floor | w | w | w | kept |
| ex8-1160 | looker.com | PATCH | `/dashboards/{lookml_dashboard_id}/sync` | method-floor | w | w | w | kept |
| ex8-1169 | looker.com | GET | `/derived_table/{materialization_id}/stop` | method | r | r | r | kept |
| ex8-1170 | looker.com | GET | `/derived_table/{model_name}/{view_name}/start` | method | r | r | r | kept |
| ex8-1178 | looker.com | GET | `/embed/sso/validate` | method | r | r | r | kept |
| ex8-1215 | looker.com | POST | `/groups/{group_id}/groups` | modify-verb | w | w | w | kept |
| ex8-1270 | looker.com | PATCH | `/mobile/device/{device_id}` | method-floor | w | w | w | kept |
| ex8-1277 | looker.com | PATCH | `/model_sets/{model_set_id}` | method-floor | w | w | w | kept |
| ex8-1289 | looker.com | PATCH | `/oidc_config` | method-floor | w | w | w | kept |
| ex8-1308 | looker.com | PATCH | `/projects/{project_id}` | method-floor | w | w | w | kept |
| ex8-1330 | looker.com | PUT | `/projects/{project_id}/git_branch` | method-floor | w | w | w | kept |
| ex8-1387 | looker.com | POST | `/scheduled_plans` | floor-post | x | w | w | lowered |
| ex8-1396 | looker.com | PATCH | `/scheduled_plans/{scheduled_plan_id}` | method-floor | w | w | w | kept |
| ex8-1407 | looker.com | PATCH | `/setting` | method-floor | w | w | w | kept |
| ex8-1419 | looker.com | PATCH | `/ssh_server/{ssh_server_id}` | method-floor | w | w | w | kept |
| ex8-1425 | looker.com | PATCH | `/ssh_tunnel/{ssh_tunnel_id}` | method-floor | w | w | w | kept |
| ex8-1516 | looker.com | PATCH | `/workforce_config` | method-floor | w | w | w | kept |
| ex8-1532 | shortcut.com | PUT | `/api/v3/custom-fields/{custom-field-public-id}` | method-floor | w | w | w | kept |
| ex8-1666 | wekan.github.io | PUT | `/api/admin/attachment-settings` | method-floor | w | w | w | kept |
| ex8-1671 | wekan.github.io | PUT | `/api/admin/orgs/features` | method-floor | w | w | w | kept |
| ex8-1672 | wekan.github.io | PUT | `/api/admin/orgs/{org}/features` | method-floor | w | w | w | kept |
| ex8-1678 | wekan.github.io | PUT | `/api/admin/teams/features` | method-floor | w | w | w | kept |
| ex8-1679 | wekan.github.io | PUT | `/api/admin/teams/{team}/features` | method-floor | w | w | w | kept |

## The known collision rows (information only; all 1,821 rows are scored above)

`docs/product/r16-exam8-leakage-check.md`: 58 teacher-train-v3 rows share method+path+summary with 26 exam ops (list rebuilt from the leakage scratch `ms_detail`, exam ids only). Effect:

| subset | mode | base | cand |
|---|---|---|---|
| the 26 collision ops | a | 25 / 1 / 0 | 26 / 0 / 0 |
| the 26 collision ops | b85 | 25 / 1 / 0 | 26 / 0 / 0 |
| the 26 collision ops | standalone | 25 / 1 / 0 | 25 / 1 / 0 |
| without them (1795 rows) | a | 1606 / 64 / 125 | 1627 / 60 / 108 |
| without them (1795 rows) | b85 | 1618 / 46 / 131 | 1630 / 44 / 121 |
| without them (1795 rows) | standalone | 1648 / 90 / 57 | 1658 / 85 / 52 |

Without the collision ops the gate reads: exact 1627 vs 1606 (pass), too loose diff -4 against allowance 17: same outcome. The collision ops gave the candidate +1 exact and -1 too loose over the baseline; the gain is not from them.

## Notes

- Mode a differs from rwxmap's CLI only if the CLI parses ops differently from ops.csv; the replay used the real secondPass and mechanical, and our mechanical matched lean.csv exactly. A difference from rwxmap's number would be a join or text issue to resolve, not a rescore.
- Files: predictions, per-row p_r/p_w/p_x with standalone letter, and mode a / b85 letters are in `data/r16/exam8/` (gitignored; sha256 in `docs/product/r16-exam8-pred-sha256.txt`). Raw result `data/r16/exam8/result.json`. Scripts: `r16/exam8-secondpass.mjs`, `r16/exam8-score.py`.
- Nothing here is a tag, push or publish.
