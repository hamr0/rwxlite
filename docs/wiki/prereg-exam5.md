# Pre-registration: shared clean exam #5, rwxlite side, candidate R13

**Status: FROZEN (2026-11-07) when committed with the predictions' sha256s (section 10), before truth is opened. Only the truth sha256 stays TBD.**
Written before the exam exists. Nothing here was run on exam #5 data: no ops.csv, no truth. The code was tested only on a synthetic ops.csv of 105 val rows (scratch, not committed) and on val/practice rows, which are R13's training data and decide nothing.
Update 2026-11-07: exam inputs are frozen (section 3); the lean now comes from rwxmap's lean.csv (section 3 and section 9); the predict script and score script changed accordingly. Still nothing predicted on exam #5.
Parent rule: `docs/wiki/prereg-r13.md` section 6 (pick, T, decision rule). This file adds the mechanics. Code commit: `c1d26e6`.

## 1. Question and bar (frozen, from prereg-r13 section 6)

May R13 replace shipped 0.2.0 as the model rwxmap ships? Two models, same rows, no tuning on exam #5. **R13 passes only if, on BOTH paths, it has no more too-loose AND no fewer exact than 0.2.0 at T 0.844:**

1. **Product path**: rwxmap's real CLI `secondPass`, mode a, lower only at top-letter p >= 0.97, **mechanical v4**, run by rwxmap on our prediction files. Numbers are rwxmap's.
2. **Standalone**: the model's own letter on every row (argmax of r = 1 - p_changes, w = p_changes - p_is_x, x = p_is_x), no mechanical letter, no second pass. `m1/exam5-score.py`.

Letters are ordered r < w < x; a letter below the truth is too loose, above is too tight (same definitions as `m1/r13-valpick.py`). Equal counts pass; any one of the four comparisons worse fails. If it fails, 0.2.0 stays and nothing is claimed. The gate config is rwxmap's CLI `secondPass`, not `a_none` (the exam #4 prereg error).

## 2. Models

| | 0.2.0 (baseline) | R13 (candidate) |
|---|---|---|
| model string (what the engine returns) | `rwxlite-0.2.0+8503b655` | `rwxlite-0.3.1+bbe1997d` |
| T | 0.844 (the default; its manifest carries none), **not refit** | 0.991463 (val fit, prereg-r13 step 1; `docs/wiki/findings.md`) |
| text format | 1 (manifest has no `textFormat`) | 1 (manifest says 1 explicitly) |
| precision / batch | fp32, batch 1 | fp32, batch 1 |
| manifest | `manifest-exact.json` | `manifest-exact.json` |
| files | `data/m1/release/` (= the GitHub v0.2.0 assets) | `data/m1-r13/` |

**The R13 version `0.3.1` is a PLACEHOLDER.** The model string contains the manifest version, so changing it changes the string and the manifest hash. It was picked as the next free minor line (a local tag `v0.3.0` already exists for the unreleased r11 candidate). If the user or rwxmap want another version, run `node m1/manifest-r13.mjs write <x.y.z>` and re-do sections 2, 6 and the package hash **before** any prediction is made. `exam5-score.py` hard-codes both model strings; it would then change too, and its hash with it.

The 0.2.0 fp32 weights are not selected by a flag of the engine: the package ships no models. A model directory holds the files; `loadAnswerer({dir, manifestFile})` picks the manifest (default `manifest.json` = int8-pc; `manifest-exact.json` = fp32). rwxmap's cache does the same with its own model directories.

### Fingerprints (sha256)

R13 training checkpoint `data/round13/models/R13/model.safetensors`: `d16276d8b0ff93221821e2c3bd107b7d6898a8804bba93c40a2f4b06bbd6b30d` (checked by `export_r13.py`).

| file | 0.2.0 | R13 |
|---|---|---|
| manifest-exact.json (fp32, **counts**) | `a484251cd4daf9c6fc7c8d2cb3f4a43f0cbdd6f4447d2c9ff65721a2f767b774` | `c6bac86970888049952305f72434abe5c9d8f854224a5537f14e5a428a977739` |
| model-fp32.onnx | `8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b` | `bbe1997d43020724f9eab9e42e8f6337e9640fe46f764b6fceac1eb1d000a3cf` |
| vocab.txt | `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` | `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` |
| manifest.json (int8-pc, information only) | `10407b787fae2cadc318780a8c4ad171dc07af1389129c284bfd85c54f6b38bc` | `e8477a1595578eec1e45020277319877d45cfb809785b22eaeb83bfb66c0a5b8` |
| model-int8-pc.onnx (information only) | `8ad0a182b37237adc819bda2c03c01f0cb0e40afc2b20bdacb06193cd62a8844` | `984714f0342ce551779f0ed9d95be57f71ab30b2ef72baec1d9818ce96d465d7` (model string `rwxlite-0.3.1+984714f0`) |

R13's ONNX files are `data/` (gitignored, not committed, as for r11 and r12); `export-sha.json` and these hashes are the record. The export is not guaranteed byte-reproducible; the hashes above are of the files used.
R13 manifest-exact.json: `{"version":"0.3.1","modelFile":"model-fp32.onnx","model":"rwxlite-0.3.1+bbe1997d","temperature":0.991463,"textFormat":1,"files":{...}}`.

### Text builder

The model text is built by `formatText` in `src/text.js` inside the engine (`src/answerer.js` `checkRequest`), format 1, the path the package ships. `src/text.js` on `dev` adds format 2 and `src/answerer.js` adds manifest `temperature`/`textFormat` since the published 0.2.1; **format 1 is unchanged**: `formatText` of v0.2.0, v0.2.1 and `dev` gives identical strings on all 112,564 round 13 train+val+v3eval rows (checked), and the published 0.2.1 engine gives bit-identical 0.2.0 fp32 p to `dev`'s on the smoke rows. The published 0.2.1 engine cannot run R13 (no manifest `temperature`); the candidate package (section 5) is built from `dev`.
`src/` sha256: `answerer.js` `a930ec1b08cc3599f2a67f477270e9a47e8f55d07f4764691018bd71a1cfed9e`, `text.js` `e1add2e9a902c3e1fc19015ea533be10f40e7eb1eab7802a3e241fe5a57617e3`, `tokenizer.js` `6f672cba5509256e074a7da348e98afff4a4a613dff6aa5bca83c5a13c5c2d32`, `index.js` `689ecb554dd4d1ba5987917a88983ab2b47dd478057abd802cb327160d2c800e`.

### Parity (R13, 598 val rows = every 7th, `m1/export_r13.py` + `m1/manifest-r13.mjs`, T 0.991463)

| comparison | max abs dp | argmax differences |
|---|---|---|
| Node engine fp32 vs Python onnxruntime fp32 | 2.7e-16 | 0 |
| Node engine int8-pc vs Python onnxruntime int8-pc | 3.3e-16 | 0 |
| Python ORT fp32 vs PyTorch fp32 | 5.9e-7 | 0 |
| Python ORT int8-pc vs ORT fp32 (information) | 0.145 | 4 |

Node `formatText` equals the stored val text on 598 of 598 rows (trailing whitespace after a 400-char description cut ignored; 3 rows). Intra-op threads (1 vs 4) gave byte-identical CSVs on the 105 smoke rows.

## 3. Inputs (frozen)

- rwxmap `data/exam5-2026-11-07/ops.csv`, header exactly `id,provider,method,path,operationId,summary,description`, ids `ex5-0001...`, 1,443 rows, 7 vendors, sha256 **`f6e245ed8e6953b8a7170a0bf6b6a371860460fc7206db6a5cbe23fbba1f26ea`** (equals `ops.csv.sha256` there). Inputs and vendor list frozen at rwxmap commit `23a2b13`. Descriptions are real (multi-line, quoted CSV); the predict script reads RFC 4180.
- Leakage check on our side: clean, `docs/wiki/exam5-leakage.md` (commit `33b484f`).
- **Lean source (changed on 2026-11-07).** The model reads the mechanical letter (class, rule) as the first words of its input. rwxmap sends `lean.csv` with the exam (header `id,class,rule,marker`, one row per op in ops.csv order, plus `lean.csv.sha256`), produced by rwxmap `poc/mech-v4/lean.mjs` at commit `94f6cc4` (mech-v4 core unchanged since `40fe161`). `exam5-predict.mjs` takes `--lean lean.csv`, verifies its sha256 against `lean.csv.sha256`, the header, and that ids and order equal ops.csv, and feeds class and rule **exactly as given** (no alias, no edit). The old path (import rwxmap's `classifyRow` via `--rwxmap-dir`) is removed. The same lean.csv is fed to 0.2.0; it too reads the three v4 rule names it never saw, unaliased. The marker (settled|tight|loose) is not read by predict; it is the review column of the product-path replica in `exam5-score.py --mech`.
- **No-alias decision** (section 8, decided on val before the draw): rule names fed as is; `src/text.js` still applies its own `credential-set` to `cant-undo-verb` alias, nothing else.
- **Text from ops fields.** The engine builds the text with `src/text.js` `formatText` from the ops.csv fields as they are (method, path, operationId, summary, description; QUERY printed as GET inside `formatText`). Nothing else is done to them. On val, the ops file for rwxmap had an empty description, so the parity run below filled it with the stored text's `desc:` segment, the way `m1/r13-v4lean-check.mjs` does; exam ops have real descriptions and use them directly.
- **Val parity of the new predict path (2026-11-07).** `exam5-predict.mjs` on the val ops (description filled as above, 4,180 rows) with `data/round13/v4-lean-val.csv` (sha256 `96e15be2048842205f5b619a3e2a684ad6977e173838a5a2f023a1bb403193f6`) gave a CSV **byte-identical** to the section 8 `asis` output `p-asis.csv` (4,180 rows, every p bit for bit).
- `truth.csv` (id,label) comes last; its sha256 is agreed with rwxmap before scoring: **TBD**. Exam `lean.csv` sha256: `93a76c5fad8f5baceecef4c087a95e03f070addeabbab1e356253221a09eb39d` (1,443 rows, markers settled 796 / tight 372 / loose 275; rwxmap commit `bbd9ab4` records the hash; the predict script refuses a file that does not match its `.sha256`).

## 4. Procedure

1. This file and the code are committed (this commit; hashes in section 6).
2. rwxmap delivers lean.csv + lean.csv.sha256 (ops.csv is already frozen). We fill the TBDs.
3. Predict, no truth (one run per model, fp32, batch 1, exclusive create so a file is never overwritten):
```
node m1/exam5-predict.mjs <ops.csv> data/m1-r13 predictions-r13.csv --lean <lean.csv> --expect-model rwxlite-0.3.1+bbe1997d
node m1/exam5-predict.mjs <ops.csv> data/m1/release predictions-v020.csv --lean <same lean.csv> --expect-model rwxlite-0.2.0+8503b655
```
   Contract CSV: UTF-8, LF, header `id,model,p_is_x,p_changes`, one row per op in ops.csv order, p as `Number.prototype.toString`, `p_changes = p(w)+p(x)`. The script refuses a wrong ops.csv sha256, a different header, a non-finite p, a p outside [0,1], or `p_changes < p_is_x`. An int8 file (`--manifest manifest.json`, to a differently named out file) may be added as information; fp32 counts.
4. The sha256 of both prediction CSVs (and both `.lean.csv`) go into `docs/wiki/exam5-predictions.sha256` and the table in section 6, committed **before** truth is opened. rwxmap replays our CSVs through its CLI and checks they reproduce (it can run the candidate package of section 5 itself: same p bit for bit).
5. rwxmap shares `truth.csv`. Scored **once**: rwxmap's `secondPass` per-row letters for both models (columns `id,letter`, plus the same `lean.csv` as `--mech` for an optional replica check), and ours:
```
python3 -I m1/exam5-score.py --ops <ops.csv> --truth <truth.csv> --truth-sha256 <agreed> --pred-r13 predictions-r13.csv --pred-v020 predictions-v020.csv \
  --sha-list docs/wiki/exam5-predictions.sha256 --out results.json --sp-r13 <letters> --sp-v020 <letters> [--mech <mech-v4.csv>]
```
   It refuses a truth file whose sha256 differs, prediction files that differ from the committed list, ids or order different from ops.csv, a wrong model string, and an existing `--out`. Verdict GO only if both paths pass section 1; without rwxmap's letters it prints INCOMPLETE.
6. The verdict, both tables and every too-loose row go into the findings. After both sides have scored, **exam #5 is burned** and may be training data. A GO is the user's release decision (release order in `.claude/remember/MEMORY.md`), not an automatic one.

## 5. Candidate package (scratch, nothing published)

Built from `dev` `src/` in a scratch copy with `version` set to `0.3.1` (the repo's `package.json` stays `0.2.1`): `npm pack --ignore-scripts` after `tsc -p tsconfig.build.json`; 14 files. Tarball `rwxlite-0.3.1.tgz`, sha256 `698c0191a772879ff424875f062fd54810dbd0eb7310b2bd8bb077c67476f7c0` (rebuilt from scratch on 2026-11-07 after the scratch dir was lost: same hash). Durable copy: `data/m1-r13/rwxlite-0.3.1.tgz` (gitignored with the rest of `data/`). A fresh `npm install` of it plus `loadAnswerer({dir, manifestFile})` gave CSVs byte-identical to `exam5-predict.mjs` for both models on the smoke rows. The package carries no model files; the R13 files are handed over as the directory `data/m1-r13/` (hashes in section 2).

## 6. Hashes and placeholders

Code (this commit; `exam5-predict.mjs` and `exam5-score.py` were changed from `c1d26e6` for the lean file and the marker column):

| file | sha256 |
|---|---|
| `m1/exam5-predict.mjs` | `fe1172dfdddfb4fe6cf3a71779fd733bd12b9db403fa712eb4941303a0782d86` |
| `m1/exam5-score.py` | `41cde546623fefc5b907b44de6abc55a0a1423eb27be03efeda422ac76ce031c` |
| `m1/export_r13.py` | `4ecec616a4c3c3ec6804bce074ec2b2e7894d3c961fa79fa3e7f194b05f71938` |
| `m1/manifest-r13.mjs` | `756ab27de24142c8d038038f66ca0816f88947e526a96cc4a4875af752f931af` |
| `m1/r13-v4lean-check.mjs` | `2134e346d2bff042106d192c65f43f8737cc2269392d18f47c64034a26fa30fe` |
| `m1/r13-v4lean-score.py` | `7f2f3b83a3d9a8dc25aea46e2a649d30e2973d1e36405a3cdacb54c1c7169095` |
| `m1/r13-valpick.py` (the replica `exam5-score.py` copies) | `82ec34bde2ce6e1a132b7084e6b69e92a4d1828e2b7dd744585b42e8881575ed` |

Predictions and lean hashes: section 10. Truth sha256 `TBD` (agreed with rwxmap before scoring).

## 7. Not allowed once predictions exist

No change of model file, manifest, T, 0.97 line, text format, tokenizer, batch size, code, bar. No re-running predict to see if it changes (the script refuses to overwrite; deleting outputs to get around that is a breach). No opening `truth.csv` before the prediction sha256s are committed. No scoring more than once; a rerun only for a crash or a row-join bug, recorded with the reason, same predictions. No choosing a model, T, config or bar after seeing a number; no adding a model (R13-L3 and R13-L3-t2 are not tried). Anything a result suggests needs a new exam with new vendors.

## 8. v4 lean names (decided on val before draw)

Question: rwxmap's mechanical v4 emits three rule names R13 never saw in training. Does R13 do better with them fed as is, or aliased to v3-era names? Decided on the 4,180 val rows only (not exam #5 data), before the exam draw. Whichever variant wins is then used for R13's exam #5 predictions (the lean text the model reads); 0.2.0 is untouched.

**Trained rule names (R13 train.jsonl, lean letter / method counts):** `cant-undo-verb` x: POST 1984, PUT 150, PATCH 29 · `cant-undo-verb-summary` x: POST 41, PUT 7, PATCH 6 · `floor-post` x: POST 22907 · `method` r: GET 45832, QUERY 4258, HEAD 2 · `method-delete` x: DELETE 10454 · `method-floor` w: PUT 6135, PATCH 5851 · `modify-verb` w: POST 2081 · `modify-verb-summary` w: POST 78 · `read-verb` r: POST 2655 · `read-verb-anywhere` r: POST 198. (`credential-set` is already aliased to `cant-undo-verb` inside `src/text.js`; unchanged.)

**Alias mapping (frozen, `ALIAS` in `m1/r13-v4lean-check.mjs`; `src/text.js` not edited):**

| v4 name (meaning, letter) | alias target | reason |
|---|---|---|
| `path-x-word` (PUT/PATCH/POST raised or kept at x, tight; x) | `cant-undo-verb` | the only trained x rule on PUT/PATCH, and x on POST; same stand-in already used for `credential-set` |
| `content-noun` (POST lowered to w, loose; w) | `modify-verb` | the only trained w rule on POST |
| `get-action` (GET raised to x; x) | `cant-undo-verb` | x for a verb-named action; x on GET was never trained under any name, so this is the closest x-by-verb rule |

The script stops if a v4 row carries a different letter than the target was trained with (x for `cant-undo-verb`, w for `modify-verb`). Other unseen names are passed as is and listed.

**Procedure.** rwxmap's producer: `poc/mech-v4` at rwxmap commit `40fe161`; it classifies the val ops file below and returns `lean.csv` (`id,class,rule,marker`, marker = settled|tight|loose, ops order). Val ops file (rwxmap's exam format, description empty because the raw description is not kept and rwxmap's mechanical never reads it, QUERY written as GET): `data/round13/val-ops-for-rwxmap.csv` (gitignored with the rest of `data/`), 4,180 rows, sha256 `efa3c5d9009757cd24f8ab75c440f7787adab3eea57bf1b8dae80c99b3339413`; copy handed to rwxmap as `.claude/scratchpad/rwxlite-val/ops.csv` with the same hash.
1. `node m1/r13-v4lean-check.mjs --val data/round13/val.jsonl --lean lean.csv --variant asis --out p-asis.csv`, then `--variant alias --out p-alias.csv` (published engine, fp32 `data/m1-r13`, batch 1; each row's lean replaced by the v4 class and rule).
2. `python3 -I m1/r13-v4lean-score.py --val data/round13/val.jsonl --lean lean.csv --asis p-asis.csv --alias p-alias.csv`. It needs the marker column and stops without it. Reports right / too loose / too tight standalone and on the product path (mode a replica, lower only at p >= 0.97 on rows with marker tight or loose, `credential-set` never lowered), with R13 on the v3 leans as context (product 3,776 / 74 / 330, standalone 3,967 / 162 / 51).

**Pick rule (frozen):** fewest too loose on the product path, then most right, ties to `asis`. Run once on val; no other mapping is tried.

**Script sha256 (smoke-tested on fake leans in scratch: asis and alias on v3 leans give bit-identical p to the engine on the parity-rows state/lean path, 50 of 50; renamed leans through alias reproduce the v3 p bit for bit, 20 of 20):**

| file | sha256 |
|---|---|
| `m1/r13-v4lean-check.mjs` | `2134e346d2bff042106d192c65f43f8737cc2269392d18f47c64034a26fa30fe` |
| `m1/r13-v4lean-score.py` | `7f2f3b83a3d9a8dc25aea46e2a649d30e2973d1e36405a3cdacb54c1c7169095` |

**Results (run once on val, scripts and mapping unchanged from `ee9765e`).** Leans: rwxmap `poc/mech-v4/lean.mjs` at commit `94f6cc4` (mech-v4 core unchanged since `40fe161`), `data/round13/v4-lean-val.csv`, sha256 `96e15be2048842205f5b619a3e2a684ad6977e173838a5a2f023a1bb403193f6` (checked against rwxmap's `lean.csv.sha256`; ids and order equal the val ops file; classes r 2426 / w 728 / x 1026; markers settled 2790 / tight 639 / loose 751; new names path-x-word 95, content-noun 58, get-action 1). Right / too loose / too tight:

| R13, val | product (mode a, 0.97) | standalone |
|---|---|---|
| v3 leans (context) | 3,776 / 74 / 330 | 3,967 / 162 / 51 |
| v4 leans, asis | 3,815 / 76 / 289 | 3,969 / 161 / 50 |
| v4 leans, alias | 3,814 / 78 / 288 | 3,968 / 158 / 54 |

**Pick: asis** (fewest too loose on the product path: 76 vs 78). The two variants differ by 2 too loose and 1 right on the product path, i.e. within noise; asis wins on the frozen rule and the tie preference. No unseen rule names other than the three were found.

The 154 rows with new rule names (product / standalone, right / too loose / too tight; the 0.97 rule lowered none of them in either variant, all 154 were sent):

| | asis product | asis standalone | alias product | alias standalone |
|---|---|---|---|---|
| path-x-word (95) | 86 / 0 / 9 | 87 / 4 / 4 | 86 / 0 / 9 | 86 / 0 / 9 |
| content-noun (58) | 52 / 5 / 1 | 51 / 6 / 1 | 51 / 7 / 0 | 51 / 7 / 0 |
| get-action (1) | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 |
| all 154 | 139 / 5 / 10 | 139 / 10 / 5 | 138 / 7 / 9 | 138 / 7 / 9 |

## 9. For rwxmap's candidate addendum

Equivalent of `exam-prereg-exam4.md` section 3 for R13. Nothing is created or published; the tag is proposed only.

- **Tarball:** `/home/hamr/PycharmProjects/rwxlite/data/m1-r13/rwxlite-0.3.1.tgz`, sha256 `698c0191a772879ff424875f062fd54810dbd0eb7310b2bd8bb077c67476f7c0`, 14 files (`src/`, `types/`, README, LICENSE, CHANGELOG, package.json), no model files. Its `src/` is byte-identical to `src/` on `dev` (checked with `diff -r` after extracting). Its `package.json` says `0.3.1` (built in a scratch copy); `package.json` on `dev` stays `0.2.1`.
- **How to install:** from the tarball, not from a git ref: `ONNXRUNTIME_NODE_INSTALL=skip npm install <path>/rwxlite-0.3.1.tgz`. A git ref of `dev` would install version 0.2.1 and its `package.json` would not match the manifests' version `0.3.1`. (Tested: fresh install, `loadAnswerer({dir, manifestFile: 'manifest-exact.json'})`, byte-identical output to `exam5-predict.mjs`.)
- **Package ref (source of the tarball's `src/`):** rwxlite `dev` commit `f7456a2acc66ce84fd8c87d7426c9001bab8ceb7`, the last commit that changed `src/`; `src/` is identical at every later `dev` commit, including the commit that holds this file. That ref gives the code, not the version number.
- **Proposed tag:** `v0.3.1` (**PROPOSED, NOT created**; `v0.3.0` is the unreleased r11 candidate).
- **Model directory:** `/home/hamr/PycharmProjects/rwxlite/data/m1-r13` (R13).
- **R13 files (sha256):**
  - `model-fp32.onnx` `bbe1997d43020724f9eab9e42e8f6337e9640fe46f764b6fceac1eb1d000a3cf`
  - `model-int8-pc.onnx` `984714f0342ce551779f0ed9d95be57f71ab30b2ef72baec1d9818ce96d465d7`
  - `manifest.json` (int8-pc) `e8477a1595578eec1e45020277319877d45cfb809785b22eaeb83bfb66c0a5b8`
  - `manifest-exact.json` (fp32) `c6bac86970888049952305f72434abe5c9d8f854224a5537f14e5a428a977739`
  - `vocab.txt` `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3`
- **R13 model strings:** fp32 (gate) `rwxlite-0.3.1+bbe1997d`; int8 (information) `rwxlite-0.3.1+984714f0`. **T 0.991463** (in both manifests as `temperature`), `textFormat` 1.
- **0.2.0 for reference** (`data/m1/release/`, tag `v0.2.0`): `manifest-exact.json` `a484251cd4daf9c6fc7c8d2cb3f4a43f0cbdd6f4447d2c9ff65721a2f767b774`, `manifest.json` `10407b787fae2cadc318780a8c4ad171dc07af1389129c284bfd85c54f6b38bc`, `model-fp32.onnx` `8503b655a25202f8d01ced40ab685c34b287f70db8c0651528ca476f1470a48b`, `model-int8-pc.onnx` `8ad0a182b37237adc819bda2c03c01f0cb0e40afc2b20bdacb06193cd62a8844`, `vocab.txt` `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3`; model strings fp32 `rwxlite-0.2.0+8503b655`, int8 `rwxlite-0.2.0+8ad0a182`; T 0.844 (no `temperature` in its manifests: the engine default).
- **The command, same shape as exam #4 (rwxmap's flag names):** `--cand-ref f7456a2acc66ce84fd8c87d7426c9001bab8ceb7 --cand-tag v0.3.1 --cand-models /home/hamr/PycharmProjects/rwxlite/data/m1-r13` with the five `--cand-file` hashes above, `--cand-model-fp32 rwxlite-0.3.1+bbe1997d --cand-model-int8 rwxlite-0.3.1+984714f0`. Because `package.json` at that ref says 0.2.1, rwxmap should install the tarball above for the candidate instead of resolving the ref.
- **Version is a placeholder** (see section 2): a different version changes both model strings and both manifest hashes; all of this is then re-agreed before any prediction.

## 10. Predictions frozen (2026-11-07)

Run per section 4 step 3, code unchanged since `bf4afab` (`m1/exam5-predict.mjs` sha256 `fe1172df...2d86` verified before the run), fp32, batch 1, `--lean` = rwxmap's lean.csv above, outside `data/` nothing written. Files are in `data/exam5-2026-11-07/` (gitignored, **not committed**, and not shown to the labellers: they hold model p and mechanical letters). Both CSVs: header `id,model,p_is_x,p_changes`, 1,443 rows in ops.csv order, every p finite with 0 <= p_is_x <= p_changes <= 1. Each `.lean.csv` equals rwxmap's lean.csv on (id,class,rule) for all 1,443 rows. Run time about 70 s for both models together. Hashes are also in `docs/wiki/exam5-predictions.sha256`, which `exam5-score.py --sha-list` checks.

| file | sha256 |
|---|---|
| `predictions-r13.csv` (`rwxlite-0.3.1+bbe1997d`, T 0.991463) | `1633417853a141cab079513dc78e8b538714bd6f46b729adb95876b34d3a73de` |
| `predictions-v020.csv` (`rwxlite-0.2.0+8503b655`, T 0.844) | `906c0edd1a237172b3e08884f87faa538be7aacee64a633399f55905aa14f162` |
| `predictions-r13.csv.lean.csv` | `e17922ad3b0c1cb90604af2d9c03dd60bcf2fde73fab8434cbaf8d1bcc370d80` |
| `predictions-v020.csv.lean.csv` | `e17922ad3b0c1cb90604af2d9c03dd60bcf2fde73fab8434cbaf8d1bcc370d80` |

## 11. Results (2026-11-07)

**Inputs.** Truth: rwxmap `data/exam5-2026-11-07/truth.csv`, rwxmap commit `bfc05c1`, sha256 `772ca84edf1e537f5e9b162229f59e3b0c439e55ba8f6f21f3070e058c70005a` (verified before it was read; 1,443 rows; r 671 / w 354 / x 418). rwxmap's secondPass letters (CLI, mode a, mechanical v4 lean as sent, 0.97): `letters-a-r13-v4.csv` sha256 `bbe8ab2b63085ba3b40e034cc04d2ad46445dad57a90dd1c2355639f8b4f522e`, `letters-a-020-v4.csv` sha256 `d681b24ebf65ab57a25eb5a87696556ab22cbec97f51463977044606e2094b15`. Parity PASSED on rwxmap's side (rwxmap `36fb827`): the replay of our `predictions-r13.csv` equals the CLI run on all 1,443 rows. Prediction hashes as in section 10 (verified again before scoring); `m1/exam5-score.py` sha256 `41cde546...031c`, unchanged.

**Deviation (recorded).** `exam5-score.py` was run twice with the same script, predictions and truth. The first run (standalone, `--mech` only, `--out results.json`) was made before rwxmap's letters existed and printed INCOMPLETE. It refuses an existing `--out` by design, so the final run used a new name, `--out results-final.json`. That is the only difference; the standalone numbers are identical in both runs.

**Numbers** (right / too loose / too tight, 1,443 rows):

| model | standalone | product (rwxmap CLI secondPass, mode a, mech v4) |
|---|---|---|
| R13 | 1,283 / 64 / 96 | 1,220 / 37 / 186 |
| 0.2.0 | 1,281 / 141 / 21 | 1,272 / 94 / 77 |

Our product numbers equal rwxmap's reported ones (a-r13-v4 1220/37/186, a-020-v4 1272/94/77): no difference. The secondPass replica of `m1/r13-valpick.py` (script `--mech` check) agrees with rwxmap's CLI letters on all 1,443 rows for both models (0 differing rows). Second pass at p >= 0.97 lowered 23 rows for R13 and 148 for 0.2.0 (raised 49 and 8).

**Frozen bar.**
- Standalone: R13 too loose 64 <= 141, right 1,283 >= 1,281: **pass**.
- Product: too loose 37 <= 94 passes, right 1,220 >= 1,272 fails (52 fewer): **fail**.
- Script verdict line: `VERDICT: NO-GO`.

**Verdict: NO-GO.** R13 does not replace 0.2.0; 0.2.0 stays, nothing is released, nothing is claimed beyond the numbers above. Exam #5 is burned for both sides and may be used as training data only. Details and per-vendor table: `docs/wiki/findings.md`, entry 2026-11-07.

