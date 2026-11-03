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
