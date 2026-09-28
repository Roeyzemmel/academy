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
  "board": "C:/Work/Math/board",
  "human": {"name": "Roey", "noteMacro": "\\Roey"}
}
```

| Key | Type | Req. | Meaning |
|---|---|---|---|
| `instances` | map name → instance | yes | Name matches `^(author\|researcher\|expert\|scientist)@[a-z0-9][a-z0-9-]*$` |
| `instances.*.role` | enum | yes | Equals the name's prefix |
| `instances.*.home` | abs path | yes | Contains `.claude/academy.json` once the instance is switched over |
| `instances.*.domains` | non-empty list | yes | Pack names under `domains/`; used for routing |
| `instances.*.ns` | str | iff the instance has a registry | Claim-id prefix (`paper`, `s1`, `lab`) |
| `board` | abs path | yes | The board repo (protocol.md section 2) |
| `human` | map | no | `name` for display, `noteMacro` for the human's margin-note macro |

`load_workspace` finds it at `$ACADEMY_WORKSPACE`, then `<academy repo>/workspace.json`,
then `C:/Work/Math/academy/workspace.json`. It adds `_path`. The current file:

```json
{"instances": {
  "expert@ts":          {"role":"expert",     "home":"C:/Work/Math/papers",                     "domains":["translation-surfaces"]},
  "scientist@ts":       {"role":"scientist",  "home":"C:/Work/Math/FlatSurfLab",                "domains":["translation-surfaces"], "ns":"lab"},
  "researcher@slope1":  {"role":"researcher", "home":"C:/Work/Math/Slope1illuminationResearch", "domains":["translation-surfaces"], "ns":"s1"},
  "author@bi":          {"role":"author",     "home":"C:/Work/Math/BilliardIllumination",       "domains":["translation-surfaces"], "ns":"paper"}},
 "board":"C:/Work/Math/board", "human":{"name":"Roey","noteMacro":"\\Roey"}}
```

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
| `paths` | map key → pattern(s) | yes | `{}` | Named path sets; per-role required keys below |
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
| `profile` | `paper` \| `s1` \| `lab` \| `none` | yes | The engine's per-home rule profile (plan section 6) |
| `root` | path | iff profile != none | Directory of the object files |
| `db` | path | no, default `.claude/academy.sqlite` | Derived SQLite + FTS index (gitignored) |
| `statusKeeper` | bare agent | no, default `claim-keeper` | The only agent that sets a status |
| `legacy` | map | no | Old command lines kept alive by shims during migration |
| `check` | command | no | Replaces the engine's `check <file>` in the record hook (`{file}` is the record); for tests |
| `build` | bool | no, default from the profile (`s1`: true) | Whether the record hook follows an edit with a blocking `build` |

The engine is `academy/registry` (`py -m registry --repo <home> <command>`, cwd
`academy/academy`); `profile` picks its rule set (`lab`, `paper`: engine profile
fsl-claims; `s1`: s1-kb). A home without academy.json gets the rule set named like its
workspace `ns`. `db` is not used yet: the engine builds its SQLite in memory for every
query, and s1-kb's `build` still writes `kb/kb.sqlite`.

*R6 (Group D, 2026-09-28):* the s1-kb profile reads a home in the notebook layout when it
has an `objects/` folder: records under `objects/<kind>/` (the record's `kind` must match
its folder), directions with prefix `DIR`, experiment audits under `audits/<subject>/`
beside `computation/verdicts/` (both accepted by `set-status --verdict`), and `build`
writes `views/` (`assumptions.md`, `INDEX.md`, `directions.md`, `graph.md`,
`rests-on.md`). Without `objects/` it reads the old layout (`claims/`, `assumptions/`,
`examples/`). The lab and paper homes keep `claims/<ns>/`.

**`budget`:**

| Key | Type | Default | Meaning |
|---|---|---|---|
| `itemsPerRun` | int 1..3 | 3 | Most tickets or agenda items one inbox or next run takes |
| `serial` | bool | true | Items run one after another |
| `orchestratorModel` | model | `sonnet` | Model for skill orchestrators |
| `maxModel` | model | `fable` | Heaviest model any agent in this home may use |
| `ticketDefault` | `{runs, max_model}` | `{1, sonnet}` | Budget written into new tickets when the sender gives none |

**`gate`:**

| Key | Type | Default | Meaning |
|---|---|---|---|
| `commit` | `strict` \| `normal` \| `off` | `normal` | `commit_gate` mode: strict fails on warnings, off disables |
| `build` | bool | true | `build_gate` runs on SubagentStop of a writer agent (author) |
| `baseline` | path \| null | null | Accepted open findings; a finding outside it blocks a commit |
| `branches` | map branch → `{commit}` | `{}` | Per-branch override; `academy-migration` sets `off` (plan 9b) |

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

**Required paths:** `tex`, `bib`, `drafts`, `agenda`, `roadmap`, `records`, `views`.

### `researcher`

| Key | Type | Meaning |
|---|---|---|
| `objectKinds` | list | `definition claim conjecture question example assumption direction` |
| `statusField` | str | The frontmatter key guarded by `status_guard` (`status`) |
| `reviewsHome` | instance | Where proof reviews live (`expert@ts`) |
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
| `shards` | map domain → path | `papers/<domain>/cards` sharding when the library serves several packs |

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
| `kind` | all | yes | `wsl` \| `local` \| `ssh` |
| `distro` | wsl | yes | The WSL distro |
| `conda` | wsl, local | no | The conda env to activate |
| `host` | ssh | yes | ssh host alias |
| `prefix` | all | no | Conda (Miniforge) prefix on that machine; default `~/miniforge3` |
| `env` | ssh | no | Remote conda env name |
| `repo` | ssh | no | Remote clone of the home |
| `maxJobs` | ssh, local | no | Runner concurrency cap, 1..3 |
| `preflight` | all | no | Pluggable check, `<name>:<arg>`, e.g. `vpn:globalprotect`; a failing preflight on an ssh profile means "queued", not an error |
| `pushUrl`, `remoteEnv` | ssh, wsl | no | Test stand-ins only (as in the legacy `queue/config.json`): the git URL the job commit is pushed to, and assignments prefixed to every runner call |

The runner is `scientist/scripts/env.py` (`list`, `check <profile> [--live]`,
`run <profile> ...`, `setup`, `vpn`, `queue ...`). Wherever it takes a profile it also
takes a `policy` key (`probe`, `test`, `run`) or a legacy target (`wsl`,
`wsl:<distro>`, `ssh:<host>`). A home with no academy.json yet gets its queue target
from `queue/config.json` (profile `queue`) and a `laptop-wsl` profile.

*Extensions (Group C, 2026-09-28):* `prefix` on every kind (was ssh only),
`pushUrl` / `remoteEnv`, `queue.mcpAdd`, and the `checker` row above (read by
`scientist/scripts/_common.py` since Group B, undocumented until now).

**Required paths:** `package`, `experiments`, `results`, `queue`, `records`, `views`.

## 4. Examples (the four homes)

These are the target configs after each home's switch-over. Paths that do not exist
yet are created by that phase. A `legacy` entry names the old command kept alive by
a shim until phase 8.

### Example: author@bi

```json
{
  "schema": 1,
  "role": "author",
  "instance": "author@bi",
  "domains": ["translation-surfaces"],
  "ns": "paper",
  "paths": {
    "tex": ["main.tex", "sections/*.tex", "tikz/*.tex"],
    "bib": "references.bib",
    "drafts": "Drafts",
    "agenda": "Drafts/agenda.md",
    "roadmap": "Drafts/roadmap.md",
    "records": "claims",
    "figures": "figures",
    "views": ["Drafts/statements.md", "Drafts/experiments.md", "Drafts/verdicts.md",
              "Drafts/sources.md", "Drafts/related_work.md", "claims/INDEX.md",
              "claims/index.html"]
  },
  "registry": {"profile": "paper", "root": "claims", "db": ".claude/academy.sqlite",
               "statusKeeper": "claim-keeper",
               "legacy": {"claims": "py ../FlatSurfLab/scripts/claims.py --repo ."}},
  "budget": {"itemsPerRun": 3, "serial": true, "orchestratorModel": "sonnet",
             "maxModel": "fable", "ticketDefault": {"runs": 1, "max_model": "sonnet"}},
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
    "noteMacros": {"human": ["\\Roey", "\\rz"],
                   "coauthors": ["\\Barak", "\\Carlos", "\\Victoria", "\\Hayim", "\\bw"],
                   "machine": ["\\Claude", "\\cl"]},
    "crlf": ["sections/*.tex", "tikz/*.tex"],
    "writers": ["math-writer", "math-editor", "tex-engineer", "figure-maker", "note-sweeper"],
    "bibWriters": ["librarian"]
  }
}
```

### Example: researcher@slope1

```json
{
  "schema": 1,
  "role": "researcher",
  "instance": "researcher@slope1",
  "domains": ["translation-surfaces"],
  "ns": "s1",
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
  "registry": {"profile": "s1", "root": "objects", "db": ".claude/academy.sqlite",
               "statusKeeper": "claim-keeper",
               "legacy": {"kb": "py tools/kb.py"}},
  "budget": {"itemsPerRun": 3, "serial": true, "orchestratorModel": "sonnet",
             "maxModel": "fable", "ticketDefault": {"runs": 1, "max_model": "sonnet"}},
  "gate": {"commit": "normal", "build": false, "baseline": null,
           "branches": {"academy-migration": {"commit": "off"}}},
  "researcher": {
    "objectKinds": ["definition", "claim", "conjecture", "question", "example",
                    "assumption", "direction"],
    "statusField": "status",
    "reviewsHome": "expert@ts",
    "lab": "scientist@ts",
    "generalize": {"maxPerRun": 3, "raiseAbove": "conjectured"}
  }
}
```

### Example: expert@ts

```json
{
  "schema": 1,
  "role": "expert",
  "instance": "expert@ts",
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
             "maxModel": "fable", "ticketDefault": {"runs": 1, "max_model": "sonnet"}},
  "gate": {"commit": "off", "build": false, "baseline": null, "branches": {}},
  "expert": {
    "bibs": ["author@bi:references.bib"],
    "accessLog": ".academy/access.log",
    "hotSize": 50,
    "web": {"clerk": false, "librarian": true},
    "shards": {}
  }
}
```

### Example: scientist@ts

```json
{
  "schema": 1,
  "role": "scientist",
  "instance": "scientist@ts",
  "domains": ["translation-surfaces"],
  "ns": "lab",
  "paths": {
    "package": "fslab",
    "experiments": "experiments/*.py",
    "results": "results",
    "queue": "queue",
    "records": "claims",
    "tests": "tests",
    "docs": "docs",
    "views": ["claims/INDEX.md", "claims/index.html"]
  },
  "registry": {"profile": "lab", "root": "claims", "db": ".claude/academy.sqlite",
               "statusKeeper": "claim-keeper",
               "legacy": {"claims": "py scripts/claims.py"}},
  "budget": {"itemsPerRun": 3, "serial": true, "orchestratorModel": "sonnet",
             "maxModel": "fable", "ticketDefault": {"runs": 1, "max_model": "sonnet"}},
  "gate": {"commit": "normal", "build": false, "baseline": null,
           "branches": {"academy-migration": {"commit": "off"}}},
  "scientist": {
    "envs": {
      "laptop-wsl": {"kind": "wsl", "distro": "Ubuntu", "conda": "flatsurf"},
      "local": {"kind": "local", "conda": "flatsurf"},
      "lingo": {"kind": "ssh", "host": "lingo", "prefix": "/data/roeyzemmel/miniforge3",
                "env": "flatsurf", "repo": "~/FlatSurfLab", "maxJobs": 1,
                "preflight": "vpn:globalprotect"}
    },
    "policy": {"probe": "laptop-wsl", "test": "laptop-wsl", "run": "lingo"},
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
- `registry.profile` is unknown, or `ns` is missing when a registry is used;
- a required path key for the role is missing, or the role block is missing;
- `budget.itemsPerRun` is outside 1..3, or a model name is unknown;
- `gate.commit` (or a branch override) is outside `strict | normal | off`;
- for a scientist: any profile `kind` is outside `wsl | local | ssh`, an ssh profile
  has no `host`, a wsl profile has no `distro`, or a `policy` entry names no
  existing profile.

Unknown extra keys are allowed, for forward compatibility. `session_start` prints the
problems and stays silent otherwise.
