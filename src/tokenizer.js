// BERT WordPiece tokenizer, matching the checkpoint's tokenizer.json:
// BertNormalizer (clean_text, handle_chinese_chars, lowercase, accents
// stripped because strip_accents is null and lowercase is on), BertPreTokenizer,
// WordPiece ('##', [UNK], max 100 chars per word), [CLS] A [SEP], truncation
// to 128 tokens. Parity with the Python tokenizer is tested in
// test/tokenizer.test.js against ids the Python wrote.

/** @param {number} cp */
function isControl(cp) {
  if (cp === 0x09 || cp === 0x0a || cp === 0x0d) return false;
  return /\p{Cc}|\p{Cf}/u.test(String.fromCodePoint(cp));
}

/** @param {number} cp */
function isWhitespace(cp) {
  // Rust char::is_whitespace (White_Space property)
  return /\s/u.test(String.fromCodePoint(cp)) && cp !== 0xfeff
    || cp === 0x85;
}

/** @param {number} cp */
function isChinese(cp) {
  return (cp >= 0x4e00 && cp <= 0x9fff) || (cp >= 0x3400 && cp <= 0x4dbf) || (cp >= 0x20000 && cp <= 0x2a6df)
    || (cp >= 0x2a700 && cp <= 0x2b73f) || (cp >= 0x2b740 && cp <= 0x2b81f) || (cp >= 0x2b820 && cp <= 0x2ceaf)
    || (cp >= 0xf900 && cp <= 0xfaff) || (cp >= 0x2f800 && cp <= 0x2fa1f);
}

/** @param {string} ch */
function isPunct(ch) {
  const cp = /** @type {number} */ (ch.codePointAt(0));
  if ((cp >= 33 && cp <= 47) || (cp >= 58 && cp <= 64) || (cp >= 91 && cp <= 96) || (cp >= 123 && cp <= 126)) return true;
  return /\p{P}/u.test(ch);
}

/** BertNormalizer, then BertPreTokenizer: the list of words.
 * @param {string} text
 * @returns {string[]} */
export function preTokenize(text) {
  let s = '';
  for (const ch of text) {
    const cp = /** @type {number} */ (ch.codePointAt(0));
    if (cp === 0 || cp === 0xfffd || isControl(cp)) continue;
    if (isWhitespace(cp)) { s += ' '; continue; }
    s += isChinese(cp) ? ` ${ch} ` : ch;
  }
  s = s.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase();
  /** @type {string[]} */
  const words = [];
  let cur = '';
  for (const ch of s) {
    const cp = /** @type {number} */ (ch.codePointAt(0));
    if (isWhitespace(cp)) { if (cur) words.push(cur); cur = ''; } else if (isPunct(ch)) {
      if (cur) words.push(cur);
      words.push(ch); cur = '';
    } else cur += ch;
  }
  if (cur) words.push(cur);
  return words;
}

export class WordPiece {
  /** @param {string} vocabText vocab.txt contents, one token per line, in id order */
  constructor(vocabText) {
    /** @type {Map<string, number>} */
    this.vocab = new Map();
    const lines = vocabText.split('\n');
    if (lines[lines.length - 1] === '') lines.pop();
    lines.forEach((w, i) => this.vocab.set(w, i));
    const need = (/** @type {string} */ t) => {
      const id = this.vocab.get(t);
      if (id === undefined) throw new Error(`tokenizer: vocab has no ${t}`);
      return id;
    };
    this.unk = need('[UNK]'); this.cls = need('[CLS]'); this.sep = need('[SEP]'); this.pad = need('[PAD]');
  }

  /** @param {string} word @returns {number[]} */
  word(word) {
    const chars = Array.from(word);
    if (chars.length > 100) return [this.unk];
    /** @type {number[]} */
    const out = [];
    let start = 0;
    while (start < chars.length) {
      let end = chars.length; let id;
      while (start < end) {
        const sub = (start > 0 ? '##' : '') + chars.slice(start, end).join('');
        id = this.vocab.get(sub);
        if (id !== undefined) break;
        end -= 1;
      }
      if (id === undefined) return [this.unk];
      out.push(id); start = end;
    }
    return out;
  }

  /**
   * [CLS] tokens [SEP], truncated so the total is at most maxLen.
   * @param {string} text
   * @param {number} [maxLen]
   * @returns {number[]}
   */
  encode(text, maxLen = 128) {
    /** @type {number[]} */
    const ids = [];
    for (const w of preTokenize(text)) {
      for (const id of this.word(w)) ids.push(id);
      if (ids.length >= maxLen - 2) break;
    }
    return [this.cls, ...ids.slice(0, maxLen - 2), this.sep];
  }
}
