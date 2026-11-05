// Round 12: Jev cross-check on variants-x2.jsonl (sends description too). Mirrors m1/r12-jev-check.mjs request code.
//   node m1/r12-jev-check.mjs        ask (resumable) then filter
// Reuses m0/jev-label.mjs request logic + questions exactly (that file runs main() on import,
// so the thin request code is mirrored here). Key never printed.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { parseEnv } from 'node:util';
import { fileURLToPath } from 'node:url';
import * as qX from '../m0/questions/criteria-x.mjs';
import * as qXRaise from '../m0/questions/criteria-x-raise.mjs';
import * as qChanges from '../m0/questions/criteria-changes.mjs';

const D = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'data', 'round12');
const OUT = path.join(D, 'jev-x2.jsonl');
const ENDPOINT = 'https://api.typesafe.ai/v1/systemone';
const CAP_USD = 2, PRICE_IN = 42 / 1e9, FALLBACK_COST = 0.000085, RESERVE = 4 * 0.0003;
const CONCURRENCY = Number(process.env.JEV_CONCURRENCY) || 4, TIMEOUT_MS = 30_000, MAX_RETRIES = 5;
const GROUPS = {
  POST: { key: 'isX', q: qX }, PUT: { key: 'isX', q: qXRaise }, PATCH: { key: 'isX', q: qXRaise },
  GET: { key: 'changes', q: qChanges },
};
function getKey() {
  if (process.env.RWXMAP_JEV_KEY) return process.env.RWXMAP_JEV_KEY;
  try { return parseEnv(fs.readFileSync(path.join(os.homedir(), 'PycharmProjects', 'rwxmap', '.env'), 'utf8')).RWXMAP_JEV_KEY || ''; } catch { return ''; }
}
async function postOnce(key, body, attempt = 0) {
  let res;
  try {
    res = await fetch(ENDPOINT, { method: 'POST', headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (e) { throw new Error(`request failed (${e instanceof Error ? e.message : 'network'})`); }
  if (res.status === 429 || res.status === 529) {
    if (attempt >= MAX_RETRIES) throw new Error(`HTTP ${res.status} after ${attempt} retries`);
    await new Promise((r) => setTimeout(r, Math.min(2 ** attempt * 500, 16_000)));
    return postOnce(key, body, attempt + 1);
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  try { return await res.json(); } catch { throw new Error('malformed JSON'); }
}
async function ask(key, row) {
  const g = GROUPS[row.method.toUpperCase()];
  const state = { method: row.method, path: row.path, operationId: row.operationId, summary: row.summary || null, description: row.description || null };
  const json = await postOnce(key, { state, model: 'jev-latest', questions: g.q.questions() });
  const a = json?.answers?.[g.key];
  const p = a && typeof a === 'object' ? a.noul : undefined;
  if (typeof p !== 'number' || !Number.isFinite(p) || p < 0 || p > 1) throw new Error('missing or malformed answer');
  const model = typeof json.model === 'string' ? json.model : '';
  if (!model) throw new Error('response carries no model string');
  const num = (n) => (typeof n === 'number' && Number.isFinite(n) ? n : 0);
  const tin = num(json.usage?.input_tokens), tout = num(json.usage?.output_tokens);
  return { question: g.key, p, model, in: tin, out: tout, cost: tin + tout > 0 ? tin * PRICE_IN : FALLBACK_COST };
}
const readJsonl = (p) => fs.existsSync(p) ? fs.readFileSync(p, 'utf8').split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean) : [];

const rows = readJsonl(path.join(D, 'variants-x2.jsonl')).map((r, i) => ({ ...r, id: `x2:${i + 1}`, batch: 'x2' }));
const callable = rows.filter((r) => GROUPS[r.method.toUpperCase()]);
const prior = readJsonl(OUT);
const done = new Set(prior.filter((x) => typeof x.p === 'number').map((x) => x.id));
const todo = callable.filter((r) => !done.has(r.id));
let spent = prior.reduce((s, x) => s + (x.cost || 0), 0);
console.log(`rows ${rows.length}, callable ${callable.length}, done ${done.size}, todo ${todo.length}, spend $${spent.toFixed(4)}`);

if (todo.length) {
  const key = getKey();
  if (!key) throw new Error('no RWXMAP_JEV_KEY in env or rwxmap/.env');
  const fd = fs.openSync(OUT, 'a');
  const queue = [...todo].reverse();
  let stopped = false, errs = 0;
  const worker = async () => {
    while (queue.length && !stopped) {
      if (spent + RESERVE > CAP_USD) { stopped = true; console.log('SPEND GUARD'); return; }
      const r = queue.pop();
      let line;
      try { const a = await ask(key, r); line = { id: r.id, seed_id: r.seed_id, kind: r.kind, question: a.question, p: a.p, model: a.model, error: null, cost: a.cost }; }
      catch (e) { line = { id: r.id, seed_id: r.seed_id, kind: r.kind, question: GROUPS[r.method.toUpperCase()].key, p: null, model: null, error: String(e.message || e).slice(0, 200), cost: 0 }; errs++; }
      spent += line.cost || 0;
      fs.writeSync(fd, JSON.stringify(line) + '\n');
    }
  };
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  fs.closeSync(fd);
  console.log(`asked ${todo.length - queue.length}, errors this run ${errs}, spend $${spent.toFixed(4)}${stopped ? ' STOPPED' : ''}`);
}


const ans = new Map();
for (const x of readJsonl(OUT)) if (typeof x.p === 'number' || !ans.has(x.id)) ans.set(x.id, x);
const surf = rows.filter((r) => r.kind === 'surface'), pv = (r) => ans.get(r.id)?.p;
const nx = surf.filter((r) => pv(r) >= 0.5).length;
console.log(`x2 surface Jev x (p>=0.5): ${nx}/${surf.length}; unanswered ${rows.filter((r) => typeof pv(r) !== 'number').length}`);
const cw = rows.filter((r) => r.kind === 'contrast');
console.log(`x2 contrast w called x: ${cw.filter((r) => pv(r) >= 0.5).length}/${cw.length}`);
