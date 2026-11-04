import test from 'node:test';
import assert from 'node:assert/strict';
import { formatText, clean } from '../src/text.js';
import { fixtureRows } from './helpers.js';

test('formatText matches the Python fmt_text on every fresh-exam fixture row', () => {
  const rows = fixtureRows().filter((r) => r.state && r.lean);
  assert.ok(rows.length >= 900);
  for (const r of rows) assert.equal(formatText(/** @type {any} */ (r.state), /** @type {any} */ (r.lean)), r.text);
});

test('formatText puts the lean first and skips empty fields', () => {
  assert.equal(formatText({ method: 'get', path: '/a' }, { class: 'r', rule: 'method' }), 'lean: r method | GET /a');
  assert.equal(formatText({ method: 'POST', path: '/a', operationId: 'op', summary: '  ', description: null }, { class: 'w', rule: 'x' }), 'lean: w x | POST /a | op: op');
});

test('clean strips tags, unescapes, collapses whitespace and cuts by code points', () => {
  assert.equal(clean('<b>a</b>  &amp;\n b', 99), 'a & b');
  assert.equal(clean(null, 5), '');
  assert.equal(clean('😀😀😀', 2), '😀😀');
  assert.equal(clean('a b c', 3), 'a b');
});
