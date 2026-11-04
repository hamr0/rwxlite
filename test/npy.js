// Minimal .npy reader for little-endian float32/float64 2-D arrays (the probs-*.npy files from m1/export_onnx.py).
import { readFileSync } from 'node:fs';

/** @param {string|URL} file @returns {{rows: number, cols: number, data: Float64Array}} */
export function readNpy(file) {
  const b = readFileSync(file);
  if (b.toString('latin1', 1, 6) !== 'NUMPY') throw new Error('not an npy file');
  const hlen = b[6] === 1 ? b.readUInt16LE(8) : b.readUInt32LE(8);
  const off = (b[6] === 1 ? 10 : 12) + hlen;
  const head = b.toString('latin1', b[6] === 1 ? 10 : 12, off);
  const descr = /'descr':\s*'([^']+)'/.exec(head)?.[1];
  const shape = /'shape':\s*\((\d+),\s*(\d+)\)/.exec(head);
  if (!descr || !shape || /'fortran_order':\s*True/.test(head)) throw new Error('unsupported npy: ' + head);
  const rows = Number(shape[1]); const cols = Number(shape[2]); const n = rows * cols;
  const data = new Float64Array(n);
  for (let i = 0; i < n; i++) data[i] = descr === '<f4' ? b.readFloatLE(off + 4 * i) : descr === '<f8' ? b.readDoubleLE(off + 8 * i) : NaN;
  if (Number.isNaN(data[0]) && descr !== '<f4' && descr !== '<f8') throw new Error('unsupported dtype ' + descr);
  return { rows, cols, data };
}
