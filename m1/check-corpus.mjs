// M1: Node text format + tokenizer against the Python on the whole local corpus
// (data/m1/corpus-parity.jsonl from m1/make_fixtures.py; local only, gitignored).
//   node m1/check-corpus.mjs
import { readFileSync } from 'node:fs';
import { formatText } from '../src/text.js';
import { WordPiece } from '../src/tokenizer.js';

const tok = new WordPiece(readFileSync(new URL('../data/m1/vocab.txt', import.meta.url), 'utf8'));
const rows = readFileSync(new URL('../data/m1/corpus-parity.jsonl', import.meta.url), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
let textBad = 0; let idBad = 0; let withState = 0; const show = [];
for (const r of rows) {
  if (r.state) {
    withState += 1;
    const t = formatText(r.state, r.lean);
    if (t !== r.text) { textBad += 1; if (show.length < 5) show.push({ kind: 'text', py: r.text, js: t }); }
  }
  const ids = tok.encode(r.text);
  if (ids.length !== r.ids.length || ids.some((v, i) => v !== r.ids[i])) { idBad += 1; if (show.length < 5) show.push({ kind: 'ids', text: r.text.slice(0, 200) }); }
}
console.log(JSON.stringify({ rows: rows.length, text_checked: withState, text_mismatch: textBad, ids_mismatch: idBad }));
for (const s of show) console.log(JSON.stringify(s));
process.exitCode = textBad || idBad ? 1 : 0;
