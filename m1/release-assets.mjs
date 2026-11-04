// Build the set of files a GitHub release carries, into a folder (default data/m1/release/). Does NOT upload.
//   node m1/release-assets.mjs [out-dir] [r10]
// `r10` as the second argument builds from data/m1-r10/ (default out data/m1-r10/release/) and carries each manifest's `temperature`.
// Without it, data/m1/ is the source and nothing under data/m1-r10 is read or written.
// Files: manifest.json (default, int8 per-channel), manifest-exact.json (fp32), model-int8-pc.onnx, model-fp32.onnx, vocab.txt.
// Every sha256 is recomputed from the copied bytes; version comes from package.json.
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { modelString } from '../src/answerer.js';

const r10 = process.argv[3] === 'r10';
const outArg = process.argv[2];
const dataDir = r10 ? 'm1-r10' : 'm1';
const src = fileURLToPath(new URL(`../data/${dataDir}/`, import.meta.url));
const out = path.resolve(outArg ?? fileURLToPath(new URL(`../data/${dataDir}/release/`, import.meta.url)));
const temperature = r10 ? JSON.parse(readFileSync(path.join(src, 'manifest.json'), 'utf8')).temperature : undefined;
const version = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).version;
const sha = (/** @type {string} */ f) => createHash('sha256').update(readFileSync(f)).digest('hex');

mkdirSync(out, { recursive: true });
for (const name of ['model-int8-pc.onnx', 'model-fp32.onnx', 'vocab.txt']) copyFileSync(path.join(src, name), path.join(out, name));
const hash = Object.fromEntries(['model-int8-pc.onnx', 'model-fp32.onnx', 'vocab.txt'].map((n) => [n, sha(path.join(out, n))]));

/** @param {string} modelFile @param {string} file */
function writeManifest(modelFile, file) {
  const files = { [modelFile]: hash[modelFile], 'vocab.txt': hash['vocab.txt'] };
  const m = { version, modelFile, model: modelString(version, hash[modelFile]), ...(temperature === undefined ? {} : { temperature }), files };
  writeFileSync(path.join(out, file), JSON.stringify(m, null, 2) + '\n');
}
writeManifest('model-int8-pc.onnx', 'manifest.json');
writeManifest('model-fp32.onnx', 'manifest-exact.json');

const names = ['manifest.json', 'manifest-exact.json', 'model-int8-pc.onnx', 'model-fp32.onnx', 'vocab.txt'];
for (const n of names) {
  const p = path.join(out, n);
  console.log(`${n.padEnd(22)} ${String(statSync(p).size).padStart(10)} bytes  sha256 ${sha(p)}`);
}
for (const n of ['manifest.json', 'manifest-exact.json']) console.log(`${n}: model ${JSON.parse(readFileSync(path.join(out, n), 'utf8')).model}`);
console.log(`\nNot uploaded. To publish, a human runs:\n  gh release upload v${version} ${names.map((n) => path.join(out, n)).join(' ')} --repo hamr0/rwxlite --clobber`);
