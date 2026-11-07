"""Vendor labels step A, part 2: run the shipped 0.2.0 fp32 checkpoint on every joined row. Same path as train/r12_predict.py:
PyTorch fp32, CPU, batch 1, max_len 128, tokenizer of ckpt-r11, text = train/common.fmt_text with the current rwxmap mechanical class/rule (vendor/mech.mjs),
QUERY->GET and credential-set->cant-undo-verb as in the shipped src/text.js. Saves raw logits (T applied later, shipped T 0.844).
  python3 -I vendor/predict.py <vendor-dir>   (needs data/vendor/joined.jsonl and mech.json)"""
import sys, os, json, time, hashlib
sys.path.append(os.path.expanduser('~/.local/lib/python3.14/site-packages'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'train'))
import numpy as np, torch
from common import fmt_text, ROOT
from transformers import AutoTokenizer, AutoModelForSequenceClassification
V = sys.argv[1]; torch.set_num_threads(4)
J = [json.loads(l) for l in open(os.path.join(V, 'joined.jsonl'))]; M = json.load(open(os.path.join(V, 'mech.json')))['v']
assert len(J) == len(M)
texts = {}
for j, m in zip(J, M):
    assert m['id'] == j['id']
    r = {'class': m['cls'], 'rule': {'credential-set': 'cant-undo-verb'}.get(m['rule'], m['rule']), 'method': 'GET' if j['method'].upper() == 'QUERY' else j['method'],
         'path': j['path'], 'operationId': j['operationId'], 'summary': j['summary'], 'description': j['description']}
    j['text'] = fmt_text(r); j['key'] = hashlib.sha1(j['text'].encode()).hexdigest(); texts[j['key']] = j['text']
d = os.path.join(ROOT, 'data/train/ckpt-r8soft/final'); tok = AutoTokenizer.from_pretrained(os.path.join(ROOT, 'data/train/ckpt-r11/final'))
model = AutoModelForSequenceClassification.from_pretrained(d, num_labels=3).eval()
sha = hashlib.sha256(open(os.path.join(d, 'model.safetensors'), 'rb').read()).hexdigest(); print('model sha256', sha, 'unique texts', len(texts), 'rows', len(J), flush=True)
out = open(os.path.join(V, 'logits.jsonl'), 'w'); t0 = time.time()
with torch.no_grad():
    for i, (k, t) in enumerate(texts.items()):
        ids = tok([t], truncation=True, max_length=128)['input_ids'][0]; a = torch.tensor([ids])
        L = model(input_ids=a, attention_mask=torch.ones_like(a)).logits[0].double().numpy()
        out.write(json.dumps({'key': k, 'logits': L.tolist()}) + '\n')
        if i % 1000 == 0: print(i, round(time.time() - t0), 's', flush=True)
out.close(); dt = time.time() - t0
json.dump({'model_sha256': sha, 'unique_texts': len(texts), 'rows': len(J), 'seconds': round(dt, 1), 'ms_per_text': round(1000 * dt / len(texts), 2), 'T': 0.844}, open(os.path.join(V, 'predict-meta.json'), 'w'), indent=1)
print('done', round(dt), 's')
