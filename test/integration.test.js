// Runs the real int8 model in Node and compares to the Python (onnxruntime) probabilities.
// Skips, with the reason, when the model files or onnxruntime-node are not there (CI has neither).
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { loadAnswerer } from '../src/answerer.js';
import { fixtureRows } from './helpers.js';
import { readNpy } from './npy.js';

const dir = new URL('../data/m1/', import.meta.url);
// shipped model file -> variant name used in the Python probability files (m1/variants.py eval)
const VARIANT = /** @type {Record<string, string>} */ ({ 'model-fp32.onnx': 'fp32', 'model-fp16.onnx': 'fp16', 'model-int8.onnx': 'int8-default', 'model-int8-pc.onnx': 'int8-pc', 'model-int8-mm.onnx': 'int8-mm', 'model-int8-pc-mm.onnx': 'int8-pc-mm' });

test('the shipped model in Node matches the Python probabilities (batch 1) within 1e-4', async (t) => {
  if (!existsSync(new URL('manifest.json', dir))) { t.skip('data/m1/manifest.json not present (model files are not in git; run m1/export_onnx.py, then npm run manifest)'); return; }
  const modelFile = JSON.parse(readFileSync(new URL('manifest.json', dir), 'utf8')).modelFile;
  const probs = `probs-${VARIANT[modelFile]}-b1-exam-2026-11-03-fresh.npy`;
  const missing = [modelFile, 'vocab.txt', probs].filter((f) => !existsSync(new URL(f, dir)));
  if (missing.length) { t.skip(`not present in data/m1: ${missing.join(', ')} (run m1/variants.py eval)`); return; }
  /** @type {import('../src/answerer.js').Answerer} */
  let a;
  try { a = await loadAnswerer({ dir: new URL(dir).pathname }); } catch (e) {
    if (/onnxruntime-node/.test(String(/** @type {Error} */ (e).message))) { t.skip('onnxruntime-node is not installed'); return; }
    throw e;
  }
  const rows = fixtureRows().filter((r) => r.state).slice(0, 949);
  const py = readNpy(new URL(probs, dir));
  assert.equal(py.rows, 949);
  const pick = Array.from({ length: 24 }, (_, i) => Math.floor((i * 949) / 24));
  // one request per call: dynamic quantisation scales depend on batch composition, and the Python side was run at batch 1
  for (const i of pick) {
    const o = await a.answer({ state: /** @type {any} */ (rows[i].state), questions: { isX: 1, changes: 1 }, lean: /** @type {any} */ (rows[i].lean) });
    const pw = py.data[i * 3 + 1]; const px = py.data[i * 3 + 2];
    const ans = /** @type {any} */ (o).answers;
    assert.ok(Math.abs(ans.isX.noul - px) < 1e-4, `isX row ${i}`);
    assert.ok(Math.abs(ans.changes.noul - (pw + px)) < 1e-4, `changes row ${i}`);
  }
});
