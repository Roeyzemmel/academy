# Concluding a proof review

The procedure for the concluder: the `review-chair` agent, or the main session when
`/expert:verify` runs by hand. A review fails loudly, in a verdict; a conclusion fails
silently, by leaving a finding in a transcript nothing will read again. This file is
about the second.

`$E` = `${CLAUDE_PLUGIN_ROOT}/scripts` (fallback `~/.claude/skills/expert/scripts`).
The concluder never grades: it applies `decision_table.py` and records. Its own
opinion of the mathematics never breaks a tie (`academy/references/roster-rules.md`).

## 0. Before run A

- **Take the ticket.** With a ticket: `tickets_update` it `open -> accepted ->
  in-progress` (receiver transitions). Its `budget.runs` must allow two reviewer runs
  plus you; if it does not, move it to `blocked`, `waiting_on: [human]`, with a thread
  line asking for the budget, and stop (`budget.md` rule 7).
- **Pin the statement.** `claims_show {id}` gives the statement and where it lives.
  Copy the statement text exactly as it stands (the registry's `statement`, or the
  environment's text in the file) into a scratch file and hash it:
  `py $E/reviews.py hash --file <scratch>`.
- **Open the pass.** `py $E/reviews.py new-pass <id> --ticket T-NNNN` gives the pass
  name; `py $E/reviews.py dir <id> <pass>` the folder the hook will land into.
- **The brief** (identical for A and B except `run`; paste nothing else — the
  reviewer reads the files, `budget.md` rule 9):

  > Review `<id>`: its statement and proof are at `<file:label or object + proofs/
  > attempt>`. The question: may it be raised to `proved`? Work through your
  > obligation ledger before reading the proof.
  > subject: `<id>` · pass: `<pass>` · run: `A` · statement_hash: `<hash>` ·
  > ticket: `<T-NNNN or none>`

- Write nothing in the pass folder, the registry or the board about this review while
  a run is in flight. A reviewer that could read a verdict mid-flight is no longer
  blind (the `review_blind_guard` hook enforces the reviews/ side of this).

## 1. Run A, then the table

Launch `rigor-reviewer` run A (`subagent_type: expert:rigor-reviewer`). When it
returns, the `land_verdict` hook has written `<pass dir>/A.md`. Then

    py $E/decision_table.py "<pass dir>/A.md" --json

- `launch_b: true` (A CONFIRMED on a primary, Fable or Opus 5.5): re-hash the
  statement; if the hash changed, stop — the statement moved under the review; record
  that and conclude nothing. Otherwise launch run B with the identical brief and `run: B`, telling it
  nothing of A.
- Otherwise conclude on A alone (`single-negative`, `degraded`, `disproved`,
  `incomplete`) and say in the record that B was **skipped by design**, not lost.

**A lost run.** A usage, rate or session limit: launch nothing further, record which
run was lost in the ticket thread, stop (`budget.md` rule 4). Any other stall or an
empty result: relaunch once from the same brief; the record says the kept run is the
relaunch. A second failure: conclude on what you have — the protocol needs two.

**A fallback.** Pass no `model` override while Fable is available. If it is genuinely
unavailable, relaunch with `model: opus`, name the substitution in the ticket thread
and the record. Opus 5.5 is an equal primary (roster-rules.md), so that run counts in
full; a run on any other model (Sonnet, Haiku, an older Opus) the table reads as
PLAUSIBLE, so nothing is proposed on it.

## 2. The table, input by input

After B (or instead of it):

    py $E/decision_table.py "<pass dir>/A.md" "<pass dir>/B.md" --established <ids> --json

`--established` lists the `modulo` inputs that are already established: a registry
claim whose status is `proved` (`claims_show`), or `bib:<key>#<pinpoint>` with a
card whose verdict is `match` and whose hypotheses cover the use. So first list the
inputs both runs name and mark each one: `proved`, `verified citation`, `sketch` /
`conjectured` / `open` (its status), `uncited folklore`, `cached but no card`,
`uncitable`. The script then decides whether the recolour is earned; you do not.

**Check by hand only what one grep or one definition settles**, and say in the record
which lines you checked. Where the runs differ, do not average them: say which is
sharper and why. A disagreement is reported as a finding.

## 3. The record: `<pass dir>/decision.md`

LF, Markdown, written by you:

- a heading naming the statement and **which proof** was reviewed (the file and label,
  or the proof attempt); if an older pass exists (`py $E/reviews.py list <id>`), a
  line saying which pass this one supersedes;
- the outcome, verbatim from the script (`outcome`, `summary`, `proposed_status`,
  `recolour`, `modulo`, `pending_inputs`, `anomalies`);
- both verdicts side by side: verdict, model, run id, blocking step;
- the findings **both** runs reached independently, numbered, then what they
  disagreed about and which was right;
- the input-by-input status from step 2;
- a **process note**: whether a run stalled or was relaunched, whether B was skipped
  after a negative A, whether either ran on a fallback, whether the pair was blind.

## 4. The registry and the board (MCP tools only)

1. **Evidence**, one row per landed run, append-only:
   `claims_attach_evidence {id, row: {type: "proof-review", ref: "file:<expert
   instance>/reviews/<ns>/<id-slug>/<pass>/<run>.md", verdict, run_id,
   statement_hash, note: <blocking or "">}}`.
2. **Status**, only when the script gives `proposed_status`:
   `claims_propose_status {id, status: <proposed_status>, reason: <summary>,
   grounds: <the script's grounds object>, refs: [<ticket>, <packet>]}`. This files a
   decision ticket to the claim-keeper; it sets nothing. Never call
   `claims_set_status`.
3. **Follow-ups**, from the script's `file_items`: for each `repair` or
   `verify-input`, one ticket (`tickets_create`) to the instance that owns the
   statement or input:
   - a repair to a notebook claim (an `s1:`-type claim): kind `prove`, to its
     Researcher;
   - a write-up repair to a `paper:` claim: kind `question`, to the Author, a
     neighbour;
   - a `lab:` claim: to the Researcher with `final_to: scientist`, since the
     Scientist is not a neighbour of the Expert;
   - an input that is itself a proof to review: kind `verify`, back to the Expert;
   - a missing card: kind `cite`.

   Each ticket says where the defect lives, what exactly is missing, the repair both
   runs propose, and whether a citation must come first.
4. **The packet**: `packets_create` kind `verification`, subject `[<id>]`,
   `status_before` from `claims_show`, `status_proposed` from the script, ticket set.
   `## Established vs assumed` names every input with its status; `## Evidence` the
   two records, run ids and the statement hash; `## Decisions needed` asks Roey only
   what the table leaves to him (a DISPROVED counterexample; a disagreement's next
   step; a modulo input nobody owns) — otherwise `None.`.
5. **The ticket**: `result` one line (e.g. `CONFIRMED x2; proved proposed; recolour
   earned`), `packets` set, then `in-progress -> delivered`.

## 5. The blast radius — the step most easily missed

A reviewer is briefed on one statement; its findings are not confined to one. Before
closing, for every input found defective:

- `claims_deps {id: <input>, reverse: true, transitive: true}`: what else rests on it.
- In an Author home, grep the label across the section files and count the other
  statements using it; check the home's generated statement registry for established
  statements resting on it.
- Say plainly, in the record, the packet and the report, when a repair is **not** a
  one-lemma repair. That sentence stops someone fixing one file and believing the
  matter closed.

## 6. Report

Both verdicts in the reviewers' own words; the outcome and the input-by-input status;
the blast radius first when there is one; every path, evidence row, ticket and packet
written. State plainly when the statement stays unsettled.
