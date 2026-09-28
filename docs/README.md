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
