// Exam #3 parity (docs/wiki/exam-prereg-exam3.md): the p-<model>.jsonl files from train/exam3_predict.py against loadAnswerer on the same rows.
//   node m0/exam3-parity.mjs <work-dir>     (inputs.jsonl + p-*.jsonl in it; reads no truth)
// Per file: model string equal, every id present once, max |dp| over pIsX and pChanges. Exit 1 if any model differs or max |dp| > 1e-6.
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { loadAnswerer } from '../src/answerer.js';

const wd = process.argv[2]; if (!wd) { console.error('usage: node m0/exam3-parity.mjs <work-dir>'); process.exit(2); }
const jl = (f) => readFileSync(f, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const rows = jl(`${wd}/inputs.jsonl`);
const d = (n) => fileURLToPath(new URL(`../data/${n}/`, import.meta.url));
const MODELS = { 'r10-int8pc': [d('m1-r10'), 'manifest.json'], 'r10-fp32': [d('m1-r10'), 'manifest-exact.json'],
  'v020-int8pc': [d('m1'), 'manifest.json'], 'v020-fp32': [d('m1'), 'manifest-fp32.json'] };
let bad = false;
for (const [name, [dir, manifestFile]] of Object.entries(MODELS)) {
  const f = `${wd}/p-${name}.jsonl`; if (!existsSync(f)) continue;
  const a = await loadAnswerer({ dir, threads: 1, manifestFile });
  const py = new Map(jl(f).map((r) => [r.id, r]));
  let max = 0, modelOk = true;
  if (py.size !== rows.length) throw new Error(`${name}: ${py.size} ids for ${rows.length} rows`);
  for (const r of rows) {
    const p = py.get(r.id); if (!p) throw new Error(`${name}: missing id ${r.id}`);
    if (p.model !== a.model) modelOk = false;
    const out = await a.answer({ state: r, lean: { class: r.class, rule: r.rule }, questions: { isX: 1, changes: 1 } });
    max = Math.max(max, Math.abs(out.answers.isX.noul - p.pIsX), Math.abs(out.answers.changes.noul - p.pChanges));
  }
  const ok = modelOk && max <= 1e-6; if (!ok) bad = true;
  console.log(`${name}: model ${a.model} ${modelOk ? 'equal' : 'DIFFERS'}, n=${rows.length}, max|dp|=${max.toExponential(3)} ${ok ? 'OK' : 'FAIL'}`);
}
process.exit(bad ? 1 : 0);
