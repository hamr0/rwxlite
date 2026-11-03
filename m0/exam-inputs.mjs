// One-time exam (pre-registered: docs/wiki/exam-prereg-r8soft.md). Builds the model inputs for the exam rows.
// Reads ONLY these columns of rwxmap's exam file: row_id, provider, method, path, operationId, summary, description.
// Every other column (truth_class, confidence, reason, ruled, ...) is dropped at parse time and never referenced.
//   node m0/exam-inputs.mjs  -> data/exam-r8soft/inputs.jsonl
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { classifyRow, needsJev } from 'rwxmap';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
const KEEP = ['row_id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'];

function parseCsv(text) { // same RFC-4180 reader as m0/mechanical.mjs, but projects to KEEP while parsing
  const rows = []; let row = []; let f = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; }
    else if (c !== '\r') f += c;
  }
  if (f !== '' || row.length) { row.push(f); rows.push(row); }
  const h = rows[0]; const idx = KEEP.map((k) => { const j = h.indexOf(k); if (j < 0) throw new Error('missing column ' + k); return j; });
  return rows.slice(1).filter((r) => !(r.length === 1 && r[0] === '')).map((r) => { const o = {}; KEEP.forEach((k, n) => { o[k] = r[idx[n]] ?? ''; }); return o; });
}
const rows = parseCsv(fs.readFileSync(path.join(RWXMAP, 'data', 'exam-2026-09-22', 'labelled.csv'), 'utf8'));
const out = rows.map((r) => {
  const v = classifyRow({ method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description });
  return { id: r.row_id, provider: r.provider, method: String(r.method).toUpperCase(), path: r.path, operationId: r.operationId, summary: r.summary, description: r.description, class: v.class, rule: v.rule, jev_tier: needsJev(v) };
});
if (new Set(out.map((o) => o.id)).size !== out.length) throw new Error('duplicate row_id');
fs.mkdirSync(path.join(HERE, '..', 'data', 'exam-r8soft'), { recursive: true });
fs.writeFileSync(path.join(HERE, '..', 'data', 'exam-r8soft', 'inputs.jsonl'), out.map((o) => JSON.stringify(o)).join('\n') + '\n');
console.log('rows', out.length);
