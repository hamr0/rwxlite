// A JS reference of the measured decision rule (docs/product/prd.md, "Decision rule rwxmap must apply").
// rwxlite itself never decides letters, so this lives in the test only. It must reproduce test/fixtures/decision.jsonl
// (made by m1/decision-fixture.py from the pre-registered scripts) from isX/changes/lean/tier/state alone.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const ORDER = { r: 0, w: 1, x: 2 };
const LETTER = ['r', 'w', 'x'];
const TIER = { 'jev-lower': 'lower', 'jev-raise-wx': 'raise-wx', 'jev-raise-get': 'raise-get' };
const CUT = { lower: 0.30, rcut: 0.40, raiseWx: 0.15, raiseGet: 0.05 };
const ASK_BELOW = 0.97;
// train/common.py, same pieces. Text is first normalised by norm() (camelCase split, non-alphanumerics to a space, lowercase).
const NOUN = '(?:password|passcode|passphrase|pin|pin code|auth key|authkey|api key|apikey|api secret|secret key|client secret)s?';
const CRED = new RegExp('\\b(?:change|reset|rotate|regenerate|renew|revoke|invalidate|expire)\\b(?: \\w+){0,3}? ' + NOUN + '\\b(?! (?:polic|rule|requirement|complexity|setting|config))');
const norm = (/** @type {any} */ s) => String(s ?? '').replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/[^A-Za-z0-9]+/g, ' ').toLowerCase();
const credHit = (/** @type {any} */ st) => String(st.method).toUpperCase() !== 'GET' && ['operationId', 'summary', 'path'].some((f) => CRED.test(norm(st[f])));

/** @returns {{letter: string, asked: boolean, move: 'lowering'|'raise'|'keep'}} */
function decide({ isX, changes, lean, jev_tier, state }) {
  const tier = /** @type {any} */ (TIER)[jev_tier] ?? 'none';
  const pw = changes - isX; const pr = 1 - changes;
  const mech = /** @type {any} */ (ORDER)[lean.class]; let m = mech;
  if (tier === 'lower' && m === 2 && isX < CUT.lower) m = (state.method === 'POST' && changes < CUT.rcut) ? 0 : 1;
  else if (tier === 'raise-wx' && m === 1 && isX >= CUT.raiseWx) m = 2;
  else if (tier === 'raise-get' && m === 0 && changes >= CUT.raiseGet) m = 1;
  if (credHit(state)) m = 2;
  const maxP = Math.max(pr, pw, isX);
  return { letter: LETTER[m], asked: m < mech && maxP < ASK_BELOW, move: m < mech ? 'lowering' : m > mech ? 'raise' : 'keep' };
}

test('the written rule reproduces every fixture row (949) from p, lean, tier and state alone', () => {
  const rows = readFileSync(new URL('./fixtures/decision.jsonl', import.meta.url), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  assert.equal(rows.length, 949);
  const n = { lowering: 0, raise: 0, keep: 0, asked: 0 };
  for (const r of rows) {
    assert.ok(Number.isFinite(r.isX) && Number.isFinite(r.changes) && r.changes >= r.isX, r.id);
    assert.ok(!('truth' in r));
    const d = decide(r);
    assert.deepEqual({ letter: d.letter, asked: d.asked }, r.expected, r.id);
    n[d.move]++; if (d.asked) n.asked++;
  }
  console.log('decision counts', JSON.stringify(n));
  assert.equal(n.lowering + n.raise + n.keep, 949);
});
