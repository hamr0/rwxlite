// The local answerer: Jev's request in, Jev's answer shape out.
//
// Request:  { state, model, questions, lean }
//   state      Jev's five fields (rwxmap jevState): method, path, operationId, summary, description.
//   model      the model asked for; ignored (there is one local model), kept so the shape matches Jev.
//   questions  an object whose KEYS say what to answer: 'isX', 'changes', or both in one call.
//              The question text itself is not read: the criteria are baked into the weights.
//   lean       { class: 'r'|'w'|'x', rule } — the mechanical verdict. Jev does not get it, but this
//              model was trained with it as the first words of its input, so it is required.
// Answer:   { model, answers: { isX?: { noul }, changes?: { noul } } }
//   isX = p(x), changes = p(w) + p(x), from softmax(logits / T). rwxmap derives
//   x = isX, w = changes - isX, r = 1 - changes.
//
// rwxlite only returns p. It never decides a letter, never applies cuts, never asks.
// Any bad request or failure throws; the caller keeps the mechanical letter (fail closed).

import { createHash } from 'node:crypto';
import os from 'node:os';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { formatText } from './text.js';
import { WordPiece } from './tokenizer.js';

/** Calibration temperature fit on the val split (docs/wiki/classifier-training.md). */
export const TEMPERATURE = 0.844;
export const MAX_LEN = 128;
export const QUESTIONS = /** @type {const} */ (['isX', 'changes']);

/**
 * @typedef {import('./text.js').State} State
 * @typedef {import('./text.js').Lean} Lean
 * @typedef {{state: State, model?: string, questions: Record<string, unknown>, lean: Lean}} Request
 * @typedef {{model: string, answers: {isX?: {noul: number}, changes?: {noul: number}}}} Answer
 * @typedef {{run: (ids: number[][]) => Promise<number[][]>}} Runner  (n,seq) token ids -> (n,3) logits
 */

/** @param {number[]} L logits for (r, w, x) @returns {[number, number, number]} */
export function calibrated(L) {
  const z = L.map((v) => v / TEMPERATURE); const m = Math.max(...z);
  const e = z.map((v) => Math.exp(v - m)); const s = e[0] + e[1] + e[2];
  return [e[0] / s, e[1] / s, e[2] / s];
}

/** @param {unknown} req @returns {{text: string, keys: string[]}} */
export function checkRequest(req) {
  const r = /** @type {any} */ (req);
  if (!r || typeof r !== 'object') throw new Error('rwxlite: request must be an object');
  const st = r.state;
  if (!st || typeof st !== 'object' || typeof st.method !== 'string' || typeof st.path !== 'string' || !st.method || !st.path) {
    throw new Error('rwxlite: state needs string method and path');
  }
  const lean = r.lean;
  if (!lean || typeof lean !== 'object' || !['r', 'w', 'x'].includes(lean.class) || typeof lean.rule !== 'string' || !lean.rule) {
    throw new Error('rwxlite: lean needs class r|w|x and a rule');
  }
  if (!r.questions || typeof r.questions !== 'object') throw new Error('rwxlite: questions must be an object');
  const keys = Object.keys(r.questions);
  if (keys.length === 0) throw new Error('rwxlite: no questions');
  for (const k of keys) if (!QUESTIONS.includes(/** @type {any} */ (k))) throw new Error(`rwxlite: unknown question ${k}`);
  return { text: formatText(st, lean), keys };
}

/** @param {[number, number, number]} P @param {string[]} keys @returns {Answer['answers']} */
function answersFrom(P, keys) {
  /** @type {Answer['answers']} */
  const a = {};
  for (const k of keys) a[/** @type {'isX'|'changes'} */ (k)] = { noul: k === 'isX' ? P[2] : P[1] + P[2] };
  return a;
}

export class Answerer {
  /** @param {{tokenizer: WordPiece, runner: Runner, model: string}} parts */
  constructor({ tokenizer, runner, model }) {
    this.tokenizer = tokenizer; this.runner = runner; this.model = model;
  }

  /** @param {Request} req @returns {Promise<Answer>} */
  async answer(req) {
    const [a] = await this.answerMany([req]);
    if (a instanceof Error) throw a;
    return a;
  }

  /**
   * Many requests in one model call. Never throws for one bad request: that slot holds an Error,
   * so the caller can keep the mechanical letter for it alone. A model failure fails every slot.
   * @param {Request[]} reqs
   * @returns {Promise<Array<Answer|Error>>}
   */
  async answerMany(reqs) {
    /** @type {Array<Answer|Error>} */
    const out = new Array(reqs.length);
    /** @type {{i: number, ids: number[], keys: string[]}[]} */
    const ok = [];
    reqs.forEach((req, i) => {
      try {
        const { text, keys } = checkRequest(req);
        ok.push({ i, ids: this.tokenizer.encode(text, MAX_LEN), keys });
      } catch (err) { out[i] = err instanceof Error ? err : new Error(String(err)); }
    });
    if (ok.length) {
      let logits;
      try {
        logits = await this.runner.run(ok.map((o) => o.ids));
        if (!Array.isArray(logits) || logits.length !== ok.length) throw new Error('rwxlite: runner returned the wrong number of rows');
      } catch (err) {
        const e = err instanceof Error ? err : new Error(String(err));
        for (const o of ok) out[o.i] = e;
        return out;
      }
      ok.forEach((o, k) => {
        const L = logits[k];
        if (!Array.isArray(L) || L.length !== 3 || !L.every(Number.isFinite)) { out[o.i] = new Error('rwxlite: bad logits'); return; }
        out[o.i] = { model: this.model, answers: answersFrom(calibrated(L), o.keys) };
      });
    }
    return out;
  }
}

/**
 * The model string: rwxlite-<semver>+<first 8 hex of the int8 weights' sha256>. Changes whenever the weights do.
 * @param {string} version
 * @param {string} sha256hex
 */
export function modelString(version, sha256hex) {
  return `rwxlite-${version}+${sha256hex.slice(0, 8)}`;
}

/**
 * An onnxruntime-node runner over (n, seq) token ids, padded per batch.
 * @param {any} ort the onnxruntime-node module
 * @param {any} session an ort.InferenceSession
 * @returns {Runner}
 */
export function ortRunner(ort, session) {
  return {
    async run(batch) {
      const n = batch.length; const L = Math.max(...batch.map((b) => b.length));
      const ids = new BigInt64Array(n * L); const mask = new BigInt64Array(n * L); const types = new BigInt64Array(n * L);
      batch.forEach((b, i) => b.forEach((id, j) => { ids[i * L + j] = BigInt(id); mask[i * L + j] = 1n; }));
      const feeds = {
        input_ids: new ort.Tensor('int64', ids, [n, L]),
        attention_mask: new ort.Tensor('int64', mask, [n, L]),
        token_type_ids: new ort.Tensor('int64', types, [n, L]),
      };
      const { logits } = await session.run(feeds);
      const d = /** @type {Float32Array} */ (logits.data);
      return Array.from({ length: n }, (_, i) => [d[i * 3], d[i * 3 + 1], d[i * 3 + 2]]);
    },
  };
}

/**
 * Load the answerer from a model directory holding the model file, vocab.txt and manifest.json
 * ({version, modelFile, files: {name: sha256}}). manifest.modelFile names the weights (e.g. model-int8.onnx), so
 * switching the shipped variant is a manifest change. Every file's sha256 is checked before use; a mismatch throws.
 * onnxruntime-node is an optional dependency, imported only here.
 * threads: intra-op threads for onnxruntime. Default Math.min(4, os.availableParallelism()); measured on a 4-core i3-8100T,
 * batch 1, int8 per-channel: 15.5 ms mean at 1 thread, 9.2 at 2, 6.9 at 4. Pass 1 for the old single-thread behaviour.
 * @param {{dir: string, threads?: number, manifestFile?: string}} opts
 * @returns {Promise<Answerer>}
 */
export async function loadAnswerer({ dir, threads = Math.min(4, os.availableParallelism()), manifestFile = 'manifest.json' }) {
  const manifest = JSON.parse(await readFile(path.join(dir, manifestFile), 'utf8'));
  if (!manifest || typeof manifest.version !== 'string' || typeof manifest.modelFile !== 'string' || !manifest.files) throw new Error('rwxlite: bad manifest.json');
  const modelFile = path.basename(manifest.modelFile);
  /** @type {Record<string, Buffer>} */
  const bytes = {};
  for (const name of [modelFile, 'vocab.txt']) {
    const want = manifest.files[name];
    const buf = await readFile(path.join(dir, name));
    const got = createHash('sha256').update(buf).digest('hex');
    if (typeof want !== 'string' || got !== want) throw new Error(`rwxlite: ${name} sha256 does not match manifest.json`);
    bytes[name] = buf;
  }
  let ort;
  try { ort = (await import('onnxruntime-node')).default; } catch {
    throw new Error('rwxlite: onnxruntime-node is not installed (it is an optional dependency)');
  }
  const session = await ort.InferenceSession.create(bytes[modelFile], {
    executionProviders: ['cpu'], intraOpNumThreads: threads, interOpNumThreads: 1, graphOptimizationLevel: 'all',
  });
  return new Answerer({
    tokenizer: new WordPiece(bytes['vocab.txt'].toString('utf8')),
    runner: ortRunner(ort, session),
    model: modelString(manifest.version, manifest.files[modelFile]),
  });
}
