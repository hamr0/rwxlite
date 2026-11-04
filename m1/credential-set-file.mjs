// Usage: node m1/credential-set-file.mjs   (writes test/fixtures/credential-set.jsonl; prints a summary)
// The 32 ops whose rule is 'credential-set' in data/m0/mechanical.jsonl.gz, answered by the model twice:
//   before: lean rule sent as the raw name 'credential-set' (what the model gave before the guard in src/text.js);
//   after:  the public path (loadAnswerer data/m1 + answerMany), which applies the guard.
// argmax = letter of max(1-changes, changes-isX, isX) for r/w/x; maxP is that max. No truth labels.
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { formatText } from '../src/text.js';
import { loadAnswerer, calibrated, MAX_LEN } from '../src/answerer.js';

const RAW = 'credential-set'; const TRAINED = 'cant-undo-verb';
const ops = gunzipSync(readFileSync(new URL('../data/m0/mechanical.jsonl.gz', import.meta.url))).toString('utf8')
  .split('\n').filter(Boolean).map((l) => JSON.parse(l)).filter((r) => r.rule === RAW)
  .sort((a, b) => (a.provider < b.provider ? -1 : a.provider > b.provider ? 1 : a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
const stateOf = (r) => ({ method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description });
const shape = (isX, changes) => {
  const p = { r: 1 - changes, w: changes - isX, x: isX };
  const argmax = Object.keys(p).reduce((a, b) => (p[b] > p[a] ? b : a));
  return { isX, changes, argmax, maxP: p[argmax] };
};

// before: build the pre-guard text by hand, run the same tokenizer and runner.
const prefix = (rule) => `lean: x ${rule}`;
const texts = ops.map((r) => {
  const t = formatText(stateOf(r), { class: 'x', rule: TRAINED });
  if (!t.startsWith(prefix(TRAINED) + ' | ')) throw new Error('unexpected text prefix');
  return prefix(RAW) + t.slice(prefix(TRAINED).length);
});
// the swap changes only the rule word: the rest is byte-identical to the guarded text
ops.forEach((r, i) => {
  const g = formatText(stateOf(r), { class: 'x', rule: RAW });
  if (g !== formatText(stateOf(r), { class: 'x', rule: TRAINED })) throw new Error('guard not active');
  if (texts[i].replace(prefix(RAW), prefix(TRAINED)) !== g) throw new Error('pre-guard text mismatch');
});

const ans = await loadAnswerer({ dir: new URL('../data/m1', import.meta.url).pathname });
const logits = await ans.runner.run(texts.map((t) => ans.tokenizer.encode(t, MAX_LEN)));
const before = logits.map((L) => { const P = calibrated(L); return shape(P[2], P[1] + P[2]); });
const res = await ans.answerMany(ops.map((r) => ({ state: stateOf(r), questions: { isX: 1, changes: 1 }, lean: { class: 'x', rule: RAW } })));
const after = res.map((a) => { if ('error' in a) throw new Error(a.error); return shape(a.answers.isX.noul, a.answers.changes.noul); });

const rows = ops.map((r, i) => ({
  provider: r.provider, method: r.method, path: r.path, operationId: r.operationId, summary: r.summary,
  before: before[i], after: after[i], model: ans.model,
}));
writeFileSync(new URL('../test/fixtures/credential-set.jsonl', import.meta.url), rows.map((r) => JSON.stringify(r)).join('\n') + '\n');

const sum = (xs) => {
  const c = { r: 0, w: 0, x: 0 }; for (const s of xs) c[s.argmax] += 1;
  const low = xs.filter((s) => s.argmax !== 'x');
  return { argmax: c, lowerings: low.length, ge97: low.filter((s) => s.maxP >= 0.97).length, ge95: low.filter((s) => s.maxP >= 0.95).length };
};
console.log(JSON.stringify({ rows: rows.length, model: ans.model, before: sum(before), after: sum(after) }, null, 1));
