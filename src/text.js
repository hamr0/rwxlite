// The model's input text, ported from train/common.py fmt_text and clean.
// The model was trained on exactly this string, so any change here changes
// the answers. Parity with the Python is tested in test/text.test.js against
// a fixture the Python wrote.
//
// Format: 'lean: <letter> <rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>'
// The lean (mechanical letter and rule) goes first so truncation never cuts it.

import { HTML5 } from './entities.js';

// Python html.unescape (CPython Lib/html/__init__.py), ported exactly: the
// regex, the longest-prefix rule for names without ';', and the invalid
// numeric references. The name table is generated into entities.js.

// Numeric references Python maps instead of decoding (HTML5 spec).
const INVALID_CHARREFS = {
  0x00: '\ufffd', 0x0d: '\r', 0x80: '\u20ac', 0x81: '\x81', 0x82: '\u201a', 0x83: '\u0192', 0x84: '\u201e',
  0x85: '\u2026', 0x86: '\u2020', 0x87: '\u2021', 0x88: '\u02c6', 0x89: '\u2030', 0x8a: '\u0160', 0x8b: '\u2039',
  0x8c: '\u0152', 0x8d: '\x8d', 0x8e: '\u017d', 0x8f: '\x8f', 0x90: '\x90', 0x91: '\u2018', 0x92: '\u2019',
  0x93: '\u201c', 0x94: '\u201d', 0x95: '\u2022', 0x96: '\u2013', 0x97: '\u2014', 0x98: '\u02dc', 0x99: '\u2122',
  0x9a: '\u0161', 0x9b: '\u203a', 0x9c: '\u0153', 0x9d: '\x9d', 0x9e: '\u017e', 0x9f: '\u0178',
};

// Numeric references Python decodes to '' (controls, noncharacters).
function isInvalidCodepoint(n) {
  return (n >= 0x1 && n <= 0x8) || n === 0xb || (n >= 0xe && n <= 0x1f) || (n >= 0x7f && n <= 0x9f) ||
    (n >= 0xfdd0 && n <= 0xfdef) || ((n & 0xfffe) === 0xfffe && n <= 0x10ffff);
}

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

// Python's _charref; the u flag makes {1,32} count code points like Python.
const CHARREF = /&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)/gu;

/** @param {string} body the text after '&' */
function replaceCharref(body) {
  if (body[0] === '#') {
    const hex = body[1] === 'x' || body[1] === 'X';
    const n = parseInt(body.slice(hex ? 2 : 1).replace(/;+$/, ''), hex ? 16 : 10);
    if (has(INVALID_CHARREFS, n)) return INVALID_CHARREFS[/** @type {keyof typeof INVALID_CHARREFS} */ (n)];
    if ((n >= 0xd800 && n <= 0xdfff) || n > 0x10ffff) return '\ufffd';
    if (isInvalidCodepoint(n)) return '';
    return String.fromCodePoint(n);
  }
  if (has(HTML5, body)) return HTML5[body];
  // longest matching name (as defined by the standard), by code points
  const cps = Array.from(body);
  for (let x = cps.length - 1; x > 1; x--) {
    const head = cps.slice(0, x).join('');
    if (has(HTML5, head)) return HTML5[head] + cps.slice(x).join('');
  }
  return '&' + body;
}

/** @param {string} s */
export function unescapeHtml(s) {
  return s.includes('&') ? s.replace(CHARREF, (_, body) => replaceCharref(body)) : s;
}

// Python's \s (str patterns) is Unicode whitespace per str.isspace, which
// includes \x1c-\x1f and excludes ﻿; JS \s differs on both.
const PY_WS = /[\t\n\v\f\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g;

/**
 * train/common.py clean(s, n): strip tags, unescape, collapse whitespace, trim, cut to n code points.
 * @param {unknown} s
 * @param {number} n
 * @returns {string}
 */
export function clean(s, n) {
  const str = s === null || s === undefined ? '' : String(s);
  const out = unescapeHtml(str.replace(/<[^>]+>/g, ' ')).replace(PY_WS, ' ').replace(/^ +| +$/g, '');
  const cps = Array.from(out);
  return cps.length > n ? cps.slice(0, n).join('') : out;
}

// HTTP QUERY (RFC 10008; rwxmap D134) is safe and idempotent like GET, and the
// model never saw it in training, so it is read as GET (measured: PRD, "QUERY").
/** @param {unknown} m */
function textMethod(m) {
  const u = String(m).toUpperCase();
  return u === 'QUERY' ? 'GET' : u;
}

/**
 * @typedef {{method: string, path: string, operationId?: string|null, summary?: string|null, description?: string|null}} State
 * @typedef {{class: 'r'|'w'|'x', rule: string}} Lean
 */

/**
 * train/common.py fmt_text: the one string the model reads.
 * @param {State} state
 * @param {Lean} lean
 * @returns {string}
 */
export function formatText(state, lean) {
  const parts = [`lean: ${lean.class} ${lean.rule}`, `${textMethod(state.method)} ${state.path}`];
  if (state.operationId) parts.push('op: ' + clean(state.operationId, 120));
  if (clean(state.summary, 1)) parts.push('sum: ' + clean(state.summary, 200));
  if (clean(state.description, 1)) parts.push('desc: ' + clean(state.description, 400));
  return parts.join(' | ');
}
