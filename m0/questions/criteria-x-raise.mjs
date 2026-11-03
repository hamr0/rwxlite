// poc/jev-tiers/criteria-x-raise.mjs — the D95 RAISE-TIER variant of the
// "is this operation x" criteria.
//
// It is an ABLATION of poc/jev-tiers/criteria-x.mjs, with three things removed:
//   - the method table (METHODS, (i)-(iv)), which pre-answers "PUT and PATCH
//     are w" on a pile that is all PUT/PATCH and so suppresses the raise;
//   - the tripwires (the `ignore` list), which forbid inferring;
//   - the w-side list (CAN_SET_BACK) and its examples.
// What is left states only what x IS, so the question can be answered on its
// own evidence rather than on a default that already decided it.
//
// SOLE SOURCE: data/relabel-2026-09-22/BRIEF-v3.md, as AMENDED 2026-09-23 by
// D98 (posting a comment or a reaction is w, not x). Every word of CANT_UNDO
// and of the x letter below is transcribed from that brief; nothing here is
// read from any label, key, ruling or truth file, and nothing beyond the
// brief's own words is invented.
//
// stateFor sends method, path, operationId, summary and description and
// NOTHING else — no step verdict, no tool class, no truth — so the answer is
// never anchored to the tool's own guess.

// ---- the x letter, verbatim from BRIEF-v3.md ----
const LETTERS = {
  x: 'x — EXECUTE. Something happened that no later write can take back. Deletes and removals, revokes, expires, voids, sends, publishes, charges, pays, refunds, runs a job. Once done, it is done.',
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
        definition: `${LETTERS.x} A pure read is not x.`,
        inspect: ['description', 'summary', 'operationId', 'path', 'method'],
        focus:
          'Apply the cannot-be-undone list in criteria.true. Say true only when the row does one of those things.',
      },
      criteria: {
        true: {
          what: 'The operation cannot be undone (x).',
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
          what: 'The operation does not do any of those things. Either it only reads, or a later call of the same API can set the change back.',
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
