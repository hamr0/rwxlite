// poc/jev-tiers/criteria-changes.mjs — the "does this operation change
// anything" criteria, used by the D95 `jev-raise` tier on the GET pile
// (flow.js rule 'method', class r), where a raise means r -> w or r -> x.
//
// Why a DIFFERENT question from criteria-x.mjs: the GET pile's leaks are
// truth w, not truth x. An "is this operation x" question cannot find them by
// construction — a row that is truth w answers "no" to it, which is exactly
// what a leaking r row would answer too. The question that separates the GET
// pile's leaks from its correct rows is the r boundary itself: does anything
// change at all?
//
// SOLE SOURCE: data/relabel-2026-09-22/BRIEF-v3.md, as AMENDED 2026-09-23 by
// D98 (posting a comment or a reaction is w, not x). The r definition and the
// GET/HEAD/OPTIONS line below are its basis; the w and x letters are carried
// verbatim too, because "changes something" is exactly "w or x" under this
// brief. Nothing here is read from any label, key, ruling or truth file, and
// nothing beyond the brief's own words is invented.
//
// stateFor is the same contract as criteria-x.mjs: method, path, operationId,
// summary, description and NOTHING else — no step verdict, no tool class, no
// truth, so the answer is never anchored to the tool's own guess.

// ---- the three letters, verbatim from BRIEF-v3.md ----
const LETTERS = {
  r: 'r — READ. Nothing changes. A read, echo, validate, search, calculation, preview or dry-run. Usual for GET; it also happens on POST and, rarely, on PUT/DELETE/PATCH.',
  w: 'w — WRITE. Something changes, and a later call of this same API can set it back. It does not matter whose thing it is: the caller\'s own record or another person\'s role, both are w if a later write restores the prior state. Edits, sets, renames, moves, creates, toggles (enable/disable, activate/deactivate, suspend/unsuspend, archive/unarchive, pause/resume, lock/unlock, block/unblock, assign/unassign, attach/detach, hide/unhide, mute/unmute), and stops or cancels of something that can be started again.',
  x: 'x — EXECUTE. Something happened that no later write can take back. Deletes and removals, revokes, expires, voids, sends, publishes, charges, pays, refunds, runs a job. Once done, it is done.',
};

// ---- the GET/HEAD/OPTIONS line, verbatim from BRIEF-v3.md's "Methods" ----
const GET_LINE =
  'GET, HEAD and OPTIONS are r unless the text says the call changes something (a GET that "sends", "triggers" or "deletes" is labelled by what it does).';

// ---- what counts as a change: the brief's x list (an x changes something
// and cannot be set back) and its w list (a change a later call can set
// back). Both are changes; neither is r. ----
const CANT_UNDO = {
  what: 'These change something AND cannot be undone. The text must say, or make plain, that one of them happens.',
  a: 'It deletes, removes, purges, wipes, destroys, erases, drops, truncates or clears a record, resource, file, message, history or data, and the text names no trash, restore or undelete. Recreating a similar thing later is not undoing: the original, with its id, history, links and contents, is gone.',
  b: 'It revokes, expires, invalidates, terminates, kills, rotates or resets a credential, key, token, secret, certificate, session, password or consent. Issuing a new one is not undoing.',
  c: 'It sends, delivers, notifies, publishes, posts or exposes something to a person or to the public: a message, an email, an SMS, a notification, a public listing. It cannot be unsent or unseen. Making something public counts; making it private again later does not undo the exposure. This clause covers what leaves the system and cannot be recalled — an email, an SMS, a notification, an invite, a public listing. It does NOT cover posting a comment or a reaction into a thread that this same API can delete: those are w.',
  d: 'It moves money or commits to an outside party: charges, refunds, pays out, bills, confirms a payment or purchase, places or cancels an order with a carrier, registry, bank, airline or marketplace, renews a paid plan.',
  e: 'It runs, triggers, executes, dispatches, syncs, imports from an outside source, rebuilds, re-runs or starts a job: the run happens and cannot be un-run, even when it touches only the caller\'s own data.',
  f: 'It cancels, aborts or stops something whose work or state is lost by stopping it: a running job whose progress is discarded, an order, payout or transaction that cannot be re-opened, a state machine that cannot step back.',
};

const CAN_SET_BACK = {
  what: 'These change something too; the change can be set back (w), even when it touches another person. A change that can be set back is still a change — it is not r.',
  list: [
    "editing plain details, settings, configuration, names, fields, preferences, prices, plans, templates, definitions or containers, yours or anyone's",
    'changing a role, permission, membership, assignment, owner or collaborator, when the text says nothing about a notification, an invite being sent, or a session being ended: the previous value can be set again',
    'a toggle with a named opposite in the same API (enable/disable, activate/deactivate, suspend/unsuspend, archive/unarchive, pause/resume, lock/unlock, block/unblock, assign/unassign, attach/detach, hide/unhide, mute/unmute)',
    'removing one item from a list, set or membership where adding it back is one more call (remove a tag from a contact, remove a track from a playlist)',
    'stopping or pausing something that can be started again: stop own transcoder, pause a campaign, stop a server',
    'a plain create: a new record, resource, definition, container, subscription, webhook, key, token, file, upload or draft. Create, add, register, provision, upload, insert, import into own store all count as creating',
  ],
};

// ---- what does NOT count as a change: the brief's r material ----
const NO_CHANGE = {
  what: 'Nothing changes. The call only reads.',
  list: [
    'a read, echo, validate, search, calculation, preview or dry-run',
    'a lookup, query, check, verify, match or estimate that stores nothing',
    'an answer generated and returned but not stored',
    'listing, fetching, exporting or downloading what already exists',
    'returning a computed or derived value the API does not keep',
  ],
};

// ---- "Rules that trip people up" from BRIEF-v3.md, the ones that bear on
// the r boundary (the "?" escape hatch is dropped, it has no Noul
// equivalent — see the tighter-on-doubt line instead) ----
const TRIPWIRES = [
  '"Whose thing is it" is NOT the test. A change to another user\'s profile, role or permissions is still a change; so is a change to your own draft. Ask one thing only: after this call, is anything different from before?',
  'Severity, sensitivity and size are NOT the test. A one-field edit and a whole-company delete both change something.',
  'A path parameter is not a reach and not a change. {userId}, {customerId}, {teamId} name a record. Judge by what the call does to it.',
  '"May", "possibly", "could affect" are not evidence. Do not infer a change the text does not name.',
  'Issuing, generating or returning a token, report, link or export changes something only if the text says the API stores or sends it; if it is merely computed and returned, nothing changed.',
  'When the row genuinely could be either AFTER applying the lists above, pick the TIGHTER answer: a change over no change.',
];

const FRAMING =
  'Each row is one HTTP operation. Decide what happens when a caller who holds a normal API key for this provider calls it.';

/** ONE Noul, asked cold: "does this operation change anything". */
export function questions() {
  return {
    changes: {
      type: 'noul',
      instructions: {
        framing: FRAMING,
        question: 'Does this operation change anything?',
        definition: `${LETTERS.r} ${LETTERS.w} ${LETTERS.x} A w and an x both CHANGE something; only an r changes nothing. ${GET_LINE} Unsure -> it changes something.`,
        inspect: ['description', 'summary', 'operationId', 'path', 'method'],
        focus:
          'Apply the no-change list in criteria.false and the change lists in criteria.true BEFORE instinct. The method alone is not the answer: judge by what the text says the call does.',
        ignore: TRIPWIRES,
      },
      criteria: {
        true: {
          what: 'Something is different after the call: it writes, deletes, sends, runs, charges or otherwise changes state. It is w or x, not r.',
          changes_and_cannot_be_undone: CANT_UNDO,
          changes_but_can_be_set_back: CAN_SET_BACK,
          examples: [
            'A GET whose text says it sends, triggers, resets or deletes something',
            'A call that starts, runs or dispatches a job',
            'A call that marks something read, seen, acknowledged or dismissed',
            'A call that creates or stores a record as a side effect of fetching',
            'A call that rotates, issues and stores, or invalidates a credential',
          ],
        },
        false: {
          what: 'Nothing is different after the call (r).',
          nothing_changes: NO_CHANGE,
          examples: [
            'List, get, fetch, search or export existing records',
            'Validate, check or verify input and return the result, storing nothing',
            'A preview, estimate, calculation or dry-run',
            'Download a file the API already holds',
            'Return the current status or configuration',
          ],
        },
      },
    },
  };
}

/**
 * The state sent for a row. Same contract as criteria-x.mjs: it names its
 * five fields explicitly and copies nothing else off the row, so a
 * `truth_class` field sitting beside them on the rows file can never reach
 * the model.
 * @param {object} row
 */
export function stateFor(row) {
  return {
    method: row.method,
    path: row.path,
    operationId: row.operationId,
    summary: row.summary || null,
    description: row.description || null,
  };
}
