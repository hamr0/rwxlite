"""Builds data/r12/summary.md from mistakes.csv, jev_overruled.csv, mistakes-raw.json (all written by m1/r12-mine.py). Pure text; no model."""
import os, csv, json, re, collections

rcsv = lambda f: list(csv.DictReader(open(f, newline='', encoding='utf-8')))
SETS = ['exam4', 'exam3', 'fresh', 'gate1', 'gate2', 'gate3', 'gate4', 'r9hand']
NAMES = {'exam4': 'exam #4 (1505)', 'exam3': 'exam #3 (1377)', 'fresh': 'fresh exam 2026-11-03 (949)', 'gate1': 'gate-1 11-03 (600)', 'gate2': 'gate-2 11-04 (600)',
         'gate3': 'gate-3 11-06 (800)', 'gate4': 'gate-4 11-07 (800)', 'r9hand': 'r9-hand (1200)'}

# Ordered; first match wins. Matched against "METHOD path operationId summary" lower-cased, camelCase split.
LOOSE = [
    ('logout / session end via GET', r'^get .*(logout|log out|signout|sign out)'),
    ('credential / secret / password / key / token written or issued', r'(password|passwd|secret|credential|api[ _-]?key|apikey|auth ?key|app ?key|passcode|totp|token|certificate|csr|signing|keys?/)'),
    ('stop / pause / cancel / deny / disconnect / unlink / disable / shutdown (cut something off)', r'\b(stop|pause|cancel|deny|disconnect|unlink|disable|shutdown|deactivat\w*|invalidate|close|ban|revoke|terminate|suspend|abort|compromise)\b'),
    ('restore / restart / failover / migrate / copy / clone / import / export / transfer env or data', r'\b(restore|restart|failover|migrat\w*|copy|clone|import|export|transfer|combine|replace|mutate|update-version|reroute|sync|apply|deploy\w*)\b'),
    ('create a server / cloud resource / subscription / account (costs or provisions)', r'(subscription|resourcegroups|linode|server|vps|instance|cluster|domain|account|provision|marketplace|billing|addon|tenant|org)'),
    ('create / send message, notification, email, text, invite, broadcast (leaves the system)', r'(message|notification|email|e-mail|sms|text|invit\w*|broadcast|share|webhook|typing|waitlist|call|mail|notify)'),
    ('money: payment, refund, invoice, credit, order, wallet, dispute, charge', r'(payment|refund|invoice|credit|order|wallet|dispute|charge|billing|price|carbon|balance|statement|purchase|payroll|tax)'),
    ('create / run a job, task, scan, audit, check (does work, may cost)', r'\b(jobs?|tasks?|scan\w*|audit\w*|check\w*|run|trigger\w*|execut\w*|analy\w*|test|robots?|verify|verification|recovery|session)\b'),
    ('accept / approve / confirm / initialize / manage / like (state change that is hard to see)', r'^post .*(accept|approve|confirm|initiali\w*|manage|like|invoke action|shipment|manifest|real-time|device|command|flush|erc20|challenge|preregistered)'),
    ('PUT/PATCH on opaque proxy / state-change endpoint', r'^(put|patch) .*(proxy|start|driver|status|confirm|resolve|finalize|update)'),
]
TIGHT = [
    ('read-by-POST: filter / search / query / list / get / fetch / lookup', r'^post .*(filter|search|query|list|\bget\b|fetch|retriev\w*|find|lookup|count|read|describe|calculat\w*|estimate|batch|view|download|evaluate|invoke action (get|list))'),
    ('ping / test / check / validate / preview / dry-run via POST', r'^post .*(ping|test|check|validat\w*|preview|dry|verify|diagnos\w*|probe|connectivity)'),
    ('pure transform / compute / render via POST (no stored change)', r'^post .*(convert|merge|resize|render|decrypt|rekey|enrich|transform|xmltojson|qr|ocr|replace ?string|rebalanc\w*|simulat\w*|ingest|remove_restrictions|compute|format|translate|encode|decode|dep-graph|error)'),
    ('reversible lifecycle step via POST: deactivate / unsubscribe / leave / undo / accept / approve / confirm / link / apply / claim / upgrade', r'^post .*(deactivat\w*|reactivat\w*|unsubscrib\w*|subscrib\w*|leave|undo|demote|promote|upgrade|accept|approve|confirm|link|apply|claim|finish|bypass|attach|extend|set|replace|metadata|copy|migrate|finali\w*|deploy|maintenance)'),
    ('toggle / mark / resolve / set status / typing / read-receipt (small reversible state)', r'(toggle|mark|resolve|status|typing|read|seen|ack\w*|pin|star|like|mute|archive|flag|label|tag|snooze|assign)'),
    ('start / enable / activate / run / trigger / execute (reversible op)', r'\b(start|resume|enable|activate|run|trigger|execute|launch|begin|retry|rerun|refresh|reload|process)\b'),
    ('PUT/PATCH update or set where truth is w (model or cli says x)', r'^(put|patch) '),
    ('GET raised to w (read judged as changing)', r'^get '),
    ('DELETE judged x, truth w (soft / reversible delete)', r'^delete '),
    ('create / add / upload / register / schedule of ordinary resource (POST)', r'^post .*(create|add|new|upload|register|schedule|submit|insert|post|generate|issue|token|login|auth\w*|request)'),
]

def text(r): return ' '.join([r['method'], r['path'], re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', r['operationId']), r['summary']]).lower()

def pat(r):
    t = text(r)
    for name, rx in (LOOSE if r['kind'] == 'too_loose' else TIGHT):
        if re.search(rx, t): return name
    return 'other (uncategorised)'

def example(r): return f"`{r['set']} {r['id']}` {r['vendor']} {r['method']} {r['path'][:70]} | {r['summary'][:50] or '(no summary)'} | truth {r['truth']}, model {r['model_letter']}, mech {r['mech_letter']}"

def pick(rows, n=3):
    """Up to n rows, spread over different sets where possible, no repeats."""
    rows = sorted(rows, key=lambda r: (r['set'], r['id'])); out = []; used = set()
    for r in rows:   # first row of each distinct set
        if r['set'] not in used and len(out) < n: out.append(r); used.add(r['set'])
    for r in rows:
        if len(out) >= n: break
        if r not in out: out.append(r)
    return out

def write(out, model):
    M = rcsv(os.path.join(out, 'mistakes.csv')); J = rcsv(os.path.join(out, 'jev_overruled.csv')); raw = json.load(open(os.path.join(out, 'mistakes-raw.json')))['counts']
    L = []; w = L.append
    w('# Round 12 step 2: mistake list (0.2.0 fp32 and Jev)\n')
    w(f'Model judged: `{model}` (published 0.2.0, fp32 ONNX, T 0.844, batch 1). No training, no Haiku call. Script: `m1/r12-mine.py` (+ `m1/r12-summary.py`). Files: `mistakes.csv`, `jev_overruled.csv`, `mistakes-raw.json`.')
    w('Order r < w < x. too_loose = answer below truth (r or w where truth is higher); too_tight = answer above truth. Rules: **argmax** = raw model letter; **a_none** = mode a, no abstain (the exam-3/4 config); **cli** = rwxmap real-product letter (CLI secondPass, 0.2.0 fp32), exam #3/#4 only, read from the rwxmap checkout and not copied.')
    w('**NOTE: exam #4 rule-level mistakes (argmax / a_none) will be replaced by rwxmap\'s list when it arrives; the `cli` rows are already rwxmap\'s per-row results (rwxmap bb05e55, `data/exam4-2026-11-04/score/rows-a-fp32-base.csv`) and are the primary exam #4 list.** Exam #3 `cli` rows come from rwxmap\'s exam-3 run (`rows-a-fp32.csv`, product of that date, so more undecided/tight than today\'s product).\n')
    w('## 1. Counts per set and rule\n')
    w('| set | rule | rows | right | too loose | too tight | wrong |'); w('|---|---|---|---|---|---|---|')
    tot = collections.Counter()
    for s in SETS:
        for rule in ('argmax', 'a_none', 'cli'):
            c = raw[s]['rules'].get(rule)
            if not c: continue
            w(f"| {NAMES[s]} | {rule} | {c['n']} | {c['right']} | {c.get('too_loose', 0)} | {c.get('too_tight', 0)} | {c.get('too_loose', 0) + c.get('too_tight', 0)} |")
            if rule != 'cli': tot[(rule, 'n')] += c['n']; tot[(rule, 'l')] += c.get('too_loose', 0); tot[(rule, 't')] += c.get('too_tight', 0)
    for rule in ('argmax', 'a_none'):
        w(f"| **all sets** | {rule} | {tot[(rule, 'n')]} | {tot[(rule, 'n')] - tot[(rule, 'l')] - tot[(rule, 't')]} | {tot[(rule, 'l')]} | {tot[(rule, 't')]} | {tot[(rule, 'l')] + tot[(rule, 't')]} |")
    ex4 = raw['exam4']['rules']['cli']
    w(f"\nExam #4 under **cli** (verified against rwxmap's rows-a-fp32-base.csv): right {ex4['right']} / too loose {ex4.get('too_loose', 0)} / too tight {ex4.get('too_tight', 0)} (expected 1391 / 16 / 98).")
    cl = collections.Counter((r['kind'], r['decision_path']) for r in M if r['set'] == 'exam4' and r['rule'] == 'cli')
    w('\nExam #4 cli mistakes by decision path (path derived by comparing with rows-mech.csv; `undecided-x` = a sent row whose review stayed tight, i.e. the model was not sure enough to lower; `model-raise/model-lower` = the model changed the letter; `settled-mech` = never sent to the model):\n')
    w('| kind | decision path | rows |'); w('|---|---|---|')
    for (k, p), n in sorted(cl.items()): w(f'| {k} | {p} | {n} |')
    w('\nMeaning: the undecided-x rows are a different fix (model needs to be confident enough to lower) from rows where the model was confidently wrong (model-raise/model-lower) or where a floor/list/rule decided before the model.\n')
    w('Note: the exam #3 a_none/argmax columns do not equal rwxmap\'s exam-3 `cli` numbers (the CLI also applies floors/lists and ran an earlier product); kept as separate rules on purpose.\n')

    # overlap
    w('## 2. Overlap between sets\n')
    key = lambda r: (r['vendor'], r['method'], r['path'], r['operationId'])
    ops = collections.defaultdict(set)
    for s in SETS:
        pass
    allops = {}
    import gzip
    # operations present in more than one set (from the mistakes' own op keys only, plus counts of shared wrong ops)
    wrong = collections.defaultdict(set)
    for r in M:
        if r['rule'] in ('argmax', 'a_none'): wrong[key(r)].add(r['set'])
    shared = {k: v for k, v in wrong.items() if len(v) > 1}
    w(f"Distinct wrong operations (argmax or a_none, any kind, by vendor+method+path+operationId): {len(wrong)}; wrong in more than one set: {len(shared)}.")
    for k, v in list(shared.items())[:10]: w(f"- {sorted(v)}: {k[1]} {k[2][:70]} ({k[0]})")
    w('\nPer-set overlap of the two rules (rows wrong under both / only argmax / only a_none / only cli):\n')
    w('| set | wrong both | only argmax | only a_none | cli wrong (all) | cli wrong and also argmax/a_none wrong |'); w('|---|---|---|---|---|---|')
    for s in SETS:
        by = collections.defaultdict(set)
        for r in M:
            if r['set'] == s: by[r['rule']].add(r['id'])
        a, b, c = by['argmax'], by['a_none'], by['cli']
        w(f"| {s} | {len(a & b)} | {len(a - b)} | {len(b - a)} | {len(c) if c else '-'} | {len(c & (a | b)) if c else '-'} |")
    # between-set same-vendor families
    w('\nThe same pattern shows across sets (counts below are over the union of argmax and a_none wrong rows, unique per set+id+kind).\n')

    # patterns
    U = {}
    for r in M:
        if r['rule'] == 'cli' and r['set'] == 'exam3': continue
        k = (r['set'], r['id'], r['kind'])
        U.setdefault(k, []).append(r)
    for kind, title in (('too_loose', 'Too-loose patterns (model/answer lower than truth)'), ('too_tight', 'Too-tight patterns (model/answer higher than truth)')):
        w(f'## 3{"a" if kind == "too_loose" else "b"}. {title}\n')
        g = collections.defaultdict(list)
        for k, rs in U.items():
            if k[2] != kind: continue
            r = dict(rs[0]); r['kind'] = kind; r['rulesw'] = ','.join(sorted({x['rule'] for x in rs})); g[pat(r)].append(r)
        order = sorted(g.items(), key=lambda kv: -len(kv[1]))
        w(f'Unique rows: {sum(len(v) for v in g.values())}. Each pattern: first-match-wins keyword grouping over method, path, operationId, summary (patterns are lexical, so some rows could fit several).\n')
        for name, rows in order:
            by = collections.Counter(r['set'] for r in rows)
            w(f"### {name}: {len(rows)} rows")
            w('sets: ' + ', '.join(f'{s} {by[s]}' for s in SETS if by[s]))
            tr = collections.Counter(f"truth {r['truth']} <- {r['model_letter']}" for r in rows); w('shape: ' + ', '.join(f'{k} x{v}' for k, v in tr.most_common(3)))
            for r in pick(rows): w('- ' + example(r))
            w('')

    # Jev
    w('## 4. Jev overruled by human truth\n')
    w('Jev letter source: exam #3/#4 = rwxmap `rows-c-jev.csv` (real Jev run, mechanical + Jev only); gates = the round-6 recipe label computed from the stored Jev p (what training would have got); r9-hand = `key.csv current_label`; fresh exam = none (Jev was never run on it). '
      '"In training" = the exact operation (vendor+method+path+operationId) is in `data/train/{train,val}.jsonl` (r8/r9 data) or `data/round11/{train,val}.jsonl`; "wrong label" = a training row of that operation carries a label different from the human truth.\n')
    def tl(r):
        out = {'r8': [], 'r11': []}
        for h in r['train_labels'].split(';'):
            if not h: continue
            f, l = h.split(':'); out['r11' if f.startswith('round11') else 'r8'].append(l.split('(')[0] != r['truth'])
        return out
    w('| set | rows with Jev letter | Jev != truth | too loose | too tight | in r8 train/val data | ...with wrong label | in round-11 train/val data | ...with wrong label |'); w('|---|---|---|---|---|---|---|---|---|')
    for s in SETS:
        c = raw[s]
        if 'jev_n' not in c: w(f'| {NAMES[s]} | none | - | - | - | - | - | - | - |'); continue
        js = [r for r in J if r['set'] == s]; t = [tl(r) for r in js]
        n8 = sum(bool(x['r8']) for x in t); w8 = sum(any(x['r8']) for x in t); n11 = sum(bool(x['r11']) for x in t); w11 = sum(any(x['r11']) for x in t)
        w(f"| {NAMES[s]} | {c['jev_n']} | {c['jev_overruled']} | {sum(r['kind'] == 'too_loose' for r in js)} | {sum(r['kind'] == 'too_tight' for r in js)} | {n8} | {w8} | {n11} | {w11} |")
    jt = [r for r in J if r['in_training_with_wrong_label'] == 'True']
    w(f"\nTotal Jev-overruled rows: {len(J)}; in training (r8 or r11 data) with a wrong label: {len(jt)}.")
    bykind = collections.Counter((r['set'], r['kind']) for r in jt)
    w('In-training-wrong by set and kind: ' + ', '.join(f'{s}/{k} {n}' for (s, k), n in sorted(bykind.items())) + '.')
    w('\nExamples of overruled Jev rows that are in training with the wrong label:\n')
    for r in pick(jt, 6): w(f"- `{r['set']} {r['id']}` {r['vendor']} {r['method']} {r['path'][:60]} | {r['summary'][:40]} | truth {r['truth']}, Jev {r['jev_letter']} | train: {r['train_labels'][:90]}")
    w('\nFindings on training overlap: (1) **gate-3 and gate-4 operations are in the r8 and r11 training data** (checked by exact vendor+method+path+operationId; 51 of gate-3 and 45 of gate-4 overruled rows, and more generally their ops, are present), with the Jev-recipe label, so those two gates are not clean held-out sets for the models trained on that data; gate-1/gate-2 are not in training. (2) `data/round11/train.jsonl` contains all 1377 exam #3 rows (ids ex3-*) and all 949 fresh-exam rows (fx-*) with human labels, so exam #3 and the fresh exam are not held-out for the r11 model (they are for 0.2.0); r11 also carries the human label for 28 r9-hand train rows, but the r9-hand rows in val (8) and every gate-3/gate-4 row stay with the Jev-recipe label in round11 too. (3) For the exams the Jev letter is the real Jev product answer (rows-c-jev.csv), which is not necessarily what the recipe put into training; where the training label already equals the truth it is not counted as wrong.')
    open(os.path.join(out, 'summary.md'), 'w').write('\n'.join(L) + '\n')
    return 'summary.md'

if __name__ == '__main__':
    import sys
    write(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'data', 'r12'), 'rwxlite-0.2.0+8503b655')
