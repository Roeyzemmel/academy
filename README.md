# academy

Role-based Claude Code plugins for research mathematics, as one local marketplace.

| Folder | What it is |
|---|---|
| `academy/` | The base plugin: generic best-practice skills, the board and packet plumbing, the MCP server, hooks, and the front desk |
| `author/`, `researcher/`, `expert/`, `scientist/` | The four role plugins. Each can run as several instances, and each has a `README.md` covering its agents, skills, scripts, hooks and place in the ticket chain |
| `domains/<name>/` | Domain packs: knowledge only, no plugin logic |
| `academy/docs/` | The contracts and the guides (start with `academy/docs/README.md`; branches and shipping: `academy/docs/branching.md`) |

The instance map, `workspace.json` (which role runs in which home, for which domains), the
board (`board/`) and the homes live in the workspace that uses these plugins, not here;
`academy/scripts/workspace_bootstrap.py` generates the map and `academy/scripts/ship.py`
commits and pushes the workspace's work (`academy/docs/branching.md`). The one-time migrations and
their goldens are archived in the workspace (`archive/academy-migrations/`).

Status: under construction (see `academy/docs/migration-log.md`). The design is the approved
plan; `academy/docs/protocol.md`, `academy/docs/packet-template.md` and `academy/docs/config.md` are the
contracts that the code implements.

## Tests

```
py -m unittest discover -s academy/tests -t academy/tests   # from the repo root; stdlib only
                                             # likewise academy/registry/tests, <role>/tests,
                                             # domains/<pack>/tests
py academy/scripts/sync_common.py --check    # the vendored copies of the shared lib
py academy/scripts/skill_index.py --check    # skill descriptions: form, length, total budget
```

The suites are hermetic: every test builds its own workspace, homes, board and library in a
temp directory, so the result depends on the repo and not on the machine (no `ACADEMY_*`
variables, `~/.claude`, global git identity or network needed). The few tests that compare the
code with the real data of a workspace (the real registries, the real library index) are opt-in:
they run only with `ACADEMY_TEST_REAL=1`, and never when `CI` is set, which the push gate sets;
`academy/tests/test_no_real_home_leaks.py` fails if a test reaches a real home any other way.
Some tests need an optional tool and skip without it: `node` (the workflow scripts of every
plugin), `bash` (`ci_local`, the runner test of the scientist plugin), `latexmk` and
`latexdiff` (the author plugin's coloured diff), `git` (the tests that make a throw-away
repo), `powershell` (the lab queue's `.ps1` front end); a machine without them tests less.
Importing the shared library still reads `/etc/environment` (a workspace's tagged variables):
it has no override, so run the suites on a machine without such a file for a fully scrubbed run.

`academy/lib/academy_common/` is the one shared library: a package of parts (config,
workspace, tickets, the board store, the inbox core, packets, hooks, ...) that callers
use as one module, `ac.<name>`. Each plugin carries a byte-identical copy as
`scripts/_academy/`; run `py academy/scripts/sync_common.py` after changing the lib.

New files use LF (`.gitattributes`); `*.ps1` keeps CRLF.
