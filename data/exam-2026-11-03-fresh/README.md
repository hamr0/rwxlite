# Fresh exam 2026-11-03 (blind)

Purpose: rwxlite's fresh one-time exam after the M0 NO-GO. The go/no-go rule is in
docs/product/prd.md, section "Option 2". rwxmap lock-checked all four vendors; the draw is the
full vendor (every operation), DELETE included. The four vendors are burned for rwxmap once
scored; the spare vendors are reserved for rwxmap.

`ops.csv` is the blind file labellers see: id, provider, method, path, operationId, summary,
description. It holds no labels or predictions. Used ONCE, never for tuning.

## Sources (pinned)

| provider | spec | source | full commit | sha256 of file |
|---|---|---|---|---|
| coolify.io | coolify.json (OpenAPI 3.1.0) | coollabsio/coolify `openapi.json` | e20e652c00d0927fa84cfe5d2d5b8e921bd46ef8 | bc7f83ff3e151843cf5d732a05620fad3127018379eed4890d70876988d276bb |
| workos.com | workos.yaml (3.1.1, spec 1.0) | workos/openapi-spec `spec/open-api-spec.yaml` | 4873892f3b965067d97dbb8a5b2cb91f7b557ac7 | 1f91e7c3470bf9841a03464c415353d66c9139687f08218a142866c0d2a45829 |
| getlago.com | lago.yaml (3.1.0, spec 1.56.0) | getlago/lago-openapi `openapi.yaml` | 1f1f510edbfe8cf489030475d27fcb2912c8dbf4 | 5d26657495a3a47ef65ec5e77f2e9f90d4d4580b77aad52f72bf3f53c2a2876a |
| resend.com | resend.yaml (3.1.2, spec 1.5.1) | resend/resend-openapi `resend.yaml` | 0b2a456ec468f07eb2e6fac73f0a76fb5463823c | e706637116ab3cf6b3ca99854c4cab4933a193c607b2b18b9d79c0cb16c68dd8 |

META recorded only 8-char commit prefixes (fetched from main). The full commits above were
resolved via the GitHub API and the file re-fetched from raw.githubusercontent.com at each
commit; all four are byte-identical to the pinned copies. `specs/` holds the four spec files
and their META.json (as `<vendor>.META.json`).

## Counts (vendor x method)

| provider | GET | POST | PUT | PATCH | DELETE | other | total |
|---|---|---|---|---|---|---|---|
| coolify.io | 119 | 108 | 4 | 49 | 41 | 0 | 321 |
| workos.com | 107 | 89 | 22 | 12 | 39 | 0 | 269 |
| getlago.com | 95 | 52 | 28 | 6 | 36 | 0 | 217 |
| resend.com | 62 | 41 | 1 | 18 | 20 | 0 | 142 |
| total | 383 | 290 | 55 | 85 | 136 | 0 | 949 |

## Build

`python3 -I m0/fresh-exam-build.py`. Ops are taken in vendor order (coolify, workos, lago,
resend), each in spec document order, then shuffled once with Python
`random.Random(20261110).shuffle`; ids fx-0001..fx-0949 follow the shuffled order. Text is
taken from the operation object only (no refs resolved), newlines collapsed to spaces.
No op key (provider+method+path) occurs in data/m0/mechanical.jsonl.gz (0 overlap).
On a fresh clone the script rebuilds from the committed pinned copies in `specs/` (each file's sha256 is checked against its `<vendor>.META.json`, exit 1 on mismatch) and writes a byte-identical ops.csv; the overlap check above runs only where the gitignored data/m0/mechanical.jsonl.gz exists, otherwise it prints a skip line.

## Labelling (frozen 2026-11-03)

Two independent labellers (A, B) labelled all 949 rows blind against BRIEF-v3 (`data/gate-2026-11-07/BRIEF-v3.md`), each with its own scratch dir, reading only the brief and ops.csv (no specs, no web docs, no model output): `labels-A.csv`, `labels-B.csv`. They agreed on 934/949 (98.4%). The 15 disagreements were ruled by the user on 2026-11-03 (accepting the main session's suggestions), in `rulings.csv`: six coolify restarts -> w (restart = stop + start; the agreed start/stop rows are w); three paid servers at DigitalOcean/Vultr/Hetzner -> x (charges at an outside provider); resend suppression batch remove -> w; workos device code -> w; resend domain claim -> x; coolify secret-manager import -> x (imports from an outside source); workos vault rekey -> r (returned, not stored); lago credit note -> x. `truth.csv` (id,label) = agreed label or ruling; 949 rows, no "?". Consistency check after rulings: start / stop / restart rows are all w; deploy / redeploy / create-preview-deployment rows are x (a run).

Truth mix r / w / x: all 406 / 328 / 215. GET 381 / 0 / 2; POST 25 / 192 / 73; PUT 0 / 51 / 4; PATCH 0 / 84 / 1; DELETE 0 / 1 / 135. Per vendor: coolify 124 / 130 / 67; workos 117 / 91 / 61; lago 103 / 61 / 53; resend 62 / 46 / 34.

No model or mechanical prediction has been computed on these rows at the time of freezing.
