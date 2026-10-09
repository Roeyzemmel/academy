# expert — the library role

Role cut: what each role writes, never writes and hands off, and to whom, is one table, `academy/references/roster-rules.md` ("Role cut").
Library scaffold and access: `templates/library/README.md` (the generic library README, written by `/academy:init expert@x`), `references/publisher-access.md` (what fetches from which publisher).

The academy's library and its proof reviewers (plan section 3.4). The Expert caches
each source once and writes its citation cards (statement, hypotheses, version,
verbatim quote) and its `index.md` row. It answers quick questions from the cache,
reviews proofs with two blind rigor-reviewer runs and a mechanical decision table,
referees whole papers cold, keeps the literature watch, and curates the domain packs.
One instance per library home (`workspace.json`). It carries no domain mathematics:
the subject comes from the domain pack, by the pack contract's file names, through the
academy MCP tool `domain_get`. The contracts it codes against are `docs/protocol.md`,
`docs/config.md` and `docs/packet-template.md`, and its standing rules are
`academy/references/budget.md` and `roster-rules.md`.

## Agents

Each agent's model, effort and fallback are in its file's frontmatter. The fallback
rule is `academy/references/roster-rules.md`, "Model fallback".

| Agent | Job |
|---|---|
| `clerk` | Quick answers from `hot.md`, the cards and the MCP read tools; read-only, no web; a miss becomes an escalation for the librarian |
| `librarian` | Fetches and caches sources, writes cards and index rows; the only editor of the cards, `index.md` and every Author's `references.bib`; curates the domain packs |
| `review-chair` | Owns one proof review: the blind rigor-reviewer runs, `decision_table.py`, the record, the evidence, the status proposal and the packet; grades nothing |
| `rigor-reviewer` | One blind, adversarial proof review (CONFIRMED / PLAUSIBLE / GAP / DISPROVED); read-only, landed by a hook |
| `referee` | Whole-paper referee report from the built PDF, read cold; read-only, landed by a hook |
| `related-work-scout` | Prior-art search for one statement, or the literature watch; writes only the library's `ledgers/<instance>/` |
| `research-intake` | Relay, author -> (expert) -> researcher: fails fast, or writes the research block and forwards a `research` ticket |
| `paper-liaison` | Relay, researcher side -> (expert) -> author: restates a question or result in the paper's terms and forwards it |

## Skills

- Entry points: `/expert:lookup` (the clerk, answered inline) and `/expert:inbox` (at
  most three tickets, each routed by kind or by `final_to`).
- `/expert:cite`, `/expert:verify` (with `references/conclude.md`, the concluder's
  procedure), `/expert:referee`, `/expert:litwatch`, `/expert:library-index`,
  `/expert:domain`, `/expert:status`.

## Scripts (`scripts/`, stdlib Python, `py`)

Each script's usage is in its docstring.

| Script | Does |
|---|---|
| `inbox.py`, `routes.py` | The tickets to take this run (`--n`/`--limit`, `--all`) and each one's route, including relay return legs; a wrapper over the academy's `inbox_core` |
| `decision_table.py` | The proof-review decision table, applied mechanically to runs A and B |
| `reviews.py` | Where review records live (`reviews/<ns>/<id>/<pass>/`), pass names, the statement hash |
| `cards.py` | The citation card: schema, scaffold, validation |
| `library_index.py` | Cached keys with no `index.md` row; draft and append the rows |
| `hot.py` | Builds `hot.md`, the clerk's digest, from the MCP server's access log (a generated view) |
| `expert_status.py` | One read-only screen on an Expert instance |
| `ledger_split.py`, `ledger_views.py` | The phase-7 migration of an Author's old ledgers into library records, and the ledgers rebuilt from them as generated views |
| `land_verdict.py`, `land_referee.py` | SubagentStop hooks (below) |
| `review_blind_guard.py`, `library_edit_check.py` | PreToolUse and PostToolUse hooks (below) |
| `_expert.py` | Shared helpers: imports the vendored lib and the MCP server's library and claims modules |
| `_academy.py` | Vendored `academy/lib/academy_common.py`; never edit |

Tests: `py -m unittest discover expert/tests` from the academy repo.

## Hooks and scoping

`hooks/hooks.json`:

- `review_blind_guard` (PreToolUse `Read|Grep|Glob`) denies a `rigor-reviewer` any
  read of, or search over, the library's `reviews/`, so run B never sees run A. It is
  silent for every other agent and every path outside the Expert homes.
- `library_edit_check` (PostToolUse edits and `Bash|PowerShell`) warns and never
  blocks. It validates an edited card (its schema and its quote against the cached
  text) and reports cached keys with no index row. It is scoped to the Expert homes of
  `workspace.json`.
- `land_verdict` and `land_referee` (SubagentStop) fire only for `rigor-reviewer` and
  `referee`. They land the verdict under `reviews/<ns>/<id>/<pass>/` and the referee
  report as a `referee` packet, since both agents are read-only.

## The ticket chain

The Expert sits between the Author and the Researcher and files tickets only to those
two neighbours. Its relays are `research-intake` (Author toward the Researcher and
the Scientist) and `paper-liaison` (Researcher side toward the Author); `/expert:inbox`
hands them every ticket whose `final_to` lies beyond the Expert. Which agents may file
in each direction is `academy/permissions.json` `tickets.edges`, described in
`docs/protocol.md` section 5.1.

## Skills

<!-- skills:begin (generated by academy/scripts/skill_index.py; edit the skill's description instead) -->

| Skill | What it does |
|---|---|
| /expert:cite | Add or verify a citation through the librarian, the only route into references.bib and the library's cards: fetch, cache once, write the card and index row, report key and pinpoint. Use before adding any citation and for every cite ticket. |
| /expert:domain | Edit a domain pack from a ticket through the librarian, one change per ticket, logged in CHANGELOG.md: notation, theorem entry, trap, example, figure convention, recipe. Use for notation tickets (incl. final_to: expert) and "add this theorem to the pack". |
| /expert:inbox | Work the Expert's inbox: take at most three open or accepted tickets, route each by kind (verify, cite, lookup, question, referee, notation; research or final_to beyond the Expert to a relay agent), logging each in the thread. Use for "work the expert inbox". |
| /expert:library-index | Keep the library's index.md in step with its cached files: find cached keys with no index row, draft and add rows via the librarian, validate every card's schema and quote. Use for "fill the index", "what's cached but not indexed". |
| /expert:litwatch | Literature watch for one paper or notebook: related-work-scout runs its keywords over the newest arXiv listings and logs hits in the library ledger; with an id, a prior-art search. Use weekly, before a coauthor round or submission, "has anyone done this". |
| /expert:lookup | Answer a quick question about the library or registry via the Expert's clerk (hot.md, cards, MCP read tools, no web); a miss escalates to the librarian. Use for "what does LMW16 Theorem 11 assume", "what's the status of paper:lem:x", "do we have Z cached". |
| /expert:referee | Whole-paper referee report for one Author instance: the read-only referee agent reads the built PDF cold, and its report lands as a referee packet for Roey. Use for a referee ticket (from presync), before a coauthor round or submission. |
| /expert:status | One screen on the Expert instance: switch-over state, library (cached keys, index rows, cards), reviews awaiting run B, hot.md age, tickets and packets. Read-only. Use for "expert status", "how is the library", before /expert:inbox. |
| /expert:verify | Review one registry statement's proof with two independent blind rigor-reviewer runs (B only if A is CONFIRMED), adjudicated by script, with a verification packet; the sanctioned route from sketch to proved. Use for every verify ticket and "verify lemma X". |

<!-- skills:end -->
