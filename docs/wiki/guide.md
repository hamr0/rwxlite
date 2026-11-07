# Using the answerer

This guide is for people who call rwxlite directly from Node, without rwxmap. It covers installing it, loading the model, what to send, what comes back, and how to turn the probabilities into a decision. Every example output below was produced by running `loadAnswerer` on the 0.3.1 int8 model (`manifest.json`, model string `rwxlite-0.3.1+984714f0`).

If you want to read OpenAPI files, get finished verdicts (a letter per operation), or gate the API calls an agent makes, use [rwxmap](https://github.com/hamr0/rwxmap) instead. rwxlite only returns probabilities. It never decides a letter, never applies a cut, never asks a human.

## 1. Install

```
ONNXRUNTIME_NODE_INSTALL=skip npm i rwxlite
```

Node 22 or newer. `onnxruntime-node` is an optional dependency of rwxlite and is the only thing that runs the model. On Linux x64 its install script downloads about 285 MB of GPU libraries; setting `ONNXRUNTIME_NODE_INSTALL=skip` avoids that, and the CPU build that ships in the package is enough. If `onnxruntime-node` is missing, `loadAnswerer` throws `rwxlite: onnxruntime-node is not installed (it is an optional dependency)`.

## 2. Get the model files

The model files are not in the npm package. Download the five files from the GitHub release `v0.3.1` (https://github.com/hamr0/rwxlite/releases) into one folder:

| File | Size | What it is |
|---|---|---|
| `manifest.json` | small | default (int8) manifest |
| `model-int8-pc.onnx` | 23 MB | int8 weights (default) |
| `manifest-exact.json` | small | fp32 ("exact") manifest |
| `model-fp32.onnx` | 91 MB | fp32 weights |
| `vocab.txt` | small | tokenizer vocabulary (both models) |

Check them against these sha256 values (the same values `m1/release-assets.mjs` enforces before a release is built):

```
e8477a1595578eec1e45020277319877d45cfb809785b22eaeb83bfb66c0a5b8  manifest.json
c6bac86970888049952305f72434abe5c9d8f854224a5537f14e5a428a977739  manifest-exact.json
984714f0342ce551779f0ed9d95be57f71ab30b2ef72baec1d9818ce96d465d7  model-int8-pc.onnx
bbe1997d43020724f9eab9e42e8f6337e9640fe46f764b6fceac1eb1d000a3cf  model-fp32.onnx
07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3  vocab.txt
```

```
cd /path/to/model-dir && sha256sum -c <<'EOF'
e8477a1595578eec1e45020277319877d45cfb809785b22eaeb83bfb66c0a5b8  manifest.json
c6bac86970888049952305f72434abe5c9d8f854224a5537f14e5a428a977739  manifest-exact.json
984714f0342ce551779f0ed9d95be57f71ab30b2ef72baec1d9818ce96d465d7  model-int8-pc.onnx
bbe1997d43020724f9eab9e42e8f6337e9640fe46f764b6fceac1eb1d000a3cf  model-fp32.onnx
07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3  vocab.txt
EOF
```

You do not strictly need to do this by hand for the model and vocabulary: at load time `loadAnswerer` hashes the model file and `vocab.txt` and compares them with the hashes written in the manifest. A mismatch throws `rwxlite: <file> sha256 does not match manifest.json`. (`loadAnswerer` does not hash the manifest file itself, which is why the list above includes it.) Only the files you actually load are read: the int8 setup needs `manifest.json`, `model-int8-pc.onnx` and `vocab.txt`; the fp32 setup needs `manifest-exact.json`, `model-fp32.onnx` and `vocab.txt`.

## 3. Load the answerer

```js
import { loadAnswerer } from 'rwxlite';

const a = await loadAnswerer({ dir: '/path/to/model-dir' });
```

Options:

- `dir` (required): the folder from step 2.
- `manifestFile` (default `'manifest.json'`): which manifest to load. `manifest.json` loads the int8 model. `manifest-exact.json` loads the fp32 model: `loadAnswerer({ dir, manifestFile: 'manifest-exact.json' })`.
- `threads` (default `Math.min(4, os.availableParallelism())`): intra-op threads for onnxruntime. It must be an integer of 0 or more; 0 leaves the choice to onnxruntime; anything else throws. More threads make one operation faster up to a point (the code comment records a 4-core desktop CPU at 15.5 ms with 1 thread, 9.2 ms with 2 and 6.9 ms with 4 for an earlier int8 model); pass `1` if you run many answerers in parallel and want each to stay on one core.

Which model to choose:

- **int8 (default, 23 MB).** Smaller. It has small rounding differences compared to the fp32 model, so probabilities can differ in the last digits.
- **fp32 ("exact", 91 MB).** No int8 rounding drift. It is the model rwxmap pins. Choose it if you want the numbers to be as stable as possible, or to compare with rwxmap's logs.

On the 1,443 exam #5 operations both score almost the same on their own (int8 1,280 right / 64 too loose / 99 too tight; fp32 1,283 / 64 / 96), so the choice is about size and numeric stability, not accuracy.

The `model` string in every answer is `rwxlite-<manifest version>+<first 8 hex of the weights hash>`, here `rwxlite-0.3.1+984714f0` (int8) or `rwxlite-0.3.1+bbe1997d` (fp32). Log it next to every decision so you can tell which model gave an answer.

## 4. The request

```js
const req = {
  state: { method: 'GET', path: '/v1/projects/{projectId}/invoices',
           operationId: 'listInvoices', summary: 'List invoices for a project', description: '' },
  lean: { class: 'r', rule: 'method' },
  questions: { isX: '', changes: '' },
};
```

- **`state`** describes the operation. `method` and `path` are required non-empty strings. `operationId`, `summary` and `description` are optional but help a lot; use the ones from the OpenAPI file. The method is case-insensitive. In `operationId`, `summary` and `description`, HTML tags are stripped, entities are unescaped, whitespace is collapsed and the text is cut to 120, 200 and 400 characters; the whole input is then cut to 128 tokens (the lean is first, so it is never the part that is cut).
- **`lean`** is required: `{ class: 'r' | 'w' | 'x', rule: '<rule name>' }`. See the next section.
- **`questions`** is required and must be an object with at least one key. See section 6.
- A `model` field is accepted and ignored (there is only one local model); it exists only so the request has the same shape as a Jev request.

### The lean, in plain words

The lean is the *mechanical first guess* about the operation, made from rules that do not use a model: for example "a GET is a read" (`r`, rule `method`) or "a DELETE is x" (`x`, rule `method-delete`). It is a letter plus the name of the rule that produced it.

rwxlite was trained with the lean as the first words of its input, so it is part of the question you are asking the model, not an optional hint. The lean is **required**, and the model's answer depends on it (section 9 shows how much).

The measured way to get a lean is rwxmap's mechanical rules (https://github.com/hamr0/rwxmap). That is what the scores in the README were measured with, so it is the recommended source. If you write your own first guess, you are outside what was measured.

The rule names the 0.3.1 model saw in training (the part of the input after the lean letter):

| Rule | Lean letter | Typical method |
|---|---|---|
| `method` | r | GET (also HEAD; QUERY is read as GET) |
| `read-verb`, `read-verb-anywhere` | r | POST with a read-style name |
| `method-floor` | w | PUT, PATCH |
| `modify-verb`, `modify-verb-summary` | w | POST with a change-style name |
| `floor-post` | x | POST |
| `method-delete` | x | DELETE |
| `cant-undo-verb`, `cant-undo-verb-summary` | x | POST, PUT, PATCH with a can't-undo-style name |

(Counted over the 102,668 training texts in `data/round13/train.jsonl`.)

Three more rule names exist in rwxmap's current mechanical rules: `path-x-word`, `content-noun` and `get-action`. **The model never saw these three in training.** They were fed to it unchanged and checked on 154 validation rows (139 right, 5 too loose, 10 too tight in the product flow), which is why they are not blocked, but it is a small sample. The rule name `credential-set` is also not in the training set; rwxlite reads it as `cant-undo-verb` (the lean class you send is kept). **Any other unseen rule name is untested**: the model will read it as unfamiliar words in its input, and nobody has measured what that does to the answer. If you invent your own rule names, measure them first.

## 5. The answer

```js
const one = await a.answer(req);
// { model: 'rwxlite-0.3.1+984714f0',
//   answers: { isX: { noul: 0.00018958376213002917 }, changes: { noul: 0.007416255903099448 } } }
```

`noul` is the probability. For each question you asked there is one entry under `answers`. Two shapes exist, both plain JSON:

- **An answer:** `{ model, answers: { isX?: { noul }, changes?: { noul } } }`.
- **No answer:** `{ model, error: '<message>' }` (there is no `answers` key). `answer()` throws an `Error` with that message instead; `answerMany()` puts the plain object in the slot (an `Error` object would serialise as `{}`, so it never does). When there is no answer, keep your first-guess letter. Typical messages: `rwxlite: request must be an object`, `rwxlite: state needs string method and path`, `rwxlite: lean needs class r|w|x and a rule`, `rwxlite: questions must be an object`, `rwxlite: no questions`, `rwxlite: unknown question <name>`, `rwxlite: bad logits`.

The `model` argument and the question text are not read; only which question names you pass matters.

### From the two numbers to p(r), p(w), p(x)

The model outputs three probabilities, p(r), p(w) and p(x), that add up to 1. Each question is plain arithmetic on them:

- `isX` = p(x)
- `changes` = p(w) + p(x)

So, when you ask both:

```js
const px = one.answers.isX.noul;
const pc = one.answers.changes.noul;
const p = { r: 1 - pc, w: pc - px, x: px };
const letter = Object.entries(p).sort((u, v) => v[1] - u[1])[0]; // [letter, its probability]
```

The top probability is how sure the model is about its own best letter. That is the number you compare to your cut (section 8).

## 6. The two questions

- **`isX`: "can this NOT be undone?"** This is p(x). It is the question that matters most for safety: x is the letter where a later call cannot put things back, including anything anyone did in between. That is wider than "destroys data": creating an API key or token, widening who has access, setting up a webhook to an outside URL, creating a login user, and adding a member to a team are all x.
- **`changes`: "does this change anything?"** This is p(w) + p(x). If it is low, the operation is a read.

How they map to letters: low `changes` means r; high `changes` and low `isX` means w; high `isX` means x. The model's r/w/x letters are exactly the letters in the README.

Why `questions: { isX: '', changes: '' }`? Only the *keys* are read; the criteria for both questions are baked into the weights, so the question text is never used and empty strings are fine. (They are kept as placeholders so the request has the same shape as Jev's.) You pass both keys so you can compute all three of p(r), p(w), p(x); pass only one key and you only get that one back. A request with no keys, or with a key other than `isX` or `changes`, is a no-answer.

## 7. Worked examples

These operations are made up, generic ones: they are not from any exam or validation set. Each is a real request and the real output from the int8 model. The leans are what rwxmap-style rules give for that method.

| # | Operation | Lean sent |
|---|---|---|
| 1 | `GET /v1/projects/{projectId}/invoices`, `listInvoices`, "List invoices for a project" | `r method` |
| 2 | `PUT /v1/projects/{projectId}/settings`, `updateProjectSettings`, "Update project settings" | `w method-floor` |
| 3 | `POST /v1/projects/{projectId}/notes`, `createNote`, "Create a note" | `x floor-post` |
| 4 | `POST /v1/projects/{projectId}/api-keys`, `createApiKey`, "Create an API key" | `x floor-post` |
| 5 | `DELETE /v1/projects/{projectId}`, `deleteProject`, "Delete a project" | `x method-delete` |

Request 1 (the JSON in full; the others differ only in `state` and `lean`):

```json
{"state":{"method":"GET","path":"/v1/projects/{projectId}/invoices","operationId":"listInvoices","summary":"List invoices for a project","description":""},"lean":{"class":"r","rule":"method"},"questions":{"isX":"","changes":""}}
```

Real answers, with the arithmetic done (rounded to 4 places):

| # | Answer JSON (`isX`, `changes`) | p(r) | p(w) | p(x) | Letter |
|---|---|---|---|---|---|
| 1 GET read | `0.00018958376213002917`, `0.007416255903099448` | 0.9926 | 0.0072 | 0.0002 | **r** |
| 2 PUT update | `0.017573521378007922`, `0.9983811919017629` | 0.0016 | 0.9808 | 0.0176 | **w** |
| 3 POST create | `0.032569596453775274`, `0.9867117866387414` | 0.0133 | 0.9541 | 0.0326 | **w** |
| 4 POST create API key | `0.9910524465521778`, `0.9974375359218973` | 0.0026 | 0.0064 | 0.9911 | **x** |
| 5 DELETE project | `0.9977202904060377`, `0.9989789430250046` | 0.0010 | 0.0013 | 0.9977 | **x** |

What they show:

- Example 3 arrived with lean `x` (a plain POST starts out at x because a POST might do anything) and the model lowered it to `w` with 95% confidence. This is the kind of row where the model earns its place, and also the kind of row where a mistake would be "too loose", so this is where your cut matters.
- Example 4 stays `x`: creating a key is x under the widened rule, and the model is 99% sure.
- Example 5 (DELETE) is x, and the model agrees with its lean.

The complete answer for example 4, as returned:

```json
{"model":"rwxlite-0.3.1+984714f0","answers":{"isX":{"noul":0.9910524465521778},"changes":{"noul":0.9974375359218973}}}
```

The script used (save outside the package, adjust `dir`):

```js
import { loadAnswerer } from 'rwxlite';
const a = await loadAnswerer({ dir: '/path/to/model-dir' });
const req = {
  state: { method: 'POST', path: '/v1/projects/{projectId}/api-keys', operationId: 'createApiKey', summary: 'Create an API key', description: '' },
  lean: { class: 'x', rule: 'floor-post' },
  questions: { isX: '', changes: '' },
};
const out = await a.answer(req);
const px = out.answers.isX.noul, pc = out.answers.changes.noul;
console.log(JSON.stringify(out), { r: 1 - pc, w: pc - px, x: px });
```

## 8. Choosing your own cut ("% adjustment")

The probabilities are calibrated: among answers where the top probability is about 0.9, about nine in ten are right. rwxlite never turns them into a decision. You do, with one number, your **cut**:

> **Answer automatically when the top probability is at least your cut. Otherwise ask a human (or keep the lean).**

A higher cut means fewer automatic answers and fewer mistakes. A lower cut means more automatic answers and more mistakes. Nothing else changes. The cut is yours: rwxmap uses 0.90 for lowering, tuned to its needs. A cut tuned on 0.2.x does not carry over: the 0.3.1 calibration temperature differs (0.991463 against 0.844), so the same number now means something different. Re-check your cut when you move to 0.3.1.

### What the cut does, measured

Measured on our validation set: 4,180 operations from vendors that also appear in training, using the fp32 model and rwxmap's v4 mechanical leans, one operation at a time. **This is validation data from the same vendors as training, so it is optimistic.** Real, unseen vendors are harder (on exam #5 the model on its own had 4.4% too loose over all rows). Use the table to see the *shape* of the trade, not to predict your rates.

Letters are "too loose" when the model's letter is safer than the truth (the dangerous mistake) and "too tight" when it is riskier than the truth. "Answered" is the share of rows whose top probability is at or above the cut; the mistake columns are counted among the answered rows only.

| Cut | Answered | Too loose (of answered) | Too tight (of answered) |
|---|---|---|---|
| 0.50 | 99.5% | 152 (3.65%) | 48 (1.15%) |
| 0.70 | 95.0% | 106 (2.67%) | 24 (0.60%) |
| 0.80 | 92.2% | 87 (2.26%) | 16 (0.42%) |
| 0.90 | 86.7% | 48 (1.32%) | 10 (0.28%) |
| 0.95 | 80.0% | 30 (0.90%) | 7 (0.21%) |

Raising the cut from 0.5 to 0.95 takes the automatic share from 99.5% to 80.0% and cuts too-loose mistakes by a factor of about 5 (152 to 30 rows, as a rate 3.65% to 0.90%). The price is that about one row in five now goes to a human.

The script (Python 3, standard library only). Its inputs are three CSV files: the model's `p_is_x` and `p_changes` per row, the true label per row, and the lean class per row:

```python
import csv, sys
P, TRUTH, LEAN = sys.argv[1:4]
RANK = {'r': 0, 'w': 1, 'x': 2}
rows = {}
for r in csv.DictReader(open(P)):                       # columns: id, p_is_x, p_changes
    px, pc = float(r['p_is_x']), float(r['p_changes'])
    rows[r['id']] = {'p': (1 - pc, pc - px, px)}        # p(r), p(w), p(x)
for r in csv.DictReader(open(TRUTH)): rows[r['id']]['truth'] = r['label']   # columns: id, label
for r in csv.DictReader(open(LEAN)):  rows[r['id']]['lean'] = r['class']    # columns: id, class

def run(cut_up, cut_down):
    n = ans = loose = tight = 0
    for d in rows.values():
        n += 1
        top = max(d['p']); letter = 'rwx'[d['p'].index(top)]
        need = cut_down if RANK[letter] < RANK[d['lean']] else cut_up   # lowering vs raising/agreeing
        if top < need: continue                                          # below the cut: ask a human
        ans += 1
        if RANK[letter] < RANK[d['truth']]: loose += 1
        elif RANK[letter] > RANK[d['truth']]: tight += 1
    return n, ans, loose, tight

for c in (0.5, 0.7, 0.8, 0.9, 0.95):
    n, a, l, t = run(c, c)
    print(f'{c:<5} {a/n:6.1%}   {l:4d} ({l/a:5.2%})   {t:4d} ({t/a:5.2%})')
n, a, l, t = run(0.5, 0.9)
print(f'asym 0.5 up / 0.9 down: {a/n:6.1%}   {l} ({l/a:5.2%})   {t} ({t/a:5.2%})')
```

The validation files are not shipped in the repository; to produce the same table on your own data, give the script your own three CSVs of the same shape.

### The asymmetric option: stricter before lowering than before raising

The two mistakes do not cost the same. Calling something **safer** than it is (too loose, for example calling a key-creating call `w`) can let a harmful call through. Calling something **riskier** than it is (too tight) only costs a human a look. So you can use two cuts: a low one when the model wants to *raise* the lean's letter, and a high one when it wants to *lower* it.

In the script: `need = cut_down if letter is safer than the lean else cut_up`. With 0.5 to raise (or agree) and 0.9 to lower, the same validation set gives:

| Rule | Answered | Too loose (of answered) | Too tight (of answered) |
|---|---|---|---|
| One cut, 0.50 | 99.5% | 152 (3.65%) | 48 (1.15%) |
| 0.5 to raise, 0.9 to lower | 95.6% | 86 (2.15%) | 47 (1.18%) |
| One cut, 0.90 | 86.7% | 48 (1.32%) | 10 (0.28%) |

Compared with a single 0.5 cut, the asymmetric rule roughly halves the too-loose mistakes (152 to 86) and keeps 95.6% of the rows automatic, while too-tight stays about the same (47 against 48). It does not reach the single 0.90 cut's too-loose rate; it gives that up to keep far more rows answered. The cost of being strict only on lowering lands on the cheap side of the error, which is why rwxmap does the same: it only moves a row off the mechanical letter in the safer direction when the model is very sure (its cut is 0.90).

## 9. How the lean changes the answer

The same operation, sent with different leans, gives different answers, because the lean is part of the input. These were run for real on the int8 model, and the values are rounded to three places. Both operations are made up. The point is the effect of the lean, not which letter is right for the operation.

`POST /v1/items/search`, `searchItems`, "Search items":

| Lean sent | p(r) | p(w) | p(x) |
|---|---|---|---|
| `r read-verb` | 0.996 | 0.004 | 0.000 |
| `w modify-verb` | 0.638 | 0.314 | 0.048 |
| `x floor-post` | 0.962 | 0.014 | 0.024 |

`POST /v1/reports/{reportId}/export`, `exportReport`, "Export a report":

| Lean sent | p(r) | p(w) | p(x) |
|---|---|---|---|
| `r read-verb` | 0.995 | 0.004 | 0.001 |
| `w modify-verb` | 0.014 | 0.274 | 0.712 |
| `x floor-post` | 0.150 | 0.130 | 0.720 |

What this shows: the model reads the name and the lean together, and a different lean can move the answer a long way. For "Export a report" a lean of `r` gives r at 0.995, while a lean of `w` gives x at 0.712. For "Search items" a lean of `w` drops the top probability to 0.638, so at a cut of 0.7 it would go to a human where the other two leans would not. So a wrong lean can pull the answer the wrong way. This is why the lean should come from rules that were measured (rwxmap's mechanical rules) and why the cut in section 8 applies to the answer for the lean you sent. Keep your lean source stable between the time you pick a cut and the time you use it.

## 10. answer and answerMany

```js
const one = await a.answer(req);          // throws on no answer
const many = await a.answerMany([req1, req2, req3]); // one slot per request, same order
```

- `answer(req)` returns an answer or throws an `Error` with the no-answer message.
- `answerMany(reqs)` returns an array; slot `i` is either `{ model, answers }` or `{ model, error }`. A bad request only fails its own slot. If the model itself fails (a runner error), every slot holds the same `{ model, error }`.
- `answerMany` runs the model **one row at a time**. That is deliberate: int8 dynamic quantisation takes its scale over a whole padded batch, so a batch would make a row's probabilities depend on its neighbours. Because of this, a request gets byte-identical probabilities from `answer`, from `answerMany` in any order, and next to any other requests, for both models. There is no speed-up from batching, so do not reach for it.
- `ortRunner` is exported too. If you call it yourself on a multi-row batch you get the batched behaviour back (int8 answers drift with the batch's neighbours); the `Answerer` never does that.
- Speed is about 17-20 ms per operation on a laptop CPU.

## 11. Two inputs that are rewritten

- The HTTP `QUERY` method is read as `GET`. The model never saw `QUERY` in training, and QUERY is safe and idempotent like GET.
- The lean rule `credential-set` is read as `cant-undo-verb`, for the same reason (the model never saw that name). The lean class (`x`) you send is kept. This alias is part of the model's input contract: the model was trained on the text `cant-undo-verb`.

## 12. Other facts

- The manifest may carry `textFormat` (1 or 2, default 1) and `temperature` (a finite number above 0; anything else makes `loadAnswerer` throw before it reads any file; a manifest with none uses 0.844). The 0.3.1 manifests carry `temperature` 0.991463 and `textFormat` 1. Format 2 exists but is switched off: the shipped 0.3.1 models use format 1.
- Every file's sha256 is checked against the manifest at load; a mismatch throws.
- Limits: OpenAPI operations only, with method, path template, operationId, summary and description. No request bodies, no query values, no hosts without a spec.

## 13. Where to go next

rwxlite answers one operation at a time with probabilities. To go from an OpenAPI file to finished verdicts, or to gate the API calls an agent makes, use rwxmap: https://github.com/hamr0/rwxmap
