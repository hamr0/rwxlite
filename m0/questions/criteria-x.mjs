// poc/jev-tiers/criteria-x.mjs — the "is this operation x" criteria, used by
// BOTH D95 tiers that turn on the x boundary:
//   jev-lower   floor-post rows (class x)        may lower x -> w only
//   jev-raise   method-floor rows (class w)      may raise w -> x only
// The two tiers are INDEPENDENT and keep their own ledgers (D95); they share
// this question only because it is the same boundary read from either side.
//
// SOLE SOURCE: data/relabel-2026-09-22/BRIEF-v3.md, as AMENDED 2026-09-23 by
// D98 (posting a comment or a reaction is w, not x). Every word of CANT_UNDO,
// CAN_SET_BACK, METHODS and TRIPWIRES below is transcribed from that brief;
// nothing here is read from any label, key, ruling or truth file, and nothing
// beyond the brief's own words is invented.
//
// Unlike poc/jev-d87/criteria.mjs (which carries the PRE-amendment clause (c)
// and drops the method material because its pile was all POST), this file
// KEEPS the brief's method table and its r definition: these piles hold POST,
// PUT and PATCH rows, so the method defaults are part of the question.
//
// stateFor sends method, path, operationId, summary and description and
// NOTHING else — no step verdict, no tool class, no truth — so the answer is
// never anchored to the tool's own guess.

// ---- the three letters, verbatim from BRIEF-v3.md ----
const LETTERS = {
  r: 'r — READ. Nothing changes. A read, echo, validate, search, calculation, preview or dry-run. Usual for GET; it also happens on POST and, rarely, on PUT/DELETE/PATCH.',
  w: 'w — WRITE. Something changes, and a later call of this same API can set it back. It does not matter whose thing it is: the caller\'s own record or another person\'s role, both are w if a later write restores the prior state. Edits, sets, renames, moves, creates, toggles (enable/disable, activate/deactivate, suspend/unsuspend, archive/unarchive, pause/resume, lock/unlock, block/unblock, assign/unassign, attach/detach, hide/unhide, mute/unmute), and stops or cancels of something that can be started again.',
  x: 'x — EXECUTE. Something happened that no later write can take back. Deletes and removals, revokes, expires, voids, sends, publishes, charges, pays, refunds, runs a job. Once done, it is done.',
  doubt: 'Unsure -> x.',
};

// ---- "Methods", verbatim from BRIEF-v3.md ----
const METHODS = {
  what: 'GET, HEAD and OPTIONS are r unless the text says the call changes something (a GET that "sends", "triggers" or "deletes" is labelled by what it does). DELETE is x: the thing is gone. The only DELETE that is w is one whose text says the thing goes to a trash or recycle bin, is soft-deleted, or can be restored or undeleted by this API. PUT and PATCH are w unless the text says the call does one of the x things. POST has no default: label it by what it does.',
  i: 'A POST that only reads — a search, lookup, query, check, verify, match, validate, calculation, estimate, preview, dry-run, or an answer generated and returned but not stored — is r.',
  ii: 'A POST that creates something and does nothing else is w. A new record, resource, definition, container, subscription, webhook, key, token, file, upload or draft: it can be deleted again, and calling it twice makes two, which is a mess, not damage. Create, add, register, provision, upload, insert, import into own store all count as creating.',
  iii: 'A POST that edits, sets, moves, archives, closes, marks, enables, disables or otherwise changes an existing item is w, exactly as it would be on PUT or PATCH.',
  iv: 'A POST that does one of the x things is x, even when it also creates something: creating a message that is sent, creating a payment that charges, creating a run that executes, creating an invite that is delivered.',
};

// ---- the x side: "What cannot be undone (x)" from BRIEF-v3.md ----
// Clause (c) below is the AMENDED (2026-09-23, D98) text.
const CANT_UNDO = {
  what: 'The text must say, or make plain, that one of these happens.',
  a: 'It deletes, removes, purges, wipes, destroys, erases, drops, truncates or clears a record, resource, file, message, history or data, and the text names no trash, restore or undelete. Recreating a similar thing later is not undoing: the original, with its id, history, links and contents, is gone.',
  b: 'It revokes, expires, invalidates, terminates, kills, rotates or resets a credential, key, token, secret, certificate, session, password or consent. Issuing a new one is not undoing.',
  c: 'It sends, delivers, notifies, publishes, posts or exposes something to a person or to the public: a message, an email, an SMS, a notification, a public listing. It cannot be unsent or unseen. Making something public counts; making it private again later does not undo the exposure. This clause covers what leaves the system and cannot be recalled — an email, an SMS, a notification, an invite, a public listing. It does NOT cover posting a comment or a reaction into a thread that this same API can delete: those are w.',
  d: 'It moves money or commits to an outside party: charges, refunds, pays out, bills, confirms a payment or purchase, places or cancels an order with a carrier, registry, bank, airline or marketplace, renews a paid plan.',
  e: 'It runs, triggers, executes, dispatches, syncs, imports from an outside source, rebuilds, re-runs or starts a job: the run happens and cannot be un-run, even when it touches only the caller\'s own data.',
  f: 'It cancels, aborts or stops something whose work or state is lost by stopping it: a running job whose progress is discarded, an order, payout or transaction that cannot be re-opened, a state machine that cannot step back.',
};

// ---- the w side: "What can be set back (w)" from BRIEF-v3.md ----
const CAN_SET_BACK = {
  what: 'What can be set back (w), even when it touches another person.',
  list: [
    "editing plain details, settings, configuration, names, fields, preferences, prices, plans, templates, definitions or containers, yours or anyone's",
    'changing a role, permission, membership, assignment, owner or collaborator, when the text says nothing about a notification, an invite being sent, or a session being ended: the previous value can be set again',
    'a toggle with a named opposite in the same API (enable/disable, activate/deactivate, suspend/unsuspend, archive/unarchive, pause/resume, lock/unlock, block/unblock, assign/unassign, attach/detach, hide/unhide, mute/unmute). Do NOT infer an opposite the API does not offer; if the text names none and the thing is gone, it is x by (a)',
    'a delete whose text says the thing goes to a trash or recycle bin, is soft-deleted, or can be restored or undeleted',
    'removing one item from a list, set or membership where adding it back is one more call (remove a tag from a contact, remove a track from a playlist) — on POST, PUT or PATCH only. On DELETE the method wins: a DELETE is x unless a trash or restore is named, even when what it removes is a membership, an assignment or a role. Removing the list or the item itself is x by (a)',
    'stopping or pausing something that can be started again: stop own transcoder, pause a campaign, stop a server',
    'a plain create, per (ii)',
  ],
};

// ---- "Rules that trip people up" from BRIEF-v3.md (the ones a cold binary
// question can use; the "?" escape hatch is dropped, it has no Noul
// equivalent — see "Unsure -> x" in LETTERS instead) ----
const TRIPWIRES = [
  '"Whose thing is it" is NOT the test. Editing another user\'s profile, role or permissions is w; deleting your own draft is x. Ask one thing only: after this call, can a later call put things back the way they were?',
  'Severity, sensitivity and size are NOT the test. Deleting one small record and deleting a whole company record are both x by (a). Editing sensitive personal data is w.',
  'A path parameter is not a reach and not a delete. {userId}, {customerId}, {teamId} name a record. Label by what the call does to it.',
  'A cascade of edits stays w. A cascade of deletes is x by (a), and no more than x.',
  '"May", "possibly", "could affect" are not evidence. Do not infer a send the text does not name, and do not infer a restore the API does not name. "The record could be recreated" is not undoable.',
  'A create that the text says notifies, invites, sends, charges or runs is x by (iv). A create the text says nothing about is w.',
  'Posting a COMMENT or a REACTION is w, not x. A comment or a reaction can be deleted by the same API, so a later call puts things back the way they were, which is the whole test. Clause (c) does not bite here: nothing left the system that cannot be recalled. This covers POST reactions/create-for-team-discussion, POST pulls/create-review-comment, POST chatMessage.setReaction and POST post_comments alike. It does not change DELETE: deleting a comment is still x unless a trash or restore is named.',
  'When the row genuinely could be either AFTER applying the lists above, pick the TIGHTER class (x over w, w over r).',
];

const FRAMING =
  'Each row is one HTTP operation. Decide what happens when a caller who holds a normal API key for this provider calls it.';

/** ONE Noul, asked cold: "is this operation x". */
export function questions() {
  return {
    isX: {
      type: 'noul',
      instructions: {
        framing: FRAMING,
        question: 'Is this operation x?',
        definition: `${LETTERS.r} ${LETTERS.w} ${LETTERS.x} ${LETTERS.doubt} "Whose thing it is" is NOT a test. A pure read is not x.`,
        inspect: ['description', 'summary', 'operationId', 'path', 'method'],
        focus:
          'Apply the method defaults in criteria.true.methods, then the cannot-be-undone list in criteria.true and the can-set-back list in criteria.false, BEFORE instinct. They settle the disputed rows and override a first impression.',
        ignore: TRIPWIRES,
      },
      criteria: {
        true: {
          what: 'The operation cannot be undone (x).',
          methods: METHODS,
          cannot_be_undone: CANT_UNDO,
          examples: [
            'Delete a record, the text names no trash or restore (a)',
            'Revoke a credential, key, token or consent (b)',
            'Send a message, email or notification to a person (c)',
            'Charge a payment or refund one (d)',
            'Trigger a pipeline run or sync (e)',
            'Cancel a running job whose progress is lost by stopping it (f)',
            'A create that also sends an invite, charges a card, or runs a job (iv)',
          ],
        },
        false: {
          what: 'A later call of the same API can set the change back (w), or the call only reads (r). Either way it is not x.',
          can_be_set_back: CAN_SET_BACK,
          examples: [
            "Edit another user's role, no notification or session-end named",
            'Toggle disable, the same API also offers an enable',
            'A plain create of a webhook, the text says nothing else (ii)',
            'Remove one tag from a contact, not the whole list, on POST, PUT or PATCH',
            'Pause a campaign or stop a transcoder, either can be started again',
            'Post a comment or a reaction into a thread this same API can delete',
            'A PUT or PATCH that edits plain fields, the text names no x thing',
            'A POST that only searches, validates or previews and stores nothing (i)',
          ],
        },
      },
    },
  };
}

/**
 * The state sent for a row. Deliberately no step verdict, no tool class and
 * no truth: it names its five fields explicitly and copies nothing else off
 * the row, so a `truth_class` field sitting beside them on the rows file can
 * never reach the model.
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
