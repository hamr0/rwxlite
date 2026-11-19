// Round 15 labelling, opinion 3 (rwxmap mechanical) + the model input text (shared by opinion 1 and 2).
// Uses rwxmap's own classifyOperations (src/exporter.js) from a read-only extract of rwxmap commit 1c25be1 (0.11.1; R13 pinned, LOWER_MIN_P 0.90):
//   git -C /home/hamr/PycharmProjects/rwxmap archive 1c25be1 src package.json | tar -x -C TREE
// Mechanical reads only method, path, operationId, summary (rwxmap types.js), so per-operation input is exact; ops built as m1/r14-compare.mjs builds them.
// Text = rwxlite src/text.js formatText(state, lean, 1) with the lean (class, rule) AS IS: the exact string R13 reads inside rwxmap, and what the bge teacher is fed.
//   node r15/label_mech.mjs --tree TREE --ops ops.jsonl --out mech.jsonl
import * as fs from 'node:fs';
import { parseArgs } from 'node:util';
import { formatText } from '../src/text.js';
const { values: a } = parseArgs({ options: { tree: { type: 'string' }, ops: { type: 'string' }, out: { type: 'string' } } });
const { classifyOperations } = await import(`${a.tree}/src/exporter.js`);
const rows = fs.readFileSync(a.ops, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const ops = rows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '') r[k] = o[k]; return r; });
const mech = classifyOperations(ops);
const out = fs.createWriteStream(a.out, { flags: 'wx' });
rows.forEach((o, i) => {
  const v = mech[i], lean = { class: v.class, rule: v.rule };
  out.write(JSON.stringify({ op_id: o.op_id, mech_letter: v.class, mech_rule: v.rule, mech_step: v.step, mech_review: v.review, text: formatText(ops[i], lean, 1) }) + '\n');
});
out.end(() => console.log('rows', rows.length));
