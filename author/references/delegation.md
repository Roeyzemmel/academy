# What the Author delegates: sources and computation

The Author writes the paper; it neither keeps a library nor runs computations. Both
belong to other roles, reached through the board. This file states the standing rules
for every Author home; the home's own `.claude/rules/` add only what is particular to it
(for example which machine the lab runs on).

**Which instance.** Never hard-code another instance's name. The Expert and the
Scientist for this paper are the instances of those roles that share one of the home's
`domains` (`.claude/academy.json`), listed in the workspace map (`workspace.json`,
MCP `workspace_get`); their homes are in the same map, and in the environment as
`$ACADEMY_HOME_<ROLE>_<NAME>` (for example `ACADEMY_HOME_SCIENTIST_X` for `scientist@x`). Where several share the domain, `agenda.py gaps --file`
takes the first by name and says so; file by hand (`board.py new`) to choose. The ticket
kinds and receivers are the routing tables in `../skills/inbox/references/routing.md`
(generated from `scripts/routes.py`); the role cut is
`../../academy/references/roster-rules.md`.

## Sources are the Expert's

The library (full texts, `index.md`, one card per relied-on statement, the review
records) is the Expert's home. Its `README.md` and the Expert plugin (`/expert:lookup`,
`/expert:cite`, the `librarian` and the `clerk`) are the authority.

- **Look before fetching.** A quick question about a cited result goes to the clerk
  (`/expert:lookup`, or the MCP `library_lookup` / `library_search`); never fetch from
  the web a paper the library may hold.
- A new citation or pinpoint is a `cite` ticket to the Expert (`/expert:cite`); only the
  librarian edits the bibliography (`author.bibWriters`, enforced by the bib gate).
- The library's views in `Drafts/` (`sources.md`, `related_work.md`, `verdicts.md`) are
  **generated** by the Expert (`expert/scripts/ledger_views.py`); change the record,
  never the view.
- Quoting (verbatim, with the source version; an extraction is never the text) is
  `academy:citation-discipline`.

## Computation is the Scientist's

Experiments are run by the Scientist instance of the paper's domain. Its `CLAUDE.md`,
its `.claude/academy.json` (environment profiles and workers, the run policy) and the
Scientist plugin (`/scientist:*`, the `experimenter` agent, `/scientist:examples-audit`
for definition tests) are the authority; nothing about the lab is restated in an Author
home.

- An experiment the paper needs is a `research` ticket to the Expert with
  `final_to: scientist` (the `experiment` ask in the routing table), naming the
  `<ns>:<label>` it bears on; the Researcher's experiment spec files it to the Scientist.
  A definition test is `/scientist:examples-audit`.
- Each experiment is a lab claim with `bears_on: <ns>:<label>`. `Drafts/experiments.md`
  is **generated** from those claims by `registry.py ledger`; never edit it by hand.
- What a computation established is in the registry (`claims_show <lab-ns>:<name>`), not
  in prose. A result is graded by the Researcher's experiment reviewers
  (`/researcher:review-experiment`) before it is cited, and only a settled lab claim
  (`supported` with its bound and class, `refuted`, or `dropped`) answers a question; an
  `open` one does not, whatever its jobs say.
