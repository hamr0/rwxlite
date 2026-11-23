// Exam #8: rwxmap's REAL secondPass (src/secondpass.js of rwxmap ecee4f1, extracted by git archive) on our prediction CSV. Reads no truth.
//   node r16/exam8-secondpass.mjs --tree DIR --ops ops.csv --lean lean.csv --pred predictions.csv --model STR --out letters.csv [--confidence 85]
// Mechanical verdicts come from the real classifyOperations on ops.csv rows; they must equal lean.csv (id,lean_letter,lean_rule) or the script stops.
// Output: id,letter (exclusive create). Mode a when no --confidence (LOWER_MIN_P in the tree = 0.90), mode b when given.
import * as fs from 'node:fs';
import { parseArgs } from 'node:util';
const { values: a } = parseArgs({ options: { tree: { type: 'string' }, ops: { type: 'string' }, lean: { type: 'string' }, pred: { type: 'string' }, model: { type: 'string' }, out: { type: 'string' }, confidence: { type: 'string' } } });
const csv = (t) => { const rows = []; let r = [], f = '', q = false; for (let i = 0; i < t.length; i++) { const c = t[i];
  if (q) { if (c === '"') { if (t[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
  else if (c === '"') q = true; else if (c === ',') { r.push(f); f = ''; } else if (c === '\n') { r.push(f); rows.push(r); r = []; f = ''; } else if (c !== '\r') f += c; }
  if (f !== '' || r.length) { r.push(f); rows.push(r); } return rows.filter((x) => !(x.length === 1 && x[0] === '')); };
const tab = (f) => { const [h, ...b] = csv(fs.readFileSync(f, 'utf8')); return b.map((r) => Object.fromEntries(h.map((k, i) => [k, r[i]]))); };
const { classifyOperations } = await import(`${a.tree}/src/exporter.js`);
const { secondPass, LOWER_MIN_P } = await import(`${a.tree}/src/secondpass.js`);
if (LOWER_MIN_P !== 0.90) throw new Error('LOWER_MIN_P != 0.90');
const rows = tab(a.ops), lean = tab(a.lean), pred = tab(a.pred);
if (rows.length !== lean.length || rows.length !== pred.length) throw new Error('row count mismatch');
rows.forEach((r, i) => { if (lean[i].id !== r.id || pred[i].id !== r.id) throw new Error('id order mismatch at ' + i); if (pred[i].model !== a.model) throw new Error('model mismatch'); });
const ops = rows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '') r[k] = o[k]; return r; });
const mech = classifyOperations(ops);
const diff = mech.filter((m, i) => m.class !== lean[i].lean_letter || m.rule !== lean[i].lean_rule).length;
console.error(`mech vs lean.csv: ${diff} differing rows`);
if (diff) throw new Error('classifyOperations differs from lean.csv');
const engine = async (items) => items.map((it) => { const p = pred[it.index]; return { pIsX: Number(p.p_is_x), pChanges: Number(p.p_changes), model: a.model }; });
const opt = { model: a.model }; if (a.confidence !== undefined) opt.confidence = Number(a.confidence);
const { verdicts, summary } = await secondPass(ops, mech, engine, opt);
console.error(JSON.stringify(summary));
fs.writeFileSync(a.out, 'id,letter\n' + rows.map((o, i) => `${o.id},${verdicts[i].class}`).join('\n') + '\n', { flag: 'wx' });
