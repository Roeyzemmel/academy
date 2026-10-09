# Migration log

One entry per phase group (plan section 9b), newest last. Each entry says what was
built, what the gate showed, and what was deferred, so the next group can resume
from here.

## Group A: phases 0-1 (goldens, academy repo, base plugin, MCP, board)

**Built.**
- Phase 0: goldens in `goldens/` (checker output, commit baseline, the three
  registries, generated views, queue listing). See `goldens/README.md`.
- The repo, with the history of `claude-paper` and `claude-flatsurf` imported under
  `_import/` (git subtree); the marketplace; five plugin manifests.
- Contracts: `docs/protocol.md`, `docs/packet-template.md`, `docs/config.md`,
  `academy/permissions.json`, and the shared library `academy/lib/academy_common.py`
  vendored as `<plugin>/scripts/_academy.py`.
- The base plugin: the best-practice skills, the desk, board, review, deep-dive,
  status, init and usage skills, the three agents, the hooks (`session_start`,
  `mcp_write_gate`, `ticket_edit_check`, `generated_view_guard`), the packet and
  deep-dive templates, the dashboard renderer, and the MCP server
  (`academy/mcp/server.py`).
- `session_usage.py` moved from `claude-paper/scripts` to `academy/scripts/`.
- The board repo `C:\Work\Math\board` (one folder per instance plus `human/`).

**Review fixes (2026-09-28).**
- The server now learns the caller through the caller handshake (protocol
  section 1): `mcp_write_gate` records each call it lets through, the server
  consumes the record, writes without one are refused, and the `caller` argument
  is reserved. Before, every agent reached the server as the human, so
  claim-keeper could set any status without grounds and ticket ownership was
  skipped.
- An agent of a role plugin can act only for an instance of its own role.
- `usage_report.py`: the live window has no upper bound, so a transcript still being
  written is counted (the flaky test and the matching live bug).
- `queue_add`, `env_list` and `env_check` exist. `queue_add` checks the submission
  and refuses with "not yet enabled" plus the command that files the job today;
  enabling it is Group C (`scientist/scripts/env.py`).
- `render_packets.py --deep-dive` refuses a bundle with a statement or a chip that has
  no status (was a model-side check in the skill).
- Claim namespaces in the MCP schemas come from `workspace.json`; the legacy set
  (`lab`, `paper`, `s1`) is confined to `LegacyCliBackend`.
- Plugin loading checked: `claude plugin validate` passes, and a linked plugin loads
  its `.mcp.json` (`goldens/README.md`).

**Deferred, by design.**
- `academy/registry/` (plan section 3.1): Group D. Until then the claims tools
  wrap the old command lines (`LegacyCliBackend`), and `claims_set_status` /
  `claims_attach_evidence` answer "not yet enabled" once their checks pass.
- `queue_add` filing a job, and live `env_check` reachability: Group C.
- The role plugins hold only their manifests and the vendored library: Group B.
- The `~/.claude/skills` link route for `.mcp.json`: checked at the phase-2 link
  swap.

**Known limits.**
- Shell writes (Bash, PowerShell) to generated views and board files are not
  parsed by the hooks. The SessionStart reconcile and `ticket_edit_check` report
  board damage afterwards. Shell commands that name the caller handshake directory
  are denied.
- The caller handshake trusts the filesystem: an agent with a shell could forge a
  record. The read-only agents must therefore get no shell (a Group B requirement).

## Group B: phases 2-3 (domain pack, method skills, the four role plugins)

**Built.** The domain pack `domains/translation-surfaces/`, the base plugin's
best-practice skills, and the four role plugins `author/`, `researcher/`, `expert/`,
`scientist/` (agents, skills, scripts, hooks, tests), from the imported copies under
`_import/`. Every plugin passes `claude plugin validate` and its own
`py -m unittest discover <plugin>/tests`.

**Old -> new mapping.** This is the provenance record; the new files do not restate it.

| Old | New |
|---|---|
| paper agents copy-editor + math-editor | `author/agents/math-editor` |
| paper latex-fixer | `author/agents/tex-engineer` |
| paper figure-maker, math-writer, notation-auditor, note-sweeper | `author/agents/*` (same names) |
| paper master-verifier | `expert/agents/review-chair` |
| paper proof-verifier | `expert/agents/rigor-reviewer` |
| paper referee | `expert/agents/referee` |
| paper related-work-scout | `expert/agents/related-work-scout` |
| paper source-checker | `expert/agents/librarian` |
| paper top-researcher | `researcher/agents/lead-researcher` |
| paper skill tier | `author/skills/agenda` + `author/skills/next` |
| paper skills audit-notation, presync, sweep | `author/skills/*` |
| paper skills cite, litwatch, referee, verify | `expert/skills/*` |
| paper skill verify-conclude | `expert/skills/verify/references/conclude.md` |
| paper scripts bib_gate, build_gate, commit_gate, tex_edit_check | `author/scripts/*` |
| paper script session_usage | `academy/scripts/session_usage.py` (Group A) |
| flatsurf agent api-prober | `scientist/agents/api-prober` |
| flatsurf agent claim-keeper | `researcher/agents/claim-keeper` |
| flatsurf agent result-auditor | `researcher/agents/experiment-reviewer` |
| flatsurf skills api-check, experiment, queue | `scientist/skills/*` |
| flatsurf skill claims | `researcher/skills/claims` |
| flatsurf skill verify-result | `researcher/skills/review-experiment` |
| flatsurf script claims_edit_check | `researcher/scripts/claims_edit_check.py` |
| flatsurf scripts commit_gate, experiment_edit_check | `scientist/scripts/*` |
| flatsurf script `_common.py` | adapted into `scientist/scripts/_common.py`; the original is at `scientist/scripts/legacy/flatsurf_plugin_common.py` |
| flatsurf references/sage-review.md | `researcher/skills/review-experiment/checklist.md` |
| domain flatsurf-computation | the pack's `computation/` + `scientist/skills/experiment-method` |
| domain flatsurf-computation scripts flatsurf-run.ps1, setup_env.sh | `scientist/scripts/legacy/`, kept as reference for `env.py` (Group C) |
| domain latex-paper-writing | `author/skills/paper-method` (macros, preamble and skeleton deleted) |
| domain math-proof-writing | `academy/skills/rigor` |
| domain translation-surfaces | the pack |
| stubs api-recipes.md, theorems.md | deleted |
| BI-local experimenter, roadmap, audit-examples | `scientist/agents/experimenter`, `author/skills/notes`, `scientist/skills/examples-audit` |
| Slope1 family-scout, family-experimenter | `researcher/agents/prover`, `scientist/agents/experimenter` |
| Slope1 claim-verifier + refutation-verifier | `expert/agents/rigor-reviewer` |
| Slope1 status-keeper, librarian | `researcher/agents/claim-keeper`, `expert/agents/librarian` |
| Slope1 skills hunt + classify, kb, settle, verify-claim | `researcher/skills/explore`, `researcher/skills/claims`, `researcher/skills/settle`, `expert/skills/verify` |

**Review fixes (2026-09-28).**
- **One commit-target parser.** The Author gate's parser moved into
  `academy/lib/academy_common.py` (`split_segments`, `resolve_dir`, `commit_targets`,
  `commit_targets_or_cwd`, `ShellParseFailure`) and was vendored with
  `sync_common.py`. It handles Git Bash drive paths, heredocs, here-strings,
  `--work-tree`/`--git-dir`, and nested `bash -c` / `powershell -Command`.
  `author/scripts/commit_gate.py` and `scientist/scripts/_common.py` both use it now.
  The Scientist gate no longer turns `/c/Work/...` into `C:\c\Work\...`. This is a
  deliberate lib change.
- **`status_guard`.** In a home that has no `academy.json` yet, the legacy keepers
  `claim-keeper` and `status-keeper` both pass (`_researcher.LEGACY_KEEPERS`). This
  keeps Slope1's live verify-claim -> status-keeper flow working until phase 6. A
  switched-over home accepts only its `registry.statusKeeper`.
- **`explainer`.** It keeps `Write`, but the limit is now mechanical:
  `academy/scripts/explainer_write_guard.py` (PreToolUse,
  Edit|Write|MultiEdit|NotebookEdit) allows only a Write of
  `<board>/deep-dives/<id>.json` and denies everything else. This was chosen over a
  SubagentStop lander because the deep-dive flow hands a JSON bundle to the renderer.
- **`notation-auditor`.** `author/scripts/notation_scope_guard.py` allows only
  `<author home>/.claude/rules/notation-decisions.md`. Author homes come from the
  config or from workspace.json, because BI has no academy.json yet. The guard scopes
  by agent, not by path, so it is silent for every other caller.
- **Experiment-review blindness.** `researcher/scripts/audit_blind_guard.py`
  (PreToolUse, Read|Grep|Glob) keeps `experiment-reviewer` out of the `audits/`
  folder of every researcher home. It is the counterpart of the Expert's
  `review_blind_guard.py`.
- **Turn caps.** rigor-reviewer, referee and experiment-reviewer now have
  `maxTurns: 60`. The cap is high on purpose: a verdict cut off halfway is worthless.
- **docs-notes.** `academy/docs-notes/` moved to the repo-root `docs-notes/`, so the
  base plugin no longer ships the domain previews.
- **Goldens.** `goldens/README.md` now says that comparisons must normalise CRLF.

**Hand-offs (these need write access to repos that are read-only here).**
- **Old-plugin guard (plan section 9, phase 3): NOT DONE, and it blocks Groups C and
  E.** Neither `claude-paper/scripts/_common.py` nor
  `claude-flatsurf/scripts/_common.py` has the early return on `.claude/academy.json`
  yet, because both repos were read-only in Group B. Add it before any home gets
  `.claude/academy.json` (Groups C and E): every old hook exits 0 when
  `.claude/academy.json` is found upward of the event cwd or the edited path.
  Without it, the old and new commit gates, tex checks and experiment checks will
  both fire in that home.
- **Shims at the old script paths (plan section 3.6).** Not in place. They need write
  access to FlatSurfLab, BI and Slope1: the lab's go in with Group C, BI's with
  Group E, Slope1's with Group D.
- **`scientist/scripts/env.py`.** It will absorb run/queue/vpn/setup_env/fsq and the
  two domain-skill scripts now in `scientist/scripts/legacy/`. This is Group C work.
- **superpowers at user scope (phase 4).** This is a precondition. The
  `superpowers:*` skills that `developer`, `experimenter` and `test-engineer` preload
  do not resolve until superpowers is installed at user scope; today it is installed
  at project scope in FlatSurfLab only.

**Open verifications.**
- **`${CLAUDE_PLUGIN_ROOT}` in skill and agent text.** It appears in 27 places, mostly
  as `${CLAUDE_PLUGIN_ROOT}/../academy/...`. Two things are unverified:
  - that Claude Code substitutes the variable in SKILL.md and agent bodies, not only
    in hooks and `.mcp.json`;
  - that `../academy` resolves through the `~/.claude/skills/<name>` links. This
    needs the links named exactly `academy`, `author`, ... side by side.

  Check both at the phase-2 link swap, in a live session. If either fails, every
  script call in those skills fails. The fallback is to resolve the base plugin
  through workspace.json or an `ACADEMY_ROOT` environment variable.

**Known limits.**
- `status_guard` matches Edit|Write|MultiEdit only. It does not intercept a shell
  edit (sed, Set-Content) of a `status:` line by an agent with a shell
  (lead-researcher, experimenter, developer). This is the same limit Group A
  recorded for board files. Afterwards, `claims_edit_check` and the registry's
  `check` report inconsistent records. An explicit drift check against the last
  committed status belongs in the SessionStart reconcile once the registry engine
  exists (Group D).
- The skills still name the human "Roey", in about 100 places, although
  workspace.json has `human.name`. Making them generic is deferred: for the
  single-user setup it is cosmetic.
- Some test fixtures carry domain content: `expert/tests/fixtures.py`,
  `academy/tests/test_mcp.py`, and `scientist/tests/fixtures/lab/*` (real FlatSurfLab
  result JSONs). No agent reads them, and they are kept as realistic fixtures.
- `_import/` still holds the old plugins' shells: `.claude-plugin/plugin.json`,
  `hooks/hooks.json`, `README.md`, `.gitignore` and `.gitattributes`. They have no
  new home and are kept as the record of the imported layout until phase 8.

## Group F: phase 7 (Expert in papers)

**Switched over.** `C:\Work\Math\papers` is a git repo (`main`, nothing committed:
Roey commits) with `.gitignore` (`*.pdf`, `*.src/`, `*_eprint.tar.gz`, `.academy/`,
`.claude/academy.sqlite`) and `.gitattributes` (`*.md`/`*.json` LF; `*.txt` and `*.meta`
`-text`, so the cached extractions, which are CRLF, are stored byte for byte despite the
system-wide `core.autocrlf=true`). `.claude/academy.json` is the config.md example for
`expert@ts` with `paths.views` = `hot.md`, `views/**`.

**Access log reconciled.** The MCP server always wrote `.academy/access.log`; the
config example and the Expert template said `ledgers/access.log`, a tracked folder
nothing wrote to. Fixed on both sides: `library.access_log_path(home)` now reads
`expert.accessLog` from the home's academy.json (default `.academy/access.log`) and
`log_access` writes there; `expert_status.py` reads the same function; `hot.py`
already read the configured log plus the default. docs/config.md and
`templates/academy-json/expert.json` now say `.academy/access.log` (derived, ignored).
Tests: `academy/tests/test_mcp.py` `TestAccessLogPath`.

**Ledger split (Expert scripts).** `ledger_split.py` gained `--verdicts` (review records
`reviews/<ns>/<id>/<date>[-<note>]/{A,B,decision}.md`, `_context.md`; entries it cannot
parse go verbatim to `reviews/_unparsed.md`), card `status` / `status_reason` from the
quote check (the quote is never altered), verbatim pieces in every record plus a
per-ledger manifest `ledgers/<instance>/_manifest-<ledger>.json`, a byte-for-byte
reproduction check, and the mapping report (`--report-dir`). `extract_quote` now needs
the quotation to open near its anchor (one Vo96a bullet had produced a span straddling
two quotations). `cards.py` knows `status`/`status_reason` and makes "verified but the
quote check fails" an error. New `ledger_views.py` rebuilds the three ledgers as
generated views (marker line first; records added later are appended under
`## Added after the migration`) and `--check`s them against the originals. Tests:
`expert/tests/test_hot_and_split.py` `SplitRecordsTests`.

**Result.** 86 cards (17 verified, 69 unverified), 11 block intros, 8 review passes (16
run records, none unparsed), 2 related-work files; all three views identical to BI's
ledgers after the generated-by marker line. The BI ledgers were only read (checksums
unchanged); the BI pointer stubs are Group E's. Report:
`papers/.migration/ledger-split-report.md`. Index: 5 rows added
(`DMTS`, `Dynamics_on_moduli_spaces_of_translation_surfaces`, `KM16`, `KZ75-en`,
`MT02-published`), cells from the files and existing metas only, unknowns marked.
`hot.md` seeded (includes this run's smoke accesses). Handover packet on the board.

**Known limits.**
- `hot.py` tallies `claims_*` accesses, but only the `library_*` tools log accesses, so
  the Claims section of `hot.md` stays empty until the claims tools log too.
- `library_verify_quote` checks `<key>.txt` only, while `cards.py` checks the `.src/`
  first for a source read; a card verified against the source can answer `false` there.

## Group C: phase 4 (Scientist switch-over in FlatSurfLab)

**Built.**
- `scientist/scripts/env.py`: the profiles (`wsl` / `local` / `ssh`), the policy, and the
  job queue over the fsq runner protocol of the legacy `queue.ps1`, with the same
  semantics (uncommitted-script skip, commit pinning to `refs/fsq/<id>`, ids,
  idempotent submit and reconcile, runner-hash check). It takes the legacy `queue.ps1`
  / `run.ps1` flags as well as subcommands. `check <profile> --live` on ssh sends only
  `fsq version` and `fsq status`. Tests: `scientist/tests/test_env.py`, with a fake
  ssh/scp (`tests/fixtures/fake_ssh.py`) and no network.
- Plugin copies: `fsq.sh` (byte-identical, pinned by a test), `run.sh` (`LAB_ROOT`),
  `vpn.ps1`, `setup_env.sh`, and `check_experiments.py` (lab from `--home` /
  `$ACADEMY_LAB_HOME` / cwd, directories from academy.json). Thin frontends
  `queue.ps1` and `run.ps1`. `lab.py cmd` now routes to them.
- MCP `queue_add`: the job is built by `env.py`. It is a dry run (returns the job
  file) unless the lab sets `scientist.queue.mcpAdd: "on"`.
- `report.py file --ask-prefix`.
- `docs/config.md`: `prefix` on every kind, `pushUrl` / `remoteEnv`, `queue.mcpAdd`,
  `scientist.checker`.
- FlatSurfLab worktree `C:\Work\Math\FlatSurfLab-academy` (branch
  `academy-migration` from 49c9072, uncommitted):
  - `.claude/academy.json`; `flatsurf.json` removed;
  - shims `scripts/{queue.ps1,run.ps1,vpn.ps1,check_experiments.py}`;
  - `docs/environment.md`, a trimmed `CLAUDE.md`, `.claude/README.md` and a note in
    `docs/queue.md`;
  - `reports/2026-09-23_ew_ornithorynque_record.md`.

**Gate.**
- `queue.ps1 -List` in the worktree equals `goldens/queue_list.txt`, over a snapshot
  of the live job files.
- Lab `tests/run_all.py`: 321 OK, 116 Sage skips.
- Suites: scientist 92 OK, academy 223 OK; author, researcher and expert green.
- lingo, read-only: VPN up, runner 5f20b8ac... equal to the plugin's, spool empty.
- Board: report packet P-0002 and review ticket T-0001 (to researcher@slope1, ask
  marked `dry-run: migration test`); handover packet P-0003.

**Not done, and why.**
- The old-plugin guard in `claude-flatsurf/scripts/_common.py` (Group B hand-off).
  That repo is read-only here, so in the worktree the old flatsurf hooks fire
  alongside the scientist ones. This is decision D4 of P-0003.
- The lab's `scripts/run.sh`, `setup_env.sh`, `fsq.sh` and `test_fsq.sh` stay real
  files. The remote runner executes `scripts/run.sh` from each job's commit, where no
  plugin exists.
- No deploy, no job, nothing committed.

## Group C/F fixes (review pass, 2026-09-28)

Fixes to findings from the Group C and Group F review (`review-f`), on top of the two
sections above. Nothing was committed or staged anywhere; the two worktrees'
`.claude/academy.json` files and `papers/.claude/academy.json` were edited in place, as
Group C and F left them.

**Group F (papers).**
- `extract_quote` (`expert/scripts/ledger_split.py`) had two bugs beyond the
  anchor-window fix already in Group F. (1) A bullet that names the paragraph it
  quotes from before getting to the actual statement ("...paragraph \"Marked points on
  translation surfaces\" in the Introduction: \"Define an n-point marking...\"") took
  the paragraph's own name in quotes as the card's quote, not the statement after the
  colon; two cards had `verified` against a heading (`AW21/1-point-marking.md`,
  `AW21/scope-of-aw21-s-base-stratum-no-marked-points.md`). Fixed by preferring a
  colon-introduced quotation within the anchor's window over an earlier one; both
  cards are still `verified`, now against their real quote. (2) A bullet that pins a
  precise `` `key.txt:lines` `` reference directly before its quote, with none of
  "verbatim"/"quoted"/"reads" anywhere in it, reported "no verbatim quote in the ledger
  entry" although the ledger plainly quotes the source; affected 5 of MS91's cards
  (`lemma-4-2`, `lemma-4-3`, `proposition-4-1`, `theorem-4-4`,
  `paragraph-after-4-4-defining-a-delaunay-triangulation`) and
  `LMW16/new-pinpoint-2-2-recent-dynamical-breakthroughs`. Fixed by a second fallback
  pattern for a bare pinpoint-then-quote. Neither fix ever repairs or alters quote
  text: `proposition-4-1` and `paragraph-after-4-4` now verify against `MS91.txt`; the
  other four now correctly report "quote not found" (their LaTeX math cannot appear in
  a pdftotext extraction) instead of the wrong "no verbatim quote" reason. Net: 15
  verified / 71 unverified -> 17 verified / 69 unverified. The 8 affected cards were
  regenerated individually (not a wholesale re-split) and diffed against a full
  from-scratch run to confirm no other card moved; `ledger_views.py --check` still
  reproduces all three BI ledgers byte for byte, and `papers/.migration/{stats.json,
  stats.md,ledger-split-report.md}` were regenerated to match. Tests added:
  `test_extract_quote_skips_a_heading_named_before_the_colon`,
  `test_extract_quote_skips_two_headings_named_before_the_colon`,
  `test_extract_quote_finds_a_pinpoint_quote_with_no_anchor_word`,
  `test_extract_quote_pinpoint_fallback_does_not_fire_on_a_cref`
  (`expert/tests/test_hot_and_split.py`).
- `papers/.gitignore`: added `DMTS.*` and
  `Dynamics_on_moduli_spaces_of_translation_surfaces.*`, so the coauthors' unpublished
  manuscript extraction (`DMTS.txt`, the PDF it comes from) is never tracked in any
  cached form, even though `*.txt` is otherwise tracked for the library. The index
  rows for both keys stay. Filed as decision D4 of the expert@ts handover packet
  (`board/packets/expert@ts/P-0001-...md`): track it or keep it ignored (recommended:
  keep ignored, since it is the coauthors' own "in preparation" manuscript, not a
  third party's published source).
- `papers/.claude/academy.json`: `registry.db` was `.claude/academy.sqlite`, but the
  MCP server's library FTS index is hardcoded to `.academy/academy.sqlite`
  (`derived_dir`/`DERIVED` in `academy/mcp/tools/library.py`). The field was unused
  here (`registry.profile` is `none`) but misleading; changed to
  `.academy/academy.sqlite`. Other homes' `registry.db` (profile `paper`/`s1`/`lab`)
  were left alone: nothing reads that key for them yet, and the finding was scoped to
  papers.
- Group F's own migration-log paragraph said "all three views identical to BI's
  ledgers"; corrected to "identical to BI's ledgers after the generated-by marker
  line" (`ledger_views.py` prepends that marker, so the views are not literally
  byte-for-byte identical to the originals, only after it) and the card-status counts
  in it and in the handover packet were updated to 17/69.

**Group C (FlatSurfLab).**
- `FlatSurfLab-academy/scripts/check_experiments.py`: the shim resolved the Scientist
  plugin only via `$SCIENTIST_PLUGIN` or the Windows link
  `~/.claude/skills/scientist`, neither of which exists under WSL or on lingo, so
  `tests/test_check_experiments.py` (and the documented Sage path, which runs under
  WSL) failed to import it there. Renamed the env var to `ACADEMY_SCIENTIST` (as
  asked) and replaced the "print SKIP and exit 0" fallback with a vendored copy,
  `scripts/_check_experiments_impl.py` (a byte copy of the plugin's
  `check_experiments.py`, kept in the lab itself so the checker always works,
  everywhere). Tests added: `ShimResolutionTests.test_vendored_copy_matches_the_plugin`
  (byte-identity against the live plugin file, where the academy repo is reachable)
  and `test_shim_runs_with_no_claude_skills_at_all` (runs the shim as a subprocess
  with `HOME`/`USERPROFILE` pointed at a fresh temp directory and `ACADEMY_SCIENTIST`
  unset, asserting exit 0 with no SKIP and no traceback) in
  `FlatSurfLab-academy/tests/test_check_experiments.py`.
- `scientist/scripts/queue.ps1`: PowerShell 5.1 drops an empty-string element when
  splatting an array onto a native command, so `-Label ''` shifted every later
  argument (`-Note` became the label's value, and the real note text spilled into the
  script's own arguments). Since `env.py` already treats a missing `-Label`/`-Note`
  exactly like an explicit empty one (`build_job` maps `None` and `""` to the same
  stored `""`), the fix is simply never to emit the pair when the value is empty,
  rather than pass a value that would vanish in transit anyway. Tests added:
  `TestQueuePs1Frontend` in `scientist/tests/test_env.py` (runs the real
  `queue.ps1` under `powershell.exe`, skipped if it is not on PATH), covering an
  empty label, an empty note before `-ScriptArgs`, and the non-empty case.
- `scientist/scripts/env.py`: `translate_legacy_run` treated any `--dry-run` token as
  its own option regardless of position, so a script's own `--dry-run` argument
  (after the script path) would have made env.py print the argv instead of running
  the script. Fixed to only recognise `--dry-run` as env.py's option before the first
  positional (the script path); one after it now reaches the script unchanged. This
  required moving the pre-existing `TestRun.test_run_legacy_flags` case's `--dry-run`
  to before its script (its real intent was always env.py's own dry run), and a new
  test, `test_legacy_dry_run_after_the_script_is_the_scripts_own_argument`, proving a
  leading `--dry-run` still works while a trailing one is now passed through.
- `FlatSurfLab-academy/.claude/academy.json`: added `"env": "flatsurf"` to the
  `lingo` profile, matching `docs/config.md`'s own example (plan section 3.5 allows
  extending the profile). Without it, `env.py setup lingo` set no `FLATSURF_ENV` and
  relied on `setup_env.sh`'s default.
- `academy/mcp/tools/queue.py`: `check_profile` kept its own looser copy of the
  profile-validity rules (`maxJobs` only had to be positive, and a malformed
  `preflight` was never checked), so `env_check` could report a profile ok that
  `env.py check` would reject. It now delegates to the Scientist plugin's own
  `env.py:static_problems` (loaded the same way `queue_add` already loads `env.py`,
  via `scientist_env()`), falling back to the old rules only if the plugin cannot be
  loaded at all. Tests added in `academy/tests/test_mcp.py::TestOtherTools` covering
  `maxJobs` above 3 and a malformed `preflight`, both now correctly rejected.
- `scientist/scripts/legacy/test_fsq.sh` (the fsq runner's own behaviour suite,
  previously not ported per the Group C `problems` list) is now run from
  `scientist/tests/test_fsq_runner.py`, via `bash` when a real Linux shell is present
  (checked by `sys.platform != "win32"` plus `/dev/shm`, `bash`/`git`/`pgrep` on
  PATH), and skips cleanly on the Windows laptop otherwise. Verified by hand under
  WSL: `bash scripts/legacy/test_fsq.sh` passes all 27 of its own checks (cap, once,
  fifo, tree, lost, cancel, pause, idle), and the new Python wrapper passes running
  under WSL's `python3 -m unittest`.
- Board: ticket `T-0001` (the dry-run migration test to `researcher@slope1`) was
  cancelled as its sender, `scientist@ts`, via `academy/scripts/board.py transition
  T-0001 cancelled --as scientist@ts --reason "dry-run migration test; cancelled to
  avoid spending review runs"`, so a `researcher@slope1` inbox run does not spend two
  Fable reviews on it (P-0003 decision D5(a)).

**Gate.** `py -m unittest` over `academy/tests`, `author/tests`, `researcher/tests`,
`expert/tests` and `scientist/tests` (run per test module rather than through
`discover` for `academy/tests`, whose new `test_registry.py::load_tests` hook trips a
`unittest` loader bug — "Path must be within the project" — when a nested
`discover(top_level_dir=...)` is combined with the `~/.claude/skills/academy` symlink;
unrelated to this pass, and left to whoever owns `academy/registry`'s test wiring):
author 79 OK; scientist 97 OK (1 skip); academy's seven test modules 232 OK between
them; `expert/tests` and `researcher/tests` each have 2 pre-existing failures, both
`grounds.producer_role is required` / `every verdict needs its grader_role`, entirely
inside `academy/registry/core/grounds.py` and `academy/mcp/tools/claims.py` --
untouched by this pass and explicitly out of scope (a concurrent session's work).
`FlatSurfLab-academy/tests/run_all.py`: 323 OK, 116 Sage skips.
`claude plugin validate C:\Work\Math\academy`: passed.

## Group D: registry R1-R4 (plan section 6; merge proposal phases 1-4)

**Built.** `academy/academy/registry/`, a stdlib package (`py -m registry`, cwd
`academy/academy`):
- `core/fm.py`: kb.py's strict parser and serializer, moved unchanged, as the one
  dialect; parameters for the field order, block lists, a scalar style, and an opt-in
  for a key with no value (fsl-claims reads `evidence:` alone as `[]`, as its records
  and its test suite do; nothing writes it).
- `core/model.py` (records with ns/type/id/fields/body/file, stores),
  `core/workspace.py` (namespaces and homes from workspace.json; worktree-suffixed
  siblings first), `core/federation.py` (a foreign namespace loaded through its own
  profile; `kb_index` is gone), `core/projection.py` (false / true / true-modulo /
  unsettled / n/a), `core/graph.py` (deps/usedby across namespaces), `core/edit.py`
  (line-preserving edits, each file's line endings kept), `core/grounds.py` (plan
  section 8, moved from the MCP server and extended: grader role != producer role,
  and the human's quoted word as `basis: human`), `core/legacy_fm.py` (the old
  claims.py reader, transitional: R2 equality and a read fallback that `check` reports).
- `profiles/fsl.py` (fsl-claims: claims.py on the core, rule sets `lab` and `paper`,
  plus `set-status`, `evidence`, `deps`, `usedby`), `profiles/s1kb.py` (s1-kb: kb.py
  on the core, unchanged except `sql` in memory and `check [files]`),
  `cli.py` (dispatch by the repo's profile, plus `graph`, `classes`, `federation`,
  `statement`, `requote`), `requote.py`.
- Shims (worktrees, uncommitted): `FlatSurfLab-academy/scripts/claims.py`,
  `Slope1illuminationResearch-academy/tools/kb.py`.
- R2: the 140 lab/paper records requoted in `FlatSurfLab-academy` and
  `BilliardIllumination-academy`, LF, with `claims/** text eol=lf` added to both
  `.gitattributes`. Report: `goldens/r2-requote-equality.md` (140/140 equal as data,
  re-verified against the committed blobs).
- R3: `goldens/r3-federation-resolutions.md` lists every new resolution.
- R4: `researcher/scripts/claims_edit_check.py` runs the engine's `check <file>` for
  every profile and a blocking `build` where the profile asks (s1-kb); silent in a
  home whose legacy hook is still registered. In the Slope1 worktree the kb_hook entry
  is gone from `.claude/settings.json` and `tools/kb_hook.py` is deleted.
- MCP: `academy/mcp/tools/claims.py` runs on `RegistryBackend` (in process; the backend
  interface kept; `$ACADEMY_CLAIMS_BACKEND=legacy` selects the old subprocess backend,
  read-only). `claims_set_status` and `claims_attach_evidence` are enabled; namespaces
  come from workspace.json. `researcher/scripts/reviews.py` now emits `producer_role`,
  `grader_role` and `ref` in its grounds; the claim-keeper agent's grounds table says so.

**Gate.** Both legacy suites unchanged against the shims (21 + 32 OK). `check` on the
three registries byte-identical to the goldens (CRLF and worktree paths normalised).
`show`: s1 identical; lab and paper identical in their back-links and equal as data in
the file text (it is requoted). Views: lab/BI `INDEX.md`, `index.html` (date masked),
`Drafts/experiments.md` identical to the goldens / views_regenerated; Slope1's eight
views identical after `build` in a temp copy, and `kb.sqlite`'s dump identical to the
old kb.py's. These are `academy/registry/tests/test_acceptance.py`. Academy suites:
academy 265 OK, researcher 79 OK, author 79 OK, scientist 97 OK; expert 2 failures
at the time (below; since resolved: expert 108 OK from R6 on, see "review fixes").
`FlatSurfLab-academy/tests/run_all.py` 323 OK.

**Hand-offs.**
- `expert/scripts/decision_table.py` (out of scope here): its proposed proof grounds
  lacked `producer_role` and per-verdict `grader_role`, which the section-8 check
  requires, so `expert/tests/test_decision_table.py::GroundsTests` (2 tests) failed.
  **Resolved** before R6 (decision_table now emits both and a `ref`); the R1-R4 report's
  `ok=false` rested on these two failures only and is out of date. The statement text
  those reviews hash should be `py -m registry statement <ns:id>` (same hash function
  as `decision_table.py`).
- The fallback reader (`core/legacy_fm.py`) and the shims go in phase 8, after the
  worktree branches are merged.

## Group D: registry R5, schema v2 (plan section 6 "One schema"; 9b)

**Built.**
- `academy/registry/core/schema.py`: the academy object schema (the notebook's object
  template's field set plus `form` and `where`), one status vocabulary, the lifecycle,
  the evidence rows (`type | ref | verdict | run_id | note`) and history rows, and the
  generic rules (`check_record`). A record is v2 exactly when it has `lifecycle`.
- Both profiles read v1 and v2. `fsl.py` keeps only its home rules on a v2 record (file
  path from the id, evidence needed for proved/supported, evidence refs, `where`, the
  paper's label and colour rules, the lab back-links) plus its one field `open`;
  `set-status` moves superseded/dropped into the lifecycle; `new` writes v2 into a v2
  registry. `s1kb.py` reads a v2 file through an adapter into its internal shape
  (kind from `form`, topics from `tags`, cleared_by and runs from the evidence rows,
  history from the frontmatter); its v1 behaviour is byte-identical (the site's two
  status lines are swapped only for a v2 kb); `set-status`, `new` and the new
  `attach_row` write v2.
- `academy/mcp/tools/claims.py`: evidence rows are five cells; s1 v2 records take v2
  words in `claims_set_status` and any evidence type in `claims_attach_evidence`.
- `academy/registry/migrate_v2.py` (`py -m registry.migrate_v2`), refusing any home
  not named `*-academy`.

**Applied** on the three worktree branches (uncommitted): 288 records rewritten (25
lab, 115 paper, 148 s1), three split cases created (`s1:STR-6..8`, `sketch`), views
regenerated. Report `goldens/r5-mapping-report.md` (7/7 machine checks PASS);
snapshot `goldens/r5-pre-migration/`; proposed verdict moves
`goldens/r5-proposed-reviews/`. Packet `board/packets/researcher@slope1/P-0004-...`
(kind `migration`, ten decisions: the OPEN-4 split, the CRIT-20 target, the Not
settled mapping, the modulo texts, the lab lifecycle moves, lab/paper `open`, the
statement field, the verdict moves, the s1 fields and id forms).

**Gate.** `check`: lab and paper byte-identical to phase 0; s1 0/0 on 186 entities
(183 + the splits). Plugin `check_paper.py` on the BI worktree: R1-R6 identical to its
golden (R7 skipped: no `.build/` in the worktree). Tests: registry 49 OK (5 phase-0
golden tests skipped as v1-only; `TestR5` and `test_schema_v2.py` new); academy
modules OK; author, researcher, expert, scientist OK; FlatSurfLab-academy
`tests/run_all.py` 323 OK; Slope1 `tools/test_kb.py` 32 OK.

**Deviations from the plan's wording, each a packet decision.** lab/paper `open:` is
kept as the profile field `open` (caveats and next steps), not renamed to `modulo`,
because on proved records it would read as missing inputs (D7); the statement is not
copied into `statement` (D8); the verdict files are not moved (D9: proposed only).

**Deviation from the plan's order (named by the Group D review).** Plan section 6 R5
says the Partial splits and the lifecycle moves come out as a list for Roey to review
*before* they are applied. The migration applied them on the branch at once: it created
`s1:STR-6`, `STR-7`, `STR-8` (status `sketch`), rewrote `OPEN-4`'s `depends_on`, and moved
the four lab records with the old status `dropped` to lifecycle `dropped`
(`lab:k4-normalizer` gets the status `open`, which no one decided: the old record had no
status besides `dropped`). P-0004 lists them as decisions, but they are decisions on
changes already made, not proposals. Mitigation: the branch is uncommitted, the cases
are `sketch`, and `goldens/r5-pre-migration/` holds every record before R5; rejecting a
decision means reverting those files from there.

**Statement hashes (effect for the handover).** 39 statement hashes changed in R5 (all
18 assumptions and all 21 examples; `goldens/r5-mapping-report.md` lists them), because
moving `## History` into the frontmatter changes a body-hashed record. None is a
status-bearing claim, but any review, verdict or deep-dive keyed on one of those hashes
no longer matches: it must be re-run (or re-keyed by hand) before it is used as grounds,
and the server refuses a proof verdict on a stale hash.

## Group D: R6 and the Slope1 switch-over (plan sections 3.3, 6 "R6", 9 phase 6)

**Built (academy repo, uncommitted).**
- `academy/registry/profiles/s1kb.py`: the notebook layout. A home with `objects/` is read
  as `objects/<kind>/<id>.md` (a record's `kind` must equal its folder), plus
  `computation/verdicts/` and `audits/<subject>/` as verdict files (the review runs
  `land_review` writes, `run: A|B`, and `_`-folders are skipped), `computation/runs/` and
  `computation/specs/`. Prefix `DIR` for directions (`new DIR` refused: directions come
  from the notebook template). `new` writes into the kind's folder; `set-status --verdict`
  and `attach_verdict` accept `audits/`; `build` writes the assumption chart to
  `views/assumptions.md` and four new views: `views/INDEX.md` (objects by kind),
  `views/directions.md` (open questions by direction), `views/graph.md` (dependency graph,
  mermaid) and `views/rests-on.md` (what rests on X). A v2 claim no longer needs `summary`
  (the title stands in). Without `objects/` nothing changes (Slope1's 32 legacy tests).
- `academy/registry/profiles/fsl.py` `resolve_ref`: a `Repo:path` ref from a worktree
  (`FlatSurfLab-academy`) resolves in the sibling worktree of the same suffix first, as
  `workspace.home_of` does for namespaces. Before, it always read the main checkout.
- `academy/registry/core/workspace.py` `sniff_ns`: also recognises `objects/assumption/`.
- `academy/mcp/tools/claims.py`: an s1 `verdict_file` may be under `audits/` too.
- `academy/registry/migrate_r6.py` (`py -m registry.migrate_r6 [--apply]`): refuses a home
  not named `*-academy` or an s1 home that already has `objects/`; plans, checks (kinds,
  collisions, links, direction ids, rewritten refs), then writes.
- Tests: `registry/tests/test_layout_r6.py` (7), `test_acceptance.py::TestR6` (4; re-runs
  R5 from `goldens/r5-pre-migration/` and then R6 from `goldens/r6-pre-migration/`, and
  compares the worktrees byte for byte). `TestR5` is skipped once R6 is applied, as
  `TestGoldens` was after R5.
- `researcher/templates/notebook/_templates/object.md`: `proof: ""` (was `proof:`, which the
  strict dialect rejects, so every `notebook.py new <kind>` object failed `kb.py check`).
- `researcher/agents/claim-keeper.md`: the s1 `verdict_file` may be under `audits/`; the
  stale "no word for supported until schema v2" clause removed.
- `docs/config.md`: the researcher example's `views` lists every generated file; the R6
  layout is documented under `registry`.
- `goldens/r6/`, `goldens/r6-pre-migration/` (the s1 `notes/`, `computation/verdicts/`,
  `computation/runs/` before R6, and a copy of the lab records after R5),
  `goldens/slope1-roster-coverage.md`.

**Applied (worktrees, uncommitted).**
- Slope1: 151 records moved byte for byte to `objects/<kind>/` (95 claim, 1 conjecture,
  1 definition, 15 question, 18 assumption, 21 example); 9 run audits to `audits/<run>/`
  (P-0004 D9 (a), the Researcher half; the 19 claim verdicts stay in
  `computation/verdicts/` for phase 7); the 19 `notes/` pages to `journal/` verbatim (links
  retargeted, a provenance comment on top); the (Q2) search record from
  `docs-notes/extracted-q2-record.md` to `journal/2026-09-20-q2-search-libgap-record.md`;
  two drafted directions `DIR-1` (Q2 at PA-4 and above), `DIR-2` (the family hunt);
  `proofs/README.md`; `kb/r6-path-map.md`; views rebuilt. `.claude/academy.json`
  (researcher@slope1). Retired: the agents claim-verifier, family-experimenter,
  librarian, status-keeper; the skills classify, hunt, kb, settle, verify-claim; the
  workflow settle-candidates.js; `flatsurf.json`. Kept (not covered):
  refutation-verifier, family-scout. `CLAUDE.md`, `README.md` and the rules trimmed
  (`notes-editing.md` -> `objects-editing.md`); `.gitignore` gains the derived state;
  `computation/inbox.md` marked retired.
- FlatSurfLab: the two evidence refs to moved audits (`lab:q2-ew-ornithorynque`,
  `lab:q2-cyclic-covers-n-14-18`) rewritten, each with a history row; lab views re-rendered.
- The paper and lab homes keep `claims/<ns>/` (schema v2 only), as the task set.

**Gate.** `check`: lab and paper byte-identical to R5 (and so to phase 0); s1 0/0 on 188
entities (186 + the two directions). Tests: registry 60 OK (9 skipped: `TestGoldens`,
`TestR5`); academy's eight modules OK; researcher 79, author 79, scientist 97 (1 skip),
expert 108 OK; Slope1 `tools/test_kb.py` 32 OK; FlatSurfLab-academy `tests/run_all.py` 323
OK (116 Sage skips). The four `docs/config.md` examples validate. Hooks simulated on a copy
of the new layout: `claims_edit_check` blocks a dangling `depends_on`, `status_guard`
denies prover a status edit. `notebook.py direction/next/status` read the new layout.

**Hand-offs and limits.**
- `set-status` for s1 anchors on a verdict file in the home; the Expert's review records
  (`papers/reviews/s1/...`) are not accepted yet. Phase 7 (the librarian moves the 19
  claim verdicts, P-0004 D9) should extend it.
- Hooks see the workspace's homes (the main checkouts), so in the Slope1 worktree the
  record hooks are silent until the branch is merged (as for the other worktrees).
- Handover packet: `board/packets/researcher@slope1/P-0005-handover-slope1-switched-over-to-researc.md` (kind `migration`).

## Group D: review fixes (2026-09-28)

A second agent reviewed Group D; these are the fixes (academy repo, uncommitted).

**Built.**
- `registry/core/grounds.py`: the graders must be the reviewers of the basis (proof:
  `rigor-reviewer`, or `expert`, the role `decision_table.py` writes; computation:
  `experiment-reviewer`), and the producer is none of the reviewer roles. Every verdict
  needs the `ref` of its review record. New `check_verdict_refs`: each ref must be a
  landed review record on disk whose frontmatter `verdict` and `run_id` match the row,
  and whose `subject`, `statement_hash` and reviewer (`agent`, or `landed_by:
  researcher/land_review`) agree when recorded. `basis: human` from an agent needs
  `where` naming a ticket or packet (`T-0007` / `P-0012`). `superseded` / `dropped` are
  targets (a `note`; `superseded` also `superseded_by`).
- `registry/profiles/fsl.py` `set_status`: applies `check_verdict_refs`, writes an
  evidence row for every verdict ref (before, a verdict without a row was only history
  text), and writes a supersession link (v1: `superseded_by` on the record; v2: the
  one-way `supersedes` on the replacing record, put back if the old record's edit is
  refused). The command line's `--roey` counts as the human.
- `registry/profiles/s1kb.py`: `show` prints the `## Statement` (or the body's head) of a
  v2 record again, as phase 0 did. `set-status` on a v2 record checks the verdict file
  (`verdict_file_problems`): a settling target needs the file to `clear` the claim and
  two `Run X` lines (or two landed review runs beside it) giving the target's verdict
  word and none contrary; other targets need the file to name the claim. `--human
  QUOTE` stands in for the runs, not for the file. An unsettled or lifecycle target on a
  v2 record may rest on `--note` alone; `superseded` needs `--superseded-by` and writes
  the replacing record's `supersedes`. If the kb does not build afterwards, every
  touched file is put back byte for byte and the command fails (before, the file stayed
  changed while the command, and MCP, reported a refusal). `check` warns on a `modulo`
  item that is not a record id (5 warnings: GEO-3, GEO-15, GEO-30 x2, CRIT-20).
- `mcp/tools/claims.py`: the s1 route checks the grounds' review records, requires
  `verdict_file` to be one of the verdicts' refs when both are given, runs
  `verdict_file_problems` for v1 and v2 records before the engine writes, and passes
  `--human` / `--superseded-by`. `claims_set_status` checks an agent's `basis: human`
  against the named ticket or packet (the quote must be in it verbatim, whitespace
  aside). `claims_set_status` and `claims_propose_status` accept `superseded` and
  `dropped`.
- `researcher/agents/claim-keeper.md` (grounds table: reviewer roles, refs checked, the
  board reference for Roey's word, the lifecycle row, the s1 verdict-file rule) and
  `researcher/skills/claims/SKILL.md` (the supersession route).
- Tests: registry 72 (9 skipped): new grounds, verdict-ref, lifecycle, s1 verdict-file,
  build-rollback, supersession and show tests; `TestR6` gains a back-link test for lab
  and paper `show` and a statement test for s1 `show` against the phase-0 goldens.
  `academy/tests/test_mcp.py`: the review's repros (made-up verdicts; the empty GAP
  verdict file; claim-keeper's unpinned quote; lifecycle moves).
  `expert/tests/test_decision_table.py`: the `rec()` fixture gets a `file`, since the
  grounds now need each verdict's ref (a test fixture only; `decision_table.py`
  unchanged).
- `goldens/r6/registry_s1.txt` regenerated: the five `modulo` warnings (the test masks
  them for the R5 comparison).

**Gate.** `check`: lab and paper byte-identical to R6 (and phase 0); s1 0 errors, 5
warnings (the new modulo rule) on 188 entities. Tests: academy 308 OK (9 skipped, the
registry's included), author 79, researcher 79, scientist 97 (1 skip), expert 108 OK;
Slope1 `tools/test_kb.py` 32 OK; `FlatSurfLab-academy/tests/run_all.py` 323 OK (116
skips).

**Judgement calls.**
- `expert` is accepted as a proof grader because `decision_table.py` writes the role, not
  the agent; the record's `agent: expert:rigor-reviewer` is what `check_verdict_refs`
  reads. The roles in the grounds stay self-declared; the tie to the landed record is
  what makes them checkable, and a record without `agent`/`landed_by` is not refused.
- The s1 verdict-file rule reads the old files heuristically (`Run X` lines, the
  `confidence:` of a VERDICT block). Of the 22 historical (file, cleared claim) pairs
  whose claim is settled, 16 pass; the other six (OBS-1, OBS-8..11: one line per run
  for several items; OPEN-10: Roey's attestation) would need `--human` or new landed
  runs to be used again. The rule applies only to new `set-status` calls; nothing existing is
  re-checked. Which of proved / proved-modulo the runs support is not read.
- On a v1 s1 record (only in fixtures now) the engine keeps kb.py's behaviour; the MCP
  route checks the verdict file for v1 too.
- The quote check against a ticket or packet is textual: it shows the words are on the
  board, not who wrote them.
- The command line (`registry set-status --roey`, `kb.py set-status --human`) cannot tell
  who runs it; a Bash call is not hooked (as for any shell edit, Group B's known limit).
- s1 Expert review records (`papers/reviews/s1/...`) are still not accepted as the s1
  anchor (phase 7, P-0004 D9).

**Not fixed here (reported).** The BI main checkout has ` M Drafts/statements.md` (mtime
before Group D) and `?? .claude/paper-gate.json` (`{"commit":"off"}`, mtime inside the
Group D window, provenance unknown); Group D cannot certify it untouched. The academy
repo's index holds staged changes from earlier groups (808 files in `git diff --cached`,
among them the `session_usage.py` rename and the plugins' added files); nothing was
staged or unstaged here.

## Opus 5.5 as an equal primary for graders (2026-09-28)

Roey's rule (2026-09-24, reconfirmed 2026-09-28): **Opus 5.5 counts as an equal primary
to Fable for verifiers.** Before this pass the plugins capped every non-Fable positive
(proof CONFIRMED read as PLAUSIBLE, experiment SOUND recorded as GAP, referee report
reduced-strength), which also caught the graders' own frontmatter fallback `opus`.

**Changed.**
- `expert/scripts/decision_table.py`: `PRIMARY_MODELS = ("fable", "opus-5.5")`,
  `model_label()` (`claude-opus-5-5`, `claude-opus-5-5[1m]`, `Opus 5.5`, `opus-5.5` ->
  `opus-5.5`; any other model -> its family), `is_primary()` against the set;
  `--primary` now takes a comma-separated list, default `fable,opus-5.5` (passing
  `fable` alone restores the old behaviour). Messages name the primaries. Every run's
  recorded `model` stays in `runs[]`.
- `expert/scripts/land_referee.py`: reduced strength via `decision_table.is_primary`.
- `researcher/scripts/_researcher.py`: the same `PRIMARY_MODELS` / `model_label` /
  `is_primary` (kept in step by hand: the vendored `_academy.py` is not touched, since
  changing it would force a change to `author/`'s copy, out of scope for this pass).
  `land_review.py` caps a positive verdict only off the set; the landed file now
  records `model` (the roster label, e.g. `opus-5.5`, where it used to collapse every
  Opus to `opus`) and `model_id` (the name as given). `settle.py` counts a candidate
  run positive on either primary.
- Text: `academy/references/roster-rules.md` ("Model fallback": two equal primaries,
  exact model ids, what is still capped), `budget.md` rule 6,
  `academy/skills/status-vocabulary`, `expert/agents/{rigor-reviewer,referee,review-chair}.md`,
  `expert/skills/verify/{SKILL.md,references/conclude.md}`, `expert/skills/referee`,
  `researcher/agents/experiment-reviewer.md`, `researcher/skills/{review-experiment,settle}`,
  `docs/roles.md`. Agent frontmatter (`model: fable`, `fallback: opus`) unchanged.
- Tests: expert 117 (+9: Opus 5.5 CONFIRMED counts alone and in pairs, Sonnet / older
  Opus / Haiku CONFIRMED -> PLAUSIBLE, `--primary fable` narrows, `model_label`, the
  referee on Opus 5.5 full strength and on Sonnet reduced); researcher 82 (+3: Opus 5.5
  SOUND not capped, older Opus capped, `is_primary`; settle cases for Opus 5.5 and
  Sonnet). academy 309 (9 skipped), author 79, scientist 97 (1 skip): all OK.

**Judgement calls.**
- A bare `opus` (no version) is read as a fallback, not as Opus 5.5: it cannot be told
  from an older Opus. The graders' briefs now ask for the exact model id; the
  experiment-review hook takes it from the transcript when it can. A reviewer that
  writes only `opus` in a VERDICT block therefore still gets PLAUSIBLE.
- `settle.py` keeps its old leniency: a candidate verdict with no `model` at all counts
  as on a primary (it did before; `fallback: true` still overrides).
- `academy/permissions.json` carries no model or verdict-cap text; nothing changed
  there. `docs/config.md` / `protocol.md` model names (`fable|opus|sonnet|haiku`) are
  budget ceilings, not grader rules; unchanged. `usage_report.model_family` (usage
  accounting) still collapses to families.
- Historical records (goldens, `_import/`, landed reviews) are not rewritten.

## Group E: phase 5 (Author switch-over in BilliardIllumination)

**Switched over** in the worktree `C:\Work\Math\BilliardIllumination-academy` (branch
`academy-migration`, base 698b0c7; nothing staged or committed). `.claude/academy.json`
is the config.md example for author@bi (plus `paths.archive`, the coauthors' inline
macros, `crlf` incl. `main.tex`, the old `flatsurf.json` notes in `notes`);
`flatsurf.json` deleted; no `paper-gate.json`. `scripts/check_paper.py` is a shim onto the
plugin checker (`$ACADEMY_AUTHOR`, `~/.claude/skills/author`, else the vendored byte copy
`scripts/_check_paper_impl.py`).

**Agenda.** `agenda_migrate.py` gave `Drafts/agenda.md` (142 entries, `\input` order). The
live items were built from a hand-checked, line-keyed spec (the script missed the Tier 6-7
bullets, read Tier 9b item 4 as dropped, kept four done items open, and skips 'Open from'
paragraphs): `Drafts/roadmap.md`, 81 items with `tags: [tier-...]`; 47 tickets from
author@bi (T-0002..T-0048: 26 verify + 8 cite to expert@ts, 5 prove to researcher@slope1,
1 experiment to scientist@ts, 7 decisions to human), each with a hold line until the
handover packet's D3. Mapping: `Drafts/archive/comment_roadmap-mapping.md` (166 lines, 0
unmapped); the old roadmap and margin notes moved verbatim to `Drafts/archive/`.

**Views, roster, rules.** sources/related_work/verdicts are the Expert's generated views
(identical after the marker line). Local roster removed; coverage in
`goldens/bi-roster-coverage.md`. CLAUDE.md and the rules rewritten (tex-conventions kept,
with the CRLF-write fix).

**R7.** 29 `\Claude` notes shortened/merged/removed (originals in
`Drafts/archive/claude-notes-2026-09-28.md`); R7 outside the baseline 7 files -> 2
(`introduction.tex:58`, `billiards.tex:22`: Roey's own pointers, left).

**Gate.** Checker R1-R6 = `goldens/check_paper.txt`; build clean; registry check =
`goldens/r6/registry_paper.txt`; author tests 79 OK. Handover packet
`board/packets/author@bi/P-0006-...`. **Still open:** the old-plugin guard in
`claude-paper/scripts/_common.py` (packet D6); a fix to `agenda_migrate.py`'s heuristics.

### Group E review fixes

An independent review of the switch-over found the verification order lost. Eight
verify tickets were cancelled (sender, reason in thread) and their items set back to
`open` with `depends_on`: T-0024/T-0036 (after R-0057), T-0035 (after R-0058, a blue
input), T-0037 (after R-0062), T-0041 (after R-0068..R-0070), T-0044 (after R-0063),
T-0048 (after R-0079, R-0083), and T-0046 (Roey's never-filed note at
`markings.tex:829` asks to replace the lemma: R-0082). T-0047 stays, with its Ask
scoped to the stabiliser Sketch it covers. New items R-0082..R-0085 (two unfiled Roey
notes, the Delaunay follow-up, the repair flags of two shortened machine notes). The
`ar-92` note is back in the tex (one line), `ar-282` folded into `ar-269`; R7 still 2
(Roey's pointers), R1-R6 = golden, build clean. `next.py` `_ask_line` drops a leading
list marker (the doubled `-- -` in 32 ticket asks, fixed in place); author tests 81 OK.
Not changed, left for the plugin owner: `land_verdict.py`/`land_referee.py` trust
the self-reported `model:` line (`land_review.py` reads the transcript);
`settle._primary` treats a missing model as primary while `decision_table.effective`
caps it; `_academy.MODELS`, `usage_report.MODEL_RANK` and scientist `inbox.WEIGHT`
rank `opus` below `fable` as budget ceilings.

## Decisions applied 2026-09-28

Roey's answers of 2026-09-28 (terminal session; recorded by the orchestrator), applied
on the branches and in the plugin repo. Nothing committed, staged, pushed or run on
lingo; no reviewer, verifier or prover ran; no ticket executed.

**Packets.** `packets.py decide` (as human, comment "Roey 2026-09-28, recorded by
orchestrator") for every decision: P-0001 D1 other (moot: papers committed as a whole,
c539d6b), D2 (b), D3 (a), D4 (a); P-0003 D1 (b), D2 (a), D3 (a), D4 (c) retire the old
links at merge, D5 (a); P-0004 D1 (b), D2-D10 (a); P-0005 D1-D3 (a), D4 (b) (already
implemented), D5 (b), D6 (b), D7 (a), D8 (a) (done now), D9 (b); P-0006 D1 (b), D2 (b),
D3 other (hold all), D4 (b), D5 (a), D6 other (no guard; retire links at merge), D7
(a). All five are `decided`. P-0002 acknowledged (D0) and set `withdrawn` by hand
(`packets.py` has no withdraw command); T-0001 was already cancelled.

**Board: everything held.** The 32 open non-human tickets got the thread line "held by
Roey 2026-09-28: do not run until Roey's command" and moved `open -> blocked` with
`waiting_on: [human]` (as human). Filed and held likewise: T-0049 (expert@ts ->
expert@ts, cite: re-check the 31 not-found/partial card quotes, P-0001 D2), T-0050
(researcher@slope1 -> expert@ts, cite: bib keys for the modulo inputs of GEO-3, GEO-15,
GEO-30, P-0004 D5), T-0051 (human -> author@bi: the agenda pass lowering `required` for
sketch-kept results and adding a first milestone, P-0006 D2). The seven decision
tickets in `human/` stay open (they are Roey's).

**Slope1 worktree.** P-0004 D1 (b): `objects/claim/STR-6.md` removed, OPEN-4's
`depends_on` is `[STR-4, CRIT-19, STR-7, STR-8]` with a history row, DIR-1 updated. D2
(a): `objects/question/OPEN-14.md` ("fixed-point-free θ with all row segments of length
≤2", CRIT-20's own words quoted verbatim), CRIT-20 `modulo: [OPEN-14]`. P-0005 D6 (b):
the 44 `## Proof` sections extracted verbatim to `proofs/<id>/attempt-1.md` (outcome
mirrors the status: complete for proved / proved-modulo, else in-progress), each object
keeping its `## Proof` heading with a pointer and a `proof:` field; no statement hash
changed (188 hashes compared before and after: a claim hashes its `## Statement` only,
and no assumption or example had a `## Proof`), so nothing needed re-pinning. P-0005 D5
(b): `.claude/rules/verification-checklist.md` (refutation-verifier's (Q2) checklist,
with the verdict mapping), family-scout's brief as the last section of
`.claude/rules/families.md`, both agents deleted; `CLAUDE.md` and
`computation.md` updated; the Opus 5.5 paragraph now records D4 (b). Check: 188
entities, 0 errors, 4 warnings (the GEO-3/15/30 free-text modulo, kept by D5 (a)).

**Plugins.** `expert/agents/rigor-reviewer.md` reads "the home's verification
checklist rule (`.claude/rules/verification-checklist.md`) if present" (generic);
`researcher/skills/settle` step 3 files the independent re-derivation as a Scientist
`verify` experiment and the Expert `verify` ticket names the checklist rule; the
roster-coverage golden marks both agents retired.

**Verdict move (P-0004 D9, P-0005 D8, phase 7).** The 19 claim verdicts copied verbatim
from `goldens/r5-proposed-reviews/` (identical to Slope1's `computation/verdicts/`) to
`papers/reviews/s1/<claim>/`, with `reviews/s1/_moved-from-slope1.md`. The 30 evidence
rows in 24 Slope1 records now point at `file:expert@ts/reviews/s1/<claim>/<file>.md`
(history row each). Engine: `workspace.instance_home` / `instances_of_role`;
`fsl.resolve_ref` resolves `file:<instance>/<path>`; s1kb accepts an Expert review ref
(or a path into the library's `reviews/`) as `set-status --verdict`, reads it for
`verdict_file_problems` (old-style files and landed run pairs), checks that an evidence
or `cleared_by` review ref exists, and keeps the `cleared_by` edge to the ledger
verdict while its old copy exists; MCP `claims_set_status` takes it as
`grounds.verdict_file`. Tests: `test_layout_r6.TestExpertReviewRefs` (6),
`test_mcp.TestRegistryBackend.test_s1_set_status_on_an_expert_review`. The old
`computation/verdicts/` files stay as they are until phase 8.
`goldens/r6-decisions/` (MANIFEST.json with sha256 pins, the s1 check output) keeps
`TestR6` a byte gate over the decided worktree.

**BI worktree.** P-0006 D4 (b): the keys in Roey's two `\Roey{Moved to ...}` pointers
break (`\texttt{thm:main-parking-}\allowbreak\texttt{garage-note-a}`,
`\texttt{conj:unfolding-}\allowbreak\texttt{characterization}`), pointer text only,
CRLF kept. `latexmk -pdf main.tex` clean; checker: R7 0 (was 2), everything else inside
the baseline. P-0006 D7 (a): the source-checker's four notes and index moved verbatim
to `papers/.claude/agent-memory/expert-librarian/` (MEMORY.md gains a provenance
header) with a "Librarian notes" section in `papers/README.md`; deleted from BI.
`Drafts/sources.md` (a generated view) still names the old memory path in one line.

**Verification fixes.** `gather_deep_dive.status_of`: a definition (also an example or
direction) with no status gets `n/a — definition`, so s1:BOUND-2-style pages render;
report cards show their packet kind rather than "no status recorded"; `board.py`
strips a namespaced `--agent` to the bare name (`bare_agent`); `expert/scripts/out.txt`
and `out2.txt` deleted, with a test against stray debug output.

**Gate.** validate 7/7; academy 353 OK (9 skipped); registry 79 OK (9 skipped);
author 81, researcher 82, expert 117, scientist 97 (1 skipped), domain pack 6; Slope1
test_kb 32; FlatSurfLab run_all 323 (116 Sage skips). Registry checks: lab 0/0, paper
1 error / 27 warnings (as golden), s1 0 errors / 4 warnings.

**Left for phase 8 / merge (Roey):** remove the old computation/verdicts copies and
the shims; retire the old paper/flatsurf links at merge (no guard); delete BI main's
`.claude/paper-gate.json` after merge; release the held tickets on Roey's command.

## Board migration to GitHub (2026-10-01 .. 2026-10-03)

**Done.**
- Rehearsals in the scratch repos `Roeyzemmel/A` (#1-40, full fidelity) and `Roeyzemmel/B`
  (skeleton #1-61, a deliberate interrupt and resume, sub-issues, an inbox scenario of
  11 steps, a bulk test #64-66, a cutover lifecycle #67). Both verify clean.
- The board is on GitHub: `Roeyzemmel/BilliardIlluminationWorkspace` issues #1-#106 =
  T-0001..T-0106 (611 comments, 37 closed, 30 sub-issue links, 1 dependency), pushed with
  `board_push.py` from the board at `a8112bc`. `board_verify.py` on a `board_dump.py` dump
  gives 0 drift, and `board_import.py` reproduces every ticket file.
- Tools (academy `lib/board_gh.py`, `scripts/board_push.py`, `board_dump.py`,
  `board_batch.py`): REST through `gh api`, resumable, numbering checked by reading
  issues by number. The `board_gh:transport` factory is the cutover switch's transport.
- Workspace repo: the `board-sync` workflow and its vendored scripts (`.github/`),
  `bootstrap.py` support for a board config, and `ship.py` adding a
  `Ticket: OWNER/NAME#N` line on the GitHub backend.

**Found and fixed on the way** (each with tests, most also live on B):
- A session's posts get a "Generated by Claude Code" footer: MCP comments, and REST issue
  bodies and comments. The codec, the store's thread check and its body comparison read
  without it.
- The REST "newest issue" listing lags behind fresh creates. Numbering checks and the dump
  read issues by number.
- GitHub's secondary rate limit on content creation: writes are spaced 1 s apart, and the
  limit is waited out.
- An MCP create with `parent_issue_number` refuses labels that do not exist yet. The bulk
  push creates every label first.
- The MCP decodes `\uXXXX` in parameters. REST posts bodies verbatim.
- `board_verify` compared parent numbers with ticket ids. It now normalises both.
- The store's save only ever added native links. A moved parent is now replaced, a cleared
  one removed, and a dependency that left `waiting_on` is removed.
- `board-sync` treated every issue as a ticket. It now syncs only board issues
  (`board_codec.is_board_issue`).
- Assignment has one rule, `board_codec.wants_human`: the human is assigned while a ticket
  is addressed to them and live, or blocked with `human` in `waiting_on`. The manifest, the
  verifier, `board-sync` (the first login of `ACADEMY_HUMAN_LOGINS`) and the store
  (`board.assignee`) all use it. Six live issues were fixed on 2026-10-03 (#65, #66, #71
  and #91 assigned; #15 and #81 unassigned).

**State at hand-over (2026-10-03).**
- The file board is still the source of truth. The **switch has not been made**: the
  auto-mode permission check refused the edit to `workspace.template.json`, which is Roey's.
  Keep the board frozen until then.
- Branches `claude/practical-newton-r84bg5`, each a fast-forward of its `main`:
  - academy: board-sync skip and assignment, links both ways, `board_batch.py`, and these
    docs.
  - workspace: the ship ticket link, and the refreshed `.github/academy/` copies.
  - board: the error ledger, `MIGRATED.md`, and the audit batch.
- A concurrent session is setting up the GitHub Project and the workflows. Coordinate on
  `.github/` (merge one, refresh the other).

**Next, in order** (as of 2026-10-03; done on 2026-10-06 except the audit README's open
questions in step 5: see the entry below).
1. Merge the three branches: academy first, because the workspace's vendored scripts come
   from it.
2. Roey: the repo variable `ACADEMY_HUMAN_LOGINS` = `Roeyzemmel`; Actions allowed to write
   issues; `gh` installed and logged in on every machine that runs the academy tools.
3. The switch: in `workspace.template.json`, set
   `"board": {"path": "board", "backend": "github", "repo":
   "Roeyzemmel/BilliardIlluminationWorkspace", "transport": "board_gh:transport",
   "assignee": "Roeyzemmel"}`, then run `py scripts/bootstrap.py` on each machine. The
   freeze ends.
4. Smoke test: move one ticket; the `board-sync` run is green and a hidden state comment
   appears.
5. The audit batch: `board/batches/2026-10-03-audit/` (README with the evidence; 33 ops,
   dry run clean). Run `board_batch.py ... --dry-run`, then the real run. Then decide the
   README's 12 open questions.
6. The Project needs a token with the `project` scope; `board_project.py` has the field
   spec. The scratch repos A and B can be kept for rehearsals or deleted.

## Board switch and after (2026-10-03 .. 2026-10-06)

**Done.**
- Cloud branches merged (academy #12, workspace #108, board #2). Pre-switch verify:
  `board_dump` + `board_verify`, 106 issues, 611 comments, 30 sub-issue links, 1 dependency,
  0 drift.
- **The switch** (workspace #109): `board` in `workspace.template.json` is `{path: board,
  backend: github, repo: Roeyzemmel/BilliardIlluminationWorkspace, transport:
  board_gh:transport, assignee: Roeyzemmel, project: users/Roeyzemmel/2}`; bootstrapped on
  Roey's machine. Repo variable `ACADEMY_HUMAN_LOGINS=Roeyzemmel`.
- **board-sync never ran before 2026-10-06**: the workflow named only `issues: write`, which
  sets `contents` to none, so every checkout of the private repo failed ("Repository not
  found"). Fixed with `contents: read` (workspace #111, academy template #14).
- **Smoke test and audit batch**: op 1 alone (T-0056), then ops 2-33; T-0112..T-0116 created,
  P-0018..P-0022 repointed (board #3). board-sync: 44 runs green, 56 cancelled (a newer run
  per issue supersedes the pending one), every touched issue has one state comment and no
  problems comment.
- **The Project** `users/Roeyzemmel/projects/2` ("BilliardIllumination Board"): the fields of
  `board_project.py`, every issue an item. Its fields are written by `board_project_sync.py`
  from Roey's machine through `gh` (project scope), writing only what differs (#13). Not in
  board-sync: Roey keeps no long-lived token in the repo, and a user-owned Project is out of
  reach of `GITHUB_TOKEN` and of fine-grained tokens (tried: "Resource not accessible by
  personal access token").
- **Cloud and local reads** (#15): SessionStart counts from the issues (`iter_meta`, no
  comments; 2 s on the scratch repo B) and says "tickets not read: ..." when GitHub cannot be
  read; `board.py list` reads metas only (1m45s -> 3s live); a missing `gh` is one clear
  error. Bootstrap warns when `gh` cannot read the board (workspace #117). `board_batch
  --dry-run` leaves `.claude/` out of its copy (a session worktree in `board/.claude/` made
  the dry run stop at op 5).
- **Checked in a cloud session** (2026-10-06, read only): `cloud-setup.sh` wrote the GitHub
  board config and reported "gh can read it"; `board.py list --to human` gave the same 11
  tickets as locally. A first run had crashed (`board_gh` has no `transport`) because the
  cloud environment attached academy at the old branch `claude/busy-cannon-dirqg2`
  (5283a7f, 2026-10-01); Roey set the environment to attach `main`.
- Superproject bump f400658: academy 8bfaeb7, board 20c0330, FlatSurfLab 95fae78,
  Slope1illuminationResearch ed16a22.

**Leftovers.**
1. *Roey:* the audit batch README's 12 open questions
   (`board/batches/2026-10-03-audit/README.md`); the new decision tickets T-0114 (flat's
   registry profile) and T-0115 (restate prop:reduced-torus-compatible) are addressed to him.
2. *Project:* Roey checked the Project's settings in the UI and set its permissions
   (2026-10-06); the built-in workflows ("Auto-add to project", "Item closed", "Item
   reopened") cannot be read through the API, so the first new ticket is the confirmation
   that it joins on its own. Views (per instance, per role, blocked) are made in the UI.
   Run `py academy/academy/scripts/board_project_sync.py` now and then: between runs a new
   issue sits in the Project with Status only (its labels carry the rest).
3. *Cloud:* the SessionStart line has not been seen in a cloud home (the read-only check ran
   at the workspace root, where the hook is silent). Check from `library/` with
   `ACADEMY_BOARD_COMMIT=0`; expect counts from GitHub (expert@ts far below the 30 the old
   files gave).
4. *Cloud:* three permission rules in `scripts/permissions.json` name
   `{USER}/.claude/skills/academy` (`packets.py`, `usage_report.py`, a Read rule). That link
   exists on Roey's machine, not in the cloud, where plugins come from the marketplace, so the
   rules match nothing there and those two scripts prompt. Fix: render them with the
   installed plugin root.
5. *Cloud environment:* every repo must be attached at `main`. A stale attached branch is
   adopted as is (bootstrap does not move a checkout; switching it automatically was refused
   by the auto-mode check as modifying shared resources). The merged branch
   `claude/busy-cannon-dirqg2` in academy can be deleted so it is not picked again.
6. *Housekeeping:* `board/.claude/worktrees/obs23` (branch `cloud/2026-09-29-obs23`) is a
   session worktree inside the board checkout; remove it once that branch is settled. The
   cloud session's check left one line in its own `board/.errors/other.jsonl` (a failed
   read-only `git status`): nothing to keep.
7. *Numbering:* pull requests share the issue numbers, so ticket ids now skip them (#107-#111,
   #117, #118 are PRs; T-0112..T-0116 are tickets; the next ticket is at least #119).
8. *Still not done in code* (from `github-board.md`, not re-checked here): the write hook in
   github mode; the Author's agenda-gap filing; `session_start`'s `reconcile_ids` still
   reconciles the file ticket counter, harmless on GitHub.
9. *Tests on Windows:* `test_bootstrap_adopt` (two symlink tests) fails without Developer
   Mode; `test_common.FileTests.test_concurrent_allocation_unique` failed once under full-suite
   load and passed 5/5 alone.
10. The scratch repos `Roeyzemmel/A` and `Roeyzemmel/B` stay, for rehearsals.

## A generic marketplace; the board in the workspace (2026-10-09)

The board branches were merged into `main` in one plan (streams `ship`, `compute`, `fixes`,
`roles`, `generic`, `text`). What changed, by theme:

- **The board is folded into the workspace.** `board/` is a plain directory of the
  workspace repository, no longer a repository of its own. Its files (packets,
  deep-dives, the pre-migration `T-*.md` snapshot) are committed with the ticket's work by
  `ship.py checkpoint --only board`, on the ticket's `<date>/<topic>/<role>` branch;
  `session_start` commits a board only when it is still a repository of its own
  (`docs/protocol.md` section 2). The old board repository is obsolete.
- **Workspace tooling moved into the plugin.** `academy/scripts/ship.py` (branch, commit,
  push, checkpoint, merge, publish; the root from `ACADEMY_WORKSPACE` / `--workspace`) and
  `academy/scripts/workspace_bootstrap.py` (plugins derived from the instances' domains),
  with `academy/templates/workspace/` (cloud setup, the permissions template). The
  workspace keeps one-line shims at `scripts/ship.py` and `scripts/bootstrap.py`, so the
  allowlist strings keep matching. The branch and ship protocol is `docs/branching.md`.
- **The marketplace is generic.** New config keys (`docs/config.md`): workspace.json
  `human.name` / `human.login`, `grading.primaryModels`, `plugins` and the `compute` block
  (remote workers and the gateways in front of them, replacing the machine defaults in the
  Scientist); academy.json `registry.prefixes`, `registry.assumptionGroups`, the env
  profiles' `worker`, `author.provenance`, `paths.verifyChecklist`. Registry rule sets are
  generic (`paper`, `notebook`, `lab`; `s1` and `s1-kb` stay as aliases of `notebook`).
  Runtime strings, prompts and docs say "the human" (the name comes from workspace.json),
  grader prompts name the grading primaries from config, examples use neutral names
  (`Ada`, `remote-a`, `nb:`), and `academy/tests/test_generic.py` fails on a project name
  anywhere in the plugin trees outside a short allowlist of history files.
- **Role cut and the pinned guard.** One table in `academy/references/roster-rules.md`
  ("Role cut") says what each role writes, never writes and hands off; a cross-role write
  guard enforces it, and the Author's pinned-statement guard keeps a cleared statement's
  text from changing without a fresh review.
- **The Author's aesthetic vision**: a reference, a per-home `vision.md`, an aesthetic pass
  and a referee check.
- **`/academy:cowork`**: a focused goal worked with the human; the session orchestrates,
  files the approved plan's tasks as tickets (as the human), and the human decides.
  Campaigns reach other roles only by tickets.
- **Workflow fixes** (`docs/workflow-triage-2026-10-09.md`): per-call instance, `claims_new`
  across instances, `domain_get`, `library_search`, `land_verdict` (now also keeps the
  VERDICT block's `gap_class`), `new-pass`, the error ledger, `packets_create`'s refusals.
- **Migrations archived.** The one-time migration scripts, their goldens and the
  real-home acceptance tests left the marketplace; they are kept in the workspace's
  `archive/academy-migrations/`.

**Left for later:** `scientist/scripts/check_experiments.py` still reads the lab's
registry through the home's `scripts/claims.py`, which the lab no longer has, so E7 (a
`Claims:` id missing from the registry) is dormant until it reads the academy registry
engine instead.
