// Shared by the tests: fixture loading and a stub runner.
import { readFileSync } from 'node:fs';

/** @typedef {{state?: import('../src/text.js').State, lean?: import('../src/text.js').Lean, text: string, ids: number[]}} FixtureRow */

/** @returns {FixtureRow[]} */
export function fixtureRows() {
  return readFileSync(new URL('./fixtures/parity.jsonl', import.meta.url), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
}

/** A tokenizer-free stub: every request becomes the same short id list. @param {(ids: number[][]) => number[][]} fn */
export function stubRunner(fn) { return { run: async (/** @type {number[][]} */ ids) => fn(ids) }; }

/** A tiny vocab: specials + a few words, enough for the Answerer's tokenizer in unit tests. */
export const TINY_VOCAB = ['[PAD]', '[UNK]', '[CLS]', '[SEP]', '[MASK]', 'get', 'lean', ':', 'r', 'w', 'x', 'method', '/', 'a', '|', '##s'].join('\n') + '\n';
