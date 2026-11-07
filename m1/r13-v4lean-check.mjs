// R13 on val with rwxmap's mechanical v4 leans (docs/wiki/prereg-exam5.md, 'v4 lean names (decided on val before draw)').
// Runs the PUBLISHED engine (src/answerer.js loadAnswerer, fp32 manifest-exact.json, batch 1) like m1/exam5-predict.mjs, but each val row's
// lean (class, rule) comes from rwxmap's lean.csv instead of the stored v3 lean. src/text.js is not edited.
//   node m1/r13-v4lean-check.mjs --val data/round13/val.jsonl --lean <lean.csv> --variant asis|alias --out <out.csv> [--model-dir data/m1-r13] [--manifest manifest-exact.json]
// - lean.csv header: id,class,rule[,marker]; must hold exactly the val ids (any order). Marker is not used here (score script uses it).
// - Row state is built as m1/export_r13.py does for the parity rows: QUERY read as GET, description = the cleaned 'desc:' segment of the stored text
//   (the raw description is not in the val files; rwxmap's mechanical never reads it).
// - Variant asis: the lean rule goes to the engine unchanged (its own credential-set -> cant-undo-verb alias in src/text.js still applies).
//   Variant alias: the three names R13 never saw are replaced by trained names via ALIAS below; the letter must equal the target's trained letter or the script stops.
// - Output id,model,p_is_x,p_changes in val order (same format as exam5-predict.mjs); an existing out file is not overwritten.
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { loadAnswerer } from '../src/answerer.js';
import { formatText } from '../src/text.js';

// FROZEN before any v4 lean was seen (prereg-exam5 'v4 lean names'). Targets are R13 training names (data/round13/train.jsonl) whose trained letter is given.
const ALIAS = {
  'path-x-word': 'cant-undo-verb', // x on PUT/PATCH/POST (train: 150/29/1984), the same stand-in src/text.js uses for credential-set
  'content-noun': 'modify-verb',   // w on POST (train: 2,081), the only w rule on POST
  'get-action': 'cant-undo-verb',  // x on a verb-named action; x on GET was never trained under any name
};
const TRAINED_LETTER = { 'cant-undo-verb': 'x', 'modify-verb': 'w' };
const TRAINED_RULES = new Set(['cant-undo-verb', 'cant-undo-verb-summary', 'floor-post', 'method', 'method-delete', 'method-floor', 'modify-verb', 'modify-verb-summary', 'read-verb', 'read-verb-anywhere']);

const die = (m) => { console.error('r13-v4lean-check: ' + m); process.exit(1); };
const opt = {}; const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) { if (!args[i].startsWith('--')) die('bad arg ' + args[i]); opt[args[i].slice(2)] = args[i + 1]; }
for (const k of ['val', 'lean', 'variant', 'out']) if (!opt[k]) die('usage: --val <val.jsonl> --lean <lean.csv> --variant asis|alias --out <out.csv> [--model-dir d] [--manifest f]');
if (!['asis', 'alias'].includes(opt.variant)) die('variant must be asis or alias');

const val = readFileSync(opt.val, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
const lines = readFileSync(opt.lean, 'utf8').split('\n').filter((l) => l !== '');
const head = lines[0].split(',');
if (head.slice(0, 3).join(',') !== 'id,class,rule') die('lean.csv header must start id,class,rule, got ' + lines[0]);
const lean = new Map();
for (const l of lines.slice(1)) {
  const f = l.split(','); if (f.length !== head.length) die('bad lean row: ' + l);
  if (lean.has(f[0])) die('duplicate lean id ' + f[0]);
  if (!['r', 'w', 'x'].includes(f[1])) die('bad class in: ' + l);
  lean.set(f[0], { class: f[1], rule: f[2] });
}
if (lean.size !== val.length || val.some((r) => !lean.has(r.id))) die(`lean.csv ids (${lean.size}) do not match the val ids (${val.length})`);

const modelDir = path.resolve(opt['model-dir'] ?? new URL('../data/m1-r13', import.meta.url).pathname);
const a = await loadAnswerer({ dir: modelDir, manifestFile: opt.manifest ?? 'manifest-exact.json' });
const out = ['id,model,p_is_x,p_changes']; const renamed = {}; const unseen = {}; let storedTextSame = 0;
for (const r of val) {
  const state = { method: r.method.toUpperCase() === 'QUERY' ? 'GET' : r.method, path: r.path, operationId: r.operationId || '', summary: r.summary || '',
    description: r.text.includes(' | desc: ') ? r.text.split(' | desc: ').slice(1).join(' | desc: ') : '' };
  const l = { ...lean.get(r.id) };
  if (opt.variant === 'alias' && Object.hasOwn(ALIAS, l.rule)) {
    const to = ALIAS[l.rule];
    if (TRAINED_LETTER[to] !== l.class) die(`${r.id}: ${l.rule} carries letter ${l.class} but ${to} was trained as ${TRAINED_LETTER[to]}`);
    renamed[l.rule] = (renamed[l.rule] ?? 0) + 1; l.rule = to;
  }
  if (!TRAINED_RULES.has(l.rule) && l.rule !== 'credential-set') unseen[l.rule] = (unseen[l.rule] ?? 0) + 1;
  if (formatText(state, l, 1) === r.text.trimEnd()) storedTextSame++;
  const o = await a.answer({ state, lean: l, questions: { isX: 1, changes: 1 } });
  const x = o.answers.isX.noul, c = o.answers.changes.noul;
  for (const p of [x, c]) if (typeof p !== 'number' || !Number.isFinite(p) || p < 0 || p > 1) die(`${r.id}: bad p ${p}`);
  if (c < x) die(`${r.id}: p_changes < p_is_x`);
  out.push(`${r.id},${a.model},${x.toString()},${c.toString()}`);
}
writeFileSync(opt.out, out.join('\n') + '\n', { flag: 'wx' });
console.log(`model ${a.model} T ${a.temperature} variant ${opt.variant} rows ${val.length}`);
console.log('renamed (alias variant):', JSON.stringify(renamed));
console.log(`model text equals the stored val text on ${storedTextSame} of ${val.length} rows (differs wherever the lean differs from the stored v3 lean)`);
if (Object.keys(unseen).length) console.log('NOTE rule names R13 never saw, passed as is:', JSON.stringify(unseen));
