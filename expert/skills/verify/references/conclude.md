# Concluding a proof review

The procedure for the concluder: the `review-chair` agent in the stages of the
`academy-verify` workflow (`workflows/verify.js`), or the main session when
`/expert:verify` runs by hand. In the workflow, **the script launches the runs and holds
sections 1, 1a and 7.5** (A, then the falsifier, B only on `launch_b` with an unchanged
hash and a falsifier that found nothing, the identical brief, one relaunch, a lost run
stops the pass); the chair's stages are *prepare* (section 0, or 7.1-7.4), *table* (the
`decision_table.py <run>.md --json` check of section 1), *falsifier* (section 1a) and
*conclude* (sections 2-6, or 7.6-7.7). Section 1 below is the by-hand
route. A review fails loudly, in a verdict; a conclusion fails
silently, by leaving a finding in a transcript nothing will read again. This file is
about the second.

`$E` = `${CLAUDE_PLUGIN_ROOT}/scripts` (fallback `~/.claude/skills/expert/scripts`).
The concluder never grades: it applies `decision_table.py` and records. Its own
opinion of the mathematics never breaks a tie (`academy/references/roster-rules.md`).

## 0. Before run A

- **Take the ticket.** With a ticket: `tickets_update` it `open -> accepted ->
  in-progress` (receiver transitions). The review costs two reviewer runs plus you;
  that cost is the route's, counted by the run that launched you (`budget.md` rule 7).
  The ticket's own `budget` field gates nothing: never block a ticket to ask for budget.
- **Pin the statement.** `claims_show {id}` gives the statement and where it lives. For
  a statement of a tex file, `py <academy repo>/author/scripts/statement.py <label>
  --where --home <the Author home>` prints its file and the line ranges of the statement
  and its proof; that line is the brief's location (2026-11-13: a brief that named only
  the file sent the reviewer, who has no shell, to a 160 000-character section it
  cannot read whole).
  Hash it through the registry engine: `py $E/reviews.py hash --claim <id>`. That is
  the hash `claims_set_status` checks the verdicts against: for a notebook record the
  `## Statement` section *with* its heading line, for a paper label the whole
  environment, `\begin`/`\label`/`\end` included. Never hash a hand-copied extract
  (`hash --file`): the section body without its heading, or an environment's body,
  hashes differently, and a pass pinned on it cannot ground a status (T-0464, T-1179;
  T-0463 and T-0568 were refused on exactly that).
- **Passes pinned on a hand-copied extract** (before 2026-11-16, T-0464). Older run
  records may carry the hash of the section body without its heading, or of an
  environment's body. To tell: the run's `statement_hash` differs from
  `reviews.py hash --claim <id>` but equals `reviews.py hash --file` of the current
  statement with the heading line (or `\begin`/`\label`/`\end`) removed. Then the text
  did not change, but `claims_set_status` refuses those verdicts. A landed run record is
  never rewritten or re-pinned. A pass of that kind needs nothing until a status
  rests on it; then either a fresh blind pass (as for T-0568), or the human sets the
  status on his word citing the pass (as for T-1179). A hash that matches neither
  means the statement changed: section 7 or a fresh pass, as always.
- **Open the pass.** `py $E/reviews.py new-pass <id> --ticket T-NNNN` gives the pass
  name; `py $E/reviews.py dir <id> <pass>` the folder the hook will land into. Never
  two concurrent passes on one statement: `new-pass` refuses while another pass on
  `<id>` is open (no `decision.md`), except the one open pass of this same ticket, which
  it returns (a rerun on another day resumes it, #89: list the runs already landed there
  with their statement_hash, so the workflow tables them instead of relaunching). Conclude
  another ticket's pass first, or, if it is dead (a
  stalled run, a changed statement), close it with
  `py $E/reviews.py abandon <id> <pass> --reason "..."` and say so in the thread.
- **Report the falsifier on record** (a blind pass; section 1a uses it after A). The
  sources are the ones `researcher/workflows/prove.js` accepts (#117): a falsifier that
  attacked this claim (an experiment or test ticket to the Scientist that tried to break
  it, or a recorded attack); one recorded on a declared input, or on the parent lead or
  direction item, whose class or statement covers the claim (say how, and name the id);
  the ticket's thread (the falsifier request this ticket waited on, once it is back, with
  its result); or the human's waiver on the ticket or the claim (quote the thread line
  `- YYYY-MM-DD human: ...` verbatim). Say what it found (nothing, or a counterexample),
  the statement hash it attacked when its record says it (a request this workflow filed
  names it in its ask), any falsifier request the ticket already filed with its status, and
  the claim's declared inputs. A ticket blocked by an earlier run of this pass (awaiting its falsifier) is taken
  `blocked -> in-progress`.
- **The brief** (identical for A and B except `run`; paste nothing else — the
  reviewer reads the files, `budget.md` rule 9):

  > Review `<id>`: its statement and proof are at `<for a tex file: the line of
  > statement.py --where, i.e. file, statement lines A-B, proof lines C-D; else the
  > object + proofs/ attempt>`. The question: may it be raised to `proved`? Work through your
  > obligation ledger before reading the proof.
  > subject: `<id>` · pass: `<pass>` · run: `A` · statement_hash: `<hash>` ·
  > ticket: `<T-NNNN or none>`

- Write nothing in the pass folder, the registry or the board about this review while
  a run is in flight. A reviewer that could read a verdict mid-flight is no longer
  blind (the `review_blind_guard` hook enforces the reviews/ side of this).

## 1. Run A, then the table (by hand; in the workflow the script does this)

Launch `rigor-reviewer` run A (`subagent_type: expert:rigor-reviewer`). When it
returns, the `land_verdict` hook has written `<pass dir>/A.md`. Then

    py $E/decision_table.py "<pass dir>/A.md" --json

- `launch_b: true` (A CONFIRMED on one of the grading primaries (`grading.primaryModels`)): re-hash the
  statement (`py $E/reviews.py hash --claim <id>`, as in section 0); if the hash changed, stop — the statement moved under the review; record
  that and conclude nothing. Otherwise the falsifier comes first (section 1a); once it is on
  record and found nothing, launch run B with the identical brief and `run: B`, telling it
  nothing of A.
- Otherwise conclude on A alone (`single-negative`, `degraded`, `disproved`,
  `incomplete`) and say in the record that B was **skipped by design**, not lost.

**A lost run.** A usage, rate or session limit: launch nothing further, record which
run was lost in the ticket thread, stop (`budget.md` rule 4). Any other stall or an
empty result: relaunch once from the same brief; the record says the kept run is the
relaunch. A second failure: conclude on what you have — the protocol needs two.

**A fallback.** Pass no `model` override while the agent's own model is available. If
it is genuinely unavailable, relaunch with the agent's frontmatter `fallback`, and name
the substitution in the ticket thread and the record. A run on any of the grading
primaries (`grading.primaryModels`, roster-rules.md) counts in full; a run on any other
model the table reads as PLAUSIBLE, so nothing is proposed on it.

## 1a. The falsifier, between A and B

A falsifier counts only on this statement's hash. Most falsifiers recorded before this
rule (2026-11-20) name no hash, so they do not count: such a claim gets a new falsifier
request (only the human's waiver counts without a hash).

The human's design (2026-11-20): the order is **attempt, run A, the falsifier, run B**. A
falsifier (an experiment or test that tries to break the claim) is spent only on a proof
that survived A. It runs only after a CONFIRMED A with `launch_b` and an unchanged hash;
a negative A concludes on A alone, and a reword pass has no falsifier stage.

- **On record and found nothing** (section 0's sources, checked by the script as
  prove.js checks them: evidence given, an input that is a declared input, a waiver
  quoting the human's thread line): B is launched at once. What counts is checked in code:
  a falsifier counts only when it found `nothing` (or a `counterexample`, below; an empty
  or other answer does not count), a falsifier request only once it is `delivered` or
  `closed`, and only on the statement hash the pass reviews: one recorded on another hash
  never counts, one whose hash is unknown counts only as the human's waiver (with a note).
  The request this stage files names the hash in its ask, so its result carries it.
- **No verify ticket** (`/expert:verify` by hand with none): the pass cannot wait, since
  nothing could resume it (`reviews.py` resumes a ticket's own pass only). The falsifier
  stage is skipped, the record's process notes say so, and B runs as before.
- **None on record**: launch no B. File one falsifier request: `tickets_create` kind
  `research` to the Researcher that `py $E/reviews.py researcher-for <id> --party <instance>...`
  names (the prepare stage runs it, a `--party` for the `from` and `to` of the ticket and of
  each ticket up its parent chain). The rule, in code (`decision_table.researcher_for`): the
  Researcher owning the claim's namespace; else (a `paper:` or `lab:` claim) the one
  Researcher owning a namespace of the claim's `bears_on`; else the one Researcher in the
  ticket's parent chain; none, or several at one step, is the human's call: file nothing and
  block the ticket `waiting_on: [human]` with the script's reason. `final_to: scientist`
  (the Expert is no neighbour of the Scientist; the Researcher's `experiment-spec` relays
  it; review-chair is an expert->researcher liaison), `parent` and `refs` the verify
  ticket and the claim. It asks for an experiment or test that tries to break the claim
  and for what it found. It never states A's verdict, its findings or anything of the pass
  folder: B stays blind. Then block the verify ticket `waiting_on` the request, with a
  thread note naming it and the open pass. A refused `tickets_create` blocks the ticket
  `waiting_on: [human]` with the refusal. The pass stays open (no `decision.md`); the
  workflow returns `awaiting-falsifier`.
- **A request already filed** by an earlier run of this pass: file nothing. Still out:
  block the ticket on it again. Back with no falsifier that counts: block the ticket
  `waiting_on: [human]` (another falsifier, or a waiver, is the human's call).
- **The rerun.** Once the request is back the Expert's inbox releases the verify ticket
  (`inbox.py`: a `released` row, `blocked -> accepted`; a request that was rejected or
  cancelled releases it to the human instead, never into B) and it is run again:
  `new-pass` returns the same open pass (#89), A is tabled, not relaunched, and the
  falsifier is read from the request's result (source `ticket`).
- **A counterexample.** B is not launched and no status changes: never
  `claims_propose_status`. Write the record (A's table, the falsifier and its evidence,
  the process notes), the evidence row for A, and route the counterexample as every
  counterexample is routed (section 4.3; `decision_table.follow_up`, kind
  `counterexample`): one `decision` ticket to the human, at once, with the counterexample
  and where it is recorded. What becomes of the claim (a weaker statement, a repair through
  the Researcher) is the human's call. The packet puts the counterexample in
  `## Decisions needed`; the ticket is delivered. The outcome is
  `falsifier-counterexample`.

## 2. The table, input by input

After B (or instead of it):

    py $E/decision_table.py "<pass dir>/A.md" "<pass dir>/B.md" --established <ids> --json

`--established` lists the `modulo` inputs that are already established: a registry
claim whose status is `proved` (`claims_show`), or `bib:<key>#<pinpoint>` with a
card whose verdict is `match` and whose hypotheses cover the use. So first list the
inputs both runs name and mark each one: `proved`, `verified citation`, `sketch` /
`conjectured` / `open` (its status), `uncited folklore`, `cached but no card`,
`uncitable`. The script then decides whether the recolour is earned; you do not.

**Definitions are not inputs** (the human's decision, 2026-10-09, T-0148): a
definition used only as notation is not an input in a verdict's modulo list; only a
definition whose content the argument relies on counts. The script applies it: when two
CONFIRMED runs' modulo lists differ only in definitions (registry kind `definition`,
else a `defn:` / `DEF-` label), it reads them as agreeing on the intersection and lists
the dropped ids in `dropped_definitions`. Copy that list into the record; do not list a
dropped definition among the inputs.

**Check by hand only what one grep or one definition settles**, and say in the record
which lines you checked. Where the runs differ, do not average them: say which is
sharper and why. A disagreement is reported as a finding.

## 3. The record: `<pass dir>/decision.md`

LF, Markdown, written by you:

- a heading naming the statement and **which proof** was reviewed (the file and label,
  or the proof attempt); if an older pass exists (`py $E/reviews.py list <id>`), a
  line saying which pass this one supersedes;
- the outcome, verbatim from the script (`outcome`, `summary`, `proposed_status`,
  `recolour`, `modulo`, `pending_inputs`, `dropped_definitions`, `anomalies`);
- both verdicts side by side: verdict, model, run id, blocking step;
- the findings **both** runs reached independently, numbered, then what they
  disagreed about and which was right;
- the input-by-input status from step 2;
- a **process note**: whether a run stalled or was relaunched, whether B was skipped
  after a negative A, whether either ran on a fallback, whether the pair was blind.

## 4. The registry and the board (MCP tools only)

1. **Evidence**, one row per landed run, append-only:
   `claims_attach_evidence {id, row: {type: "verdict", ref: "file:<expert
   instance>/reviews/<ns>/<id-slug>/<pass>/<run>.md", verdict, run_id,
   statement_hash, note: <blocking or "">}}`.
2. **Status**, only when the script gives `proposed_status`:
   `claims_propose_status {id, status: <proposed_status>, reason: <summary>,
   grounds: <the script's grounds object>, refs: [<ticket>, <packet>]}`. This files a
   decision ticket to the claim-keeper; it sets nothing. Never call
   `claims_set_status`.
3. **Follow-ups**, from the script's `file_items`: every item carries its `route`
   (`kind`, `to_role`, `final_to`, `gap_class`), computed by the role cut
   (`academy/references/roster-rules.md`, rule 3). File one ticket (`tickets_create`)
   per item, as routed; never re-route one by your own reading:
   - a `hypothesis`, `statement` or `proof` finding, on any claim (a `paper:` claim
     included): kind `prove`, to the Researcher of the claim's domain, with the
     falsifier the run gave. **Never an Author `apply` or `write` ticket**: the
     Researcher proves, the Author only lands what comes back;
   - a `wording` finding alone: kind `question`, to the statement's owner (the
     Author for a `paper:` claim). A pinned statement (`author/scripts/pinned.py`)
     is not edited for wording: the ticket says it waits for the human's batch;
   - a `lab:` claim: to the Researcher with `final_to: scientist`, since the
     Scientist is not a neighbour of the Expert;
   - an input that is itself a proof to review: kind `verify`, back to the Expert;
   - a counterexample, from a DISPROVED run or from the falsifier of section 1a, or runs
     that disagree on the inputs: a `decision` ticket to the human (the one rule for a
     counterexample; never a `prove` ticket);
   - a missing card: kind `cite`.

   Each ticket says where the defect lives, what exactly is missing, the repair both
   runs propose, and whether a citation must come first.
4. **The packet**: `packets_create` kind `verification`, subject `[<id>]`,
   `status_before` from `claims_show`, `status_proposed` from the script, ticket set
   (required: `title`, `kind`, and `body` or `sections`; each decision is
   `### Dk. question`, 2-4 `- (a) option` lines and a `- Recommendation:` line;
   docs/packet-template.md section 3).
   `## Established vs assumed` names every input with its status; `## Evidence` the
   two records, run ids and the statement hash; `## Decisions needed` asks the human only
   what the table leaves to them (a DISPROVED counterexample; a disagreement's next
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

## 7. A reword pass (one informed run, T-0347)

The human's rule (2026-10-12, T-0347, verbatim): "A statement that was re-worded should get a
verifier with some access to the rewording recommending'a chain of thought, as the proof
does not require a new proof from scratch". The design chosen: one informed run.

**When.** The statement's text changed (its hash differs) after a pass whose
`decision.md` records `confirmed` or `confirmed-modulo` on the old hash, and the proof is
unchanged or changed only in wording. Typically: a wording finding, a notation pass, a
restatement that drops a redundant hypothesis. **Not** when the proof changed in
substance, when the base pass was anything but CONFIRMED x2, or when the rewording
answers a hypothesis / statement / proof finding: those take a full blind pass
(sections 0-6).

**Steps** (`$E` as above; scratch files in the session scratchpad, never under
`reviews/`):

1. Take the ticket as in section 0. The cost is one reviewer run plus you.
2. Recover the statement **as the base pass reviewed it** (its `decision.md` names
   which file and label; `git show <commit>:<file>` from the commit before the
   rewording) into `old.txt`, in the form the base pass hashed (the engine's text: a
   notebook record's `## Statement` section with its heading line, a paper label's
   whole environment; a base pass pinned before T-0464 may have hashed the body alone,
   see "Passes pinned on a hand-copied extract" in section 0). `py $E/reviews.py hash --file old.txt` must equal the base runs'
   `statement_hash`. The current statement needs no file: `reword-brief` takes it from
   the registry, and its hash is `py $E/reviews.py hash --claim <id>`.
3. Open the pass: `py $E/reviews.py new-pass <id> --reword-of <base pass> --ticket
   T-NNNN`. It refuses unless the base pass is CONFIRMED x2 (by its own table) and not
   abandoned; the name ends in `-reword`.
4. Write the bundle: `py $E/reviews.py reword-brief <id> <pass> --old-file old.txt
   --findings <file or "T-NNNN: one line"> ... --out
   <scratch>/bundle.md`. It refuses when `old.txt` is not the reviewed statement or the
   statement did not change. A `--new-file`/`--new-text` is still accepted (when the
   registry cannot read the record), but refused when it does not hash like the
   registry's statement.
5. Launch `rigor-reviewer` once, with the brief:

   > Reword review of `<id>` (reword mode, run R): read the bundle `<scratch>/bundle.md`
   > first; the proof is at `<file:label or object + proofs/attempt>`. The question: does
   > the proof as reviewed still prove the new wording?

   The `land_verdict` hook lands it as `<pass dir>/R.md`.

   **A renamed label** (T-0476, the human's decision of 2026-10-17: a rename is a
   rewording). The new record (`paper:<new label>`) `supersedes` the old id, and the
   CONFIRMED x2 base pass stays in the old id's folder. In step 3 add
   `--base-subject <old id>`: `py $E/reviews.py new-pass <new id> --reword-of <base
   pass> --base-subject <old id> --ticket T-NNNN`. It refuses unless the new record
   lists `<old id>` in `supersedes`; the pass opens under the new id and notes
   `base_subject`. `reword-brief <new id> <pass> ...` then reads the base from the old
   id's folder and puts `base_subject: <old id>` into the lines R copies; the table
   (step 6) reads the base there, and its grounds carry `base_subject`, which
   `set-status` accepts only for a record that supersedes that id.
6. The table: `py $E/decision_table.py "<pass dir>/R.md" --established <ids> --json`.
   It finds the base pass beside the reword pass (`--base-dir` overrides) and recomputes
   the base's table. Outcomes:
   - `confirmed` / `confirmed-modulo`: propose `proved` / `proved-modulo` with the
     script's grounds (`mode: reword`, the reword row first, then the base rows); the
     recolour is earned as in the normal table. The base pass's modulo is carried over,
     plus any input R adds.
   - `full-pass-needed` (R is GAP, or `reword_scope: exceeds`): no status. Write the
     record, then open a **fresh blind pass** on the new statement (section 0, a new
     `new-pass` without `--reword-of`); its brief says nothing of R.
   - `disproved`: the counterexample to the human at once, as in section 4.
   - `degraded`: re-run R on a primary. `incomplete`: relaunch R once.
   - `invalid-base`: no status; the anomalies say why (base missing or not confirmed,
     `base_hash` not the base runs' hash, an unchanged statement, a shared run id, base
     runs about another id than the reword run's subject or its `base_subject`).
7. The record `<pass dir>/decision.md` (section 3), naming the base pass, both hashes,
   the word diff and `reword_scope`. Evidence: one row for R.md (section 4.1); the base
   rows are already on the claim. Packet and ticket as in section 4.
