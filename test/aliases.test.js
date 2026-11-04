import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

// m1/round10_aliases.py is the table the round 10 assembly imports; it must equal LEAN_RULE_ALIASES in src/text.js.
test('python lean-rule alias table equals src/text.js', (t) => {
  const r = spawnSync('python3', ['m1/round10_aliases.py'], { encoding: 'utf8' });
  if (r.error) return t.skip('python3 not available');
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /ok \{'credential-set': 'cant-undo-verb'\}/);
});
