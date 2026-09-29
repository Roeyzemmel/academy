# Roles and rosters

Plan section 3. The roster that the code enforces is `academy/permissions.json`
(`roster`, `groups`, `tools`); this page explains it. Model notation: a primary
model, then "→" the fallback the launching session applies and names. For the graders
(`experiment-reviewer`, `rigor-reviewer`, `referee`) Fable and Opus 5.5 are equal
primaries (Roey, 2026-09-24, reconfirmed 2026-09-28): "Fable → Opus" there means the
substitution keeps full authority; only a verdict on another model (Sonnet, Haiku, an
older Opus) is capped (roster-rules.md, "Model fallback").

## academy (base plugin)

Generic best practice and shared plumbing. No instances of its own: its agents act
for the home they run in.

| Agent | Model | Job |
|---|---|---|
| `concierge` | Sonnet | Behind `/academy:desk`: routes Roey's requests |
| `explainer` | Opus → Sonnet | Behind `/academy:deep-dive`: read-only, grades nothing |
| `usage-analyst` | Haiku → Sonnet | The weekly usage packet |
| `secretary` | Sonnet → Haiku | Behind `/academy:decide`: phrases pending-decision batches in plain language; read-only, records nothing |

Skills: `desk`, `board`, `review`, `decide`, `deep-dive`, `status`, `init`, `usage`,
and the best-practice skills `rigor`, `status-vocabulary`, `citation-discipline`,
`notation-discipline`, `honest-reporting`.

## Author (one per paper)

Liaisons: files to the Expert as `main`, `math-writer`, `notation-auditor` and `figure-maker`. A request that must reach the Researcher or the Scientist is a `research` ticket to the Expert with `final_to`.

| Agent | Model | Job |
|---|---|---|
| `math-writer` | Opus → Sonnet | Exposition from established results; a new argument becomes a `research` ticket to the Expert with `final_to: researcher` |
| `math-editor` | Sonnet → Opus | Editing, copy-editing, the recolouring edit |
| `tex-engineer` | Sonnet → Opus | The LaTeX toolchain, the build, the checker and its tests |
| `figure-maker` | Sonnet → Opus | Figures, following the pack's figure conventions |
| `note-sweeper` | Sonnet → Opus | Machine-note sweeps |
| `notation-auditor` | Sonnet → Opus | The home's notation decisions; domain notation goes to Expert as a ticket |

## Researcher (one per research domain)

Liaisons: to the Expert `main`, `lead-researcher`, `prover`, `lit-request`; to the Scientist `main`, `lead-researcher`, `experiment-spec`. Relays: `experiment-spec` (expert -> scientist) and `lit-request` (scientist -> expert / author).

| Agent | Model | Job |
|---|---|---|
| `lead-researcher` | Sonnet → Opus | Owns a direction and commissions work; grades nothing |
| `prover` | Fable → Opus | Definitions, proofs, corollaries, generalizations |
| `experiment-reviewer` | Fable → Opus | Reviews experiments (verdicts SOUND / SOUND MODULO / GAP / BROKEN) |
| `claim-keeper` | Haiku → Sonnet | The only agent that changes a status, in any namespace; the server re-checks its grounds |
| `experiment-spec` | Sonnet | Relay, expert -> (researcher) -> scientist: fails fast or writes the experiment spec and forwards it |
| `lit-request` | Haiku | Relay, scientist -> (researcher) -> expert / author: states the cite or literature ask and forwards it |

## Expert (the library)

Liaisons: to the Author `librarian`, `review-chair`, `research-intake`, `paper-liaison`; to the Researcher `research-intake`, `review-chair`. Relays: `research-intake` (author -> researcher) and `paper-liaison` (researcher side -> author).

| Agent | Model | Job |
|---|---|---|
| `clerk` | Haiku | Fast answers from the cache and index; escalates misses to the librarian |
| `librarian` | Sonnet → Opus | The only editor of the bibliography, the cards and the index |
| `related-work-scout` | Sonnet → Opus | Literature watch |
| `review-chair` | Sonnet → Opus | Runs proof review and applies the decision table; grades nothing |
| `rigor-reviewer` | Fable → Opus | Proof review (CONFIRMED / PLAUSIBLE / GAP / DISPROVED); read-only |
| `referee` | Fable → Opus | Whole-paper referee report; read-only |
| `research-intake` | Sonnet | Relay, author -> (expert) -> researcher: fails fast or writes the research block and forwards it |
| `paper-liaison` | Haiku | Relay, researcher side -> (expert) -> author: restates a question or result in the paper's terms and forwards it |

## Scientist (the lab)

Liaisons: to the Researcher `main` and `experimenter`; the other lab agents file only inside the lab.

| Agent | Model | Job |
|---|---|---|
| `experimenter` | Sonnet → Opus | Designs and writes experiments |
| `developer` | Opus → Sonnet | The lab's code, the runner and the environments, test-first |
| `test-engineer` | Sonnet → Opus | Tests written independently of the developer; reviews its diffs |
| `upstream-contributor` | Sonnet → Opus | Drafts upstream issues and patches; Roey files them |
| `api-prober` | Sonnet → Opus | Confirms library calls before they are used |

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
