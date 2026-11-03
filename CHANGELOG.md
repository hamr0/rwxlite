# Changelog

All notable changes to rwxlite are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-11-03

Module 0 (M0): a research release. It measures whether a small local classifier
can say whether an API operation reads (r), writes (w) or can't be taken back (x).
**No model is shipped in this release.** Weights stay local; the int8 export and
the Node runtime are M1. Both exams below were NO-GO.

### Added
- Mechanical pass over all APIs.guru operations (rwxmap's `classifyRow`), about
  123,340 operations from 2,529 specs (`m0/mechanical.mjs`).
- Jev labelling pipeline: per-method questions, resumable, hard spend guard under
  the $50 cap (`m0/jev-label.mjs`, `m0/run-step2.sh`, `m0/questions/`). Includes the
  POST "changes" pass, two-step lowering of POST rows and a narrow credential rule.
- Label gates, each used once on a blind 600-row sample with two labellers and a
  95% bar. Gate-1 failed at 90.8% (all too tight, mostly reads labelled as POST).
  Gate-2, after the rule changes, passed at 96.5% (`m0/gate-sample.mjs`,
  `m0/gate-score.mjs`, `m0/parity.mjs`, `data/gate-*`).
- Training pipeline in `train/`: TF-IDF + logistic regression baseline, MiniLM
  (all-MiniLM-L6-v2) first run and r6 with own-cut tuning, then r8 soft targets
  with temperature calibration (T = 0.844) and cuts tuned leave-one-vendor-out.
- Measurements on practice rows (5,716 v3 tuning rows, not exams): round 8 abstain
  evaluation, round 9b fallback-to-mechanical (ASK, MECH, MECH-THEN-ASK), and round
  9c lowering flag (accept a lowering only at p >= 0.97: 93.2% right, 0.41% too
  loose, 9.6% asked).
- Round 9 hand labels: 1,200 training rows of the two failing shapes labelled
  blind by two labellers (98.8% agreement). Training labels were too loose on 32
  rows (2.7%); the retrain was skipped.
- One-time exam on rwxmap's 2026-09-22 exam (4,279 rows: cloudflare, pagerduty,
  sentry): **NO-GO**. Exact 95.91% passes; too loose 0.84% (36 rows) fails the
  0.5% line.
- Fresh exam on coolify, workos, lago and resend (949 ops, pinned specs, labels
  frozen before any prediction, pre-registered): **NO-GO by one row**. 92.57% right
  (pass), 7.8% asked (pass), 5 too loose = 0.57% (fail; the line is 0.5%, 4 rows).
  The lowering flag worked (no lowering was too loose); the 5 misses are 3
  credential upserts and 2 logout GETs raised one step short of x.
- Gate 3 and gate 4 samples, labels and rulings built for rwxmap (F2 and
  take-backs exams).
- PRD flow: rwxmap adapter, three engines, the two-question call and the lowering
  flag, with the fresh-exam rule set to LOWER-BAR-ASK at 0.97.
- Apache-2.0 licence, README, secret-scanning config that skips vendor spec
  copies, and `.gitignore` entries for local `.claude/` and `.litectx/`.
- Docs: PRD contract, `docs/wiki/findings.md`, classifier-training wiki and the
  two exam pre-registrations.

### Changed
- README abstain row now follows the contract rule.
- Exam pre-registration addendum: code not pinned, rule switched after labels
  were seen. PRD label-gate bar wording clarified.

### Fixed
- `m0/fresh-exam-build.py` now runs directly and on a fresh clone: `env -S`
  shebang, repo root taken from the script path instead of a hardcoded home dir,
  rebuild from the committed pinned specs (sha256-checked) when the local download
  dir is absent, and the corpus-overlap check is skipped without the local corpus.
  Output `ops.csv` is byte-identical either way.
- Dropped a dead line in `train/exam_fresh.py`.
