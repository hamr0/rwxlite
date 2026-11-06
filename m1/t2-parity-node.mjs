// Reads JSON rows (one per line) on stdin, writes JSON {t1, t2} per line: Node formatText format 1 and 2. Used by m1/t2-parity.py.
import { createInterface } from 'node:readline';
import { formatText } from '../src/text.js';

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
const out = [];
for await (const line of rl) {
  if (!line) continue;
  const r = JSON.parse(line);
  const st = { method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description };
  const lean = { class: r.class, rule: r.rule };
  out.push(JSON.stringify({ t1: formatText(st, lean, 1), t2: formatText(st, lean, 2) }));
}
process.stdout.write(out.join('\n') + '\n');
