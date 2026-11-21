// Round 16 small runs: rwxmap's REAL secondPass (mode a, LOWER_MIN_P 0.90 in the tree of rwxmap 1c25be1) on dev rows, fed probabilities from r16/score_dev.py.
//   node r16/secondpass_real.mjs --tree data/r16/scratch/rwxmap-1c25be1 --ops dev-ops.jsonl --p p.jsonl --out letters.jsonl
// ops.jsonl: {op_id, method, path, operationId, summary, description}; p.jsonl: {op_id, p:[pr,pw,px]} (already at the run's T). Output {op_id, letter}. The engine hands back pIsX = px, pChanges = pw + px.
import * as fs from 'node:fs';
import { parseArgs } from 'node:util';
const { values: a } = parseArgs({ options: { tree: { type: 'string' }, ops: { type: 'string' }, p: { type: 'string' }, out: { type: 'string' } } });
const { classifyOperations } = await import(`${a.tree}/src/exporter.js`);
const { secondPass } = await import(`${a.tree}/src/secondpass.js`);
const rd = (f) => fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const rows = rd(a.ops), P = new Map(rd(a.p).map((r) => [r.op_id, r.p]));
const ops = rows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '') r[k] = o[k]; return r; });
const MODEL = 'rwxlite-0.4.0+e4317638', mech = classifyOperations(ops);
const engine = async (items) => items.map((it) => { const [, pw, px] = P.get(rows[it.index].op_id); return { pIsX: px, pChanges: pw + px, model: MODEL }; });
const { verdicts } = await secondPass(ops, mech, engine, { model: MODEL });
fs.writeFileSync(a.out, rows.map((o, i) => JSON.stringify({ op_id: o.op_id, letter: verdicts[i].class, mech: mech[i].class })).join('\n') + '\n', { flag: 'wx' });
