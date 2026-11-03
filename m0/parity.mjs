// Module 0, step 3: wobble stats, parity report, >=95% label gate. No network.
//   node m0/parity.mjs   -> data/m0/parity-report.json + printed summary
// Reads data/m0/mechanical.jsonl.gz, jev-pass1.jsonl, jev-pass2.jsonl and
// rwxmap's hand labels / calibration labels (read in place, never written).
// The exam (rwxmap data/exam-2026-09-22) is never read here.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(HERE, '..', 'data', 'm0');
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
const D = (...p) => path.join(RWXMAP, 'data', ...p);
const ORDER = { r: 0, w: 1, x: 2 };
const first = (s) => String(s || '').toLowerCase().split(/[.:]/)[0];
const opKey = (m, p, o) => `${String(m).toUpperCase()}|${p}|${o}`;

// rwxmap thresholds (src/jev.js a7bc855)
const RW = { lower: 0.10, 'raise-wx': 0.80, 'raise-get': 0.50 };
const TIER = { 'jev-lower': 'lower', 'jev-raise-wx': 'raise-wx', 'jev-raise-get': 'raise-get' };

// ---- csv
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
const pct = (n, d) => (d ? Math.round((1000 * n) / d) / 10 : null);

// ---- load
const mech = zlib.gunzipSync(fs.readFileSync(path.join(DATA, 'mechanical.jsonl.gz'))).toString('utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const byId = new Map(mech.map((r) => [r.id, r]));
const pass1 = readJsonl(path.join(DATA, 'jev-pass1.jsonl'));
const pass2 = readJsonl(path.join(DATA, 'jev-pass2.jsonl'));
const checks = {
  pass1_rows: pass1.length, pass2_rows: pass2.length,
  errors: [...pass1, ...pass2].filter((x) => x.error || typeof x.p !== 'number').length,
  models: [...new Set([...pass1, ...pass2].map((x) => x.model))],
  spend_usd: Math.round([...pass1, ...pass2].reduce((s, x) => s + (x.cost || 0), 0) * 100) / 100,
  dup_ids_pass1: pass1.length - new Set(pass1.map((x) => x.id)).size,
};
const p1 = new Map(pass1.map((x) => [x.id, x.p]));
const p2 = new Map(pass2.map((x) => [x.id, x.p]));
for (const id of [...p1.keys(), ...p2.keys()]) if (!byId.has(id)) throw new Error('unknown id ' + id);
if ([...p1.keys()].some((id) => byId.get(id).exam || byId.get(id).exam_opkey_overlap)) throw new Error('exam row has a Jev p');

// attach p
for (const r of mech) {
  const a = p1.get(r.id);
  r.vendor = first(r.provider);
  r.q = null; r.p = null; r.pA = null; r.pB = null;
  if (a !== undefined) {
    r.pA = a; r.pB = p2.get(r.id) ?? null;
    r.p = r.pB === null ? a : (a + r.pB) / 2;
    r.q = r.method.toUpperCase() === 'GET' ? 'changes' : 'isX';
  }
  r.noDesc = !String(r.description || '').trim();
}
const asked = mech.filter((r) => r.p !== null);

// the cut that matters for a row, from its mechanical letter
const cutFor = (r) => (r.q === 'changes' ? RW['raise-get'] : r.class === 'x' ? RW.lower : r.class === 'w' ? RW['raise-wx'] : RW['raise-get']);
// hypothetical disagreement of Jev with the mechanical letter (rwxmap thresholds)
function disagrees(r, th = RW) {
  if (r.q === 'changes') return r.class === 'r' ? r.p >= th['raise-get'] : r.p < th['raise-get'];
  if (r.class === 'x') return r.p < th.lower;
  if (r.class === 'w') return r.p >= th['raise-wx'];
  return r.p >= th['raise-wx'];
}

// ---- 1. wobble
const wob = { rows: 0, diffs: { identical: 0 } };
const reRows = asked.filter((r) => r.pB !== null);
const buckets = [[0, 0, 'equal'], [0, 0.02, '0-0.02'], [0.02, 0.05, '0.02-0.05'], [0.05, 0.1, '0.05-0.10'], [0.1, 0.2, '0.10-0.20'], [0.2, 1.01, '>=0.20']];
wob.rows = reRows.length;
wob.absDiffBuckets = {};
for (const r of reRows) {
  const d = Math.round(Math.abs(r.pA - r.pB) * 1e6) / 1e6;
  const b = d === 0 ? 'equal' : buckets.slice(1).find(([lo, hi]) => d > lo && d <= hi)?.[2] ?? '>=0.20';
  wob.absDiffBuckets[b] = (wob.absDiffBuckets[b] || 0) + 1;
}
const ds = reRows.map((r) => Math.abs(r.pA - r.pB)).sort((a, b) => a - b);
wob.meanAbsDiff = Math.round(1e4 * ds.reduce((s, x) => s + x, 0) / ds.length) / 1e4;
wob.median = ds[ds.length >> 1]; wob.p90 = ds[Math.floor(ds.length * 0.9)]; wob.max = ds[ds.length - 1];
wob.pctDifferent = pct(ds.filter((d) => d > 1e-9).length, ds.length);
// a "cross" = pA and pB fall on different sides of the cut (>= cut counts as above)
const crossAt = (r, c) => (r.pA >= c) !== (r.pB >= c);
wob.cross = { 'all rows at 0.10': 0, 'all rows at 0.50': 0, 'all rows at 0.80': 0, 'row own cut (rwxmap)': 0 };
wob.crossByGroup = {};
for (const r of reRows) {
  for (const c of [0.1, 0.5, 0.8]) if (crossAt(r, c)) wob.cross[`all rows at ${c.toFixed(2)}`]++;
  const own = crossAt(r, cutFor(r)); if (own) wob.cross['row own cut (rwxmap)']++;
  const g = `${r.method.toUpperCase()}/${r.class}/${r.rule}`;
  wob.crossByGroup[g] ??= { reasked: 0, own_cut_cross: 0 };
  wob.crossByGroup[g].reasked++; if (own) wob.crossByGroup[g].own_cut_cross++;
}
wob.rwxmap_reference = '200 rows twice -> 114 differed (largest gap 0.08)';

// ---- 2. parity report
const pileOf = (r) => TIER[r.jev_tier] || null;
const hist = (rows) => { const h = Array(10).fill(0); for (const r of rows) h[Math.min(9, Math.floor(r.p * 10))]++; return h; };
const summarise = (rows) => {
  const d = rows.filter((r) => disagrees(r)).length;
  return { n: rows.length, disagree: d, rate: pct(d, rows.length), hist: hist(rows) };
};
const group = (rows, kf) => { const m = new Map(); for (const r of rows) { const k = kf(r); if (!m.has(k)) m.set(k, []); m.get(k).push(r); } return m; };
const parity = { piles: {}, outsidePiles: {}, byRule: {}, byVendor: [], noDescription: {} };
for (const [name, rows] of group(asked.filter(pileOf), pileOf)) parity.piles[name] = summarise(rows);
parity.piles['(all piles)'] = summarise(asked.filter(pileOf));
for (const [k, rows] of group(asked.filter((r) => !pileOf(r)), (r) => `${r.method.toUpperCase()} ${r.class}/${r.rule}`)) parity.outsidePiles[k] = summarise(rows);
for (const [k, rows] of group(asked, (r) => `${r.method.toUpperCase()} ${r.class}/${r.rule}${pileOf(r) ? '' : ' (outside pile)'}`)) parity.byRule[k] = summarise(rows);
const vend = [...group(asked, (r) => r.provider)].map(([v, rows]) => ({ vendor: v, ...summarise(rows) })).filter((v) => v.n >= 50);
parity.vendorsWithMin50 = vend.length;
parity.byVendor = {
  topByCount: [...vend].sort((a, b) => b.disagree - a.disagree).slice(0, 25).map(({ hist: _h, ...v }) => v),
  topByRate: [...vend].sort((a, b) => b.rate - a.rate || b.n - a.n).slice(0, 25).map(({ hist: _h, ...v }) => v),
};
const nd = asked.filter((r) => r.noDesc), wd = asked.filter((r) => !r.noDesc);
const centrality = (rows) => ({ n: rows.length, meanAbsFromCut: Math.round(1e3 * rows.reduce((s, r) => s + Math.abs(r.p - cutFor(r)), 0) / rows.length) / 1e3, shareP01to09: pct(rows.filter((r) => r.p >= 0.1 && r.p <= 0.9).length, rows.length), disagreeRate: pct(rows.filter((r) => disagrees(r)).length, rows.length) });
parity.noDescription = { without: centrality(nd), with: centrality(wd), allRowsWithoutDescriptionInCorpus: mech.filter((r) => r.noDesc).length };

// ---- 3. gate
const hand = new Map(readCsv(D('corpus', 'labelled.csv')).map((r) => [`${first(r.repo)}|${opKey(r.method, r.path, r.operationId)}`, r.gt_class]));
const calibTruth = {};
for (const c of ['A', 'B', 'C']) {
  const blind = readCsv(D('calibration-2026-09-14', `calib${c}-blind.csv`));
  const lab = new Map(readCsv(D('calibration-2026-09-14', `calib${c}-labels.csv`)).map((r) => [r.row_id, r.truth_class]));
  for (const b of blind) calibTruth[`${b.provider}|${opKey(b.method, b.path, b.operationId)}`] = lab.get(b.row_id);
}
const gateAll = [];
const drops = { exam_vendor: 0, exam_opkey_overlap: 0, bad_label: 0 };
for (const r of mech) {
  if (!r.hand_set && !r.calib_set) continue;
  if (r.exam) { drops.exam_vendor++; continue; }
  if (r.exam_opkey_overlap) { drops.exam_opkey_overlap++; continue; }
  const h = r.hand_set ? hand.get(`${r.vendor}|${opKey(r.method, r.path, r.operationId)}`) : undefined;
  const c = r.calib_set ? calibTruth[`${r.provider}|${opKey(r.method, r.path, r.operationId)}`] : undefined;
  const truth = h ?? c;
  if (!(truth in ORDER)) { drops.bad_label++; continue; }
  gateAll.push({ ...r, truth, src: h ? 'hand_set' : 'calib_set', both: !!(h && c) });
}
if (gateAll.some((r) => r.exam || ['cloudflare', 'pagerduty', 'sentry'].includes(r.vendor))) throw new Error('exam vendor in gate set');
const gateSets = {
  hand_set: gateAll.filter((r) => r.hand_set && hand.has(`${r.vendor}|${opKey(r.method, r.path, r.operationId)}`)),
  calib_set: gateAll.filter((r) => r.calib_set),
  combined: gateAll,
};

function labelOf(r, th) {
  const t = pileOf(r);
  if (!t || r.p === null) return r.class;
  if (t === 'lower') return r.p < th.lower ? 'w' : r.class;
  if (t === 'raise-wx') return r.p >= th['raise-wx'] ? 'x' : r.class;
  return r.p >= th['raise-get'] ? 'w' : r.class;
}
function score(rows, labelFn) {
  const s = { n: rows.length, exact: 0, loose: 0, tight: 0 };
  for (const r of rows) { const l = labelFn(r); if (l === r.truth) s.exact++; else if (ORDER[l] < ORDER[r.truth]) s.loose++; else s.tight++; }
  s.exactPct = pct(s.exact, s.n); s.loosePct = pct(s.loose, s.n); s.tightPct = pct(s.tight, s.n);
  return s;
}
const gate = { rows: {}, drops, mechanical: {}, rwxmapThresholds: {}, sweeps: {}, tuned: {}, lovo: {}, standaloneB: {}, misses: {} };
for (const [k, v] of Object.entries(gateSets)) gate.rows[k] = v.length;
gate.rows.overlap_hand_and_calib = gateAll.filter((r) => r.both).length;
gate.rows.notAsked_mechanicalKept = gateAll.filter((r) => r.p === null).length;
gate.rows.byTier = Object.fromEntries([...group(gateAll, (r) => pileOf(r) || 'none')].map(([k, v]) => [k, v.length]));
for (const [k, v] of Object.entries(gateSets)) {
  gate.mechanical[k] = score(v, (r) => r.class);
  gate.rwxmapThresholds[k] = score(v, (r) => labelOf(r, RW));
}

// sweeps: per tier, only that tier's rows (others untouched), grid values
const GRID = {
  lower: [0, 0.02, 0.03, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5],
  'raise-wx': [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 1.01],
  'raise-get': [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01],
};
const tierRows = (rows, t) => rows.filter((r) => pileOf(r) === t);
for (const t of Object.keys(GRID)) {
  gate.sweeps[t] = GRID[t].map((v) => ({ threshold: v, ...score(tierRows(gateAll, t), (r) => labelOf(r, { ...RW, [t]: v })) }));
}
// tuning per tier on a set of rows: lexi = min too-loose then max exact; budget = max exact s.t. loose <= mechanical loose
function tune(rows, t, mode) {
  const tr = tierRows(rows, t);
  const base = score(tr, (r) => r.class);
  let best = null;
  for (const v of GRID[t]) {
    const s = score(tr, (r) => labelOf(r, { ...RW, [t]: v }));
    if (mode === 'budget' && s.loose > base.loose) continue;
    const better = !best || (mode === 'lexi' ? (s.loose < best.s.loose || (s.loose === best.s.loose && s.exact > best.s.exact)) : s.exact > best.s.exact);
    if (better) best = { v, s };
  }
  return best?.v ?? (t === 'lower' ? 0 : 1.01);
}
const OFF = { lower: 0, 'raise-wx': 1.01, 'raise-get': 1.01 };
for (const mode of ['lexi', 'budget']) {
  const th = {}; for (const t of Object.keys(GRID)) th[t] = tune(gateAll, t, mode);
  gate.tuned[mode] = { thresholds: th, score: score(gateAll, (r) => labelOf(r, th)) };
  // leave-one-vendor-out over vendors that have gate rows
  const vendors = [...new Set(gateAll.map((r) => r.vendor))];
  const chosen = {}; const agg = { n: 0, exact: 0, loose: 0, tight: 0 };
  for (const v of vendors) {
    const train = gateAll.filter((r) => r.vendor !== v), test = gateAll.filter((r) => r.vendor === v);
    const lt = {}; for (const t of Object.keys(GRID)) lt[t] = tune(train, t, mode);
    for (const t of Object.keys(lt)) (chosen[t] ??= []).push(lt[t]);
    const s = score(test, (r) => labelOf(r, lt));
    for (const k of ['n', 'exact', 'loose', 'tight']) agg[k] += s[k];
  }
  agg.exactPct = pct(agg.exact, agg.n); agg.loosePct = pct(agg.loose, agg.n); agg.tightPct = pct(agg.tight, agg.n);
  const med = (a) => [...a].sort((x, y) => x - y)[a.length >> 1];
  gate.lovo[mode] = { vendors: vendors.length, score: agg, medianChosenThreshold: Object.fromEntries(Object.entries(chosen).map(([t, a]) => [t, med(a)])), chosenRange: Object.fromEntries(Object.entries(chosen).map(([t, a]) => [t, [Math.min(...a), Math.max(...a)]])) };
}

// mode (b) standalone: classifier from p alone, cut 0.5
const bLabel = (r) => (r.p === null ? null : r.q === 'changes' ? (r.p >= 0.5 ? 'w' : 'r') : (r.p >= 0.5 ? 'x' : 'w'));
for (const [name, f] of [['GET changes (r vs w+; truth x counts as not-r)', (r) => r.method.toUpperCase() === 'GET'], ['POST isX (w vs x)', (r) => r.method.toUpperCase() === 'POST'], ['PUT/PATCH isX (w vs x)', (r) => ['PUT', 'PATCH'].includes(r.method.toUpperCase())]]) {
  const rows = gateAll.filter((r) => f(r) && r.p !== null);
  // binary scoring: GET changes: truth r vs truth in {w,x}; isX: truth x vs not x
  const bin = (r) => (r.q === 'changes' ? (r.truth !== 'r') : (r.truth === 'x'));
  const ok = rows.filter((r) => (r.p >= 0.5) === bin(r)).length;
  gate.standaloneB[name] = { n: rows.length, binaryAccuracyPct: pct(ok, rows.length), mechanicalLetterAccuracyPct: pct(rows.filter((r) => r.class === r.truth).length, rows.length) };
}


// subsets: DELETE rows keep mechanical x by contract and dominate the hand labels
{
  const subs = { all: gateAll, nonDelete: gateAll.filter((r) => r.method.toUpperCase() !== 'DELETE'), pilesOnly: gateAll.filter((r) => pileOf(r)) };
  gate.subsets = {};
  for (const [k, v] of Object.entries(subs)) gate.subsets[k] = { mechanical: score(v, (r) => r.class), rwxmap: score(v, (r) => labelOf(r, RW)), tunedLexi: score(v, (r) => labelOf(r, gate.tuned.lexi.thresholds)), tunedBudget: score(v, (r) => labelOf(r, gate.tuned.budget.thresholds)) };
  gate.deleteTruth = {};
  for (const src of ['hand_set', 'calib_set']) { const d = gateAll.filter((r) => r.method.toUpperCase() === 'DELETE' && r.src === src); gate.deleteTruth[src] = { n: d.length, r: d.filter((r) => r.truth === 'r').length, w: d.filter((r) => r.truth === 'w').length, x: d.filter((r) => r.truth === 'x').length }; }
  gate.methodMix = Object.fromEntries([...group(gateAll, (r) => r.method.toUpperCase())].map(([k, v]) => [k, v.length]));
}

// misses at the headline setting (filled below once verdict chosen)
function missReport(th) {
  const lab = (r) => labelOf(r, th);
  const miss = gateAll.filter((r) => lab(r) !== r.truth);
  const byTier = {}, byRule = {};
  for (const [k, v] of group(gateAll, (r) => pileOf(r) || 'none')) byTier[k] = score(v, lab);
  for (const [k, v] of group(gateAll, (r) => `${r.method.toUpperCase()} ${r.class}/${r.rule}`)) byRule[k] = score(v, lab);
  const examples = [...miss].sort((a, b) => (a.id < b.id ? -1 : 1)).filter((_, i) => i % Math.max(1, Math.floor(miss.length / 10)) === 0).slice(0, 10).map((r) => ({ id: r.id, vendor: r.provider, method: r.method, path: r.path, op: r.operationId, summary: String(r.summary || '').slice(0, 140), mech: `${r.class}/${r.rule}`, p: r.p, label: lab(r), truth: r.truth }));
  return { missCount: miss.length, byTier, byRule, examples };
}
gate.misses.rwxmapThresholds = missReport(RW);
gate.misses.tunedLexi = missReport(gate.tuned.lexi.thresholds);
gate.misses.tunedBudget = missReport(gate.tuned.budget.thresholds);

// wobble flips across the chosen cuts (drop candidates)
const flips = (th) => reRows.filter((r) => { const t = pileOf(r); return t && crossAt(r, th[t]); }).length;
wob.flipDropCandidates = {
  rwxmap_thresholds: flips(RW),
  tuned_budget: flips(gate.tuned.budget.thresholds),
  tuned_lexi: flips(gate.tuned.lexi.thresholds),
  note: 'pile rows only; a flip = the two asks fall on different sides of the tier cut',
};

const report = { generated: new Date().toISOString().slice(0, 10), checks, counts: { mechanicalRows: mech.length, asked: asked.length, reasked: reRows.length }, wobble: wob, parity, gate };
fs.writeFileSync(path.join(DATA, 'parity-report.json'), JSON.stringify(report, null, 1));

// ---- print
const J = (o) => console.log(JSON.stringify(o));
console.log('CHECKS'); J(checks);
console.log('WOBBLE'); J({ ...wob, crossByGroup: undefined });
console.log('PILES'); J(Object.fromEntries(Object.entries(parity.piles).map(([k, v]) => [k, { n: v.n, disagree: v.disagree, rate: v.rate, hist: v.hist.join(',') }])));
console.log('OUTSIDE'); for (const [k, v] of Object.entries(parity.outsidePiles)) console.log(' ', k, v.n, v.disagree, v.rate + '%', v.hist.join(','));
console.log('BYRULE'); for (const [k, v] of Object.entries(parity.byRule)) console.log(' ', k, v.n, v.disagree, v.rate + '%');
console.log('VENDOR top count'); for (const v of parity.byVendor.topByCount.slice(0, 25)) console.log(' ', v.vendor, v.n, v.disagree, v.rate + '%');
console.log('VENDOR top rate'); for (const v of parity.byVendor.topByRate.slice(0, 25)) console.log(' ', v.vendor, v.n, v.disagree, v.rate + '%');
console.log('NODESC'); J(parity.noDescription);
console.log('GATE rows'); J(gate.rows); J(gate.drops);
console.log('mechanical'); J(gate.mechanical);
console.log('rwxmap thresholds'); J(gate.rwxmapThresholds);
console.log('sweeps'); for (const [t, a] of Object.entries(gate.sweeps)) { console.log(' ', t); for (const s of a) console.log('   ', s.threshold, s.n, s.exact, s.loose, s.tight); }
console.log('tuned'); J(gate.tuned); console.log('lovo'); J(gate.lovo); console.log('subsets'); J(gate.subsets); J(gate.deleteTruth); J(gate.methodMix); console.log('standaloneB'); J(gate.standaloneB);
console.log('misses rwxmap'); J({ ...gate.misses.rwxmapThresholds, examples: undefined });
console.log('misses budget'); J({ ...gate.misses.tunedBudget, examples: undefined });
for (const e of gate.misses.tunedBudget.examples) J(e);
