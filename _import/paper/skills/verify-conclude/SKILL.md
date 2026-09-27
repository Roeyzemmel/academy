---
name: verify-conclude
description: Land the results of a /paper:verify pass without losing context — apply the decision table input by input, write Drafts/verdicts.md, file the modulo-inputs as tagged roadmap items, check whether a finding reaches past the verified label into other sections and the colour check, and record the process anomalies. Use as the last step of every /paper:verify, and whenever two proof-verifier reports are in hand and nothing has been written down yet.
---

# Concluding a verification

`/paper:verify` says how to *run* the two verifiers. This skill says how the pass is
**landed** once they hand back. The two jobs fail differently: a verification fails
loudly, in a verdict; a conclusion fails silently, by leaving a finding in a transcript
where nothing will ever read it again.

**Who reads this.** Normally the `master-verifier` agent, which owns a verification end
to end and carries this skill; when the main session runs `/paper:verify` by hand, it
reads this in the same seat. Either way you are called *the concluder* below. The
concluder never verifies — it adjudicates two readings it did not make, and its own
opinion of the mathematics never breaks a tie. The only edits it makes are to the
ledgers; the recolouring of an earned verdict is a LaTeX edit that `/paper:verify`
step 3 gives to `latex-fixer`, and no `sections/*.tex` is touched here.

## 0. Before the pair is dispatched

Habits that can only be established *before* the runs, each of which has been lost at
least once in practice:

- **Pick the label explicitly.** A bare `/paper:verify` has no argument: take the head
  of the `## Verification queue` section of `Drafts/comment_roadmap.md`, and say which
  label you took, before dispatching. Do not let the choice be implicit.
- **Run B only after a positive run A.** The pair runs in sequence; B is launched only
  when A returns proved or proved modulo. A negative A is concluded alone (the "single
  negative run" row of the decision table).
- **Write nothing to `Drafts/verdicts.md` while runs are in flight.** A verifier that
  reads a verdict mid-flight is no longer blind, and the pair is then worth less than it
  appears. Run both, then write.
- **A stalled or empty run is not a verdict.** A run lost to a usage or session limit is
  **not** relaunched: record the interruption and stop. Any other stall is relaunched
  once from the same brief, and the ledger records that the run you kept is the
  relaunch. If the relaunch also fails, conclude on one run and no recolouring: the
  protocol needs two.
- **Do not force the fallback.** Each agent's frontmatter carries its own model; pass no
  `model` override while the primary is available. A fallback `proof-verifier` returns
  PLAUSIBLE and can never recolour, so an override applied out of habit silently costs
  the pass its authority. If the primary is genuinely unavailable, apply the fallback
  rule deliberately and name the substitution in the report.

## 1. Apply the decision table, and name the modulo-inputs

The table is in `/paper:verify`. The case that needs care is **proved modulo X on both
runs**: it recolours only if *every* input in X is black or a verified citation.

So the conclusion is not "modulo X" — it is a **status per input**. List X explicitly
and mark each one `black`, `verified citation`, `blue`, `unreferenced folklore`,
`cached but not in references.bib`, or `uncitable`. If any is not black or verified,
the statement stays blue and those inputs are the next items (step 3).

## 2. Check what you can check by hand

A verifier's falsifiable claims are cheap to confirm and change how much weight the
write-up can carry. Before recording a finding as fact, check the ones settled by a
single grep or a single reading of a definition — then say in the ledger that the
concluder confirmed it by hand, so a later reader knows which lines are an agent's word
and which are checked. Checking a definition is not verifying the proof; do not drift
from one into the other.

Where the runs differ, do not average them. Say which is sharper and why. Two hostile
readings that differ have found an ambiguity in the write-up even when the mathematics
is fine, so the disagreement is itself a finding and is reported as one.

## 3. File the inputs as roadmap items

The decision table says the inputs "become the next `[verify]` items" in one clause and
stops there. Landing that means editing `Drafts/comment_roadmap.md`:

- Amend the item that asked for the verification so it records the **outcome**, with a
  `[done YYYY-MM-DD]` bullet pointing at `Drafts/verdicts.md`. Do not delete the
  original item; the sweep and later readers need the history.
- Add one `[verify, blocking]` bullet **per input** in X that is not black or verified.
  Each says where the input lives (`file.tex:lines`), what exactly is wrong or missing,
  the repair both runs propose, and whether the repair needs a `/paper:cite` first.
- Add `[apply]` bullets for repairs the runs agree are short and **do not** block the
  colour, so they are not mistaken for blockers.
- Add `[note, lead]` for anything the runs found that strengthens or simplifies a
  statement rather than repairing it.

File under the tier that owns the file, per the project's existing convention.

## 4. The blast radius — the step most easily missed

A verifier is briefed on **one label**. Its findings are not confined to one label, and
the most valuable thing a pass produces is often a defect in something the verifiers
were never asked about — a definition used across several sections, a citation that does
not say what it was taken to say, a hypothesis silently inherited.

So before closing, for every input found defective:

- Grep the label across `sections/` and count the *other* statements that use it.
- Check `Drafts/statements.md` and the roadmap's colour-check block, if the project keeps
  one, for established statements resting on it — a defective blue input may already sit
  under an `[apply]` item that this verification has just re-scoped.
- Check the project's accepted baseline: a finding outside it is a regression and blocks
  a commit.
- Say plainly in both the ledger and the roadmap when a repair is **not** a one-lemma
  repair. That sentence is what stops someone fixing one file and believing the matter
  closed.

## 5. Write `Drafts/verdicts.md`

Newest first, in the file's existing shape. **Check the file's line endings and preserve
them** — ledgers are not uniform across a project, and writing a CRLF file through a
CRLF-translating write doubles every carriage return. Beyond the skeleton in
`/paper:verify`, the entry carries:

- a heading that says **which proof** was verified when a rewrite has happened, and an
  opening line marking the older entry **superseded**. A verdict on a proof that has
  since been deleted is not evidence about the current one, and the ledger must not read
  as though it is.
- the findings **both** runs reached independently, numbered — this is what
  `note-sweeper` reads to decide a "blue because unverified" note is answered;
- what the runs **disagreed** about, and which was right;
- a **process note**: whether a run stalled and was relaunched, whether run B was
  skipped after a negative run A, whether the pair was genuinely blind, and whether
  either ran on a fallback.

Then remove the label's line from the `## Verification queue` section of the roadmap,
whatever the outcome; a repair filed in step 3 re-queues it once the repair lands.

**The claim registry, if the project keeps one.** When the project's
`.claude/flatsurf.json` names a `claims.py` registry, dispatch one
`flatsurf:claim-keeper` with `paper:<label>`, the outcome, and the entry you just wrote as
its grounds. It adds the verdict as evidence and a history line, and changes the status
only as the outcome warrants: recoloured → `proved` / `proved-modulo`; disproved →
`refuted` or `refuted-as-stated`; stays blue → evidence only. It never recolours the
draft; that stays with `latex-fixer`. Name what it changed in the report.

## 6. Report

Per `/paper:verify` step 5: both verdicts in the verifiers' own words, the decision the
table gives, the recolouring if earned, and the input-by-input status. Add two things
that skill does not ask for:

- the **blast radius** sentence, if any;
- where you wrote things, as paths, so the author can check the filing rather than take
  it on trust.

State plainly that the statement stays blue when it does. A modulo verdict is a real
result — it converts an unknown into a named, filed obligation — and reporting it as a
near-miss misrepresents what the pass bought.
