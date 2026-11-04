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

// Answers must not depend on batch composition, for both shipped models (int8 per-channel: dynamic activation scale over the padded batch).
for (const [name, manifestFile] of [['int8-pc', 'manifest.json'], ['fp32', 'manifest-exact.json']]) {
  test(`${name}: answerMany of a mixed-length set equals per-row answer() exactly, in any order and with any neighbours`, async (t) => {
    const rel = new URL('release/', dir);
    const d = existsSync(new URL(manifestFile, rel)) ? rel : dir;
    const mf = d === rel ? manifestFile : 'manifest.json';
    const modelFile = existsSync(new URL(mf, d)) ? JSON.parse(readFileSync(new URL(mf, d), 'utf8')).modelFile : '';
    const want = name === 'fp32' ? 'model-fp32.onnx' : 'model-int8-pc.onnx';
    if (modelFile !== want || !existsSync(new URL(want, d)) || !existsSync(new URL('vocab.txt', d))) { t.skip(`${want} + manifest not present under data/m1 (or data/m1/release)`); return; }
    /** @type {import('../src/answerer.js').Answerer} */
    let a;
    try { a = await loadAnswerer({ dir: new URL(d).pathname, manifestFile: mf }); } catch (e) {
      if (/onnxruntime-node/.test(String(/** @type {Error} */ (e).message))) { t.skip('onnxruntime-node is not installed'); return; }
      throw e;
    }
    const all = fixtureRows().filter((r) => r.state).slice(0, 949);
    // longest and shortest texts first so the batch padding differs a lot between neighbours
    const idx = all.map((_, i) => i).sort((x, y) => all[x].text.length - all[y].text.length);
    const pick = [...idx.slice(0, 6), ...idx.slice(-6), ...idx.slice(400, 406)];
    const reqs = pick.map((i) => ({ state: /** @type {any} */ (all[i].state), questions: { isX: 1, changes: 1 }, lean: /** @type {any} */ (all[i].lean) }));
    const single = [];
    for (const r of reqs) single.push(await a.answer(r));
    assert.deepEqual(await a.answerMany(reqs), single);
    const order = reqs.map((_, i) => (i * 7) % reqs.length);
    assert.deepEqual(await a.answerMany(order.map((i) => reqs[i])), order.map((i) => single[i]));
    assert.deepEqual(await a.answerMany(reqs.slice(3, 9)), single.slice(3, 9));
  });
}
