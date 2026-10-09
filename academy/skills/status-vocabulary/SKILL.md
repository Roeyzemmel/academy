---
name: status-vocabulary
description: 'The one mapping between draft colours, registry claim statuses, and review verdict words (CONFIRMED / PLAUSIBLE / GAP / DISPROVED; SOUND / SOUND MODULO / GAP / BROKEN). Use whenever a status, colour or verdict is written, read or proposed.'
---

# One status vocabulary

Every status, colour and verdict word in the academy comes from these tables. Do not
coin synonyms. Do not reconstruct a status from prose: read it from the registry
(`claims_show`) and quote it.

## Claim statuses (the registry, every namespace)

| Status | Meaning | Projection class |
|---|---|---|
| `open` | Not settled. Includes "ran, but the outcome was never recorded" | unsettled |
| `conjectured` | Believed and stated as a conjecture; no argument claimed | unsettled |
| `sketch` | An argument exists but has not been verified | unsettled |
| `supported` | A bounded computation found no counterexample. **Not a proof**; the evidence note states the bound and the class searched | unsettled |
| `proved-modulo` | Proved, given the inputs listed in `modulo:` (black boxes or a reduction target) | true-modulo |
| `proved` | Proved and verified: two agreeing verdicts, or a precise citation | true |
| `refuted` | False; a counterexample or disproof is recorded as evidence | false |
| `refuted-as-stated` | False as written; the repaired statement `supersedes` it | false |

`supported` is unsettled on purpose: no computation proves a claim. Definitions,
remarks and examples carry no status (projection `n/a`).

**Lifecycle** is separate from status: `active` (default), `superseded` (a newer
object `supersedes` it), `dropped` (withdrawn). A superseded or dropped object
projects to `n/a` whatever its status. Nothing is deleted; a false claim becomes
`refuted`, never removed.

**Who moves a status:** only the status keeper (`claim-keeper`), with grounds, or the human.
Everyone else proposes (`claims_propose_status`).

## Draft colours (Author homes)

The environment and macro names come from the home's `author.envs`,
`author.colourCommands` and `author.colours`; the defaults are:

| Draft colour | Environment / span | Colour | Registry statuses it may carry |
|---|---|---|---|
| established | uncoloured | black | `proved` (by two agreeing verdicts or a precise citation) |
| sketch | `sketch` / `\Sketch{}` | blue | `sketch`, `proved-modulo` (the `modulo` inputs named in a machine note) |
| conjectural | `conjectural` / `\Conjectural{}` | red | `open`, `conjectured`, `supported` (the computation cited) |
| meta | `meta` / `\Meta{}` | brown | none: commentary about the paper, not a claim |

A statement turns black only when the registry says `proved`. An established
statement never rests on a blue or red one. The Author checker enforces the draft side.

## Verdicts

| Proof review (Expert, `rigor-reviewer`) | Meaning |
|---|---|
| CONFIRMED | Valid from its stated inputs; cited results used within their real hypotheses; on a primary model (Fable or Opus 5.5, equal) |
| PLAUSIBLE | No gap found, but on a non-primary model (Sonnet, Haiku, an older Opus) or with reduced strength; never counts toward `proved` |
| GAP | A step does not follow; the verdict names the step and what would close it |
| DISPROVED | False, with an explicit verified counterexample |

| Experiment review (Researcher, `experiment-reviewer`) | Meaning |
|---|---|
| SOUND | The computation checks what the header says, within the class it names, and the reviewer actively tried to break it |
| SOUND MODULO `<assumption>` | Sound given a named assumption the reviewer could not check |
| GAP | The check does not establish what it claims (a shadow of the claim, a class that cannot contain the answer, float where exact was needed) |
| BROKEN | A concrete defect, with the line and the consequence |

## From verdicts to a status

| Grounds | Status the keeper may set |
|---|---|
| Two CONFIRMED, distinct run ids, same statement hash, no inputs | `proved` |
| Two CONFIRMED with named black-box inputs | `proved-modulo`, inputs in `modulo` |
| Any PLAUSIBLE or GAP | no change; GAP files a repair |
| DISPROVED, counterexample verified | `refuted` or `refuted-as-stated` |
| Two SOUND (or SOUND MODULO the same assumption, recorded in the evidence note), commit hash, validation case reproduced, no counterexample | `supported` |
| The same, with a verified counterexample | `refuted` or `refuted-as-stated` |
| Any GAP or BROKEN on an experiment | no change |
| The human's word | any status; the history line says so |

Computation never reaches `proved` or `proved-modulo`.

## Old words

| Old | Now |
|---|---|
| Proved | `proved` |
| Proved modulo stated inputs | `proved-modulo` |
| Reduced | `proved-modulo`, `modulo: [the reduction target]` |
| Partial | split: each proved case its own `proved` claim; the parent stays `open`, `depends_on` the cases |
| Disproved | `refuted` |
| Not settled | `open`, `conjectured` or `sketch`, by kind and proof state |
| blue / red / brown / black | sketch / conjectural / meta / established |

Ticket lifecycle words (`open`, `accepted`, `in-progress`, `delivered`, `closed`, …)
belong to tickets, not to claims: `docs/protocol.md` section 4. A ticket that is
`open` says nothing about a claim that is `open`.
