```
   rwxlite
   three questions in ──→ JSON out ──→ or no answer
   a small, local gut check for what an API call can do
```

**A small local classifier that says whether an API operation reads (r), writes (w) or can't be taken back (x). Jev-shaped questions in, JSON out, no answer if it isn't confident.**

> Status: module 0, research repo, **not released**. Parts of this page describe the plan. They are marked *planned*.

Agentic automation is on the rise, and there's no solution in sight for controlling API access with guardrails. It's impossible to account for every possibility. Today's answers don't scale and don't adapt to different shapes: scoped MCPs, policies built on MCP hints that aren't widely adopted or accurate, accountability moved into rigid sandboxes, or pushed back to the consumer through fine-grained IAM or APIs scoped at creation. Meanwhile we're creating new open standards for agents (MCP, WebMCP, headless browsing) faster than we can guardrail them.

rwxlite is meant to solve that on the fly. Jev-shaped three questions in, JSON out, no answer if it isn't confident. Use it on its own, or couple it with [rwxmap](https://github.com/hamr0/rwxmap) to replace Jev. Free, local, responds in milliseconds, quantized to int8 at about 24 MB (*planned*, see below).

## The three letters

- **r** — nothing changes.
- **w** — changes something a later call can set back.
- **x** — can't be taken back.

## Two modes

- **a. With rwxmap.** Mechanical rules lean first. The model only moves the contested rows. It answers in Jev's JSON, so rwxmap only swaps the client. *Planned (M2).*
- **b. Standalone.** One operation in, `{letter, p}` out. A low top probability is the "ask a human" signal. The threshold is yours. *Planned (M1).*

```json
// request (same as Jev's)
{ "state": { "method": "POST", "path": "/v1/search", "operationId": "search",
             "summary": "Search records", "description": "" },
  "model": "rwxlite-0.1.0",
  "questions": { "isX": "<the a7bc855 question text>" } }

// answer (same shape as Jev's)
{ "answers": { "isX": { "noul": 0.04 } },
  "model": "rwxlite-0.1.0+<weights-hash>" }

// standalone (mode b)
{ "letter": "r", "p": { "r": 0.91, "w": 0.07, "x": 0.02 }, "model": "rwxlite-0.1.0+<hash>" }
```

The model outputs three probabilities. Every Jev question is arithmetic on them: `isX` is p(x), `changes` is p(w) + p(x).

## Start here

This is a research repo for now. There is nothing to install.

- Read the [PRD](docs/product/prd.md) first.
- Mechanical labels: `node m0/mechanical.mjs`
- Training: `python3 train/build_dataset.py`, `train/baseline.py`, `train/finetune.py`, `train/tune_cuts.py`
- Gate scripts for the label exam live in `m0/`.

## What's inside

| Part | State | What it does |
|---|---|---|
| Label recipe | built, measured | rwxmap mechanical + Jev, per-method questions, two-step POST lower, credential rule |
| Baseline | trained | TF-IDF + logistic regression, 24 MB, about 1.5 ms/op |
| Fine-tuned MiniLM | trained, still tuning | 22.7M params, 90.9 MB fp32, about 22-28 ms/op in fp32 PyTorch |
| int8 ONNX export + Node answerer | *planned (M1)* | the in-process answerer that speaks Jev's JSON |
| Abstain threshold | *planned* | "no answer when not confident" |
| rwxmap integration | *planned (M2)* | mechanical leans first, model moves contested rows |

Input is OpenAPI operations only: method, path template, operationId, summary, description.

## It tells you the truth

As of 2026-11-03, rwxlite is in module 0 and not released.

- **Labels are measured.** The label recipe passed a fresh blind gate at 96.5% exact and 0.7% too loose, against 79.3% and 1.2% for mechanical alone. Two findings went back into rwxmap (D129 two-step POST, D131 credential rule).
- **Models are trained, not yet judged.** On tuning rows (leave-one-vendor-out) the baseline scores 91.0% exact, with too-loose equal to mechanical. MiniLM scores 92.0% exact, but its too-loose rate is above mechanical. Work continues. Neither has been scored on the go/no-go exam.
- **"No answer if not confident" is not built.** The model returns probabilities today. The abstain threshold is planned.
- **"About 24 MB int8" is an estimate** for the neural model. The baseline is already about 24 MB. The int8 export is not built.
- **Limits.** OpenAPI operations only. No request bodies, no query values, no hosts without a spec.

## Docs

- **[PRD](docs/product/prd.md)** — scope, milestones, open questions.
- **[Findings](docs/wiki/findings.md)** — what was measured and what was decided.
- **[Classifier training](docs/wiki/classifier-training.md)** — how training works and how the model answers.

## License

Licence: not chosen yet (see PRD open questions).
