// M1 benchmark in Node: load time, per-op latency (batch 1, --threads=N, default 1), batch-32 throughput (default threads),
// and agreement with the Python probabilities saved by m1/variants.py eval (batch 1).
//   node m1/bench.mjs                 the shipped model (data/m1/manifest.json)  -> data/m1/bench.json
//   node m1/bench.mjs --variants      every variant (or --only=a,b)               -> data/m1/bench-<variant>.json, then merges data/m1/variants.json
//   --threads=N      threads for the batch-1 latency session (default 1, comparable with existing results). N != 1 writes
//                    bench-<variant>-t<N>.json (bench-t<N>.json for the shipped model) and does not touch variants.json.
//   --latency-only   skip the agreement and batch-32 parts (quick run); the fresh-exam latency is still measured. Also leaves variants.json alone.
//                    Adds a -latency suffix (bench-<variant>[-t<N>]-latency.json) so it never overwrites the full result.
// Latency depends on what else the machine is doing; the load average at the start is recorded in the result.
import { createHash } from 'node:crypto';
import { execSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import { loadAnswerer, modelString } from '../src/answerer.js';
import { readNpy } from '../test/npy.js';

const dir = new URL('../data/m1/', import.meta.url);
const root = new URL('../', import.meta.url);
const version = JSON.parse(readFileSync(new URL('package.json', root), 'utf8')).version;
const VARIANTS = { fp32: 'model-fp32.onnx', 'int8-default': 'model-int8.onnx', 'int8-pc': 'model-int8-pc.onnx', 'int8-mm': 'model-int8-mm.onnx', 'int8-pc-mm': 'model-int8-pc-mm.onnx', fp16: 'model-fp16.onnx' };
const sha = (/** @type {string} */ f) => createHash('sha256').update(readFileSync(new URL(f, dir))).digest('hex');

/** @param {string} file */
function lines(file) { return readFileSync(new URL(file, root), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)); }
const stateOf = (/** @type {any} */ r) => ({ method: r.method, path: r.path, operationId: r.operationId, summary: r.summary, description: r.description });
const toReq = (/** @type {any} */ r) => ({ state: stateOf(r), questions: { isX: 1, changes: 1 }, lean: { class: r.class, rule: r.rule } });
const THREADS = (() => { const a = process.argv.find((x) => x.startsWith('--threads=')); if (!a) return 1; const n = Number(a.slice(10)); if (!Number.isInteger(n) || n < 0) throw new Error(`bad ${a}`); return n; })();
const LATENCY_ONLY = process.argv.includes('--latency-only');
const SUFFIX = (THREADS === 1 ? '' : `-t${THREADS}`) + (LATENCY_ONLY ? '-latency' : '');
const q = (/** @type {number[]} */ sorted, /** @type {number} */ f) => sorted[Math.min(sorted.length - 1, Math.floor(f * sorted.length))];
const SETS = { 'exam-2026-11-03-fresh': 'data/exam-fresh-r8soft/inputs.jsonl', 'exam-2026-09-22': 'data/exam-r8soft/inputs.jsonl' };

/** @param {string} name @param {string} modelFile */
async function benchOne(name, modelFile) {
  const manifestFile = `manifest-${name}.json`;
  const files = { [modelFile]: sha(modelFile), 'vocab.txt': sha('vocab.txt') };
  writeFileSync(new URL(manifestFile, dir), JSON.stringify({ version, modelFile, model: modelString(version, files[modelFile]), files }, null, 2) + '\n');
  const dpath = new URL(dir).pathname;
  const res = { variant: name, file: modelFile, model: modelString(version, files[modelFile]), sha256: files[modelFile], size_mb: +(readFileSync(new URL(modelFile, dir)).length / 1e6).toFixed(2) };

  let t0 = performance.now();
  const one = await loadAnswerer({ dir: dpath, threads: THREADS, manifestFile });
  res.threads = THREADS;
  res.load_ms_1thread = +(performance.now() - t0).toFixed(0);
  const fresh = lines(SETS['exam-2026-11-03-fresh']);
  for (const r of fresh.slice(0, 20)) await one.answerMany([toReq(r)]); // warm-up
  res.agreement = {};
  for (const [ex, file] of Object.entries(SETS)) {
    if (LATENCY_ONLY && !ex.endsWith('fresh')) continue;
    const rows = ex.endsWith('fresh') ? fresh : lines(file);
    const py = !LATENCY_ONLY && existsSync(new URL(`probs-${name}-b1-${ex}.npy`, dir)) ? readNpy(new URL(`probs-${name}-b1-${ex}.npy`, dir)) : null;
    /** @type {number[]} */ const ms = []; let maxD = 0; let sumD = 0; let bad = 0;
    for (let i = 0; i < rows.length; i++) {
      const s = performance.now();
      const [o] = await one.answerMany([toReq(rows[i])]);
      ms.push(performance.now() - s);
      if (o instanceof Error) { bad += 1; continue; }
      if (py) {
        const a = /** @type {any} */ (o).answers; const pw = py.data[i * 3 + 1]; const px = py.data[i * 3 + 2];
        const d = Math.max(Math.abs(a.isX.noul - px), Math.abs(a.changes.noul - (pw + px)));
        maxD = Math.max(maxD, d); sumD += d;
      }
    }
    const sorted = [...ms].sort((a, b) => a - b);
    res.agreement[ex] = { n: rows.length, errors: bad, python_probs: py ? `probs-${name}-b1-${ex}.npy` : null, max_abs_diff: py ? maxD : null, mean_abs_diff: py ? sumD / rows.length : null };
    if (ex.endsWith('fresh')) res.latency_ms_batch1_1thread = { n: rows.length, p50: +q(sorted, 0.5).toFixed(2), p95: +q(sorted, 0.95).toFixed(2), p99: +q(sorted, 0.99).toFixed(2), mean: +(ms.reduce((a, b) => a + b, 0) / ms.length).toFixed(2), max: +sorted[sorted.length - 1].toFixed(2) };
  }
  if (LATENCY_ONLY) return res;
  const many = await loadAnswerer({ dir: dpath, threads: 0, manifestFile });
  const reqs = fresh.map(toReq);
  await many.answerMany(reqs.slice(0, 32));
  t0 = performance.now();
  for (let i = 0; i + 32 <= reqs.length; i += 32) await many.answerMany(reqs.slice(i, i + 32));
  const n = Math.floor(reqs.length / 32) * 32;
  res.throughput_batch32_default_threads = { rows: n, ms_per_op: +((performance.now() - t0) / n).toFixed(2) };
  return res;
}

const cpu = (() => { try { return execSync("lscpu | grep 'Model name'").toString().split(':')[1].trim(); } catch { return os.cpus()[0]?.model; } })();
const machine = { cpu, load_avg_at_start: os.loadavg().map((x) => +x.toFixed(1)), nproc: os.cpus().length, node: process.version, platform: `${process.platform}-${process.arch}`, onnxruntime_node: JSON.parse(readFileSync(new URL('node_modules/onnxruntime-node/package.json', root), 'utf8')).version };

if (process.argv.includes('--variants')) {
  const only = process.argv.find((a) => a.startsWith('--only='))?.slice(7).split(',');
  const all = {};
  for (const [name, f] of Object.entries(VARIANTS)) {
    if (only && !only.includes(name)) continue;
    if (!existsSync(new URL(f, dir))) { console.log('skip', name, '(file missing)'); continue; }
    const r = await benchOne(name, f); all[name] = r;
    writeFileSync(new URL(`bench-${name}${SUFFIX}.json`, dir), JSON.stringify({ machine, ...r }, null, 2) + '\n');
    console.log(name, JSON.stringify({ size_mb: r.size_mb, load_ms: r.load_ms_1thread, lat: r.latency_ms_batch1_1thread, b32: r.throughput_batch32_default_threads, fresh_maxdiff: r.agreement['exam-2026-11-03-fresh'].max_abs_diff, threads: r.threads }));
  }
  if (LATENCY_ONLY || THREADS !== 1) process.exit(0); // partial / non-default-thread results must not overwrite the merged variants.json
  const prev = existsSync(new URL('variants.json', dir)) ? JSON.parse(readFileSync(new URL('variants.json', dir), 'utf8')) : JSON.parse(readFileSync(new URL('variants-py.json', dir), 'utf8'));
  for (const [name, r] of Object.entries(all)) Object.assign(prev.variants[name], { node: { machine, ...r } });
  writeFileSync(new URL('variants.json', dir), JSON.stringify(prev, null, 2) + '\n');
} else {
  const m = JSON.parse(readFileSync(new URL('manifest.json', dir), 'utf8'));
  const name = Object.keys(VARIANTS).find((k) => VARIANTS[k] === m.modelFile) ?? m.modelFile;
  const r = await benchOne(name, m.modelFile);
  writeFileSync(new URL(`bench${SUFFIX}.json`, dir), JSON.stringify({ machine, ...r }, null, 2) + '\n');
  console.log(JSON.stringify({ machine, ...r }, null, 2));
}
