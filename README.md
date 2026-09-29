# academy

Role-based Claude Code plugins for research mathematics, as one local marketplace.

| Folder | What it is |
|---|---|
| `academy/` | The base plugin: generic best-practice skills, the board and packet plumbing, the MCP server, hooks, and the front desk |
| `author/`, `researcher/`, `expert/`, `scientist/` | The four role plugins. Each can run as several instances, and each has a `README.md` covering its agents, skills, scripts, hooks and place in the ticket chain |
| `domains/<name>/` | Domain packs: knowledge only, no plugin logic |
| `workspace.json` | The instance map: which role runs in which home, for which domains |
| `docs/` | The contracts and the guides (start with `docs/README.md`) |
| `goldens/` | Phase-0 reference outputs that every migration phase must reproduce |
| `_import/` | The imported history of the two predecessor plugins, being moved into place |

Status: under construction (see `docs/migration-log.md`). The design is the approved
plan; `docs/protocol.md`, `docs/packet-template.md` and `docs/config.md` are the
contracts that the code implements.

## Tests

```
py -m unittest discover academy/tests       # from the repo root; stdlib only
py academy/scripts/sync_common.py --check    # the vendored copies of the shared lib
py academy/scripts/skill_index.py --check    # skill descriptions: form, length, total budget
```

`academy/lib/academy_common.py` is the one shared library. Each plugin carries a
byte-identical copy as `scripts/_academy.py`; run `py academy/scripts/sync_common.py`
after changing the lib.

New files use LF (`.gitattributes`); `*.ps1` keeps CRLF.
