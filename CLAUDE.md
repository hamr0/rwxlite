<!-- MEMORY:START -->
@.claude/remember/MEMORY.md
<!-- MEMORY:END -->

<!-- AGENT_RULES:START -->
**One writer per piece of state.** One function assigns each field; everything else
calls it. Grep who writes it before you write it — and if a write can land from a
callback, thread, or lifecycle, the reader must tell stale from fresh.

**Surgical changes only.** Touch what the task requires. Dead code, nits, bugs you
pass: if it's inside or affects the code you're already changing and the fix changes
no behavior, fix it and say so — otherwise report it and say what it costs to leave
it. A problem you don't fix goes in the report, never in a comment.

Standards guide (read when designing/building something new, not hot context):
.claude/remember/AGENT_RULES.md
<!-- AGENT_RULES:END -->
