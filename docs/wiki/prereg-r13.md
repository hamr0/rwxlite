# Pre-registration: round 13 (R13, R13-L3, R13-L3-t2) trained on all labelled data with BRIEF-v4 labels, 2026-11-06

**Status: FROZEN when committed on branch `dev`, before any of the candidates has started training.** No round 13 model exists yet; nothing has been predicted or scored. The one open part is the text-format-2 definition (section 4b); it must be filled in and committed before R13-L3-t2 trains, and nothing else here may change.
The candidates are **candidates**. The only thing that can ship one is the frozen rule in section 6, applied once to a fresh exam #5. Nothing in this file is a release.

## 1. Question

Does a model trained on **everything we have labelled, under the shared BRIEF-v4 labels** (rwxmap's D137 access-grant rule: creating a credential, widening access, adding a member and similar are x, not w), keep 0.2.0's exact rate and not add leaks on vendors it has never seen? And do two variants help: a loss that charges too-loose mistakes 3x (R13-L3), and a new input format with a built-in access hint (R13-L3-t2)? One candidate is picked on val by a frozen rule (section 6) and only that one is tested against 0.2.0.

## 2. Label source (single source of truth, nothing relabelled by us)

- rwxmap repo, branch `docs/d137-truth-v4`, **commit `95104e3`**, directory `data/export-v4-gap-2026-11-06/` (read-only). Both files were read from that commit and from the working tree; the hashes match:
  - `export-v4.csv` sha256 `0e371db2a3554309dd3cce8cbe287ab4b7d693893589c114146cbe186c58114b` (we use the 28,757 rows with `set = rwxlite`: 22,727 w, 6,029 x, 1 r; the other sets are not used)
  - `inherit-v4.csv` sha256 `e1993a27e2f6287424801b4dc3cfd1c956e727df42f7577c3ee0fe3d68b56ee3` (570 surface variants; their README says label = their seed's v4 label)
- Our export that the labels were made from: `data/v4/rwxlite-w-unique.csv` sha256 `a40d1f59dc56b31628e1a48cf8b1c99e9159d6dff0b645050079e141d7edd558` (29,327 rows = 28,757 + the 570 variants; `docs/wiki/label-inventory.md` section 9.5).
- **Merge-group rule.** Each exported `your_id` stands for a whole group of rows with the same merge key (provider lower-case + method with QUERY folded into GET + path + operationId + summary whitespace-collapsed lower-case; the key is checked unique over the 28,757 exported rows). The v4 label applies to **every row in every file whose key equals that key**: snapshots, QUERY copies, rows in val, rows we add. A group that is not in the export keeps the label it has now.
- Surface variants: counted only (none is trained on, see section 3). Of the 570, the inherited label equals the variant's current label (w) on 479 and differs (w to x) on 91.

## 3. Data build (`m1/r13-assemble.py`, deterministic, no training; output `data/round13/`, gitignored)

Text formatting is identical to S0 (`train/common.fmt_text`; no change under `src/`; every S0 row's text is asserted byte-equal). The script stops on any assertion.

**Base: S0 as it was actually trained**, `data/round12/final/S0/train.jsonl` (sha256 `75185cebf44bcf9647263d9d796b71abd220b9bbc9b9edfd7aaeeb454c72e36c`, 95,291 rows; the copy on the home server is identical). Note: `data/round12/train.jsonl` (`84062b23...`) is the same 95,291 ids **before** the 62 D136 relabels; the S0 that trained is the D136 one, so that is the base. It contains all 87,657 rows of 0.2.0.

**Added** (each hand-truth row is one-hot, `status fresh`, `tier none`, the convention of the round 12 label fixes):

| added | rows | label used |
|---|---|---|
| holdout goharbor+render (`final/holdout.jsonl`, D136 truth) | 455 | its label |
| v3eval (`round12/v3eval.jsonl`) | 5,716 | the human `truth` field (1,352 rows differ from the Jev-recipe `label` and the truth wins) |
| gate-1 + gate-2 (hand truth, zero previous overlap with any training file) | 600 + 600 | `truth.csv`, text from the corpus row of the same operation (same `fmt_text`, `credential-set` aliased as in round 10) |
| gate-3 + gate-4: 6 operations that were in no file (4 + 2) | 6 | `truth.csv` |
| gate-3 + gate-4: operations already in S0 | 0 added | hand truth replaces the Jev label on every snapshot of the operation (2 rows changed, both Jev w to truth x) |

- **Generated variants: none.** The 1,199 unique generated variants (570 surface, 629 contrast) are excluded as in S0; round 12 showed they do not help.
- **Merge repeats.** One authoritative label per merge group: hand truth over Jev/mechanical, then v4 over everything. Groups with disagreeing labels before v4: **0** (nothing to resolve; v3eval has 0 groups with conflicting truth).
- **Soft targets.** Round 12 trained with `--soft --alpha 0.7`. A row whose label **changed under v4** and had a Jev soft target gets a **hard one-hot target for its new label** (Jev's p would contradict it): 4,302 train rows. Unchanged Jev-soft rows keep their soft targets as in S0. Rows of the added hand-truth sets are one-hot.
- **Validation:** `data/round12/val.jsonl` with v4 labels applied (223 w to x). Asserted: no val operation (merge key or provider+method+path+operationId) is in train; the val and train vendor sets are not asserted disjoint (they never were; the split is by operation group).
- `v3eval.parquet` is only the file the trainer needs for its end-of-run report; it is now training data, so that report means nothing.

### Counts (`data/round13/summary.json`)

| | rows | r | w | x | x share |
|---|---|---|---|---|---|
| S0 (as trained) | 95,291 | 53,481 | 25,449 | 16,361 | 17.17% |
| **R13 train** | **102,668** | 55,532 | 22,479 | 24,657 | 24.02% |
| of which S0 rows after v4 | 95,291 | 53,482 | 20,137 | 21,672 | |
| of which added rows | 7,377 | 2,050 | 2,342 | 2,985 | |
| **R13 val** | 4,180 | 2,435 | 922 | 823 | 19.69% (was 600 x, 1,145 w) |

Unique operations (merge key): train 96,424 (S0 94,104 by provider+method+path); unique ids 102,668 = rows. Vendors in train 645, providers 653.

**Labels changed under v4** (total 6,245 train rows + 223 val rows; every change is w to x except one w to r):

| source | w to x | w to r |
|---|---|---|
| S0 rows, Jev soft | 4,301 | 1 |
| S0 rows, mechanical word-rule | 437 | 0 |
| S0 rows, hand or rule (r9-hand, fixes, rulings, credential rule) | 159 | 0 |
| S0 rows, exam #3 / exam #4 / fresh exam | 208 / 111 / 93 | 0 |
| added: v3eval | 825 | 0 |
| added: holdout / gate-1 / gate-2 / gate-3 / gate-4 | 27 / 44 / 37 / 1 / 1 | 0 |
| val | 223 | 0 |

Per-row record: `data/round13/provenance.csv` (id, source, split, label before, label after, reason).

### Data sha256 (`data/round13/SHA256SUMS`)

```
8144e5056e0244e888ca6360ac312901762245d4c8874b0c304bcd897a788fef  train.jsonl
91808a87cf24ac9c70f4d5b8f26fe68341ca9836606ce30a3e86273fce129aa5  train.parquet
8c0fdcfb32ca107db4ba8e5a535cf5851da91a164903603c250fd4dfb0654983  val.jsonl
580a1141e6ee416b4ff2b445c749fc95b60bcdbddd04d0bbdd0464196ff840d1  val.parquet
cd6e423c7a271d6ec200ae780804b1d0b4860f5df513d0df3083f8ec0da0e1f5  v3eval.jsonl
7c0df6fa7f38f79a4e603239c54d78db7c92fe7213930918b12988002af907ad  v3eval.parquet
d282871f5ebb29cde7a8e9b438129b94838328663fd96b0811b11de356819a13  provenance.csv
e6f978882d20ec13d9102b12f99197321577ef4f6f39ca671169112c3fb1b3b9  summary.json
```

## 4. Candidates, recipe and command lines

Three candidates, same data (section 3), same base model, same seed:

| candidate | change over the S0 recipe | text format |
|---|---|---|
| **R13** | none | 1 (today's `formatText`, unchanged) |
| **R13-L3** | too-loose mistakes cost 3x a too-tight one (section 4a) | 1 |
| **R13-L3-t2** | R13-L3 plus the new input format of section 4b | 2 (placeholder) |

### 4. Recipe (R13; the other two change only what their section says)

Base `sentence-transformers/all-MiniLM-L6-v2`, **trained fresh, not from 0.2.0** (no `--init`), `--soft --alpha 0.7`, 1 epoch, batch 32, AdamW lr 5e-5 weight decay 0.01, warmup 6% then linear decay, max_len 128, x_weight 1.0, `torch.manual_seed(1)`, `--threads 4`, `--ckpt 250`. 3,209 steps (102,668 / 32). One seed, no variance estimate.
`train/finetune.py` differs from the copy that trained S0 by the unused `--init` option (default None = base model) and the `--loose_cost` option (default 0 = off); with both at default the training path is the S0 one. `train/common.py` is byte-identical to S0's (`96663877...`) until the text-format-2 work. Exact sha256 of the scripts as launched go into the findings.

```
# laptop -> home server, new dir only (nothing else under ~/rwxlite-train is touched)
ssh ahassan@192.168.178.180 'mkdir -p ~/rwxlite-train/r13-R13/train ~/rwxlite-train/r13-R13/data/train   # and r13-R13-L3 the same'
scp train/common.py train/finetune.py train/losscost.py ahassan@192.168.178.180:~/rwxlite-train/r13-R13/train/
scp data/round13/{train,val,v3eval}.{jsonl,parquet} data/round13/SHA256SUMS ahassan@192.168.178.180:~/rwxlite-train/r13-R13/data/train/
scp m1/r13-train.sh ahassan@192.168.178.180:~/rwxlite-train/r13-train.sh
# start (on the server), one candidate at a time, each in its own dir ~/rwxlite-train/r13-<name>/ with the same copied files
nohup ~/rwxlite-train/r13-train.sh R13 > ~/rwxlite-train/r13-R13.log 2>&1 & echo $! > ~/rwxlite-train/r13-R13.pid
nohup ~/rwxlite-train/r13-train.sh R13-L3 > ~/rwxlite-train/r13-R13-L3.log 2>&1 & echo $! > ~/rwxlite-train/r13-R13-L3.pid   # after R13 has finished
# what the script runs (R13; R13-L3 adds --loose_cost 3 and --tag r13-L3)
HF_HOME=$HOME/rwxlite-train/hf-cache $HOME/rwxlite-train/.venv/bin/python train/finetune.py --epochs 1 --soft --alpha 0.7 --threads 4 --ckpt 250 --tag r13 > data/train/finetune-r13.log 2>&1
```

### 4a. R13-L3: cost-sensitive term (`train/losscost.py`, flag `--loose_cost 3` in `train/finetune.py`)

Letters ordered r < w < x. "Too loose" = probability on a letter below the truth. Exact formula, added to the recipe's loss and nothing else changed (soft targets, alpha 0.7, x_weight 1.0 untouched):

```
cost(t, j) = 3 if j < t      (too loose)
             1 if j > t      (too tight)
             0 if j == t
loss = recipe_loss + mean over the batch rows of  sum_j softmax(logits)_j * cost(y, j)
```

`y` is the row's **hard label** (the v4 label), also for rows trained with a soft target. So a too-loose error costs exactly 3 times an equal too-tight one. Weight of the term is 1. The unit check `python3 -I train/test_losscost.py` asserts a too-loose prediction scores higher than an equal too-tight one (exactly 3.0 against 1.0). With `--loose_cost 0` (default) the code path is the S0 one.

### 4b. R13-L3-t2: text format 2 (defined; code commit `f7456a2acc66ce84fd8c87d7426c9001bab8ceb7`)

Everything else (data rows, labels, targets, recipe, `--loose_cost 3`) is as R13-L3. Only the `text` column differs.

**Definition.** Format 1 is today's text, unchanged byte for byte. Format 2 is format 1 with one extra segment, `hint: access`, placed **directly after the lean segment** and only on hinted operations: `lean: w floor-put | hint: access | PUT /... | op: ... | sum: ... | desc: ...`. It is second, so the 128-token cut cannot reach it (the long summary and description come after it). Unhinted rows are byte-identical to format 1.

**The hint** is computed inside `src/text.js` (`accessHint`) and `train/common.py` (`access_hint`) from the operation's own method, path, operationId and summary. It is never supplied by the caller and never read from the lean. The description is not read (the round 13 data files do not carry it). DELETE is never hinted. It fires when any of six families matches (text first normalised: tags stripped, camelCase split, lower-case, non-alphanumerics to one space):

1. grants or widens access: IAM, ACL, permissions, role bindings and assignments, share, invite, collaborators, deploy keys, ssh keys, and resource/bucket/key/queue/topic/repository/vault/registry/secret/security/trust/network/access policies, with a write-type verb (a GET only if its name starts with a write verb);
2. creates an API key or token (api key, access key, personal access or bearer token, client secret, application password);
3. flips an access-widening toggle (public access, anonymous or guest access, external sharing, open registration, disable MFA or authentication and the like);
4. registers a webhook or subscription to an outside URL (webhook, callback URL, event subscription, notification endpoint);
5. creates a login user (create or invite a user, admin or service account);
6. adds a member to a team, org, project, group or workspace.

Non-access "policies" (autoscaling, lifecycle, retention, routing, backup, cache, alert, schedule and similar) do not count, and neither do read, delete, revoke, disable, verify, reset or refresh verbs. The pattern started from the widened pattern of the BRIEF-v4 inventory work and was changed in three obvious places only after a look at the false positives: `shared`/`shares` no longer match (shared cache, shared drive item, file shares are not grants; `share` and `sharing` still do), Kubernetes `pod binding` is not a role binding, and `pre-receive hooks` are not webhooks. It was not tuned to the labels beyond that.

**Version.** The manifest gets an optional `textFormat` (integer 1 or 2). Absent means 1, so 0.2.0 and every existing manifest give byte-identical text; any other value throws before any file is read. `formatText(state, lean, format = 1)` and `new Answerer({..., textFormat})` keep the old API working. Test: `test/text.test.js` proves format 1 (default and explicit) equals the Python fixture on every one of its 900+ rows, and format 2 equals Python on `test/fixtures/text2.jsonl` (800 rows, 400 hinted).

**Parity (`m1/t2-parity.py`, Python `fmt_text` against Node `formatText`, byte for byte).** round13 train+val 106,848 rows: format 1 mismatches 0, format 2 mismatches 0 (1,959 hinted); whole corpus `data/m0/mechanical.jsonl.gz` 123,339 rows: 0 and 0 (2,595 hinted); 5 hand probes (unicode, html, CR/LF, QUERY, dotted operationId): 0 and 0. The stored round13 text equals `fmt_text` format 1 on every row (everything before the `desc:` segment; the data files carry no description). Note: Node prints HTTP QUERY as GET (D134) while Python prints the stored method, so the method token is folded before comparing; the hint itself folds QUERY to GET on both sides.

**Hint coverage on data/round13 (train+val, 106,848 rows).** Hinted 1,959 rows (1.8%): x 1,813, w 131, r 15. Precision (hinted rows labelled x) 92.5% (train 93.1%, val 75.4% on 65 rows). Of all x rows 7.1% are hinted. Recall on the 6,467 rows that v4 changed from w to x: 1,647 hinted, **25.5%** (train 1,605 of 6,244 = 25.7%; val 42 of 223 = 18.8%). So the hint is a precise but narrow marker: three quarters of the v4 w-to-x changes carry no hint. Row counts, not unique operations.

**Re-rendered data (`m1/r13-t2-render.py`, output `data/round13-t2/`, gitignored, deterministic: two runs give identical hashes).** Inserts `hint: access` as second segment on hinted rows; asserted: removing the segment gives the old text, every other field is equal. Hinted rows: train 1,894 (r 8, w 122, x 1,764), val 65 (r 7, w 9, x 49), v3eval 394. `train/common.py` is no longer the S0 file: its sha256 is `061da692d8781a10...` at the code commit (`git show f7456a2:train/common.py | sha256sum` for the full value); `src/text.js` is changed too. Neither affects R13 or R13-L3, which use the stored format 1 text.

```
55c2d80c1595e0b3c5037482f7fd4120854e266dd0d6b0a85e8b4fbcd02437dc  train.jsonl
32d329c7e370b64b94ee0399193eae48cdd71c513ff13acb16a74dd3ea3cd9a4  train.parquet
b082e4611c712d9648fdb2db83ec003cb7d492c8a4e76170df0d002951f37f86  val.jsonl
fbd89c101591cbc26af320a580f566f0f14e6f01eec2c8af039e707ac83287e0  val.parquet
ab60c2842b809c4d3708c6d4b388cc4bdf12509ff67998346583198ab53ab6a9  v3eval.jsonl
32af1c204c6bebe58a9bd1e533013fe3d08a22372513d5d3bdd7c8d126241051  v3eval.parquet
```

Copy for R13-L3-t2 (own dir `~/rwxlite-train/r13-R13-L3-t2/`, same layout as section 4): `data/round13-t2/{train,val,v3eval}.{jsonl,parquet}` into `data/train/`, and `train/common.py` as committed; start with `r13-train.sh R13-L3-t2` (adds `--loose_cost 3`, tag `r13-L3-t2`). A released model trained on format 2 needs `textFormat: 2` in its manifest.

Expected duration per candidate: S0 took 53 min (95,291 rows); these have 7.7% more rows, so about 57 to 60 min each, run one after the other. Start times and first log lines go into the findings.

## 5. What exists to check against, and what does not

**Every earlier exam, gate, holdout and v3eval row is now training data** (exams #3 and #4, the fresh exam, gate-1 to gate-4, goharbor+render, r9-hand, v3eval). There is **no internal held-out check**: a candidate's scores on v3eval or any old exam decide nothing; val is used only for the step-1 pick and the T fit of section 6, never as evidence against 0.2.0. The only evidence is exam #5.

## 6. Scoring plan and frozen decision rule

**Exam #5**: drawn later, with rwxmap, from vendors **outside** `data/round13/vendors-r13-seen.txt` (645 training vendors plus the val vendors, 649 names in all; generated from the frozen files: `python3 -I -c "import json;print('\n'.join(sorted({json.loads(l)['vendor'] for f in ('train','val') for l in open('data/round13/'+f+'.jsonl')})))"`; sha256 of the list `see findings`), and outside every held set (goharbor and render are training data now, so they are burned for exam #5 too). Labelled by BRIEF-v4. **Scored once.** Predict and score code committed before the truth is opened, as in exam #3/#4.

**Step 1, pick ONE candidate on val only (frozen).** For each of R13, R13-L3, R13-L3-t2 (the R13 family): fit its own T on `val.jsonl` (4,180 rows, v4 labels, sha256 above) with `temp_fit` of `train/tune_cuts.py`, on that candidate's own batch-1 fp32 probabilities (PyTorch CPU, max_len 128); then score the 4,180 val rows under the product rule, mode a, lower only at top-letter p >= 0.97, credential-set never lowered, mechanical letter from each row's `mech` field (the second-pass replica that matched rwxmap row for row in the round 12 calibration; its code is committed before the first score). Pick the candidate with the **fewest too-loose rows; ties go to the most exact; if still tied, R13 (the fewest changes)**. No other criterion, no looking at exam #5 first. Val is not a held-out set for these models in any other sense (labels v4, vendors shared with train); this use is a selection among our own variants and proves nothing against 0.2.0. Only the picked candidate sits exam #5.

**Step 2, models and temperatures on exam #5.**
- **Baseline: shipped 0.2.0 at T = 0.844, NOT refit** (the round 12 lesson: refitting its T cost 7 exact). Same path as shipped.
- **The picked candidate**: the T of step 1, frozen before exam #5 is drawn and recorded in the findings.

**Two paths, both on exam #5, both for both models:**
1. **Product path**: rwxmap's real CLI `secondPass`, mode a, lower only at top-letter p >= 0.97 (raise needs no cut-off). Numbers: exact / too loose / too tight, rwxmap's.
2. **Standalone, model-only**: the model's own letter on every row, no mechanical letter and no second pass (our `a_none`/argmax scorer). Numbers: exact / too loose / too tight.

**Decision rule (frozen).** The picked candidate ships only if, on exam #5, it is **the same as or better than shipped 0.2.0 on BOTH paths**: **no more too-loose AND no fewer exact** on path 1, and the same on path 2. Equal counts pass; any one of the four comparisons worse fails. If it fails, 0.2.0 stays and nothing is claimed (the other candidates are not tried on exam #5 afterwards). Release mechanics (int8 export, parity, GitHub release, publish) follow the project's release order and are separate.

## 7. Not allowed after training starts

No change to data, hyperparameters, the T rule, the 0.97 line, the exam, the scoring rule or the decision rule. No second run chosen for a "better" result. A rerun only for a crash or a data-join bug, recorded in the findings with the reason. Any new relabel from rwxmap means a new round, not an edit of this one.

## Run order

1. This file, `m1/r13-assemble.py`, `m1/r13-train.sh`, `train/losscost.py` committed (done before any training). 2. Text format 2 is defined and committed in section 4b. 3. User confirms; copy to the home server and start the candidates one after the other (section 4); record start times and first log lines in the findings. 4. Copy each final checkpoint back, step-1 pick on val. 5. Export and parity-check the picked one. 6. Exam #5 is drawn with rwxmap from unseen vendors; predictions committed; rwxmap scores; we score standalone; the rule in section 6 decides.
