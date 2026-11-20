# Research: fine-tuning choices for round 16

Written 2026-11-20. This is a web literature review and nothing was run for it. It covers seven questions about how to train the round 16 model, then gives ranked advice. Every claim links to its source. Where I am not sure a source says exactly what is written here, the text says so.

**How strong is each source?** Each one gets a tag.
- **Strong**: a well-known peer-reviewed paper, with results that others have repeated.
- **Medium**: a single peer-reviewed paper, or results from settings quite unlike ours.
- **Weak**: a preprint, theory only, or a second-hand summary.

**Does it transfer?** Most papers test bigger models, image models, or many classes. Each section says how well the result should carry over to our case: a small 3-class text model (r/w/x), about 300k rows, CPU only.

## Terms used once and then reused

- **Checkpoint**: a saved copy of the model's weights.
- **Base checkpoint**: the public all-MiniLM-L6-v2 (or bge-base) before we train it.
- **Warm start, or continued training**: starting round 16 from round 15's trained weights instead of from the base.
- **Catastrophic forgetting**: training on new data makes the model worse at what it learned before.
- **Replay, or rehearsal**: mixing some old rows back into the new training data so the model does not forget them.
- **Learning rate (LR)**: how big each weight update is. **Warmup**: the LR starts small and ramps up. **Decay**: the LR shrinks towards the end of training.
- **Knowledge distillation (KD)**: a small "student" model learns from a big "teacher" model's probabilities (its **soft targets**), not only from the single correct letter (the **hard label**). Our **alpha** is the share of the loss that comes from soft targets: we use 0.7 soft + 0.3 hard.
- **Calibration**: when the model says 90%, it should be right about 90% of the time. **Over-confident** means it says 95% but is right less often than that.
- **Temperature scaling (T)**: divide the model's raw scores by one number T before the softmax. T > 1 makes the model less sure, so a fitted T of 1.38 means the raw model was over-confident.
- **Label smoothing**: train towards "0.93 r, 0.03 w, 0.03 x" instead of "1, 0, 0", so the model never learns to be 100% sure.
- **Focal loss**: a loss that pays less attention to rows the model already gets right with confidence.
- **ECE (expected calibration error)**: the usual measure of how far the model's confidence is from its real accuracy.
- **In-distribution (ID)** test data looks like the training data (our val, about 97%). **Out-of-distribution (OOD)** data looks different (unseen vendors, about 90%).

## What our current recipe is (from the repo, for context)

From `m1/r15-train.sh`, `train/finetune.py` and `docs/wiki/prereg-r15.md`:
- **Model head**: `AutoModelForSequenceClassification`. That reads the [CLS] token through BERT's pooler layer. all-MiniLM-L6-v2 itself was trained with mean pooling, which averages all the tokens.
- **Training settings**: 1 epoch, batch 32, AdamW at LR 5e-5, weight decay 0.01, 6% warmup then linear decay, max_len 128, gradients clipped at 1.0, seed 1.
- **Loss**: 0.7 soft CE + 0.3 hard CE. Each row's loss is multiplied by its row weight. Rows labelled by Sonnet or Opus (the contested rows) get weight 3.0, some get 0.3, and the batch is not renormalised.
- **Teacher**: bge-base, trained from base for 1 epoch. Its r15 rows had one-hot targets.
- **Soft targets**: the teacher's probabilities at T=1, computed on the same train rows the teacher was just trained on. These became the student's soft targets.
- **Both rounds 13 and 15 trained from the base checkpoint.** `finetune.py --init` already supports a warm start.

---

## 1. Continue from round 15, or retrain from the base?

**What the evidence says**

- **Warm starting can generalise worse than a fresh start.** [Ash & Adams 2020, "On Warm-Starting Neural Network Training" (NeurIPS)](https://arxiv.org/abs/1910.08475) found this in a specific setup. They trained a model on part of the data, then kept training it on all of the data. It reached the same training accuracy as a fresh model but scored worse on test data. Their fix is "shrink and perturb": scale the old weights towards zero and add a little noise before training on. **Medium evidence, weak transfer.** They used image models trained *from random weights*. We start from a pre-trained language model, and the lesson there is the opposite: reusing pre-trained weights is the whole point. A [reproduction study](https://arxiv.org/pdf/2206.10011) found the gap in some settings but could not always reproduce it. As far as I found, nobody has measured this for fine-tuning a BERT-size model from its own earlier fine-tuned checkpoint. That makes it an open question for us, not a known risk.
- **Learning rate, warmup and decay matter more than whether you warm start.** [Ibrahim et al. 2024, "Simple and Scalable Strategies to Continually Pre-train LLMs"](https://arxiv.org/abs/2403.08763) and [Gupta et al. 2023, "How to (re)warm your model?"](https://arxiv.org/abs/2308.04014) report three things:
  - Warm up the LR again, then decay it again, and replay some old data. Doing all three matched retraining from scratch on all the data.
  - A higher peak LR adapts more to the new data but forgets more of the old.
  - The replay share they used was small: a figure caption shows 5% replay for a mild data shift and 25% for a big shift. I did not check every experiment, so treat those numbers as examples.
  **Strong evidence for large language models in pre-training. Medium transfer**: the principle ("a lower LR keeps the old, a higher LR adapts more") is general, but the exact numbers are not ours.
- **A small replay buffer goes a long way for pre-trained language models.** [Scialom et al. 2022, "Fine-tuned Language Models are Continual Learners" (EMNLP)](https://arxiv.org/abs/2205.12393) kept nearly all of the old skill with **1%** rehearsal while adding 8 new tasks. **Medium evidence, medium transfer**: those were different *tasks*, while our new data is the same task with new *vendors*. Our shift is milder, so forgetting should be smaller.
- **Fine-tuning can damage what the pre-trained model knew, and that hurts OOD.** [Kumar et al. 2022, "Fine-Tuning can Distort Pretrained Features" (ICLR)](https://arxiv.org/abs/2202.10054) and [Wortsman et al. 2022, "WiSE-FT" (CVPR)](https://arxiv.org/abs/2109.01903) both show this. WiSE-FT also shows a cheap repair: average the weights of two models. Averaging the starting and fine-tuned weights improved OOD accuracy at no extra training cost. **Strong evidence (mostly vision, CLIP), medium transfer.** For us, averaging the round 15 and round 16 weights is a cheap experiment, not a proven win.

**For a model our size**: retraining from base on all ~600k rows is the safe choice, since it is what worked in rounds 13 and 15. It is also the most CPU time. Warm starting from round 15 on new rows plus a replay sample is cheaper, but it is untested here. If we warm start:
- use a lower peak LR than 5e-5 (for example 2e-5),
- keep a short warmup,
- replay at least 10-25% old rows. Our "old" data is the only source for some vendors and for D136/D137/D141 decisions, so be generous.

The literature does not say which choice wins for us, so test both on val and the unseen-vendor holdout before the exam.

## 2. Knowledge distillation: what alpha does, and when KD helps

**What the evidence says**

- **[Hinton, Vinyals & Dean 2015, "Distilling the Knowledge in a Neural Network"](https://arxiv.org/abs/1503.02531)** is the original KD paper. The loss is a weighted sum of soft CE, using the teacher's probabilities softened by a temperature, and hard CE on the true label. Hinton reports the best results with a *much smaller* weight on the hard term. They multiply the soft term by T² when T > 1. Soft targets carry "dark knowledge": for example, "this w row looks a bit like an x". **Strong evidence, general.**
- **[DistilBERT (Sanh et al. 2019)](https://arxiv.org/abs/1910.01108)** uses KD mostly during *pre-training* (masked words), not when training a classifier. Its loss weights do not apply directly to our case. **Weak transfer.**
- **Bigger or more accurate teachers do not always make better students.** [Cho & Hariharan 2019, "On the Efficacy of Knowledge Distillation" (ICCV)](https://arxiv.org/abs/1910.01348) found that when the student is much smaller than the teacher, a larger teacher can teach worse. A teacher stopped early (less over-fitted, softer) often teaches better. **Medium evidence (images), medium transfer.** bge-base is about 5x the size of MiniLM, a moderate gap.
- **Students rarely copy their teacher well, and copying better does not always help.** [Stanton et al. 2021, "Does Knowledge Distillation Really Work?" (NeurIPS)](https://arxiv.org/abs/2106.05945) found a large gap between student and teacher predictions even when the student could in principle match them. Closer copying ("fidelity") did not always improve test accuracy. They found that the data you distil on, and the temperature, matter most. **Strong evidence, general.**
- **KD helps most when the teacher labels extra unlabelled rows.** The same paper, plus common practice, points the same way: the student then gets teacher signal where no hard label exists. Our round 14 finding fits: distilling on the same rows gained nothing (see `classifier-training.md`). We already knew this. Round 15's gain came from new data, not from KD.
- **Distillation on the same data can still help a little ("born-again").** [Furlanello et al. 2018](https://arxiv.org/abs/1805.04770) showed that a student the same size as its teacher, trained on the same data, can beat the teacher. **Medium evidence, mostly images.** The gains are small.

**KD and over-confidence (this matters for our T of 1.38)**

- **The student inherits the teacher's confidence.** Teachers trained with plain cross-entropy are over-confident, and students copy that ([Yang & Song, "Rethinking KD from the perspective of model calibration"](https://arxiv.org/abs/2111.01684); [a 2025 IEEE Access paper](https://arxiv.org/html/2508.20224v1)). Both report that calibrating the teacher first, for example by dividing its scores by its own fitted T, gives better students. **Weak to medium evidence: preprints and a journal paper, mostly images.**
- **Distillation can push the student past the teacher's confidence.** [Nagarajan et al. 2023 (Google)](https://arxiv.org/abs/2301.12923) found that the student becomes *more* confident than the teacher on rows where the teacher is already confident. **Medium evidence.**
- **Label smoothing and KD pull in opposite directions.** [Müller, Kornblith & Hinton 2019, "When Does Label Smoothing Help?" (NeurIPS)](https://arxiv.org/abs/1906.02629) found that a teacher trained with label smoothing is better calibrated but a *worse* teacher. [Lukasik et al. 2020 (ICML)](https://arxiv.org/abs/2003.02819) found the opposite *when labels are noisy*: smoothing the teacher helped the student. Our labels are noisy, so their result is closer to our case. The question is described as still contested ([Chandrasegaran et al. 2022](https://arxiv.org/abs/2206.14532)).

**A likely cause of our over-confidence (my own reasoning, not from a paper; test it)**

We compute the teacher's soft targets on the same rows it was just trained on. For the 200k r15 rows, the teacher was trained towards one-hot labels with alpha 0.7. Its probabilities on its own training rows are therefore likely close to one-hot and sharper than on unseen rows. The student then learns near-one-hot targets on two thirds of the data, which is close to plain hard-label training, and becomes over-confident.

Two standard ways to soften those targets:
- **Use teacher scores from rows it did not train on.** Train 2-5 teachers, each on part of the data, and score each row with a teacher that did not see it. This is called "out-of-fold" prediction. It costs more teacher time.
- **Divide the teacher's scores by its val-fitted T** (or a T above 1, as Hinton does) before handing them to the student.

Check this before changing alpha. It is cheap to measure: compare the average top probability of the teacher's soft targets on r15 train rows with its average top probability on val.

**About alpha**: no source gives a universal best value. Hinton found a low hard weight works well. Most fine-tuning papers tune alpha on held-out data. Changing alpha alone is unlikely to matter much compared with fixing the teacher's sharpness.

## 3. More rows or more distinct sources? Dedup, caps, active learning

**What the evidence says**

- **Our own data is the strongest evidence here.** New vendors raised the unseen-vendor holdout from 74.0 to 81.8 exact, while a bigger teacher on old data gave nothing. No paper outweighs that for our task.
- **More domains beats more rows from the same domains for OOD.** A theory paper ([an AAAI-24 paper; I did not confirm its exact title](https://ojs.aaai.org/index.php/AAAI/article/view/29497/30822)) argues that a model needs *many training domains*, not just many rows per domain. **Weak evidence: theory plus image benchmarks.** [Gokhale et al. 2022](https://arxiv.org/abs/2203.07653) found that more data and more diversity both help OOD, while *filtering* data hurt OOD. **Medium evidence.** [Zhang et al. 2023](https://arxiv.org/abs/2312.16243) found that more rows from the same mixture stop helping once the test shift is large. **Weak to medium evidence.** Together these support "more vendors over more rows from known vendors", but direct NLP evidence is thin.
- **Pre-trained transformers are more robust OOD, and more diverse pre-training helps** ([Hendrycks et al. 2020 (ACL)](https://arxiv.org/abs/2004.06100)). **Strong evidence, indirect.**
- **Deduplicate.** [Lee et al. 2022, "Deduplicating Training Data Makes Language Models Better" (ACL)](https://arxiv.org/abs/2107.06499) showed this for language models: duplicates waste compute and make the model memorise. **Strong evidence for language models, medium transfer.** For us, near-duplicate operations (the same CRUD template across many Microsoft Graph versions, for example) act like a hidden extra weight on large vendors. A per-vendor cap, or down-weighting rows that share the same normalised path and summary, is the obvious fix. I found no paper that tests per-source caps for text classifiers, so this is standard practice rather than proven. Test it.
- **Active learning (picking which rows to label) helps in some cases and not others.** [Ein-Dor et al. 2020, "Active Learning for BERT: An Empirical Study" (EMNLP)](https://aclanthology.org/2020.emnlp-main.638) report that it helps most with small labelling budgets and rare classes. I read only the abstract and second-hand summaries, not the tables. [Karamcheti et al. 2021, "Mind Your Outliers" (ACL)](https://arxiv.org/abs/2107.02331) found that picking the most uncertain rows can *fail* and do worse than random, because it picks unlearnable or noisy rows. **Medium evidence.** With 300k rows and a cheap rule-based first pass, the main value of disagreement is deciding *where to spend Sonnet and Opus*, which we already do. Picking which vendors to add is a diversity question more than an uncertainty question.
- **Dataset cartography.** [Swayamdipta et al. 2020 (EMNLP)](https://arxiv.org/abs/2009.10795) tracked each row's confidence across training and sorted rows into three groups:
  - "ambiguous" rows: training on these helped OOD most;
  - "hard-to-learn" rows: these were often mislabelled;
  - "easy" rows: these helped training get going.
  **Strong evidence, good transfer: it uses text classifiers.** We can run it cheaply by saving per-row probabilities at a few checkpoints during one training run.

## 4. Label noise from LLM labellers

**What the evidence says**

- **BERT copes with random noise, but noise-handling methods often do not help it on top of that.** [Zhu et al. 2022, "Is BERT Robust to Label Noise?" (ACL Insights workshop)](https://arxiv.org/abs/2204.09371) found that, for BERT-style models, common noise-handling methods often fail to improve accuracy and sometimes make it worse. A follow-up ([Agro & Aldarmaki 2023](https://arxiv.org/abs/2305.16337)) says BERT is fairly robust to *random* noise but not to *systematic* noise, meaning errors that depend on the text. LLM labelling errors are systematic: they cluster on the same kinds of operations, such as access-policy PUT/PATCH. **Medium evidence, good transfer.** The lesson: fix systematic noise at the source (rulings, the prompt order, rwxmap's pipeline). A clever loss will not do it.
- **Noise-robust losses** such as generalised CE ([Zhang & Sabuncu 2018](https://arxiv.org/abs/1805.07836)) and symmetric CE ([Wang et al. 2019](https://arxiv.org/abs/1908.06112)) were mostly tested on images with injected noise. Zhu et al. suggest the gains for BERT are small. **Weak transfer.**
- **Label smoothing is about as good as noise-correction methods** ([Lukasik et al. 2020](https://arxiv.org/abs/2003.02819)). **Medium evidence.** It is simple and also helps OOD calibration (section 5).
- **Find and drop likely-wrong labels.** "Confident learning" ([Northcutt et al. 2021, JAIR](https://arxiv.org/abs/1911.00068), the `cleanlab` library) flags rows where a model trained without that row strongly disagrees with the label. **Strong evidence, good transfer**, but it needs predictions on rows the model did not train on, the same out-of-fold setup as in section 2. Under our rules ("rwxmap's pipeline is the single label truth; never relabel on our side"), flagged rows should go back to rwxmap or be down-weighted. They should not be relabelled by us.
- **Weighting disputed rows: careful.** We give contested rows (resolved by Sonnet or Opus) weight 3.0. The noise literature usually gives *lower* weight to rows the labellers disagreed on, because those labels are less reliable. Cartography (section 3) argues the opposite: ambiguous rows teach the most. Both views have support, and I found no paper that settles weight 3 against weight 1 for LLM-cascade labels. Test it.

## 5. Calibration of fine-tuned small transformers

**What the evidence says**

- **Modern neural networks are over-confident, and fitting one temperature T on val fixes most of it** ([Guo et al. 2017, "On Calibration of Modern Neural Networks" (ICML)](https://arxiv.org/abs/1706.04599)). **Strong evidence, general.** We already do this.
- **For BERT-style models**, [Desai & Durrett 2020, "Calibration of Pre-trained Transformers" (EMNLP)](https://arxiv.org/abs/2003.07892) found three things:
  - in-domain, the models are fairly well calibrated, and temperature scaling fixes the rest;
  - *out-of-domain*, a T fitted in-domain does less;
  - label smoothing during training helped OOD calibration.
  **Strong evidence, good transfer.** This matters for us because the 0.90 cut-off is applied to *unseen vendors*, while T is fitted on val, which is in-distribution. Our val (97%) is easier than unseen vendors (90%), so a T fitted on val will tend to leave the model **too confident on unseen vendors**. Fitting T on a held-out set of unseen vendors (not the exam) would match real use better.
- **Label smoothing** improves calibration ([Müller et al. 2019](https://arxiv.org/abs/1906.02629); Desai & Durrett). It also caps the model's top probability. With smoothing 0.1 over 3 classes, the target for the top class is about 0.93. That interacts with our 0.90 cut-off, so T must be refitted and the lowering rate re-checked.
- **Focal loss** ([Mukhoti et al. 2020, NeurIPS](https://arxiv.org/abs/2002.09437)) gives better calibration than plain CE before any temperature, mostly on image models. After temperature scaling the gap shrinks. **Medium evidence, medium transfer.** Low priority, since we fit T anyway.
- **int8 quantisation and calibration**: I found **no study that measures calibration error for int8 BERT or MiniLM.**
  - Image work suggests better-calibrated models can lose more accuracy when quantised ([“On Calibration of Modern Quantized Efficient Neural Networks”, 2023](https://arxiv.org/abs/2309.13866)).
  - For large language models, the effect varies by model and dataset ([Proskurina et al. 2024](https://arxiv.org/abs/2405.00632)).
  Our own repo is better evidence: `export_r15.py` already measures int8 against fp32 probability differences. Under D142, int8 is information only. Keep checking the lowering decisions at 0.90 on int8 as well as fp32.

## 6. Asymmetric costs: build them into the loss, or set thresholds afterwards?

**What the evidence says**

- **With well-calibrated probabilities, the best decision for any cost table is a threshold rule, with no retraining needed** ([Elkan 2001, "The Foundations of Cost-Sensitive Learning" (IJCAI)](https://cseweb.ucsd.edu/~elkan/rescale.pdf)). Pick the answer with the lowest expected cost. With our costs, that means "only lower when p(lower letter) is very high". **Strong evidence (theory plus a classic paper), full transfer.** This is what the 0.90 cut-off does. It only works if the probabilities are well calibrated *on the data where it is applied*, which is why sections 2 and 5 matter most.
- **Cost-weighted losses** change what the model learns, not just the decision. [Buda et al. 2018](https://arxiv.org/abs/1710.05381) found that threshold-moving is a strong, simple baseline for class imbalance. **Medium evidence (images).** Our round 13 L3 experiment (a ×3 cost for too-loose answers) added nothing, which fits: a cost in the loss is usually no better than a threshold on calibrated probabilities. A cost in the loss also distorts the probabilities, which then makes T and the 0.90 cut-off harder to trust.
- **Bottom line**: keep the loss plain (no cost term), keep the probabilities calibrated, and put the asymmetry in the decision rule (the cut-off).

## 7. Practical recipes for MiniLM- or BERT-size classifiers on CPU

**What the evidence says**

- **LR and layer-wise LR decay.** [Sun et al. 2019, "How to Fine-Tune BERT for Text Classification?"](https://arxiv.org/abs/1905.05583) found that LR around 2e-5 worked best for BERT-base. Giving lower layers a smaller LR (each layer down gets about 0.95 times the LR of the layer above) gave small gains. **Strong evidence (much cited), medium transfer.** MiniLM has only 6 layers, so the effect should be smaller. Our 5e-5 is within the usual range (2e-5 to 5e-5). Small models usually tolerate the higher end.
- **Stability.** [Mosbach et al. 2021, "On the Stability of Fine-tuning BERT" (ICLR)](https://arxiv.org/abs/2006.04884) found that unstable runs come from too few training steps and from Adam without bias correction. Their fix is a small LR, warmup, and more steps. [Zhang et al. 2021, "Revisiting Few-sample BERT Fine-tuning" (ICLR)](https://arxiv.org/abs/2006.05987) agree. Those papers are about small datasets. With 300k rows and one epoch we are not in that situation. One run per stage with no repeat seeds remains a weak point. A val difference of a few tenths of a point between two recipes may be noise.
- **Epochs.** One epoch over a large set is common and fine. More passes mostly help small datasets. On CPU, a second epoch doubles the cost, and the evidence does not suggest a large gain at our size. If we try it, compare the end of epoch 1 with the end of epoch 2 inside one run.
- **Pooling.** all-MiniLM-L6-v2 was trained with **mean pooling** and an input length of 128 ([model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2); [Reimers & Gurevych 2019, Sentence-BERT](https://arxiv.org/abs/1908.10084) found mean pooling best for their training). Our `AutoModelForSequenceClassification` reads the [CLS] token through a pooler layer that sentence-transformers did not train. With full fine-tuning on 300k rows the difference is usually small. I found no paper that measures it for this exact model, so treat it as a cheap experiment with probably small gains.
- **max_len 128** matches how MiniLM was trained, and it is cheaper on CPU. Check how many rows get cut off (method + path + summary + description). If many lose the description's key words, try 192 or 256, which costs more time.
- **Freezing layers** saves CPU time, but it usually costs accuracy when the data is plentiful. Kumar et al. (LP-FT, above) suggest a different order: first train only the head with the body frozen, then fine-tune everything. They found this protects OOD accuracy. **Medium transfer.** It is a cheap first stage.
- **SetFit** ([Tunstall et al. 2022](https://arxiv.org/abs/2209.11055)) is built for *few* labels (8-64 per class). With 300k labels, ordinary fine-tuning is the right tool. Not relevant.
- **Smaller subsets to save CPU**: for hyperparameter checks (LR, pooling, alpha), train on a fixed 30-50k sample stratified by vendor. Compare variants on val and the unseen-vendor holdout. Only the winner gets the full run. This is ordinary practice, not a specific paper.

---

## What this means for round 16

Ranked by expected value per hour of CPU. "Test" means a small experiment on val plus an unseen-vendor holdout that is *not* exam #8. Under our rules, the exam is scored once and never tuned on.

1. **Keep adding new vendors. That is where the gain is.**
   - **Evidence**: our own 74.0 to 81.8 jump; diversity work in section 3.
   - **Do**: spend the effort on vendor breadth, not on more rows per known vendor. Add a per-vendor cap or near-duplicate down-weighting so the five big vendors (62% of the old corpus) do not dominate (Lee et al. 2022). **Test** the cap: train once with and once without it on the subset.

2. **Fix the teacher's sharpness before touching alpha.**
   - **Evidence**: section 2; students inherit and amplify teacher confidence (Yang & Song; Nagarajan et al.); the round 15 student came out at T 1.38. The likely cause is that the teacher's soft targets were computed on its own training rows, which it had trained towards one-hot.
   - **Do first (no training)**: compare the teacher's average top probability on r15 train rows with the same figure on val.
   - **Test**: either divide the teacher's scores by its val-fitted T before using them as soft targets (cheap), or use out-of-fold teacher predictions (2-3x teacher time). Keep alpha at 0.7 unless that test leaves the student still over-confident.

3. **Fit T where the model is actually used.**
   - **Evidence**: Desai & Durrett 2020; Guo et al. 2017.
   - **Problem**: val is 97% while unseen vendors are about 90%, so a val-fitted T will leave the model too confident on new vendors, where the 0.90 cut-off decides lowerings.
   - **Do**: hold back a few thousand rows from vendors not in training (separate from exam #8) and fit T there. **Test**: compare too-loose counts at 0.90 under the val T and the holdout T. Note: the baseline keeps its shipped T, so this applies only to the candidate's own T.

4. **Retrain from base unless a test shows warm starting is as good.**
   - **Evidence**: section 1.
   - **Why**: retraining from base is the safe default that worked in rounds 13 and 15. Warm starting from round 15 saves CPU, but nobody has tested it at our size, and the Ash & Adams warning comes from image models trained from random weights.
   - **Test (subset)**: three runs.
     - (a) from base on all rows;
     - (b) `--init` round 15 on new rows plus 20% old replay, at LR 2e-5 with fresh warmup and decay (Ibrahim et al.; Scialom et al.);
     - (c) the weight average of (b) and round 15 (WiSE-FT).
     Pick on the unseen-vendor holdout. If (b) or (c) matches (a), the saved time can go to the teacher.

5. **Keep the loss plain and the asymmetry in the cut-off.**
   - **Evidence**: Elkan 2001; our own L3 null result.
   - **Do**: no cost-weighted loss and no class weights. Spend the effort on calibration (items 2 and 3) instead, because the cut-off is only as good as the probabilities.

6. **Re-check the ×3 weight on contested rows.**
   - **Evidence**: section 4. The noise literature favours lower weight for disputed rows; cartography favours ambiguous rows. Nothing settles it for LLM-cascade labels.
   - **Test (subset)**: weight 3 against weight 1 on contested rows, and compare too-loose counts on the holdout.

7. **Try label smoothing (about 0.05-0.1) as one variant, not by default.**
   - **Evidence**: helps OOD calibration (Desai & Durrett) and noisy-label teachers (Lukasik et al.), but can hurt distillation (Müller et al.), and it caps confidence near our 0.90 line.
   - **Test**: on the teacher only, then compare the student's T and lowering rate.

8. **Run a cartography or confident-learning pass for rwxmap, not for us to relabel.**
   - **Evidence**: Swayamdipta et al. 2020; Northcutt et al. 2021.
   - **Do**: save per-row probabilities at a few checkpoints, list "hard-to-learn" and high-disagreement rows by vendor, and send them to rwxmap as candidates under their pipeline. It costs almost nothing extra if out-of-fold teachers (item 2) are trained anyway.

9. **Cheap recipe checks, low expected gain.**
   - **Evidence**: section 7.
   - **Test** on a 30-50k vendor-stratified subset:
     - mean pooling instead of [CLS] plus pooler (it matches how MiniLM was trained);
     - LR 3e-5 against 5e-5;
     - share of rows cut off at max_len 128.
   - Do not expect much from layer-wise LR decay, freezing, a second epoch, focal loss or SetFit at our size.

**Things not to assume (measure them instead)**
- That warm starting hurts or helps. No study matches our setup.
- That int8 keeps calibration. No int8 BERT calibration study was found, so keep measuring fp32 against int8 at the cut-off.
- That a val-fitted T holds on unseen vendors. The evidence says it probably does not.
- That small val differences between single runs are real. Use the same seed for both arms and, where affordable, a second seed for the winner.

**Caveats on this review**: I read abstracts, search summaries and some full texts, not every paper end to end. Specific numbers I did not check in the paper are marked as such above: the 5%/25% replay in Ibrahim et al., Ein-Dor's per-setting results, and the exact noise type in Zhu et al. Every link points to the paper's arXiv, ACL Anthology, proceedings or author page.
