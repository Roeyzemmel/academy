# Roles and rosters

Plan section 3. The roster that the code enforces is `academy/permissions.json`
(`roster`, `groups`, `tools`); this page explains it. Each role plugin's `README.md`
lists its agents with their jobs, its skills, scripts and hooks; each agent's model,
effort and fallback are in its file's frontmatter, and the fallback rule (with the
graders' two equal primaries, Fable and Opus 5.5) is
`academy/references/roster-rules.md`, "Model fallback".

**The ticket chain.** Tickets between role plugins go only to a neighbour in
`[author, expert, researcher, scientist]`, filed by a liaison of that direction; a
request that crosses a middle plugin carries `final_to` and is forwarded by that
plugin's relay. The liaisons, the relays, the hop limit and the exemptions are
`academy/permissions.json` `tickets.edges`, described in `docs/protocol.md`
section 5.1.

## academy (base plugin)

Generic best practice and shared plumbing. No instances of its own: its agents act
for the home they run in. It has no README; its agents are:

| Agent | Job |
|---|---|
| `concierge` | Behind `/academy:desk`: routes Roey's requests |
| `explainer` | Behind `/academy:deep-dive`: read-only, grades nothing |
| `usage-analyst` | The weekly usage packet |
| `secretary` | Behind `/academy:decide`: phrases pending-decision batches in plain language; read-only, records nothing |

Skills: `desk`, `board`, `review`, `decide`, `deep-dive`, `status`, `init`, `usage`,
and the best-practice skills `rigor`, `status-vocabulary`, `citation-discipline`,
`notation-discipline`, `honest-reporting`.

## Author (one per paper): `author/README.md`

Writes the paper. Its only neighbour is the Expert; a request for the Researcher or
the Scientist is a `research` ticket to the Expert with `final_to`.

## Expert (the library): `expert/README.md`

Keeps the library, reviews proofs, referees papers. Neighbours: the Author and the
Researcher. Relays: `research-intake` (author -> researcher) and `paper-liaison`
(researcher side -> author).

## Researcher (one per research domain): `researcher/README.md`

Owns the research notebook and the claim statuses (`claim-keeper`); `/researcher:campaign` runs a capped portfolio of approaches on one claim. Neighbours: the
Expert and the Scientist. Relays: `experiment-spec` (expert -> scientist) and
`lit-request` (scientist -> expert / author).

## Scientist (the lab): `scientist/README.md`

Runs the computations and keeps the lab's code. Its only neighbour is the Researcher;
a request for the Expert or the Author goes to the Researcher with `final_to`.

## Rules that hold across roles

- The producer never grades its own work; the grader never edits what it grades;
  the commissioning agent never grades.
- The read-only group (`explainer`, `clerk`, `secretary`, and the graders) calls no
  write tool. A grader's verdict reaches the files through a SubagentStop hook;
  `secretary` never writes at all, and `/academy:decide` is the only caller of
  `AskUserQuestion` and the only one that records an answer.
- Proofs reach `proved` / `proved-modulo` only through two agreeing proof reviews;
  computations reach `supported` / `refuted` / `refuted-as-stated` only, never
  `proved`.
- An agent of a role plugin acts only for an instance of its own role
  (`docs/protocol.md` section 1).
