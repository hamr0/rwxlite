// Round 14 step 2: score p files through rwxmap's real second pass (mode a at several cuts, mode b at one confidence).
// Mode a: rwxmap's poc/replay-r12/replay.mjs with --lower-min-p, unchanged, exactly as poc/cutoff-r13/curve.mjs ran it.
// Mode b: the real src/secondpass.js with {confidence}, mechanical from classifyOperations as replay.mjs builds it.
// Both need the rwxmap tree as it was at the cut sweep (src with `export const LOWER_MIN_P = 0.97;`, i.e. the parent of
// rwxmap commit 5e6b9cb); extract it read-only with: git -C <rwxmap> archive 5e6b9cb^ src package.json poc/replay-r12/replay.mjs | tar -x -C DIR
// Usage (normally called by m1/r14-compare.py, which writes the p files):
//   node m1/r14-compare.mjs --tree DIR --ops ops.csv --truth val-truth.csv --pdir P_DIR --out report.json [--conf 85]
// P_DIR holds p-<name>.jsonl files ({id, model, pIsX, pChanges}); the report has one entry per file.
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { spawnSync } from 'node:child_process';
import { parseArgs } from 'node:util';
const { values: a } = parseArgs({ options: { tree: { type: 'string' }, ops: { type: 'string' }, truth: { type: 'string' }, pdir: { type: 'string' }, out: { type: 'string' }, conf: { type: 'string', default: '85' } } });
const RANK = { r: 0, w: 1, x: 2 }, CUTS = [0.97, 0.95, 0.93, 0.90, 0.85];
function parseCsv(text) {
  const rows = []; let row = [], f = '', i = 0, q = false;
  while (i < text.length) { const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i += 2; continue; } q = false; i++; continue; } f += c; i++; continue; }
    if (c === '"') { q = true; i++; continue; } if (c === ',') { row.push(f); f = ''; i++; continue; } if (c === '\r') { i++; continue; }
    if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; i++; continue; } f += c; i++; }
  if (f !== '' || row.length) { row.push(f); rows.push(row); }
  const h = rows[0]; return rows.slice(1).filter((x) => !(x.length === 1 && x[0] === '')).map((x) => Object.fromEntries(h.map((k, j) => [k, x[j]])));
}
const rd = (f) => parseCsv(fs.readFileSync(f, 'utf8'));
const tally = (pairs) => { const t = { right: 0, loose1: 0, loose2: 0, loose: 0, tight: 0, n: pairs.length }; for (const [l, tr] of pairs) { const d = RANK[l] - RANK[tr]; if (d === 0) t.right++; else if (d === -1) t.loose1++; else if (d < -1) t.loose2++; else t.tight++; } t.loose = t.loose1 + t.loose2; return t; };
const { classifyOperations } = await import(`${a.tree}/src/exporter.js`);
const { secondPass, readAnswer } = await import(`${a.tree}/src/secondpass.js`);
const opsRows = rd(a.ops), truth = new Map(rd(a.truth).map((r) => [r.id, r.label]));
const ops = opsRows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '') r[k] = o[k]; return r; });
const mech = classifyOperations(ops), tr = opsRows.map((o) => truth.get(o.id));
const out = { mech_alone: tally(mech.map((m, i) => [m.class, tr[i]])), models: {} };
for (const f of fs.readdirSync(a.pdir).filter((x) => /^p-.*\.jsonl$/.test(x)).sort()) {
  const name = f.slice(2, -6), pf = path.join(a.pdir, f);
  const pById = new Map(fs.readFileSync(pf, 'utf8').split('\n').filter(Boolean).map((l) => { const r = JSON.parse(l); return [r.id, r]; }));
  const model = [...new Set([...pById.values()].map((r) => r.model))][0];
  const engine = async (items) => items.map((it) => { const r = pById.get(opsRows[it.index].id); return { pIsX: r.pIsX, pChanges: r.pChanges, model: r.model }; });
  const m = { modeA: {}, modeB: null, realA097: null };
  for (const c of CUTS) {
    const rf = path.join(os.tmpdir(), `r14cmp-${process.pid}-${name}-${c}.csv`);
    const r = spawnSync('node', [`${a.tree}/poc/replay-r12/replay.mjs`, '--ops', a.ops, '--truth', a.truth, '--p', pf, '--out', rf, '--lower-min-p', String(c)], { encoding: 'utf8', cwd: os.tmpdir() });
    if (r.status !== 0) { console.error(r.stdout + r.stderr); process.exit(2); }
    const rows = rd(rf); fs.rmSync(rf);
    m.modeA[c] = { ...tally(rows.map((x) => [x.letter, x.truth])), lowered: rows.filter((x) => x.rule === 'rwxlite-lower').length, undecided: rows.filter((x) => x.rule === 'rwxlite-undecided').length };
    if (c === 0.97) m.rowsA097 = rows.map((x) => x.letter).join('');
  }
  const real = await secondPass(ops, mech, engine, { model });                          // the real module, LOWER_MIN_P as in this tree (0.97)
  m.realA097 = real.verdicts.map((v) => v.class).join('') === m.rowsA097 ? 'equals replay --lower-min-p 0.97 on every row' : 'DIFFERS';
  delete m.rowsA097;
  const b = await secondPass(ops, mech, engine, { model, confidence: Number(a.conf) });
  m.modeB = { confidence: Number(a.conf), ...tally(b.verdicts.map((v, i) => [v.class, tr[i]])), summary: b.summary };
  out.models[name] = m;
}
fs.writeFileSync(a.out, JSON.stringify(out, null, 1));
const row = (t) => `${String(t.right).padStart(5)} / ${String(t.loose).padStart(3)} / ${String(t.tight).padStart(4)}  (loose-1 ${t.loose1}, loose-2 ${t.loose2})`;
console.log('mechanical alone', row(out.mech_alone));
for (const [n, m] of Object.entries(out.models)) {
  console.log(`\n== ${n} ==  (right / too loose / too tight)   [real module at 0.97 ${m.realA097}]`);
  for (const c of CUTS) console.log(`mode a ${c.toFixed(2)}  ${row(m.modeA[c])}  lowered ${m.modeA[c].lowered} undecided ${m.modeA[c].undecided}`);
  console.log(`mode b ${m.modeB.confidence}    ${row(m.modeB)}  ${JSON.stringify(m.modeB.summary)}`);
}
