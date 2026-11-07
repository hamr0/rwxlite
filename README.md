```
   rwxlite
   three questions in ──→ JSON out ──→ or no answer
   a small, local gut check for what an API call can do
```

<p align="center">
  <a href="https://github.com/hamr0/rwxlite/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/hamr0/rwxlite/ci.yml?label=CI" alt="CI"></a>
  <img src="https://img.shields.io/github/package-json/v/hamr0/rwxlite?label=version&color=2a4f8c" alt="version (auto from package.json)">
  <img src="https://img.shields.io/badge/classifier-rwxlite--0.3.1%2B984714f0-2a4f8c" alt="classifier: rwxlite-0.3.1+984714f0 (int8 default)">
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

- **With [rwxmap](https://github.com/hamr0/rwxmap).** rwxmap's full flow: the mechanical rules give the first letter, and rwxlite only moves the contested rows, at rwxmap's 0.90 cut. rwxlite answers in Jev's JSON, so rwxmap only swaps the client. To read OpenAPI files, get finished verdicts, or gate the API calls an agent makes, use rwxmap.
- **On its own.** See [Using rwxlite on its own](#using-rwxlite-on-its-own) below.

The model outputs three probabilities, p(r), p(w) and p(x). Every Jev question is arithmetic on them: `isX` is p(x), `changes` is p(w) + p(x).

## How well it does

Tested once, on 1,443 operations from 7 vendors that no model had seen (Front, PlanetScale, Paddle, Hookdeck, FusionAuth, Semaphore UI, Weaviate). Two independent AI labellers set the answers, and a human ruled on every disagreement.

| | right | too loose | too tight |
|---|---|---|---|
| **On its own** (rwxlite 0.3.1, int8 default, given rwxmap's mechanical first guess) | 1,280 (88.7%) | 64 (4.4%) | 99 (6.9%) |
| **With rwxmap** (full flow, rwxlite moves contested rows at the 0.90 cut) | 1,269 (87.9%) | 40 (2.8%) | 134 (9.3%) |

- **Too loose** means it called an operation safer than it is. This is the costly mistake.
- **Too tight** means it called an operation riskier than it is. This is annoying but safe.
- The fp32 model on its own scores 1,283 / 64 / 96.
- The 0.90 cut belongs to rwxmap. It was tuned on this same test and on validation data, so it is not yet proven on vendors nobody has tested.
- Until rwxmap updates its pin, the released rwxmap still runs rwxlite 0.2.0 at a 0.97 cut.

It was trained on about 102,700 labelled API operations from about 900 public API providers, labelled under the wider x rule above. Speed is about 17-20 ms per operation on a laptop CPU.

## Install

```
ONNXRUNTIME_NODE_INSTALL=skip npm i rwxlite
```

Setting `ONNXRUNTIME_NODE_INSTALL=skip` avoids a 285 MB GPU download; the CPU build is enough. `onnxruntime-node` is an optional dependency.

The model files are not in the npm package. Download them from the [GitHub release](https://github.com/hamr0/rwxlite/releases) `v0.3.1` into one folder and point `dir` at it: `manifest.json`, `model-int8-pc.onnx` (23 MB) and `vocab.txt` for the default, or `manifest-exact.json`, `model-fp32.onnx` (91 MB) and `vocab.txt` for the fp32 "exact" option. Details and the sha256 values are in the guide.

## Using rwxlite on its own

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

rwxlite returns probabilities only. Turning them into a letter, or into "ask a human", is your decision, and the cut is yours. The full guide is **[docs/guide.md](docs/guide.md)**: loading the int8 or fp32 model, the request and the lean, the answer shape, worked examples, choosing your cut, and the other details (batching, `QUERY`, `credential-set`, limits).

## For contributors

The training, labelling and test scripts are in `m0/`, `m1/` and `train/`. They need a sibling checkout of [rwxmap](https://github.com/hamr0/rwxmap) and local data that is not in the repo. Background notes are in [docs/wiki/](docs/wiki/): [findings](docs/wiki/findings.md) and [classifier training](docs/wiki/classifier-training.md). Tests: `npm test`. Types: `npm run typecheck`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
