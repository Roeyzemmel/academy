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

## Not captured here

- `claude plugin validate` on a stub and whether a symlinked plugin loads its `.mcp.json`
  (also listed in plan step 0) were outside this task.

## Line endings

Python on Windows writes captured stdout with CRLF. The captured `*.txt` outputs were
normalised to LF (`sed -i 's/\r$//'`); compare new output after the same normalisation.
`paper-gate-baseline.txt` and everything under `views/` and `views_regenerated/` are
byte copies and were not normalised (the hashes are of the bytes).
