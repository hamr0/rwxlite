# Findings

Dated learnings, newest last. Plain English. The contract lives in `docs/product/prd.md`.

## 2026-11-03: M0 step 1, mechanical pass

Source: `m0/mechanical.mjs`, commit 53ab0d9.

- 123,339 operations from 673 providers, 0 dropped, 8.3 seconds, free.
- Mechanical letters: r 62,879 / w 17,344 / x 43,116.
- Rule split: r/method 59,977; r/read-verb 2,686; r/read-verb-anywhere 216; w/method-floor 15,128; w/modify-verb 2,135; w/modify-verb-summary 81; x/floor-post 27,666; x/method-delete 13,276; x/cant-undo-verb 2,113; x/cant-undo-verb-summary 61.
- Jev piles (rwxmap's tiers): raise-get 59,977, lower 27,666, raise-wx 15,128, none 20,568. So 83% of rows sit in a pile.
- Methods: GET 59,779; POST 34,805; DELETE 13,276; PATCH 7,734; PUT 7,542; HEAD 114; OPTIONS 84; TRACE 5.
- 14,329 rows are flagged destructive.

### Exam sanity

Re-scoring the 4,279-op exam with the same function gives 3,520 exact (82.26%), 34 too loose (0.79%), 725 too tight (16.94%). This matches rwxmap's 82.3 / 0.8 / 16.9.
The exam README says 37 leaks and 722 over-tight. Exact agrees; 3 rows sit on the other side of the loose/tight line. Cause not found. It does not change any bar.

### Leakage check

- 0 rows from the 10 locked vendors (auth0, cloudflare, hubspot, zendesk, pagerduty, dropbox, shopify, linear, miro, sentry). Source: rwxmap `docs/logs/pre-registered-split-2026-09-18.md`. Checked by the main session.
- 19 rows share method + path + operationId with an exam row, from unrelated vendors. Flagged `exam_opkey_overlap`; the PRD drops them.
- 240 of the 1,186 hand labels are rows from exam vendors. Exclude them if hand labels enter training.

### Joins

- 1,152 rows carry a hand label (`hand_set`).
- 549 rows are calibration rows (`calib_set`).
- These two sets are the check for the 95% label gate.

## 2026-11-03: advice from the rwx session on asking Jev

Sources: rwxmap `docs/logs/jev-learnings.md`; rwxmap `docs/logs/learnings.md` lines 4126, 4446, 4820, 4886.

- Send five fields only: method, path, operationId, summary, description. Never a verdict. Naming the tool's verdict anchors Jev toward w.
- Read p from `answers.<key>.noul`. Record the response's model string.
- Keep two separate yes/no questions. One 3-way run leaked 20.6% on a clean exam (x recall 47.8%).
- Use different criteria per method. The full isX criteria (~2,190 tokens) say "PUT and PATCH are w", so 1,544 of 1,657 PUT/PATCH rows landed under p=0.1. The x-only criteria (`criteria-x-raise.mjs`, 743 tokens) fix that.
- Jev is not repeatable: the same 200 rows asked twice gave 114 different answers (largest gap 0.08, 3 crossed a 0.6 cut). Hence the re-ask rule.
- A threshold is valid only for the client it was swept on. Hence rwxlite tunes its own.
- Rows with no description give weak signal.
- Keeping only agreed rows biases training to easy rows. Hence the PRD trains on all rows.
- Price: $42 per billion input tokens, about $0.000085 per answer.

### The a7bc855 fix

Both questions shipped in rwxmap at v0.4.0 to v0.8.0 were wrong:
- jev-raise-wx sent the full loaded isX criteria instead of the x-only raise criteria.
- jev-raise-get reused the isX w-side list; it differed from `criteria-changes.mjs` in 5 places.

Fixed on rwxmap branch `fix/jev-raise-wx-criteria`, commit a7bc855 (D127), unreleased. rwxlite takes its questions from the three poc files at that commit, byte for byte. The working-tree copies were confirmed identical to the commit.

## 2026-11-03: M0 step 2 smoke run (Jev labelling)

Source: `m0/jev-label.mjs --smoke`, output `data/m0/jev-smoke.jsonl` (gitignored).

- 30 rows (10 GET changes, 10 POST isX, 10 PUT/PATCH isX): 0 errors, all p values parsed.
- Cost $0.0025 for 30 answers = $0.000082 each, on the $0.000085 estimate (billed on input tokens only; about 2,080 tokens per GET, 2,620 per POST, 1,150 per PUT/PATCH).
- Answers look sane against mechanical letters: GET rows mostly p 0.01-0.03; POST `publishMessagesToChannel` 0.95 and `post-deleteShareholders` 0.96 (mechanical x); PUT/PATCH rows all low (0.01-0.35). Odd ones: GET `firstData` 0.74, POST `registerPushDevice` 0.07 under mechanical floor-post x (these are the cases Jev is expected to disagree on).
- Surprise: the response model string is `jev-1.14.0`, not the `jev-1.13.0` the rwxmap learnings recorded. Thresholds from rwxmap were swept on 1.13.0, which is another reason rwxlite tunes its own.
- Rows skipped with no Jev call: 13,273 DELETE, 19 `exam_opkey_overlap`, 203 other methods (HEAD 114, OPTIONS 84, TRACE 5). 0 exam/locked-vendor rows (none in the corpus). Rows to ask: 109,844.
- Full pass 1 started right after: about 1,300 rows/min, projected about 85 minutes and about $10.4.

## 2026-11-03: M0 step 3, parity report and 95% label gate

Source: `m0/parity.mjs` (no network), output `data/m0/parity-report.json` (gitignored). Jev data checks: 109,844 first asks and 14,188 re-asks, 0 errors, every answer from model `jev-1.14.0`, total spend $11.44. Where a row was asked twice, p is the average of the two asks.

### Verdict: the 95% label gate FAILS

Scored against hand labels and calibration labels outside the exam (hand_set 1,152 + calib_set 547 = 1,699 rows; 2 rows with a "?" label dropped; 0 exam-vendor rows, asserted). Exam never touched.

| Labels | Rows | Exact | Too loose | Too tight |
|---|---|---|---|---|
| mechanical alone | 1,699 | 55.5% | 4.8% | 39.7% |
| mechanical + Jev at rwxmap's cuts (0.10 / 0.80 / 0.50) | 1,699 | 54.6% | 7.2% | 38.1% |
| mechanical + Jev, tuned cuts (budget rule, below) | 1,699 | 56.9% | 2.8% | 40.3% |
| same, only rows in a Jev pile | 850 | 87.6% | 4.6% | 7.8% |
| same, only non-DELETE rows | 885 | 86.6% | 5.3% | 8.1% |

Even the best case (pile rows only) is 87.6%, about 7 points short of 95%.

**Where the misses are**
- The biggest cause is not Jev. 814 of the 1,699 gate rows are DELETE. The PRD keeps DELETE at mechanical x, but the hand labels call 70% of those w (hand_set: 384 w, 168 x of 552; calib_set: 229 w, 33 x of 262). Mechanical is 24.7% exact on DELETE, 75% too tight. These rows never get a Jev p, so nothing in the pipeline can fix them.
- Tier exact at rwxmap's cuts: raise-wx (558 rows) 91.6% (8.2% too loose); raise-get (127) 89.8% (10.2% too loose); lower (165) 49.1% (33.9% too loose). Mechanical alone on those: raise-wx 89.8%, raise-get 86.6%, lower 66.7%.
- The lower tier is the problem inside the piles. On this label set floor-post POST is 110 x / 55 w, and Jev p under 0.10 picks the wrong rows: at 0.10 it moves 56 true-x rows to w. Lowering never beats "do not lower" below 0.03.
- raise-wx: moving w to x only helps a little. Best cut 0.60 (520 exact, 26 loose, 12 tight vs 501 / 57 / 0 for no raising). The 57 true-x rows that mechanical calls w are mostly still missed.
- raise-get: raising r to w gains 4 rows and loses none at any cut from 0.2 to 0.9 (114 exact vs 110); the 13 loose rows are GET rows whose truth is x that Jev does not catch (example: slack `/rtm.connect`, no summary, p 0.655, truth x).
- Example misses (tuned budget cuts): ably `DELETE /push/deviceRegistrations` mech x, truth w; github `DELETE /repos/.../autolinks/{id}` mech x, truth w; github `DELETE /user/starred/{owner}/{repo}` mech x, truth w; clicksend `PUT /sms/cancel-all` mech x/cant-undo-verb, p 0.70, truth w; powerdns `PUT /servers/{id}/cache/flush` mech w, p 0.92 -> x, truth w; slack `GET /rtm.connect` mech r, p 0.655 -> w, truth x. Full list of 10 in the JSON.

### Tuned thresholds

Two rules, both swept on the 1,699 rows:
- "Minimise too-loose first" (rwxmap's literal method) degenerates: lower 0.03, raise-wx 0.50, raise-get 0.20 -> 54.9% exact, 2.6% loose. It mostly switches the lowering off.
- "Budget": best exact subject to too-loose no worse than mechanical's: lower 0.03, raise-wx 0.60, raise-get 0.20 -> 56.9% exact, 2.8% loose.
- Leave-one-vendor-out (224 vendors, tune on the rest, score the held-out vendor): lexi 54.9% exact / 2.6% loose; budget 55.9% / 3.8% loose. Chosen cuts were stable (lower 0 to 0.03, raise-wx 0.5 to 0.8, raise-get always 0.2). The cuts are stable but the gain over mechanical is small.
- Caveat: tuning data is only 165 / 558 / 127 rows per tier, and the hand sets are not a random sample of the corpus (DELETE-heavy, vendor-clustered).

### Wobble (14,188 re-asked rows, p between 0.1 and 0.9 the first time)

| Gap between the two asks | Rows |
|---|---|
| identical | 2,476 (17.5%) |
| up to 0.02 | 7,453 |
| 0.02 to 0.05 | 3,515 |
| 0.05 to 0.10 | 701 |
| 0.10 to 0.20 | 43 (max 0.17) |

- 82.5% differ at all (rwxmap: 114 of 200 = 57%, but those were rows of all p). Mean gap 0.020, median 0.02, 90th percentile 0.04.
- Rows whose two asks land on different sides of a cut, any row: 753 at 0.10, 286 at 0.50, 136 at 0.80. At each row's own rwxmap cut (x rows 0.10, w rows 0.80, r and GET 0.50): 607.
- Drop candidates (pile rows whose two asks straddle the tier cut): 591 at rwxmap's cuts; 59 at the tuned budget cuts (the tuned cuts sit outside the busy zone). That is 0.5% of rows or less, so dropping them costs nothing.

### Parity report (Jev vs mechanical at rwxmap's cuts, all 102,552 pile rows plus 7,292 outside)

"Disagree" = Jev's p would move the letter (x: p under 0.10; w: p at or over 0.80; r/GET: changes at or over 0.50).

| Pile | Rows | Would move | Rate |
|---|---|---|---|
| lower (POST floor-post x) | 27,656 | 16,224 | 58.7% |
| raise-wx (PUT/PATCH w) | 15,126 | 137 | 0.9% |
| raise-get (GET r) | 59,770 | 1,307 | 2.2% |

- Lower disagrees 58.7% of the time: 16,224 of 27,656 POST rows come back under 0.10. This is the same pattern seen in the hand labels: Jev says "not x" far more often than the hand labels do. Treat Jev's p on POST as the weakest of the three.
- Outside the piles (report only): POST x/cant-undo-verb 3.4% disagree (1,979 rows), POST w/modify-verb 1.9% (2,135), POST r/read-verb 0.3% (2,686), PUT/PATCH x/cant-undo-verb 8 to 10% (134 rows), POST x/cant-undo-verb-summary 14.9% (47). Mechanical's word-based rules agree with Jev almost everywhere.
- Deciles of p are in the JSON; GET is 97% in the lowest decile, raise-wx 89%, POST floor-post 59% lowest decile and 5% highest.
- By vendor (min 50 rows; 25 listed in the JSON): by count microsoft.com 4,437 of 29,556 (15%), amazonaws.com 4,080 of 12,519 (32.6%), googleapis.com 1,383 of 5,429 (25.5%), github.com 1,284 of 12,275 (10.5%), azure.com 647 (9.2%), autotask.net 613 (21.6%). By rate: portfoliooptimizer.io 78%, plaid.com 59%, epa.gov 42%, slack.com 39%, sinao.app 35%. The big clouds dominate because they carry most POST rows.

### No-description rows

39,085 rows in the corpus have no description; 32,608 of them were asked. Their p is not weaker: mean distance from the cut 0.46 vs 0.43 with a description, only 8.4% fall in the unsure zone (0.1 to 0.9) vs 14.0%, and they disagree with mechanical 14.9% vs 16.7%. They are more confident, not less (probably because they are short, mostly bare GETs).

### Mode (b) standalone, reported only

On the gate rows that Jev was asked about, p alone at a 0.5 cut, as a yes/no: GET changes (r vs not-r) 99.2% right (127 rows, but few are non-r); PUT/PATCH isX (x vs not-x) 86.7% (566 rows; mechanical letter alone is 88.9% exact); POST isX 46.9% (192 rows; mechanical letter alone 67.2%). So POST isX is not usable standalone.

### Proposed PRD contract changes (for the user to sign off, PRD not edited)

1. DELETE: "skip Jev, keep mechanical x" fails the hand labels (70% of 814 DELETE gate rows are w). Options: (a) ask Jev a question on DELETE too (costs about $1.1 for 13k rows) or (b) accept that the gate is measured on pile rows only and say so, or (c) review the hand-label standard for DELETE.
2. Gate wording: "at least 95% correct against the hand labels" cannot be met at all by mechanical (84.8% on pile rows) or by Jev moves (87.6%). The contract needs either a different measure (for example, "labels no worse than mechanical on too-loose, and better on exact, per tier") or a decision to fix the lower tier first.
3. Lower tier: Jev's isX under 0.10 on POST is wrong more often than right on the hand labels at rwxmap's cut. Propose the first model does not train the lower move from Jev p alone (keep mechanical x unless p under 0.03), or the lower tier gets a re-check on the full hand-labelled POST rows.
4. The PRD's tuning rule "leave-one-vendor-out, minimise too-loose first" collapses to "never move"; proposed wording: "maximise exact subject to too-loose no worse than mechanical".

## 2026-11-03: M0 step 3b, gate re-scored on BRIEF-v3 labels

Source: `node m0/parity.mjs --truth v3` (no network, no paid calls), output `data/m0/parity-report-v3.json` (gitignored). The v1 run (`node m0/parity.mjs`) is unchanged and byte-identical to before. Exam `data/exam-2026-09-22` never read.

### What the v1 mismatch was

Step 3 scored against `data/corpus/labelled.csv` (2026-09-16) and the calibration-2026-09-14 labels, both made under rwxmap's BRIEF v1. The exam and Jev's questions follow BRIEF-v3 (D87, adopted 2026-09-22; amended by D98), where DELETE is x (except trash/recoverable wording) and plain POST creates are w. v3 is bidirectional against v1: rwxmap moved 777 of 803 DELETE rows w to x and 930 POST rows x to w on the combined set, and 943 of 1,819 buildset rows (51.8%). So step 3's 70%-w DELETE "failure" and its "Jev lowers the wrong POST rows" were a standard mismatch, not a classifier fault.

### v3 truth source (reused, not rebuilt)

rwxmap already assembled it. Two flat files, both TUNING DATA (D24):
- `data/combined-2026-09-21/labelled.csv` (`tools/make-combined-labelled.js`): 6,557 rows, 23 providers. v1 r labels stand; each non-r row takes its BRIEF-v3 label from nine blind labellers (`data/relabel-2026-09-22/label/labels-*.csv`), with `rulings.csv` (4 abstentions ruled x) overriding. Practice/holdback calibration rows are inside it. Sources: `pc-` tuning corpus, `x17-`/`x20-` burned exams. Per rwxmap's README no number over these rows is a generalization claim.
- `data/relabel-buildset-2026-09-23/labelled.csv` (`tools/make-buildset-v3-labelled.js`): 1,819 rows, 13 APIs.guru vendors (github, microsoft, gitea, appcenter, netbox, clearblade, keycloak, atlassian, dracoon, trello, box, gitlab, launchdarkly), relabelled under v3 (D97), D98 comment/reaction correction already applied (w 1,130 / x 646 / r 43). Also tuning data: step 2's word lists were mined on it.
- No other v3-standard non-exam labels exist in rwxmap (the exam-2026-09-22 labels are the burned exam; not read). Both files are single-labeller-per-row; there is no second labeller outside the 200-row calibration draws, so label noise is unmeasured here (391 combined and the buildset's low-confidence rows are flagged; dropping them is the `high_confidence_only` set in the JSON).

### Join

Key: provider + method + path + operationId against `mechanical.jsonl.gz`. The combined set uses bare vendor names, so an explicit map was used (stripe.com, squareup.com, zoom.us, jira.local, ...); buildset vendors match by bare name.
- 8,376 truth rows, 3,724 joined (44.5%): buildset 1,819 of 1,819, combined 1,905 of 6,557.
- Unjoined combined rows: 1,995 are vendors not in the APIs.guru corpus at all (paypal, mailchimp, datadog, intercom, canva, figma, auth0, hubspot, klaviyo, miro, zendesk); 2,657 are vendors present where the operation is absent (official spec vs APIs.guru snapshot differ in path/operationId; jira 0 of 610, okta 2 of 734, openai 17 of 346, stripe 441 of 594, ...).
- 3,724 truth rows map to 5,716 mechanical rows because APIs.guru holds several snapshots/versions of the same operation (316 keys joined to 2+ rows, e.g. github). All 5,716 are scored. No mechanical row matched two truth rows.
- Asserted: zero rows from cloudflare, pagerduty, sentry, nor the other 7 locked vendors (auth0, hubspot, zendesk, miro, dropbox, shopify, linear); none of them exist in the mechanical file. `exam` flag false on all; 1 row dropped for `exam_opkey_overlap`. Docusign/okta/xero (burned exam x17) and asana..zoom (tuning corpus) are included as tuning data, as the relabel README allows.
- Gate composition: 5,716 rows = buildset 3,726 + combined 1,990 (pc- 1,380, burned x17/x20 610); 375 of them were also in the v1 gate. Tiers: lower 1,641, raise-wx 1,486, raise-get 959, no pile 1,630 (of which DELETE 1,364). It is write-heavy and github/microsoft-heavy, not a random sample of the corpus.

### Sanity check

Mechanical alone: 76.3% exact / 1.3% too loose / 22.3% too tight (v1 labels: 55.5%). Closer to the exam's 82.3 / 0.8 / 16.9 but not equal, for identifiable reasons: DELETE is now 99.3% exact (v1: 24.7%); by source mechanical is buildset 72.7%, pc- 80.9%, burned x17/x20 88.2%. The buildset (65% of rows) is where step 2's lists were mined against v1 labels that v3 then changed on 51.8% of rows, and POST floor-post is x in mechanical but w in 71% of v3 truth (24.3% exact). Nothing indicates a join or scoring bug.

### Verdict: the 95% gate still FAILS on honest numbers, but narrowly, and the cause is now tuning, not labels

| Labels | Rows | Exact | Too loose | Too tight |
|---|---|---|---|---|
| mechanical alone | 5,716 | 76.3% | 1.3% | 22.3% |
| mechanical + Jev, rwxmap cuts (0.10 / 0.80 / 0.50) | 5,716 | 92.6% | 1.3% | 6.1% |
| tuned, per-tier budget rule (0.03 / 0.60 / 0.20) | 5,716 | 77.2% | 0.4% | 22.4% |
| tuned, rwxmap's min-too-loose rule (0.03 / 0.50 / 0.20) | 5,716 | 76.6% | 0.3% | 23.1% |
| tuned, global budget (0.20 / 0.60 / 0.20), in sample | 5,716 | 95.5% | 1.2% | 3.3% |
| same, leave-one-vendor-out (23 vendors) | 5,716 | 94.0% | 0.9% | 5.0% |

- Per-tier budget rule degenerates: mechanical's lower tier has 0 too-loose rows under v3, so "no worse than mechanical" forces lower to 0.03 (switched off). A budget on total too-loose across the three cuts (max exact s.t. total too-loose at most mechanical's 77) gives lower 0.20. Both are reported; the global one is the sensible reading but is a new rule (see proposals). Chosen cuts under LOVO were stable: lower 0.1 to 0.3, raise-wx 0.6, raise-get 0.2.
- Per tier at rwxmap cuts (exact / loose / tight): lower 80.3 / 0.5 / 19.2 (n 1,641; mechanical 24.3 / 0 / 75.7); raise-wx 95.9 / 4.0 / 0.1 (n 1,486; mechanical 95.2 / 4.8 / 0.1); raise-get 100 / 0 / 0 (n 959); no pile 97.7 / 0.4 / 2.0 (n 1,630). At the global-budget cuts: lower 88.0 / 2.7 / 9.3, raise-wx 98.4 / 1.2 / 0.4.
- DELETE vs non-DELETE (rwxmap cuts): DELETE 99.3% exact (1,364 rows, all kept mechanical x; 9 of them truth w). Non-DELETE 90.5 / 1.7 / 7.8 (mechanical alone 69.1). Pile-only rows (4,086): mechanical 67.8, rwxmap 90.6 / 1.6 / 7.8, global-budget 94.6 / 1.5 / 3.9. DELETE no longer needs Jev.
- Mode (b), p alone at 0.5, reported only: GET changes 100% (959); PUT/PATCH isX 95.8% (1,503; mechanical letter 94.5%); POST isX 91.9% (1,890; mechanical letter 33.3%). Under v1 labels this was 46.9% for POST.
- Sweeps: lower tier exact peaks at cut about 0.30 (1,467 of 1,641 exact, 58 loose); 0.10 gives 1,318 / 8 loose. raise-get cuts change nothing (all 959 are r). raise-wx best at 0.60 (1,462 exact, 18 loose, 6 tight).

### Is the lower tier weak? No, the v1 labels made it look weak

Jev says not-x (p under 0.5) on 1,360 of 1,641 POST floor-post rows (83%); v3 truth is x on only 399 (24%), w 1,165, r 77. So Jev's not-x is right: it agrees with v3 on 1,231 of the 1,242 non-x rows. It misses 129 of 399 true-x rows (32%). At rwxmap's 0.10 cut it lowers 31 true-x rows wrongly and leaves 315 w/r rows at x (p between 0.10 and 0.5), the 19.2% too tight. The fix is a higher lower cut (0.2 to 0.3), at the price of more too-loose (rwxmap's own range).

Lower-tier misses, 10 examples at global-budget cuts (lower 0.20), mechanical x/floor-post:
- appcenter POST `.../analytics/audiences/definition/test`, no summary, p 0.09 (lowered to w), truth r
- asana POST `/webhooks` "Establish a webhook", p 0.23 (kept x), truth w
- digitalocean POST `/v2/apps/{app_id}/rollback/revert` "Revert App Rollback", p 0.145 (lowered), truth x
- dracoon POST `/v4/nodes/rooms/{room_id}/keypairs` "Create key pair and preserve copy of old private key", p 0.23, truth w
- github POST `/repos/{owner}/{repo}/transfer` "Transfer a repository", p 0.18 (lowered), truth x (two snapshots)
- github POST `/applications/{client_id}/token` "Check a token", p 0.125 (lowered to w), truth r
- microsoft POST `/devices/{device-id}/microsoft.graph.getMemberObjects` "Invoke action getMemberObjects", p 0.05, truth r
- microsoft POST `.../calendarView/{event-id}/instances/.../tentativelyAccept` "Invoke action tentativelyAccept", p 0.14 (lowered), truth x
- spotify POST `/me/player/next` "Skip To Next", p 0.345 (kept x), truth w
- Also from the rwxmap-cut list: asana POST `/tasks/{task_gid}/stories` "Create a story on a task" p 0.04, squareup `/v2/cards/{card_id}/disable` p 0.08, stripe POST `/v1/payment_intents` (no summary) p 0.09, all truth x, all lowered wrongly.
The true-x misses are sends/transfers/state actions with ordinary-sounding create/invoke summaries; the r and w misses are check/read-by-POST and plain creates. This is the lowering error band, not a systematic failure.

### Caveats

- Everything here is tuning data (including burned exams x17-/x20-); no number is a generalization claim. In particular the cuts are tuned and scored on the same 5,716 rows; LOVO is the honest estimate (94.0 / 0.9).
- Rows are write-heavy: the buildset has no GETs, and 24% of the gate is DELETE at 99% exact, which lifts every overall number. Pile-only and non-DELETE rows are the harder measure (90.6 and 90.5 at rwxmap cuts, 94.6 and 94.3 at the global-budget cuts).
- Single labeller per row; v3 truth has its own noise (391 low-confidence combined rows, an unknown count in the buildset). The 316 duplicate APIs.guru snapshots weight github-type operations more than once.
- Whole-corpus parity numbers (58.7% of lower-tier rows at p under 0.10) from step 3 stand; they are label-independent. What changes is their reading: Jev disagrees with mechanical x there because v3 truth is mostly w.

### Proposed PRD contract changes (PRD not edited)

1. Label standard: state that gate/tuning labels are BRIEF-v3 (D87 + D98) and name the source files above. v1 labels must not be used for the gate.
2. DELETE: keep "skip Jev, keep mechanical x". Under v3 it is 99.3% exact on 1,364 rows. Drop the step-3 option of asking Jev about DELETE.
3. Gate wording: measure on non-DELETE (or pile-only) rows and report overall too; require 95% exact with total too-loose no worse than mechanical's, judged on leave-one-vendor-out, not in-sample. Current best LOVO is 94.0%, so either more tuning/labels or a 94% bar is needed, a user call.
4. Tuning rule: replace "leave-one-vendor-out, minimise too-loose first" (collapses to never move) and the per-tier budget (collapses to lower 0.03 when a tier's mechanical too-loose is 0) with "max exact subject to total too-loose across all tiers no worse than mechanical alone". Starting cuts: lower 0.20, raise-wx 0.60, raise-get 0.20 (or keep raise-get off; it changes nothing on this set).
5. Lower tier: keep it, with its cut near 0.20 (not 0.10); do not drop it. The v1-based proposal to keep mechanical x unless p under 0.03 should be withdrawn.
6. Add a note that the gate set is tuning data with 65% buildset rows and duplicate snapshots; a fresh v3-labelled sample drawn from the full APIs.guru corpus (non-DELETE, stratified by tier) would give an honest gate.

## 2026-11-03: Fresh v3 gate scored (once)

Source: `m0/gate-score.mjs`, `data/gate-2026-11-03/score.json`. Truth: two blind labellers, 588/600 agreed (98%), user ruled the other 12 (`rulings.csv`). Sample is now burned.

**Verdict: FAIL.** Jev-derived labels at the PRD cuts (lower 0.20 / raise-wx 0.60 / raise-get 0.20) are 90.8% exact on all 600 (90.0% on the 472 vendor-clean rows, see correction below). The bar is 95%, so the cause goes back to the PRD; the bar is not loosened. Too-loose is 7 (1.2%), better than mechanical alone (13, 2.2%), so the safety half of the contract holds; the failure is all too-tight (48 rows, 8.0%).

| config (all 600) | exact | too loose | too tight |
|---|---|---|---|
| mechanical alone | 76.5% | 13 (2.2%) | 128 (21.3%) |
| mechanical + Jev, PRD cuts (the gate) | 90.8% | 7 (1.2%) | 48 (8.0%) |
| mechanical + Jev, rwxmap cuts 0.10/0.80/0.50 | 88.5% | 8 (1.3%) | 61 (10.2%) |
| Jev mode (b) alone, p 0.5 | 89.8% | 10 (1.7%) | 51 (8.5%) |

Vendor-clean line (472 rows; corrected 2026-11-03: the earlier 523-row line used a 14-name list, rwxmap's fuller 24-name list leaves 472): mechanical 75.4% exact / 13 too-loose / 103 too-tight; rwxmap cuts 87.9 / 8 / 49; rwxlite (PRD) cuts 90.0 / 7 / 40; Jev mode (b) alone 89.2 / 10 / 41.

Gate line by tier (all 600): raise-get 325 rows 100% exact; raise-wx 97 rows 94.8% (5 too loose); lower 145 rows 68.3% (2 too loose, 44 too tight; mechanical alone 14.5%); no pile 33 rows 87.9% (4 too tight). By method: GET 100%, PATCH 96%, PUT 90%, POST 72.6%.

Where the 55 misses are (PRD cuts): 
- 46 lower-tier POST rows left or put wrong: 44 too tight, mostly read-by-POST (query, get, list, retrieve: autotask `/query`, plaid `/get`, azure `/list*`/`getX`, apisetu certificate lookups) where Jev p sits at 0.04 to 0.20, plus a few at p 0.2 to 0.5 (a "download", "start", "burntoken", "enrich", "markdown") that stay x. Truth is r (about 36 of them). Mechanical floor-post x is simply a bad prior for POST in this corpus, and Jev's 0.20 cut still leaves the 0.20 to 0.50 band at x.
- Genuine w kept at x (p 0.2 to 0.57): deregister, restart, transferJobs create, SyncPlay ready, feedback; these were the user's rulings on borderline cases.
- Too loose, 7 rows: 2 in lower (addMessage p 0.115, mist support-files upload p 0.12, truth x) and 5 password/credential PUT/PATCH in raise-wx at p 0.04 to 0.49 (letmc, kubernetes node proxy, blazemeter, britbox pin, kumpeapps authkey; truth x).
- No-pile x rows (cant-undo-verb) with truth w: unsubscribe, approve, start, complete-registration (4 too tight). The PRD cuts do not touch these (Jev has p for 33 of them but no cut is defined).

Post-hoc, NOT for tuning (sample is burned; this explains the number, it must not choose cuts): within the lower tier, moving the cut from 0.20 to 0.30 would add 4 exact rows and 0.40 to 0.50 would trade them for more too-loose; the tier ceiling is about 71% exact (about 103 of 145) at any cut because the true-r POST rows with p above 0.2 are not separable by p. raise-wx at 0.5 to 0.6 is flat; raise-get is flat (325/325). So no cut alone reaches 95%; the lower tier is the problem, not the threshold.

## 2026-11-03: Two-step POST lower + credential rule (tuning)

Source: `m0/parity.mjs --truth v3` (ROUND6 block, `data/m0/parity-report-v3.json`), `m0/jev-label.mjs --question changes --methods POST`. Tuning data only: the 5,716 joined v3 rows (23 vendors). Neither gate sample nor the exam is read.

**Paid pass.** The "changes" question (`m0/questions/criteria-changes.mjs`, byte-identical to rwxmap a7bc855) was asked on all 34,800 non-DELETE POST rows (not the ~28-30k estimated; 19 `exam_opkey_overlap` rows excluded, no exam/locked vendors present), then re-asked on 2,981 rows with p in 0.1..0.9. Zero errors. Smoke 20 rows: 0 errors, $0.0000887 per answer (target 0.000085). Spend this step $3.39; cumulative $14.83 of the $45 stop ($50 cap). Concurrency 8, about 2,400 rows/min.

**Rule.** POST x row in the lower tier: if isX p < lower cut then (changes p < r cut -> r, else w), else x stays. r cut grid 0, .02, .03, .05, .07, .1, .15, .2, .3, .4, .5. Tuned by the global-budget rule (max exact s.t. total too-loose no worse than mechanical), leave-one-vendor-out (23 folds).

**Tuned r cut: 0.20** (all-data fit and LOVO median); LOVO range 0.15 to 0.40. Other cuts unchanged: lower 0.20 (LOVO 0.10 to 0.30), raise-wx 0.60, raise-get 0.20. The lower tier is 1,641 rows, all POST.

**Credential rule.** x when a non-GET operation (operationId, summary or path, camelCase split) has change/reset/rotate/regenerate/renew/revoke/invalidate/expire within 3 words before password, passcode, passphrase, PIN, auth key, API key/secret, secret key or client secret; not when followed by policy/rule/requirement/setting/config. It does not match create/issue/login token or session. Per BRIEF-v3 clause (b). First draft hit "Change password policies" (truth w); excluded as a policy, not a credential. Final narrow rule: 9 hits (6 PUT, 3 POST), truth all x. At the all-data tuned cuts: exact +4, -0, too-loose -4, too-tight +0. Wider variants (add description text, or update/set/replace) hit 11 to 12 rows and change nothing. Applied: adds no too-loose and gains net. Only 9 hits, so it is small; the gain beyond 4 rows in the LOVO table below is mostly budget reallocation (4 freed too-loose rows let the lower cut rise), not 9 rows.

**LOVO, global budget (5,716 rows; mechanical alone 76.3 / 1.3 / 22.3):**

| config | exact | too loose | too tight |
|---|---|---|---|
| before: one-step lower | 5374 (94.0%) | 54 (0.9%) | 288 (5.0%) |
| two-step lower | 5410 (94.6%) | 54 (0.9%) | 252 (4.4%) |
| one-step + credential | 5422 (94.9%) | 58 (1.0%) | 236 (4.1%) |
| two-step + credential | 5475 (95.8%) | 58 (1.0%) | 183 (3.2%) |

Non-DELETE rows (4,352): before 92.3%, two-step 93.2%, two-step + credential 94.7% (too-loose 54, 54, 58).

By tier, before -> two-step + credential (exact / too-loose / too-tight):
- lower (1,641): 1361 / 30 / 250 (82.9%) -> 1458 / 38 / 145 (88.8%)
- raise-wx (1,486): 1462 / 18 / 6 (98.4%) -> 1466 / 14 / 6 (98.7%)
- raise-get (959): 959 / 0 / 0 (100%), unchanged
- no pile, DELETE (1,364): 1355 / 0 / 9 (99.3%), unchanged
- no pile, other (266): 237 / 6 / 23 (89.1%), unchanged

Reading. The two-step lower alone adds 0.6 point; credential rule and budget reallocation add 1.2 more. The mechanical-only contract line holds (total too-loose 58 vs 77 mechanical). 95.8% on tuning data is optimistic by construction; the 95% bar is measured on gate-2 (`data/gate-2026-11-04/`, drawn, not labelled). The lower tier (88.8%) and the no-pile non-DELETE rows (89.1%, no cut defined) remain the weak spots.

## 2026-11-03: Gate-2 scored (once)

Source: `m0/gate-score.mjs --gate 2026-11-04`, `data/gate-2026-11-04/score.json`. Truth: two blind labellers (BRIEF-v3, high/low confidence only), 590/600 agreed (98.3%), user ruled the other 10 (`rulings.csv`). Truth mix r 353 / w 204 / x 43. Sample is now burned. Gate-1 outputs were not rewritten; the generalised scorer reproduces them byte for byte when run into a temp path.

**Verdict: PASS.** The round-6 recipe (lower 0.20, POST two-step r cut 0.20 on the changes p, raise-wx 0.60, raise-get 0.20, narrow credential rule) is 96.5% exact on all 600 (579 rows; bar 95%). Too-loose is 4 (0.7%), no worse than mechanical alone (7). Recipe was fixed before scoring; nothing was tuned on this set.

| config | all 600: exact / too-loose / too-tight | vendor-clean 483: exact / too-loose / too-tight |
|---|---|---|
| (i) mechanical alone | 79.3% / 7 / 117 | 77.8% / 7 / 100 |
| (ii) round-6 recipe (THE GATE) | 96.5% / 4 / 17 | 95.9% / 4 / 16 |
| (iii) round-5 (no two-step, no credential rule), 0.20/0.60/0.20 | 93.2% / 4 / 37 | 92.3% / 4 / 33 |
| (iv) rwxmap shipped, 0.10/0.80/0.50, one-step | 91.5% / 3 / 48 | 90.3% / 3 / 44 |
| (v) Jev mode (b) at 0.5 | 92.0% / 11 / 37 | 91.5% / 9 / 32 |

Vendor-clean excludes the 24 rwxmap-tuning names (adyen ... zoom), 483 rows here.

(ii) by tier, all 600 (exact / too-loose / too-tight): lower 142 (all POST) 93.0% / 1 / 9 (mechanical 21.1%); raise-wx 100 rows 99.0% / 1 / 0; raise-get 325 rows 98.5% / 2 / 3; no pile 33 rows 84.8% / 0 / 5. By mechanical letter: r 334 98.5%, w 110 98.2%, x 156 91.0%. By method: GET 98.5, PUT 100, PATCH 98, POST 91.4.

**Two-step hits: 20 rows** (lower-tier POST with isX p < 0.20 and changes p < 0.20), all truth r, all gained (round-5 would label them w). Effect +20 exact, too-loose unchanged. **Credential rule hits: 0** on this set (no effect; the gate-1/tuning-set rule did not fire, so it is neither confirmed nor refuted here). The round-6 gain over round-5 (+20 rows, 3.3 points) is entirely the two-step.

**The 21 misses of (ii), by pattern:**
- 9 POST x kept as x, truth w (too-tight): 5 in the lower tier (p 0.24 to 0.6 with changes p high: code-references, Tokens writeCodespaces, hetzner create Certificate, magento increaseBalance, contract-p /auth login) and 4 outside any pile (cant-undo-verb: requestPasswordReset, azure StartTransition, mist locate, mandrill cancel-warmup). Separately 1 POST w with truth r outside any pile (pdfblocks remove_restrictions).
- 4 POST read-by-POST in the lower tier: 2 kept x (zuora billing preview, quickchart /qr, truth r; the first is the user's preview ruling) and 2 sent to w instead of r (plaid precheck, taggun validate; changes p 0.83 and 0.32 above the 0.20 cut).
- 3 GET raise-get false raises (truth r, predicted w): GET `/validate`, GET `/sms/send` summary "send", GET tokenburn (name alone, user ruling).
- 2 GET raise-get truth x (too-loose): AWS GET `/#Action=DeleteNotificationConfiguration` (p 0.97) and smart-me GET FastSendDeviceValues; the raise-get cut sends them to w, not x.
- 2 other too-loose: orthanc POST /tools/shutdown (lower tier p 0.16, truth x, now w); kumpeapps PATCH `/appkey` "Compromise app key" (raise-wx p 0.295, truth x; the credential rule did not match).

Post-hoc, NOT for tuning (sample is burned): in the lower tier raising the isX cut from 0.20 to 0.30 would add 1 exact and 2 too-loose; the r cut is flat from 0.05 to 0.30 (132/142); raise-get at 0.30 to 0.50 would add 1 to 3 exact with no new too-loose. None of this selects cuts.

Also corrected: gate-1's vendor-clean line is 472 rows (see the gate-1 entry above), not 523.

## 2026-11-03: M0 step 4, training pipeline, TF-IDF baseline, MiniLM first run

Code: `train/common.py`, `train/build_dataset.py`, `train/baseline.py`, `train/finetune.py`. Outputs in `data/train/` (gitignored). Rebuilt on the ROUND-6 recipe (cuts 0.20 / 0.60 / 0.20; POST x rows lowered by isX get r if the averaged POST-changes p is under 0.20, else w; narrow credential rule gives x; DELETE x) after the label gate passed. Excluded from train and val: exam vendors and locked vendors, the 19 exam_opkey_overlap rows, every id in gate-1 and gate-2 `ids.txt` (1,481), and all 5,716 rows joined to v3 truth. No gate labels, exam data or v1 labels read.

### Dataset
- Input string: `lean: <letter> <rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>`. Leaning first so truncation never cuts it; HTML stripped; summary cut at 200 chars, description at 400; empty fields omitted.
- 123,339 mechanical rows -> 87,657 train + 4,180 val (66 of 664 vendors in val, seed 20261103, split by vendor = first dotted token of provider). Dropped: 23,790 duplicate snapshots (provider+method+path+operationId, one kept), 201 non-asked non-DELETE (HEAD etc.), 295 wobble rows that straddle their tier cut (the POST-changes asks were not used for wobble), 1,481 gate ids, 5,716 v3-eval rows.
- Train label balance: r 47,841 (54.6%), w 24,161 (27.6%), x 15,655 (17.9%). Status: kept 62,486, moved by Jev 16,557, DELETE 8,548, credential rule 66. Val: r 2,432, w 1,154, x 594. Raw Jev p (jev_p, pA, pB) and POST-changes p (jev_pC) are stored per row for a soft-target variant.
- v3-truth eval: 5,716 rows (truth r 1,080, w 2,761, x 1,875), tier lower 1,641 / raise-wx 1,486 / raise-get 959 / none 1,630. The cuts were tuned on these rows, so read them as in-sample-ish. Other ops of the same vendors (github, microsoft) are still in train, so vendor style is not held out here.
- Mode (a) = model only makes Jev's moves on pile rows (mechanical in charge). Variants: `a_cuts` (model p(x) / p(w)+p(x) against the PRD cuts; lower goes to r if p(changes) < 0.20 else w) and `a_argmax` (move when the argmax agrees). Credential rule applied in both. Mode (b) = plain argmax.

### TF-IDF (word 1-2 + char_wb 3-5) + logistic regression, round-6 targets
- Val accuracy vs target 96.2%. Fit 232 s on a loaded machine. Pickle 24.4 MB. Inference 19.8 ms/op one at a time (vectorisers dominate), 2.1 ms/op batched.
- v3 truth, exact / too loose / too tight: mechanical 76.3 / 1.3 / 22.3; a_cuts 93.4 / 2.0 / 4.7; a_argmax 94.1 / 2.8 / 3.2; mode (b) 94.0 / 2.9 / 3.1. Non-DELETE: mechanical 69.1; a_cuts 91.5 / 2.6 / 5.9; a_argmax 92.4 / 3.7 / 4.0; b 92.3 / 3.7 / 3.9. DELETE 99.3 in every mode. Per tier at a_cuts: lower 83.3 / 2.6 / 14.1, raise-wx 95.6 / 4.2 / 0.1, raise-get 99.8, none 97.7. POST: mechanical 33.3, a_cuts 84.5, b 87.6.
- Too loose is the weak side: 2.0% at a_cuts against mechanical's 1.3%, so mode (a) as is would not meet "no worse than mechanical" on this set. Tuned model cuts, not the PRD's Jev cuts, are the next step (the model's p is not Jev's p).

### MiniLM (all-MiniLM-L6-v2 + 3-way head), CPU
- Token length of the string: median 66, p90 124, p95 140, 8% over 128; max_len 128 used (leaning is first, so only description tail is cut). 22.7M params, fp32 90.9 MB (int8 should land near a quarter of that; export is M1).
- The laptop was heavily shared with other jobs (load average 20-36 on 8 cores). Measured 0.2-0.46 steps/s at batch 32 (4-6 threads), i.e. 6-15 rows/s; a bare forward+backward on 32x80 tokens took 5-10 s at the worst. Batched inference under that load 52 ms/op; not a valid latency figure.
- Smoke (1,600 rows, 1 epoch, 50 steps, old pre-round-6 targets): val acc 94.25%; v3 a_argmax 89.7 / 8.3 / 1.9, b 89.3 / 9.1 / 1.6. Pipeline check only.
- Subsample run (36,000 rows, 1 epoch, 1,125 steps, old targets, log `data/train/finetune.log`, tag sub36k) was started before the recipe change and is kept only as a pipeline/timing check; its metrics are not round-6 results.
- Full round-6 epoch (87,657 rows = 2,740 steps): about 100 min at the best observed 0.46 step/s, about 3 h at 0.25 step/s. Two epochs: 3.5 to 6 h. Needs a quiet machine.
