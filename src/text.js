// The model's input text, ported from train/common.py fmt_text and clean.
// The model was trained on exactly this string, so any change here changes
// the answers. Parity with the Python is tested in test/text.test.js against
// a fixture the Python wrote.
//
// Format: 'lean: <letter> <rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>'
// The lean (mechanical letter and rule) goes first so truncation never cuts it.

/** Named HTML entities the Python html.unescape would decode that occur in API
 * specs. Python knows about 2,200; this list covers the ones seen in the
 * training and exam corpora (test/text.test.js checks the corpus fixture). */
const NAMED = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', copy: '©', reg: '®',
  trade: '™', hellip: '…', mdash: '—', ndash: '–', lsquo: '‘', rsquo: '’',
  ldquo: '“', rdquo: '”', bull: '•', middot: '·', times: '×', rarr: '→',
  larr: '←', deg: '°', euro: '€', pound: '£', sect: '§', para: '¶',
  laquo: '«', raquo: '»', ge: '≥', le: '≤', ne: '≠', plusmn: '±',
  lbrace: '{', rbrace: '}', lbrack: '[', rbrack: ']', colon: ':', comma: ',', period: '.', sol: '/',
  bsol: '\\', num: '#', excl: '!', quest: '?', lowbar: '_', grave: '`', Hat: '^', verbar: '|',
  vert: '|', ast: '*', midast: '*', equals: '=', plus: '+', dollar: '$', percnt: '%', commat: '@',
  semi: ';', lpar: '(', rpar: ')', newline: '\n', Tab: '\t', zwj: '‍', zwnj: '‌',
};

// Python html.unescape maps these invalid numeric references (HTML5 spec).
const INVALID_CHARREFS = {
  0x00: '�', 0x0d: '\r', 0x80: '€', 0x81: '\x81', 0x82: '‚', 0x83: 'ƒ', 0x84: '„',
  0x85: '…', 0x86: '†', 0x87: '‡', 0x88: 'ˆ', 0x89: '‰', 0x8a: 'Š', 0x8b: '‹',
  0x8c: 'Œ', 0x8d: '\x8d', 0x8e: 'Ž', 0x8f: '\x8f', 0x90: '\x90', 0x91: '‘', 0x92: '’',
  0x93: '“', 0x94: '”', 0x95: '•', 0x96: '–', 0x97: '—', 0x98: '˜', 0x99: '™',
  0x9a: 'š', 0x9b: '›', 0x9c: 'œ', 0x9d: '\x9d', 0x9e: 'ž', 0x9f: 'Ÿ',
};

/** @param {string} s */
function unescapeHtml(s) {
  if (!s.includes('&')) return s;
  return s.replace(/&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[A-Za-z][A-Za-z0-9]*;)/g, (m, body) => {
    if (body[0] === '#') {
      const hex = body[1] === 'x' || body[1] === 'X';
      const n = parseInt(body.slice(hex ? 2 : 1).replace(/;$/, ''), hex ? 16 : 10);
      if (n in INVALID_CHARREFS) return INVALID_CHARREFS[n];
      if ((n >= 0xd800 && n <= 0xdfff) || n > 0x10ffff) return '�';
      return String.fromCodePoint(n);
    }
    const name = body.slice(0, -1);
    return Object.prototype.hasOwnProperty.call(NAMED, name) ? NAMED[name] : m;
  });
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
  const parts = [`lean: ${lean.class} ${lean.rule}`, `${String(state.method).toUpperCase()} ${state.path}`];
  if (state.operationId) parts.push('op: ' + clean(state.operationId, 120));
  if (clean(state.summary, 1)) parts.push('sum: ' + clean(state.summary, 200));
  if (clean(state.description, 1)) parts.push('desc: ' + clean(state.description, 400));
  return parts.join(' | ');
}
