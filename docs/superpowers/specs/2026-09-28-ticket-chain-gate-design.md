# Ticket chain gate: neighbour-only tickets, liaisons, directional relays

Status: design agreed with Roey, 2026-09-28. Next: the implementation plan.

## 1. Purpose

Fail fast. A request should reach a role only after the role before it has
checked it and added what the next role needs:

- the Author consults the Expert before any research is started, and the
  Expert grounds the request in the literature (a research block) and tells
  the Author about relevant results;
- the Researcher turns ideas into exact experiment specs for the Scientist,
  and asks the Expert for literature as its research advances;
- results and questions travel back the same way, one hop at a time.

Today nothing restricts who files a ticket to whom (`permissions.json`, the
`mcp_write_gate` hook and `validate_ticket` check tools and schema only;
`docs/protocol.md` §3 gives "typical routes").

## 2. The rule

The chain is `[author, expert, researcher, scientist]`. A ticket from S to R,
filed by agent A, is allowed iff one of:

1. S or R is `human`;
2. S and R have the same role (self-tickets, and researcher to researcher
   across domains);
3. the roles of S and R are adjacent in the chain **and** A is on the liaison
   list of the direction role(S) -> role(R) (section 4);
4. the ticket is clerical and exempt (section 4.3).

Roles, not instances, are compared. A refusal names the neighbour to file
to instead and its relay for that direction.

Out of scope, unchanged: replies and deliveries on the same ticket,
`packets_create`, thread appends, and re-routing `to` (human-only). None of
them creates a new sender-to-receiver edge.

## 3. Who the caller is

- A subagent: its plugin gives its role; its instance is the home it runs in
  (as today, `academy/mcp/tools/__init__.py` `instance`).
- **The main session inside a role home** files as that home's instance, with
  agent `main`. Today it files as `human`; this is the main behavioural
  change. A main session outside every home is still `human`.
- **Filing as Roey from inside a home**: only `/academy:board`,
  `/academy:desk` and `/academy:decide` may pass `as_human: true` to
  `tickets_create` (and `--as human` to `board.py new`), and only after Roey
  confirmed the ticket through AskUserQuestion. A test fails if any other
  skill, agent or script uses it. This is enforced by convention and that
  test; the main session is ultimately Roey's.
- **`board.py new`** loses its default sender `human`: `--as <instance>` and
  `--agent <name>` are required. `author/scripts/next.py`,
  `scientist/scripts/report.py` and `researcher/scripts/generalize.py` pass
  their home's instance and `main`.

## 4. Configuration: `academy/permissions.json` `tickets.edges`

```json
"edges": {
  "chain": ["author", "expert", "researcher", "scientist"],
  "maxHops": 3,
  "liaisons": {
    "author->expert":       ["main", "math-writer", "notation-auditor", "figure-maker"],
    "expert->author":       ["librarian", "review-chair", "research-intake", "paper-liaison"],
    "expert->researcher":   ["research-intake", "review-chair"],
    "researcher->expert":   ["main", "lead-researcher", "prover", "lit-request"],
    "researcher->scientist":["main", "lead-researcher", "experiment-spec"],
    "scientist->researcher":["main", "experimenter"]
  },
  "exempt": ["claim-keeper", "usage-analyst", "concierge"]
}
```

### 4.1 What each direction carries

| Direction | Carries |
|---|---|
| author -> expert | verify, cite, referee, litwatch, notation, and the new `research` request (replaces `[lead]`/`prove`/`[experiment]` sent past the Expert) |
| expert -> author | `note` (new kind: literature results the Author should know, unsolicited), repair questions on `paper:` claims, forwarded questions and results (paper-liaison) |
| expert -> researcher | the prepared `lead` ticket with its research block; prove/repair after a review |
| researcher -> expert | verify, cite, literature asks on the current direction; forwarded lab cite asks (lit-request) |
| researcher -> scientist | exact experiment and test specs |
| scientist -> researcher | review-experiment, questions, results bearing on a claim |

### 4.2 Removed from today's practice

- prover -> scientist (`researcher/agents/prover.md`): experiments go through
  lead-researcher (or experiment-spec), one spec per direction.
- api-prober, developer, test-engineer, upstream-contributor file only inside
  the lab.
- related-work-scout files no tickets (unchanged).

### 4.3 Exempt (clerical, not requests)

- claim-keeper `decision` tickets from `claims_propose_status`: still checked
  to go to the keeper of the claim's namespace, as today.
- usage-analyst: files only to `human`.
- concierge: files as `human` after Roey confirms.

## 5. Relays

Two roles sit in the middle of the chain, each with two crossings, so there
are four directional relays. A relay checks, sharpens and forwards; it writes
no mathematics, grades nothing, uses no web and no shell, and makes one pass.

| Relay | Crossing | Model |
|---|---|---|
| `expert:research-intake` | author -> (expert) -> researcher | sonnet |
| `expert:paper-liaison` | researcher -> (expert) -> author | haiku |
| `researcher:experiment-spec` | expert -> (researcher) -> scientist | sonnet |
| `researcher:lit-request` | scientist -> (researcher) -> expert | haiku |

Tools: the MCP read tools, `tickets_create`, `tickets_update`,
`library_lookup`, `library_search`, `claims_show`. Models live in the agent
files; the weekly usage packet decides later downgrades.

### 5.1 Recognising a relay ticket: `final_to`

New optional sender-owned ticket field `final_to: <role or instance>`, the
role the request is really for. The check (section 2) requires `to` to be a
neighbour; `final_to` may be any role further along the same direction. When
a receiver's `final_to` is not itself, its inbox routes the ticket to the
relay of the matching crossing (the neighbour it came from, the direction of
`final_to`), whatever the kind.

### 5.2 What each relay does

1. **Fail fast**: deliver straight back to the sender with the reason, filing
   nothing further, when
   - research-intake: the ask is not pinned down (no statement or claim id,
     no "what counts as done"); the library already answers it (a known
     result or counterexample, delivered with its card); a registry claim
     settles it;
   - experiment-spec: no claim is named; the lab already has a result for the
     claim and class (evidence row or results JSON);
   - lit-request: the library's read tools already answer the cite;
   - paper-liaison: the question does not concern a `paper:` claim or section
     of that Author (returned to the sender to be redirected).
2. **Sharpen**:
   - research-intake writes the **research block** into the child ticket: the
     relevant cards with pinpoints, the related registry claims with
     statuses, known results nearby, and open literature gaps stated as
     questions. Results the Author should know go back as `note` tickets;
   - experiment-spec writes the **experiment spec** in the lab's header
     vocabulary: claim id, kind (search / measure / verify), the class and
     bounds, what refutes the claim, a suggested validation case, the scope
     defaults (translation surfaces, non-periodic points unless stated);
   - lit-request states the cite or literature ask with the claim's context;
   - paper-liaison restates the question or result in the paper's terms
     (claim id, section, what the Author must decide).
3. **Forward**: file a child ticket to the next neighbour toward `final_to`,
   with `parent` = the received ticket and `final_to` kept; set the received
   ticket `blocked`, `waiting_on` the child. When the child is delivered, the
   inbox runs the same relay to deliver the parent with a short result
   pointing at the child.

### 5.3 Hop limit

A relay chain may have at most `maxHops` (3) links, author to scientist. Only
consecutive ancestors that carry `final_to` count: an ordinary `parent` link (a
review-experiment ticket filed against the ticket that commissioned the
experiment) is not a relay hop. The check refuses a relayed child that would
exceed the limit.

## 6. Flows rerouted

| Today | Becomes |
|---|---|
| author `[lead]`/`prove` -> researcher (`author/scripts/next.py` ASK_ROUTES, `routing.md`, `math-writer.md`) | author `research` -> expert (research-intake) -> researcher |
| author `[experiment]` -> scientist (`next.py`, `routing.md`, `figure-maker.md`) | author -> research-intake -> researcher (experiment-spec) -> scientist, `final_to: scientist` |
| math-editor `claims_propose_status` | unchanged (exempt decision ticket) |
| review-chair repair on a `lab:` claim -> scientist (`expert/skills/verify/references/conclude.md`, `review-chair.md`) | -> researcher (experiment-spec) -> scientist |
| scientist cite -> expert (`academy/skills/citation-discipline`, `expert/skills/domain`) | -> researcher (lit-request) -> expert |
| scientist examples-audit question -> author (`scientist/skills/examples-audit`) | -> researcher -> expert (paper-liaison) -> author |

## 7. Where the code changes

- `academy/lib/academy_common.py`: `ticket_edge_allowed(frm, to, agent,
  perms, parents)` returning `(ok, reason)`; `final_to` in the ticket schema
  (`validate_ticket`). Vendored copies re-synced (`test_vendored.py`).
- `academy/mcp/tools/tickets.py` `create_ticket`: calls the check; accepts
  `as_human`, `final_to`. `academy/mcp/tools/__init__.py`: main session in a
  home is the home's instance, agent `main`.
- `academy/mcp/tools/claims.py` `claims_propose_status`: keeps its
  namespace check, marked exempt.
- `academy/scripts/board.py new`: `--as` and `--agent` required, calls the
  check, `--final-to`.
- `academy/permissions.json`: `tickets.edges`; the `tickets_create` substance
  text; the four relays in the roster and in the `tickets_create` /
  `tickets_update` allow lists.
- New agents: `expert/agents/research-intake.md`,
  `expert/agents/paper-liaison.md`, `researcher/agents/experiment-spec.md`,
  `researcher/agents/lit-request.md`.
- Inbox routing on `final_to` and on the kinds `research` and `note`:
  `expert/skills/inbox`, `researcher/skills/inbox`; `author` lands `note`
  tickets (`author/skills/next`).
- The flows of section 6: `author/scripts/next.py` and
  `author/skills/next/references/routing.md`, `author/agents/math-writer.md`,
  `author/agents/figure-maker.md`, `researcher/agents/prover.md`,
  `expert/skills/verify/references/conclude.md`,
  `expert/agents/review-chair.md`, `scientist/skills/examples-audit`,
  `academy/skills/citation-discipline`, `expert/skills/domain`.
- `academy/skills/board`, `desk`, `decide`: pass `as_human` after
  confirmation.
- Docs: `docs/protocol.md` §1 (parties, main session), §3 (required routes
  and the new kinds), §5 (permissions), §6 (worked flows);
  `docs/roles.md`; each plugin README's agent list.

## 8. Tests

- `ticket_edge_allowed`: every direction allowed and refused; liaison
  membership per direction; same role; `human` at either end; exempt agents;
  `final_to` beyond `to` and in the wrong direction; the hop limit.
- Caller identity: main session in a home files as the instance; outside a
  home as `human`; `as_human` honoured for the three academy skills and a
  lint test that no other skill, agent or script uses it.
- `board.py new`: refuses without `--as`; applies the check.
- Inbox routing: a ticket with `final_to` beyond the receiver goes to the
  right directional relay.
- Existing fixtures that break the rule are rewritten:
  `scientist/tests/test_report.py` (`to="author@bi"`),
  `author/tests/test_next.py` routes, `academy/tests/test_mcp.py` and
  `test_board.py` cases.
- Run: `py -m unittest discover <plugin>/tests` for academy, author, expert,
  researcher, scientist.

## 9. Open for later, not in this change

- Downgrading the Sonnet relays after usage data.
- Whether thread appends by non-parties should also respect the chain.
