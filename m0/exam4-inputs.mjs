// Exam #4 inputs (docs/wiki/exam-prereg-exam4.md). Guarded wrapper around m0/exam3-inputs.mjs (unchanged; reads no truth).
//   RWXMAP_DIR=<git-archive of rwxmap at RWXMAP_REF> RWXMAP_REF=<40-hex> node m0/exam4-inputs.mjs <ops.csv> <out-dir> [--smoke]
// Real run: ops.csv sha256 must equal the frozen exam #4 hash, out-dir must be data/exam4, inputs.jsonl must not exist yet, RWXMAP_DIR and
// RWXMAP_REF are required (the ref is written to <out-dir>/rwxmap-ref.txt). --smoke: out-dir must not be data/exam4 and its name must contain "smoke".
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OPS_SHA = 'e9836ff2f9e8288e3721f97506ed666b871a3486f7b781c544b5234a0b5da0b4';
const smoke = process.argv.includes('--smoke');
const [opsPath, outDir] = process.argv.slice(2).filter((a) => a !== '--smoke');
if (!opsPath || !outDir) { console.error('usage: node m0/exam4-inputs.mjs <ops.csv> <out-dir> [--smoke]'); process.exit(2); }
const real = path.resolve(HERE, '..', 'data', 'exam4');
const out = path.resolve(outDir);
const die = (m) => { console.error(m); process.exit(1); };
if (fs.existsSync(path.join(out, 'inputs.jsonl'))) die(`refusing to overwrite ${path.join(out, 'inputs.jsonl')}`);
const sha = crypto.createHash('sha256').update(fs.readFileSync(opsPath)).digest('hex');
if (smoke) {
  if (out === real || !path.basename(out).includes('smoke')) die('--smoke: out-dir must not be data/exam4 and its name must contain "smoke"');
  if (sha === OPS_SHA) die('--smoke: refusing the real exam #4 ops.csv');
} else {
  if (out !== real) die(`real run: out-dir must be ${real}`);
  if (sha !== OPS_SHA) die(`ops.csv sha256 ${sha} != frozen ${OPS_SHA}`);
  if (!process.env.RWXMAP_DIR || !/^[0-9a-f]{40}$/.test(process.env.RWXMAP_REF || '')) die('real run: set RWXMAP_DIR (git archive of rwxmap) and RWXMAP_REF (40-hex commit)');
}
execFileSync('node', [path.join(HERE, 'exam3-inputs.mjs'), opsPath, out], { stdio: 'inherit', env: process.env });
fs.writeFileSync(path.join(out, 'ops-sha256.txt'), sha + '\n');
if (!smoke) fs.writeFileSync(path.join(out, 'rwxmap-ref.txt'), process.env.RWXMAP_REF + '\n');
