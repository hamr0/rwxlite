// Draws the fresh BRIEF-v3 label-gate sample (blind). Deterministic: same seed + same inputs -> same files.
//   node m0/gate-sample.mjs           -> data/gate-2026-11-03/{blind.csv,ids.txt,README.md}   (gate-1, seed 20261103)
//   node m0/gate-sample.mjs --gate 2  -> data/gate-2026-11-04/{blind.csv,ids.txt,README.md,providers.txt}   (gate-2, seed 20261104)
// Gate-2 additionally excludes every op key in gate-1's ids.txt (all snapshots).
// No network. Reads data/m0/mechanical.jsonl.gz and rwxmap truth sets in place (never written).
// blind.csv carries no mechanical letter, no Jev p, nothing hinting at a class.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GATE2 = process.argv.includes('--gate') && process.argv[process.argv.indexOf('--gate') + 1] === '2';
const DIR = GATE2 ? 'gate-2026-11-04' : 'gate-2026-11-03';
const OUT = path.join(HERE, '..', 'data', DIR);
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
const D = (...p) => path.join(RWXMAP, 'data', ...p);
const SEED = GATE2 ? 20261104 : 20261103;
const GATE1_IDS = GATE2 ? new Set(fs.readFileSync(path.join(HERE, '..', 'data', 'gate-2026-11-03', 'ids.txt'), 'utf8').split('\n').filter(Boolean)) : new Set();
const N = 600, MIN_GET = 100, MIN_PUTPATCH = 100, VENDOR_CAP = Math.floor(N * 0.05);
const EXAM_AND_LOCKED = ['cloudflare', 'pagerduty', 'sentry', 'auth0', 'hubspot', 'zendesk', 'miro', 'dropbox', 'shopify', 'linear'];
const SAMPLED = ['GET', 'POST', 'PUT', 'PATCH'];
const first = (s) => String(s || '').toLowerCase().split(/[.:]/)[0];
const opKey = (m, p, o) => `${String(m).toUpperCase()}|${p}|${o}`;
const PMAP = { stripe: 'stripe.com', openai: 'openai.com', square: 'squareup.com', zoom: 'zoom.us', 'meta-whatsapp': 'whatsapp.local', spotify: 'spotify.com', digitalocean: 'digitalocean.com', jira: 'jira.local', asana: 'asana.com', okta: 'okta.local', docusign: 'docusign.net', xero: 'xero.com' };

function parseCsv(text) {
  const rows = []; let row = []; let f = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; }
    else if (c !== '\r') f += c;
  }
  if (f !== '' || row.length) { row.push(f); rows.push(row); }
  const h = rows[0];
  return rows.slice(1).filter((r) => !(r.length === 1 && r[0] === '')).map((r) => { const o = {}; h.forEach((k, i) => { o[k] = r[i] ?? ''; }); return o; });
}
const csvCell = (v) => { const s = String(v ?? ''); return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
function mulberry32(a) { return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function shuffle(arr, rnd) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }

const mech = zlib.gunzipSync(fs.readFileSync(path.join(HERE, '..', 'data', 'm0', 'mechanical.jsonl.gz'))).toString('utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const ex = { total: mech.length, exam_vendor: 0, locked_vendor: 0, exam_opkey_overlap: 0, in_v3_truth: 0, gate1: 0, head_options_trace_other: 0, delete: 0 };

// ops already in any v3 truth set (provider-matched, as m0/parity.mjs joins them)
const truthKeys = new Set();
for (const t of parseCsv(fs.readFileSync(D('combined-2026-09-21', 'labelled.csv'), 'utf8'))) { const mp = PMAP[t.provider]; if (mp) truthKeys.add(`${mp}|${opKey(t.method, t.path, t.operationId)}`); }
for (const t of parseCsv(fs.readFileSync(D('relabel-buildset-2026-09-23', 'labelled.csv'), 'utf8'))) truthKeys.add(`vendor:${t.provider}|${opKey(t.method, t.path, t.operationId)}`);

const groups = new Map(); // op key (provider+method+path+operationId) -> all snapshot rows
for (const r of mech) r.vendor = first(r.provider);
for (const r of mech) { const k = `${r.provider}|${opKey(r.method, r.path, r.operationId)}`; (groups.get(k) ?? groups.set(k, []).get(k)).push(r); }

const eligible = [];
for (const [k, rows] of groups) {
  const r = rows[0]; const m = r.method.toUpperCase();
  if (rows.some((x) => x.exam) || r.vendor === 'cloudflare' || r.vendor === 'pagerduty' || r.vendor === 'sentry') { ex.exam_vendor++; continue; }
  if (EXAM_AND_LOCKED.includes(r.vendor)) { ex.locked_vendor++; continue; }
  if (rows.some((x) => x.exam_opkey_overlap)) { ex.exam_opkey_overlap++; continue; }
  if (rows.some((x) => GATE1_IDS.has(x.id))) { ex.gate1++; continue; }
  const ok = opKey(r.method, r.path, r.operationId);
  if (truthKeys.has(`${r.provider}|${ok}`) || truthKeys.has(`vendor:${r.vendor}|${ok}`)) { ex.in_v3_truth++; continue; }
  if (m === 'DELETE') { ex.delete++; continue; }
  if (!SAMPLED.includes(m)) { ex.head_options_trace_other++; continue; }
  eligible.push({ key: k, rows, row: rows[0], method: m, vendor: r.vendor });
}
ex.op_keys_total = groups.size; ex.op_keys_eligible = eligible.length;

const rnd = mulberry32(SEED);
const pool = shuffle(eligible.sort((a, b) => (a.key < b.key ? -1 : 1)), rnd);
const avail = Object.fromEntries(SAMPLED.map((m) => [m, eligible.filter((e) => e.method === m).length]));
const total = Object.values(avail).reduce((a, b) => a + b, 0);
// quotas: proportional to availability, floors for GET and PUT+PATCH
const quota = Object.fromEntries(SAMPLED.map((m) => [m, Math.round((N * avail[m]) / total)]));
const floorFix = () => {
  if (quota.GET < MIN_GET) quota.GET = MIN_GET;
  const pp = quota.PUT + quota.PATCH;
  if (pp < MIN_PUTPATCH) { const need = MIN_PUTPATCH - pp; const sp = quota.PUT / Math.max(1, pp); quota.PUT += Math.round(need * sp); quota.PATCH += need - Math.round(need * sp); }
  let over = SAMPLED.reduce((s, m) => s + quota[m], 0) - N;
  while (over > 0) { quota.POST--; over--; }
};
floorFix();
const picked = []; const nM = {}; const nV = {};
for (const e of pool) {
  if ((nM[e.method] || 0) >= quota[e.method] || (nV[e.vendor] || 0) >= VENDOR_CAP) continue;
  picked.push(e); nM[e.method] = (nM[e.method] || 0) + 1; nV[e.vendor] = (nV[e.vendor] || 0) + 1;
}
const short = SAMPLED.filter((m) => (nM[m] || 0) < quota[m]);
if (short.length) console.warn('quota short for', short, nM, quota);

// blind order: pool is already seeded-shuffled; picked keeps that order. Ids gate-0001..
const rows = picked.map((e, i) => ({ id: `${GATE2 ? 'gate2' : 'gate'}-${String(i + 1).padStart(4, '0')}`, e }));
fs.mkdirSync(OUT, { recursive: true });
const H = ['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'];
fs.writeFileSync(path.join(OUT, 'blind.csv'), [H.join(','), ...rows.map(({ id, e }) => [id, e.row.provider, e.row.method, e.row.path, e.row.operationId, e.row.summary, e.row.description].map(csvCell).join(','))].join('\n') + '\n');
const ids = rows.flatMap(({ e }) => e.rows.map((r) => r.id)).sort();
fs.writeFileSync(path.join(OUT, 'ids.txt'), ids.join('\n') + '\n');

const cnt = (f) => { const m = {}; for (const { e } of rows) m[f(e)] = (m[f(e)] || 0) + 1; return Object.entries(m).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)); };
const byMethod = cnt((e) => e.method), byVendor = cnt((e) => e.vendor);
const fmt = (a) => a.map(([k, v]) => `| ${k} | ${v} |`).join('\n');
fs.writeFileSync(path.join(OUT, 'README.md'), `# data/${DIR} — fresh BRIEF-v3 label-gate sample (blind)

## What this is

${rows.length} operations drawn from the 123k APIs.guru ops (\`data/m0/mechanical.jsonl.gz\`) to measure the 95% label gate
(PRD, Step 4) on data nobody has labelled or trained on. Two blind labellers (Claude workers) label \`blind.csv\`
under \`BRIEF-v3.md\` (this directory; byte-identical copy of rwxmap \`data/relabel-2026-09-22/BRIEF-v3.md\`,
rwxmap commit 4143b6d26d69e9177f15f4913c3613a0a361724c, the last commit touching it). The user rules disputes.

**Used ONCE.** This sample is the label gate and nothing else. It is never used for tuning, threshold sweeps, model
selection or any repeated scoring. After the gate it is burned. Nothing is scored on the exam until the gate passes.

## Files

- \`blind.csv\`: ${H.join(', ')}. Shuffled order. No mechanical letter, no Jev p, no class hint of any kind.
- \`ids.txt\`: ${ids.length} \`ag-\` row ids = the ${rows.length} sampled rows PLUS every APIs.guru snapshot sharing their
  op key (provider+method+path+operationId). This is the training exclusion list: none of these may enter training or tuning.
- \`BRIEF-v3.md\`: the only label standard.
- Truth comes from the labellers later. There is no key here.

## Draw

- Seed: ${SEED} (mulberry32; sort op keys, one Fisher-Yates shuffle, take in order subject to quotas). \`node m0/gate-sample.mjs${GATE2 ? ' --gate 2' : ''}\` reproduces these files byte for byte.
- Unit = op key (provider+method+path+operationId); one row per op key (first snapshot's text).
- Quotas (GET/POST/PUT/PATCH): ${SAMPLED.map((m) => `${m} ${quota[m]}`).join(', ')}. Proportional to availability, with at least ${MIN_GET} GET and ${MIN_PUTPATCH} PUT+PATCH.
- Vendor cap: ${VENDOR_CAP} rows per vendor (5% of ${N}); vendor = first dotted token of provider.

## Exclusions (op keys)

Total op keys: ${ex.op_keys_total} (from ${ex.total} rows). Excluded, in order: exam vendors (cloudflare, pagerduty, sentry) ${ex.exam_vendor};
the other 7 locked vendors (auth0, hubspot, zendesk, dropbox, shopify, linear, miro) ${ex.locked_vendor}; exam_opkey_overlap ${ex.exam_opkey_overlap};
already in a v3 truth set (combined-2026-09-21, relabel-buildset-2026-09-23) ${ex.in_v3_truth};${GATE2 ? ` already in gate-1 (any snapshot of an op key in data/gate-2026-11-03/ids.txt) ${ex.gate1};` : ''} DELETE ${ex.delete}; HEAD/OPTIONS/TRACE/other ${ex.head_options_trace_other}.
Eligible: ${ex.op_keys_eligible}.

## Counts

| method | n |
|---|---|
${fmt(byMethod)}

| vendor | n |
|---|---|
${fmt(byVendor.slice(0, 15))}

(${byVendor.length} vendors in all.)
`);
if (GATE2) fs.writeFileSync(path.join(OUT, 'providers.txt'), [...new Set(rows.map(({ e }) => e.row.provider))].sort().join('\n') + '\n');
console.log(JSON.stringify({ ex, avail, quota, nM, sample: rows.length, ids: ids.length, vendors: byVendor.length, top: byVendor.slice(0, 8) }));
