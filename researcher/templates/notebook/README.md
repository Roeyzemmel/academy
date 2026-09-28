# Research notebook

The notebook of one Researcher instance (plan section 3.3): **one typed object store
plus a journal**. Scaffolded by `/academy:init researcher@<name>` from the Researcher
plugin's `templates/notebook/`.

```
objects/<kind>/<id>.md      kind: definition | claim | conjecture | question | example |
                            assumption | direction
proofs/<id>/attempt-<n>.md  versioned proof attempts; failed attempts are kept
journal/YYYY-MM-DD.md       working memory: tried, dead ends, next steps (never graded)
audits/<lab-id>/            experiment reviews, landed by a hook (never edited by hand)
views/                      generated: index, dependency graph, open questions, what rests on X
```

## Objects

Every object is one Markdown file with one frontmatter schema (plan section 6), the
same in every namespace:

| Field | Meaning |
|---|---|
| `id` | The id inside this namespace; the reference form is `<ns>:<id>` |
| `kind` | One of the seven kinds above |
| `title` | One line |
| `status` | Only for claim, conjecture and question: open · conjectured · sketch · supported · proved-modulo · proved · refuted · refuted-as-stated |
| `statement` | The statement, verbatim |
| `modulo` | The missing inputs of a `proved-modulo` object |
| `depends_on`, `bears_on`, `supersedes` | Links by id; `superseded_by` is derived |
| `lifecycle` | active · superseded · dropped (a lifecycle, not a status) |
| `aliases`, `domain`, `tags` | Old labels, the domain pack, free tags |
| `proof` | The current attempt, `proofs/<id>/attempt-<n>.md` |
| `evidence` | Rows `type \| ref \| verdict \| run_id \| note` |
| `history` | Rows `YYYY-MM-DD \| status \| what happened`, newest first |

A **direction** is itself an object: a research program listing its questions,
candidate claims and falsifiers. `/researcher:explore` works directions -> questions
-> claims.

## Who writes what

- `prover` writes definitions, statements, proofs, corollaries and generalizations.
- `lead-researcher` keeps the directions and the journal.
- **Only `claim-keeper` changes a `status:` line**, through `claims_set_status`, with
  grounds (two agreeing reviews, or Roey's word). A hook denies it to everyone else.
- `audits/` is written by the `land_review` hook; `views/` by scripts. Neither is
  edited by hand.
- Nothing is deleted: a false claim becomes `refuted`, a replaced one `superseded`.
