// Round 10: manifest + Node parity for data/m1-r10 (does not touch data/m1).
//   node m1/manifest-r10.mjs write <T>             -> data/m1-r10/manifest.json (int8-pc) and manifest-exact.json (fp32)
//   node m1/manifest-r10.mjs parity <T>            -> Node answerer (loadAnswerer, T=0.844 baked in src) vs Python ORT on 400 val rows
// loadAnswerer has T=0.844 hard-coded (src/answerer.js TEMPERATURE); r10's refit T is carried in the manifest as `temperature`
// (ignored by loadAnswerer today) and applied by the exam code. Parity here compares at the SAME T (0.844) so it checks the
// graph, tokenizer and text path, not the calibration.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { modelString, loadAnswerer } from '../src/answerer.js';

const dir = new URL('../data/m1-r10/', import.meta.url);
const sha = (n) => createHash('sha256').update(readFileSync(new URL(n, dir))).digest('hex');
const cmd = process.argv[2];
const T = Number(process.argv[3]);
if (cmd === 'write') {
  const version = process.argv[4] ?? JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).version;
  for (const [modelFile, out] of [['model-int8-pc.onnx', 'manifest.json'], ['model-fp32.onnx', 'manifest-exact.json']]) {
    const files = { [modelFile]: sha(modelFile), 'vocab.txt': sha('vocab.txt') };
    const m = { version, modelFile, model: modelString(version, files[modelFile]), temperature: T, files };
    writeFileSync(new URL(out, dir), JSON.stringify(m, null, 2) + '\n');
    console.log(out, JSON.stringify(m));
  }
} else if (cmd === 'parity') {
  // rows from the practice val split, pre-tokenised text from Python: data/m1-r10/parity-rows.jsonl {state, lean, p:[r,w,x] at T=0.844 from Python ORT int8-pc b=1}
  const rows = readFileSync(new URL('parity-rows.jsonl', dir), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
  const res = {};
  for (const [tag, mf] of [['int8-pc', 'manifest.json'], ['fp32', 'manifest-exact.json']]) {
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
    res[tag] = { model: a.model, n: rows.length, max_abs_p_diff: maxd, argmax_diff: argmaxDiff, side_097_flips: flips };
    console.log(tag, JSON.stringify(res[tag]));
  }
  writeFileSync(new URL('node-parity.json', dir), JSON.stringify(res, null, 1) + '\n');
} else { console.error('usage: write <T> [version] | parity <T>'); process.exit(2); }
