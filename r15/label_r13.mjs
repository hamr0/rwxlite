// Round 15 labelling, opinion 2: R13 (shipped rwxlite 0.3.1, int8-pc, T 0.991463) through rwxmap's real second pass, mode a, LOWER_MIN_P 0.90.
// Every row gets R13's probabilities (batch 1 per row, as the shipped answerMany does) with its mechanical lean as is. The mode-a letter then comes from
// rwxmap's own secondPass() (rwxmap commit 1c25be1 extract), fed those answers: only rows mechanical marks loose/tight are sent in mode a, settled rows keep the
// mechanical letter. Probabilities for settled rows are stored too (information; they did not decide anything).
//   node r15/label_r13.mjs --tree TREE --ops ops.jsonl --mech mech.jsonl --model-dir data/m1-r13 --out DIR [--threads 2]
// DIR/r13-probs.jsonl (resumable, appended per 64 rows) then DIR/r13-modea.jsonl {op_id, r13_letter_modea, r13_rule, r13_review, r13_sent, p_r, p_w, p_x, p_is_x, p_changes}.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { parseArgs } from 'node:util';
import { loadAnswerer } from '../src/answerer.js';
const { values: a } = parseArgs({ options: { tree: { type: 'string' }, ops: { type: 'string' }, mech: { type: 'string' }, 'model-dir': { type: 'string' }, out: { type: 'string' }, threads: { type: 'string', default: '2' } } });
const { secondPass, LOWER_MIN_P } = await import(`${a.tree}/src/secondpass.js`);
const { classifyOperations } = await import(`${a.tree}/src/exporter.js`);
if (LOWER_MIN_P !== 0.90) throw new Error('LOWER_MIN_P is ' + LOWER_MIN_P);
const rd = (f) => fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const rows = rd(a.ops), mech = rd(a.mech);
if (rows.length !== mech.length || rows.some((r, i) => r.op_id !== mech[i].op_id)) throw new Error('ops and mech differ');
fs.mkdirSync(a.out, { recursive: true });
const pf = path.join(a.out, 'r13-probs.jsonl');
const ans = await loadAnswerer({ dir: a['model-dir'], threads: Number(a.threads) });
console.log('model', ans.model);
let have = 0;
if (fs.existsSync(pf)) { const t = fs.readFileSync(pf, 'utf8'); const lines = t.split('\n'); if (lines[lines.length - 1] !== '') lines.pop(); have = lines.length; fs.writeFileSync(pf, lines.length ? lines.join('\n') + '\n' : ''); }
const t0 = Date.now(), CH = 64;
for (let i = have; i < rows.length; i += CH) {
  const idx = []; for (let j = i; j < Math.min(i + CH, rows.length); j++) idx.push(j);
  const reqs = idx.map((j) => ({ state: { method: rows[j].method, path: rows[j].path, operationId: rows[j].operationId, summary: rows[j].summary, description: rows[j].description },
    questions: { isX: 1, changes: 1 }, lean: { class: mech[j].mech_letter, rule: mech[j].mech_rule } }));
  const got = await ans.answerMany(reqs);
  fs.appendFileSync(pf, idx.map((j, k) => { const g = got[k]; return JSON.stringify('error' in g ? { op_id: rows[j].op_id, error: g.error } : { op_id: rows[j].op_id, model: g.model, p_is_x: g.answers.isX.noul, p_changes: g.answers.changes.noul }); }).join('\n') + '\n');
  if ((i / CH) % 50 === 0) { const d = i + idx.length - have, el = (Date.now() - t0) / 1000; console.log(`rows ${i + idx.length}/${rows.length} ${(d / el).toFixed(1)} rows/s eta ${((rows.length - i - idx.length) / (d / el) / 60).toFixed(1)}m`); }
}
// decide: the real secondPass in mode a
const P = rd(pf); if (P.length !== rows.length || P.some((p, i) => p.op_id !== rows[i].op_id)) throw new Error('probs do not line up');
const ops = rows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '') r[k] = o[k]; return r; });
const verdicts = classifyOperations(ops);
verdicts.forEach((v, i) => { if (v.class !== mech[i].mech_letter || v.rule !== mech[i].mech_rule) throw new Error('mechanical differs at ' + i); });
const engine = async (items) => items.map((it) => { const p = P[it.index]; return p.error ? { error: p.error } : { pIsX: p.p_is_x, pChanges: p.p_changes, model: p.model }; });
const res = await secondPass(ops, verdicts, engine, { model: ans.model });
const outf = fs.createWriteStream(path.join(a.out, 'r13-modea.jsonl'), { flags: 'w' });
res.verdicts.forEach((v, i) => { const p = P[i], e = p.error !== undefined;
  outf.write(JSON.stringify({ op_id: rows[i].op_id, r13_letter_modea: v.class, r13_rule: v.rule, r13_review: v.review, r13_sent: verdicts[i].review === 'loose' || verdicts[i].review === 'tight',
    p_r: e ? null : 1 - p.p_changes, p_w: e ? null : p.p_changes - p.p_is_x, p_x: e ? null : p.p_is_x, p_is_x: e ? null : p.p_is_x, p_changes: e ? null : p.p_changes, error: e ? p.error : null }) + '\n'); });
outf.end(() => console.log('summary', JSON.stringify(res.summary), 'seconds', ((Date.now() - t0) / 1000).toFixed(0)));
