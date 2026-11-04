// Write data/m1/manifest.json: the version (package.json), which file holds the weights, and the sha256 of every
// file the answerer loads. loadAnswerer refuses to run if a file does not match.
//   node m1/manifest.mjs [model-file]     default model-int8-pc.onnx; any model-*.onnx in data/m1 works
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { modelString } from '../src/answerer.js';

const modelFile = process.argv[2] ?? 'model-int8-pc.onnx';
const dir = new URL('../data/m1/', import.meta.url);
const version = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).version;
/** @type {Record<string, string>} */
const files = {};
for (const name of [modelFile, 'vocab.txt']) files[name] = createHash('sha256').update(readFileSync(new URL(name, dir))).digest('hex');
const manifest = { version, modelFile, model: modelString(version, files[modelFile]), files };
writeFileSync(new URL('manifest.json', dir), JSON.stringify(manifest, null, 2) + '\n');
console.log(JSON.stringify(manifest));
