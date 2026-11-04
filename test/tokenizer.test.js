import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { WordPiece } from '../src/tokenizer.js';
import { fixtureRows } from './helpers.js';

// test/fixtures/vocab.txt is a copy of data/m1/vocab.txt (the MiniLM vocab; sha256 in the manifest test).
const vocabUrl = new URL('./fixtures/vocab.txt', import.meta.url);

test('tokenizer ids equal the Python tokenizer on the fixture (fresh exam rows + edge strings)', () => {
  const tok = new WordPiece(readFileSync(vocabUrl, 'utf8'));
  const rows = fixtureRows();
  assert.ok(rows.length >= 949);
  for (const r of rows) assert.deepEqual(tok.encode(r.text), r.ids, r.text.slice(0, 80));
});

test('tokenizer on a tiny vocab: specials, lowercase, truncation', () => {
  const tok = new WordPiece('[PAD]\n[UNK]\n[CLS]\n[SEP]\nget\nthe\n##s\n');
  assert.deepEqual(tok.encode('GET'), [2, 4, 3]);
  assert.deepEqual(tok.encode('gets zzz'), [2, 4, 6, 1, 3]);
  const long = tok.encode('get '.repeat(50), 8);
  assert.equal(long.length, 8); assert.equal(long[0], 2); assert.equal(long[7], 3);
});
