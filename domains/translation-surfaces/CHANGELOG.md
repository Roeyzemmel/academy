# Changelog — translation-surfaces domain pack

Newest first. One line per change to a pack file; a theorem entry or an API finding
names its section.

## Unreleased — 2026-10-09: the conda env's package list

- `computation/env.txt` (new): the conda-forge packages `env.py setup <profile>` installs
  for this domain (moved from the Scientist plugin's `setup_env.sh`, which now names no
  package), with the gcc/gxx 14 pin and its reason.
- `computation/env-check.py` (new): the import-and-compute check run in a fresh env
  (moved from the same script).

## 0.1.1 — 2026-09-29: scope defaults for experiments

- `computation/README.md`: new section "Scope defaults for experiments" (translation
  surfaces; non-periodic points unless the claim says otherwise), moved here from the
  ticket-chain design (spec 5.2) so that `researcher:experiment-spec` reads it through
  `domain_get` instead of naming domain objects in the role plugin.

## 0.1.0 — 2026-09-28: the pack is created (academy migration, Group B)

Built from the four old `domain/` skills of claude-flatsurf, as imported under
`academy/_import/flatsurf/domain/`.

**Moved (content unchanged apart from path fixes):**
- `translation-surfaces/references/notation.md` → `notation.md` (header reframed: pack <
  project decisions < draft, per `academy:notation-discipline`; the old "the drafts win,
  update this file" rule is replaced by a `notation` ticket to Expert).
- `translation-surfaces/references/theorems/{INDEX,illumination,orbit-closures,veech,strata,unverified}.md`
  → `theorems/`; `theorems/open-problems.md` → `open-problems.md` at the pack root (the
  pointers in `theorems/INDEX.md` and `open-problems.md` updated). Section numbers
  unchanged, so "§1.2" etc. still resolve.
- `translation-surfaces/references/tikz-figures.md` → `figures.md`. **Fixed** the stale
  advice "keep each figure under `figures/` and `\input` it": the project decides the
  figure directory and inclusion command (BilliardIllumination: `tikz/` +
  `\includestandalone`); the preamble section now says the project decides where the
  libraries are loaded.
- `flatsurf-computation/references/api/*.md` → `computation/api/`. `INDEX.md`'s "One copy"
  and "Writing" paragraphs rewritten for the pack.
- `flatsurf-computation/scripts/{billiard_trace,origami_illumination}.py` →
  `computation/scripts/` (self-tests pass).

**Stripped from `computation/api/` (machine and job records), kept verbatim elsewhere:**
- `setup.md` §12, `libgap.md` §12.2, §12.7 intro, §12.7.5, `INDEX.md`, `quick-reference.md`
  (pyflatsurf row), `origamis.md` (§12.5 heading, the `fslab/vh.py` pointer): the lingo
  paths and prefix, `/home/roey`, job and result records, the copies of the old file →
  `docs-notes/extracted-environment.md` (destined for
  `FlatSurfLab/docs/environment.md`). The API findings stay, reworded as "two targets" /
  "a remote server".
- `libgap.md` §12.6 heading and timing, §12.7.6, §12.8: the (Q2) search record
  (`gapinv.py`, `gap_reverify.py`, `_BFS_GAP` / `_COVER_GAP`, job `20260920-123729`) →
  `docs-notes/extracted-q2-record.md` (destined for Slope1 `notes/`). §12.7.6 is
  now a generic entry (RepresentativeAction in a subgroup, conjugator non-uniqueness,
  timing); §12.8 keeps the refutation, the fix and the usage checks; the two production
  sources are named `SOURCE_A` / `SOURCE_B` in the quoted output.

**New:**
- `skills/translation-surfaces/SKILL.md`: the entry point (trigger description kept from
  the old skill), linking every pack file by relative path.
- `examples.md`: one list with ids unifying the 7 examples of BilliardIllumination's
  `notation-decisions.md`, the 5 of the old `translation-surfaces` skill and the 3 of the
  old `flatsurf-computation` skill; invariants only as stated there, plus pointers to
  values on file in `computation/api/`. Two entries marked [CHECK]/[UNSPECIFIED]
  (`regular-pentagon`, `nmk-triangles`), and the two different "3-square L" origamis in the
  recipes flagged under `L3`.
- `traps.md`: the old skill's four traps (§A); the domain examples cut from
  `math-proof-writing` when it became `academy:rigor` (§B, from
  `docs-notes/removed-domain-examples.md`); the API traps of the old
  `flatsurf-computation` skill plus three from the recipes (§C).
- `computation/README.md`: which tool, the bundled scripts, the recipe index (from the
  old `flatsurf-computation` skill, without the machine table).
- `pack.json`, `tests/test_pack.py`.

**Sent to other plugins:**
- `flatsurf-computation` experiment discipline → `docs-notes/experiment-method-source.md`
  (for `scientist/skills/experiment-method`).
- `latex-paper-writing` generic content and `references/modern-latex.md` →
  `docs-notes/paper-method-source/` (for `author/skills/paper-method`).
- `flatsurf-computation/scripts/{flatsurf-run.ps1,setup_env.sh}` left in `_import` for
  the Scientist's `env.py`.

**Deleted:** `latex-paper-writing/references/macros.md`, `assets/preamble.tex`,
`assets/main-skeleton.tex` (stale; BilliardIllumination's `tex-conventions.md` is
authoritative); the split stubs `theorems.md` and `api-recipes.md` (their text is in the
claude-flatsurf history, c06dbe7 and aded233).
