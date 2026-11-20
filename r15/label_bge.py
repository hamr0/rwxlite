"""Round 15 labelling, opinion 1 (server): bge-base teacher logits over the model-input texts, resumable in chunks.
  ~/rwxlite-train/.venv/bin/python label_bge.py --ckpt CKPT --texts texts.jsonl --out DIR --threads 3
texts.jsonl lines: {op_id, text}. Same tokenizer, max_len 128 and padded batches sorted by length as train/teacher_probs.py (round 14 teacher run).
Each chunk of --chunk rows is saved as DIR/chunk-NNNNN.npy (float32 logits (rows,3), RAW, no temperature) + a done-marker is the file itself (written via tmp+rename);
an existing chunk is skipped, so re-running resumes. Temperature is applied later on the laptop. Prints rows/s, ETA and peak RSS."""
import argparse, os, json, time, resource
import numpy as np, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
ap = argparse.ArgumentParser()
ap.add_argument('--ckpt', required=True); ap.add_argument('--texts', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--chunk', type=int, default=4000); ap.add_argument('--bs', type=int, default=64); ap.add_argument('--threads', type=int, default=3); ap.add_argument('--max_len', type=int, default=128)
a = ap.parse_args(); torch.set_num_threads(a.threads); os.makedirs(a.out, exist_ok=True)
rows = [json.loads(l) for l in open(a.texts) if l.strip()]
tok = AutoTokenizer.from_pretrained(a.ckpt); model = AutoModelForSequenceClassification.from_pretrained(a.ckpt).eval()
t0 = time.time(); done0 = 0; n = len(rows)
for c0 in range(0, n, a.chunk):
    fn = os.path.join(a.out, f'chunk-{c0 // a.chunk:05d}.npy')
    if os.path.exists(fn): done0 += min(a.chunk, n - c0); continue
    part = rows[c0:c0 + a.chunk]; E = tok([r['text'] for r in part], truncation=True, max_length=a.max_len)['input_ids']
    order = sorted(range(len(E)), key=lambda i: len(E[i])); L = np.zeros((len(E), 3), dtype=np.float32)
    with torch.no_grad():
        for i in range(0, len(order), a.bs):
            ids = order[i:i + a.bs]; w = max(len(E[j]) for j in ids)
            x = torch.zeros(len(ids), w, dtype=torch.long); m = torch.zeros(len(ids), w, dtype=torch.long)
            for r, j in enumerate(ids): x[r, :len(E[j])] = torch.tensor(E[j]); m[r, :len(E[j])] = 1
            L[ids] = model(input_ids=x, attention_mask=m).logits.float().numpy()
    np.save(fn + '.tmp.npy', L); os.replace(fn + '.tmp.npy', fn)
    done = c0 + len(part); el = time.time() - t0; rate = (done - done0) / el
    print(f'rows {done}/{n} {rate:.1f} rows/s elapsed {el/60:.1f}m eta {(n-done)/rate/60:.1f}m peakRSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f}MB', flush=True)
print('ALL DONE', n, 'rows', f'{(time.time()-t0)/60:.1f}m', flush=True)
