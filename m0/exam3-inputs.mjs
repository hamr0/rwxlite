// Exam #3 inputs (see docs/wiki/exam-prereg-exam3.md). Reads ONLY id, provider, method, path, operationId, summary, description
// from the ops file you pass; the truth file is never opened here. For each row: rwxmap's classifyRow / needsJev (lean) and
// the exact model text from the SHIPPED text path (src/text.js formatText: QUERY read as GET, credential-set aliased).
//   node m0/exam3-inputs.mjs <ops.csv> <out-dir>   -> <out-dir>/inputs.jsonl
// Needs a rwxmap checkout at ../rwxmap or $RWXMAP_DIR; its HEAD sha is written to <out-dir>/rwxmap-head.txt.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { formatText } from '../src/text.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const [opsPath, outDir] = process.argv.slice(2);
if (!opsPath || !outDir) { console.error('usage: node m0/exam3-inputs.mjs <ops.csv> <out-dir>'); process.exit(2); }
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
const { classifyRow, needsJev } = await import(pathToFileURL(path.join(RWXMAP, 'src', 'index.js')).href).catch((e) => {
  throw new Error(`rwxmap not found at ${RWXMAP} (clone hamr0/rwxmap beside this repo or set RWXMAP_DIR): ${e.message}`);
});
const KEEP = ['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'];

function parseCsv(text) { // RFC-4180, projects to KEEP while parsing; no other column is retained
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
const rows = parseCsv(fs.readFileSync(opsPath, 'utf8'));
const out = rows.map((r) => {
  const v = classifyRow({ method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description });
  const text = formatText({ method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description }, { class: v.class, rule: v.rule });
  return { id: r.id, provider: r.provider, method: String(r.method).toUpperCase(), path: r.path, operationId: r.operationId, summary: r.summary, description: r.description, class: v.class, rule: v.rule, jev_tier: needsJev(v), text };
});
if (new Set(out.map((o) => o.id)).size !== out.length) throw new Error('duplicate id');
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'inputs.jsonl'), out.map((o) => JSON.stringify(o)).join('\n') + '\n');
let head = 'unknown'; try { head = execFileSync('git', ['-C', RWXMAP, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(); } catch { /* not a git checkout */ }
fs.writeFileSync(path.join(outDir, 'rwxmap-head.txt'), head + '\n');
console.log('rows', out.length, 'rwxmap', head);
