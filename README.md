```
                 ┌───────────┐     r  reads
  API call ───▶ │  rwxlite  │ ──▶ w  writes
                 └───────────┘     x  can't undo

  local · 23 MB · ~20 ms
```

<p align="center">
  <a href="https://github.com/hamr0/rwxlite/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/hamr0/rwxlite/ci.yml?label=CI" alt="CI"></a>
  <img src="https://img.shields.io/github/package-json/v/hamr0/rwxlite?label=version&color=2a4f8c" alt="version (auto from package.json)">
  <img src="https://img.shields.io/badge/classifier-rwxlite--0.5.0%2Bfac72395-2a4f8c" alt="classifier: rwxlite-0.5.0+fac72395 (int8 default)">
  <img src="https://img.shields.io/badge/license-Apache%202.0-2a4f8c" alt="license: Apache 2.0">
</p>

**A small local classifier that says whether an API operation reads (r), writes (w) or can't be taken back (x). Jev-shaped questions in, JSON out, probabilities only.**

Agentic automation is on the rise, and there's no solution in sight for controlling API access with guardrails. It's impossible to account for every possibility. Today's answers don't scale and don't adapt to different shapes: scoped MCPs, policies built on MCP hints that aren't widely adopted or accurate, accountability moved into rigid sandboxes, or pushed back to the consumer through fine-grained IAM or APIs scoped at creation. Meanwhile we're creating new open standards for agents (MCP, WebMCP, headless browsing) faster than we can guardrail them.

rwxlite is meant to solve that on the fly. You give it an API operation (method, path, name, summary, description). It gives back how likely each letter is. Free, local, responds in milliseconds, and the default model is about 23 MB.

## The three letters

- **r** - nothing changes.
- **w** - changes something that a later call can set back.
- **x** - a later call can't restore things. That includes whatever anyone did in between.

The x rule is wider than "destroys data". Handing out or widening access is x, because someone may already have used it before you take it back:

- Creating an API key or token is x.
- Turning on a setting that widens who can get in is x.
- Setting up a webhook that sends data to an outside URL is x.
- Creating a login user is x.
- Adding a member to a team or account is x.
- Narrowing access is w. If an access change could go either way (set or replace), it counts as x, to be safe. Policies that are not about access stay w.

Restarting, or stopping, starting or pausing a server, is w. Stopping a job in a way that loses its work is x.

## Two ways to use it

Every request needs a `lean`: a first-guess letter (r, w or x) and the rule behind it. rwxmap's mechanical rules produce it.

- **With [rwxmap](https://github.com/hamr0/rwxmap).** rwxmap's full flow: the mechanical rules give the first letter, and rwxlite only moves the contested rows, at rwxmap's 0.90 cut (mode a). rwxmap can also let rwxlite judge every row (mode b). rwxlite answers in Jev's JSON, so rwxmap only swaps the client. To read OpenAPI files, get finished verdicts, or gate the API calls an agent makes, use rwxmap.
- **On its own.** See [Using rwxlite on its own](#using-rwxlite-on-its-own) below.

The model outputs three probabilities, p(r), p(w) and p(x). Every Jev question is arithmetic on them: `isX` is p(x), `changes` is p(w) + p(x).

## How well it does

**Tested once on 1,821 operations from 6 APIs no model had seen**, scored on 2026-11-23 through rwxmap's real CLI (rwxmap `474ecb1`), with rwxlite 0.5.0 (fp32, `rwxlite-0.5.0+82fa50c3`).

| | right | too loose | too tight |
|---|---|---|---|
| **With rwxmap** (mode a, 0.90 cut) | 1,653 (90.8%) | 60 (3.3%) | 108 (5.9%) |
| **On its own** (rwxmap mode b, rwxlite judges every row, confidence 85) | 1,656 (90.9%) | 44 (2.4%) | 121 (6.6%) |
| **Rules only** (no model) | 1,556 (85.4%) | 73 (4.0%) | 192 (10.5%) |

- **Too loose** means it called an operation safer than it is. This is the costly mistake.
- **Too tight** means it called an operation riskier than it is. This is annoying but safe.
- Two Claude models (Sonnet and Opus) labelled every row blind, on the BRIEF-v4 rules plus the D141 and D143 (bookings are x) addenda. They agreed on 1,711 of 1,821 rows (94.0%), and a person ruled all 110 disagreements. Agreement between models reading the same rulebook shows consistency, not truth.
- Mode a is rwxmap's default: the rules answer first, and rwxlite moves only the contested rows, at a 0.90 cut. The previous model, 0.4.0, scored 1,631 / 65 / 125 on the same rows and cut, so 0.5.0 is better here (exact +22, too loose -5).
- Mode b has rwxlite alone judge every row. Under the confidence, a row becomes x and is marked for review. The 85 was picked on earlier tests. rwxmap's default is still 95, so pass `--confidence 85`.
- The default int8 model was not scored on this exam; the figures above are the fp32 model.

It was trained on 360,536 labelled API operations: about 300,000 (299,600) new ones from about 32,000 new vendors, about 60,000 re-used from the earlier sets, and a few hundred more (rows rwxmap re-ruled, exam #7's mistakes, 400 check rows). Labels came from three agreeing checks, else Sonnet, and rwxmap ruled the rows Sonnet was unsure about. Speed is about 17-20 ms per operation on a laptop CPU.

## Install

```
ONNXRUNTIME_NODE_INSTALL=skip npm i rwxlite
```

Setting `ONNXRUNTIME_NODE_INSTALL=skip` avoids a 285 MB GPU download; the CPU build is enough. `onnxruntime-node` is an optional dependency.

The model files are not in the npm package. Download them from the [GitHub release](https://github.com/hamr0/rwxlite/releases) `v0.5.0` into one folder and point `dir` at it: `manifest.json`, `model-int8-pc.onnx` (23 MB) and `vocab.txt` for the default, or `manifest-exact.json`, `model-fp32.onnx` (91 MB) and `vocab.txt` for the fp32 "exact" option. Details and the sha256 values are in the guide.

## Using rwxlite on its own

First download the five model files into one folder, as described in [Get the model files](https://github.com/hamr0/rwxlite/blob/main/docs/wiki/guide.md#2-get-the-model-files); without them the snippet below throws `ENOENT` on `manifest.json`.

```js
import { loadAnswerer } from 'rwxlite';

const a = await loadAnswerer({ dir: '/path/to/model-dir' });
const req = {
  state: { method: 'GET', path: '/v1/search', operationId: 'search', summary: 'Search records', description: '' },
  lean: { class: 'r', rule: 'method' },
  questions: { isX: '', changes: '' },
};
const out = await a.answer(req); // { model, answers: { isX: { noul }, changes: { noul } } }; throws on a no-answer
```

rwxlite returns probabilities only. Turning them into a letter, or into "ask a human", is your decision, and the cut is yours. The full guide is **[docs/wiki/guide.md](https://github.com/hamr0/rwxlite/blob/main/docs/wiki/guide.md)**: loading the int8 or fp32 model, the request and the lean, the answer shape, worked examples, choosing your cut, and the other details (batching, `QUERY`, `credential-set`, limits).

## For contributors

The training, labelling and test scripts are in `m0/`, `m1/` and `train/`. They need a sibling checkout of [rwxmap](https://github.com/hamr0/rwxmap) and local data that is not in the repo. Background notes are in [docs/wiki/](https://github.com/hamr0/rwxlite/tree/main/docs/wiki/): [findings](https://github.com/hamr0/rwxlite/blob/main/docs/wiki/findings.md) and [classifier training](https://github.com/hamr0/rwxlite/blob/main/docs/wiki/classifier-training.md). Tests: `npm test`. Types: `npm run typecheck`.

## License

Apache License 2.0. See [LICENSE](https://github.com/hamr0/rwxlite/blob/main/LICENSE).
