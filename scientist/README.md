# scientist — the lab role

The academy's coding department (plan sections 3.5 and 3.6): experiments with
provenance, the lab's code, its tests, upstream drafts, and API checks. One instance
per lab home; the first is `scientist@ts` in `C:\Work\Math\BilliardIlluminationWorkspace\FlatSurfLab`. Generic
programming habits come from the `superpowers` plugin, preloaded by name; this plugin
adds the maths-specific layer (`experiment-method`, provenance, reports). It carries
no domain mathematics: the subject comes from the domain pack, by the pack
contract's file names (`examples.md`, `traps.md`, `computation/`), through the
academy MCP tool `domain_get`.

## Agents

Each agent's model, effort and fallback are in its file's frontmatter (the fallback
rule: `academy/references/roster-rules.md`, "Model fallback").

| Agent | Job |
|---|---|
| `experimenter` | Designs and writes experiments; the report draft |
| `developer` | The lab's code, the runner and env profiles, academy scripts; TDD in a worktree |
| `test-engineer` | Tests written independently; reviews the developer's diffs |
| `upstream-contributor` | Drafts upstream issues and patches; Roey files them |
| `api-prober` | Confirms one library call; records it in the pack's `computation/api/` + CHANGELOG |

## Skills

`experiment`, `queue`, `api-check`, `env`, `examples-audit`, `experiment-method`,
`inbox`, `status`.

## Scripts (`scripts/`, stdlib Python, `py`)

| Script | Does | Tests |
|---|---|---|
| `env.py` | env profiles (`wsl` / `local` / `ssh`) and the policy: `list`, `check <profile> [--live]`, `run <profile> ...` (wsl/local only), `setup`, `vpn`, and the job queue over the fsq runner protocol (`queue add\|list\|check\|tick\|fetch\|status\|log\|preflight\|deploy\|pause\|resume`, legacy `queue.ps1` flags too); job state in `<lab>/queue/` | `tests/test_env.py` (fake ssh/scp `tests/fixtures/fake_ssh.py`, a temp git lab, no network) |
| `queue.ps1`, `run.ps1` | thin PowerShell frontends to `env.py` with the lab's old flags (`-LabHome` is set by the lab's shims) | via `test_env.py`; golden: `queue.ps1 -List` = `goldens/queue_list.txt` |
| `run.sh` | the Linux side of a `wsl`/`local` run: sourced `conda activate`, `LAB_ROOT` on `PYTHONPATH` (the lab keeps its own `scripts/run.sh` for the remote runner) | — |
| `fsq.sh` | the remote runner, deployed to `<fsqHome>/bin/fsq` by `env.py queue deploy` (Roey's call); byte-identical to `legacy/fsq.sh` | `test_env.py` pins the bytes |
| `vpn.ps1`, `setup_env.sh` | the `vpn:globalprotect` preflight; the conda env installer (`env.py setup`) | — |
| `check_experiments.py` | the lab's experiment-header checker, finding the lab from `--home` / `$ACADEMY_LAB_HOME` / the cwd, dirs from `academy.json` | `tests/test_check_experiments_home.py`; the rules: the lab's `tests/test_check_experiments.py` through its shim |
| `report.py` | `check` / `render` / `file` the experiment-report packet from the header, the result JSON and the report draft; refuses without a type or `## Conclusion`; files the review ticket to the Researcher (`--ask-prefix` marks its ask) | `tests/test_report.py` (real result JSONs in `tests/fixtures/lab/`, golden in `tests/fixtures/expected/`) |
| `lab.py` | `home`, `cmd <queue\|run\|vpn\|check>` (the command that runs it: `env.py` / the plugin checker, else the lab's scripts), `status` | `tests/test_lab_inbox.py` |
| `inbox.py` | the ≤3 tickets to take and each one's route | `tests/test_lab_inbox.py` |
| `commit_gate.py` | PreToolUse `Bash\|PowerShell` hook on `git commit` in the lab repo | `tests/test_hooks.py` |
| `experiment_edit_check.py` | PostToolUse hook: the header checker on an edited lab experiment | `tests/test_hooks.py` |
| `_common.py` | lab scoping, the checker, git, commit-target parsing | via the above |
| `_academy.py` | vendored `academy/lib/academy_common.py`; never edit | academy's `test_vendored.py` |
| `legacy/` | byte-exact copies of the lab's queue/runner scripts, the source of the Group C port; kept until phase 8 | — |

Run the tests: `py -m unittest discover -s tests -t tests` from this folder.

Templates: `templates/report-{search,measure,verify,probe}.md`, the packet bodies
`report.py` fills (sections per docs/packet-template.md section 3).

## Hooks and scoping

Both hooks act only inside a Scientist home: a directory whose
`.claude/academy.json` has `role: scientist` and whose `instance` workspace.json lists
as a scientist (by name, so a worktree of the lab counts). The edit check is scoped
by the edited path (`paths.experiments`), the commit gate by the repository each
`git commit` in the command actually runs in (`cd`, `Set-Location`, `pushd`,
`git -C`), for Bash and PowerShell alike. The mode is the home's `gate` block with
its per-branch override (`academy-migration` is `off`). Before a home is switched
over (no `academy.json`) both hooks are silent and the old plugin's hooks still run.

## The ticket chain

The Scientist's only neighbour is the Researcher. A request for the Expert or the Author
(a citation, a question on a paper's definition) goes to the Researcher with `final_to`,
and the Researcher's `lit-request` relays it; experiments and tests arrive from the
Researcher, whose `experiment-spec` relays those sent on from the Expert. Which lab
agents may file to the Researcher is `academy/permissions.json` `tickets.edges`,
described in `docs/protocol.md` section 5.1.

## Skills

<!-- skills:begin (generated by academy/scripts/skill_index.py; edit the skill's description instead) -->

| Skill | What it does |
|---|---|
| /scientist:api-check | Confirm a library call the lab relies on exists and behaves as assumed, by running it on the probe profile against a known answer, and record the result in the domain pack. Use before writing or queuing any unfamiliar call. |
| /scientist:env | Manage the lab's environment profiles: list, check, set up, switch which profile probe / test / run work uses, add a wsl, local or ssh profile. Use for "which machine does this run on", "is the server reachable", "add a profile". |
| /scientist:examples-audit | Standard-examples audit: for each definition an Author or Researcher states, the experimenter queues a definition test on the domain pack's standard examples and records a lab claim. Use after new definitions, before one is raised to established. |
| /scientist:experiment | Take a mathematical claim from words to a queued, provenance-stamped lab experiment and then to a report packet; header approved before any compute. Use for "let's check this", "can we test", "find a counterexample to", or a finished run's report. |
| /scientist:experiment-method | Discipline for computational experiments in mathematics: numerics refute and suggest, never prove; state the refutation first, validate on known cases, prefer exact arithmetic, keep provenance. Use whenever a claim is tested numerically or a result is quoted. |
| /scientist:inbox | Work the lab's board inbox: take at most three open or accepted tickets and route each by kind (experiment/test, code, Upstream, question). Use for "work the inbox", "handle T-NNNN", or when SessionStart reports tickets. |
| /scientist:queue | Drive the lab's job queue: file a run on an env profile, check preflight, tick, poll, read logs, settle finished jobs and report results. Use for anything about running an experiment, "is it done yet", "start the jobs", or watching pending jobs. |
| /scientist:status | One screen on the lab: switch-over state, env profiles and policy, job queue by state, tickets and packets, results back with no report packet yet. Use for "lab status", "what's running", "what came back", and after a queue tick. |

<!-- skills:end -->
