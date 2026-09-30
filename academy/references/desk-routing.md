# Desk routing: how the concierge classifies a request

The concierge reads one request from Roey and returns one **routing card**. It never
does the work itself, never files a ticket, never asks a question, and never launches
more than one clerk lookup.

## Classes

| Class | When | Target | The concierge does |
|---|---|---|---|
| `answered` | A quick factual question the library or a registry answers: what a cited result says or assumes, the status of an id, where something is proved, what a ticket or packet says | the Expert's `clerk` (library, cards, `hot.md`), or the read tools directly for a status or a ticket | asks once, returns the answer with its source; on a clerk miss, becomes `ticket` (kind `lookup` or `cite`) |
| `explain` | "explain", "walk me through", "what is", "give me an overview of" a concept, definition, claim and its proof, paper, experiment or direction | `/academy:deep-dive` | resolves the subject to an id (`<ns>:<id>`, `bib:<key>`, a result path, `concept:<term>`) |
| `action` | One step that a role's public skill does as it stands: cite a key, verify one label, run one queued experiment, show the agenda | that skill, e.g. `/expert:cite`, `/researcher:prove`, `/scientist:queue`, `/author:next` | names the skill and the exact arguments |
| `ticket` | Anything larger, or anything crossing roles: a new argument, a new experiment, a review, a notation change | the receiving instance, chosen below | drafts the ticket |
| `unclear` | The request has two readings that route differently | none | states the one question that separates them |

## Choosing the receiver

- By the work: proofs, verification, citations, the library → Expert; new arguments,
  directions, experiment reviews, generalizations → Researcher; computations and code
  → Scientist; the paper's text, build, figures, notation decisions → Author. The
  ticket kinds and their required routes are in `docs/protocol.md` section 3.
- By the domain: among instances of that role, the one whose `domains` contain the
  request's domain. If several match, prefer the one whose home the request names or
  whose registry holds the ids it mentions; otherwise pick the first and say so.
- By the refs: an id `paper:…` belongs to the Author instance with ns `paper`, `s1:…`
  to the Researcher with ns `s1`, `lab:…` to the Scientist with ns `lab`.

## The card

```
class: answered | explain | action | ticket | unclear
target: <instance, skill or clerk>
subject: <id or free text>            (explain)
skill: /<plugin>:<skill> <args>       (action)
answer: <text>                        (answered)
source: <card path, id or quote ref>  (answered)
question: <one question>              (unclear)
ticket:                               (ticket)
  to: <instance>
  kind: <ticket kind>
  title: <short>
  ask: <one sentence>
  deliverable: <one sentence, checkable>
  refs: [<refs>]
  priority: normal
  budget: {runs: <n>}
why: <one line: why this route>
```

Keep budgets small: the receiver's `budget.ticketDefault` runs unless the ask plainly
needs more. The desk does not choose a model: the receiving agent runs on its agent
file's model (`budget.md` rule 6).
