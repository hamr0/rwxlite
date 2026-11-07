// Build the set of files a GitHub release carries, into a folder. Does NOT upload.
//   node m1/release-assets.mjs [out-dir] [r10 | r13] [--skip-version-check]
// The mode is the 2nd positional argument, so r10/r13 need an out-dir given first. Without an out-dir (possible only in plain m1 mode, since r10/r13 need one) the default is data/m1/release/.
// Note: `node m1/release-assets.mjs r13` alone treats "r13" as the out-dir and runs the default m1 build.
// `r10` builds from data/m1-r10/ and carries each manifest's `temperature`.
// `r13` builds from data/m1-r13/ and COPIES all five files verbatim, manifests included (never rewrites them):
// the R13 files must stay byte-identical to what exam #5 tested. Each sha256 is checked against the five values hard-coded below
// (same as docs/wiki/prereg-exam5.md section 9) and any mismatch exits 1. The two manifests must carry the same version, and it must equal
// package.json's version (0.3.1); `--skip-version-check` skips only the package.json comparison (for a dry run before the /release version bump).
// The printed upload command uses the manifests' version as the tag; under --skip-version-check with a differing package.json it prints no command.
// Without r10/r13, data/m1/ is the source and nothing under data/m1-r10 is read or written.
// Files: manifest.json (default, int8 per-channel), manifest-exact.json (fp32), model-int8-pc.onnx, model-fp32.onnx, vocab.txt.
// Every sha256 is recomputed from the copied bytes; version comes from package.json.
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { modelString } from '../src/answerer.js';

const flags = process.argv.slice(2).filter((a) => a.startsWith('--'));
const pos = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const r10 = pos[1] === 'r10';
const r13 = pos[1] === 'r13';
const outArg = pos[0];
const dataDir = r13 ? 'm1-r13' : r10 ? 'm1-r10' : 'm1';
const src = fileURLToPath(new URL(`../data/${dataDir}/`, import.meta.url));
const out = path.resolve(outArg ?? fileURLToPath(new URL('../data/m1/release/', import.meta.url)));
const temperature = r10 ? JSON.parse(readFileSync(path.join(src, 'manifest.json'), 'utf8')).temperature : undefined;
const version = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).version;
const sha = (/** @type {string} */ f) => createHash('sha256').update(readFileSync(f)).digest('hex');

const R13_SHA = {
  'manifest.json': 'e8477a1595578eec1e45020277319877d45cfb809785b22eaeb83bfb66c0a5b8',
  'manifest-exact.json': 'c6bac86970888049952305f72434abe5c9d8f854224a5537f14e5a428a977739',
  'model-int8-pc.onnx': '984714f0342ce551779f0ed9d95be57f71ab30b2ef72baec1d9818ce96d465d7',
  'model-fp32.onnx': 'bbe1997d43020724f9eab9e42e8f6337e9640fe46f764b6fceac1eb1d000a3cf',
  'vocab.txt': '07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3',
};

let assetVersion;
if (r13) {
  const bad = [];
  for (const n of Object.keys(R13_SHA)) if (sha(path.join(src, n)) !== R13_SHA[n]) bad.push(`${n}: source sha256 ${sha(path.join(src, n))} != expected ${R13_SHA[n]}`);
  if (bad.length) { console.error(`R13 source files differ from the exam #5 values:\n  ${bad.join('\n  ')}`); process.exit(1); }
  const mvs = ['manifest.json', 'manifest-exact.json'].map((n) => JSON.parse(readFileSync(path.join(src, n), 'utf8')).version);
  if (mvs[0] !== mvs[1]) { console.error(`manifest.json version ${mvs[0]} != manifest-exact.json version ${mvs[1]}.`); process.exit(1); }
  assetVersion = mvs[0];
  if (!flags.includes('--skip-version-check') && assetVersion !== version) { console.error(`package.json version ${version} != manifests version ${assetVersion}. Bump package.json first (done in /release), or pass --skip-version-check for a dry run.`); process.exit(1); }
  mkdirSync(out, { recursive: true });
  for (const n of Object.keys(R13_SHA)) copyFileSync(path.join(src, n), path.join(out, n));
  for (const n of Object.keys(R13_SHA)) {
    const got = sha(path.join(out, n));
    if (got !== R13_SHA[n]) { console.error(`${n}: copied sha256 ${got} != expected ${R13_SHA[n]}`); process.exit(1); }
    console.log(`${n.padEnd(22)} ${String(statSync(path.join(out, n)).size).padStart(10)} bytes  sha256 ${got}  OK`);
  }
  console.log('\nAll five match the exam #5 values. Not uploaded.');
  if (assetVersion !== version) console.log(`DRY RUN: package.json is ${version}, assets are ${assetVersion}; bump first (done in /release), then re-run without --skip-version-check to get the upload command.`);
  else console.log(`To publish, a human runs:\n  gh release upload v${assetVersion} ${Object.keys(R13_SHA).map((n) => path.join(out, n)).join(' ')} --repo hamr0/rwxlite --clobber`);
  process.exit(0);
}

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
