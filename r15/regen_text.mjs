// Round 15 (prereg section 7.2, PROPOSED): regenerate the model input text of training/val rows with the mechanical lean of ONE frozen rwxmap ref, so training lean = exam #7 lean.
//   git -C /home/hamr/PycharmProjects/rwxmap archive <REF> src package.json | tar -x -C TREE
//   node r15/regen_text.mjs --tree TREE --in rows.jsonl --out out.jsonl
// rows.jsonl lines {id, method, path, operationId, summary, description}; out lines {id, class, rule, review, text}. Same op construction and formatText(state, lean, 1) as r15/label_mech.mjs
// (which produced data/r15/labels/texts-r15.jsonl at rwxmap 1c25be1: running this at 1c25be1 on the r15 rows must reproduce those texts byte for byte; r15_assemble.py asserts it).
import * as fs from 'node:fs';
import { parseArgs } from 'node:util';
import { formatText } from '../src/text.js';
const { values: a } = parseArgs({ options: { tree: { type: 'string' }, in: { type: 'string' }, out: { type: 'string' } } });
const { classifyOperations } = await import(`${a.tree}/src/exporter.js`);
const rows = fs.readFileSync(a.in, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const ops = rows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '' && o[k] != null) r[k] = o[k]; return r; });
const mech = classifyOperations(ops);
const out = fs.createWriteStream(a.out, { flags: 'wx' });
rows.forEach((o, i) => { const v = mech[i]; out.write(JSON.stringify({ id: o.id, class: v.class, rule: v.rule, review: v.review, text: formatText(ops[i], { class: v.class, rule: v.rule }, 1) }) + '\n'); });
out.end(() => console.log('rows', rows.length));
