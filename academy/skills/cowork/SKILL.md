---
name: cowork
description: 'Work a focused goal with the human (a section, a lemma chain): break it into tasks, file tagged tickets, run each next actor; the session orchestrates, the human decides. Use for "/academy:cowork <slug>", "let''s do X together".'
---

# /academy:cowork

`$ARGUMENTS`: `<slug> [--goal "..."] [--agents A] [--resume]`. Opt-in and interactive,
never autonomous: **the human leads**, and this session is the **orchestrator** under
`${CLAUDE_PLUGIN_ROOT}/references/orchestrator.md` (read it first; it is the charter:
breakdown, tickets, the next actor, the plan file, every decision to the human; never
mathematics, tex or code, never a grade, never a status). The research-focused,
autonomous counterpart is `/researcher:campaign`. Caps: `references/budget.md`
("Cowork"): `--agents` binds (default 1), the rest is advisory. The role cut is
`references/roster-rules.md`. Scripts: `$S` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`.

## 0. Open or resume

- **New**: `py $S/cowork.py new <slug> --goal "<goal>" --agents <A>` writes the plan
  file `<board>/cowork/<slug>.md` (refused if it exists: resume instead).
- **`--resume`**: read the plan file and `py $S/cowork.py status <slug>`; show the
  human the task table with each ticket's state and continue at step 3.

## 1. Breakdown, with the human

Read what the goal touches (the agenda, the registry, `claims_deps`, the tickets
already open). Propose a breakdown into focused tasks, each with: the **owning role**
(by the role cut: a new argument or a hypothesis repair is the Researcher's, landing
and form the Author's, a verification or a citation the Expert's, a computation the
Scientist's), the **deliverable**, the **dependencies** (other tasks) and the
**done-test** (what makes it delivered). Put it to the human with `AskUserQuestion`
batches (approve / change / drop, per task or per group), revise, and write the
approved table into the plan file.

## 2. Seeding (before any dispatch)

The lessons of the campaigns that were really coworks:

1. **Registry records** for every new label the plan touches: one `claims_new` through
   the owning role (a ticket to it when the record is not this home's), so a status
   can move later.
2. **Pinned statements**: `py <author plugin>/scripts/pinned.py --home <paper home>`;
   list them in the plan file. No task edits one; a change one needs is a Researcher
   task.
3. **Cited but unreadable sources**: list them; one ticket to the Expert (`cite`) for
   all of them, before any task that rests on one.
4. **Cost estimate**: tasks x runs per task x average tokens per run
   (`py $S/usage_report.py --json`), shown to the human, who confirms before step 3.
5. **The standing reviewer brief**: the paper home's `.claude/rules/`, pointed to in
   every `verify` ticket's ask.

Record each in the plan file's `## Seeding`.

## 3. Execution

- **File** one ticket per task to its owning instance, tagged `cowork: <slug>`
  (`tickets_create` field `cowork`, or `board.py new --cowork <slug>`), with `refs`,
  `agenda` and `blocks` links for the dependencies. Acting for the human who approved
  the plan, the session files as the human (`board.py new --as human`, or
  `tickets_create` with `as_human`); work a role files during its own run carries that
  role's instance. Write each ticket id into the task table.
- **Release in dependency order.** A task is released when its dependencies are
  delivered; at most `--agents` independent tickets in flight.
- **Trigger the next actor.** For each released ticket, run that role's inbox scoped
  to the cowork, `/<role>:inbox --cowork <slug>`, from that role's home (its agents
  spawned there, under its own rules). Never do the role's work in this thread, and
  never run another role's agents outside its inbox.
- **After each delivered ticket**: the checkpoint (`py <role plugin>/scripts/inbox.py
  --check T-NNNN`, which also runs the workspace's `ship.py checkpoint`), then
  `/author:sweep` if tex was touched, then update the plan file's task table and log,
  then a short status to the human. **Ask the human** (`AskUserQuestion`) before
  continuing about any hypothesis-level finding (it becomes a Researcher task), any
  decision, any re-plan.
- `py $S/cowork.py status <slug>` is the state from the tickets: `WAITING` (tickets out
  with their next actor), `PAUSE` (a decision is the human's), `DONE`.

## 4. Stop

Every task delivered or closed, or the human stops it. The close-out: a summary in the
plan file (what was delivered, what is still open and why), the remaining
non-blocking findings filed as **one** wording-batch ticket to the Author (pinned
statements in it wait for the human's release), and `status: closed` in the plan
file's header. Report the tickets, their states and the branches checkpointed.

A limit error stops the cowork at once (`budget.md` rule 4): note in the plan file what
was and was not done, and report.
