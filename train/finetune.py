"""Fine-tune all-MiniLM-L6-v2 with a 3-way head on CPU.
  python3 train/finetune.py --n 5000 --epochs 1 --tag smoke
  nohup python3 train/finetune.py --epochs 2 --tag full > data/train/finetune.log 2>&1 &
Dynamic padding with length bucketing, max_len 128 (p95 of the formatted text is 140 tokens; the leaning is first so it is never cut).
Checkpoints every --ckpt steps and per epoch to data/train/ckpt-<tag>/ ; resumes from last.pt if present."""
import argparse, time, json, os, random, math
import numpy as np, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, get_linear_schedule_with_warmup
from common import *
ap = argparse.ArgumentParser()
ap.add_argument('--n', type=int, default=0); ap.add_argument('--epochs', type=float, default=1)
ap.add_argument('--bs', type=int, default=32); ap.add_argument('--lr', type=float, default=5e-5)
ap.add_argument('--max_len', type=int, default=128); ap.add_argument('--tag', default='run'); ap.add_argument('--ckpt', type=int, default=500); ap.add_argument('--threads', type=int, default=8)
ap.add_argument('--soft', action='store_true', help='round 8: soft targets from Jev p (see common.soft_targets)')
ap.add_argument('--alpha', type=float, default=0.7, help='weight of soft CE; loss = alpha*soft + (1-alpha)*hard')
ap.add_argument('--x_weight', type=float, default=1.0, help='class weight on x in both CE terms')
a = ap.parse_args()
torch.set_num_threads(a.threads); torch.manual_seed(1); random.seed(1)
BASE = 'sentence-transformers/all-MiniLM-L6-v2'
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForSequenceClassification.from_pretrained(BASE, num_labels=3)
tr, va, ev = load_split('train'), load_split('val'), load_split('v3eval')
if a.n: tr = tr.sample(a.n, random_state=1)
texts, ys = list(tr.text), tr.y.values
soft = torch.tensor(soft_targets(tr)) if a.soft else None
cw = torch.tensor([1.0, 1.0, a.x_weight])
enc = tok(texts, truncation=True, max_length=a.max_len)['input_ids']
def batches(order):
    # bucket: sort within chunks of 50 batches by length so padding is small, then shuffle batch order
    chunks = [order[i:i + a.bs * 50] for i in range(0, len(order), a.bs * 50)]
    out = []
    for c in chunks:
        c = sorted(c, key=lambda i: len(enc[i])); out += [c[i:i + a.bs] for i in range(0, len(c), a.bs)]
    random.shuffle(out); return out
def collate(ids, E, Y=None):
    L = max(len(E[i]) for i in ids); x = torch.zeros(len(ids), L, dtype=torch.long); m = torch.zeros(len(ids), L, dtype=torch.long)
    for j, i in enumerate(ids): x[j, :len(E[i])] = torch.tensor(E[i]); m[j, :len(E[i])] = 1
    return x, m
steps_per_epoch = math.ceil(len(texts) / a.bs); total = int(steps_per_epoch * a.epochs)
opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
sch = get_linear_schedule_with_warmup(opt, int(0.06 * total), total)
ckdir = os.path.join(OUT, 'ckpt-' + a.tag); os.makedirs(ckdir, exist_ok=True); last = os.path.join(ckdir, 'last.pt')
step = 0
if os.path.exists(last):
    s = torch.load(last); model.load_state_dict(s['model']); opt.load_state_dict(s['opt']); sch.load_state_dict(s['sch']); step = s['step']; print('resumed at step', step, flush=True)
def save():
    torch.save({'model': model.state_dict(), 'opt': opt.state_dict(), 'sch': sch.state_dict(), 'step': step}, last + '.tmp'); os.replace(last + '.tmp', last)
@torch.no_grad()
def predict(df):
    model.eval(); E = tok(list(df.text), truncation=True, max_length=a.max_len)['input_ids']
    order = sorted(range(len(E)), key=lambda i: len(E[i])); P = np.zeros((len(E), 3), dtype=np.float32)
    for i in range(0, len(order), 128):
        ids = order[i:i + 128]; x, m = collate(ids, E)
        P[ids] = torch.softmax(model(input_ids=x, attention_mask=m).logits, -1).numpy()
    model.train(); return P
def evaluate(tag):
    Pva = predict(va); acc = float((Pva.argmax(1) == va.y.values).mean())
    t0 = time.time(); Pev = predict(ev); batch_ms = (time.time() - t0) / len(ev) * 1000
    rep = v3_report(ev, Pev); print(f'== eval {tag}: val acc {acc*100:.2f}%  (v3 batched {batch_ms:.2f} ms/op)', flush=True); print_report(rep)
    json.dump({'tag': tag, 'step': step, 'val_acc': round(acc*100, 2), 'v3_batch_ms_per_op': round(batch_ms, 2), 'v3': rep}, open(os.path.join(OUT, f'finetune-{a.tag}-results.json'), 'w'), indent=1)
    np.save(os.path.join(OUT, f'probs-{a.tag}-v3eval.npy'), Pev); np.save(os.path.join(OUT, f'probs-{a.tag}-val.npy'), Pva)
model.train(); t0 = time.time(); t_start_step = step; ema = None; ep = 0
print(f'rows {len(texts)} steps/epoch {steps_per_epoch} total {total}', flush=True)
done = step >= total
while not done:
    random.seed(100 + ep); order = list(range(len(texts))); random.shuffle(order)
    bl = batches(order); skip = step % steps_per_epoch if ep == step // steps_per_epoch else 0
    for b in bl[skip:]:
        x, m = collate(b, enc); y = torch.tensor(ys[b])
        logits = model(input_ids=x, attention_mask=m).logits
        hard = torch.nn.functional.cross_entropy(logits, y, weight=cw)
        if soft is not None:
            sce = -(soft[b] * cw * torch.log_softmax(logits, -1)).sum(1).mean()
            loss = a.alpha * sce + (1 - a.alpha) * hard
        else: loss = hard
        loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sch.step(); opt.zero_grad(); step += 1
        ema = loss.item() if ema is None else 0.98 * ema + 0.02 * loss.item()
        if step % 25 == 0:
            el = time.time() - t0; rate = (step - t_start_step) / el
            print(f'step {step}/{total} loss {ema:.4f} {rate:.2f} step/s  elapsed {el/60:.1f}m  eta {(total-step)/rate/60:.1f}m', flush=True)
        if step % a.ckpt == 0: save()
        if step >= total: done = True; break
    ep += 1; save(); print(f'epoch {ep} done step {step}', flush=True)
    if not done and ep < a.epochs: evaluate(f'epoch{ep}')
evaluate('final')
model.save_pretrained(os.path.join(ckdir, 'final')); tok.save_pretrained(os.path.join(ckdir, 'final'))
n = sum(p.numel() for p in model.parameters()); print(f'params {n/1e6:.1f}M fp32 {n*4/1e6:.1f} MB; train time {(time.time()-t0)/60:.1f} m', flush=True)
