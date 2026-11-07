# Pre-registration: shared clean exam #5, rwxlite side, candidate R13

**Status: DRAFT until the placeholders marked `TBD` are filled; FROZEN when this file is committed with the predictions' sha256s, before truth is opened.**
Written before the exam exists. Nothing here was run on exam #5 data: no ops.csv, no truth. The code was tested only on a synthetic ops.csv of 105 val rows (scratch, not committed) and on val/practice rows, which are R13's training data and decide nothing.
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

## 3. Inputs (not delivered yet)

`data/exam5-.../ops.csv` from rwxmap, header exactly `id,provider,method,path,operationId,summary,description`, ids `ex5-0001...`, plus `ops.csv.sha256`, spec files, `sources.json`. ops.csv sha256: **TBD** (`__OPS_SHA__`), rwxmap ref: **TBD** (`__RWXMAP_REF__`), rows: **TBD**. `truth.csv` (id,label) comes last; its sha256 is agreed with rwxmap before scoring: **TBD**.

The model reads the mechanical letter (class, rule) as the first words of its input. `exam5-predict.mjs` takes it from rwxmap's `classifyRow` in a rwxmap tree passed as `--rwxmap-dir` (QUERY read as GET), so **it must be the rwxmap ref that holds mechanical v4**; its HEAD is printed and goes into the findings. The lean it used is written to `<out>.lean.csv` (id,class,rule) so rwxmap can check it equals theirs.

## 4. Procedure

1. This file and the code (commit `c1d26e6`) are committed. Hashes of the code are in section 6.
2. rwxmap delivers ops.csv + ops.csv.sha256 (+ the rwxmap ref with mechanical v4). We fill the TBDs.
3. Predict, no truth (one run per model, fp32, batch 1, exclusive create so a file is never overwritten):
```
node m1/exam5-predict.mjs <ops.csv> data/m1-r13 predictions-r13.csv --rwxmap-dir <rwxmap tree at the ref> --expect-model rwxlite-0.3.1+bbe1997d
node m1/exam5-predict.mjs <ops.csv> data/m1/release predictions-v020.csv --rwxmap-dir <same tree> --expect-model rwxlite-0.2.0+8503b655
```
   Contract CSV: UTF-8, LF, header `id,model,p_is_x,p_changes`, one row per op in ops.csv order, p as `Number.prototype.toString`, `p_changes = p(w)+p(x)`. The script refuses a wrong ops.csv sha256, a different header, a non-finite p, a p outside [0,1], or `p_changes < p_is_x`. An int8 file (`--manifest manifest.json`, to a differently named out file) may be added as information; fp32 counts.
4. The sha256 of both prediction CSVs (and both `.lean.csv`) go into `docs/wiki/exam5-predictions.sha256` and the table in section 6, committed **before** truth is opened. rwxmap replays our CSVs through its CLI and checks they reproduce (it can run the candidate package of section 5 itself: same p bit for bit).
5. rwxmap shares `truth.csv`. Scored **once**: rwxmap's `secondPass` per-row letters for both models (columns `id,letter`, plus their mechanical v4 `id,class,rule,review` for an optional replica check), and ours:
```
python3 -I m1/exam5-score.py --ops <ops.csv> --truth <truth.csv> --truth-sha256 <agreed> --pred-r13 predictions-r13.csv --pred-v020 predictions-v020.csv \
  --sha-list docs/wiki/exam5-predictions.sha256 --out results.json --sp-r13 <letters> --sp-v020 <letters> [--mech <mech-v4.csv>]
```
   It refuses a truth file whose sha256 differs, prediction files that differ from the committed list, ids or order different from ops.csv, a wrong model string, and an existing `--out`. Verdict GO only if both paths pass section 1; without rwxmap's letters it prints INCOMPLETE.
6. The verdict, both tables and every too-loose row go into the findings. After both sides have scored, **exam #5 is burned** and may be training data. A GO is the user's release decision (release order in `.claude/remember/MEMORY.md`), not an automatic one.

## 5. Candidate package (scratch, nothing published)

Built from `dev` `src/` in a scratch copy with `version` set to `0.3.1` (the repo's `package.json` stays `0.2.1`): `npm pack --ignore-scripts` after `tsc -p tsconfig.build.json`; 14 files. Tarball `rwxlite-0.3.1.tgz`, sha256 `698c0191a772879ff424875f062fd54810dbd0eb7310b2bd8bb077c67476f7c0` (a second `npm pack` of the same scratch copy gave the same hash; it lives in the worker scratch dir, not in the repo). A fresh `npm install` of it plus `loadAnswerer({dir, manifestFile})` gave CSVs byte-identical to `exam5-predict.mjs` for both models on the smoke rows. The package carries no model files; the R13 files are handed over as the directory `data/m1-r13/` (hashes in section 2).

## 6. Hashes and placeholders

Code (committed at `c1d26e6`):

| file | sha256 |
|---|---|
| `m1/exam5-predict.mjs` | `dccafd098d54a1eecdd5d80cacecbdd68682d21602e5d643f4c8eb6ad68df7a7` |
| `m1/exam5-score.py` | `ed7d0173a7180577d892b1ac9e02613294b79fa8d6c21ff55cecc79803c53704` |
| `m1/export_r13.py` | `4ecec616a4c3c3ec6804bce074ec2b2e7894d3c961fa79fa3e7f194b05f71938` |
| `m1/manifest-r13.mjs` | `756ab27de24142c8d038038f66ca0816f88947e526a96cc4a4875af752f931af` |
| `m1/r13-valpick.py` (the replica `exam5-score.py` copies) | `82ec34bde2ce6e1a132b7084e6b69e92a4d1828e2b7dd744585b42e8881575ed` |

To fill before truth: ops.csv sha256 `TBD`; rwxmap ref `TBD`; `predictions-r13.csv` `TBD`; `predictions-v020.csv` `TBD`; `predictions-r13.csv.lean.csv` `TBD`; `predictions-v020.csv.lean.csv` `TBD`; truth sha256 `TBD`.

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

**Results: TBD** (asis `TBD`, alias `TBD`, pick `TBD`).
