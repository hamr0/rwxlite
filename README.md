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
| Fine-tuned MiniLM | trained, exam failed (too loose) | 22.7M params, 90.9 MB fp32, about 22-28 ms/op in fp32 PyTorch; 95.9% exact, 0.84% too loose on the exam |
| int8 ONNX export + Node answerer | *planned (M1)* | the in-process answerer that speaks Jev's JSON |
| Abstain threshold | measured, not built | "no answer when not confident"; the contract rule asks on lowerings under 0.97 and trusts raises and keeps: fresh exam 92.6% right, 5 too loose, 7.8% asked |
| rwxmap integration | *planned (M2)* | mechanical leans first, model moves contested rows |

Input is OpenAPI operations only: method, path template, operationId, summary, description.

## It tells you the truth

As of 2026-11-03, rwxlite is in module 0 and not released.

- **Labels are measured.** The label recipe passed a fresh blind gate at 96.5% exact and 0.7% too loose, against 79.3% and 1.2% for mechanical alone. Two findings went back into rwxmap (D129 two-step POST, D131 credential rule).
- **The model failed its go/no-go exam, on one line.** The fine-tuned MiniLM was scored once on 4,279 operations from vendors it never saw (cloudflare, pagerduty, sentry). It answered 95.9% exact, ahead of mechanical + Jev (93.0%) and mechanical alone (82.3%). But 0.84% of its answers were too loose (36 rows), over the 0.5% line set by Jev. Most of those are Cloudflare "create" calls that move money or start jobs, which it confidently called editable. Next step is open.
- **Asking helps, but wasn't the pass/fail check.** When the model answers only at 95% confidence or above and asks on the rest, it answers 90.2% of rows at 98.7% exact and 0.47% too loose. That was reported, not pre-registered, so it doesn't count as a pass. Full table in the [PRD](docs/product/prd.md#m0-exam-result-2026-11-03-no-go).

**How to read "ask".** Every operation lands in one pile: right, too loose (called safer than it is, the dangerous one), too tight (called riskier, annoying but safe), or asked (the user decides). The confidence bar only moves rows into "asked". On the 4,279-row exam:

| bar | right | too loose | too tight | asked | what the asks held (right + loose + tight) |
|---|---|---|---|---|---|
| none | 4104 | 36 | 139 | 0 | |
| 70% | 4064 | 36 | 69 | 110 | 40 + **0** + 70 |
| 90% | 3961 | 21 | 37 | 260 | 143 + **15** + 102 |
| 95% | 3812 | 18 | 31 | 418 | 292 + **18** + 108 |

At 70% all 36 dangerous mistakes are still answered: the model was sure of them. From 90% the asks start catching them, at the cost of asking on 6% to 10% of operations.

- **Training labels aren't the cause.** Two blind labellers re-labelled 1,200 training rows of the failing shapes: the training labels were too loose on only 32 (2.7%). The exam misses are mostly one vendor's pattern (Cloudflare billing and jobs).
- **Fresh exam: missed by one row.** On 949 operations from four vendors nobody had trained on (Coolify, WorkOS, Lago, Resend), with lowerings flagged and asked under 97% confidence: 92.6% right, 7.8% asked, 5 too-loose answers (0.57%) against a line of 4 (0.5%). The lowering flag caught every wrong lowering; the 5 misses are credential updates and logouts that the mechanical rules already call too safe. Mechanical alone: 77.6% right, 6 too loose. Details in the [PRD](docs/product/prd.md#fresh-exam-result-2026-11-03-no-go-by-one-row).
- **"No answer if not confident" is measured, not built.** The model returns probabilities today. The "ask" rule exists only in the scoring scripts.
- **"About 24 MB int8" is an estimate** for the neural model. The baseline is already about 24 MB. The int8 export is not built.
- **Limits.** OpenAPI operations only. No request bodies, no query values, no hosts without a spec.

## Docs

- **[PRD](docs/product/prd.md)** — scope, milestones, open questions.
- **[Findings](docs/wiki/findings.md)** — what was measured and what was decided.
- **[Classifier training](docs/wiki/classifier-training.md)** — how training works and how the model answers.

## License

Apache License 2.0. See [LICENSE](LICENSE).
