// Dump rwxmap mechanical verdicts (class, rule, review) per set. Read-only import of rwxmap src.
import * as fs from 'node:fs';
const REPO = '/home/hamr/PycharmProjects/rwxmap';
const { classifyOperations } = await import(`${REPO}/src/exporter.js`);
function parseCsv(text) {
  const rows = []; let row = [], f = '', i = 0, q = false;
  while (i < text.length) { const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i += 2; continue; } q = false; i++; continue; } f += c; i++; continue; }
    if (c === '"') { q = true; i++; continue; } if (c === ',') { row.push(f); f = ''; i++; continue; }
    if (c === '\r') { i++; continue; } if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; i++; continue; }
    f += c; i++; }
  if (f !== '' || row.length) { row.push(f); rows.push(row); } return rows; }
const csv = (file) => { const r = parseCsv(fs.readFileSync(file, 'utf8')); const h = r[0]; return r.slice(1).filter((x) => !(x.length === 1 && x[0] === '')).map((x) => Object.fromEntries(h.map((k, i) => [k, x[i]]))); };
const sets = JSON.parse(process.argv[2]); const out = {};
for (const [name, file] of Object.entries(sets)) {
  const rows = csv(file);
  const ops = rows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '') r[k] = o[k]; return r; });
  const m = classifyOperations(ops);
  out[name] = rows.map((o, i) => ({ id: o.id, provider: o.provider, method: o.method, path: o.path, operationId: o.operationId, cls: m[i].class, rule: m[i].rule, review: m[i].review, source: m[i].source }));
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
console.log(Object.entries(out).map(([k, v]) => `${k}:${v.length}`).join(' '));
