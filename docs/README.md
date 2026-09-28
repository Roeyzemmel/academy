# The academy, for Roey

One front desk, four kinds of worker, one board between them. Nothing runs on its
own: every run starts from something you type.

## Where to start

- **`/academy:desk <request in plain words>`**: the front desk. The concierge decides
  whether it is a quick question (answered inline), an "explain X" (a deep-dive
  page), one action (the right role's skill), or bigger work (a ticket, which you
  confirm before it is filed).
- **`/academy:desk`** with no argument: one screen with what needs you, what is in
  flight, what came back since your last visit, and this week's usage.
- **`/academy:review`**: the open review packets as one private HTML dashboard. Each
  pending decision is then asked in the terminal and written back into the packet
  and its ticket. Editing a packet's `## Decision` section in VS Code counts too.
- **`/academy:deep-dive <subject>`**: an explainer page on a claim, a concept, a
  paper, an experiment or a direction. Every statement on it shows its status, so a
  sketch never looks like a theorem.
- **`/academy:board`**, **`/academy:status`**, **`/academy:usage`**: the tickets, the
  health of every instance, and the usage report.

Each role keeps its own public skills (`/author:next`, `/expert:lookup`,
`/scientist:queue`, ...); the desk only routes to them.

## Reviewing packets

`/academy:review` writes one private dashboard page (every open packet, grouped by
instance, with the status legend), then asks you each pending decision in the
terminal. Each answer is written into the packet's `## Decision` section and appended
to its ticket's thread. From a shell, the same is:

    py C:\Work\Math\academy\academy\scripts\packets.py list --open
    py C:\Work\Math\academy\academy\scripts\packets.py show P-0006
    py C:\Work\Math\academy\academy\scripts\packets.py decide P-0006 --decision 1 --choice a --comment "..."

## Deep-dives

`/academy:deep-dive <subject>` takes `s1:BOUND-2`, `paper:lem:...`, `lab:<name>`,
`bib:MS91` (or `MS91`), `concept:<term>` or a direction id. A script gathers the input
(`gather_deep_dive.py`), the read-only explainer writes the prose, and
`render_packets.py --deep-dive` renders it. The renderer refuses a page on which any
statement lacks a status. A copy stays at `C:\Work\Math\board\deep-dives\`, and a
re-run updates the same page. Known gap (2026-09-28): a claim whose dependencies include
a Slope1 definition object is refused, because definitions carry no status; see
`board/human/SUMMARY.md`.

## Each role's entry skills

| Role (instance, home) | Start with | Also |
|---|---|---|
| Author (`author@bi`, BilliardIllumination) | `/author:status`, `/author:next` (at most 3 items, chosen by script from `Drafts/agenda.md`, `Drafts/roadmap.md` and the board) | `/author:notes` (files your `\Roey` notes), `/author:agenda`, `/author:sweep`, `/author:audit-notation`, `/author:presync` |
| Researcher (`researcher@slope1`, Slope1illuminationResearch) | `/researcher:status`, `/researcher:inbox` | `/researcher:explore <DIR-n>`, `/researcher:prove <id>`, `/researcher:corollaries`, `/researcher:generalize`, `/researcher:review-experiment`, `/researcher:settle`, `/researcher:claims` |
| Expert (`expert@ts`, papers) | `/expert:lookup <question>` (the clerk, answered inline), `/expert:inbox` | `/expert:cite`, `/expert:verify <id>`, `/expert:referee`, `/expert:litwatch`, `/expert:library-index`, `/expert:domain`, `/expert:status` |
| Scientist (`scientist@ts`, FlatSurfLab) | `/scientist:status`, `/scientist:inbox` | `/scientist:experiment`, `/scientist:queue`, `/scientist:env check lingo`, `/scientist:api-check`, `/scientist:examples-audit` |
| All roles | `/academy:desk`, `/academy:review` | `/academy:board`, `/academy:status`, `/academy:usage`, `/academy:deep-dive`, `/academy:init` |

Only a status keeper changes a status: the Researcher's `claim-keeper`, or you. Without
grounds the server refuses the change. Grounds are two agreeing reviews, or your word
quoted from a ticket or packet.

## The pieces

- **Roles** (`docs/roles.md`): Author writes a paper, Researcher owns a research
  domain's notebook, Expert keeps the library and reviews proofs, Scientist runs
  the computations.
- **Instances** (`workspace.json`): a role bound to one home and its domains, for
  example `author@bi` in BilliardIllumination. A second paper is a second Author
  instance, not a new plugin.
- **The board** (`C:\Work\Math\board`): one Markdown file per ticket, in the
  receiver's folder, with an append-only thread. Your own inbox is `human/`.
- **Packets**: what a role hands back for review, with a summary, what is
  established versus assumed, and numbered decisions for you.
- **Grading**: whoever produces never grades, whoever grades never edits, and
  whoever commissions never grades. Proofs are reviewed by Expert, experiments by
  Researcher.

## Budget

At most three items per run, run one after another; orchestrators on Sonnet; no
relaunch after a usage-limit error. A ticket carries its own budget. The weekly
usage packet flags overruns.

## What is checked by machine

The hooks and the MCP server enforce who may call which tool, ticket field ownership
and transitions, append-only threads, generated views, and the grounds for a status
change (two agreeing verdicts, or your word). See `docs/protocol.md`.
