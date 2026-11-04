import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { formatText, clean, unescapeHtml } from '../src/text.js';
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

test('QUERY is read as GET; other methods are unchanged', () => {
  const lean = { class: /** @type {'r'} */ ('r'), rule: 'method' };
  const f = { path: '/a', operationId: 'op', summary: 's', description: 'd' };
  const get = formatText({ method: 'GET', ...f }, lean);
  assert.equal(formatText({ method: 'QUERY', ...f }, lean), get);
  assert.equal(formatText({ method: 'query', ...f }, lean), get);
  assert.ok(formatText({ method: 'POST', ...f }, lean).includes('| POST /a'));
  assert.ok(formatText({ method: 'delete', ...f }, lean).includes('| DELETE /a'));
});

test('clean strips tags, unescapes, collapses whitespace and cuts by code points', () => {
  assert.equal(clean('<b>a</b>  &amp;\n b', 99), 'a & b');
  assert.equal(clean(null, 5), '');
  assert.equal(clean('😀😀😀', 2), '😀😀');
  assert.equal(clean('a b c', 3), 'a b');
});

test('unescapeHtml and clean match Python html.unescape on every probe (test/fixtures/unescape.jsonl)', () => {
  const rows = readFileSync(new URL('./fixtures/unescape.jsonl', import.meta.url), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  assert.ok(rows.length >= 300);
  for (const r of rows) {
    const got = r.kind === 'clean' ? clean(r.in, r.n) : unescapeHtml(r.in);
    assert.equal(got, r.out, JSON.stringify(r.in));
  }
});
