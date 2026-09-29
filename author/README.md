# author: the Author role plugin

One Author instance per paper (plan section 3.2); the first is `author@bi`
(BilliardIllumination). The instance's home holds the paper, `Drafts/agenda.md`,
`Drafts/roadmap.md` and `.claude/academy.json`; this plugin holds the logic. The
contracts it codes against are the academy repo's `docs/protocol.md`,
`docs/config.md` and `docs/packet-template.md`; the standing rules are
`academy/references/budget.md` and `roster-rules.md`.

Each agent's model, effort and fallback are in its file's frontmatter (the fallback
rule: `academy/references/roster-rules.md`, "Model fallback").

| Agent | Job |
|---|---|
| `math-writer` | Exposition from established results; a new argument becomes a `research` ticket to the Expert (`final_to: researcher`) |
| `math-editor` | Decided edits, `[copy]` mode (was copy-editor), landing verdicts and the recolour |
| `tex-engineer` | The LaTeX toolchain, the build, `check_paper.py` and its tests (was latex-fixer) |
| `figure-maker` | Figures, after the pack's `figures.md` |
| `note-sweeper` | The machine-note sweep |
| `notation-auditor` | The home's notation decisions; domain notation goes to the Expert as a ticket |

Skills: `/author:next` (replaces `tier`), `/author:agenda`, `/author:notes` (was BI's
`roadmap`), `/author:sweep`, `/author:audit-notation`, `/author:presync`,
`/author:status`, and `paper-method` (preloaded by the writing agents).

Hooks (`hooks/hooks.json`), each a silent no-op outside an Author home:
`tex_edit_check` (PostToolUse edits: checker + dirty marker), `bib_gate` (only
`expert:librarian` edits the bibliography), `notation_scope_guard` (PreToolUse edits:
the notation-auditor edits only the home's `notation-decisions.md`; scoped by agent),
`commit_gate` (Bash|PowerShell, scoped by
the repo actually committed), `build_gate` (SubagentStop of a writer, namespace-stripped,
under `.build/.lock`).

Ticket chain: the Author's only neighbour is the Expert. A request for the Researcher or
the Scientist is a `research` ticket to the Expert with `final_to`, which the Expert's
`research-intake` relays. Which agents may file to the Expert is `academy/permissions.json`
`tickets.edges`, described in `docs/protocol.md` section 5.1.

Scripts and formats: `references/scripts.md`, `references/formats.md`. Tests:
`py -m unittest discover -s author/tests -t author/tests` from the academy repo.
