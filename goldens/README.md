# Phase-0 goldens

Captured 2026-09-27 (plan section 9, step 0), read-only on the homes. Every later
migration phase must end green against these files: the new code paths (plugin
scripts, registry engine, shims) must reproduce them, modulo the dated lines noted
below.

Home state at capture (unchanged afterwards; verified with `git status --porcelain`):

| Home | Branch | HEAD | Working tree |
|---|---|---|---|
| BilliardIllumination | main | 220ac1bc1040a422726b5f83b9938f00fa8b422d | clean |
| FlatSurfLab | housekeeping-api-split | 49c9072fdf5504e578de84efbdf5190926f0bce6 | 5 modified experiment scripts, 1 modified + 4 untracked results (pre-existing) |
| Slope1illuminationResearch | main | 9cbe45b6e0f6abda9f50f29f17961b63054ff6a5 | clean |

All commands were run from Git Bash with `PYTHONIOENCODING=utf-8` and
`PYTHONDONTWRITEBYTECODE=1`. **`PYTHONIOENCODING=utf-8` is required**: without it,
`check_paper.py` crashes with `UnicodeEncodeError` (cp1255 console codepage) as soon
as a finding contains a non-ASCII character, when stdout is redirected to a file.
Each captured file ends with an `exit=<code>` line appended by the capture command.

**Line endings.** The goldens are stored LF. Live checker output on Windows is CRLF
(the Group B review found `check_paper.txt` identical to the plugin checker's output
under `diff --strip-trailing-cr`, and the plugin and home checkers byte-identical to
each other). A gate comparing against a golden must normalise line endings first
(CRLF to LF); a strict byte comparison fails on the line endings alone.

## Files

### Paper checker (BilliardIllumination)

| File | Content | Reproduce (cwd `C:\Work\Math\BilliardIllumination`) |
|---|---|---|
| `check_paper.txt` | Checker output without the build-log summary and without writing the registry. 153 statements, 2 violations, 125 warnings (115 of them R7), exit 1. | `py scripts/check_paper.py --no-log --no-registry` |
| `check_paper_with_registry.txt` | Same run, writing the registry outside the home instead of into `Drafts/statements.md` (the file was then moved to `views_regenerated/bi__Drafts__statements.md`). Identical to `check_paper.txt` plus one `Registry written:` line. | `py scripts/check_paper.py --no-log --registry C:/Work/Math/academy/goldens/check_paper_registry.md` |
| `check_paper_with_log.txt` | Full run including the `.build/` summary (`BUILD: errors 0, undefined 0, multiply 0, bibtex warnings 3, ?? 0`). Takes about 60 s (synctex per R7 fragment). | `py scripts/check_paper.py --no-registry` |
| `check_paper_selftest.txt` | Built-in self-test, 0 checks failed. | `py scripts/check_paper.py --self-test` |
| `paper-gate-baseline.txt` | Copy of `.claude/paper-gate-baseline.txt` (the commit baseline, 14 accepted findings). | `cp .claude/paper-gate-baseline.txt` |

Caveat: R7 (clipped fragments) reads `.build/main.pdf` and `main.synctex.gz` even with
`--no-log`, so the R7 lines depend on the last LaTeX build, not only on the sources. A
rebuild (e.g. LaTeX Workshop on save) can change them. Compare R1-R6 strictly and R7
only against the same build.

### Registries

| File | Content | Reproduce |
|---|---|---|
| `registry_lab.txt` | 25 claims, 0 errors, 0 warnings, exit 0 | cwd FlatSurfLab: `py scripts/claims.py check` |
| `registry_paper.txt` | 115 claims, 1 error, 27 warnings, exit 1 | cwd FlatSurfLab: `py scripts/claims.py --repo C:/Work/Math/BilliardIllumination check` |
| `registry_s1.txt` | 183 entities, 0 errors, 0 warnings, exit 0 | cwd Slope1illuminationResearch: `py tools/kb.py check` |
| `show_lab.txt` | `show` for `lab:arith-dark-pairs-pm1` (open), `lab:descent-family-n-le-7` (supported), `lab:fact-compatible-half-translation-genus2` (dropped) | `py scripts/claims.py show <id>` |
| `show_paper.txt` | `show` for `paper:conj:origami-slope`, `paper:cor:arith-billiard-finite`, `paper:thm:moeller-primitive` | `py scripts/claims.py --repo C:/Work/Math/BilliardIllumination show <id>` |
| `show_s1.txt` | `show` for `BOUND-1` (claim), `GA-2T` (assumption), `EX-2x1` (example) | cwd Slope1: `py tools/kb.py show <id>` |

Outputs contain absolute Windows paths (e.g. `C:\Work\Math\BilliardIllumination\claims\paper\...`);
a new engine run from another location must normalise them before comparing.

### Test suites

| File | Result | Reproduce |
|---|---|---|
| `tests_lab_claims.txt` | 21 tests, OK | cwd FlatSurfLab: `py -m unittest tests.test_claims -v` |
| `tests_s1_kb.txt` | 32 tests, OK | cwd `Slope1illuminationResearch/tools`: `py -m unittest test_kb -v` |

Together 53 tests (the plan and the merge proposal say 47; the suites have grown).
Both suites work in temporary directories and leave the homes untouched.

### Generated views

`views/` holds byte copies of the committed generated views, hashed in
`views.sha256` (`cd views && sha256sum *`). Names are `<home>__<path with / as __>`:

- FlatSurfLab: `claims/INDEX.md`, `claims/index.html`
- BilliardIllumination: `claims/INDEX.md`, `claims/index.html`, `Drafts/experiments.md`, `Drafts/statements.md`
- Slope1: `STATUS.md`, `INDEX.md`, `OPEN.md`, `assumptions/README.md`,
  `computation/verdicts.md`, `computation/runs.md`, `kb/claims.json`, `site/index.html`
  (the last is gitignored, but `kb.py build` writes it)

Freshness of the committed views, i.e. would the current tools regenerate them byte for byte:

| View | Fresh? | Difference |
|---|---|---|
| lab and BI `claims/INDEX.md` | yes | |
| lab and BI `claims/index.html` | no | only the `Generated ... on <date>` line |
| BI `Drafts/experiments.md` | no | job-state column: the committed file says `running` for three jobs that the local queue now records as `done ok` |
| BI `Drafts/statements.md` | no | the date line, the warning count (102 -> 125, the R7 findings) and two line numbers in `sections/introduction.tex` (83/93 -> 84/94) |
| all Slope1 views | yes | `kb.py build` on a copy wrote nothing but `kb/kb.sqlite` |

`views_regenerated/` (hashes in `views_regenerated.sha256`) holds what the current
tools produce for the four non-fresh views. A new engine is compared against these,
after masking the date line. They were produced without writing into any home:

- `bi__Drafts__statements.md`: the `--registry` run above.
- `lab__claims__index.html`, `bi__claims__index.html`, `bi__Drafts__experiments.md`:
  `render_html(load(registry_root(repo))[0])` and `render_experiments(bi)` from
  `FlatSurfLab/scripts/claims.py`, imported with `importlib` (equivalently
  `py scripts/claims.py --repo C:/Work/Math/BilliardIllumination ledger --stdout` for
  the ledger, which prints one extra trailing newline).
- Slope1 freshness: `git ls-files -z | tar --null -T - -cf - | tar -xf - -C <copy>/s1`,
  plus `site/`, with `<copy>/papers/index.md` copied from `C:\Work\Math\papers` (kb.py
  reads `../papers/index.md`), then `py tools/kb.py build` in the copy and `cmp` of each view.

### Queue (FlatSurfLab)

| File | Content | Reproduce |
|---|---|---|
| `queue_list.txt` | 34 jobs, all under `done`; `pending` and `running` empty | cwd FlatSurfLab: `powershell -NoProfile -File scripts/queue.ps1 -List` |
| `queue_dirs.txt` | Listing of `queue/{pending,running,done,parked}` and `queue/config.json` | `ls queue/<dir>`, `cat queue/config.json` |

`queue.ps1 -List` was read first: it loads `queue/config.json` and the job files and
makes no network call (no `Reachable`/`Remote`/`ssh`/`scp`). Its only side effect is
`New-Item -Force` on `queue/{pending,running,done}`, which already existed. The plan's
`queue.ps1 -Status` was **not** captured: it ssh-es to lingo, which this run must not contact.

## Plugin loading (plan step 0, checked 2026-09-28)

- **`claude plugin validate`** passes on the marketplace (`C:\Work\Math\academy`) and
  on each of the five plugins (`academy`, `author`, `researcher`, `expert`,
  `scientist`), with `~/.local/bin/claude.exe` (not on the Git Bash PATH).
- **A linked plugin loads its `.mcp.json`.** `claude --plugin-dir <dir> mcp list`
  reports `plugin:academy:academy: py <dir>/mcp/server.py - Connected`, both for
  `<dir>` = `C:\Work\Math\academy\academy` and for `<dir>` = a directory junction
  pointing at it (Windows refused an unprivileged symbolic link, so the junction
  stood in; it was removed afterwards). The tools therefore appear as
  `mcp__plugin_academy_academy__<tool>`, which the `mcp_write_gate` matcher
  `mcp__.*academy.*` covers, as it covers `mcp__academy__<tool>` from the
  `claude mcp add -s user` fallback.
- **Still open:** the `~/.claude/skills/<name>` link route itself was not exercised,
  because that means changing `~/.claude` (phase 2 does it, after
  `academy-restore.ps1` exists). Check it then with `claude mcp list` in a home; only
  if `plugin:academy:academy` is missing is the `claude mcp add -s user` fallback needed.
- `queue.ps1 -Status` stays uncaptured on purpose (it contacts lingo); `-List` above
  replaces it.

## Line endings

Python on Windows writes captured stdout with CRLF. The captured `*.txt` outputs were
normalised to LF (`sed -i 's/\r$//'`); compare new output after the same normalisation.
`paper-gate-baseline.txt` and everything under `views/` and `views_regenerated/` are
byte copies and were not normalised (the hashes are of the bytes).

## Registry migration reports (Group D, 2026-09-28)

- `r2-requote-equality.md`: the R2 requote of the 140 lab/paper records, old reader vs
  new parser, field by field (140/140 equal as data).
- `r3-federation-resolutions.md`: the new resolutions of `s1:` ids from federation
  through profiles.
- The engine's own gate against this directory is
  `academy/academy/registry/tests/test_acceptance.py` (run against the `*-academy`
  worktrees; skipped where they are absent).

## Schema v2 (R5, Group D, 2026-09-28)

After R5 the worktrees hold schema-v2 records, so the phase-0 registry goldens above
describe the v1 records only; the R1-R4 comparisons in `test_acceptance.py::TestGoldens`
are skipped on migrated worktrees, and `TestR5` is the gate:

| File | Content |
|---|---|
| `r5-mapping-report.md` | The R5 mapping report: seven machine checks (all PASS), the field table, the old -> new status of every file with its projection class before and after, the split cases, the judgement calls, the changed statement hashes. Generated by `py -m registry.migrate_v2` |
| `r5-mapping.json` | The same, machine-readable |
| `r5-pre-migration/{lab,paper,s1}/` | Byte copies of the 288 records as they were before R5 (the R2-requoted v1 files); `TestR5` re-runs the migration from them and compares with the worktrees byte for byte |
| `r5-proposed-reviews/` | Proposed homes of Slope1's 28 verdict files (copies; `MANIFEST.md`); nothing was written into `C:\Work\Math\papers` |
| `r5/registry_{lab,paper,s1}.txt` | `check` after R5 through the shims (normalised as above). lab and paper are identical to phase 0; s1 differs only by `183 -> 186 entities` (the three split cases) |

Regenerated views after R5 (in the worktrees, uncommitted): lab and BI `claims/INDEX.md`
(identical to phase 0 except the lab's `dropped` heading, now a lifecycle blurb) and
`claims/index.html` (five-cell evidence rows, `modulo / open`), BI `Drafts/experiments.md`
(identical to `views_regenerated/`), Slope1's `STATUS.md`, `INDEX.md`, `OPEN.md`,
`kb/claims.json`, `site/index.html` (v2 status words; three new rows).

## The notebook layout (R6, Group D, 2026-09-28)

After R6 Slope1's records are under `objects/<kind>/`, so `TestR5` is skipped in turn and
`test_acceptance.py::TestR6` is the gate:

| File | Content |
|---|---|
| `r6/registry_{lab,paper,s1}.txt` | `check` after R6 through the shims (normalised as above). lab and paper are identical to R5 (and phase 0); s1 differs from R5 only by `186 -> 188 entities` (the two directions) |
| `r6-pre-migration/s1/` | Byte copies of the s1 files R5 left alone and R6 moves: `notes/`, `computation/verdicts/`, `computation/runs/` (identical to the branch base 9cbe45b); `TestR6` re-runs R5 from `r5-pre-migration/`, adds these, runs `migrate_r6`, and compares with the worktrees byte for byte |
| `r6-pre-migration/lab-claims-post-r5/` | The 25 lab records after R5, before R6's two ref rewrites (for review and rollback; not read by the tests) |
| `slope1-roster-coverage.md` | The retired Slope1 roster, file by file, against the plugins that cover it |

The old-to-new path table of every moved Slope1 file is in the worktree,
`Slope1illuminationResearch-academy/kb/r6-path-map.md`.

## Review fixes (Group D, 2026-09-28)

- `r6/registry_s1.txt` is regenerated: `check` now warns on a `modulo` item that is not a
  record id (plan section 6: `modulo: [ids]`), 5 warnings on GEO-3, GEO-15, GEO-30 (two)
  and CRIT-20. `TestR6` masks those lines when it compares with R5.
- **`show` after R5, against the phase-0 goldens** (check (2) of this directory):
  - s1 (`show_s1.txt`): the frontmatter is the v2 file's (kind, lifecycle, the v2 field
    order and quoting, evidence and history rows in the frontmatter). The text below it
    is the phase-0 text, except the `## History` section, which R5 moved into the
    frontmatter, and the v2 status words in an example's claim lines (`Proved` ->
    `proved`, `Disproved` -> `refuted`). Before the review fix a v2 record printed only
    its frontmatter; `TestR6.test_show_s1_keeps_the_statement` now holds this.
  - lab and paper (`show_lab.txt`, `show_paper.txt`): the printed record is the v2 file:
    new `kind`, `lifecycle` and `domain` lines; the v2 field order (`tags` and `open`
    before `evidence`); flow lists for short lists where phase 0 had block lists; the
    dialect's re-quoting of values with `:` or `#`; five-cell evidence rows (`- ` for the
    run id); the migration's history row (`schema v2 migration (R5)`). The data is the
    R5 mapping (`r5-mapping-report.md`); the back-links (`cited by`) are identical to
    phase 0 (`TestR6.test_show_lab_and_paper_back_links`).
- **Statement hashes.** 39 hashes changed in R5 (all 18 assumptions, all 21 examples;
  listed in `r5-mapping-report.md`) because `## History` left their bodies. None is a
  status-bearing claim, but any review, verdict or deep-dive keyed on one of them no
  longer matches and must be re-run before it serves as grounds.
- The BI main checkout is **not** clean: ` M Drafts/statements.md` (mtime 01:25, before
  every Group D file) and `?? .claude/paper-gate.json` (mtime 10:14, inside the Group D
  window, provenance unknown). Group D wrote to neither as far as its own records show,
  but cannot certify the checkout untouched.
