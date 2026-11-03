// Module 0, step 1: rwxmap's mechanical classifier (classifyRow) over every
// APIs.guru operation. Offline, free, no network, no Jev calls.
//
//   node m0/mechanical.mjs            -> data/m0/mechanical.jsonl.gz + summary
//   node m0/mechanical.mjs --sanity   -> also re-scores the exam (4279 ops)
//
// Input is rwxmap's data/corpus/apis-guru-ops.csv.gz read in place. That CSV
// already carries method/path/operationId/summary/description, which is all
// classifyRow reads, so the specs are not re-parsed.
//
// rwxmap is imported via the file: dependency (node_modules/rwxmap -> ../rwxmap)
// and is never written to.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { classifyRow, needsJev } from 'rwxmap';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.join(HERE, '..', 'data', 'm0');
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
const D = (...p) => path.join(RWXMAP, 'data', ...p);

const EXAM_PROVIDERS = new Set(['cloudflare', 'pagerduty', 'sentry']); // exam-2026-09-22 provider column
const ORDER = { r: 0, w: 1, x: 2 };

// ---- small RFC-4180 reader (same behaviour as rwxmap tools/csv.js parseCsv)
function parseCsv(text) {
  const rows = []; let row = []; let f = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; }
    else if (c !== '\r') f += c;
  }
  if (f !== '' || row.length) { row.push(f); rows.push(row); }
  const h = rows[0];
  return rows.slice(1).filter((r) => !(r.length === 1 && r[0] === '')).map((r) => {
    const o = {}; h.forEach((k, i) => { o[k] = r[i] ?? ''; }); return o;
  });
}
const readCsv = (p) => parseCsv(p.endsWith('.gz') ? zlib.gunzipSync(fs.readFileSync(p)).toString('utf8') : fs.readFileSync(p, 'utf8'));

const first = (s) => String(s || '').toLowerCase().split(/[.:]/)[0];
const opKey = (m, p, o) => `${String(m).toUpperCase()}|${p}|${o}`;
const provKey = (prov, m, p, o) => `${prov}|${opKey(m, p, o)}`;

function verdictOf(r) {
  return classifyRow({ method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description });
}

function main() {
  const t0 = Date.now();
  const sanity = process.argv.includes('--sanity');
  fs.mkdirSync(OUT_DIR, { recursive: true });

  // lookup sets for exam / hand-label overlap
  const exam = readCsv(D('exam-2026-09-22', 'labelled.csv'));
  const examOpKeys = new Set(exam.map((r) => opKey(r.method, r.path, r.operationId)));
  const hand = readCsv(D('corpus', 'labelled.csv'));
  const handKeys = new Map(hand.map((r) => [`${r.repo}|${opKey(r.method, r.path, r.operationId)}`, r.set]));
  const handExamProv = hand.filter((r) => EXAM_PROVIDERS.has(r.repo)).length;
  const calib = new Map();
  for (const c of ['calibA', 'calibB', 'calibC']) {
    for (const r of readCsv(D('calibration-2026-09-14', `${c}-blind.csv`))) calib.set(provKey(r.provider, r.method, r.path, r.operationId), c);
  }

  const ops = readCsv(D('corpus', 'apis-guru-ops.csv.gz'));
  const stats = { total: ops.length, dropped: 0, byClass: {}, byRule: {}, byTier: {}, exam: 0, examByProvider: 0, examByOpKey: 0, hand: 0, calib: 0, step: {}, review: {}, destructive: 0 };
  const inc = (o, k) => { o[k] = (o[k] || 0) + 1; };

  const gz = zlib.createGzip({ level: 6 });
  gz.pipe(fs.createWriteStream(path.join(OUT_DIR, 'mechanical.jsonl.gz')));
  let emitted = 0;
  ops.forEach((r, i) => {
    if (!r.method || !r.path) { stats.dropped++; return; }
    const v = verdictOf(r);
    const tier = needsJev(v);
    const byProv = EXAM_PROVIDERS.has(first(r.provider)) || EXAM_PROVIDERS.has(first(r.api_key));
    const byOp = examOpKeys.has(opKey(r.method, r.path, r.operationId));
    const handSet = handKeys.get(`${first(r.provider)}|${opKey(r.method, r.path, r.operationId)}`) || null;
    const calibSet = calib.get(provKey(r.provider, r.method, r.path, r.operationId)) || null;
    const out = {
      id: `ag-${String(i).padStart(6, '0')}`, // 0-based position in apis-guru-ops.csv.gz data rows
      provider: r.provider, api_key: r.api_key, spec_version: r.spec_version,
      method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description,
      class: v.class, rule: v.rule, step: v.step, source: v.source, review: v.review,
      matched: v.matched, destructive: v.destructive === true, jev_tier: tier,
      exam: byProv, // provider match only: these are excluded from training
      exam_opkey_overlap: byOp, // same method|path|operationId as an exam row (provider-agnostic)
      hand_set: handSet, calib_set: calibSet,
    };
    gz.write(JSON.stringify(out) + '\n');
    emitted++;
    inc(stats.byClass, v.class); inc(stats.byRule, `${v.class}/${v.rule}`); inc(stats.byTier, tier || 'none');
    inc(stats.step, v.step); inc(stats.review, v.review);
    if (v.destructive) stats.destructive++;
    if (byProv) stats.exam++;
    if (byOp) stats.examByOpKey++;
    if (handSet) stats.hand++;
    if (calibSet) stats.calib++;
  });
  gz.end();
  stats.emitted = emitted;
  stats.handExamProviderRows = handExamProv;
  stats.providers = new Set(ops.map((r) => r.provider)).size;
  stats.seconds = (Date.now() - t0) / 1000;
  console.log(JSON.stringify(stats, null, 2));

  if (sanity) {
    const t = { rows: 0, exact: 0, leak: 0, tight: 0 };
    const per = {};
    for (const r of exam) {
      const p = verdictOf(r).class;
      const k = p === r.truth_class ? 'exact' : ORDER[p] < ORDER[r.truth_class] ? 'leak' : 'tight';
      t.rows++; t[k]++;
      per[r.provider] ??= { rows: 0, exact: 0, leak: 0, tight: 0 };
      per[r.provider].rows++; per[r.provider][k]++;
    }
    const pc = (n) => `${n} (${((n / t.rows) * 100).toFixed(2)}%)`;
    console.log('SANITY exam rows', t.rows, 'exact', pc(t.exact), 'too loose (leak)', pc(t.leak), 'too tight', pc(t.tight));
    console.log(JSON.stringify(per));
  }
}
main();
