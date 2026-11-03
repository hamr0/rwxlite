# Findings

See also: [classifier-training.md](classifier-training.md) (how the model is trained and how it answers)

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

## 2026-11-03: Baseline: own cuts (LOVO)

Code: `train/tune_cuts.py` (results in `data/train/tune-cuts-results.json`, gitignored). TF-IDF baseline from the step-4 entry (trained on rows that exclude every v3 row, so p on the 5,716 v3 tuning rows is out-of-sample w.r.t. training). Mode (a) recipe as round 6 with the model's p in place of Jev's: lower on isX = p(x), raise-wx on p(x), raise-get on changes = p(w)+p(x), POST two-step r cut on changes, narrow credential rule. Cuts picked by the PRD global-budget rule (max exact s.t. TOTAL too-loose <= mechanical's), leave-one-vendor-out: each of the 23 held-out vendors is scored with cuts chosen on the other 22. Grids are wider than parity.mjs (lower 0..0.8, raise-wx 0.02..1.01, raise-get 0.02..1.01, r cut 0..0.8), because the model's p is not Jev's. Calibration: one temperature T=1.274 fit on the val split (not v3).

### LOVO, exact / too loose / too tight (v3 tuning truth, n=5,716; loose rows in brackets)
| | all | non-DELETE | DELETE |
|---|---|---|---|
| mechanical | 76.3 / 1.3 / 22.3 (74) | 69.1 | 99.3 |
| Jev labels, own LOVO (round 6) | 95.8 / 1.0 / 3.2 | | |
| baseline PRD cuts (0.20/0.60/0.20, not tuned) | 93.4 / 2.0 / 4.7 | 91.5 / 2.6 / 5.9 | 99.3 |
| (a) own cuts, raw p | 89.8 / 1.3 / 8.9 (74) | 86.8 / 1.7 / 11.5 | 99.3 / 0.0 / 0.7 |
| (a) own cuts, temperature-calibrated p | **91.0 / 1.3 / 7.8 (74)** | 88.3 / 1.7 / 10.0 | 99.3 / 0.0 / 0.7 |
| (b) argmax + too-loose guard, raw | 87.9 / 1.0 / 11.2 (57) | 84.3 / 1.3 / 14.5 | 99.3 |
| (b) argmax + too-loose guard, calibrated | 88.3 / 1.0 / 10.7 (57) | 84.9 / 1.3 / 13.8 | 99.3 |
| (b) plain argmax, no guard | 94.0 / 2.9 / 3.1 (166) | 92.3 / 3.7 / 3.9 | 99.3 |

Per tier, mode (a) calibrated (exact / loose / tight): lower 79.3 / 3.5 / 17.2, raise-wx 90.6 / 0.7 / 8.7, raise-get 100.0 / 0.0 / 0.0, none-DELETE 99.3 / 0.0 / 0.7, none-other 89.1 / 2.3 / 8.6. Raw: lower 79.2 / 3.2 / 17.6, raise-wx 86.5 / 0.9 / 12.7, raise-get 99.9.

### Cuts
- Calibrated (on p after T=1.274), chosen on all 23 vendors: lower 0.40, r cut 0.20, raise-wx 0.10, raise-get 0.70. LOVO ranges over the 23 folds: lower 0.10 to 0.40, r cut 0.02 to 0.50, raise-wx 0.10 to 0.15, raise-get 0.70 (fixed).
- Raw p: lower 0.20, r cut 0.15, raise-wx 0.10, raise-get 0.80. LOVO ranges: lower 0.07 to 0.40, r cut 0.05 to 0.50, raise-wx 0.02 to 0.10, raise-get 0.70 to 0.80.
- Calibration helps stability: raise-wx and raise-get ranges collapse to nearly one value and exact rises 1.2 points, all of it in raise-wx (+4 points in that tier). The lower and r cuts stay loose (flat optimum); do not read them to two decimals.

### Verdicts (indicators only; the exam decides)
- Mode (a) with own calibrated cuts: too loose 74 rows = mechanical's 74 (budget met by construction under LOVO, held-out total equals mechanical's), exact 91.0, so it clears "too loose no worse than mechanical, exact >= 91" by 0.0 to 0.1 points. Thin: the 91 line is on the edge and 3 points under the Jev labels' 95.8.
- Why the PRD-cut run (93.4 / 2.0) is not simply better: it sits above the budget (2.0% vs 1.3% too loose). The budget costs about 2.4 exact points; where it costs is the lower tier (POST), which is also where the baseline is weakest (tight 17%, loose 3.5%).
- Mode (b) guarded argmax meets the budget on loose (1.0%, below mechanical) but only 88.3 exact. Plain argmax gets 94.0 but 2.9% too loose, which fails the budget. No cheap guard sits between them: the margin guard converts too-loose into too-tight at nearly 1:1 on the lower and raise-wx tiers. Mode (b) does not meet exact >= 91 under the budget.
- Mode (a) calibrated is the better option for the baseline.

### Latency (laptop, load average varied 3 to 25 during the work)
- Single op, full sklearn path: 5.8 to 6.2 ms when the machine is quiet; the earlier 19.8 ms was under heavy load, not representative.
- Breakdown (ms/op): word vectoriser 0.5, char vectoriser 0.7 to 1.1, sklearn `predict_proba` on the 383k-feature sparse row 4.2 to 5.1. So the vectorisers do NOT dominate; sklearn's predict_proba overhead (input validation plus the dense 383k x 3 coef path) does. Replacing it with `X @ coef.T + b` and a hand softmax (numerically identical, `allclose` True) gives 1.5 ms single op total. That is already well under 20 ms with no accuracy change; no lighter vectoriser needed for latency.
- Lighter vectoriser setups (refit, same LOVO mode (a) tuning, raw p): char 3-5 + word cap 100k each 90.5 / 1.2 / 8.3 (val acc 95.98); char 3-4 cap 50k each 89.9 / 1.4 / 8.7 (96.17); word 1-2 only cap 100k 88.6 / 1.3 / 10.1 (96.05, 63 s fit). Versus 89.8 raw for the full 383k setup: capping at 100k per vectoriser loses nothing (+0.7, within noise), dropping chars loses 1.2 points. Single-op times for these were measured while the machine was at load 20+ and are not comparable (3.8 to 4.7 ms); the quiet-machine number to cite is the 1.5 ms above. A smaller feature cap mainly shrinks the pickle (24 MB now), which matters for the package size.
- Hashing vectoriser not tried: the fast matvec path already makes latency a non-issue and the hashing trades away the vocabulary needed for the lighter cap above.

## 2026-11-03: MiniLM round-6: own cuts (LOVO) vs baseline

Model: all-MiniLM-L6-v2 + 3-way head, round-6 full run on the home server (1 epoch, 87,657 rows, 48.8 min, val acc 97.27%). Probs pulled to `data/train/probs-r6full-{val,v3eval}.npy`, HF model to `data/train/ckpt-r6full/final/` (gitignored). Same procedure as the baseline entry above, run by `python3 train/tune_cuts.py --tag r6full` (results `data/train/tune-cuts-r6full-results.json`): temperature fit on the val split only (T=1.322), global-budget rule (max exact s.t. TOTAL too-loose <= mechanical's), leave-one-vendor-out over the 23 v3 vendors, model p in place of Jev p, POST two-step r cut on p(w)+p(x), credential rule, DELETE stays x; plus guarded-argmax mode (b). One change: the model's p is far more peaked than TF-IDF's, so every grid got extra points near 0 and 1 (0.001/0.005/0.01, 0.99/0.995/0.999; margin 0.95..0.999). Baseline grids were left as they were.

Count correction: mechanical's too-loose is 77 rows (1.35%), not 74. The "74" in earlier tables was 1.3% x 5,716, a rounding artifact; `tune_cuts.py` now prints exact row counts (`looseRows`). Re-scoring the cached baseline probs (`--tag baseline`) gives the same percentages with true counts: baseline (a) calibrated = 74 loose rows (under the 77 budget), baseline (b) calibrated = 57.

### LOVO, exact / too loose / too tight (v3 tuning truth, n=5,716; loose rows in brackets)
| | overall | non-DELETE | DELETE |
|---|---|---|---|
| mechanical | 76.3 / 1.3 / 22.3 (77) | 69.1 | 99.3 |
| Jev labels, own LOVO (round 6) | 95.8 / 1.0 / 3.2 | | |
| baseline (a) own cuts, calibrated | 91.0 / 1.3 / 7.8 (74) | 88.3 / 1.7 / 10.0 | 99.3 / 0.0 / 0.7 |
| MiniLM (a) PRD cuts, no tuning (model's own eval) | 94.4 / 2.0 / 3.5 | | |
| MiniLM (a) own cuts, raw | 92.3 / 1.9 / 5.8 (108) | 90.1 / 2.5 / 7.4 | 99.3 / 0.0 / 0.7 |
| **MiniLM (a) own cuts, calibrated** | **92.0 / 1.9 / 6.1 (108)** | 89.7 / 2.5 / 7.9 | 99.3 / 0.0 / 0.7 |
| MiniLM (b) guarded, raw | 89.4 / 1.3 / 9.3 (74) | 86.2 / 1.7 / 12.1 | 99.3 / 0.0 / 0.7 |
| **MiniLM (b) guarded, calibrated** | **88.6 / 1.3 / 10.1 (76)** | 85.2 / 1.7 / 13.1 | 99.3 / 0.0 / 0.7 |
| MiniLM (b) plain argmax, no guard | 95.1 / 2.5 / 2.4 (142) | | |

Per tier, exact / loose / tight (calibrated):
| tier (n) | baseline (a) | MiniLM (a) | MiniLM (b) |
|---|---|---|---|
| lower (1,641) | 79.3 / 3.5 / 17.2 | 82.6 / 3.4 / 14.0 | 71.4 / 1.3 / 27.4 |
| raise-wx (1,486) | 90.6 / 0.7 / 8.7 | 90.8 / 3.2 / 6.0 | 90.4 / 3.3 / 6.3 |
| raise-get (959) | 100.0 / 0.0 / 0.0 | 100.0 / 0.0 / 0.0 | 99.8 / 0.0 / 0.2 |
| none-DELETE (1,364) | 99.3 / 0.0 / 0.7 | 99.3 / 0.0 / 0.7 | (none, 1,630) 97.6 / 0.4 / 2.0 |
| none-other (266) | 89.1 / 2.3 / 8.6 | 89.1 / 2.3 / 8.6 | |

### Cuts (calibrated p, chosen on all 23 vendors; LOVO range over the 23 folds)
- Mode (a): lower 0.20 (0.05 to 0.50), r cut 0.30 (0.07 to 0.80), raise-wx 0.02 (0.02 to 0.20), raise-get 0.05 (fixed). Raw p: lower 0.15, r cut 0.07, raise-wx 0.01, raise-get 0.02.
- Mode (b): guard margin 0.90 to 0.95 per fold (raw 0.95 to 0.98).
- In-sample (cuts fit and scored on all 23 vendors, not honest): 92.4 / 1.35 / 6.3, 77 loose rows, so exactly at the budget. Honest LOVO puts the same procedure at 108 loose rows: the cuts that satisfy the budget on 22 vendors do not hold on the 23rd.

### What this says
- The MiniLM is a better ranker than the baseline (val 97.27 vs 96.20, plain argmax 95.1 vs 94.0 exact), and mode (a) calibrated gains 1.0 exact point over the baseline's own cuts (92.0 vs 91.0, DELETE identical, all of the gain in lower and raise-wx tight).
- But it is too sure of itself on the rows it gets wrong. Raise-wx is the problem tier: the chosen cut sinks to 0.02 (the model puts almost no mass on x for w rows it should raise), and with those cuts the held-out vendors give 47 too-loose rows in raise-wx alone (baseline: 11). Total 108 too loose vs mechanical's 77 (1.9% vs 1.35%). Mode (a) fails the budget by 31 rows, under honest LOVO.
- Mode (b) holds the budget (76 rows, 1.33%, within 1 row of 77) but exact falls to 88.6, below 91; the guard again converts too-loose into too-tight (lower tier tight 27.4%). Same shape as the baseline's (b).
- So neither MiniLM mode clears the PRD rule here, and the baseline mode (a) calibrated (91.0 / 74 rows) is the only one that does, by a hair.

### Latency and size (local laptop, PyTorch fp32, batch 1, max_len 128, torch threads 4, load average 3 to 4; 300 v3 texts after 20 warm-up)
- Two runs: mean 22.6 ms (p50 22.5, p95 33.2, max 40.9) and mean 28.4 ms (p50 26.9, p95 45.8). Tokenizer 0.8 ms of that. Model forward is the rest. Not quiet-machine certain, so read as 22 to 28 ms; this is fp32 PyTorch, not the int8 ONNX that M1 will measure.
- 22.7M parameters, fp32 weights 90.9 MB (`model.safetensors` 90,869,484 bytes). Baseline for comparison: 24 MB pickle, 1.5 ms single op.

### Verdicts (indicators only; the exam decides)
- By the PRD rule (exact >= 91 and too-loose no worse than mechanical) on these tuning rows: baseline (a) calibrated passes (91.0, 74 vs 77 rows); MiniLM (a) fails on loose (108 vs 77); MiniLM (b) fails on exact (88.6). Edge cases: the baseline's pass is 0.0 above the exact line, and MiniLM (a) would pass if the budget were judged in-sample (92.4 / 77) rather than LOVO.
- Caveats: one split of 23 vendors, rows within a vendor are correlated; the cut grid was extended for MiniLM only; v3 truth is Jev-derived labels, so every figure is against labels, not ground truth; the MiniLM is one seed, one epoch; loose differences of 30 rows are a few vendors' worth.

## 2026-11-03: rwxmap take-backs and gate-3 (rwxmap F2 exam)

### rwxmap decisions that touch rwxlite
- D128 (rwxmap): rwxlite's trained model is scored ONCE on rwxmap exam-2026-09-22 as the M0 go/no-go, and only after a fresh label gate passes.
- D129 (rwxmap) = our F1 two-step POST lower, built into rwxmap src and scored once on gate-2 by rwxmap's real CLI (jev-1.14.0, 654 requests, 0 failed; rwxmap T_r = 0.50, chosen on its tuning set). All 600 shipped rows: 91.7 / 3 / 47 (exact% / too-loose rows / too-tight rows) -> with F1 94.5 / 3 / 30. Vendor-clean 483: 90.5 -> 93.6. It moved 17 rows, all right. It is stricter than ours: it moves rows only after isX lowers, ours moved 20.
- rwxmap F2 tuning finding: a broad credential-noun rule on PUT/PATCH fails (6 right vs 17 wrong on rwxmap combined). Most credential-naming rows are config edits, which are w. Only replacing the credential itself is x.

### Gate-3 (data/gate-2026-11-06/; commits b3d8e0e, ec76d1b, 7323817, 0f61b68)
- Drawn for rwxmap's F2 exam. It is NOT an rwxlite exam: the rwxlite MiniLM was trained on these rows.
- 800 rows: credential stratum 200 (POST 100 / PUT 68 / PATCH 32; regex password|passcode|\bpin\b|secret|credential|key|token|certificate|session on path + operationId + summary, POST/PUT/PATCH) plus 600 general.
- hubapi.com (HubSpot, burned x20) dropped by name after rwxmap's lock check; 2 credential POST rows redrawn.
- Labellers agreed on 785 of 800 (98.1%); the user ruled the other 15.
- Truth: credential stratum r 19 / w 149 / x 32; general r 365 / w 203 / x 32.
- D131 (rwxmap) = F2 narrow credential rule: PUT/PATCH whose last path segment is password|passcode|pin, or whose lead verb is change|regenerate|regen naming one; singular only. Scored once on gate-3: fired 4, 3 right (signl4 changePassword, sendgrid /user/password, jira changeMyPassword), 1 wrong (whapi plusCard pin, truth w). Credential part 56.5 / 16 / 71 -> 57.5 / 13 / 72; general unchanged 77.5 / 10 / 125; vendor-clean too-loose 21 -> 19.
- Gate-3 is burned for both projects.

### Process notes
- Shared scratchpad: the two gate-3 labellers shared a scratch folder and one helper script was overwritten. It only printed blind rows (never labels), so the labels stayed independent. Lesson: give each labeller its own scratch dir.
- Workflow lesson: background workers left orphan sleep/watch loops. Now each worker must leave none, and the main session stops finished workers.
- Repo: public at https://github.com/hamr0/rwxlite (branches main = PRD 0d270c9, m0 = work), Apache-2.0 (7951645), README in bareagent shape (b2aae56) with honest "planned" markers.

## 2026-11-03: Round 8: soft targets + abstain table

User sign-off: "we need less loose". r6 (hard targets) left 108 too-loose rows at LOVO own cuts, 47 of them raise-wx (PUT/PATCH): hard labels pushed p(x) on PUT/PATCH to about 0, so no cut could raise the true-x rows.

Change (`train/finetune.py --soft`, `soft_targets()` in `train/common.py`; data unchanged, columns jev_p/jev_pC already in `train.parquet`): 3-way target per row from the stored Jev probabilities. lower/raise-wx tier rows: p(x)=isX; POST rows p(r)=(1-isX)(1-changes), p(w)=(1-isX)changes (changes = jev_pC; missing -> all non-x mass to w); PUT/PATCH p(w)=1-isX; GET (raise-get) p(r)=1-changes, p(w)=changes; DELETE, credential rows, tier-none rows and rows without Jev p are one-hot of the round-6 label. Loss = alpha x soft CE + (1-alpha) x hard CE, alpha 0.7 (default `--alpha`; chosen a priori, not tuned: soft term carries the uncertainty, the hard term keeps the argmax anchored to the r6 label). `--x_weight` (class weight on x) added, default 1.0, not needed. Run: server, 1 epoch, 87,657 rows, 2740 steps, 48.5 min, val acc (vs hard r6 labels) 96.89% (r6: 97.27). Eval by `python3 train/tune_cuts.py --tag r8soft` (T=0.844 on val; r6full T=1.322), unchanged procedure; abstain tables by new `train/abstain.py` (results `data/train/abstain-<tag>.json`). Because r8soft passes the rule the r8softx follow-up was not run.

### LOVO, exact / too loose / too tight (v3 tuning truth, n=5,716; too-loose rows in brackets; calibrated p)
| | overall | non-DELETE | lower (1,641) | raise-wx (1,486) |
|---|---|---|---|---|
| mechanical | 76.3 / 1.3 / 22.3 (77) | | | |
| baseline (a) | 91.0 / 1.3 / 7.8 (74) | 88.3 | 79.3 / 3.5 / 17.2 | 90.6 / 0.7 / 8.7 |
| r6full (a) own cuts | 92.0 / 1.9 / 6.1 (108) | 89.7 | 82.6 / 3.4 / 14.0 (55) | 90.8 / 3.2 / 6.0 (47) |
| **r8soft (a) own cuts** | **92.8 / 1.3 / 5.9 (73)** | 90.7 / 1.7 / 7.6 | 86.3 / 3.5 / 10.2 (57) | 90.0 / 0.7 / 9.3 (10) |
| r6full (b) guarded | 88.6 / 1.3 / 10.1 (76) | 85.2 | 71.4 / 1.3 / 27.4 (21) | 90.4 / 3.3 / 6.3 (49) |
| **r8soft (b) guarded** | **91.9 / 1.0 / 7.1 (55)** | 89.6 / 1.3 / 9.2 | 82.7 / 2.4 / 14.9 (39) | 90.5 / 0.7 / 8.8 (10) |

raise-get 99.8 to 100 and DELETE 99.3 / 0 / 0.7 for all rows. Cuts r8soft mode (a), calibrated, chosen on all data: lower 0.30 (LOVO 0.10 to 0.50), r cut 0.40 (0.15 to 0.60), raise-wx 0.15 (0.05 to 0.15), raise-get 0.05 (0.02 to 0.05); mode (b) margin 0.6 to 0.9. Raw p (no calibration): (a) 93.4 / 1.3 / 5.3 (75), (b) 92.3 / 0.9 / 6.8 (51). Plain argmax r8soft 95.7 / 2.5 / 1.8 (142 loose), so cuts and guard still do the work of keeping loose down.

Result: raise-wx too-loose fell from 47 to 10 (baseline 11), the whole 108 -> 73 gain. Lower tier is unchanged in too-loose (57 vs 55) but its tight fell 14.0 -> 10.2. Both modes now clear "exact >= 91 and too-loose <= 77" under honest LOVO. The lower tier (57 of 73 loose rows in mode a) is now the remaining loose source.

### Abstain / ask table (honest LOVO cuts/margins, calibrated p; confidence = max p; abstained rows become "ask")
Cell = answered rows' exact % / too-loose rows / too-tight rows; abstained count with, in brackets, how many of those the unguarded answer would have got too-loose.

r8soft mode (b) guarded standalone
| thr | answered % | exact % | too-loose | too-tight | abstained (loose avoided) |
|---|---|---|---|---|---|
| none | 100.0 | 91.9 | 55 | 408 | 0 |
| 0.5 | 99.5 | 92.2 | 55 | 388 | 26 (0) |
| 0.6 | 97.5 | 93.5 | 55 | 309 | 143 (0) |
| 0.7 | 95.2 | 94.6 | 55 | 239 | 273 (0) |
| 0.8 | 92.9 | 95.5 | 54 | 185 | 407 (1) |
| 0.85 | 90.8 | 96.5 | 45 | 139 | 526 (10) |
| 0.9 | 88.7 | 97.3 | 38 | 99 | 646 (17) |
| 0.95 | 82.9 | 98.7 | 24 | 37 | 978 (31) |
| 0.99 | 54.3 | 98.7 | 6 | 33 | 2612 (49) |

r8soft mode (a) own cuts
| thr | answered % | exact % | too-loose | too-tight | abstained (loose avoided) |
|---|---|---|---|---|---|
| none | 100.0 | 92.8 | 73 | 340 | 0 |
| 0.5 | 99.5 | 93.1 | 70 | 324 | 26 (3) |
| 0.6 | 97.5 | 94.3 | 68 | 247 | 143 (5) |
| 0.7 | 95.2 | 95.3 | 65 | 192 | 273 (8) |
| 0.8 | 92.9 | 95.8 | 54 | 168 | 407 (19) |
| 0.85 | 90.8 | 96.9 | 45 | 118 | 526 (28) |
| 0.9 | 88.7 | 97.7 | 38 | 78 | 646 (35) |
| 0.95 | 82.9 | 98.7 | 24 | 39 | 978 (49) |
| 0.99 | 54.3 | 98.7 | 6 | 33 | 2612 (67) |

r6full mode (b) guarded standalone
| thr | answered % | exact % | too-loose | too-tight | abstained (loose avoided) |
|---|---|---|---|---|---|
| none | 100.0 | 88.6 | 76 | 578 | 0 |
| 0.5 | 99.8 | 88.7 | 76 | 569 | 9 (0) |
| 0.6 | 98.6 | 89.6 | 76 | 511 | 78 (0) |
| 0.7 | 97.6 | 90.3 | 76 | 464 | 140 (0) |
| 0.8 | 96.2 | 91.1 | 76 | 412 | 219 (0) |
| 0.85 | 94.6 | 92.2 | 76 | 347 | 306 (0) |
| 0.9 | 92.8 | 93.2 | 76 | 283 | 413 (0) |
| 0.95 | 89.8 | 95.0 | 76 | 183 | 585 (0) |
| 0.99 | 47.3 | 98.9 | 3 | 28 | 3010 (73) |

r6full mode (a) own cuts
| thr | answered % | exact % | too-loose | too-tight | abstained (loose avoided) |
|---|---|---|---|---|---|
| none | 100.0 | 92.0 | 108 | 351 | 0 |
| 0.5 | 99.8 | 92.1 | 107 | 343 | 9 (1) |
| 0.6 | 98.6 | 93.0 | 105 | 289 | 78 (3) |
| 0.7 | 97.6 | 93.8 | 103 | 245 | 140 (5) |
| 0.8 | 96.2 | 94.6 | 96 | 202 | 219 (12) |
| 0.85 | 94.6 | 95.5 | 90 | 156 | 306 (18) |
| 0.9 | 92.8 | 96.2 | 85 | 117 | 413 (23) |
| 0.95 | 89.8 | 96.8 | 75 | 89 | 585 (33) |
| 0.99 | 47.3 | 98.9 | 3 | 28 | 3010 (105) |

Band abstain, mode (a) (abstain when the tier-relevant p is within +-0.1 of its cut):
| model | rule | answered % | exact % | too-loose | too-tight | abstained (loose avoided) |
|---|---|---|---|---|---|---|
| r6full | moved rows only (spec) | 91.4 | 92.4 | 96 | 299 | 494 (12) |
| r6full | any in-tier row | 60.2 | 90.9 | 89 | 223 | 2277 (19) |
| r8soft | moved rows only (spec) | 91.1 | 93.6 | 66 | 266 | 506 (7) |
| r8soft | any in-tier row | 63.4 | 93.1 | 63 | 186 | 2092 (10) |

Reading: r8soft is also better calibrated for abstaining. At 0.9 it answers 88.7% at 97.7% exact with 38 too-loose rows (mode a), abstaining on 646 rows of which 35 would have been too-loose; r6full at 0.9 answers 92.8% at 96.2% exact with 85 loose. The confidence of the r6 model carries almost no loose signal in mode (b) (its 76 loose rows are all answered with confidence >= 0.95), whereas r8soft's loose rows are concentrated at low confidence. Band abstain is a weak ask rule: it catches only 7 to 12 loose rows for about 500 asks; the max-p threshold is the better signal. About 98.7% exact is reached at p >= 0.95 (83% coverage) and 0.99 (54%).

Caveats: one seed, one epoch, one 23-vendor split; thresholds are not tuned on v3 (grid reported as is); truth is Jev-derived labels; LOVO cuts differ per fold. Latency/size unchanged from r6 (same architecture).

## 2026-11-03: One-time exam: r8soft

Pre-registered in `docs/wiki/exam-prereg-r8soft.md` (f05ec42) before any exam truth was read. Scored once, 4,279 rows (cloudflare, pagerduty, sentry), join 1:1, no rerun, nothing changed after seeing the numbers. Code: `m0/exam-inputs.mjs` (reads input columns only), `train/exam_score.py predict` (never opens truth), `train/exam_score.py score` (only place truth is opened). Outputs in `data/exam-r8soft/` (`predictions.csv`, `results.json`, `score.log`). Model MiniLM r8soft fp32 on CPU, T 0.844, mode (a) cuts lower 0.30 / r 0.40 / raise-wx 0.15 / raise-get 0.05 + credential rule, mode (b) guarded margin 0.6. Before scoring, the inference path was checked against the saved v3 probabilities (286 rows, max abs diff 2e-7).

### Verdict: NO-GO on the letter of the bar

Mode (a), no ask: **exact 95.91% (passes >= 91%), too loose 0.84% = 36 rows (fails <= 0.5%, which allows 21 rows)**. Exact clears by 4.9 points; too loose misses by 15 rows. The bar is a joint AND, so M0 does not pass as pre-registered.

### Reference lines (same exam, overall)
| | exact | too loose | too tight |
|---|---|---|---|
| mechanical (re-scored here) | 82.26 (3520) | 0.79 (34) | 16.94 (725) |
| mechanical + Jev (rwxmap, PRD) | 93.0 | 0.5 | 6.5 |
| r8soft mode (a), none | 95.91 (4104) | 0.84 (36) | 3.25 (139) |
| r8soft mode (b), none | 95.54 (4088) | 0.75 (32) | 3.72 (159) |

Mechanical reproduces rwxmap exactly (82.3 / 0.8 / 16.9). The model is better than Jev on exact by about 3 points and on too-tight by half, but 36 loose rows is more than Jev's ~21 and about the same as mechanical's own 34. The LOVO tuning estimate was 1.3% loose on v3 data, so the tuning rule (loose no worse than mechanical's) is essentially met here (36 vs mechanical's 34), but mechanical's own 0.79% is already above the 0.5% bar, so that rule could not have delivered it.

### Mode (a) vs mode (b), all configs (answered rows; "asked, loose" = asked rows the unasked answer would have had too loose)
| ask thr | mode | answered % | exact % | too loose rows (%) | too tight rows (%) | asked (loose avoided) |
|---|---|---|---|---|---|---|
| none | a | 100.0 | 95.91 | 36 (0.84) | 139 (3.25) | 0 |
| none | b | 100.0 | 95.54 | 32 (0.75) | 159 (3.72) | 0 |
| 0.7 | a | 97.4 | 97.48 | 36 (0.86) | 69 (1.66) | 110 (0) |
| 0.7 | b | 97.4 | 97.39 | 32 (0.77) | 77 (1.85) | 110 (0) |
| 0.9 | a | 93.9 | 98.56 | 21 (0.52) | 37 (0.92) | 260 (15) |
| 0.9 | b | 93.9 | 98.66 | 21 (0.52) | 33 (0.82) | 260 (11) |
| 0.95 | a | 90.2 | 98.73 | 18 (0.47) | 31 (0.80) | 418 (18) |
| 0.95 | b | 90.2 | 98.73 | 18 (0.47) | 31 (0.80) | 418 (14) |

Reading the ask tables: asking at 0.7 (110 rows) removes 70 too-tight rows and zero too-loose rows, because every too-loose row is answered with high confidence. Only at 0.9 does it start to catch loose rows (15 of 36 in mode a), and at 0.9 / 0.95 the answered set passes the loose bar (21 rows = 0.5225%, just over by rounding at 0.9; 0.47% at 0.95) at the cost of asking 6.1% / 9.8% of rows. This is for information only; the bar was set on mode (a) with no ask. The v3 LOVO abstain table predicted more loose avoidance at 0.9 (35 of 73); here the model is confidently wrong on the loose rows (median max p of the 36 loose rows is 0.94).

### By method (none ask; exact % / loose rows / tight rows)
| method | n | mode (a) | mode (b) |
|---|---|---|---|
| GET | 2,099 | 99.38 / 2 / 11 | 99.62 / 2 / 6 |
| POST | 892 | 86.32 / 25 / 97 | 83.74 / 19 / 126 |
| PUT | 460 | 96.52 / 6 / 10 | 96.74 / 7 / 8 |
| PATCH | 270 | 94.81 / 3 / 11 | 95.19 / 4 / 9 |
| DELETE | 558 | 98.21 / 0 / 10 | 98.21 / 0 / 10 |

### By tier (none ask)
| tier | n | mode (a) | mode (b) |
|---|---|---|---|
| lower (POST x) | 808 | 87.13 / 22 loose / 82 tight | 84.28 / 16 / 111 |
| raise-wx | 724 | 96.27 / 9 / 18 | 96.55 / 11 / 14 |
| raise-get | 2,099 | 99.38 / 2 / 11 | 99.62 / 2 / 6 |
| none | 648 | 95.22 / 3 / 28 | 95.22 / 3 / 28 |

By provider (mode a): cloudflare 95.58% exact, 30 loose; pagerduty 97.63%, 4; sentry 97.49%, 2.

### Where the 36 too-loose rows are (mode a)
- 22 in the lower tier, all POST: 21 are mechanical x/floor-post lowered to w where truth is x (one more lowered to r where truth is w). Truth x for a POST "create" is typically a create with side effects or cost: "Create a top-up" (ai-gateway billing), "Create Zone Subscription" (x2), "Create a new rollout for an application", "Restore D1 Database to a bookmark", "Create Registration" (registrar sandbox), "Disable Outgoing Zone Transfers", "Create a Status Page Post" (pagerduty), "Create Replay Batch Deletion Job" (sentry). Model p(x) on these is 0.1 to 0.27, just above the 0.30 lower cut when it fails, with max p (on w) between 0.72 and 0.98.
- 9 are raise-wx PUT/PATCH rows left at w where truth is x: "Update a Cloudflare Tunnel", "Update takedown notice", "Update r2.dev Domain of Bucket", "Replace token validation credentials" (cloudflare), "Update ServiceNow credentials" and "Configure an account's session configurations" (pagerduty). The model gives p(x) 0.01 to 0.11, below the raise-wx cut 0.15.
- 3 outside the pile and 2 raise-get GET: sentry "Add a Member to an Organization" (POST, mechanical w/modify-verb, p(x) about 0), cloudflare "Test a webhook configuration" POST (mech r/read-verb, truth x, p(r) 1.0, twice); GET "Connect PagerDuty" and "Close a browser target" (mech r, truth w, p(r) 0.95 and 0.97).
- One POST "Get a browser session ID" lowered to r where truth is w (p(r) 0.72).
- Confusion (truth rows x predicted r/w/x), mode (a): r [2179, 14, 34], w [3, 1253, 91], x [2, 31, 672]. Mode (b): r [2180, 4, 43], w [2, 1233, 112], x [2, 28, 675].
- 29 of the 36 loose rows are shared with mode (b); 7 are mode (a) only, 3 mode (b) only.

### Mode (a) vs mode (b), and tweaks
- Mode (b) standalone is nearly as good as mode (a) on this exam: exact 95.54 vs 95.91, loose 32 vs 36 rows. It wins on too-loose (POST lower tier 16 vs 22) and on GET; it loses on too-tight (159 vs 139), almost all in POST (126 vs 97). Its guard (margin 0.6) is a cheaper way to keep loose down, since it needs no mechanical letter. Neither mode meets the 0.5% bar without asking.
- What suggests a tweak (for a fresh exam, never this one): (1) the lower tier is the problem in both modes (22 / 16 loose rows of 808): a lower cut under 0.30 or a stricter lower guard, for POST "create" rows that touch money, subscriptions, jobs, restores or deletions; a lower cut would trade more too-tight, and the lower tier is already 10% tight. (2) raise-wx cut 0.15 misses 9 PUT/PATCH x rows whose p(x) is 0.01 to 0.11; at v3 tuning the cut was already at the bottom of its LOVO range. (3) Ask at 0.9 or 0.95 is the practical lever: it catches 15 to 18 of the 36 loose rows; this exam shows no loose-row catch at 0.7. These are observations, not changes; nothing has been retuned.
- Caveat: the exam truth is from rwxmap's labeller under BRIEF-v3, same label standard as the training truth; many of the 36 are borderline "create" or "update" rows where a reasonable labeller could say w. Label noise on the loose side is unmeasured here.

Note for the prereg file: it states "0.6 in 18 of 23 folds (0.7 in 4, 0.9 in 1)"; the results file says 0.6 in 17, 0.7 in 5, 0.9 in 1. Descriptive only; the margin used (0.6) is unaffected.

## 2026-11-03: Round 9b: unsure falls back to mechanical

Practice (LOVO) rows, not an exam: v3 tuning truth only (n=5,716), honest per-fold cuts/margins exactly as `train/abstain.py` (new `train/fallback.py` reuses its `lovo_preds`), r8soft, calibrated p (T 0.844), confidence = max p. Exam and gate truth not touched. Results `data/train/fallback-r8soft.json` (all bars, all rules, both modes; includes ask-would-have-been right/loose/tight). Every row lands in exactly one of right / too loose / too tight / asked (asserted, sums to 5,716).

Rules for rows below the bar. ASK: ask. MECH: use the mechanical letter, no asks. MECH-THEN-ASK: mechanical letter if it is at least as strict as the model's (r < w < x), else ask. Percentages are of answered rows; asked % is of all rows. 'none' = no bar (identical for all rules).

Reference lines: mechanical alone 76.3 right / 77 too loose / 22.3 too tight (earlier count); this run's MECH at 0.99, which is almost mechanical alone, gives 76.4 right / 76 too loose (1.33%), one row apart from the earlier count. r8soft mode (a) no bar 5303 right (92.8%) / 73 loose (1.28%) / 340 tight (5.95%); mode (b) no bar 5253 (91.9%) / 55 (0.96%) / 408 (7.14%).

### Mode (a) mechanical + cuts
| rule | bar | right | too loose | too tight | asked (would be right / loose / tight) |
|---|---|---|---|---|---|
| ASK | none | 5303 (92.77%) | 73 (1.28%) | 340 (5.95%) | 0 (0.0%) (0 / 0 / 0) |
| ASK | 0.7 | 5186 (95.28%) | 65 (1.19%) | 192 (3.53%) | 273 (4.78%) (117 / 8 / 148) |
| ASK | 0.9 | 4954 (97.71%) | 38 (0.75%) | 78 (1.54%) | 646 (11.3%) (349 / 35 / 262) |
| ASK | 0.95 | 4675 (98.67%) | 24 (0.51%) | 39 (0.82%) | 978 (17.11%) (628 / 49 / 301) |
| MECH | 0.7 | 5329 (93.23%) | 74 (1.29%) | 313 (5.48%) | 0 (0.0%) (0 / 0 / 0) |
| MECH | 0.9 | 5269 (92.18%) | 96 (1.68%) | 351 (6.14%) | 0 (0.0%) (0 / 0 / 0) |
| MECH | 0.95 | 5186 (90.73%) | 85 (1.49%) | 445 (7.79%) | 0 (0.0%) (0 / 0 / 0) |
| MECH-THEN-ASK | 0.7 | 5281 (93.32%) | 65 (1.15%) | 313 (5.53%) | 57 (1.0%) (9 / 0 / 48) |
| MECH-THEN-ASK | 0.9 | 5168 (92.98%) | 39 (0.7%) | 351 (6.32%) | 158 (2.76%) (57 / 0 / 101) |
| MECH-THEN-ASK | 0.95 | 5050 (91.45%) | 27 (0.49%) | 445 (8.06%) | 194 (3.39%) (58 / 0 / 136) |

### Mode (b) guarded standalone
| rule | bar | right | too loose | too tight | asked (would be right / loose / tight) |
|---|---|---|---|---|---|
| ASK | none | 5253 (91.9%) | 55 (0.96%) | 408 (7.14%) | 0 (0.0%) (0 / 0 / 0) |
| ASK | 0.7 | 5149 (94.6%) | 55 (1.01%) | 239 (4.39%) | 273 (4.78%) (104 / 0 / 169) |
| ASK | 0.9 | 4933 (97.3%) | 38 (0.75%) | 99 (1.95%) | 646 (11.3%) (320 / 17 / 309) |
| ASK | 0.95 | 4677 (98.71%) | 24 (0.51%) | 37 (0.78%) | 978 (17.11%) (576 / 31 / 371) |
| MECH | 0.7 | 5292 (92.58%) | 64 (1.12%) | 360 (6.3%) | 0 (0.0%) (0 / 0 / 0) |
| MECH | 0.9 | 5248 (91.81%) | 96 (1.68%) | 372 (6.51%) | 0 (0.0%) (0 / 0 / 0) |
| MECH | 0.95 | 5188 (90.76%) | 85 (1.49%) | 443 (7.75%) | 0 (0.0%) (0 / 0 / 0) |
| MECH-THEN-ASK | 0.7 | 5244 (92.67%) | 55 (0.97%) | 360 (6.36%) | 57 (1.0%) (9 / 0 / 48) |
| MECH-THEN-ASK | 0.9 | 5154 (92.61%) | 39 (0.7%) | 372 (6.68%) | 151 (2.64%) (57 / 0 / 94) |
| MECH-THEN-ASK | 0.95 | 5059 (91.5%) | 27 (0.49%) | 443 (8.01%) | 187 (3.27%) (58 / 0 / 129) |

### Too-loose rows per tier (rows; MECH-THEN-ASK also shows asked)
| mode | rule | bar | lower (1,641) | raise-wx (1,486) | raise-get (959) | none (1,630) |
|---|---|---|---|---|---|---|
| a | MECH | 0.9 | 23 | 67 | 0 | 6 |
| a | MECH | 0.95 | 11 | 68 | 0 | 6 |
| a | MECH-THEN-ASK | 0.9 | 23 | 10 (asked 158) | 0 | 6 |
| a | MECH-THEN-ASK | 0.95 | 11 | 10 (asked 194) | 0 | 6 |
| b | MECH | 0.9 | 23 | 67 | 0 | 6 |
| b | MECH | 0.95 | 11 | 68 | 0 | 6 |
| b | MECH-THEN-ASK | 0.9 | 23 | 10 (asked 151) | 0 | 6 |
| b | MECH-THEN-ASK | 0.95 | 11 | 10 (asked 187) | 0 | 6 |

Reading. MECH alone is not a fix: below the bar the mechanical letter is wrong in the loose direction on most raise-wx rows (PUT/PATCH where mechanical says w and truth is x), so MECH loose rises from 73 to 85 to 96 as the bar rises (mode a, 0.95: 85 loose, 90.7% right) and only gets worse than ASK. All the extra loose rows are in raise-wx (67-68 vs 10). Lower tier does improve (23 at 0.9, 11 at 0.95, vs 57 at none) because the mechanical x is stricter than the model's r/w there.
MECH-THEN-ASK keeps that lower-tier gain and asks only on the raise-wx rows where mechanical is looser than the model, so it asks far less than ASK. Mode (a): 0.9 gives 39 loose with 2.8% asked (ASK 0.9: 38 loose, 11.3% asked); 0.95 gives 27 loose (0.49% of answered) with 3.4% asked, 91.5% right, 8.1% tight. ASK 0.95 gives 24 loose (0.51%) but asks 17.1% (over the 15% limit), 98.7% right, 0.82% tight. Mode (b) is the same story (MECH-THEN-ASK 0.95: 27 loose, 3.3% asked).
Which gives the fewest loose rows at an ask rate of about 15% or less: in a strict sense MECH-THEN-ASK at 0.99 (16 loose, 3.5% asked) but it is nearly the mechanical letter everywhere (76.6% right, 23% too tight), so it is not useful. Among usable settings, MECH-THEN-ASK at 0.95 (27 loose, 3.4% asked) beats ASK at 0.9 (38 loose, 11.3% asked) on both loose and ask rate, and is within 3 loose rows of ASK 0.95 at a fifth of the asks. The price is too-tight: 8% of answered rows versus under 1% for ASK 0.95, because the mechanical fallback is blunt (it holds the mechanical letter everywhere the model is unsure, 445 tight rows). So the choice is loose vs tight: ASK 0.95 buys very high exactness with 17% asks; MECH-THEN-ASK 0.95 buys the same loose count with 3% asks and a lot of tight rows. Whether tight rows cost less than asks is a product call, not measured here.
Caveat: practice rows, not an exam; the One-time exam showed the model is confidently wrong on its loose rows more than LOVO suggested (median max p 0.94), so the loose avoidance here may not transfer.
