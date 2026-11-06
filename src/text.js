// The model's input text, ported from train/common.py fmt_text and clean.
// The model was trained on exactly this string, so any change here changes
// the answers. Parity with the Python is tested in test/text.test.js against
// a fixture the Python wrote.
//
// Format: 'lean: <letter> <rule> | <METHOD> <path> | op: <operationId> | sum: <summary> | desc: <description>'
// The lean (mechanical letter and rule) goes first so truncation never cuts it.
//
// Text format 2 (manifest `textFormat: 2`) is format 1 plus one segment, 'hint: access', placed directly after the lean
// segment and only on operations accessHint() flags (grants or widens access, creates a key/token, webhook, login user,
// team member; see accessHint). Because it sits second, right behind the lean, truncation at 128 tokens never cuts it.
// Unhinted rows are byte-identical to format 1, and format 1 is today's text unchanged.

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

// Lean rule names the model never saw, read as the trained rule they behave like.
// rwxmap D131 added step-2 rule `credential-set` (class x, PUT/PATCH). Measured with the
// 0.2.0 int8-pc model on the 32 credential-set ops in data/m0/mechanical.jsonl.gz:
// as `credential-set` argmax w on 12 (3 at p >= 0.97); as `cant-undo-verb` all 32 argmax x
// (isX >= 0.9996). The lean class stays as sent. Keep: round 10 was trained on the alias text
// `cant-undo-verb` (it never saw the name `credential-set`), so the alias is part of the model's input contract.
const LEAN_RULE_ALIASES = { 'credential-set': 'cant-undo-verb' };

/** @param {string} rule */
function textRule(rule) {
  return has(LEAN_RULE_ALIASES, rule) ? LEAN_RULE_ALIASES[/** @type {keyof typeof LEAN_RULE_ALIASES} */ (rule)] : rule;
}

// ---- access hint (text format 2). Mirrors train/common.py access_hint; the patterns are shared in spirit and
// parity is tested row by row. Text is normalised first (hnorm), so every pattern is plain ASCII lower-case.
const HVERB_READ = String.raw`(?:get|list|describe|read|retrieve|fetch|check|validate|test|search|count|export|view|show|find|query|lookup|download|batch get|is|has)`;
const HVERB_OUT = String.raw`(?:remove|delete|revoke|detach|unassign|unshare|disable|deny|block|leave|decline|reject|cancel|withdraw|disassociate|deregister|unlink|clear|expire|list|get|describe|read|retrieve|fetch|check|validate|test|search|count|export|view|show|find|query|lookup|download|batch get|is|has|verify|reset|resend|rotate|refresh|login|log in|sign in|logout|log out|sign out|authenticate)`;
const HVERB_MUT = String.raw`(?:attach|add|set|put|grant|assign|invite|share|bind|update|modify|change|create|enable|replace|authorize|authorise|allow|upsert|patch|edit|register|link|transfer|promote|accept|apply|configure|reset|import|copy)`;
const HHTTP = String.raw`^(?:(?:get|post|put|patch) )?`;
const H_READ = new RegExp(String.raw`^` + HVERB_READ + String.raw`\b`);
const H_OUT = new RegExp(HHTTP + HVERB_OUT + String.raw`\b`);
const H_MUT = new RegExp(String.raw`^` + HVERB_MUT + String.raw`\b`);
const H_NARROWV = new RegExp(String.raw`^(remove|delete|revoke|detach|unassign|unshare|disable|deny|block|leave|decline|reject|cancel|withdraw|disassociate|deregister|unlink|clear|expire)\b`);
// non-access "policies" and settings that must never count as access
const H_NONACC = new RegExp(String.raw`\b(autoscal\w*|scaling|lifecycle|life cycle|retention|routing|routes?|backup|maintenance|cach\w*|refund|returns?|cancell?ation|escalation|sla|sampling|retry|rate limit\w*|throttl\w*|dunning|pricing|billing|tax|shipping|ttl|expir\w*|compliance|alert\w*|notification|schedul\w*)\b`);
const H_CORE = new RegExp(String.raw`\b(iam|acls?|permissions?|grants?|principals?|access control|shar\w+|invit\w+|collaborators?|deploy keys?|ssh keys?|roles?)\b`);
// 1. grants / widens access
const H_GRANT = new RegExp(String.raw`\b(iam|acls?|access control|permissions?|role bindings?|role assign\w*|assign\w* roles?|bind\w* roles?|(?<!pod )bindings?|grants?|share|sharing|invit\w+|collaborators?|deploy keys?|ssh keys?|authori[sz]ed keys?|(iam|resource|bucket|key|trust|queue|topic|repository|vault|registry|secret|security|sharing|authorization|access|network) polic(?:y|ies)|principals?|entitlements?|privileges?|access (?:levels?|rights?|lists?|rules?|grants?)|member (?:roles?|permissions?|access)|team (?:permissions?|access))\b`);
// 2. API key / token create
const H_CREATE = new RegExp(HHTTP + String.raw`(create|generate|issue|new|add|mint|provision|make|request|regenerate|rotate)\b`);
const H_KEYOBJ = new RegExp(String.raw`\b(api ?keys?|apikeys?|access ?keys?|secret (?:access )?keys?|(?:personal )?access tokens?|api tokens?|auth(?:entication)? tokens?|bearer tokens?|service tokens?|app(?:lication)? passwords?|passwords? credentials?|client secrets?|service account keys?|service specific credentials?|tokens?|add password|application passwords?)\b`);
const H_KEYNOT = new RegExp(String.raw`\b(login|log in|sign ?in|authenticate|refresh|oauth|exchange|introspect|verify|validate|revoke|csrf|one time|otp|presigned|pre signed|session token|id token|reset|forgot|recover|encryption keys?|kms|customer managed|two factor|2fa|qr|audit copy|verification|polic(?:y|ies)|invoices?|experiments?|snippets?|quer(?:y|ies)|sub ?accounts?|issuance|key pair|key pairs|keypair|public keys?|license keys?|sort keys?|partition keys?|key vault|keystore|key store|primary keys?|foreign keys?|cache keys?|feature flags?|object keys?|tag keys?|key values?|master keys?|data keys?|grant tokens?)\b`);
const H_SETVERB = new RegExp(HHTTP + String.raw`(enable|set|put|update|replace|import)\b`);
const H_KEYWORD = new RegExp(String.raw`\b(api ?keys?|access ?keys?|tokens?)\b`);
const H_PASSWORD = new RegExp(String.raw`\b(add|create) password\b`);
// 3. access-widening toggle
const H_WID = new RegExp(String.raw`\b(public access|publicly (?:accessible|readable|writable|visible)|make public|set public|public (?:links?|urls?|sharing|visibility|read|write|network access|endpoint)|anonymous (?:access|users?|sign ?ins?|login)|guest (?:access|users?|sharing)|external (?:sharing|access|users?|collaborat\w+)|allow (?:external|public|guest|anonymous|all|any)\w*|open (?:registration|signups?|to)|self ?(?:registration|signup|service sign ?up)|signups?|sign ups?|enable (?:public|remote|external|guest|ssh|sftp|ftp|telnet|rdp|console|serial console|link sharing|sharing|sso bypass|access|cross account|cross region access|direct access)|disable (?:mfa|2fa|two ?factor|multi ?factor|authentication|password|ssl|tls|login protection|ip restrictions?|require\w*|verification)|public access blocks?|(?<!message )visibility(?! timeout)|is public|link sharing|share link|remote access)\b`);
const H_WIDMUT = new RegExp(HHTTP + String.raw`(enable|disable|allow|set|put|update|modify|change|make|open|turn|toggle|configure|replace|edit|share|publish|expose|switch)\b`);
const H_LISTGET = new RegExp(HHTTP + String.raw`(list|get|describe)\b`);
const H_WIDNOT = new RegExp(String.raw`expir|message visibility|visibility timeout`);
// 4. webhook / subscription to an outside URL
const H_HOOK = new RegExp(String.raw`\b(web ?hooks?|(?<!lifecycle )(?<!life cycle )(?<!pre receive )hooks?|event subscriptions?|callbacks?(?: urls?)?|notification (?:urls?|endpoints?|channels?|subscriptions?|destinations?|hooks?|targets?)|event (?:destinations?|endpoints?|targets?|hooks?)|api destinations?|push (?:notifications?|channels?)|http endpoints?|endpoint urls?)\b`);
const H_HOOKMUT = new RegExp(HHTTP + String.raw`(create|add|register|set|update|configure|enable|subscribe|put|replace|edit|modify|change|insert|new|install|connect|watch|test)\b`);
const H_HOOKNOT = new RegExp(String.raw`verification|lifecycle|life cycle|signing|alerts?\b`);
const H_TEST = new RegExp(HHTTP + String.raw`test\b`);
// 5. create a login-capable user
const H_MOD = String.raw`(?:(?:a|an|the|new|another|one|more|auth|app|admin|sub|api|team|org|organization|workspace|tenant|local|portal|system|bulk|multiple|single|batch|additional|full|normal|login) ){0,3}`;
const H_USERNOUN = new RegExp(String.raw`^` + H_MOD + String.raw`(users?|login profiles?|administrators?|admins?|service accounts?|employees?|user accounts?|sub ?users?)(?= *$| (?:account|with|and|using|via|by)\b)(?! (to|for|in|on|from|as|into|of|groups?|pools?|profiles?|preferences?|attributes?|settings?|roles?|sessions?|tokens?|keys?|policy|policies|permissions?|mappings?|import|export|id|ids|name|names)\b)( |$)`);
const H_USERMUT = new RegExp(HHTTP + String.raw`(create|add|new|register|provision|invite|import|signup|sign up|admin create|bulk create|batch create|insert)\b`);
const H_USERPATH = new RegExp(String.raw`/(users|admins|administrators)/?(?![\s\S])`);
const H_USERNOT = new RegExp(String.raw`\b(import|export|search|query|lookup|list|find|verify|check|reset|sessions?|tokens?)\b`);
// 6. add a member to a team / org / project / group
const H_MEMBOBJ = new RegExp(String.raw`\b(members?|users?|collaborators?|participants?|memberships?|admins?|owners?|people|persons?|principals?)\b`);
const H_CONT = new RegExp(String.raw`\b(teams?|orgs?|organi[sz]ations?|projects?|groups?|workspaces?|spaces?|channels?|tenants?|companies|company|repos?|repositor\w+|boards?|rooms?|clusters?|domains?)\b`);
const H_MEMBMUT = new RegExp(HHTTP + String.raw`(add|create|invite|assign|join|enroll|insert|attach|batch add|bulk add)\b`);
const H_MEMBNOT = new RegExp(String.raw`\b(role|roles|permissions?|settings?|count|stats|tag|tags|mentions?|notes?|comments?|attachments?)\b`);
const H_MEMBGRP = new RegExp(String.raw`\b(users?|members?) groups?\b|\bgroups?\b.*\bgroups?\b`);
const H_MEMBER = new RegExp(String.raw`\bmembers?\b`);
const H_MEMBNOT2 = new RegExp(String.raw`\b(tags?|attachments?|comments?)\b`);
const H_MEMBPATH = new RegExp(String.raw`/(teams?|orgs?|organi[sz]ations?|projects?|groups?|workspaces?|spaces?|channels?|tenants?|companies|boards?|rooms?|repos?)/[^/]+/(members?|team_members|users?|collaborators?|memberships?|participants?|admins?|people)(/\{[^/]*\}|/\$ref)?/?(?![\s\S])|/members/\$ref(?![\s\S])|/(members|memberships|collaborators)/?(?![\s\S])`);
const H_MEMBREAD = new RegExp(String.raw`^(?:get )?(list|get|describe|read|search|query|check|count|export|update|set|replace)\b`);
const H_PATHPARAM = new RegExp(String.raw`\{[^}]*\}`);
const H_PATH_FRAGMENT = /#[^\n]*/g;
const H_PATH_PARAM = /\{[^}]*\}/g;

/** The hint's text normalisation (train/common.py _hnorm): tags out, camelCase split, lower-case, runs of non-alphanumerics to one space. @param {unknown} t */
function hnorm(t) {
  const s = (t === null || t === undefined || t === '' ? '' : String(t)).replace(/<[^>]+>/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2');
  return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').replace(/^ +| +$/g, '');
}

/**
 * train/common.py access_hint: true when the operation's own method, path, operationId and summary say it grants or
 * widens access (BRIEF-v4 / rwxmap D137: x, not w). Six families, any one is enough: (1) grants or widens access (IAM, ACL,
 * resource/bucket/key policies, role bindings, permission assignments, share, invite, deploy keys); (2) creates an API key
 * or token; (3) flips an access-widening toggle; (4) registers a webhook or subscription to an outside URL; (5) creates a
 * login user; (6) adds a member to a team, org, project or group. Non-access "policies" (autoscaling, lifecycle, retention,
 * routing) and read or revoke verbs never count. DELETE is never hinted. The description is not read.
 * @param {{method: string, path: string, operationId?: string|null, summary?: string|null}} st
 */
export function accessHint(st) {
  let m = String(st.method).toUpperCase();
  if (m === 'DELETE') return false;
  if (m === 'QUERY') m = 'GET';
  const path = String(st.path);
  const opid = (st.operationId ? String(st.operationId) : '').replace(/^(GET|POST|PUT|PATCH|DELETE)_/, '');
  const summ = st.summary ? String(st.summary) : '';
  const leads = [hnorm(opid), hnorm(summ)];                           // whole operationId, summary
  const leads2 = [hnorm(opid.split('.').pop()), hnorm(summ)];         // operationId after its last '.', summary
  const t = hnorm(opid + ' ' + summ + ' ' + path);                    // what the grant test reads
  const t2 = hnorm(opid + ' ' + summ + ' ' + path.replace(H_PATH_FRAGMENT, '').replace(H_PATH_PARAM, ''));  // path without #fragments and {params}
  const any2 = (/** @type {RegExp} */ rx) => leads2.some((x) => rx.test(x));
  const out2 = any2(H_OUT);
  const segs = path.split('/').filter((s) => s && !s.startsWith('{') && !s.startsWith('#'));
  const lastseg = segs.length ? hnorm(segs[segs.length - 1]) : '';
  const hasMut = leads.some((x) => H_MUT.test(x));
  const hasRead = leads.some((x) => H_READ.test(x)) && !hasMut;
  // 1. grants / widens access
  if (['POST', 'PUT', 'PATCH', 'GET'].includes(m) && H_GRANT.test(t) && !(H_NONACC.test(t) && !H_CORE.test(t)) && !leads.some((x) => H_NARROWV.test(x))) {
    if (m === 'GET') { if (hasMut) return true; }
    else if (!hasRead) { if (hasMut || ((m === 'PUT' || m === 'PATCH') && H_GRANT.test(lastseg))) return true; }
  }
  // 2. API key / token create
  if (any2(H_CREATE) && !out2 && !H_KEYNOT.test(t2) && !(H_SETVERB.test(leads2[0]) && !H_KEYWORD.test(t2))) {
    if (H_KEYOBJ.test(t2) || (/\bpasswords?\b/.test(t2) && H_PASSWORD.test(t2))) return true;
  }
  // 3. access-widening toggle
  if (any2(H_WIDMUT) && !H_LISTGET.test(leads2[0]) && !H_WIDNOT.test(t2) && H_WID.test(t2)) return true;
  // 4. webhook / subscription to an outside URL
  if (any2(H_HOOKMUT) && !out2 && !H_TEST.test(leads2[0]) && !H_HOOKNOT.test(t2) && H_HOOK.test(t2)) return true;
  // 5. creating a login user
  if (!out2) {
    for (const x of leads2) {
      const mm = H_USERMUT.exec(x);
      if (mm && H_USERNOUN.test(x.slice(mm[0].length).trim())) return true;
    }
    if (m === 'POST' && H_USERPATH.test(path.split('?')[0]) && !H_OUT.test(leads2[0]) && !H_USERNOT.test(t2)) return true;
  }
  // 6. adding a member to a team / org / project / group
  if (!out2) {
    for (const x of leads2) {
      const mm = H_MEMBMUT.exec(x);
      if (mm) {
        const rest = x.slice(mm[0].length).trim();
        const head = rest.split(/ +/).filter(Boolean).slice(0, 5).join(' ');
        if (H_MEMBOBJ.test(head) && !H_MEMBGRP.test(head) && (H_CONT.test(rest) || H_CONT.test(hnorm(path))) && !H_MEMBNOT.test(head)) return true;
        if (H_MEMBER.test(head) && !H_MEMBNOT2.test(head) && H_CONT.test(hnorm(path))) return true;
      }
    }
    if ((m === 'POST' || m === 'PUT') && H_MEMBPATH.test(path.split('?')[0]) && !H_MEMBREAD.test(leads2[0])) return true;
  }
  return false;
}

/**
 * @typedef {{method: string, path: string, operationId?: string|null, summary?: string|null, description?: string|null}} State
 * @typedef {{class: 'r'|'w'|'x', rule: string}} Lean
 */

/** The text formats the model has: 1 (today's) and 2 (plus the access hint). @param {unknown} f @returns {1|2} */
export function checkTextFormat(f) {
  if (f !== 1 && f !== 2) throw new Error(`rwxlite: textFormat must be 1 or 2, got ${String(f)}`);
  return f;
}

/**
 * train/common.py fmt_text: the one string the model reads. format 1 (default) is the original text; format 2 adds
 * the 'hint: access' segment right after the lean when accessHint(state) is true. The hint comes from the operation's
 * own fields, never from the caller.
 * @param {State} state
 * @param {Lean} lean
 * @param {number} [format] 1 or 2, default 1
 * @returns {string}
 */
export function formatText(state, lean, format = 1) {
  checkTextFormat(format);
  const parts = [`lean: ${lean.class} ${textRule(lean.rule)}`];
  if (format === 2 && accessHint(state)) parts.push('hint: access');
  parts.push(`${textMethod(state.method)} ${state.path}`);
  if (state.operationId) parts.push('op: ' + clean(state.operationId, 120));
  if (clean(state.summary, 1)) parts.push('sum: ' + clean(state.summary, 200));
  if (clean(state.description, 1)) parts.push('desc: ' + clean(state.description, 400));
  return parts.join(' | ');
}
