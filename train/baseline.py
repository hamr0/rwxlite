"""TF-IDF (word + char n-grams) + logistic regression. Run: python3 train/baseline.py"""
import time, json, pickle, os
import numpy as np, scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from common import *
tr, va, ev = load_split('train'), load_split('val'), load_split('v3eval')
wv = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=300000, sublinear_tf=True, token_pattern=r'[A-Za-z0-9_]+')
cv = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), min_df=3, max_features=300000, sublinear_tf=True)
t0 = time.time()
Xtr = sp.hstack([wv.fit_transform(tr.text), cv.fit_transform(tr.text)]).tocsr()
feat = lambda s: sp.hstack([wv.transform(s), cv.transform(s)]).tocsr()
clf = LogisticRegression(C=10, max_iter=300, solver='saga' if False else 'lbfgs', n_jobs=8)
clf.fit(Xtr, tr.y.values); fit_s = time.time() - t0
def proba(df): return clf.predict_proba(feat(df.text))
Pva = proba(va); acc = (Pva.argmax(1) == va.y.values).mean()
print(f'fit {fit_s:.0f}s  val acc vs target {acc*100:.2f}% (n={len(va)})')
Pev = proba(ev); rep = v3_report(ev, Pev); print_report(rep)
# inference timing per op (single-op, as the product would call it)
texts = list(ev.text.values[:300]); t0 = time.time()
for s in texts: clf.predict_proba(feat([s]))
per_op_ms = (time.time() - t0) / len(texts) * 1000
t0 = time.time(); proba(ev); batch_ms = (time.time() - t0) / len(ev) * 1000
pickle.dump((wv, cv, clf), open(os.path.join(OUT, 'baseline.pkl'), 'wb')); size = os.path.getsize(os.path.join(OUT, 'baseline.pkl')) / 1e6
res = {'val_acc': round(acc*100, 2), 'fit_s': round(fit_s), 'per_op_ms_single': round(per_op_ms, 2), 'per_op_ms_batch': round(batch_ms, 3), 'model_mb': round(size, 1), 'v3': rep}
json.dump(res, open(os.path.join(OUT, 'baseline-results.json'), 'w'), indent=1)
print(f'per-op {per_op_ms:.2f} ms single, {batch_ms:.3f} ms batched; pickle {size:.1f} MB')
