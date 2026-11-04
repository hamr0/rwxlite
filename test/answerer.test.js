import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { Answerer, calibrated, checkRequest, checkTemperature, manifestTemperature, loadAnswerer, modelString, TEMPERATURE } from '../src/answerer.js';
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
  assert.ok('error' in out[1] && !('answers' in out[1]));
  assert.ok(!('error' in out[0]) && !('error' in out[2]));
  assert.equal(/** @type {any} */ (out[0]).answers.isX.noul, calibrated([0, 0, 0])[2]);
  assert.equal(/** @type {any} */ (out[2]).answers.isX.noul, calibrated([1, 0, 0])[2]);
});

test('answerMany: a runner failure fails every good slot, nothing leaks through', async () => {
  const a = make(() => { throw new Error('boom'); });
  const out = await a.answerMany([req(), req(), req({ lean: null })]);
  assert.ok(out.every((o) => 'error' in o && !('answers' in o)));
  assert.match(/** @type {any} */ (out[0]).error, /boom/);
  await assert.rejects(a.answer(req()), /boom/);
});

test('answerMany: wrong row count, wrong length, NaN and Infinity logits are errors', async () => {
  assert.ok('error' in (await make(() => []).answerMany([req()]))[0]);
  const out = await make(() => [[1, 2], [NaN, 0, 0], [0, Infinity, 0], [0, 0, 0]]).answerMany([req(), req(), req(), req()]);
  assert.ok('error' in out[0] && 'error' in out[1] && 'error' in out[2]);
  assert.ok(!('error' in out[3]));
});

test('answerMany: empty input is empty output and the runner is not called', async () => {
  const a = make(() => { throw new Error('should not run'); });
  assert.deepEqual(await a.answerMany([]), []);
});

const rt = (/** @type {any} */ x) => JSON.parse(JSON.stringify(x));

test('both shapes survive JSON, every slot of a mixed batch too', async () => {
  const a = make(() => [[0, 1, 2], [2, 1, 0]]);
  const out = await a.answerMany([req(), req({ lean: null }), req({ questions: { isX: 1 } }), req({ questions: {} })]);
  assert.equal(out.length, 4);
  for (const o of out) assert.deepEqual(rt(o), o);
  assert.ok('answers' in out[0] && 'error' in out[1] && 'answers' in out[2] && 'error' in out[3]);
  assert.match(/** @type {any} */ (out[1]).error, /^rwxlite: lean/);
  assert.equal(out[1].model, 'rwxlite-0.0.0+deadbeef');
});

test('a no-answer never carries answers; a success never carries error; answer() throws the same text', async () => {
  const a = make(() => [[0, 1, 2]]);
  const [bad] = await a.answerMany([req({ lean: null })]);
  assert.deepEqual(Object.keys(bad).sort(), ['error', 'model']);
  const [good] = await a.answerMany([req()]);
  assert.deepEqual(Object.keys(good).sort(), ['answers', 'model']);
  await assert.rejects(a.answer(req({ lean: null })), (/** @type {Error} */ e) => e.message === /** @type {any} */ (bad).error);
});

test('noul is a finite number in [0,1] and changes >= isX, extreme logits included', async () => {
  const cases = [[1000, -1000, 0], [-1000, -1000, 1000], [0, 0, 0], [-1000, 1000, -1000], [1e6, -1e6, 1e6], [5, -3, 2]];
  const a = make((/** @type {number[][]} */ ids) => ids.map((_, i) => cases[i]));
  const out = await a.answerMany(cases.map(() => req()));
  for (const o of out) {
    const { isX, changes } = /** @type {any} */ (o).answers;
    for (const v of [isX.noul, changes.noul]) assert.ok(Number.isFinite(v) && v >= 0 && v <= 1, String(v));
    assert.ok(changes.noul >= isX.noul);
  }
});

test('the three question shapes return exactly those keys', async () => {
  const a = make(() => [[0, 1, 2]]);
  for (const q of [{ isX: 'q' }, { changes: 'q' }, { isX: 'q', changes: 'q' }]) {
    const o = /** @type {any} */ (await a.answer(req({ questions: q })));
    assert.deepEqual(Object.keys(o.answers).sort(), Object.keys(q).sort());
  }
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

test('manifest temperature: used when present, 0.844 when absent', async () => {
  assert.equal(manifestTemperature({ temperature: 0.858 }), 0.858);
  assert.equal(manifestTemperature({}), 0.844);
  const logits = [[0.5, 1.5, 2.5]];
  const mk = (/** @type {any} */ extra) => new Answerer({ tokenizer: new WordPiece(TINY_VOCAB), runner: stubRunner(() => logits), model: 'm', ...extra });
  const x = async (/** @type {Answerer} */ a) => /** @type {any} */ (await a.answer(req())).answers.isX.noul;
  assert.equal(await x(mk({})), calibrated(logits[0], 0.844)[2]);
  assert.equal(await x(mk({ temperature: 0.858 })), calibrated(logits[0], 0.858)[2]);
  assert.notEqual(await x(mk({ temperature: 0.858 })), await x(mk({})));
  assert.equal(calibrated(logits[0]).join(), calibrated(logits[0], 0.844).join());
});

test('bad temperature throws: 0, negative, NaN, Infinity, string, null, boolean', async () => {
  for (const t of [0, -1, NaN, Infinity, '0.858', null, true]) {
    assert.throws(() => manifestTemperature({ temperature: t }), /temperature must be a finite number > 0/);
    assert.throws(() => checkTemperature(t), /temperature/);
    assert.throws(() => new Answerer({ tokenizer: new WordPiece(TINY_VOCAB), runner: stubRunner(() => []), model: 'm', temperature: /** @type {any} */ (t) }), /temperature/);
  }
  const dir = await mkdtemp(path.join(tmpdir(), 'rwxlite-'));
  try {
    await writeFile(path.join(dir, 'manifest.json'), JSON.stringify({ version: '0.0.0', modelFile: 'model-x.onnx', temperature: 0, files: {} }));
    await assert.rejects(loadAnswerer({ dir }), /temperature must be a finite number > 0/);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('loadAnswerer validates threads before touching the disk: -1, 1.5, "2", NaN throw; 0 and 4 pass the check', async () => {
  const dir = path.join(tmpdir(), 'rwxlite-no-such-dir');
  for (const threads of [-1, 1.5, '2', NaN]) {
    await assert.rejects(loadAnswerer({ dir, threads: /** @type {any} */ (threads) }), /rwxlite: threads must be an integer >= 0/, String(threads));
  }
  // valid values get past the check and fail later, on the missing manifest
  for (const threads of [0, 4]) await assert.rejects(loadAnswerer({ dir, threads }), /ENOENT/, String(threads));
});
