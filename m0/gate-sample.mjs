// Draws the fresh BRIEF-v3 label-gate sample (blind). Deterministic: same seed + same inputs -> same files.
//   node m0/gate-sample.mjs           -> data/gate-2026-11-03/{blind.csv,ids.txt,README.md}   (gate-1, seed 20261103)
//   node m0/gate-sample.mjs --gate 3  -> data/gate-2026-11-06/ (gate-3 for rwxmap F2: credential stratum 200 + general 600, seed 20261106; see block below)
//   node m0/gate-sample.mjs --gate 2  -> data/gate-2026-11-04/{blind.csv,ids.txt,README.md,providers.txt}   (gate-2, seed 20261104)
// Gate-2 additionally excludes every op key in gate-1's ids.txt (all snapshots).
// No network. Reads data/m0/mechanical.jsonl.gz and rwxmap truth sets in place (never written).
// blind.csv carries no mechanical letter, no Jev p, nothing hinting at a class.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GATEARG = process.argv.includes('--gate') ? process.argv[process.argv.indexOf('--gate') + 1] : '1';
const GATE2 = GATEARG === '2';
const GATE3 = GATEARG === '3';
const DIR = GATE3 ? 'gate-2026-11-06' : GATE2 ? 'gate-2026-11-04' : 'gate-2026-11-03';
const OUT = path.join(HERE, '..', 'data', DIR);
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
const D = (...p) => path.join(RWXMAP, 'data', ...p);
const SEED = GATE3 ? 20261106 : GATE2 ? 20261104 : 20261103;
const GATE1_IDS = GATE2 ? new Set(fs.readFileSync(path.join(HERE, '..', 'data', 'gate-2026-11-03', 'ids.txt'), 'utf8').split('\n').filter(Boolean)) : new Set();
const N = 600, MIN_GET = 100, MIN_PUTPATCH = 100, VENDOR_CAP = Math.floor(N * 0.05);
const EXAM_AND_LOCKED = ['cloudflare', 'pagerduty', 'sentry', 'auth0', 'hubspot', 'zendesk', 'miro', 'dropbox', 'shopify', 'linear'];
// Gate-2 amendment (rwxmap lock check): burned-exam and locked vendors are excluded BY NAME (whole domain labels of
// provider, split on '.' and ':'), not only by row. Burned exam vendors: okta, docusign, xero (exam-2026-09-17);
// klaviyo (exam-2026-09-20, plus auth0/hubspot/miro/zendesk); cloudflare, pagerduty, sentry (exam-2026-09-22).
// Locked: auth0, hubspot, zendesk, miro, dropbox, shopify, linear.
const BURNED_NAMES = ['okta', 'docusign', 'xero', 'klaviyo', 'cloudflare', 'pagerduty', 'sentry', 'auth0', 'hubspot', 'zendesk', 'miro', 'dropbox', 'shopify', 'linear'];
const byName = (provider) => String(provider || '').toLowerCase().split(/[.:]/).some((l) => BURNED_NAMES.includes(l));
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

if (GATE3) {
  const readIds = (d) => new Set(fs.readFileSync(path.join(HERE, '..', 'data', d, 'ids.txt'), 'utf8').split('\n').filter(Boolean));
  const PRIOR = new Set([...readIds('gate-2026-11-03'), ...readIds('gate-2026-11-04')]);
  const CRED = /password|passcode|\bpin\b|secret|credential|key|token|certificate|session/i;
  const x3 = { op_keys_total: groups.size, by_name: 0, exam_opkey_overlap: 0, prior_gates: 0, in_v3_truth: 0, delete: 0, head_options_trace_other: 0 };
  const el = [];
  for (const [k, rs] of groups) {
    const r = rs[0]; const m = r.method.toUpperCase(); const ok = opKey(r.method, r.path, r.operationId);
    if (byName(r.provider)) { x3.by_name++; continue; }
    if (rs.some((x) => x.exam_opkey_overlap || x.exam)) { x3.exam_opkey_overlap++; continue; }
    if (rs.some((x) => PRIOR.has(x.id))) { x3.prior_gates++; continue; }
    if (truthKeys.has(`${r.provider}|${ok}`) || truthKeys.has(`vendor:${r.vendor}|${ok}`)) { x3.in_v3_truth++; continue; }
    if (m === 'DELETE') { x3.delete++; continue; }
    if (!SAMPLED.includes(m)) { x3.head_options_trace_other++; continue; }
    el.push({ key: k, rows: rs, row: r, method: m, vendor: r.vendor });
  }
  el.sort((a, b) => (a.key < b.key ? -1 : 1));
  const rnd3 = mulberry32(SEED);
  const credPool = shuffle(el.filter((e) => ['POST', 'PUT', 'PATCH'].includes(e.method) && CRED.test(`${e.row.path} ${e.row.operationId} ${e.row.summary}`)), rnd3);
  const credAvail = Object.fromEntries(['POST', 'PUT', 'PATCH'].map((m) => [m, credPool.filter((e) => e.method === m).length]));
  const take = (pool, need, cap, vN, out) => { for (const e of pool) { if (out.length >= need) break; if ((vN[e.vendor] || 0) >= cap) continue; out.push(e); vN[e.vendor] = (vN[e.vendor] || 0) + 1; } };
  const cred = []; const cV = {};
  take(credPool.filter((e) => e.method !== 'POST'), 100, 10, cV, cred);
  const ppN = cred.length;
  take(credPool.filter((e) => e.method === 'POST'), 200, 10, cV, cred);
  const credKeys = new Set(cred.map((e) => e.key));
  const genPool = shuffle(el.filter((e) => !credKeys.has(e.key)), rnd3);
  const genAvail = Object.fromEntries(SAMPLED.map((m) => [m, genPool.filter((e) => e.method === m).length]));
  const GQ = { GET: 325, POST: 175, PUT: 50, PATCH: 50 };
  const gen = []; const gV = {}; const gM = {};
  for (const e of genPool) { if ((gM[e.method] || 0) >= GQ[e.method] || (gV[e.vendor] || 0) >= 30) continue; gen.push(e); gM[e.method] = (gM[e.method] || 0) + 1; gV[e.vendor] = (gV[e.vendor] || 0) + 1; }
  for (const m of SAMPLED) if (gM[m] !== GQ[m]) console.warn('general quota short', m, gM[m]);
  const all = shuffle([...cred.map((e) => ({ e, part: 'cred' })), ...gen.map((e) => ({ e, part: 'general' }))], rnd3);
  const rows3 = all.map((x, i) => ({ id: `gate3-${String(i + 1).padStart(4, '0')}`, ...x }));
  fs.mkdirSync(OUT, { recursive: true });
  const H3 = ['id', 'provider', 'method', 'path', 'operationId', 'summary', 'description'];
  fs.writeFileSync(path.join(OUT, 'blind.csv'), [H3.join(','), ...rows3.map(({ id, e }) => [id, e.row.provider, e.row.method, e.row.path, e.row.operationId, e.row.summary, e.row.description].map(csvCell).join(','))].join('\n') + '\n');
  fs.writeFileSync(path.join(OUT, 'part.csv'), ['id,part', ...rows3.map(({ id, part }) => `${id},${part}`)].join('\n') + '\n');
  const ids3 = rows3.flatMap(({ e }) => e.rows.map((r) => r.id)).sort();
  fs.writeFileSync(path.join(OUT, 'ids.txt'), ids3.join('\n') + '\n');
  fs.writeFileSync(path.join(OUT, 'providers.txt'), [...new Set(rows3.map(({ e }) => e.row.provider))].sort().join('\n') + '\n');
  const cm = (part) => { const m = {}; for (const x of rows3) if (x.part === part) m[x.e.method] = (m[x.e.method] || 0) + 1; return m; };
  const cv = (part) => { const m = {}; for (const x of rows3) if (x.part === part) m[x.e.vendor] = (m[x.e.vendor] || 0) + 1; return Object.entries(m).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)); };
  const tbl = (o) => Object.entries(o).map(([k, v]) => `| ${k} | ${v} |`).join('\n');
  const tv = (a) => a.slice(0, 10).map(([k, v]) => `| ${k} | ${v} |`).join('\n');
  fs.writeFileSync(path.join(OUT, 'README.md'), `# data/${DIR} — gate-3 sample for rwxmap F2 (credential-change words exam), blind

## Purpose

800 operations drawn from the 123k APIs.guru ops (\`data/m0/mechanical.jsonl.gz\`) as the exam set for rwxmap's F2
(credential-change words). This is an rwxmap exam, NOT an rwxlite exam: rwxlite's MiniLM was trained on these rows, so
scoring rwxlite on them would be contaminated.

**Used ONCE.** Never used for tuning, threshold sweeps, model selection or repeated scoring.

## Files

- \`blind.csv\`: ${H3.join(', ')}. 800 rows, ids gate3-0001..0800 assigned after one seeded shuffle of all 800, so credential-stratum rows are indistinguishable from general rows.
- \`part.csv\`: id,part (cred|general). This is the KEY saying which part a row is in. **Labellers must never see part.csv.**
- \`ids.txt\`: ${ids3.length} \`ag-\` row ids = the 800 sampled rows PLUS every APIs.guru snapshot sharing their op key (provider+method+path+operationId). Training exclusion list.
- \`providers.txt\`: sorted provider list (${new Set(rows3.map(({ e }) => e.row.provider)).size}).
- \`BRIEF-v3.md\`: byte copy of gate-2's.

## Draw

Seed ${SEED} (mulberry32), one rng stream: shuffle of the credential pool, shuffle of the general pool, then the final shuffle of all 800. Reproduce: \`node m0/gate-sample.mjs --gate 3\`.
Unit = op key (provider+method+path+operationId); one row per op key (first snapshot's text).

Eligibility (both parts): exclude op keys in data/gate-2026-11-03/ids.txt and data/gate-2026-11-04/ids.txt (any snapshot); ops in rwxmap combined-2026-09-21 and relabel-buildset-2026-09-23; exam / exam_opkey_overlap rows; HEAD/OPTIONS/TRACE; DELETE; and by whole domain label (split on "." and ":") ${BURNED_NAMES.join(' ')}.

Part 1, credential stratum (200): method in POST/PUT/PATCH AND the string (path + " " + operationId + " " + summary; description NOT used) matches, case-insensitive:

    ${CRED.toString()}

PUT+PATCH drawn first, up to 100 (got ${ppN}), then POST to fill to 200. Vendor cap 10 per vendor across the stratum.

Part 2, general (600), drawn after and never sharing an op key with Part 1: GET 325 / POST 175 / PUT 50 / PATCH 50, vendor cap 30. Vendor = first dotted token of provider.

## Exclusion counts (op keys)

Total ${x3.op_keys_total}. by-name ${x3.by_name}; exam/exam_opkey_overlap ${x3.exam_opkey_overlap}; prior gates ${x3.prior_gates}; v3 truth ${x3.in_v3_truth}; DELETE ${x3.delete}; HEAD/OPTIONS/TRACE/other ${x3.head_options_trace_other}. Eligible ${el.length}.

## Pool sizes

Credential-eligible: ${Object.entries(credAvail).map(([k, v]) => `${k} ${v}`).join(', ')}. General pool (eligible minus stratum draw): ${Object.entries(genAvail).map(([k, v]) => `${k} ${v}`).join(', ')}.

## Counts

Credential part:

| method | n |
|---|---|
${tbl(cm('cred'))}

General part:

| method | n |
|---|---|
${tbl(cm('general'))}

Top vendors, credential: ${cv('cred').slice(0, 8).map(([k, v]) => `${k} ${v}`).join(', ')}.
Top vendors, general: ${cv('general').slice(0, 8).map(([k, v]) => `${k} ${v}`).join(', ')}.
`);
  console.log(JSON.stringify({ x3, eligible: el.length, credAvail, genAvail, ppN, cm_cred: cm('cred'), cm_gen: cm('general'), topCred: cv('cred').slice(0, 6), topGen: cv('general').slice(0, 6), ids: ids3.length, providers: new Set(rows3.map(({ e }) => e.row.provider)).size }));
  process.exit(0);
}

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
// Gate-2 minimal fix: keep every retained row (and its id/position); redraw only slots whose vendor is excluded by name,
// from a second seeded shuffle (SEED+1) of the by-name-eligible pool, same method stratum, same vendor cap.
let redraw = null;
if (GATE2) {
  const keep = (e) => !byName(e.row.provider);
  const slotsOut = picked.map((e, i) => (keep(e) ? -1 : i)).filter((i) => i >= 0);
  const kept = picked.filter(keep);
  const used = new Set(picked.map((e) => e.key));
  const need = {}; for (const i of slotsOut) need[picked[i].method] = (need[picked[i].method] || 0) + 1;
  const vN = {}; for (const e of kept) vN[e.vendor] = (vN[e.vendor] || 0) + 1;
  const pool2 = shuffle(eligible.filter((e) => keep(e) && !used.has(e.key)).sort((a, b) => (a.key < b.key ? -1 : 1)), mulberry32(SEED + 1));
  const got = {};
  for (const e of pool2) {
    if ((got[e.method] || []).length >= (need[e.method] || 0) || (vN[e.vendor] || 0) >= VENDOR_CAP) continue;
    (got[e.method] ??= []).push(e); vN[e.vendor] = (vN[e.vendor] || 0) + 1;
  }
  redraw = { slotsOut, need, replaced: [] };
  for (const i of slotsOut) { const m = picked[i].method; const n = got[m]?.shift(); if (!n) throw new Error('redraw short ' + m); redraw.replaced.push({ slot: i, old: picked[i], now: n }); picked[i] = n; }
  ex.byname_replaced = slotsOut.length;
  ex.byname_eligible = eligible.filter(keep).length;
}
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
Eligible: ${ex.op_keys_eligible}.${GATE2 ? `

## Amendment: burned-exam vendors excluded by name (rwxmap lock check)

rwxmap's lock check on this gate found xero.com in the draw: xero was an exam vendor in rwxmap \`data/exam-2026-09-17\`
(with okta and docusign). rwxmap's rule is that a draw excludes prior exam vendors BY NAME, not only by row. The first
draw only excluded exam rows/op keys and cloudflare/pagerduty/sentry by first token, so xero.com (1 row) slipped in.

Fix (minimal): the original seeded draw above is unchanged; every row whose provider has a whole domain label (split on
\`.\` and \`:\`) in the burned/locked name list is dropped, and only those slots are redrawn: ${redraw.replaced.length} rows. Each new row takes
the freed id/position, comes from a second seeded shuffle (seed ${SEED + 1}, mulberry32, sorted op keys) of the by-name-eligible pool, same
method stratum (${Object.entries(redraw.need).map(([m, n]) => `${m} ${n}`).join(', ')}), same ${VENDOR_CAP}-row vendor cap, same exclusions as above
(including gate-1). All other ${N - redraw.replaced.length} rows and ids are unchanged. ids.txt and providers.txt are rewritten.
Names excluded: ${BURNED_NAMES.join(', ')}. Burned exam vendors: okta, docusign, xero (exam-2026-09-17); auth0, hubspot, klaviyo, miro, zendesk
(exam-2026-09-20); cloudflare, pagerduty, sentry (exam-2026-09-22). Locked only: dropbox, shopify, linear.
Replaced ids: ${redraw.replaced.map((r) => `gate2-${String(r.slot + 1).padStart(4, '0')}`).join(', ')} (all were xero.com, replaced in place).` : ''}

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
if (redraw) console.log('replaced', redraw.replaced.map((r) => `${r.slot + 1}:${r.old.method}:${r.old.row.provider}->${r.now.row.provider}`).join(' '));
console.log(JSON.stringify({ ex, avail, quota, nM, sample: rows.length, ids: ids.length, vendors: byVendor.length, top: byVendor.slice(0, 8) }));
