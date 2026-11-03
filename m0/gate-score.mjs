// Label gate, scored ONCE (2026-11-03). No network. Do not re-run for tuning: this sample is burned.
//   node m0/gate-score.mjs -> data/gate-2026-11-03/{rulings.csv,truth.csv,score.json} + printed summary
// Label logic is m0/parity.mjs labelOf(): a row is only changed if it is in a Jev pile (jev_tier), by that pile's cut.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const G = path.join(HERE, '..', 'data', 'gate-2026-11-03');
const DATA = path.join(HERE, '..', 'data', 'm0');
const ORDER = { r: 0, w: 1, x: 2 };
const pct = (n, d) => (d ? Math.round((1000 * n) / d) / 10 : null);

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
const readCsv = (p) => parseCsv(fs.readFileSync(p, 'utf8'));
const readJsonl = (p) => fs.readFileSync(p, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const csvCell = (v) => { const s = String(v ?? ''); return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };

// ---- 1. rulings (user, 2026-11-03) and truth
const RULING = {
  'gate-0026': ['w', 'POST list removal, re-register is one call'],
  'gate-0048': ['w', 'POST list removal, re-register is one call'],
  'gate-0037': ['w', 'restart: stop of something that can be started again'],
  'gate-0145': ['w', 'restart: stop of something that can be started again'],
  'gate-0146': ['w', 'nameserver update can be set back'],
  'gate-0191': ['w', 'create with no send named; do not infer a send'],
  'gate-0288': ['w', 'creates a job definition, text does not say it runs now'],
  'gate-0299': ['w', 'text says create entry'],
  'gate-0306': ['w', 'text says create entry'],
  'gate-0422': ['x', 'device sends support files out to vendor support'],
  'gate-0574': ['x', 'clause (b) credential change'],
  'gate-0595': ['w', 'start of something that can be stopped'],
};
const A = new Map(readCsv(path.join(G, 'labels-A.csv')).map((r) => [r.id, r.label]));
const B = new Map(readCsv(path.join(G, 'labels-B.csv')).map((r) => [r.id, r.label]));
const blind = readCsv(path.join(G, 'blind.csv'));
if (blind.length !== 600) throw new Error('blind rows ' + blind.length);
const disputes = blind.filter((b) => A.get(b.id) !== B.get(b.id)).map((b) => b.id);
if (disputes.length !== 12 || disputes.some((d) => !RULING[d]) || Object.keys(RULING).some((d) => !disputes.includes(d))) throw new Error('disputes mismatch: ' + disputes);
fs.writeFileSync(path.join(G, 'rulings.csv'), ['id,A,B,ruling,reason', ...disputes.map((id) => [id, A.get(id), B.get(id), RULING[id][0], RULING[id][1]].map(csvCell).join(','))].join('\n') + '\n');
const truthOf = new Map();
for (const b of blind) {
  const t = A.get(b.id) === B.get(b.id) ? A.get(b.id) : RULING[b.id][0];
  if (!(t in ORDER)) throw new Error('bad label ' + b.id + ' ' + t);
  truthOf.set(b.id, t);
}
if (truthOf.size !== 600) throw new Error('truth size');
fs.writeFileSync(path.join(G, 'truth.csv'), ['id,label', ...blind.map((b) => `${b.id},${truthOf.get(b.id)}`)].join('\n') + '\n');
const agree = 600 - disputes.length;

// ---- 2. join gate ids to the sampled ag- row (first snapshot of the op key, as gate-sample.mjs)
const mech = zlib.gunzipSync(fs.readFileSync(path.join(DATA, 'mechanical.jsonl.gz'))).toString('utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const firstOf = new Map();
for (const r of mech) { const k = [r.provider, r.method, r.path, r.operationId].join('\u0001'); if (!firstOf.has(k)) firstOf.set(k, r); }
const ids = new Set(fs.readFileSync(path.join(G, 'ids.txt'), 'utf8').split('\n').filter(Boolean));
const pass1 = readJsonl(path.join(DATA, 'jev-pass1.jsonl')), pass2 = readJsonl(path.join(DATA, 'jev-pass2.jsonl'));
const p1 = new Map(pass1.map((x) => [x.id, x.p])), p2 = new Map(pass2.map((x) => [x.id, x.p]));
const TIER = { 'jev-lower': 'lower', 'jev-raise-wx': 'raise-wx', 'jev-raise-get': 'raise-get' };
const rows = blind.map((b) => {
  const m = firstOf.get([b.provider, b.method, b.path, b.operationId].join('\u0001'));
  if (!m || m.summary !== b.summary || !ids.has(m.id)) throw new Error('join failed ' + b.id);
  const a = p1.get(m.id), c = p2.get(m.id);
  const p = a === undefined ? null : (c === undefined ? a : (a + c) / 2);
  const M = b.method.toUpperCase();
  return { id: b.id, ag: m.id, provider: b.provider, method: M, path: b.path, summary: b.summary, mech: m.class, rule: m.rule, tier: TIER[m.jev_tier] || 'none', p, q: p === null ? null : (M === 'GET' ? 'changes' : 'isX'), truth: truthOf.get(b.id), exam: !!(m.exam || m.exam_opkey_overlap) };
});
if (rows.some((r) => r.exam)) throw new Error('exam row in gate');
const tierNoP = rows.filter((r) => r.tier !== 'none' && r.p === null).length;
const pNoTier = rows.filter((r) => r.tier === 'none' && r.p !== null).length;

// ---- 3. label functions (labelOf from m0/parity.mjs)
const PRD = { lower: 0.20, 'raise-wx': 0.60, 'raise-get': 0.20 };
const RW = { lower: 0.10, 'raise-wx': 0.80, 'raise-get': 0.50 };
function labelOf(r, th) {
  if (r.tier === 'none' || r.p === null) return r.mech;
  if (r.tier === 'lower') return r.p < th.lower ? 'w' : r.mech;
  if (r.tier === 'raise-wx') return r.p >= th['raise-wx'] ? 'x' : r.mech;
  return r.p >= th['raise-get'] ? 'w' : r.mech;
}
// mode (b) alone: question answered at p 0.5; rows never asked keep the mechanical letter
const bLabel = (r) => (r.p === null ? r.mech : r.q === 'changes' ? (r.p >= 0.5 ? 'w' : 'r') : (r.p >= 0.5 ? 'x' : 'w'));
const CFG = { i_mechanical: (r) => r.mech, ii_prd_cuts: (r) => labelOf(r, PRD), iii_rwxmap_cuts: (r) => labelOf(r, RW), iv_modeB_p05: bLabel };
function score(rs, f) {
  const s = { n: rs.length, exact: 0, tooLoose: 0, tooTight: 0 };
  for (const r of rs) { const l = f(r); if (l === r.truth) s.exact++; else if (ORDER[l] < ORDER[r.truth]) s.tooLoose++; else s.tooTight++; }
  s.exactPct = pct(s.exact, s.n); s.tooLoosePct = pct(s.tooLoose, s.n); s.tooTightPct = pct(s.tooTight, s.n);
  return s;
}
const OVERLAP = new Set('jira.local openai.com whatsapp.local zoom.us atlassian.com box.com clearblade.com dracoon.team gitea.io github.com gitlab.com keycloak.local microsoft.com netbox.dev'.split(' '));
const lines = { all600: rows, nonOverlap: rows.filter((r) => !OVERLAP.has(r.provider)) };
const groupBy = (rs, kf) => { const m = {}; for (const r of rs) (m[kf(r)] ??= []).push(r); return m; };
const out = { generated: '2026-11-03', usedOnce: true, labelAgreement: { agree, total: 600, pct: pct(agree, 600) }, cuts: { prd: PRD, rwxmap: RW }, join: { tierWithoutP: tierNoP, pWithoutTier: pNoTier, asked: rows.filter((r) => r.p !== null).length }, truthMix: groupBy(rows, (r) => r.truth), lines: {} };
out.truthMix = Object.fromEntries(Object.entries(out.truthMix).map(([k, v]) => [k, v.length]));
for (const [ln, rs] of Object.entries(lines)) {
  const L = out.lines[ln] = { n: rs.length, overall: {}, byMethod: {}, byTier: {}, byMechLetter: {} };
  for (const [cn, f] of Object.entries(CFG)) {
    L.overall[cn] = score(rs, f);
    for (const [k, v] of Object.entries(groupBy(rs, (r) => r.method))) (L.byMethod[k] ??= {})[cn] = score(v, f);
    for (const [k, v] of Object.entries(groupBy(rs, (r) => r.tier))) (L.byTier[k] ??= {})[cn] = score(v, f);
    for (const [k, v] of Object.entries(groupBy(rs, (r) => r.mech))) (L.byMechLetter[k] ??= {})[cn] = score(v, f);
  }
  const asked = rs.filter((r) => r.p !== null);
  L.modeB_askedOnly = score(asked, bLabel);
}
const misses = rows.filter((r) => CFG.ii_prd_cuts(r) !== r.truth).map((r) => ({ id: r.id, provider: r.provider, method: r.method, path: r.path, summary: r.summary.slice(0, 100), mech: `${r.mech}/${r.rule}`, tier: r.tier, p: r.p, truth: r.truth, predicted: CFG.ii_prd_cuts(r), kind: ORDER[CFG.ii_prd_cuts(r)] < ORDER[r.truth] ? 'too-loose' : 'too-tight' }));
out.missesPrdCuts = misses;
const gateNum = out.lines.all600.overall.ii_prd_cuts, mechNum = out.lines.all600.overall.i_mechanical;
out.verdict = { gateExactPct: gateNum.exactPct, bar: 95, tooLoose: gateNum.tooLoose, mechanicalTooLoose: mechNum.tooLoose, tooLooseNoWorseThanMechanical: gateNum.tooLoose <= mechNum.tooLoose, result: gateNum.exact / gateNum.n >= 0.95 ? 'PASS' : 'FAIL' };

// post-hoc, NOT for tuning: sweep of the three cuts on this set, global
const GRID = { lower: [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5], 'raise-wx': [0.5, 0.6, 0.7, 0.8, 0.9, 1.01], 'raise-get': [0.2, 0.3, 0.5, 0.8, 1.01] };
const sw = { note: 'POST-HOC, NOT FOR TUNING: sample is burned; reported only to explain the gate number', perTier: {} };
for (const t of Object.keys(GRID)) sw.perTier[t] = GRID[t].map((v) => { const s = score(rows.filter((r) => r.tier === t), (r) => labelOf(r, { ...PRD, [t]: v })); return { cut: v, ...s }; });
out.posthocSweepNotForTuning = sw;
fs.writeFileSync(path.join(G, 'score.json'), JSON.stringify(out, null, 1));

const J = (o) => console.log(JSON.stringify(o));
J(out.labelAgreement); J(out.join); J(out.truthMix); J(out.verdict);
for (const [ln, L] of Object.entries(out.lines)) {
  console.log('==', ln, L.n);
  for (const [cn, s] of Object.entries(L.overall)) console.log(' ', cn, s.n, `exact ${s.exactPct} loose ${s.tooLoosePct} (${s.tooLoose}) tight ${s.tooTightPct} (${s.tooTight})`);
  for (const key of ['byMethod', 'byTier', 'byMechLetter']) for (const [k, v] of Object.entries(L[key])) console.log(' ', key, k, Object.entries(v).map(([cn, s]) => `${cn.split('_')[0]}:${s.n}/${s.exactPct}/L${s.tooLoose}/T${s.tooTight}`).join('  '));
  J(L.modeB_askedOnly);
}
console.log('MISSES', misses.length); for (const m of misses) J(m);
console.log('POSTHOC'); for (const [t, a] of Object.entries(sw.perTier)) { console.log(' ', t); for (const s of a) console.log('   ', s.cut, s.n, s.exact, s.tooLoose, s.tooTight); }
