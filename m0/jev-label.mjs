// Module 0, step 2: the paid Jev labelling pass.
//
//   node m0/jev-label.mjs --smoke    30 rows (10 per method group) -> data/m0/jev-smoke.jsonl
//   node m0/jev-label.mjs            pass 1  -> data/m0/jev-pass1.jsonl
//   node m0/jev-label.mjs --reask    pass 2  -> data/m0/jev-pass2.jsonl (rows with 0.1 <= p <= 0.9)
//   node m0/jev-label.mjs --question changes --methods POST [--smoke|--reask]
//       round 6: the "changes" question on every non-DELETE POST row
//       -> data/m0/jev-post-changes.jsonl (smoke: jev-post-changes-smoke.jsonl; --reask: jev-post-changes-2.jsonl)
//
// Resumable: ids already answered (p present) in the output file are skipped.
// Output lines: { id, question, p, model, error, in, out, cost }. Gitignored (data/).
//
// Questions: m0/questions/*.mjs are byte copies of rwxmap poc/jev-tiers/* at
// commit a7bc855. NEVER take questions from rwxmap src/jev.js at <= v0.8.0.
//   POST -> isX (criteria-x)   PUT/PATCH -> isX (criteria-x-raise)   GET -> changes
// DELETE, HEAD, OPTIONS, TRACE: no Jev call (DELETE keeps mechanical x).
// State sent = method, path, operationId, summary, description, nothing else.
//
// Spend guard: stops cleanly before cumulative spend (smoke + pass1 + pass2
// files together) would exceed CAP_USD. The key is never printed or logged.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import os from 'node:os';
import readline from 'node:readline';
import { parseEnv } from 'node:util';
import { fileURLToPath } from 'node:url';
import * as qX from './questions/criteria-x.mjs';
import * as qXRaise from './questions/criteria-x-raise.mjs';
import * as qChanges from './questions/criteria-changes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(HERE, '..', 'data', 'm0');
const IN = path.join(DATA, 'mechanical.jsonl.gz');
const ENDPOINT = 'https://api.typesafe.ai/v1/systemone';
const CAP_USD = 45;
const PRICE_IN = 42 / 1e9; // $ per input token (jev-learnings.md)
const PRICE_OUT = 0; // output tokens not billed per the learnings; tracked anyway
const FALLBACK_COST = 0.000085; // $ per answer when tokens are not returned
const RESERVE = 4 * 0.0003; // headroom for in-flight calls
const CONCURRENCY = Number(process.env.JEV_CONCURRENCY) || 4;
const TIMEOUT_MS = 30_000;
const MAX_RETRIES = 5;

const EXAM = new Set(['cloudflare', 'pagerduty', 'sentry']);
const LOCKED = new Set(['auth0', 'cloudflare', 'hubspot', 'zendesk', 'pagerduty', 'dropbox', 'shopify', 'linear', 'miro', 'sentry']);
const first = (s) => String(s || '').toLowerCase().split(/[.:]/)[0];
const isBanned = (r) => [r.provider, r.api_key].some((v) => LOCKED.has(first(v)) || EXAM.has(first(v)));

const GROUPS = {
  POST: { key: 'isX', q: qX, name: 'post-isX' },
  PUT: { key: 'isX', q: qXRaise, name: 'putpatch-isX' },
  PATCH: { key: 'isX', q: qXRaise, name: 'putpatch-isX' },
  GET: { key: 'changes', q: qChanges, name: 'get-changes' },
};

function getKey() {
  if (process.env.RWXMAP_JEV_KEY) return process.env.RWXMAP_JEV_KEY;
  const envPath = path.join(os.homedir(), 'PycharmProjects', 'rwxmap', '.env');
  try { return parseEnv(fs.readFileSync(envPath, 'utf8')).RWXMAP_JEV_KEY || ''; } catch { return ''; }
}

async function postOnce(key, body, attempt = 0) {
  let res;
  try {
    res = await fetch(ENDPOINT, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
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
  const cost = tin + tout > 0 ? tin * PRICE_IN + tout * PRICE_OUT : FALLBACK_COST;
  return { question: g.key, p, model, in: tin, out: tout, cost };
}

function readJsonl(p) {
  if (!fs.existsSync(p)) return [];
  return fs.readFileSync(p, 'utf8').split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
}

async function loadRows() {
  const rows = [];
  const rl = readline.createInterface({ input: fs.createReadStream(IN).pipe(zlib.createGunzip()) });
  for await (const l of rl) if (l) rows.push(JSON.parse(l));
  return rows;
}

async function main() {
  const smoke = process.argv.includes('--smoke');
  const reask = process.argv.includes('--reask');
  const argv = process.argv;
  const qArg = argv.includes('--question') ? argv[argv.indexOf('--question') + 1] : null;
  const mArg = argv.includes('--methods') ? argv[argv.indexOf('--methods') + 1] : null;
  const postChanges = qArg === 'changes' && mArg === 'POST';
  if (qArg || mArg) { if (!postChanges) throw new Error('only --question changes --methods POST is supported'); GROUPS.POST = { key: 'changes', q: qChanges, name: 'post-changes' }; }
  const outName = postChanges ? (smoke ? 'jev-post-changes-smoke.jsonl' : reask ? 'jev-post-changes-2.jsonl' : 'jev-post-changes.jsonl') : smoke ? 'jev-smoke.jsonl' : reask ? 'jev-pass2.jsonl' : 'jev-pass1.jsonl';
  const OUT = path.join(DATA, outName);

  const all = await loadRows();
  const skipped = { exam_vendor_or_locked: 0, exam_opkey_overlap: 0, delete: 0, other_method: {} };
  let rows = [];
  for (const r of all) {
    if (isBanned(r) || r.exam) { skipped.exam_vendor_or_locked++; continue; }
    if (r.exam_opkey_overlap) { skipped.exam_opkey_overlap++; continue; }
    const m = r.method.toUpperCase();
    if (m === 'DELETE') { skipped.delete++; continue; }
    if (postChanges && m !== 'POST') { continue; }
    if (!GROUPS[m]) { skipped.other_method[m] = (skipped.other_method[m] || 0) + 1; continue; }
    rows.push(r);
  }
  // Re-assert: nothing banned may reach a paid call.
  if (rows.some((r) => isBanned(r) || r.exam || r.exam_opkey_overlap)) throw new Error('banned row in send list');
  console.log('skipped (no Jev call):', JSON.stringify(skipped), '| to ask:', rows.length);

  if (reask) {
    const p1 = new Map(readJsonl(path.join(DATA, postChanges ? 'jev-post-changes.jsonl' : 'jev-pass1.jsonl')).filter((x) => typeof x.p === 'number').map((x) => [x.id, x.p]));
    rows = rows.filter((r) => { const p = p1.get(r.id); return p !== undefined && p >= 0.1 && p <= 0.9; });
    console.log('re-ask rows (0.1 <= p <= 0.9):', rows.length);
  }
  if (smoke) {
    const per = {};
    rows = rows.filter((r) => {
      const g = GROUPS[r.method.toUpperCase()].name;
      per[g] = per[g] || 0;
      if (r.id.slice(-1) !== '7' || per[g] >= (postChanges ? 20 : 10)) return false;
      per[g]++;
      return true;
    });
  }

  const done = new Set(readJsonl(OUT).filter((x) => typeof x.p === 'number').map((x) => x.id));
  const todo = rows.filter((r) => !done.has(r.id));
  let spent = 0;
  for (const f of ['jev-smoke.jsonl', 'jev-pass1.jsonl', 'jev-pass2.jsonl', 'jev-post-changes-smoke.jsonl', 'jev-post-changes.jsonl', 'jev-post-changes-2.jsonl']) for (const x of readJsonl(path.join(DATA, f))) spent += x.cost || 0;
  console.log(`${outName}: ${rows.length} rows, ${done.size} done, ${todo.length} todo; spend so far $${spent.toFixed(4)} (cap $${CAP_USD})`);

  const key = getKey();
  if (!key) throw new Error('no RWXMAP_JEV_KEY in env or rwxmap/.env');

  const fd = fs.openSync(OUT, 'a');
  const t0 = Date.now();
  let n = 0, errs = 0, stopped = false, tok = 0;
  const queue = [...todo].reverse();
  async function worker() {
    while (queue.length && !stopped) {
      if (spent + RESERVE > CAP_USD) { stopped = true; console.log(`SPEND GUARD: stopping at $${spent.toFixed(4)}`); return; }
      const r = queue.pop();
      let line;
      try { line = { id: r.id, ...(await ask(key, r)), error: null }; }
      catch (e) { line = { id: r.id, question: GROUPS[r.method.toUpperCase()].key, p: null, model: null, error: String(e.message || e).slice(0, 200), cost: 0 }; errs++; }
      spent += line.cost || 0; tok += line.in || 0;
      fs.writeSync(fd, JSON.stringify(line) + '\n');
      n++;
      if (n % 500 === 0 || n === todo.length) {
        const mins = (Date.now() - t0) / 60000;
        console.log(`${n}/${todo.length} errors ${errs} (${(100 * errs / n).toFixed(1)}%) ${(n / mins).toFixed(0)} rows/min cost $${spent.toFixed(4)} eta ${((todo.length - n) / (n / mins)).toFixed(0)} min`);
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  fs.closeSync(fd);
  console.log(`finished: ${n} asked, ${errs} errors, ${tok} input tokens, spend $${spent.toFixed(4)}${stopped ? ' (STOPPED by guard)' : ''}`);
}
main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
