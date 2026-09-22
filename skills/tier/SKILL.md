---
name: tier
description: Run the next batch of the current roadmap tier through the agent roster — at most three issues per invocation, one at a time, each routed to the lightest agent that can do it (math-editor, math-writer, source-checker, or top-researcher for a [lead]); arguments are queued for /paper:verify rather than verified here; then latex-fixer and the paper checker at the close. Resumable — the next invocation picks up where this one stopped. Use when the author says "do the next tier", "run Tier 4", or "continue the roadmap".
---

# Run one batch of a roadmap tier

The main session **briefs and relays only**; every piece of work happens in a subagent.
That is what keeps the verifying agents independent of the editing ones.

A run is **bounded**: at most **three issues**, executed **serially**, with no
verification inside it. The budget rules are in the plugin README, "Budget"; they bind
every agent this pass launches. Routing and relaying need no heavy model — this pass runs
fine from a Sonnet session, and saying so once per run is enough.

## 1. Pick the tier and the batch

Read `Drafts/comment_roadmap.md`. The target is the **first tier whose heading is not
marked `[done …]`**, unless the user named one. A heading marked
`[issues 1–k of n done …]` or `[interrupted at issue k …]` is resumed, not restarted:
read its record to see which issues are closed. Then honour what the roadmap records:

- **"Wait with Tier N"**, or any similar instruction from the author: skip it, say so,
  and move on only if the user asked for "the next tier" rather than that tier.
- **Parked items** — `[needs Roey]`, `[dropped]`, or parked in `Drafts/experiments.md`.
  Not dispatched. List them as untouched, with the reason.
- **Stated dependencies** ("needs Tier 7"). If the prerequisite is not done, report the
  item as blocked rather than attempting it.

Read the previous tier's "Open from this tier" paragraph: what is marked done there is
what this tier may rely on.

## 2. Group into issues, number them, take the first three

An **issue** is one roadmap item, or a few that stand or fall together — a statement and
the definition it needs, a lead and the lemma that settles it, all the `[apply]` items in
one section file. Number the tier's live issues in dependence order (record the
numbering under the tier heading on the first run, so later runs agree on it) and take
**the first three not yet closed**. The grouping is a routine judgement call; state it
in the report.

## 3. Route each issue to the lightest agent that can do it

| Issue content | Dispatch |
|---|---|
| only `[apply]` and mechanical `[write]` (a cross-reference, a `quest` environment, an already-verified citation, a split with the text unchanged), batched per section file | `math-editor` |
| prose `[write]`, batched per section file | `math-writer`; `figure-maker` directly for an illustration, `source-checker` directly for a new citation |
| `[verify]` on a reference | `source-checker`, one batch |
| anything containing a `[lead]` | `top-researcher`, which runs falsifier → citations → writer for it |
| `[verify]` on an argument | **not dispatched** — appended to the verification queue (§4) and counted as closed for this run |

`[lead]` writing runs on fable: `top-researcher` launches `math-writer` with the `model:
fable` override, the one override the README sanctions besides the fallback rule. When
the main session launches `math-writer` for a prose `[write]`, it passes no override.

**Briefs are short.** Point to each item by its tier heading and a quoted phrase — the
agent reads the roadmap itself. Do not paste the item, the surrounding tex or the
previous tier's history into the brief; add only what the agent cannot find: the
dependence order, the files it may touch, and what an earlier issue of this run changed.

**Serial, and a checkpoint after each.** Launch one issue, wait for it, confirm its items
are recorded in the roadmap (`[done]` with a "how", or blocked with the reason), then
launch the next. Nothing runs concurrently, so no agent is told about siblings and every
agent may build and run the checker itself.

**The session-limit stop.** If any agent returns a usage-limit or session-limit error, or
an empty result: **launch nothing further and do not relaunch it.** Write `**[interrupted at issue k YYYY-MM-DD]**` on the tier heading,
with one line on what the interrupted agent had and had not recorded, and go to §6.
Relaunching into an exhausted quota is how the Tier 3d run turned one failure into
eighteen.

A result marked **partial** because the agent reached its `maxTurns` is different: the
quota is fine and the cap did its job. Do not relaunch it or raise the cap. Record the
unfinished items in the roadmap as still open, with what the agent reported, and go on
to the next issue.

Mind the depth: the main session is layer 0, `top-researcher` layer 1, its commissions
layer 2. Verification no longer runs under a tier, so the three-deep verification chain
starts from `/paper:verify` instead.

## 4. The verification queue

Arguments are not verified inside a tier. Any agent that finishes an argument which
could be recoloured — and the main session, for a standalone `[verify]` item — appends a
line to the `## Verification queue` section at the end of `Drafts/comment_roadmap.md`:

```
- `<label>` — `<file>` — <why: new sketch / repaired proof / author's [verify]> — queued by <tier, issue>
```

Only `thm`, `prop`, `lem`, `cor` and `claim` environments with a proof are queued
automatically. A `rmk`, `fact` or `defn` is queued only when the author tagged it
`[verify]`. The author runs `/paper:verify` on the queue when they choose; it takes the
head of the queue when given no label.

## 5. Close the run

Once the last issue of the run has returned — never while one is still running:

1. If the build is not clean, dispatch `latex-fixer`.
2. Run the paper checker from the repo root and relay its output verbatim. Fix what it
   flags by dispatching the right agent, never by editing here.
3. Update the tier heading: `**[issues 1–k of n done YYYY-MM-DD]**`, or
   `**[done YYYY-MM-DD]**` when the last issue has closed — and only then with the "Open
   from this tier" paragraph and the new-notes list present.
4. When, and only when, the tier reached `[done]`, run `/paper:sweep`.

## 6. Report

The record is in the roadmap; the report is an index to it, not a copy. One table row per
issue — items, agent, files, labels touched, outcome — then, **verbatim** and only these:
every new Sketch claim, every new `\Claude` note, every **blast-radius finding** (a defect
reaching past the item it was filed under, the part most easily lost), and every label
queued for verification. Then the build before and after, the checker's output, the
items skipped and why, where the next run resumes, and every model substitution applied
at any layer. If the run was interrupted, say so in the first line. Never ask questions.
