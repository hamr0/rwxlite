"""Round 12, step 2: mine the mistakes of 0.2.0 fp32 (and Jev's overruled labels) from every human-labelled set.
No training, no Haiku. Writes NEW files only into data/r12/ (gitignored): mistakes.csv, jev_overruled.csv, mistakes-raw.json, summary.md.
Run from the repo root:  .venv/bin/python m1/r12-mine.py
Model: published 0.2.0 fp32 (data/m1/release/model-fp32.onnx, T 0.844), batch 1, via train/exam3_common.probs (the same path as exam3/4 predictions).
Rules: argmax (raw letter), a_none (mode a, no abstain), cli (rwxmap real-product rows, exam #3 / #4 only; read from the rwxmap checkout, not copied).
Jev letter: exam #3/#4 = rwxmap rows-c-jev.csv (the real Jev run); gates = the round-6 recipe label applied to the stored Jev p (what training would get);
r9-hand = key.csv current_label (the recipe label); fresh exam = none (Jev was never run on it).
"""
import os, sys, csv, json, gzip, hashlib, subprocess, collections, re
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'train'))
import numpy as np
import exam_score as E
import exam3_common as C
from common import ORDER, LABELS, cred_hit

D = os.path.join(REPO, 'data'); OUT = os.path.join(D, 'r12'); os.makedirs(OUT, exist_ok=True)
RWXMAP = os.environ.get('RWXMAP_DIR', os.path.abspath(os.path.join(REPO, '..', 'rwxmap', 'data')))
EX3_TRUTH = os.path.join(RWXMAP, 'exam3-2026-11-04', 'truth.csv')
EX3_SHA = '929725d51397098b6f45d86a5a551e7f0c095875557a944c02e08930efdab3c0'
jl = lambda f: [json.loads(l) for l in open(f) if l.strip()]
rcsv = lambda f: list(csv.DictReader(open(f, newline='', encoding='utf-8')))
okey = lambda r: (r['provider'], str(r['method']).upper(), r['path'], r.get('operationId') or '')

# ---------------------------------------------------------------- sets
SETS = {  # name -> (ops csv or inputs.jsonl, truth)
    'exam4': ('inputs', os.path.join(D, 'exam4')),
    'exam3': ('inputs', os.path.join(D, 'exam3')),
    'fresh': ('ops', os.path.join(D, 'exam-2026-11-03-fresh', 'ops.csv')),
    'gate1': ('ops', os.path.join(D, 'gate-2026-11-03', 'blind.csv')),
    'gate2': ('ops', os.path.join(D, 'gate-2026-11-04', 'blind.csv')),
    'gate3': ('ops', os.path.join(D, 'gate-2026-11-06', 'blind.csv')),
    'gate4': ('ops', os.path.join(D, 'gate-2026-11-07', 'blind.csv')),
    'r9hand': ('ops', os.path.join(D, 'r9-hand', 'blind.csv')),
}
TRUTH = {'exam4': os.path.join(D, 'exam4', 'truth.csv'), 'exam3': EX3_TRUTH, 'fresh': os.path.join(D, 'exam-2026-11-03-fresh', 'truth.csv'),
         'gate1': os.path.join(D, 'gate-2026-11-03', 'truth.csv'), 'gate2': os.path.join(D, 'gate-2026-11-04', 'truth.csv'),
         'gate3': os.path.join(D, 'gate-2026-11-06', 'truth.csv'), 'gate4': os.path.join(D, 'gate-2026-11-07', 'truth.csv')}

def inputs_for(name):
    kind, src = SETS[name]
    if kind == 'inputs': return jl(os.path.join(src, 'inputs.jsonl'))
    d = os.path.join(OUT, 'inputs', name)
    if not os.path.exists(os.path.join(d, 'inputs.jsonl')):
        subprocess.run(['node', os.path.join(REPO, 'm0', 'exam3-inputs.mjs'), src, d], check=True, cwd=REPO)
    return jl(os.path.join(d, 'inputs.jsonl'))

def truth_for(name):
    if name == 'r9hand':
        A = {r['id']: r['label'] for r in rcsv(os.path.join(D, 'r9-hand', 'labels-A.csv'))}; B = {r['id']: r['label'] for r in rcsv(os.path.join(D, 'r9-hand', 'labels-B.csv'))}
        return {i: max(A[i], B[i], key=lambda l: ORDER[l]) for i in A}   # stricter of A and B (r9-hand README)
    if name == 'exam3':
        got = hashlib.sha256(open(EX3_TRUTH, 'rb').read()).hexdigest(); assert got == EX3_SHA, f'exam3 truth sha {got}'
    return {r['id']: r['label'] for r in rcsv(TRUTH[name])}

# ---------------------------------------------------------------- model
def run_model(rows):
    from transformers import AutoTokenizer
    C.check_hashes()
    tok = AutoTokenizer.from_pretrained(os.path.join(REPO, 'data', 'train', 'ckpt-r8soft', 'final'))
    ids = tok([r['text'] for r in rows], truncation=True, max_length=C.MAXLEN)['input_ids']
    path, _, T = C.MODELS['v020-fp32']
    return C.probs(path, ids, T)

MODEL_STR = json.load(open(os.path.join(D, 'm1', 'release', 'manifest-exact.json')))['model']

# ---------------------------------------------------------------- Jev letters
def jev_letters_gate(name, rows, ids_txt):
    """Round-6 recipe label from stored Jev p (gate-score.mjs label2, cuts lower .2 / raise-wx .6 / raise-get .2 / rcut .2, narrow credential rule)."""
    mech = {}
    with gzip.open(os.path.join(D, 'm0', 'mechanical.jsonl.gz'), 'rt') as f:
        for l in f:
            if not l.strip(): continue
            r = json.loads(l); mech.setdefault(okey(r), r)
    def mp(fn):
        return {x['id']: x['p'] for x in jl(os.path.join(D, 'm0', fn)) if isinstance(x.get('p'), (int, float))}
    p1, p2, c1, c2 = mp('jev-pass1.jsonl'), mp('jev-pass2.jsonl'), mp('jev-post-changes.jsonl'), mp('jev-post-changes-2.jsonl')
    TIER = {'jev-lower': 'lower', 'jev-raise-wx': 'raise-wx', 'jev-raise-get': 'raise-get'}
    out = {}; miss = 0
    for r in rows:
        m = mech.get(okey(r))
        if not m: miss += 1; continue
        a, c = p1.get(m['id']), p2.get(m['id']); p = None if a is None else (a if c is None else (a + c) / 2)
        pc = c1.get(m['id']); pc = None if pc is None else ((pc + c2[m['id']]) / 2 if m['id'] in c2 else pc)
        t = TIER.get(m.get('jev_tier'), 'none'); l = m['class']
        if t != 'none' and p is not None:
            if t == 'lower' and p < 0.20: l = 'r' if (pc is not None and pc < 0.20) else 'w'
            elif t == 'raise-wx' and p >= 0.60: l = 'x'
            elif t == 'raise-get' and p >= 0.20: l = 'w'
        if cred_hit({'method': r['method'], 'operationId': r.get('operationId'), 'summary': r.get('summary'), 'path': r['path']}): l = 'x'
        out[r['id']] = {'letter': l, 'p': p, 'tier': t}
    return out, miss

def jev_letters_rwxmap(name):
    f = os.path.join(RWXMAP, f'{name}-2026-11-04', 'score', 'rows-c-jev.csv')
    return {r['id']: {'letter': r['letter'], 'p': None, 'tier': r['evidence']} for r in rcsv(f)}

# ---------------------------------------------------------------- CLI rows (rwxmap real product)
def cli_rows(name):
    s = os.path.join(RWXMAP, f'{name}-2026-11-04', 'score')
    mech = {r['id']: r for r in rcsv(os.path.join(s, 'rows-mech.csv'))}
    out = {}
    for r in rcsv(os.path.join(s, 'rows-a-fp32-base.csv' if name == 'exam4' else 'rows-a-fp32.csv')):
        m = mech[r['id']]['letter']; l = r['letter']
        if l != m: path = ('model-raise' if ORDER[l] > ORDER[m] else 'model-lower') if r['evidence'] == 'rwxlite' else f"{r['evidence']}-{'raise' if ORDER[l] > ORDER[m] else 'lower'}"
        elif r['review'] == 'settled': path = 'settled-mech'
        elif r['review'] == 'tight': path = 'undecided-x'
        else: path = 'kept-mech'
        out[r['id']] = {'letter': l, 'path': path, 'review': r['review'], 'evidence': r['evidence'], 'mech_cli': m}
    return out

# ---------------------------------------------------------------- training lookup
def load_train():
    T = {}
    for tag, f in (('r8', 'train/train.jsonl'), ('r8', 'train/val.jsonl'), ('r11', 'round11/train.jsonl'), ('r11', 'round11/val.jsonl')):
        p = os.path.join(D, f)
        if not os.path.exists(p): continue
        for l in open(p):
            if not l.strip(): continue
            r = json.loads(l); T.setdefault(okey(r), []).append((tag, os.path.basename(os.path.dirname(f)) + '/' + os.path.basename(f), r['label'], r['status']))
    return T

kind_of = lambda letter, truth: 'too_loose' if ORDER[letter] < ORDER[truth] else 'too_tight'

def main():
    mist = []; jev_rows = []; counts = {}; unusable = []
    TR = load_train()
    for name in SETS:
        rows = inputs_for(name); truth = truth_for(name)
        assert {r['id'] for r in rows} == set(truth), f'{name}: join not 1:1 ({len(rows)} vs {len(truth)})'
        P = run_model(rows); pa = E.mode_a(rows, P)
        if name in ('exam3', 'exam4'):   # sanity: recomputed == committed predictions-v020-fp32.csv
            pr = {r['id']: r for r in rcsv(os.path.join(D, name, 'predictions-v020-fp32.csv'))}
            bad = sum(1 for i, r in enumerate(rows) if pr[r['id']]['a_none'] != LABELS[pa[i]]); assert bad == 0, f'{name}: {bad} a_none differ from committed predictions'
        cli = cli_rows(name) if name in ('exam3', 'exam4') else {}
        c = {'rows': len(rows), 'rules': {}}
        letters = {'argmax': [LABELS[int(k)] for k in P.argmax(1)], 'a_none': [LABELS[int(k)] for k in pa]}
        for i, r in enumerate(rows):
            t = truth[r['id']]; pr = [round(float(x), 6) for x in P[i]]
            for rule in ('argmax', 'a_none', 'cli'):
                if rule == 'cli':
                    if r['id'] not in cli: continue
                    ml, dpath = cli[r['id']]['letter'], cli[r['id']]['path']
                else:
                    ml, dpath = letters[rule][i], ('lower' if ORDER[ml_ := letters[rule][i]] < ORDER[r['class']] else 'raise' if ORDER[ml_] > ORDER[r['class']] else 'keep')
                s = c['rules'].setdefault(rule, collections.Counter()); s['n'] += 1
                if ml == t: s['right'] += 1; continue
                k = kind_of(ml, t); s[k] += 1
                mist.append({'set': name, 'id': r['id'], 'vendor': r['provider'], 'method': str(r['method']).upper(), 'path': r['path'], 'operationId': r.get('operationId', ''),
                             'summary': re.sub(r'\s+', ' ', r.get('summary') or '')[:140], 'truth': t, 'model_letter': ml, 'mech_letter': r['class'], 'mech_rule': r['rule'], 'kind': k,
                             'decision_path': dpath, 'p_r': pr[0], 'p_w': pr[1], 'p_x': pr[2], 'rule': rule, 'model': MODEL_STR})
        counts[name] = c
        # Jev
        jev = None
        if name in ('exam3', 'exam4'): jev = jev_letters_rwxmap({'exam3': 'exam3', 'exam4': 'exam4'}[name]); src = 'rwxmap rows-c-jev.csv (real Jev run)'
        elif name.startswith('gate'):
            ids_txt = None; jev, miss = jev_letters_gate(name, rows, ids_txt); src = 'round-6 recipe on stored Jev p'; c['jev_unjoined'] = miss
        elif name == 'r9hand':
            key = {r['ag_id']: r for r in rcsv(os.path.join(D, 'r9-hand', 'key.csv'))}
            key = {r['id']: r for r in rcsv(os.path.join(D, 'r9-hand', 'key.csv'))}
            jev = {i: {'letter': k['current_label'], 'p': None, 'tier': k['shape']} for i, k in key.items()}; src = 'key.csv current_label (r6 recipe label from Jev)'
        c['jev_source'] = src if jev else 'none (Jev never run on this set)'
        if jev:
            c['jev_n'] = len(jev); c['jev_overruled'] = 0; c['jev_overruled_in_train_wrong'] = 0; c['jev_overruled_in_train'] = 0
            byid = {r['id']: r for r in rows}
            for i, j in jev.items():
                t = truth[i]
                if j['letter'] == t: continue
                r = byid[i]; c['jev_overruled'] += 1; hits = TR.get(okey(r), [])
                wrong = [h for h in hits if h[2] != t]
                if hits: c['jev_overruled_in_train'] += 1
                if wrong: c['jev_overruled_in_train_wrong'] += 1
                jev_rows.append({'set': name, 'id': i, 'vendor': r['provider'], 'method': str(r['method']).upper(), 'path': r['path'], 'operationId': r.get('operationId', ''),
                                 'summary': re.sub(r'\s+', ' ', r.get('summary') or '')[:140], 'truth': t, 'jev_letter': j['letter'], 'mech_letter': r['class'], 'mech_rule': r['rule'],
                                 'kind': kind_of(j['letter'], t), 'jev_source': src, 'jev_detail': j['tier'], 'jev_p': '' if j['p'] is None else round(j['p'], 3),
                                 'in_training': bool(hits), 'train_labels': ';'.join(f'{h[1]}:{h[2]}({h[3]})' for h in hits), 'in_training_with_wrong_label': bool(wrong)})
        print(name, {k: dict(v) if isinstance(v, collections.Counter) else v for k, v in c['rules'].items()}, flush=True)
    # write
    cols = ['set', 'id', 'vendor', 'method', 'path', 'operationId', 'summary', 'truth', 'model_letter', 'mech_letter', 'mech_rule', 'kind', 'decision_path', 'p_r', 'p_w', 'p_x', 'rule', 'model']
    for fn, rs, cs in (('mistakes.csv', mist, cols), ('jev_overruled.csv', jev_rows, list(jev_rows[0].keys()))):
        with open(os.path.join(OUT, fn), 'w', newline='') as f:
            w = csv.DictWriter(f, cs); w.writeheader(); w.writerows(rs)
    json.dump({'counts': {k: {**v, 'rules': {a: dict(b) for a, b in v['rules'].items()}} for k, v in counts.items()}}, open(os.path.join(OUT, 'mistakes-raw.json'), 'w'), indent=1)
    sys.path.insert(0, os.path.dirname(__file__))
    import importlib.util
    spec = importlib.util.spec_from_file_location('r12summ', os.path.join(os.path.dirname(__file__), 'r12-summary.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.write(OUT, MODEL_STR)

if __name__ == '__main__': main()
