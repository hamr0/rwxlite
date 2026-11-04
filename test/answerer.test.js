import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { Answerer, calibrated, checkRequest, loadAnswerer, modelString, TEMPERATURE } from '../src/answerer.js';
import { WordPiece } from '../src/tokenizer.js';
import { stubRunner, TINY_VOCAB } from './helpers.js';

const state = { method: 'GET', path: '/a', operationId: 'getA', summary: 's', description: 'd' };
const lean = { class: 'r', rule: 'method' };
const req = (/** @type {any} */ over = {}) => ({ state, model: 'jev-x', questions: { isX: 'q', changes: 'q' }, lean, ...over });
const make = (/** @type {any} */ fn, model = 'rwxlite-0.0.0+deadbeef') => new Answerer({ tokenizer: new WordPiece(TINY_VOCAB), runner: stubRunner(fn), model });

test('calibrated: softmax(logits / T), sums to 1, order kept', () => {
  const p = calibrated([2, 0, -1]);
  assert.ok(Math.abs(p[0] + p[1] + p[2] - 1) < 1e-12);
  assert.ok(p[0] > p[1] && p[1] > p[2]);
  const z = [2, 0, -1].map((v) => Math.exp(v / TEMPERATURE)); const s = z[0] + z[1] + z[2];
  assert.ok(Math.abs(p[0] - z[0] / s) < 1e-12);
  assert.deepEqual(calibrated([5, 5, 5]).map((v) => +v.toFixed(6)), [0.333333, 0.333333, 0.333333]);
  assert.ok(calibrated([1000, 0, -1000]).every(Number.isFinite));
});

test('checkRequest accepts a good request and returns the model text and keys', () => {
  const { text, keys } = checkRequest(req());
  assert.equal(text, 'lean: r method | GET /a | op: getA | sum: s | desc: d');
  assert.deepEqual(keys, ['isX', 'changes']);
});

test('checkRequest fails closed on every bad shape', () => {
  /** @type {Array<[string, any]>} */
  const bad = [
    ['null', null], ['string', 'x'], ['no state', req({ state: undefined })], ['empty method', req({ state: { method: '', path: '/a' } })],
    ['no path', req({ state: { method: 'GET' } })], ['no lean', req({ lean: undefined })], ['bad class', req({ lean: { class: 'q', rule: 'm' } })],
    ['no rule', req({ lean: { class: 'r' } })], ['no questions', req({ questions: undefined })], ['empty questions', req({ questions: {} })],
    ['unknown question', req({ questions: { isX: 1, other: 1 } })],
  ];
  for (const [name, r] of bad) assert.throws(() => checkRequest(r), /rwxlite:/, name);
});

test('answer returns Jev shape: isX = p(x), changes = p(w)+p(x)', async () => {
  const a = make(() => [[0, 1, 2]]);
  const out = await a.answer(req());
  const p = calibrated([0, 1, 2]);
  assert.equal(out.model, 'rwxlite-0.0.0+deadbeef');
  assert.deepEqual(Object.keys(out.answers).sort(), ['changes', 'isX']);
  assert.ok(Math.abs(/** @type {any} */ (out.answers.isX).noul - p[2]) < 1e-12);
  assert.ok(Math.abs(/** @type {any} */ (out.answers.changes).noul - (p[1] + p[2])) < 1e-12);
});

test('only the asked questions come back', async () => {
  const a = make(() => [[0, 0, 0]]);
  assert.deepEqual(Object.keys((await a.answer(req({ questions: { isX: 'q' } }))).answers), ['isX']);
  assert.deepEqual(Object.keys((await a.answer(req({ questions: { changes: 'q' } }))).answers), ['changes']);
});

test('answerMany: a bad slot is isolated and the good ones still answer, in order', async () => {
  let seen = 0;
  const a = make((/** @type {number[][]} */ ids) => { seen = ids.length; return ids.map((_, i) => [i, 0, 0]); });
  const out = await a.answerMany([req(), req({ lean: null }), req()]);
  assert.equal(seen, 2);
  assert.ok(out[1] instanceof Error);
  assert.ok(!(out[0] instanceof Error) && !(out[2] instanceof Error));
  assert.equal(/** @type {any} */ (out[0]).answers.isX.noul, calibrated([0, 0, 0])[2]);
  assert.equal(/** @type {any} */ (out[2]).answers.isX.noul, calibrated([1, 0, 0])[2]);
});

test('answerMany: a runner failure fails every good slot, nothing leaks through', async () => {
  const a = make(() => { throw new Error('boom'); });
  const out = await a.answerMany([req(), req(), req({ lean: null })]);
  assert.ok(out.every((o) => o instanceof Error));
  assert.match(/** @type {Error} */ (out[0]).message, /boom/);
  await assert.rejects(a.answer(req()), /boom/);
});

test('answerMany: wrong row count, wrong length, NaN and Infinity logits are errors', async () => {
  assert.ok((await make(() => []).answerMany([req()]))[0] instanceof Error);
  const out = await make(() => [[1, 2], [NaN, 0, 0], [0, Infinity, 0], [0, 0, 0]]).answerMany([req(), req(), req(), req()]);
  assert.ok(out[0] instanceof Error && out[1] instanceof Error && out[2] instanceof Error);
  assert.ok(!(out[3] instanceof Error));
});

test('answerMany: empty input is empty output and the runner is not called', async () => {
  const a = make(() => { throw new Error('should not run'); });
  assert.deepEqual(await a.answerMany([]), []);
});

test('modelString is rwxlite-<semver>+<sha8>', () => {
  assert.equal(modelString('1.2.3', 'abcdef0123456789'), 'rwxlite-1.2.3+abcdef01');
});

test('loadAnswerer throws on a sha256 mismatch, a missing manifest and a bad manifest (before loading any model)', async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'rwxlite-'));
  try {
    await assert.rejects(loadAnswerer({ dir }), /ENOENT/);
    await writeFile(path.join(dir, 'model-x.onnx'), 'fake model');
    await writeFile(path.join(dir, 'vocab.txt'), 'fake vocab');
    await writeFile(path.join(dir, 'manifest.json'), '{"nope":1}');
    await assert.rejects(loadAnswerer({ dir }), /bad manifest/);
    await writeFile(path.join(dir, 'manifest.json'), JSON.stringify({ version: '0.0.0', modelFile: 'model-x.onnx', files: { 'model-x.onnx': '0'.repeat(64), 'vocab.txt': '0'.repeat(64) } }));
    await assert.rejects(loadAnswerer({ dir }), /sha256 does not match/);
  } finally { await rm(dir, { recursive: true, force: true }); }
});
