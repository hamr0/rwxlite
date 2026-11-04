"""M1: write the Python side of the Node parity checks (text format + token ids).

  .venv/bin/python m1/make_fixtures.py
    test/fixtures/parity.jsonl   committed: the 949 fresh-exam rows (state, lean, text, ids) + edge strings (text, ids)
    data/m1/corpus-parity.jsonl  local only: both exams' 5,228 rows + every train/val/v3eval text (102k)
Checked by test/text.test.js, test/tokenizer.test.js (fixture) and m1/check-corpus.mjs (corpus).
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'train'))
from common import ROOT, OUT, fmt_text
from transformers import AutoTokenizer

CKPT = os.path.join(OUT, 'ckpt-r8soft', 'final')
tok = AutoTokenizer.from_pretrained(CKPT)
ids = lambda texts: tok(texts, truncation=True, max_length=128)['input_ids']

EDGE = ['', 'lean: x path-verb | DELETE /v1/{id}', 'Café naïve résumé Ünïcödé', 'Ｆｕｌｌｗｉｄｔｈ ＡＢＣ', '中文字符 and 日本語 かな',
        'emoji 🚀 test 👍🏽 ok', 'tabs\tand\nnewlines\r\nmixed', 'zero​width‍j', 'soft­hyphen', 'nbsp here',
        "don't won’t «quote» —dash– …", 'a' * 150, 'x' + 'é' * 120, 'PUT /a/b_c-d.e~f', 'snake_case_operationId camelCaseOpId',
        '<b>html</b> &amp; &lt;tag&gt;', 'İstanbul ǅ ß ẞ', 'ﬁ ligature', '\u0000nul\u0001ctl\u007fdel', 'math ∑ ≥ ≠ µ Ω',
        ' '.join(['word'] * 200), 'arabic العربية hebrew עברית', 'thai ภาษาไทย devanagari हिन्दी', 'korean 한국어']

def exam_rows(path):
    out = []
    for l in open(path):
        if not l.strip(): continue
        r = json.loads(l)
        out.append({'state': {k: r.get(k) for k in ('method', 'path', 'operationId', 'summary', 'description')},
                    'lean': {'class': r['class'], 'rule': r['rule']}, 'text': fmt_text(r)})
    return out

def with_ids(rows):
    for r, i in zip(rows, ids([r['text'] for r in rows])): r['ids'] = i
    return rows

fresh = with_ids(exam_rows(os.path.join(ROOT, 'data', 'exam-fresh-r8soft', 'inputs.jsonl')))
edge = with_ids([{'text': t} for t in EDGE])
os.makedirs(os.path.join(ROOT, 'test', 'fixtures'), exist_ok=True)
with open(os.path.join(ROOT, 'test', 'fixtures', 'parity.jsonl'), 'w', encoding='utf-8') as f:
    for r in fresh + edge: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('fixture rows', len(fresh) + len(edge))

old = with_ids(exam_rows(os.path.join(ROOT, 'data', 'exam-r8soft', 'inputs.jsonl')))
texts = []
for s in ('train', 'val', 'v3eval'):
    texts += [json.loads(l)['text'] for l in open(os.path.join(OUT, s + '.jsonl')) if l.strip()]
corpus = with_ids([{'text': t} for t in texts])
with open(os.path.join(ROOT, 'data', 'm1', 'corpus-parity.jsonl'), 'w', encoding='utf-8') as f:
    for r in fresh + old + corpus: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('corpus rows', len(fresh) + len(old) + len(corpus))
