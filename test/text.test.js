import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { formatText, accessHint, checkTextFormat, clean, unescapeHtml } from '../src/text.js';
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

test('lean rule credential-set is read as cant-undo-verb; other rules are unchanged', () => {
  const st = { method: 'PUT', path: '/account/pin', operationId: 'op', summary: 's', description: 'd' };
  const a = formatText(st, { class: 'x', rule: 'credential-set' });
  assert.equal(a, formatText(st, { class: 'x', rule: 'cant-undo-verb' }));
  assert.ok(a.startsWith('lean: x cant-undo-verb | PUT /account/pin'));
  assert.ok(formatText(st, { class: 'x', rule: 'modify-verb' }).startsWith('lean: x modify-verb |'));
  assert.ok(formatText(st, { class: 'w', rule: 'method' }).startsWith('lean: w method |'));
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

// ---- text format 2 (access hint) ----

test('format 1 is today\'s text unchanged: default and explicit 1 equal the Python fixture on every row', () => {
  const rows = fixtureRows().filter((r) => r.state && r.lean);
  assert.ok(rows.length >= 900);
  for (const r of rows) {
    assert.equal(formatText(/** @type {any} */ (r.state), /** @type {any} */ (r.lean), 1), r.text);
    assert.equal(formatText(/** @type {any} */ (r.state), /** @type {any} */ (r.lean)), r.text);
  }
});

test('format 2 equals the Python fmt_text(format=2) on every row of test/fixtures/text2.jsonl, and only the hint differs', () => {
  const rows = readFileSync(new URL('./fixtures/text2.jsonl', import.meta.url), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  assert.ok(rows.length >= 800);
  let hinted = 0;
  for (const r of rows) {
    assert.equal(formatText(r.state, r.lean, 1), r.t1);
    assert.equal(formatText(r.state, r.lean, 2), r.t2);
    if (r.t2 !== r.t1) { hinted++; assert.equal(r.t2, r.t1.replace(' | ', ' | hint: access | ')); }
  }
  assert.ok(hinted >= 300 && hinted < rows.length);
});

test('format 2 puts the hint right after the lean; unhinted operations are unchanged; the hint comes from the operation alone', () => {
  const lean = { class: /** @type {'w'} */ ('w'), rule: 'floor-put' };
  const grant = { method: 'PUT', path: '/projects/{id}/iam/policy', operationId: 'setIamPolicy', summary: 'Set the IAM policy' };
  assert.equal(formatText(grant, lean, 2), 'lean: w floor-put | hint: access | PUT /projects/{id}/iam/policy | op: setIamPolicy | sum: Set the IAM policy');
  assert.equal(formatText(grant, lean, 1), 'lean: w floor-put | PUT /projects/{id}/iam/policy | op: setIamPolicy | sum: Set the IAM policy');
  const plain = { method: 'PUT', path: '/autoscaling/policy', operationId: 'putScalingPolicy', summary: 'Set the autoscaling policy' };
  assert.equal(accessHint(plain), false);
  assert.equal(formatText(plain, lean, 2), formatText(plain, lean, 1));
  // a caller cannot inject the hint: extra fields are ignored, and the lean never carries it
  assert.equal(formatText(/** @type {any} */ ({ ...plain, hint: 'access' }), lean, 2), formatText(plain, lean, 1));
  // the description is not read
  assert.equal(accessHint(/** @type {any} */ ({ ...plain, description: 'Grants permissions to other users and shares access.' })), false);
  // DELETE is never hinted
  assert.equal(accessHint({ method: 'DELETE', path: '/a/b/members/{id}', operationId: 'addMember', summary: 'Add member' }), false);
  // the hint sits right behind the lean, so the 128-token cut cannot reach it (the long fields come after it)
  const long = formatText({ ...grant, summary: 'x '.repeat(300), description: 'y '.repeat(300) }, lean, 2);
  assert.ok(long.startsWith('lean: w floor-put | hint: access | PUT '));
});

test('accessHint: the six access families are hinted, non-access policies and reads are not', () => {
  const yes = [
    ['PUT', '/b/{b}/policy', 'PutBucketPolicy', ''], ['POST', '/projects/{p}:setIamPolicy', 'setIamPolicy', ''], ['POST', '/repos/{r}/keys', 'repos/create-deploy-key', 'Create a deploy key'],
    ['POST', '/user/keys', 'users/create-public-ssh-key', 'Create a public SSH key for the authenticated user'], ['POST', '/api-keys', 'createApiKey', 'Create an API key'],
    ['POST', '/webhooks', 'createWebhook', 'Create a webhook'], ['POST', '/users', 'createUser', 'Create user'], ['PUT', '/teams/{t}/members/{u}', 'addTeamMember', 'Add a member to a team'],
  ];
  for (const [method, path, operationId, summary] of yes) assert.equal(accessHint({ method, path, operationId, summary }), true, `${method} ${path} ${operationId}`);
  const no = [
    ['GET', '/b/{b}/policy', 'GetBucketPolicy', 'Get the bucket policy'], ['PUT', '/b/{b}/lifecycle', 'PutBucketLifecyclePolicy', 'Set the lifecycle policy'],
    ['PUT', '/retention/policy', 'putRetentionPolicy', 'Set retention policy'], ['POST', '/routing/policy', 'createRoutingPolicy', 'Create a routing policy'],
    ['GET', '/users', 'listUsers', 'List users'], ['POST', '/auth/token/refresh', 'refreshToken', 'Refresh a token'], ['POST', '/files', 'createFile', 'Create a file'],
  ];
  for (const [method, path, operationId, summary] of no) assert.equal(accessHint({ method, path, operationId, summary }), false, `${method} ${path} ${operationId}`);
});

test('bad text format throws: 0, 3, 1.5, "2", null, NaN', () => {
  for (const f of [0, 3, 1.5, '2', null, NaN, true]) {
    assert.throws(() => checkTextFormat(f), /textFormat must be 1 or 2/);
    assert.throws(() => formatText({ method: 'GET', path: '/a' }, { class: 'r', rule: 'method' }, /** @type {any} */ (f)), /textFormat must be 1 or 2/);
  }
  assert.equal(checkTextFormat(1), 1);
  assert.equal(checkTextFormat(2), 2);
});
