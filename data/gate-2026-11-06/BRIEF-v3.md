# Labelling brief v3 — the D87 definition (chmod reading)

This brief replaces v1 (`data/calibration-2026-09-14/BRIEF.md`) and
the unused v2 for every label made from 2026-09-22 on. v1 stays
verbatim in its own directory because every label before this date
was made under it. v3 is NOT one-directional against v1: a v1 x can
become a v3 w (a change that reaches another person but can be set
back) and a v1 w can become a v3 x (a delete). So every non-r row is
relabelled under v3; v1 r labels stand.

Calibration status: practice measured 2026-09-22 — two blind
labellers agreed 97 of 100 (A: w 63 / x 36 / ? 1; B: w 64 / x 35 /
? 1). The three disputes all sat on one seam, a DELETE that removes a
membership; the user ruled the method wins (x), and the membership
bullet below was narrowed to non-DELETE methods. Holdback measured
once: two fresh labellers agreed 98 of 100 (C: w 50 / x 50; D: w 48 /
x 52), both disputes low confidence, both x by tighter-on-doubt.
BRIEF-v3 is ADOPTED 2026-09-22 for the relabel and later exams.

Amendment note: this brief was ADOPTED 2026-09-22 and AMENDED
2026-09-23 by the D98 ruling, which makes posting a comment or a
reaction w rather than x. The amendment clarifies the boundary of
clause (c) only; no other rule changes.

## The brief, verbatim

You are a blind labeller for an API-safety exam. You read API
operations and label each one r, w or x. Work alone.

Blindness — strict: open ONLY your assigned blind file and write ONLY
your assigned output file. Do NOT open, list, grep or search anything
else in the repository — no code, no docs, no other data files, no
other parts, no git history. You must not see any classifier, word
list, prior label or prior result. If you need more context, label
from the row alone and lower your confidence instead.

Each row is one HTTP operation: provider, method, path, operationId,
summary, description. Decide what happens when a caller who holds a
normal API key for this provider calls it.

The three letters mean what they mean on a file:

- r — READ. Nothing changes. A read, echo, validate, search,
  calculation, preview or dry-run. Usual for GET; it also happens on
  POST and, rarely, on PUT/DELETE/PATCH.
- w — WRITE. Something changes, and a later call of this same API can
  set it back. It does not matter whose thing it is: the caller's
  own record or another person's role, both are w if a later write
  restores the prior state. Edits, sets, renames, moves, creates,
  toggles (enable/disable, activate/deactivate, suspend/unsuspend,
  archive/unarchive, pause/resume, lock/unlock, block/unblock,
  assign/unassign, attach/detach, hide/unhide, mute/unmute), and
  stops or cancels of something that can be started again.
- x — EXECUTE. Something happened that no later write can take back.
  Deletes and removals, revokes, expires, voids, sends, publishes,
  charges, pays, refunds, runs a job. Once done, it is done.

Unsure → x.

Methods. GET, HEAD and OPTIONS are r unless the text says the call
changes something (a GET that "sends", "triggers" or "deletes" is
labelled by what it does). DELETE is x: the thing is gone. The only
DELETE that is w is one whose text says the thing goes to a trash or
recycle bin, is soft-deleted, or can be restored or undeleted by this
API. PUT and PATCH are w unless the text says the call does one of
the x things. POST has no default: label it by what it does.

  (i) A POST that only reads — a search, lookup, query, check,
      verify, match, validate, calculation, estimate, preview,
      dry-run, or an answer generated and returned but not stored —
      is r.
  (ii) A POST that creates something and does nothing else is w. A
      new record, resource, definition, container, subscription,
      webhook, key, token, file, upload or draft: it can be deleted
      again, and calling it twice makes two, which is a mess, not
      damage. Create, add, register, provision, upload, insert,
      import into own store all count as creating.
  (iii) A POST that edits, sets, moves, archives, closes, marks,
      enables, disables or otherwise changes an existing item is w,
      exactly as it would be on PUT or PATCH.
  (iv) A POST that does one of the x things is x, even when it also
      creates something: creating a message that is sent, creating a
      payment that charges, creating a run that executes, creating
      an invite that is delivered.

What cannot be undone (x). The text must say, or make plain, that one
of these happens:

  a. It deletes, removes, purges, wipes, destroys, erases, drops,
     truncates or clears a record, resource, file, message, history
     or data, and the text names no trash, restore or undelete.
     Recreating a similar thing later is not undoing: the original,
     with its id, history, links and contents, is gone.
  b. It revokes, expires, invalidates, terminates, kills, rotates or
     resets a credential, key, token, secret, certificate, session,
     password or consent. Issuing a new one is not undoing.
  c. It sends, delivers, notifies, publishes, posts or exposes
     something to a person or to the public: a message, an email, an
     SMS, a notification, a public listing. It cannot be unsent or
     unseen. Making something public counts; making it private again
     later does not undo the exposure. This clause covers what leaves
     the system and cannot be recalled — an email, an SMS, a
     notification, an invite, a public listing. It does NOT cover
     posting a comment or a reaction into a thread that this same API
     can delete: those are w.
  d. It moves money or commits to an outside party: charges, refunds,
     pays out, bills, confirms a payment or purchase, places or
     cancels an order with a carrier, registry, bank, airline or
     marketplace, renews a paid plan.
  e. It runs, triggers, executes, dispatches, syncs, imports from an
     outside source, rebuilds, re-runs or starts a job: the run
     happens and cannot be un-run, even when it touches only the
     caller's own data.
  f. It cancels, aborts or stops something whose work or state is
     lost by stopping it: a running job whose progress is discarded,
     an order, payout or transaction that cannot be re-opened, a
     state machine that cannot step back.

What can be set back (w), even when it touches another person:

  - editing plain details, settings, configuration, names, fields,
    preferences, prices, plans, templates, definitions or containers,
    yours or anyone's;
  - changing a role, permission, membership, assignment, owner or
    collaborator, when the text says nothing about a notification,
    an invite being sent, or a session being ended: the previous
    value can be set again;
  - a toggle with a named opposite in the same API (see the w list
    above). Do NOT infer an opposite the API does not offer; if the
    text names none and the thing is gone, it is x by (a);
  - a delete whose text says the thing goes to a trash or recycle
    bin, is soft-deleted, or can be restored or undeleted;
  - removing one item from a list, set or membership where adding it
    back is one more call (remove a tag from a contact, remove a
    track from a playlist) — on POST, PUT or PATCH only. On DELETE
    the method wins: a DELETE is x unless a trash or restore is named,
    even when what it removes is a membership, an assignment or a
    role. Removing the list or the item itself is x by (a);
  - stopping or pausing something that can be started again: stop own
    transcoder, pause a campaign, stop a server;
  - a plain create, per (ii).

Rules that trip people up:

- "Whose thing is it" is NOT the test. Editing another user's
  profile, role or permissions is w; deleting your own draft is x.
  Ask one thing only: after this call, can a later call put things
  back the way they were?
- Severity, sensitivity and size are NOT the test. Deleting one small
  record and deleting a whole company record are both x by (a).
  Editing sensitive personal data is w.
- A path parameter is not a reach and not a delete. {userId},
  {customerId}, {teamId} name a record. Label by what the call does
  to it.
- A cascade of edits stays w. A cascade of deletes is x by (a), and
  no more than x.
- "May", "possibly", "could affect" are not evidence. Do not infer a
  send the text does not name, and do not infer a restore the API
  does not name. "The record could be recreated" is not undoable.
- A create that the text says notifies, invites, sends, charges or
  runs is x by (iv). A create the text says nothing about is w.
- Posting a COMMENT or a REACTION is w, not x. A comment or a
  reaction can be deleted by the same API, so a later call puts
  things back the way they were, which is the whole test. Clause (c)
  does not bite here: nothing left the system that cannot be
  recalled. This covers POST reactions/create-for-team-discussion,
  POST pulls/create-review-comment, POST chatMessage.setReaction and
  POST post_comments alike. It does not change DELETE: deleting a
  comment is still x unless a trash or restore is named.
- When the row genuinely could be either AFTER applying the lists
  above, pick the TIGHTER class (x over w, w over r) and mark
  confidence low.
- If the text is contradictory or absent and you truly cannot tell,
  answer ? rather than guess.

Output format: header row_id,truth_class,confidence,reason.
truth_class is r, w, x or ?. confidence is EXACTLY high or low — there
is no medium, and a file containing any other value is rejected.
reason is a short phrase under 15 words with no commas (or the whole
reason double-quoted) and names the clause you applied, e.g.
"a deletes own record no restore", "c sends email to contact",
"w edits another users role settable back", "ii plain create of
webhook", "toggle disable has enable". One line per input row, same
order, no rows skipped, no extras.
