# Editing a notebook

The editing contract of every Researcher notebook (the layout is the scaffold's
`templates/notebook/README.md`). Who may write what is the role cut
(`academy/references/roster-rules.md`): `prover` writes objects and proof attempts,
`lead-researcher` the directions and the journal, `claim-keeper` the statuses; hooks
enforce it. A home's `.claude/rules/` adds only what is its own (its assumption names,
frozen folders, old-label maps).

## What is the source of truth

| path | role |
|---|---|
| `objects/<kind>/<ID>.md` | **source of truth**, one object per file, in the folder of its `kind` (a record's `kind` must match its folder) |
| `proofs/<ID>/attempt-<n>.md` | proof attempts, named by the object's `proof:` field; a failed one is kept |
| `journal/*.md` | working memory; never graded |
| `audits/<subject>/*.md` | ledger entries, one per file, landed by the `land_review` hook; a new verdict is a new file, an entry is never rewritten |
| `views/` and any other file the home's registry profile generates | **generated** by `registry.py build`; never edit them, the record hook rebuilds after every edit to an object |

Ask the registry, don't read files whole: `registry.py find`, `show ID --deps`,
`show ID --full`, `usedby ID --transitive`, `resolve "old label"`.

## Object files

The frontmatter schema is the scaffold's `_templates/object.md` and the registry's
schema v2. The frontmatter is the registry's strict YAML subset
(`academy/registry/core/fm.py`): `registry.py check` rejects anything else. Fields worth
knowing beyond the obvious:

- `modulo`: the missing inputs of a `proved-modulo` object (ids or plain text).
- `depends_on` (ids the statement or proof uses), `bears_on` (ids it is evidence for, any
  namespace), `supersedes` (one-way; `superseded_by` is derived).
- `lifecycle`: active · superseded · dropped (not a status).
- `aliases`: every old label that has meant this item; `resolve` maps them.
- `tags`: free labels. `notation-only` on a definition marks it as used only as notation:
  the Expert's decision table then drops it from a verdict's `modulo` list; any other
  definition listed there stays an input (`proved-modulo`, #103). The tag is the
  human's call; a reviewer's own mark never counts.
- `evidence` rows `type | ref | verdict | run_id | note`; `history` rows
  `date | status | note`, newest first.
- `body_status_ack: "why"` silences a reviewed mismatch between the body's first status
  word and the `status`.

Body: `## Statement`, `## Proof` (a one-line pointer to the `proof:` attempt), `## Notes`.

**Structured records (optional, #127).** A statement with several conclusions may name
its hypotheses and its items, so that each conclusion carries its own status, modulo
and hash (a whole proposition is no longer held back by one item's inputs, and a
reworded item invalidates only its own reviews). Two map fields:

```
hypotheses:
  H1: "P is a rational polygon"        # its text, or the definition it uses
  H2: DEF-4
items:
  C1: [proved]                         # [status, modulo input, ...]
  C2: [proved-modulo, GEO-9]
```

and in `## Statement` one line per part, `**H1.** ...` / `**C1.** ...` (a `- ` bullet
before it is allowed); a part runs to the next part's marker, a blank line or a heading.
Every `items` key has its `**C<n>.**` line and every such line a key; the same for the
hypotheses. The record's `status` is the one its items derive (every item `proved` ->
`proved`; every item `proved` or `proved-modulo` -> `proved-modulo`, `modulo` the union
of the items'; otherwise the weakest item status), and `registry.py check` refuses a
mismatch. Each item's hash covers the hypotheses' texts and its own text:
`registry.py statement ID --items` lists them (the whole-statement hash is unchanged).
In the paper an item key is its `\label{it:KEY}` without the `it:` prefix, its text is
the `\item` that carries the label, and the hypotheses' texts are the frontmatter's.
The migration is lazy: a new or reworded claim takes the form; an old record keeps its
own until it is next touched, when `registry.py structure ID` proposes the fields from
its body (each item at the record's status) and `--write` adds them. Never bulk-migrate.
`steps:` (a Lamport-style proof outline) is not part of the form.

**Verbatim bodies.** Text migrated from an older source keeps its old labels, its old
status words, its old paths and its original numbering; inside such a block a bare
"Prop. 1.6" means that block's own document, as named in `source`. Never reword it.

**Cleared statements are frozen.** After a claim is cleared, never edit its Statement or
Proof: a repair is a new object that `supersedes` it, or a new proof attempt, and a fresh
review.

**New material.** `registry.py new PREFIX --title "…"` (or `claims_new`) creates the next
free id, unsettled, in the folder of its kind. A number is never reused and an id never
renamed. A direction comes from `notebook.py new direction DIR-<n>`.

**Superseding.** Never delete an object. Set `supersedes: [OLD]` on the new one; the old
one's `lifecycle` becomes `superseded` through claim-keeper, and each gets a history row.

## Statuses

A status moves only through claim-keeper, on two agreeing reviews or the human's word
(`claims_set_status`; from a shell `registry.py set-status ID STATUS --verdict <file>`).
The human's word is an attestation, recorded as `academy:status-vocabulary` says (a
verdict file of `kind: attestation`; never inferred). After a change,
`registry.py usedby ID --transitive` lists every dependant whose status now rests on a
weaker input; `registry.py check` warns on a proved claim that depends on an unproved one.

When a cleared verdict carries an *Allowed wording* for a draft, that wording becomes the
object's Statement (prover), and nothing beyond it. Earn an `open` flag: say what a
counterexample would have to look like, try to build one, and record the class searched.

## Assumptions

`objects/assumption/` holds the hypothesis hierarchy, grouped by prefix
(`registry.assumptionGroups`, rendered in `views/assumptions.md`). `implies:` holds only
proved edges; an edge awaiting verification goes in `implies_pending:` (the claim id in a
comment) and moves into `implies` once that claim is proved. `incomparable_with:` must be
symmetric, and `check` enforces it.

## Directions

`objects/direction/DIR-<n>.md`, from the direction template: `## Program`, then bullet
lists `- <ns>:<id> — one line` under `## Questions`, `## Candidate claims` and
`## Falsifiers` (the smallest case where each candidate could fail), and a numbered
`## Next steps` (at most three). `views/directions.md` shows each item's status.
