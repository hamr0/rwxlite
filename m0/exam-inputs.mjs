// One-time exam (pre-registered: docs/wiki/exam-prereg-r8soft.md). Builds the model inputs for the exam rows.
// Reads ONLY these columns of rwxmap's exam file: row_id, provider, method, path, operationId, summary, description.
// Every other column (truth_class, confidence, reason, ruled, ...) is dropped at parse time and never referenced.
// Needs a rwxmap checkout at ../rwxmap or $RWXMAP_DIR (not an npm dependency).
//   node m0/exam-inputs.mjs  -> data/exam-r8soft/inputs.jsonl
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
// rwxmap is deliberately not an npm dependency of rwxlite (npm ci must work on a clean clone); it is
// loaded from a checkout beside this repo, or from RWXMAP_DIR.
const { classifyRow, needsJev } = await import(pathToFileURL(path.join(RWXMAP, 'src', 'index.js')).href).catch((e) => {
  throw new Error(`rwxmap not found at ${RWXMAP} (clone hamr0/rwxmap beside this repo or set RWXMAP_DIR): ${e.message}`);
});
const FRESH = process.argv[2] === 'fresh'; // fresh exam 2026-11-03: ops.csv is blind (id column), output data/exam-fresh-r8soft/
const IDCOL = FRESH ? 'id' : 'row_id';
const KEEP = [IDCOL, 'provider', 'method', 'path', 'operationId', 'summary', 'description'];

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
const SRC = FRESH ? path.join(HERE, '..', 'data', 'exam-2026-11-03-fresh', 'ops.csv') : path.join(RWXMAP, 'data', 'exam-2026-09-22', 'labelled.csv');
const OUTDIR = path.join(HERE, '..', 'data', FRESH ? 'exam-fresh-r8soft' : 'exam-r8soft');
const rows = parseCsv(fs.readFileSync(SRC, 'utf8'));
const out = rows.map((r) => {
  const v = classifyRow({ method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description });
  return { id: r[IDCOL], provider: r.provider, method: String(r.method).toUpperCase(), path: r.path, operationId: r.operationId, summary: r.summary, description: r.description, class: v.class, rule: v.rule, jev_tier: needsJev(v) };
});
if (new Set(out.map((o) => o.id)).size !== out.length) throw new Error('duplicate row_id');
fs.mkdirSync(OUTDIR, { recursive: true });
fs.writeFileSync(path.join(OUTDIR, 'inputs.jsonl'), out.map((o) => JSON.stringify(o)).join('\n') + '\n');
console.log('rows', out.length);
