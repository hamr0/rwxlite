// Exam #5 predictions (docs/wiki/prereg-exam5.md). Runs the PUBLISHED engine (src/answerer.js loadAnswerer: formatText, tokenizer, ONNX fp32,
// calibrated with the manifest's temperature), batch 1, and writes the contract CSV for rwxmap. Reads no truth (it only reads ops.csv and lean.csv).
//   node m1/exam5-predict.mjs <ops.csv> <model-dir> <out.csv> --lean <lean.csv> [--manifest manifest-exact.json]
//                             [--expect-model rwxlite-x.y.z+sha8] [--threads N] [--sha-file <ops sha file>] [--lean-sha-file <lean sha file>]
// - ops.csv sha256 must equal the hash in <ops.csv>.sha256 (or --sha-file); header must be exactly id,provider,method,path,operationId,summary,description.
// - The model reads the mechanical letter as its first words. The lean (class, rule) per row is rwxmap's lean.csv, fed AS IS (no alias, no edit;
//   src/text.js still applies its own credential-set -> cant-undo-verb alias inside formatText). lean.csv: header exactly id,class,rule,marker; sha256 must equal
//   <lean.csv>.sha256 (or --lean-sha-file); ids and order must equal ops.csv. The marker is not read here.
// - The text is built by src/text.js formatText inside the engine from the ops.csv fields as they are (method, path, operationId, summary, description).
// - Output CSV: header id,model,p_is_x,p_changes ; LF ; one row per op, same order as ops.csv; p written with Number.prototype.toString (shortest round trip).
//   p_is_x = p(x), p_changes = p(w) + p(x), both from the engine. Every p must be finite, in [0,1], and p_changes >= p_is_x, or the script stops.
// - Also writes <out>.lean.csv (id,class,rule: the lean the model was given). Neither file is overwritten (exclusive create).
// - Prints the sha256 of ops.csv, lean.csv, the CSV, the lean file.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { loadAnswerer } from '../src/answerer.js';

const HEADER = ['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'];
const die = (m) => { console.error('exam5-predict: ' + m); process.exit(1); };
const args = process.argv.slice(2); const pos = []; const opt = {};
for (let i = 0; i < args.length; i++) {
  if (args[i].startsWith('--')) { opt[args[i].slice(2)] = args[++i]; } else pos.push(args[i]);
}
const [opsPath, modelDir, outPath] = pos;
if (!opsPath || !modelDir || !outPath || !opt.lean) die('usage: <ops.csv> <model-dir> <out.csv> --lean <lean.csv> [--manifest f] [--expect-model s] [--threads n] [--sha-file f] [--lean-sha-file f]');
const sha = (b) => createHash('sha256').update(b).digest('hex');

const opsBytes = readFileSync(opsPath);
const opsSha = sha(opsBytes);
const shaFile = opt['sha-file'] ?? opsPath + '.sha256';
const want = readFileSync(shaFile, 'utf8').trim().split(/\s+/)[0];
if (!/^[0-9a-f]{64}$/.test(want)) die(`${shaFile} does not hold a sha256`);
if (want !== opsSha) die(`ops.csv sha256 ${opsSha} != ${want} (${shaFile})`);

function parseCsv(text) { // RFC 4180
  const rows = []; let row = []; let f = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; }
    else if (c !== '\r') f += c;
  }
  if (q) die('unterminated quote in ops.csv');
  if (f !== '' || row.length) { row.push(f); rows.push(row); }
  return rows.filter((r) => !(r.length === 1 && r[0] === ''));
}
const table = parseCsv(opsBytes.toString('utf8'));
if (table[0].join(',') !== HEADER.join(',')) die(`header must be exactly ${HEADER.join(',')}, got ${table[0].join(',')}`);
const ops = table.slice(1).map((r, n) => {
  if (r.length !== HEADER.length) die(`row ${n + 2} has ${r.length} fields`);
  return Object.fromEntries(HEADER.map((k, i) => [k, r[i]]));
});
if (!ops.length) die('no rows');
if (new Set(ops.map((o) => o.id)).size !== ops.length) die('duplicate id');

const leanBytes = readFileSync(opt.lean); const leanSha = sha(leanBytes);
const leanWant = readFileSync(opt['lean-sha-file'] ?? opt.lean + '.sha256', 'utf8').trim().split(/\s+/)[0];
if (!/^[0-9a-f]{64}$/.test(leanWant)) die('lean sha file does not hold a sha256');
if (leanWant !== leanSha) die(`lean.csv sha256 ${leanSha} != ${leanWant}`);
const leanTable = parseCsv(leanBytes.toString('utf8'));
if (leanTable[0].join(',') !== 'id,class,rule,marker') die(`lean.csv header must be exactly id,class,rule,marker, got ${leanTable[0].join(',')}`);
const leanRows = leanTable.slice(1);
if (leanRows.length !== ops.length) die(`lean.csv has ${leanRows.length} rows, ops.csv ${ops.length}`);
leanRows.forEach((r, i) => {
  if (r.length !== 4) die(`lean row ${i + 2} has ${r.length} fields`);
  if (r[0] !== ops[i].id) die(`lean row ${i + 2}: id ${r[0]} != ops id ${ops[i].id} (ids and order must match)`);
  if (!['r', 'w', 'x'].includes(r[1]) || !r[2]) die(`lean row ${i + 2}: bad class/rule`);
});

const threads = opt.threads === undefined ? undefined : Number(opt.threads);
const a = await loadAnswerer({ dir: path.resolve(modelDir), manifestFile: opt.manifest ?? 'manifest-exact.json', ...(threads === undefined ? {} : { threads }) });
if (opt['expect-model'] && a.model !== opt['expect-model']) die(`model ${a.model} != expected ${opt['expect-model']}`);

const lines = ['id,model,p_is_x,p_changes']; const lean = ['id,class,rule'];
for (const o of ops) {
  const state = { method: o.method, path: o.path, operationId: o.operationId, summary: o.summary, description: o.description };
  const v = { class: leanRows[lines.length - 1][1], rule: leanRows[lines.length - 1][2] };
  const out = await a.answer({ state, lean: { class: v.class, rule: v.rule }, questions: { isX: 1, changes: 1 } });
  const x = out.answers.isX.noul; const c = out.answers.changes.noul;
  for (const p of [x, c]) if (typeof p !== 'number' || !Number.isFinite(p) || p < 0 || p > 1) die(`${o.id}: p out of [0,1] or not finite: ${p}`);
  if (c < x) die(`${o.id}: p_changes ${c} < p_is_x ${x}`);
  if (out.model !== a.model) die(`${o.id}: model string changed`);
  if (/[",\r\n]/.test(o.id) || /[",\r\n]/.test(a.model)) die(`${o.id}: unsafe csv field`);
  lines.push(`${o.id},${a.model},${x.toString()},${c.toString()}`);
  lean.push(`${o.id},${v.class},${v.rule}`);
}
if (lines.length - 1 !== ops.length) die('row count mismatch');
const body = lines.join('\n') + '\n'; const leanBody = lean.join('\n') + '\n';
writeFileSync(outPath, body, { flag: 'wx' }); writeFileSync(outPath + '.lean.csv', leanBody, { flag: 'wx' });
console.log(`ops.csv    sha256 ${opsSha}  rows ${ops.length}`);
console.log(`lean.csv   sha256 ${leanSha}  rows ${leanRows.length}`);
console.log(`model      ${a.model}  T ${a.temperature}  textFormat ${a.textFormat}  manifest ${opt.manifest ?? 'manifest-exact.json'}`);
console.log(`${sha(Buffer.from(body))}  ${outPath}`);
console.log(`${sha(Buffer.from(leanBody))}  ${outPath}.lean.csv`);
