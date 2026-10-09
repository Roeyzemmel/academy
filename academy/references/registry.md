# The claim registry: record format of the `lab` and `paper` rule sets

Every home with a registry (`registry.profile` in its `.claude/academy.json`,
`docs/config.md`) keeps one short text file per claim, read by the academy's registry
engine (`academy/registry`, run as `py $ACADEMY_ROOT/academy/scripts/registry.py`, or
the MCP `claims_*` tools). The files are the source of truth; the SQLite database
behind `registry.py sql` and the index pages (`<root>/INDEX.md`, `<root>/index.html`)
are generated from them and never edited by hand. To find out what is known about X,
run `registry.py show X`; never piece a status together from prose, headers or chat. If
the registry is missing something, fix the registry.

This file is the record format of the `lab` and `paper` rule sets (engine profile
`fsl`). A notebook home (`notebook` rule set) uses the richer schema v2 of the Researcher
plugin, `researcher/references/notebook-editing.md`. The status words and who may move
them are `academy:status-vocabulary`.

## Ids and namespaces

An id is `<ns>:<name>`. Each namespace has one home, named in `workspace.json` (the
instance's `ns`), which owns its files; other homes only link to its ids, and `check`
resolves every link against that home:

- a `paper` namespace's ids are the paper's `\label`s (`<ns>:prop:x`): the record must be
  a file in the Author home's registry root, or at least a `\label` in its tex;
- a notebook namespace's ids are its object ids; an old label (an alias) is an error that
  names the current id, and `registry.py resolve <text>` maps any other;
- a claim filed outside its home is an error;
- a link into a home that is not present on this machine (a remote worker's checkout) is
  not checked.

In a `paper` registry `check` also requires every id to be a `\label`, and a statement
that is established in the draft (black in `Drafts/statements.md`) to have status
`proved` or `proved-modulo` plus a `verdict` or `citation` evidence line, so a refuted
statement cannot stay black.

The file is `<root>/<ns>/<name>.md`, with any `:` in the name written as `__`
(`paper:prop:x` lives in `claims/paper/prop__x.md`); `check` enforces it.

A lab claim is the computational statement itself, as its experiment's kind produces it
(the Scientist's `experiment-method`; the lab's `experiments/README.md`): a search's
"an example of P exists" or "not found under constraints C", a measure's "the quantity
over class C is …", a verify's "object O has property P". The theorem it bears on is
named under `bears_on`. Keeping the two apart stops "the search found nothing" from being
read as "the theorem is proved". Checks on code are tests, never claims.

## Format

```
---
id: lab:example-property
title: the property holds on the standard examples, below bound B
status: supported
where: experiments/2026-09-18_example_property.py
bears_on:
  - paper:prop:example
depends_on:
evidence:
  - experiment | results/2026-09-18_example_property.json | not audited | 0 counterexamples, 6 objects
history:
  - 2026-09-24 | supported | seeded from the experiment header and result JSON
open:
  - no /researcher:review-experiment audit yet
---
Optional prose: a few lines at most. A long argument belongs in the paper or a notebook.
```

Scalars take one line; lists are `key:` followed by `  - item` lines (the engine's strict
YAML subset, `academy/registry/core/fm.py`).

| Field | Kind | Meaning |
|---|---|---|
| `id` | scalar, required | as above |
| `title` | scalar, required | the claim in one line |
| `status` | scalar, required | the one vocabulary (below) |
| `where` | scalar | the file that states or tests it; a path, never a line number |
| `bears_on` | list | ids this one is evidence for or against |
| `depends_on` | list | ids this claim uses; `check` warns when one is refuted |
| `supersedes`, `superseded_by` | scalar | the repaired or replacing statement |
| `evidence` | list | `kind \| ref \| verdict \| note` |
| `history` | list, required | `YYYY-MM-DD \| status \| what happened`, newest first; the first line's status equals `status` |
| `open` | list | what is still missing |
| `tags` | list | free |

- **Evidence `kind`**: `experiment`, `audit`, `verdict`, `hand`, `citation`, `note`.
- **Evidence `ref`**: a path in this home, or `<Home>:<path>` in a sibling home. `check`
  verifies that `experiment`, `audit` and `verdict` refs exist.
- **Evidence `verdict`**: for an experiment, its audit state (`not audited`, `cleared`,
  `not cleared`); for a review run, its verdict word.

## Statuses

`open` · `conjectured` · `sketch` · `supported` · `proved-modulo` · `proved` · `refuted` ·
`refuted-as-stated`, plus `superseded` and `dropped` (`academy:status-vocabulary`).
`supported` is a bounded computation that found no counterexample, **never a proof**: its
evidence note states the bound and the class. `proved-modulo` lists its inputs under
`open`. `supported` and `proved` need at least one evidence line; `refuted-as-stated`
needs its `superseded_by`.

## Who writes what

- A status changes only through `claim-keeper` (MCP `claims_set_status`), on grounds:
  two agreeing reviews (`/researcher:review-experiment`, `/expert:verify`) or the
  human's recorded word. Anything less stays `open`, with the reason under `open`.
- Every change adds a `history` line. Nothing is deleted: a claim that turned out false
  becomes `refuted`, not a missing file.
- After an edit, `registry.py check` (the record hook runs it) and `render`.

## Linking from experiments

The experiment header's `Claims:` line, `env.save_result(..., claims=[...])` in the
result JSON, and the queue's `--label` all name ids; `registry.py show` finds all three
as back-links.

## Queries

```
registry.py list --status refuted
registry.py grep "some phrase"
registry.py sql "select c.id, e.ref from claims c join evidence e on e.claim = c.id where e.verdict = 'not audited'"
registry.py sql "select dst, count(*) from links where rel = 'bears_on' group by dst"
```

Tables: `claims(id, ns, status, title, where, file, body)`,
`evidence(claim, kind, ref, verdict, note)`, `history(claim, date, status, note)`,
`links(src, rel, dst)`, `open_items(claim, item)`.
