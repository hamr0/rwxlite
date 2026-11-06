// Exam #5 candidate R13: manifests + Node parity for data/m1-r13 (does not touch any other data dir). Pattern of m1/manifest-r11.mjs.
//   node m1/manifest-r13.mjs write <version>  -> data/m1-r13/manifest-exact.json (fp32, the one that counts) and manifest.json (int8-pc, information)
//       temperature 0.991463, textFormat 1 (written explicitly). <version> is required: it is part of the model string.
//   node m1/manifest-r13.mjs parity           -> Node loadAnswerer (manifest T, batch 1) vs Python ORT p on 598 val rows (parity-rows.jsonl):
//                                                 max |dp|, argmax differences, and Node formatText == stored text (trailing whitespace ignored: the stored text keeps a space after a 400-char cut)
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { modelString, loadAnswerer } from '../src/answerer.js';
import { formatText } from '../src/text.js';

const dir = new URL('../data/m1-r13/', import.meta.url);
const T = 0.991463;
const sha = (n) => createHash('sha256').update(readFileSync(new URL(n, dir))).digest('hex');
const cmd = process.argv[2];
const MODELS = [['fp32', 'manifest-exact.json'], ['int8-pc', 'manifest.json']];
if (cmd === 'write') {
  const version = process.argv[3];
  if (!/^\d+\.\d+\.\d+$/.test(version ?? '')) { console.error('usage: write <x.y.z>'); process.exit(2); }
  for (const [modelFile, out] of [['model-fp32.onnx', 'manifest-exact.json'], ['model-int8-pc.onnx', 'manifest.json']]) {
    const files = { [modelFile]: sha(modelFile), 'vocab.txt': sha('vocab.txt') };
    const m = { version, modelFile, model: modelString(version, files[modelFile]), temperature: T, textFormat: 1, files };
    writeFileSync(new URL(out, dir), JSON.stringify(m, null, 2) + '\n');
    console.log(out, JSON.stringify(m));
  }
} else if (cmd === 'parity') {
  const rows = readFileSync(new URL('parity-rows.jsonl', dir), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
  const textDiff = rows.filter((r) => formatText(r.state, r.lean, 1) !== r.text.trimEnd()).length;
  const res = { rows: rows.length, node_text_differs_from_stored: textDiff };
  for (const [tag, mf] of MODELS) {
    const a = await loadAnswerer({ dir: dir.pathname, manifestFile: mf });
    let maxd = 0, argmaxDiff = 0;
    for (const r of rows) {
      const out = await a.answer({ state: r.state, lean: r.lean, questions: { isX: 1, changes: 1 } });
      const x = out.answers.isX.noul, c = out.answers.changes.noul; const P = [1 - c, c - x, x];
      for (let k = 0; k < 3; k++) maxd = Math.max(maxd, Math.abs(P[k] - r.p[tag][k]));
      if (P.indexOf(Math.max(...P)) !== r.p[tag].indexOf(Math.max(...r.p[tag]))) argmaxDiff++;
    }
    res[tag] = { model: a.model, temperature: a.temperature, textFormat: a.textFormat, max_abs_p_diff: maxd, argmax_diff: argmaxDiff };
  }
  console.log(JSON.stringify(res)); writeFileSync(new URL('node-parity.json', dir), JSON.stringify(res, null, 1) + '\n');
} else { console.error('usage: write <x.y.z> | parity'); process.exit(2); }
