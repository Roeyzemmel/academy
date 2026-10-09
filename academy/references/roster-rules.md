# Roster rules: who may do what

Stated once, here. Every role plugin's agents and skills follow these rules; the
permission tables that enforce part of them are in `academy/permissions.json`, and
the ticket protocol is `docs/protocol.md`.

## Independence

1. **The producer never grades its own work.** Whoever wrote an argument, an
   experiment, a citation card or a piece of code does not issue the verdict on it.
2. **The grader never edits what it grades.** Graders (`rigor-reviewer`,
   `experiment-reviewer`, `referee`) are read-only. Their verdicts reach the files
   through a SubagentStop hook, never through their own writes or the MCP write tools.
3. **The commissioner never grades.** An agent or skill that commissioned a piece of
   work (a lead-researcher that asked for a proof, a review-chair that launched two
   reviewer runs) adjudicates mechanically at most, by the decision table; it does
   not substitute its own reading for a verdict.
4. **Two agreeing, independent verdicts** are the grounds for raising a status
   (the `status-vocabulary` skill gives the mapping). Run B is launched only if run A
   is positive, and neither run sees the other. A definition used only as notation is
   not an input in a verdict's `modulo` list; only a definition whose content the
   argument relies on counts (the human's decision, 2026-10-09, T-0148). So two
   CONFIRMED runs whose `modulo` lists differ only in definitions agree, on the
   intersection of the lists; the decision table flags the definitions it dropped.
5. **Only the status keeper changes a status** (`registry.statusKeeper`, default
   `claim-keeper`), and only with grounds, or on the human's word.
6. **Only the human decides a packet.** Agents propose; `packets_decide` is
   human-only.

7. **Blind provers are independent by their brief.** Provers working on different
   approaches to one target are briefed only with their own approach, its directions
   and the target statement: no other approach's text, status or result. Independence
   comes from the brief, not from concurrency (they run one after another).

## Role cut

Who writes what, and what each role hands off to whom. Every role and agent prompt
points here; `docs/roles.md` explains the roles and the chain. Five rules, learnt from
the campaigns:

1. **The Researcher proves; the Author only lands.** Every new argument (a proof, a
   missing step, a repaired hypothesis, a cleaner formulation) is constructed in a
   Researcher notebook. The Author organises the paper, asks for what it needs, and
   lands what was delivered.
2. **Editors never touch a pinned or verified statement.** A statement whose hash is
   recorded by a CONFIRMED review run (`author/scripts/pinned.py`) keeps its
   environment byte for byte; its proof body stays free, since the hash covers the
   statement only. The `pinned_guard` hook refuses the edit; only the human releases a
   pin.
3. **Hypothesis-level findings go to the Researcher.** A review finding that touches a
   hypothesis or the statement, or needs a new argument, is a `prove` ticket to the
   Researcher with the falsifier, never an Author `apply` or `write` ticket
   (`expert/scripts/decision_table.py` `follow_up`).
4. **Each role files as itself.** A ticket's `from` is the instance whose agent did the
   work, never `human` on an agent's behalf (per-call instance resolution of the MCP
   server). Only the main session acting for the human files as `human`.
5. **No role does another role's work.** Work for another role is a ticket to it, and
   waits for that role's next actor (its `/<role>:inbox`). A campaign or a cowork never
   runs another role's agents inline.

| Role | Writes | Never writes | Hands off (ticket kind, to whom) |
|---|---|---|---|
| Researcher | notebook objects, proof attempts, directions, journal (`prover`, `lead-researcher`); statuses in any namespace, with grounds (`claim-keeper` only) | tex, a bibliography, library cards, lab code | `verify` / `cite` / `lookup` to the Expert; `experiment` / `test` to the Scientist; a delivered proof the paper needs reaches the Author through the Expert (`paper-liaison`) |
| Author | the paper's tex outside pinned statements, figures, `Drafts/` (agenda, `vision.md`); lands delivered results; owns form and taste (`author/references/aesthetic-vision.md`) | a new argument, a pinned statement's environment, notebook objects or records in a Researcher home, a status, the bibliography | a missing argument, a hypothesis question, a cleaner formulation: `research` to the Expert with `final_to: researcher`; `verify`, `cite`, `referee` and domain `notation` to the Expert |
| Expert | the library: cards, `index.md`, the bibliography (`librarian`); review records and decisions (`review-chair`); domain packs | tex, notebook objects, a status; graders write nothing at all | a hypothesis, statement or proof-step GAP: `prove` to the Researcher; a wording-only finding on a paper statement: `question` to the Author; a status: a proposal to the claim-keeper |
| Scientist | lab code, experiments, results, lab claims (`experimenter`, `developer`) | proofs, tex, notebook objects | a result to review: `review-experiment` to the Researcher; anything for the Expert or Author: to the Researcher with `final_to` |
| Human | anything by hand; decides packets; attests; releases a pin; leads a cowork | — | — |
| Orchestrator (the main session in `/academy:cowork`), campaign lead | the plan file, tickets, the campaign's approach objects (lead) | mathematics, tex or code in another role's remit; a grade; a status | everything, as tickets to the owning role (`academy/references/orchestrator.md`) |

The hooks that make part of this mechanical: `academy:role_write_guard`
(`permissions.json` `files.cross_role`: an Author agent writes nothing in a Researcher
home, a Researcher agent edits no tex), `author:pinned_guard`, `researcher:status_guard`,
`author:bib_gate`, and the chain gate on `tickets_create`.

## Explaining is not grading

`explainer` and `clerk` are read-only. They report the status the registry holds and
never form their own view of whether something is true.

## Model fallback

Each agent's frontmatter carries `model:`, `effort:` and `fallback:`.

- When the primary model is unavailable, the **launching session** (the main session
  or the agent that spawns it) relaunches through the Agent tool's `model` override
  set to the fallback, and **names the substitution in its report** and in the ticket
  thread.
- The override is otherwise never passed. Passing it out of habit silently costs the
  run whatever authority its primary model carried.
- The Agent tool cannot override `effort`; a task that deserves another effort gets
  its own agent.
- **Graders have equal primaries**, the models listed in workspace.json's
  `grading.primaryModels` (default: Fable and Opus 5.5; docs/config.md). A verdict of
  `rigor-reviewer`, `experiment-reviewer` or `referee` on any primary carries full
  authority; with the default list, the graders' frontmatter fallback `opus` resolves
  to Opus 5.5 and so is itself a primary. Every verdict records the exact model it ran
  on (`claude-fable-…`, `claude-opus-5-5`), never a bare family name: a bare `opus`
  names no version and is read as a fallback.
- **Graders degrade rather than substitute.** A proof verdict reached on any other
  model (Sonnet, Haiku, an older Opus) is at most PLAUSIBLE; an experiment verdict on
  one is at most GAP; a referee report on one marks itself reduced-strength. A
  degraded verdict never counts toward the two agreeing verdicts. The scripts apply
  this mechanically, reading `grading.primaryModels`: `expert/scripts/decision_table.py`
  (`configured_primaries`), `researcher/scripts/_researcher.py` (`primary_models`, used
  by `land_review.py` and `settle.py`) and `expert/scripts/land_referee.py`.
- A limit error is not "unavailable": it stops the run (budget.md rule 4).

## Standing conduct

- Never invent a citation, a pinpoint, an id or a result (`citation-discipline`).
- Every judgement call gets a machine note (`honest-reporting`).
- No `git stash`, no push. Commit only where the home's config and the human allow it.
- Agents change the board only through the MCP tools or the board scripts; the human
  may edit by hand.
