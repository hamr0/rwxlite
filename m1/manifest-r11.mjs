// Round 11: manifest + Node parity for data/m1-r11 (does not touch data/m1 or data/m1-r10).
//   node m1/manifest-r11.mjs write <T> [version]  -> data/m1-r11/manifest.json (int8-pc) and manifest-exact.json (fp32), version from package.json
//   node m1/manifest-r11.mjs parity               -> Node loadAnswerer (manifest temperature) vs Python ORT batch 1 on the 949 burned fresh rows (parity-rows.jsonl, T from the manifest)
//   node m1/manifest-r11.mjs batch                -> answerMany with mixed batches vs per-row answer(), both models, every row (exact equality)
// Parity rows are the burned fresh-exam rows, parity only, not a result (r11 is trained on them).
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { modelString, loadAnswerer } from '../src/answerer.js';

const dir = new URL('../data/m1-r11/', import.meta.url);
const sha = (n) => createHash('sha256').update(readFileSync(new URL(n, dir))).digest('hex');
const cmd = process.argv[2];
const readRows = () => readFileSync(new URL('parity-rows.jsonl', dir), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const MODELS = [['int8-pc', 'manifest.json'], ['fp32', 'manifest-exact.json']];
if (cmd === 'write') {
  const T = Number(process.argv[3]);
  const version = process.argv[4] ?? JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).version;
  for (const [modelFile, out] of [['model-int8-pc.onnx', 'manifest.json'], ['model-fp32.onnx', 'manifest-exact.json']]) {
    const files = { [modelFile]: sha(modelFile), 'vocab.txt': sha('vocab.txt') };
    const m = { version, modelFile, model: modelString(version, files[modelFile]), temperature: T, files };
    writeFileSync(new URL(out, dir), JSON.stringify(m, null, 2) + '\n');
    console.log(out, JSON.stringify(m));
  }
} else if (cmd === 'parity') {
  const rows = readRows(); const res = {};
  for (const [tag, mf] of MODELS) {
    const a = await loadAnswerer({ dir: dir.pathname, threads: 1, manifestFile: mf });
    let maxd = 0, argmaxDiff = 0, flips = 0;
    for (const r of rows) {
      const out = await a.answer({ state: r.state, lean: r.lean, questions: { isX: 1, changes: 1 } });
      const x = out.answers.isX.noul, c = out.answers.changes.noul; const P = [1 - c, c - x, x];
      const ref = r.p[tag];
      for (let k = 0; k < 3; k++) maxd = Math.max(maxd, Math.abs(P[k] - ref[k]));
      if (P.indexOf(Math.max(...P)) !== ref.indexOf(Math.max(...ref))) argmaxDiff++;
      if ((Math.max(...P) >= 0.97) !== (Math.max(...ref) >= 0.97)) flips++;
    }
    res[tag] = { model: a.model, temperature: a.temperature, n: rows.length, max_abs_p_diff: maxd, argmax_diff: argmaxDiff, side_097_flips: flips };
    console.log(tag, JSON.stringify(res[tag]));
  }
  writeFileSync(new URL('node-parity.json', dir), JSON.stringify(res, null, 1) + '\n');
} else if (cmd === 'batch') {
  const rows = readRows(); const res = {};
  let seed = 12345; const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32;
  const qsets = [{ isX: 1, changes: 1 }, { isX: 1 }, { changes: 1 }];
  const reqs = rows.map((r, i) => ({ state: r.state, lean: r.lean, questions: qsets[i % 3] }));
  for (const [tag, mf] of MODELS) {
    const a = await loadAnswerer({ dir: dir.pathname, threads: 1, manifestFile: mf });
    const single = []; for (const q of reqs) single.push(await a.answer(q));
    // shuffled order, random batch sizes 1..64, so every row meets different neighbours than in the per-row run
    const order = reqs.map((_, i) => i).sort(() => rnd() - 0.5);
    let diffs = 0, batches = 0, maxSize = 0;
    for (let i = 0; i < order.length;) {
      const n = 1 + Math.floor(rnd() * 64); const idx = order.slice(i, i + n); i += n; batches++; maxSize = Math.max(maxSize, idx.length);
      const out = await a.answerMany(idx.map((j) => reqs[j]));
      idx.forEach((j, k) => { if (JSON.stringify(out[k]) !== JSON.stringify(single[j])) diffs++; });
    }
    // one more pass: one big batch of all rows
    const big = await a.answerMany(reqs); let bigDiffs = 0; big.forEach((o, j) => { if (JSON.stringify(o) !== JSON.stringify(single[j])) bigDiffs++; });
    res[tag] = { model: a.model, rows: reqs.length, mixed_batches: batches, max_batch: maxSize, mismatches_mixed: diffs, mismatches_one_big_batch: bigDiffs };
    console.log(tag, JSON.stringify(res[tag]));
  }
  writeFileSync(new URL('batch-parity.json', dir), JSON.stringify(res, null, 1) + '\n');
} else { console.error('usage: write <T> [version] | parity | batch'); process.exit(2); }
