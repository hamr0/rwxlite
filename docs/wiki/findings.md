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
