// Round 15 Jev pilot: Jev as the answerer inside rwxmap's own mode-c pipeline, on the 400 blind-reviewed rows. Offline labelling only.
// Same steps as rwxmap src/cli.js runJev (commit 1c25be1, read-only extract):
//   classifyOperations (mechanical) -> needsJev (tier by pile) -> askJev (src/jev-client.js: jevState + jevQuestions(tier), jev-latest)
//   -> applyJev (thresholds lower 0.10 / raise-wx 0.80 / raise-get 0.50) -> for jev-lower rows moved to w, a second askJev with the
//   jev-raise-get "changes" question, applyJev again (r when p(changes) <= 0.50). Rows in no pile get no call and keep the mechanical letter.
// Stores per row: tier, p_first (isX or changes), p_changes (second question), model, tokens, letters. Never prints or stores the key.
//   git -C /home/hamr/PycharmProjects/rwxmap archive 1c25be1 src package.json | tar -x -C TREE
//   node r15/jev_pilot.mjs --tree TREE --ops ops.jsonl --out jev.jsonl [--limit N] [--cap USD]
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { parseArgs, parseEnv } from 'node:util';
const { values: a } = parseArgs({ options: { tree: { type: 'string' }, ops: { type: 'string' }, out: { type: 'string' }, limit: { type: 'string' }, cap: { type: 'string' } } });
const { classifyOperations } = await import(`${a.tree}/src/exporter.js`);
const { needsJev, applyJev, jevTier, jevUndecided } = await import(`${a.tree}/src/jev.js`);
const { askJev } = await import(`${a.tree}/src/jev-client.js`);
const PRICE_IN = 42 / 1e9; // $ per input token, as m0/jev-label.mjs (rwxmap jev-learnings); output not billed
const CAP = Number(a.cap || 1);
function getKey() {
  if (process.env.RWXMAP_JEV_KEY) return process.env.RWXMAP_JEV_KEY;
  try { return parseEnv(fs.readFileSync(path.join(os.homedir(), 'PycharmProjects', 'rwxmap', '.env'), 'utf8')).RWXMAP_JEV_KEY || ''; } catch { return ''; }
}
const key = getKey();
if (!key) throw new Error('no RWXMAP_JEV_KEY in env or rwxmap/.env');
let rows = fs.readFileSync(a.ops, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
if (a.limit) rows = rows.slice(0, Number(a.limit));
const ops = rows.map((o) => { const r = { method: o.method.toUpperCase(), path: o.path }; for (const k of ['operationId', 'summary', 'description']) if (o[k] !== '') r[k] = o[k]; return r; });
const mech = classifyOperations(ops);
const opts = { fetchImpl: fetch, key, concurrency: 4 };
const out = rows.map((o, i) => ({ op_id: o.op_id, mech_letter: mech[i].class, mech_rule: mech[i].rule, tier: needsJev(mech[i]), p_first: null, p_changes: null, model: null, called: 0, failed: 0, tok_in: 0, tok_out: 0, calls: 0, jev_letter: mech[i].class, jev_move: 'none' }));
let spent = 0, stop = false;
const bill = (u) => { spent += u.input * PRICE_IN; if (spent > CAP) stop = true; };
const queue = out.map((_, i) => i).filter((i) => out[i].tier);
async function worker() {
  while (queue.length && !stop) {
    const i = queue.pop(), t = out[i], tier = t.tier, v = mech[i], m = ops[i].method;
    let first = null;
    try { first = await askJev(ops[i], tier, opts); } catch { /* fail closed below */ }
    t.calls++;
    if (!first) { t.failed++; const u = jevUndecided(v, { method: m }); t.jev_letter = u.class; t.jev_move = 'undecided'; continue; }
    bill(first.usage); t.tok_in += first.usage.input; t.tok_out += first.usage.output; t.p_first = first.p; t.model = first.model; t.called = 1;
    const moved = applyJev(v, { p: first.p, model: first.model }, { method: m });
    t.jev_letter = moved.class; t.jev_move = moved.class !== v.class ? 'first' : 'none';
    const spec = jevTier(tier);
    if (spec && spec.second && moved.class === spec.to && moved.class !== v.class) {
      let sec = null;
      try { sec = await askJev(ops[i], spec.second.ask, opts); } catch { /* undecided */ }
      t.calls++;
      if (!sec) { t.failed++; const u = jevUndecided(v, { method: m }); t.jev_letter = u.class; t.jev_move = 'undecided'; continue; }
      bill(sec.usage); t.tok_in += sec.usage.input; t.tok_out += sec.usage.output; t.p_changes = sec.p;
      const f = applyJev(v, { p: first.p, model: first.model, changes: { p: sec.p, model: sec.model } }, { method: m });
      if (f.jev === undefined) { t.failed++; t.jev_letter = f.class; t.jev_move = 'undecided'; } else { t.jev_letter = f.class; t.jev_move = f.class !== v.class ? 'second' : 'none'; }
    }
  }
}
await Promise.all(Array.from({ length: 4 }, worker));
fs.writeFileSync(a.out, out.map((x) => JSON.stringify(x)).join('\n') + '\n');
const calls = out.reduce((s, x) => s + x.calls, 0), tin = out.reduce((s, x) => s + x.tok_in, 0);
console.log(JSON.stringify({ rows: out.length, tiered: out.filter((x) => x.tier).length, calls, failed: out.reduce((s, x) => s + x.failed, 0), tok_in: tin, tok_out: out.reduce((s, x) => s + x.tok_out, 0), spend_usd: +spent.toFixed(5), stopped_by_cap: stop }));
