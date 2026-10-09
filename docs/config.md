# Configuration: `workspace.json` and `.claude/academy.json`

Plan sections 2, 3.5 and 3.6. There are two files:

- **`workspace.json`**, one per academy, at the repo root. It is the instance map.
- **`.claude/academy.json`**, one per home. It holds what is local to that instance.
  It replaces `.claude/flatsurf.json` and the never-created `.claude/paper-gate.json`.

The loader is `academy_common`:

- `load_workspace()`;
- `find_home(path)` then `load_config(home)`, which merges `CONFIG_DEFAULTS`,
  validates with `validate_config` and adds `_home`;
- `path_in_role(path, config, key)`;
- `gate_mode(config, branch)`.

The tests validate the four examples below, taken directly from this file, so keep
them valid.

**Conventions:**
- All JSON is UTF-8, LF, 2-space indented.
- Paths inside a home are relative to the home and use `/`.
- Absolute paths use `C:/...` forward slashes.
- A plugin script is referred to as `${CLAUDE_PLUGIN_ROOT}/scripts/<name>`.
- Model names are `fable | opus | sonnet | haiku`.

## 1. `workspace.json`

```json
{
  "instances": {
    "<role>@<name>": {
      "role": "author | researcher | expert | scientist (must equal the name's prefix)",
      "home": "C:/absolute/path/of/the/home",
      "domains": ["<pack name>", "..."],
      "ns": "<registry namespace, omitted when the instance has no registry>"
    }
  },
  "board": "C:/absolute/path/of/the/board",
  "human": {"name": "Ada", "noteMacro": "\\ada"},
  "compute": {
    "workers": {"<worker>": {"transport": "ssh", "host": "...", "gateway": "<gateway>", "...": "..."}},
    "gateways": {"<gateway>": {"kind": "vpn", "check": "...", "...": "..."}}
  }
}
```

| Key | Type | Req. | Meaning |
|---|---|---|---|
| `instances` | map name → instance | yes | Name matches `^(author\|researcher\|expert\|scientist)@[a-z0-9][a-z0-9-]*$` |
| `instances.*.role` | enum | yes | Equals the name's prefix |
| `instances.*.home` | abs path | yes | Contains `.claude/academy.json` once the instance is switched over |
| `instances.*.domains` | non-empty list | yes | Pack names under `domains/`; used for routing |
| `instances.*.ns` | str | iff the instance has a registry | Claim-id prefix (`paper`, `nb`, `lab`) |
| `board` | abs path | yes | The board directory, normally the workspace's `board/` (protocol.md section 2) |
| `human` | map | no | `name` for display (default `human`; prompts and scripts say "the human" then), `noteMacro` for the human's margin-note macro, `login` the human's GitHub login (default: `board.assignee`; the GitHub board's ticket form and `board-migrate` use it) |
| `compute` | map | no | The workspace's remote workers and the gateways in front of them (below) |
| `grading` | map | no | `primaryModels`: the grading primaries, equal in authority (default `["fable", "opus-5.5"]`). A positive verdict on any other model is capped (`roster-rules.md`, "Graders degrade"); read by the Expert's `decision_table.py` and `land_referee.py` and the Researcher's experiment reviews |
| `plugins` | list of str | no | The plugins the workspace needs (the bootstrap installs them). Default: `academy`, the role plugins of its instances, and the plugin of every domain pack an instance names (the marketplace's name for `domains/<pack>`) |

`load_workspace` finds it at `$ACADEMY_WORKSPACE`, then `<academy repo>/workspace.json`,
then `<academy repo>/../workspace.json` (the academy checked out inside the workspace). It
adds `_path` and fills the defaults of `human` (`name`, `login`), `grading.primaryModels`
and `plugins`; read them through `human_name()`, `human_login()`, `primary_models()`. The workspace repo generates the file (`scripts/bootstrap.py`, from its
`workspace.template.json`, with this machine's absolute paths) and exports where everything is
as environment variables, so no code or document needs a literal path:

| Variable | Meaning |
|---|---|
| `ACADEMY_ROOT` | the academy repo (plugins, scripts) |
| `ACADEMY_WORKSPACE` | the `workspace.json` above |
| `ACADEMY_BOARD` | the board directory (overrides `board`) |
| `ACADEMY_HOME_<ROLE>_<NAME>` | the home of instance `<role>@<name>` (overrides its `home`) |
| `ACADEMY_LIBRARY` | the home of the first Expert instance |
| `ACADEMY_ENV_WORKSPACE` | the file the variables were derived from; the overrides apply to that file only |
| `ACADEMY_PYTHON` | the Python the plugins' hooks and MCP server run with. Unset: the hooks run `py`, else `python3` (they run in bash, Git Bash on Windows); the MCP server (`.mcp.json`, no shell) runs `py`, so a machine without `py` (Linux, macOS) sets it, e.g. to `python3` |

They are set in `.claude/settings.local.json` of the workspace and of every home, and in the
workspace's `workspace.env` for plain shells (`set -a; . ./workspace.env`). To move a home,
change the variable (or `home`) and nothing else.

### `compute`: remote workers and gateways

The machines experiments run on belong to the workspace, not to the academy: the plugins
ship the mechanism (an ssh transport, the `fsq` queue runner deployed from the Scientist
plugin, pluggable gateway checks; `scientist/scripts/workers.py`) and no machine of their
own. A Scientist home names a worker; the worker's values live here, once:

```json
"compute": {
  "workers": {
    "remote-a": {"transport": "ssh", "host": "remote-a", "user": "ada",
                 "remoteRoot": "~", "maxJobs": 1,
                 "conda": {"prefix": "/data/ada/miniforge3", "env": "sci"},
                 "gateway": "site-vpn"}
  },
  "gateways": {
    "site-vpn": {"kind": "vpn", "client": "globalprotect", "check": "globalprotect",
                 "portal": "vpn.example.org", "probeHost": "remote-a.example.org:22",
                 "owner": "Ada", "onDown": "ask {owner} to connect {gateway}"}
  }
}
```

| Key | Req. | Meaning |
|---|---|---|
| `workers.<w>.transport` | no | `ssh` (the only transport; default) |
| `workers.<w>.host` | yes | ssh host or alias (an `~/.ssh/config` alias may carry user and key) |
| `workers.<w>.user` | no | ssh user; the destination becomes `user@host` |
| `workers.<w>.remoteRoot` | no | Where homes are cloned on the worker: a home's remote repo is `<remoteRoot>/<home folder name>` (default `~/<home folder name>`); a profile's `repo` overrides (set it when the home is also used from a worktree with another folder name) |
| `workers.<w>.conda` | no | `{prefix, env}`: the Miniforge prefix and the conda env jobs run in (`env.py setup` creates it, the runner activates it) |
| `workers.<w>.maxJobs` | no | Runner concurrency cap, 1..3 |
| `workers.<w>.gateway` | no | A key of `gateways`; none means the worker is reached directly |
| `gateways.<g>.kind` | yes | `vpn` or `none` |
| `gateways.<g>.check` | vpn | How "up" is decided, locally, before anything is sent: `globalprotect` (the adapter's status on Windows via `vpn.ps1`, else the `globalprotect` CLI), `openconnect` (an `openconnect` process runs), `tcp-reachable` (a TCP connection to `probeHost` opens within `timeoutMs`, default 4000), `command` (`command`, a shell line, exits 0 up / 1 down). Default: `client` |
| `gateways.<g>.client`, `portal` | no | The VPN client and the portal the human connects to (for the human; `client` is the default `check`) |
| `gateways.<g>.probeHost` | tcp-reachable | `host:port`; also what `env.py gateway --probe` connects to after a local check says up |
| `gateways.<g>.adapter` | no | `globalprotect` on Windows: the adapter match (default `PANGP\|GlobalProtect`) |
| `gateways.<g>.owner` | no | Who can bring the gateway up (default `human.name`) |
| `gateways.<g>.onDown` | no | What the agent tells the human when the gateway is down; `{owner}`, `{human}`, `{gateway}`, `{worker}` are filled in (default "ask {owner} to bring up {gateway}; jobs for {worker} wait in the queue") |

A gateway that is down means "queued, not failed": jobs wait in the home's queue, the
agent repeats the `onDown` and stops. `env.py list` shows the resolved profiles and any
problem of the block; `env.py gateway` runs the check alone. The workspace bootstrap
copies `compute` from `workspace.template.json` into `workspace.json` unchanged (it holds
no paths of the local machine).

Adding an instance means one row here plus one `academy.json` in its home
(`/academy:init`). The two must agree on `role`, `instance`, `domains` and `ns`;
`session_start` reports any disagreement.

## 2. `.claude/academy.json`: common keys

| Key | Type | Req. | Default | Meaning |
|---|---|---|---|---|
| `schema` | int | yes | | `1` |
| `role` | enum | yes | | `author` \| `researcher` \| `expert` \| `scientist` |
| `instance` | str | yes | | `<role>@<name>`; its prefix equals `role` |
| `domains` | list of str | yes | | Pack names; the same as in workspace.json |
| `ns` | str | iff `registry.profile != "none"` | | This home's claim namespace |
| `workspace` | abs path | no | lookup order above | Override for `workspace.json` |
| `paths` | map key → pattern(s) | yes | `{}` | Named path sets; per-role required keys below. `paths.verifyChecklist` (any role with a registry, default `.claude/rules/verification-checklist.md`): the home's own checklist the rigor review and `/researcher:settle` read, when it has one |
| `registry` | map | yes | | See below |
| `budget` | map | no | see below | Per-run limits |
| `gate` | map | no | see below | Commit and build gates |
| `<role>` | map | yes | | The role block (`author`, `researcher`, `expert` or `scientist`) |

**`paths`.** Each value is a pattern or a list of patterns.
- A pattern without `*`/`?` matches that file, or everything under it if it is a
  directory.
- `*` matches within one segment, and `**` matches any number of segments.
- Matching is case-insensitive on Windows.
- `path_in_role(p, cfg, "tex")` answers "is `p` one of this home's tex files";
  `path_in_role(p, cfg, cfg["role"])` answers "is `p` in this home at all".
- `views` lists the generated files, which `generated_view_guard` protects.

**`registry`:**

| Key | Type | Req. | Meaning |
|---|---|---|---|
| `profile` | `paper` \| `notebook` \| `lab` \| `none` | yes | The engine's per-home rule set (plan section 6). `s1` and `s1-kb`, the older names of `notebook`, are still accepted |
| `prefixes` | map prefix → name | no, default none | `notebook` rule set: the id prefixes, in display order (ids are `PREFIX-<number or token>`; `Q` also admits `Q<n>`; `EX` is reserved for examples and `DIR` for directions when listed). Without it any slug id is allowed |
| `assumptionGroups` | map prefix → name | no, default none | `notebook` rule set: the prefixes of assumption records and the heading of each group in `views/assumptions.md`. Without it assumptions are one ungrouped list |
| `root` | path | iff profile != none | Directory of the object files |
| `db` | path | no, default `.claude/academy.sqlite` | Derived SQLite + FTS index (gitignored) |
| `statusKeeper` | bare agent | no, default `claim-keeper` | The only agent that sets a status |
| `legacy` | map | no | Old command lines kept alive by shims during migration |
| `check` | command | no | Replaces the engine's `check <file>` in the record hook (`{file}` is the record); for tests |
| `build` | bool | no, default from the profile (`notebook`: true) | Whether the record hook follows an edit with a blocking `build` |

The engine is `academy/registry` (`py -m registry --repo <home> <command>`, cwd
`academy/academy`); `profile` picks its rule set (`lab`, `paper`: engine profile
fsl-claims; `notebook`: s1-kb). A home without academy.json gets the rule set named like
its workspace `ns` (an old alias included), else `lab`. `db` is not used yet: the engine builds its SQLite in memory for every
query, and s1-kb's `build` still writes `kb/kb.sqlite`.

*R6 (Group D, 2026-09-28):* the s1-kb profile reads a home in the notebook layout when it
has an `objects/` folder: records under `objects/<kind>/` (the record's `kind` must match
its folder), directions with prefix `DIR`, experiment audits under `audits/<subject>/`
beside `computation/verdicts/` (both accepted by `set-status --verdict`), and `build`
writes `views/` (`assumptions.md`, `INDEX.md`, `directions.md`, `graph.md`,
`rests-on.md`). Without `objects/` it reads the old layout (`claims/`, `assumptions/`,
`examples/`). The lab and paper homes keep `claims/<ns>/`.

*Phase 7 (2026-09-28, P-0004 D9 / P-0005 D8):* the 19 s1 claim verdicts are in the
Expert's library, `<library>/reviews/s1/<claim>/`, and s1 records cite them as
`file:expert@main/reviews/s1/<claim>/<file>.md`. `set-status --verdict` (and MCP
`claims_set_status`, `grounds.verdict_file`) accepts such a ref, or a path into the
library's `reviews/`, as the verdict anchor; the instance's home comes from
workspace.json (`registry/core/workspace.instance_home`, a worktree sibling first).
`check` reports a review ref whose file is missing. The old copies in the notebook's
`computation/verdicts/` were deleted in phase 8.

**`budget`:**

| Key | Type | Default | Meaning |
|---|---|---|---|
| `itemsPerRun` | int 1..3 | 3 | Most tickets one inbox run takes (a campaign lifts the cap) |
| `serial` | bool | true | Items run one after another |
| `orchestratorModel` | model | `sonnet` | Model for skill orchestrators |
| `maxModel` | model | `fable` | Heaviest model any agent in this home may use |
| `ticketDefault` | `{runs}` | `{1}` | Budget written into new tickets when the sender gives none. A `max_model` here is ignored: an agent runs on its agent file's model (T-0071) |

**`gate`:**

| Key | Type | Default | Meaning |
|---|---|---|---|
| `commit` | `strict` \| `normal` \| `warn` \| `off` | `normal` | `commit_gate` mode: strict fails on warnings, warn reports what would block without blocking (Author and Scientist gates), off disables |
| `build` | bool | true | `build_gate` runs on SubagentStop of a writer agent (author) |
| `baseline` | path \| null | null | Accepted open findings; a finding outside it blocks a commit |
| `branches` | map branch or glob → `{commit}` | `{}` | Per-branch override; `academy-migration` sets `off` (plan 9b). An exact name wins, else the first matching glob in map order (`fnmatch`, case-sensitive, `*` also matches `/`), e.g. `"????-??-??/*/*": {"commit": "warn"}` for work branches |

## 3. Role blocks

### `author`

| Key | Type | Meaning |
|---|---|---|
| `main` | path | The root `.tex` file |
| `build` | `{dir, cmd, lock}` | Output dir, build argv, and the lock file `build_gate` holds against LaTeX Workshop |
| `checker` | `{script, args, strictArgs, statements}` | `check_paper.py` in the plugin and its arguments; `statements` is its generated registry view |
| `theorems` | `{all, provable, commentary}` | Replaces `THEOREM_ENVS`, `PROVABLE_ENVS`, `COMMENTARY_ENVS` |
| `envs` | map env → status | Replaces `COLOUR_ENVS`; the draft-colour environments and the status each marks |
| `colourCommands` | map macro → status | Replaces `COLOUR_COMMANDS` |
| `colours` | map status → colour name | For the legend and the dashboard |
| `noteMacros` | `{human: [..], coauthors: [..], machine: [..]}` | Margin-note macros; machine notes are the `\Claude` family |
| `crlf` | list of patterns | Files written with `newline="\r\n"`; everything else is LF |
| `writers` | list of bare agents | Agents whose SubagentStop triggers `build_gate` |
| `bibWriters` | list of bare agents | Agents allowed to edit `paths.bib` (`bib_gate`) |
| `provenance` | map, optional | The provenance marker for what the authors added since the last accepted round (a new claim, an added assumption, a proof following a lead), layered on the status colour: `env` (block environment, default `added`), `command` (short-span macro, default `\Added`), `kinds` (the `%% added: <kind>` tags, default `claim`, `assumption`, `lead-proof`), `removedBy` (default `human`: writers never remove it). Absent, or `"enabled": false`: no marker. Read by `academy_common.author_provenance` |

**Required paths:** `tex`, `bib`, `drafts`, `agenda`, `records`, `views`. (`paths.roadmap`
was required until 2026-09-30, when the roadmap was dropped and the board became the
Author's only queue; a config that still has the key validates and the key is ignored.)

### `researcher`

| Key | Type | Meaning |
|---|---|---|
| `objectKinds` | list | `definition claim conjecture question example assumption direction` (`approach` too, for campaigns) |
| `statusField` | str | The frontmatter key guarded by `status_guard` (`status`) |
| `reviewsHome` | instance | Where proof reviews live (`expert@main`) |
| `lab` | instance | The Scientist instance experiments go to |
| `generalize` | `{maxPerRun, raiseAbove}` | Most generalizations per `/researcher:generalize` run, and the highest status it may set (`conjectured`) |

**Required paths:** `objects`, `proofs`, `journal`, `audits`, `records`, `views`.

### `expert`

| Key | Type | Meaning |
|---|---|---|
| `bibs` | list of `<instance>:<path>` | The bibliographies the librarian keeps |
| `accessLog` | path | Clerk access log feeding `hot.md`: the MCP server appends one line per `library_*` call there, and `hot.py` reads it. Default `.academy/access.log` (derived state, ignored by git); keep it under `.academy/` |
| `hotSize` | int | Entries kept in `hot.md` |
| `web` | `{clerk, librarian}` | Whether each agent may fetch from the web (the clerk never does) |
| `shards` | map domain → path | `<library>/<domain>/cards` sharding when the library serves several packs |

**Required paths:** `index`, `cards`, `ledgers`, `reviews`, `hot`, `cache`, `views`.

### `scientist`

| Key | Type | Meaning |
|---|---|---|
| `envs` | map profile → profile | Environment profiles, see below |
| `policy` | `{probe, test, run}` → profile | Which profile each kind of work uses; "no laptop compute" is `run` pointing at a remote profile |
| `queue` | `{dir, fsqHome, maxJobs, mcpAdd}` | Local queue state and runner settings; `mcpAdd` is `dry-run` (default: the MCP tool `queue_add` returns the job file it would write) or `on` (it writes it). Filing from the shell is unaffected |
| `checker` | path | The experiment-header checker the hooks run (default: the home's `scripts/check_experiments.py`; the plugin's is `${CLAUDE_PLUGIN_ROOT}/scripts/check_experiments.py`) |
| `experimentTypes` | list | `search measure verify probe` |
| `reportTemplates` | path | Report templates by type (plugin-relative) |
| `knownCases` | str | Validation cases in words, and where they live |

**Environment profile** (`envs.<name>`):

| Key | Kinds | Req. | Meaning |
|---|---|---|---|
| `worker` | (ssh) | — | A worker of the workspace's `compute.workers` (section 1): the profile is that worker's ssh profile (host, user, conda prefix and env, remote repo, maxJobs, gateway); any other key given here overrides the worker's value for this home. `kind` may then be omitted |
| `kind` | all | yes, unless `worker` | `wsl` \| `local` \| `ssh` |
| `distro` | wsl | yes | The WSL distro |
| `conda` | wsl, local | no | The conda env to activate |
| `host` | ssh | yes | ssh host alias |
| `user` | ssh | no | ssh user (`user@host`) |
| `prefix` | all | no | Conda (Miniforge) prefix on that machine; default `~/miniforge3` |
| `env` | ssh | no | Remote conda env name |
| `repo` | ssh | no | Remote clone of the home |
| `maxJobs` | ssh, local | no | Runner concurrency cap, 1..3 |
| `gateway` | ssh | no | A key of the workspace's `compute.gateways`, checked before anything is sent; down means "queued", not an error |
| `preflight` | all | no | The older inline form of a gateway, `vpn:<check>` (e.g. `vpn:globalprotect`) |
| `pushUrl`, `remoteEnv` | ssh, wsl | no | Test stand-ins only (as in the legacy `queue/config.json`): the git URL the job commit is pushed to, and assignments prefixed to every runner call |

The runner is `scientist/scripts/env.py` (`list`, `check <profile> [--live]`,
`run <profile> ...`, `setup`, `gateway` (alias `vpn`), `queue ...`). Wherever it takes a
profile it also takes a `policy` key (`probe`, `test`, `run`) or a legacy target (`wsl`,
`wsl:<distro>`, `ssh:<host or worker>`). It has no built-in profile: a name the home does
not define is refused, with a pointer at `compute`. `setup` installs the packages the
home's domain packs list in `domains/<pack>/computation/env.txt` (and runs the pack's
`env-check.py`). A home with no academy.json yet gets its queue target from
`queue/config.json` (profile `queue`, which must name a `target`) and a `laptop-wsl`
profile.

*Extensions (Group C, 2026-09-28):* `prefix` on every kind (was ssh only),
`pushUrl` / `remoteEnv`, `queue.mcpAdd`, and the `checker` row above (read by
`scientist/scripts/_common.py` since Group B, undocumented until now).

**Required paths:** `package`, `experiments`, `results`, `queue`, `records`, `views`.

## 4. Examples (the four homes)

One config per role, for a workspace whose human is "Ada", with a paper (`paper`), a
notebook (`nb`) and a lab (`lab`). The tests read these blocks, so they stay valid.

### Example: author@main

```json
{
  "schema": 1,
  "role": "author",
  "instance": "author@main",
  "domains": ["translation-surfaces"],
  "ns": "paper",
  "paths": {
    "tex": ["main.tex", "sections/*.tex", "tikz/*.tex"],
    "bib": "references.bib",
    "drafts": "Drafts",
    "agenda": "Drafts/agenda.md",
    "records": "claims",
    "figures": "figures",
    "views": ["Drafts/statements.md", "Drafts/experiments.md", "Drafts/verdicts.md",
              "Drafts/sources.md", "Drafts/related_work.md", "claims/INDEX.md",
              "claims/index.html"]
  },
  "registry": {"profile": "paper", "root": "claims", "db": ".claude/academy.sqlite",
               "statusKeeper": "claim-keeper"},
  "budget": {"itemsPerRun": 3, "serial": true, "orchestratorModel": "sonnet",
             "maxModel": "fable", "ticketDefault": {"runs": 1}},
  "gate": {"commit": "normal", "build": true,
           "baseline": ".claude/paper-gate-baseline.txt",
           "branches": {"academy-migration": {"commit": "off"}}},
  "author": {
    "main": "main.tex",
    "build": {"dir": ".build", "cmd": ["latexmk", "-pdf", "main.tex"], "lock": ".build/.lock"},
    "checker": {"script": "${CLAUDE_PLUGIN_ROOT}/scripts/check_paper.py", "args": [],
                "strictArgs": ["--strict"], "statements": "Drafts/statements.md"},
    "theorems": {
      "all": ["thm", "prop", "lem", "fact", "cor", "conj", "defn", "exc", "rmk", "ex",
              "exer", "quest", "claim", "case", "claim*", "problem"],
      "provable": ["thm", "prop", "lem", "cor", "claim", "claim*"],
      "commentary": ["rmk", "quest"]
    },
    "envs": {"sketch": "sketch", "conjectural": "conjectural", "meta": "meta"},
    "colourCommands": {"\\Sketch": "sketch", "\\Conjectural": "conjectural", "\\Meta": "meta"},
    "colours": {"established": "black", "sketch": "blue", "conjectural": "red", "meta": "brown"},
    "noteMacros": {"human": ["\\ada"],
                   "coauthors": ["\\Bo", "\\Cy"],
                   "machine": ["\\Claude", "\\cl"]},
    "crlf": ["sections/*.tex", "tikz/*.tex"],
    "writers": ["math-writer", "math-editor", "tex-engineer", "figure-maker", "note-sweeper"],
    "bibWriters": ["librarian"]
  }
}
```

### Example: researcher@alpha

```json
{
  "schema": 1,
  "role": "researcher",
  "instance": "researcher@alpha",
  "domains": ["translation-surfaces"],
  "ns": "nb",
  "paths": {
    "objects": "objects",
    "proofs": "proofs",
    "journal": "journal",
    "audits": "audits",
    "records": "objects",
    "library": "literature",
    "views": ["views", "INDEX.md", "OPEN.md", "STATUS.md", "site/index.html",
              "kb/claims.json", "computation/verdicts.md", "computation/runs.md"]
  },
  "registry": {"profile": "notebook", "root": "objects", "db": ".claude/academy.sqlite",
               "statusKeeper": "claim-keeper"},
  "budget": {"itemsPerRun": 3, "serial": true, "orchestratorModel": "sonnet",
             "maxModel": "fable", "ticketDefault": {"runs": 1}},
  "gate": {"commit": "normal", "build": false, "baseline": null,
           "branches": {"academy-migration": {"commit": "off"}}},
  "researcher": {
    "objectKinds": ["definition", "claim", "conjecture", "question", "example",
                    "assumption", "direction"],
    "statusField": "status",
    "reviewsHome": "expert@main",
    "lab": "scientist@main",
    "generalize": {"maxPerRun": 3, "raiseAbove": "conjectured"}
  }
}
```

### Example: expert@main

```json
{
  "schema": 1,
  "role": "expert",
  "instance": "expert@main",
  "domains": ["translation-surfaces"],
  "paths": {
    "index": "index.md",
    "cards": "cards",
    "ledgers": "ledgers",
    "reviews": "reviews",
    "hot": "hot.md",
    "cache": ["*.pdf", "*.txt", "*.meta", "*.src/**", "*_eprint.tar.gz"],
    "views": ["hot.md"]
  },
  "registry": {"profile": "none", "db": ".claude/academy.sqlite"},
  "budget": {"itemsPerRun": 3, "serial": true, "orchestratorModel": "sonnet",
             "maxModel": "fable", "ticketDefault": {"runs": 1}},
  "gate": {"commit": "off", "build": false, "baseline": null, "branches": {}},
  "expert": {
    "bibs": ["author@main:references.bib"],
    "accessLog": ".academy/access.log",
    "hotSize": 50,
    "web": {"clerk": false, "librarian": true},
    "shards": {}
  }
}
```

### Example: scientist@main

```json
{
  "schema": 1,
  "role": "scientist",
  "instance": "scientist@main",
  "domains": ["translation-surfaces"],
  "ns": "lab",
  "paths": {
    "package": "labpkg",
    "experiments": "experiments/*.py",
    "results": "results",
    "queue": "queue",
    "records": "claims",
    "tests": "tests",
    "docs": "docs",
    "views": ["claims/INDEX.md", "claims/index.html"]
  },
  "registry": {"profile": "lab", "root": "claims", "db": ".claude/academy.sqlite",
               "statusKeeper": "claim-keeper"},
  "budget": {"itemsPerRun": 3, "serial": true, "orchestratorModel": "sonnet",
             "maxModel": "fable", "ticketDefault": {"runs": 1}},
  "gate": {"commit": "normal", "build": false, "baseline": null,
           "branches": {"academy-migration": {"commit": "off"}}},
  "scientist": {
    "envs": {
      "laptop-wsl": {"kind": "wsl", "distro": "Ubuntu", "conda": "flatsurf"},
      "local": {"kind": "local", "conda": "flatsurf"},
      "remote-a": {"worker": "remote-a"}
    },
    "policy": {"probe": "laptop-wsl", "test": "laptop-wsl", "run": "remote-a"},
    "queue": {"dir": "queue", "fsqHome": "~/fsq", "maxJobs": 1},
    "experimentTypes": ["search", "measure", "verify", "probe"],
    "reportTemplates": "${CLAUDE_PLUGIN_ROOT}/templates",
    "knownCases": "the square torus, the 3-square L in H(2), the Eierlegende Wollmilchsau, the double pentagon, and the worked cases in tests/"
  }
}
```

## 5. Validation summary

`validate_config` rejects a config when any of the following holds:

- `schema` is not 1, or `role` / `instance` is bad or they disagree;
- `domains` is empty;
- `registry.profile` is unknown, or `ns` is missing when a registry is used, or
  `registry.prefixes` / `registry.assumptionGroups` is neither a map nor a list;
- a required path key for the role is missing, or the role block is missing;
- `budget.itemsPerRun` is outside 1..3, or a model name is unknown;
- `gate.commit` (or a branch override) is outside `strict | normal | warn | off`;
- for a scientist: any profile `kind` is outside `wsl | local | ssh` (a profile with
  `worker` may omit it), an ssh profile has no `host`, a wsl profile has no `distro`,
  a `worker` is empty, or a `policy` entry names no existing profile. Whether the
  worker exists in the workspace's `compute` is checked by `env.py` (`list`, `check`)
  and `env_check`, not here.

Unknown extra keys are allowed, for forward compatibility. `session_start` prints the
problems and stays silent otherwise.
