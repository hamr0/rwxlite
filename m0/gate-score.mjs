// Label gate, scored ONCE (2026-11-03). No network. Do not re-run for tuning: this sample is burned.
//   node m0/gate-score.mjs                      -> data/gate-2026-11-03/{rulings.csv,truth.csv,score.json} (gate-1, unchanged logic)
//   node m0/gate-score.mjs --gate 2026-11-04    -> data/gate-2026-11-04/{rulings.csv,truth.csv,score.json} (gate-2, round-6 recipe)
//   --out DIR writes the outputs somewhere else (to reproduce a gate without touching its files)
// Label logic is m0/parity.mjs labelOf(): a row is only changed if it is in a Jev pile (jev_tier), by that pile's cut.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d) => (process.argv.includes(k) ? process.argv[process.argv.indexOf(k) + 1] : d);
const GATE = arg('--gate', '2026-11-03');
const G = path.join(HERE, '..', 'data', 'gate-' + GATE);
const OUT = arg('--out', G);
fs.mkdirSync(OUT, { recursive: true });
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

if (GATE === '2026-11-03') {
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
fs.writeFileSync(path.join(OUT, 'rulings.csv'), ['id,A,B,ruling,reason', ...disputes.map((id) => [id, A.get(id), B.get(id), RULING[id][0], RULING[id][1]].map(csvCell).join(','))].join('\n') + '\n');
const truthOf = new Map();
for (const b of blind) {
  const t = A.get(b.id) === B.get(b.id) ? A.get(b.id) : RULING[b.id][0];
  if (!(t in ORDER)) throw new Error('bad label ' + b.id + ' ' + t);
  truthOf.set(b.id, t);
}
if (truthOf.size !== 600) throw new Error('truth size');
fs.writeFileSync(path.join(OUT, 'truth.csv'), ['id,label', ...blind.map((b) => `${b.id},${truthOf.get(b.id)}`)].join('\n') + '\n');
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
fs.writeFileSync(path.join(OUT, 'score.json'), JSON.stringify(out, null, 1));

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

} else if (GATE === '2026-11-04') {
  await gate2();
} else throw new Error('unknown gate ' + GATE);

// ================= gate-2 (2026-11-04): round-6 recipe, scored ONCE =================
// The round-6 label function is copied VERBATIM from m0/parity.mjs (ROUND6 block: normText, NOUN, mkRe, CRED.narrow,
// credHit, label2) and labelOf (rows carry r.class / r.pC / r.p / pile as there). parity.mjs is a script with side effects
// and cannot be imported; do not edit this copy without editing parity.mjs.
async function gate2() {
  const DATA2 = path.join(HERE, '..', 'data', 'm0');
  const RULING2 = {
    'gate2-0023': ['r', 'preview, nothing billed, clause i'],
    'gate2-0146': ['w', 'plain create'],
    'gate2-0170': ['r', 'GET r unless text says change; no text'],
    'gate2-0220': ['w', 'update of a definition, can be set back'],
    'gate2-0322': ['r', 'eligibility check is a read'],
    'gate2-0336': ['w', 'create the text says nothing about'],
    'gate2-0377': ['r', 'GET, no text, name alone not evidence'],
    'gate2-0527': ['w', 'ledger adjustment undoable, not a payment'],
    'gate2-0560': ['w', 'create the text says nothing about'],
    'gate2-0593': ['w', 'PATCH w unless text names an x thing'],
  };
  const A = new Map(readCsv(path.join(G, 'labels-A.csv')).map((r) => [r.id, r.label]));
  const B = new Map(readCsv(path.join(G, 'labels-B.csv')).map((r) => [r.id, r.label]));
  const blind = readCsv(path.join(G, 'blind.csv'));
  if (blind.length !== 600) throw new Error('blind rows ' + blind.length);
  const disputes = blind.filter((b) => A.get(b.id) !== B.get(b.id)).map((b) => b.id);
  if (disputes.length !== 10 || disputes.some((d) => !RULING2[d]) || Object.keys(RULING2).some((d) => !disputes.includes(d))) throw new Error('disputes mismatch: ' + disputes);
  fs.writeFileSync(path.join(OUT, 'rulings.csv'), ['id,A,B,ruling,reason', ...disputes.map((id) => [id, A.get(id), B.get(id), RULING2[id][0], RULING2[id][1]].map(csvCell).join(','))].join('\n') + '\n');
  const truthOf = new Map();
  for (const b of blind) {
    const t = A.get(b.id) === B.get(b.id) ? A.get(b.id) : RULING2[b.id][0];
    if (!(t in ORDER)) throw new Error('bad label ' + b.id + ' ' + t);
    truthOf.set(b.id, t);
  }
  fs.writeFileSync(path.join(OUT, 'truth.csv'), ['id,label', ...blind.map((b) => `${b.id},${truthOf.get(b.id)}`)].join('\n') + '\n');
  const agree = 600 - disputes.length;

  const mech = zlib.gunzipSync(fs.readFileSync(path.join(DATA2, 'mechanical.jsonl.gz'))).toString('utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  const firstOf = new Map();
  for (const r of mech) { const k = [r.provider, r.method, r.path, r.operationId].join('\u0001'); if (!firstOf.has(k)) firstOf.set(k, r); }
  const ids = new Set(fs.readFileSync(path.join(G, 'ids.txt'), 'utf8').split('\n').filter(Boolean));
  const mp = (f) => new Map(readJsonl(path.join(DATA2, f)).filter((x) => typeof x.p === 'number').map((x) => [x.id, x.p]));
  const p1 = mp('jev-pass1.jsonl'), p2 = mp('jev-pass2.jsonl'), c1 = mp('jev-post-changes.jsonl'), c2 = mp('jev-post-changes-2.jsonl');
  const TIER2 = { 'jev-lower': 'lower', 'jev-raise-wx': 'raise-wx', 'jev-raise-get': 'raise-get' };
  const rows = blind.map((b) => {
    const m = firstOf.get([b.provider, b.method, b.path, b.operationId].join('\u0001'));
    if (!m || m.summary !== b.summary || !ids.has(m.id)) throw new Error('join failed ' + b.id);
    const a = p1.get(m.id), c = p2.get(m.id), pc = c1.get(m.id);
    const M = b.method.toUpperCase();
    return { id: b.id, ag: m.id, provider: b.provider, method: M, path: b.path, operationId: b.operationId, summary: b.summary, description: b.description, class: m.class, rule: m.rule, tier: TIER2[m.jev_tier] || 'none',
      p: a === undefined ? null : (c === undefined ? a : (a + c) / 2), pC: pc === undefined ? null : (c2.has(m.id) ? (pc + c2.get(m.id)) / 2 : pc),
      q: a === undefined ? null : (M === 'GET' ? 'changes' : 'isX'), truth: truthOf.get(b.id), exam: !!(m.exam || m.exam_opkey_overlap) };
  });
  if (rows.some((r) => r.exam)) throw new Error('exam row in gate');
  const join = { asked: rows.filter((r) => r.p !== null).length, tierWithoutP: rows.filter((r) => r.tier !== 'none' && r.p === null).length, pWithoutTier: rows.filter((r) => r.tier === 'none' && r.p !== null).length,
    lowerTierRows: rows.filter((r) => r.tier === 'lower').length, lowerTierMethods: rows.filter((r) => r.tier === 'lower').reduce((o, r) => (o[r.method] = (o[r.method] || 0) + 1, o), {}),
    lowerTierWithoutPC: rows.filter((r) => r.tier === 'lower' && r.pC === null).length, postWithPC: rows.filter((r) => r.pC !== null).length };

  // ---- labelOf (parity.mjs, pileOf = r.tier) and ROUND6 label2 / credential rule, verbatim
  const RW2 = { lower: 0.10, 'raise-wx': 0.80, 'raise-get': 0.50 };
  const PRD2 = { lower: 0.20, 'raise-wx': 0.60, 'raise-get': 0.20 };
  const pileOf = (r) => (r.tier === 'none' ? null : r.tier);
  function labelOf(r, th) {
    const t = pileOf(r);
    if (!t || r.p === null) return r.class;
    if (t === 'lower') return r.p < th.lower ? 'w' : r.class;
    if (t === 'raise-wx') return r.p >= th['raise-wx'] ? 'x' : r.class;
    return r.p >= th['raise-get'] ? 'w' : r.class;
  }
  const normText = (s) => String(s || '').replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/[^A-Za-z0-9]+/g, ' ').toLowerCase();
  const NOUN = '(?:password|passcode|passphrase|pin|pin code|auth key|authkey|api key|apikey|api secret|secret key|client secret)s?';
  const mkRe = (verbs) => new RegExp(`\\b(?:${verbs})\\b(?: \\w+){0,3}? ${NOUN}\\b(?! (?:polic|rule|requirement|complexity|setting|config))`);
  const CRED = { narrow: { re: mkRe('change|reset|rotate|regenerate|renew|revoke|invalidate|expire'), fields: ['operationId', 'summary', 'path'] } };
  const credHit = (r, v) => r.method.toUpperCase() !== 'GET' && CRED[v].fields.some((f) => CRED[v].re.test(normText(r[f])));
  const label2 = (r, th, cred) => {
    const t = pileOf(r); let l;
    if (t === 'lower' && r.p !== null && r.p < th.lower) l = r.pC !== null && r.pC !== undefined && r.pC < th.rcut ? 'r' : 'w';
    else l = labelOf(r, th);
    if (cred && credHit(r, cred)) l = 'x';
    return l;
  };
  const R6 = { ...PRD2, rcut: 0.20 };
  const bLabel = (r) => (r.p === null ? r.class : r.q === 'changes' ? (r.p >= 0.5 ? 'w' : 'r') : (r.p >= 0.5 ? 'x' : 'w'));
  const CFG = {
    i_mechanical: (r) => r.class,
    ii_round6_GATE: (r) => label2(r, R6, 'narrow'),
    iii_round5_cuts: (r) => labelOf(r, PRD2),
    iv_rwxmap_shipped: (r) => labelOf(r, RW2),
    v_modeB_p05: bLabel,
  };
  function score(rs, f) {
    const s = { n: rs.length, exact: 0, tooLoose: 0, tooTight: 0 };
    for (const r of rs) { const l = f(r); if (l === r.truth) s.exact++; else if (ORDER[l] < ORDER[r.truth]) s.tooLoose++; else s.tooTight++; }
    s.exactPct = pct(s.exact, s.n); s.tooLoosePct = pct(s.tooLoose, s.n); s.tooTightPct = pct(s.tooTight, s.n);
    return s;
  }
  const BURNED = new Set('adyen appcenter atlassian azure box clearblade dracoon gitea github gitlab jira keycloak linode microsoft netbox notion openai slack trello twilio vercel whatsapp xero zoom'.split(' '));
  const vendorDirty = (r) => String(r.provider).toLowerCase().split(/[.:]/).some((x) => BURNED.has(x));
  const lines = { all600: rows, vendorClean: rows.filter((r) => !vendorDirty(r)) };
  const groupBy = (rs, kf) => { const m = {}; for (const r of rs) (m[kf(r)] ??= []).push(r); return m; };
  const out = { generated: '2026-11-03', gate: GATE, usedOnce: true, labelAgreement: { agree, total: 600, pct: pct(agree, 600) },
    recipe: { round6: R6, round5: PRD2, rwxmapShipped: RW2, credentialRule: 'narrow (parity.mjs ROUND6)', vendorCleanExcludedNames: [...BURNED] },
    join, truthMix: Object.fromEntries(Object.entries(groupBy(rows, (r) => r.truth)).map(([k, v]) => [k, v.length])), lines: {} };
  for (const [ln, rs] of Object.entries(lines)) {
    const L = out.lines[ln] = { n: rs.length, overall: {}, byMethod: {}, byTier: {}, byMechLetter: {} };
    for (const [cn, f] of Object.entries(CFG)) {
      L.overall[cn] = score(rs, f);
      for (const [k, v] of Object.entries(groupBy(rs, (r) => r.method))) (L.byMethod[k] ??= {})[cn] = score(v, f);
      for (const [k, v] of Object.entries(groupBy(rs, (r) => r.tier))) (L.byTier[k] ??= {})[cn] = score(v, f);
      for (const [k, v] of Object.entries(groupBy(rs, (r) => r.class))) (L.byMechLetter[k] ??= {})[cn] = score(v, f);
    }
    L.modeB_askedOnly = score(rs.filter((r) => r.p !== null), bLabel);
  }
  // two-step and credential-rule effect on this set (at the round-6 cuts)
  const oneStep = (r) => labelOf(r, R6);
  const twoHits = rows.filter((r) => r.tier === 'lower' && r.p !== null && r.p < R6.lower && r.pC !== null && r.pC < R6.rcut);
  const credHits = rows.filter((r) => credHit(r, 'narrow'));
  const eff = (hs, was, now) => ({ hits: hs.length, truthMix: hs.reduce((o, r) => (o[r.truth] = (o[r.truth] || 0) + 1, o), {}), exactGained: hs.filter((r) => was(r) !== r.truth && now(r) === r.truth).length, exactLost: hs.filter((r) => was(r) === r.truth && now(r) !== r.truth).length,
    tooLooseBefore: hs.filter((r) => ORDER[was(r)] < ORDER[r.truth]).length, tooLooseAfter: hs.filter((r) => ORDER[now(r)] < ORDER[r.truth]).length, ids: hs.map((r) => r.id) });
  out.twoStep = eff(twoHits, oneStep, (r) => label2(r, R6, null));
  out.credentialRule = { ...eff(credHits, (r) => label2(r, R6, null), (r) => label2(r, R6, 'narrow')), methods: credHits.reduce((o, r) => (o[r.method] = (o[r.method] || 0) + 1, o), {}) };
  // misses of (ii), grouped by pattern
  const G2 = CFG.ii_round6_GATE;
  const misses = rows.filter((r) => G2(r) !== r.truth).map((r) => ({ id: r.id, provider: r.provider, method: r.method, path: r.path, summary: r.summary.slice(0, 100), mech: `${r.class}/${r.rule}`, tier: r.tier, p: r.p, pC: r.pC, truth: r.truth, predicted: G2(r), kind: ORDER[G2(r)] < ORDER[r.truth] ? 'too-loose' : 'too-tight' }));
  const pat = (m) => `${m.method} tier=${m.tier} mech=${m.mech.split('/')[0]} truth=${m.truth} pred=${m.predicted} (${m.kind})`;
  out.missesRound6 = misses; out.missPatterns = Object.fromEntries(Object.entries(groupBy(misses, pat)).sort((a, b) => b[1].length - a[1].length).map(([k, v]) => [k, v.length]));
  const gN = out.lines.all600.overall.ii_round6_GATE, mN = out.lines.all600.overall.i_mechanical;
  out.verdict = { gateExactPct: gN.exactPct, bar: 95, exactRows: gN.exact, tooLoose: gN.tooLoose, mechanicalTooLoose: mN.tooLoose, tooLooseNoWorseThanMechanical: gN.tooLoose <= mN.tooLoose, result: gN.exact / gN.n >= 0.95 && gN.tooLoose <= mN.tooLoose ? 'PASS' : 'FAIL' };
  // post-hoc, NOT for tuning
  const sw = { note: 'POST-HOC, NOT FOR TUNING: sample is burned; reported only to explain the gate number', perTier: {} };
  const GR = { lower: [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5], 'raise-wx': [0.5, 0.6, 0.7, 0.8, 0.9, 1.01], 'raise-get': [0.2, 0.3, 0.5, 0.8, 1.01] };
  for (const t of Object.keys(GR)) sw.perTier[t] = GR[t].map((v) => ({ cut: v, ...score(rows.filter((r) => r.tier === t), (r) => label2(r, { ...R6, [t]: v }, 'narrow')) }));
  sw.rcut = [0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.01].map((v) => ({ cut: v, ...score(rows.filter((r) => r.tier === 'lower'), (r) => label2(r, { ...R6, rcut: v }, 'narrow')) }));
  out.posthocSweepNotForTuning = sw;
  fs.writeFileSync(path.join(OUT, 'score.json'), JSON.stringify(out, null, 1));

  const J = (o) => console.log(JSON.stringify(o));
  J(out.labelAgreement); J(out.join); J(out.truthMix); J(out.verdict);
  for (const [ln, L] of Object.entries(out.lines)) {
    console.log('==', ln, L.n);
    for (const [cn, s] of Object.entries(L.overall)) console.log(' ', cn, s.n, `exact ${s.exactPct} (${s.exact}) loose ${s.tooLoosePct} (${s.tooLoose}) tight ${s.tooTightPct} (${s.tooTight})`);
    for (const key of ['byMethod', 'byTier', 'byMechLetter']) for (const [k, v] of Object.entries(L[key])) console.log(' ', key, k, Object.entries(v).map(([cn, s]) => `${cn.split('_')[0]}:${s.n}/${s.exactPct}/L${s.tooLoose}/T${s.tooTight}`).join('  '));
    J(L.modeB_askedOnly);
  }
  console.log('TWOSTEP'); J({ ...out.twoStep, ids: undefined }); console.log('CRED'); J(out.credentialRule);
  console.log('MISS PATTERNS'); J(out.missPatterns);
  console.log('MISSES', misses.length); for (const m of misses) J(m);
  console.log('POSTHOC'); for (const [t, a] of Object.entries(sw.perTier)) { console.log(' ', t); for (const s of a) console.log('   ', s.cut, s.n, s.exact, s.tooLoose, s.tooTight); }
  console.log(' rcut'); for (const s of sw.rcut) console.log('   ', s.cut, s.n, s.exact, s.tooLoose, s.tooTight);
}
