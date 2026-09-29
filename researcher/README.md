# researcher — the research-notebook role

One Researcher instance per research domain (plan section 3.3; the instances are in
`workspace.json`). The instance's home is a notebook: typed objects under
`objects/<kind>/`, proof attempts under `proofs/`, the journal, the experiment reviews
under `audits/`, and generated `views/` (the layout is `templates/notebook/README.md`).
The Researcher owns directions end to end: falsifier first, prior art second, proof
third. It turns ideas into exact experiment specs for the Scientist, reviews the
Scientist's results, and sends finished proofs to the Expert for review. Its
`claim-keeper` is the one agent that changes a claim status, in any namespace. It
carries no domain mathematics: the subject comes from the domain pack through
`domain_get`. The contracts it codes against are `docs/protocol.md`, `docs/config.md`
and `docs/packet-template.md`, and its standing rules are
`academy/references/budget.md` and `roster-rules.md`.

## Agents

Each agent's model, effort and fallback are in its file's frontmatter. The fallback
rule is `academy/references/roster-rules.md`, "Model fallback".

| Agent | Job |
|---|---|
| `lead-researcher` | Owns one direction or one ticket; commissions prover and files the experiment, test, lookup and cite tickets; writes no mathematics, grades nothing |
| `prover` | Writes the mathematics: definitions, statements, proof attempts, corollaries, generalizations, prior-art scouts; never computes, never sets a status above `sketch` |
| `experiment-reviewer` | One blind, adversarial review of a computed result (SOUND / SOUND MODULO / GAP / BROKEN); read-only, landed by a hook |
| `claim-keeper` | The only agent that changes a status, through `claims_set_status`, and only on grounds on disk |
| `experiment-spec` | Relay, expert -> (researcher) -> scientist: fails fast, or writes the experiment spec and forwards it |
| `lit-request` | Relay, scientist -> (researcher) -> expert / author: answers from the library, or states the cite or literature ask and forwards it |

## Skills

- Entry points: `/researcher:status` and `/researcher:inbox` (at most three tickets,
  each routed by kind or by `final_to`).
- `/researcher:explore <direction>`, `/researcher:prove <claim>`,
  `/researcher:corollaries`, `/researcher:generalize`, `/researcher:review-experiment`
  (with its `checklist.md`), `/researcher:settle`, `/researcher:claims`.

## Scripts (`scripts/`, stdlib Python, `py`)

The command lines are in `references/scripts.md`, and each script's docstring says the
rest.

| Script | Does |
|---|---|
| `notebook.py` | Notebook bookkeeping: objects, directions, the next items, proof attempts, the journal, the scaffold |
| `reviews.py` | The experiment-review pair: landed runs, the decision table, the grounds; writes nothing |
| `settle.py` | Settles a result with candidate counterexamples: plan, decide, record |
| `generalize.py` | From a reviewed Conclusion to conjectures with falsifiers, their `test` tickets and the packet body |
| `inbox.py` | The tickets to take and each one's route, including relay return legs |
| `status_guard.py`, `claims_edit_check.py`, `audit_blind_guard.py`, `land_review.py` | Hooks (below) |
| `_researcher.py` | Shared helpers: homes, record roots, tolerant frontmatter |
| `_academy.py` | Vendored `academy/lib/academy_common.py`; never edit |

Tests: `py -m unittest discover researcher/tests` from the academy repo.

## Hooks and scoping

`hooks/hooks.json`:

- `status_guard` (PreToolUse edits) denies a change to a registry record's status
  line unless the caller is the status keeper (`claim-keeper`) or Roey. It covers the
  records of every home with a claim namespace, not only the Researcher's.
- `claims_edit_check` (PostToolUse edits) runs the registry engine's `check` on an
  edited record, plus a blocking `build` where the home's profile asks for one. It is
  silent in a home whose legacy hook is still registered.
- `audit_blind_guard` (PreToolUse `Read|Grep|Glob`) denies an `experiment-reviewer`
  the audits folders, so run B never sees run A.
- `land_review` (SubagentStop) fires only for `experiment-reviewer` in a Researcher
  home. It writes the verdict as `audits/<lab-id>/<date>-<A|B>.md`.

## The ticket chain

The Researcher sits between the Expert and the Scientist and files tickets only to
those two neighbours (and to other Researcher instances). Its relays are
`experiment-spec` (Expert toward the Scientist) and `lit-request` (Scientist toward
the Expert and the Author); `/researcher:inbox` hands them every ticket whose
`final_to` lies beyond the Researcher. `prover` files no ticket to the Scientist: a
number it needs is a request to `lead-researcher`. Which agents may file in each
direction is `academy/permissions.json` `tickets.edges`, described in
`docs/protocol.md` section 5.1.
