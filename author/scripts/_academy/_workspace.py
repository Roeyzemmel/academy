"""``workspace.json`` (the instance map) and what hangs off it: the workspace's
environment variables, the human, model tiers and the graders' primaries, agent files.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import json
import os
import re

from ._base import (
    BOARD_BACKENDS, ConfigError, HUMAN, PLUGINS, RE_INSTANCE, ROLES, _norm, _same_file,
    env_home_name, repo_root)
from ._config import (
    DEFAULT_MIN_TIER, DEFAULT_MODEL_TIERS, DEFAULT_NAMED_PRIMARIES, DEFAULT_PRIMARY_MODELS,
    MODEL_RANK, TIERS, VERSIONLESS, _read_json)

_WS_VAR = re.compile(r"^ACADEMY_WS__(.+?)__(.+)$")


def resolve_workspace_env(environ=None, etc="/etc/environment", cwd=None):
    """Make the unprefixed ``ACADEMY_*`` variables of *one* workspace visible.

    A workspace's bootstrap exports its variables twice: unprefixed into the
    ``.claude/settings.local.json`` of its own root and homes (sessions opened there),
    and tagged ``ACADEMY_WS__<TAG>__<NAME>`` into the machine-wide places (user settings,
    /etc/environment, shell rc files, the Windows registry), where several workspaces
    must coexist. A process that has no unprefixed ``ACADEMY_WORKSPACE`` (a plugin's MCP
    server started by a cloud harness outside any workspace) gets them here from the
    tagged set of one workspace: the one named by ``ACADEMY_WORKSPACE_TAG``, else the
    one whose root or homes contain ``cwd`` (``$CLAUDE_PROJECT_DIR``), else the only one.
    Variables already set win. Returns the chosen tag, or None (with the candidate tags
    in ``WORKSPACE_TAGS`` when the choice is ambiguous)."""
    global WORKSPACE_TAGS
    env = os.environ if environ is None else environ
    pool = {}
    try:
        with open(etc, encoding="utf-8") as fh:
            for ln in fh.read().splitlines():
                k, sep, v = ln.partition("=")
                k = k.strip()
                if sep and k.startswith("ACADEMY_"):
                    pool[k] = v.strip().strip("\"'")
    except OSError:
        pass
    pool.update((k, v) for k, v in env.items() if k.startswith("ACADEMY_"))
    WORKSPACE_TAGS = []
    if "ACADEMY_WORKSPACE" in pool:
        chosen = None           # a per-directory (unprefixed) set is in force
    else:
        tags = {}
        for k, v in pool.items():
            m = _WS_VAR.match(k)
            if m:
                tags.setdefault(m.group(1), {})[m.group(2)] = v
        tags = {t: d for t, d in tags.items() if "WORKSPACE" in d}
        want = pool.get("ACADEMY_WORKSPACE_TAG")
        chosen = want if want in tags else None
        if chosen is None and want is None:
            here = os.path.realpath(cwd or env.get("CLAUDE_PROJECT_DIR") or os.getcwd())

            def inside(tag):
                d = tags[tag]
                paths = [os.path.dirname(d["WORKSPACE"]), d.get("BOARD", "")] + \
                        [v for k, v in d.items() if k.startswith("HOME_")]
                return any(p and (here == os.path.realpath(p) or
                                  here.startswith(os.path.realpath(p) + os.sep))
                           for p in paths)
            hits = [t for t in tags if inside(t)]
            pick = hits if hits else list(tags)
            if len(pick) == 1:
                chosen = pick[0]
            else:
                WORKSPACE_TAGS = sorted(pick)
        if chosen is not None:
            for name, v in tags[chosen].items():
                pool.setdefault("ACADEMY_" + name, v)
    for k, v in pool.items():
        if not _WS_VAR.match(k) and k not in env:
            env[k] = v
    return chosen


WORKSPACE_TAGS = []
resolve_workspace_env()


def load_workspace(path=None):
    """Load workspace.json: ``{"instances": {...}, "board": ..., "human": {...}}``.

    Lookup order: ``path``; ``$ACADEMY_WORKSPACE``; ``<repo_root()>/workspace.json``;
    ``<repo_root()>/../workspace.json`` (the academy checked out inside the workspace).
    ``$ACADEMY_BOARD`` and ``$ACADEMY_HOME_<INSTANCE>`` override the file's ``board`` and
    instance homes, but only for the file ``$ACADEMY_ENV_WORKSPACE`` names (the one the
    workspace bootstrap derived them from), never for a fixture. Raises ConfigError if none is readable or the file is malformed.
    """
    candidates = [path, os.environ.get("ACADEMY_WORKSPACE"),
                  os.path.join(repo_root(), "workspace.json"),
                  os.path.join(repo_root(), os.pardir, "workspace.json")]
    chosen = next((c for c in candidates if c and os.path.isfile(c)), None)
    if not chosen:
        raise ConfigError("workspace.json not found" + (
            "; several workspaces are configured (%s): start the session inside one of them "
            "or set ACADEMY_WORKSPACE_TAG" % ", ".join(WORKSPACE_TAGS) if WORKSPACE_TAGS else ""))
    ws = _read_json(chosen)
    if not isinstance(ws, dict) or not isinstance(ws.get("instances"), dict):
        raise ConfigError("%s: 'instances' object missing" % chosen)
    # ``board`` is a path (the file board) or {"path", "backend": files|github, ...}; the
    # path stays in ws["board"] (packets and deep-dives are files either way), the rest in
    # ws["board_config"] (see open_store)
    if isinstance(ws.get("board"), dict):
        ws["board_config"] = dict(ws["board"])
        ws["board"] = ws["board_config"].get("path")
    else:
        ws["board_config"] = {}
    if ws["board_config"].get("backend", "files") not in BOARD_BACKENDS:
        raise ConfigError("%s: board.backend must be one of %s" % (chosen,
                                                                   ", ".join(BOARD_BACKENDS)))
    if _same_file(chosen, os.environ.get("ACADEMY_ENV_WORKSPACE")):
        if os.environ.get("ACADEMY_BOARD"):
            ws["board"] = os.environ["ACADEMY_BOARD"]
        for name, inst in ws["instances"].items():
            if isinstance(inst, dict) and os.environ.get(env_home_name(name)):
                inst["home"] = os.environ[env_home_name(name)]
    if not isinstance(ws.get("board"), str) or not ws["board"]:
        raise ConfigError("%s: 'board' path missing" % chosen)
    for name, inst in ws["instances"].items():
        if not RE_INSTANCE.match(name):
            raise ConfigError("%s: bad instance name %r" % (chosen, name))
        if not isinstance(inst, dict) or inst.get("role") != name.split("@", 1)[0]:
            raise ConfigError("%s: instance %r: role must match its name" % (chosen, name))
        if not inst.get("home") or not inst.get("domains"):
            raise ConfigError("%s: instance %r needs home and domains" % (chosen, name))
    seen = {}
    for name, inst in ws["instances"].items():
        key = (inst["role"], _norm(inst["home"]))
        if key in seen:
            raise ConfigError("%s: instances %r and %r have the same role and home; "
                              "an (role, home) pair is one instance" % (chosen, seen[key], name))
        seen[key] = name
    human = ws.get("human") if isinstance(ws.get("human"), dict) else {}
    human.setdefault("name", "human")
    human.setdefault("login", (ws["board_config"].get("assignee") or None))
    ws["human"] = human
    problems = model_problems(ws)
    if problems:
        raise ConfigError("%s: %s" % (chosen, "; ".join(problems)))
    ws["models"] = dict(ws.get("models") or {}, tiers=model_tiers(ws))
    grading = ws.get("grading") if isinstance(ws.get("grading"), dict) else {}
    # the file's primaryModels are named primaries; the loaded list is the effective one,
    # the named ones followed by the floor's (grading_primaries)
    grading["minTier"] = grading.get("minTier") or DEFAULT_MIN_TIER
    grading["primaryModels"] = list(grading_primaries(ws["models"]["tiers"], grading))
    if not grading["primaryModels"]:
        raise ConfigError("%s: grading has no primary model: grading.primaryModels is empty "
                          "and grading.minTier grants none (docs/config.md, \"models\")"
                          % chosen)
    ws["grading"] = grading
    if ws.get("plugins") is None:
        ws["plugins"] = derived_plugins(ws)
    elif not (isinstance(ws["plugins"], list) and all(isinstance(p, str) for p in ws["plugins"])):
        raise ConfigError("%s: plugins must be a list of plugin names" % chosen)
    ws["_path"] = os.path.abspath(chosen).replace("\\", "/")
    return ws


def _marketplace_domains():
    """{domain pack name: plugin name} from the academy's marketplace.json (a pack's
    ``source`` is ``./domains/<pack>``); empty when the file cannot be read."""
    path = os.path.join(repo_root(), ".claude-plugin", "marketplace.json")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            entries = json.load(fh).get("plugins") or []
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for e in entries:
        src = str((e or {}).get("source") or "").replace("\\", "/").rstrip("/")
        if src.startswith("./domains/") and e.get("name"):
            out[src.rsplit("/", 1)[1]] = e["name"]
    return out


def derived_plugins(ws):
    """The plugins a workspace needs when it names none (``plugins`` in workspace.json):
    the base plugin, the role plugins of its instances, and the plugin of every domain
    pack its instances name (the marketplace's name for ``domains/<pack>``, else the
    pack name)."""
    insts = [i for i in (ws.get("instances") or {}).values() if isinstance(i, dict)]
    roles = {i.get("role") for i in insts}
    packs = _marketplace_domains()
    out = ["academy"] + [r for r in ROLES if r in roles]
    for inst in insts:
        for d in inst.get("domains") or []:
            name = packs.get(d, d)
            if name not in out:
                out.append(name)
    return out


def _workspace_or_none(ws=None):
    if ws is not None:
        return ws
    try:
        return load_workspace()
    except ConfigError:
        return None


def human_name(ws=None):
    """The human's display name (workspace.json ``human.name``), else 'the human'."""
    ws = _workspace_or_none(ws)
    name = ((ws or {}).get("human") or {}).get("name")
    return name if name and name != HUMAN else "the human"


def human_login(ws=None):
    """The human's GitHub login: ``human.login``, else ``board.assignee``, else None."""
    ws = _workspace_or_none(ws)
    if not ws:
        return None
    login = (ws.get("human") or {}).get("login")
    return login or (ws.get("board_config") or {}).get("assignee") or None


def primary_models(ws=None):
    """The grading primaries as a tuple of model labels: the named
    ``grading.primaryModels`` and the floor's (``grading_primaries``), for a loaded or a
    raw workspace dict alike; ``DEFAULT_PRIMARY_MODELS`` when there is no workspace."""
    ws = _workspace_or_none(ws)
    if ws is None:
        return DEFAULT_PRIMARY_MODELS
    # the same answer for a loaded and a raw workspace dict: the named primaries plus the
    # floor's, recomputed (idempotent on a loaded dict, whose list is already effective)
    grading = ws.get("grading") if isinstance(ws.get("grading"), dict) else {}
    return grading_primaries(model_tiers(ws), grading)


# ----------------------------------------------------------------------------
# Model tiers (docs/config.md, "models"): an agent file declares ``tier:``; the
# workspace maps tiers to models; the graders' floor is ``grading.minTier``.
# ----------------------------------------------------------------------------

RE_OPUS_55 = re.compile(r"opus-?5-5(?![0-9])")
RE_MODEL_ID = re.compile(r"^claude-[a-z0-9][a-z0-9.-]*(\[[a-z0-9]+\])?$")


def model_label(name):
    """A model name reduced to the label the roster rules use: ``fable``, ``opus-5.5``,
    or the family (``opus``, ``sonnet``, ``haiku``) of any other model; the name itself
    (lower-cased) when it names no known family, '' when empty. ``claude-opus-5-5[1m]``,
    ``Opus 5.5`` and ``opus-5.5`` all read as ``opus-5.5``; a bare ``opus`` names no
    version and reads as ``opus``. (The one copy: researcher ``_researcher.py`` and
    expert ``decision_table.py`` call it.)"""
    n = str(name or "").strip().lower()
    if not n:
        return ""
    k = re.sub(r"[\s_.]+", "-", n)
    if "fable" in k:
        return "fable"
    if RE_OPUS_55.search(k):
        return "opus-5.5"
    for fam in ("opus", "sonnet", "haiku"):
        if fam in k:
            return fam
    return n


def model_family(name):
    """The family (a ``MODEL_RANK`` key) a model alias or id names, or None."""
    n = str(name or "").lower()
    for fam in sorted(MODEL_RANK, key=lambda f: -MODEL_RANK[f]):
        if fam in n:
            return fam
    return None


def launch_model(value):
    """The Agent-tool ``model`` value (an alias) for a tier's model: the alias itself, or
    the family a full id names (``claude-opus-5-5`` -> ``opus``)."""
    return model_family(value) or str(value or "")


def tier_at_least(tier, floor):
    """True when ``tier`` is ``floor`` or heavier (both in ``TIERS``)."""
    return TIERS.index(tier) >= TIERS.index(floor)


def _model_value_ok(value):
    if not isinstance(value, str) or not value:
        return False
    v = value.strip().lower()
    return v in MODEL_RANK or bool(RE_MODEL_ID.match(v) and model_family(v))


def model_problems(ws):
    """Problems with a workspace's ``models`` and ``grading`` keys (empty when valid):
    ``models.tiers`` maps tiers of ``TIERS`` to an alias (``haiku``, ``sonnet``,
    ``opus``, ``fable``) or a ``claude-...`` model id, no tier lighter than the one below
    it; ``grading.minTier`` is a tier or ``none``; ``grading.primaryModels`` a list of
    model names."""
    out = []
    models = (ws or {}).get("models")
    tiers = {}
    if models is not None:
        if not isinstance(models, dict):
            out.append("models must be an object with 'tiers'")
        else:
            tiers = models.get("tiers")
            if tiers is None:
                tiers = {}
            elif not isinstance(tiers, dict):
                out.append("models.tiers must map tiers (%s) to models" % ", ".join(TIERS))
                tiers = {}
    for tier, value in tiers.items():
        if tier not in TIERS:
            out.append("models.tiers: unknown tier %r (tiers: %s)" % (tier, ", ".join(TIERS)))
        elif not _model_value_ok(value):
            out.append("models.tiers.%s: %r is not a model (an alias %s, or a claude-... id)"
                       % (tier, value, "/".join(sorted(MODEL_RANK, key=MODEL_RANK.get))))
    if not out:
        merged = dict(DEFAULT_MODEL_TIERS, **tiers)
        ranks = [MODEL_RANK[model_family(merged[t])] for t in TIERS]
        for i in range(1, len(TIERS)):
            if ranks[i] < ranks[i - 1]:
                out.append("models.tiers: %s (%s) is lighter than %s (%s)"
                           % (TIERS[i], merged[TIERS[i]], TIERS[i - 1], merged[TIERS[i - 1]]))
    grading = (ws or {}).get("grading")
    if isinstance(grading, dict):
        floor = grading.get("minTier")
        if floor is not None and floor not in TIERS + ("none",):
            out.append("grading.minTier must be one of %s or none" % ", ".join(TIERS))
        prim = grading.get("primaryModels")
        if prim is not None and not (isinstance(prim, list)
                                     and all(isinstance(m, str) and m for m in prim)):
            out.append("grading.primaryModels must be a list of model names")
    return out


def model_tiers(ws=None):
    """The workspace's tier map: ``models.tiers`` over ``DEFAULT_MODEL_TIERS``. With no
    argument the workspace is loaded; the default when there is none."""
    ws = _workspace_or_none(ws)
    tiers = (((ws or {}).get("models") or {}).get("tiers")) or {}
    return dict(DEFAULT_MODEL_TIERS, **{k: v for k, v in tiers.items() if k in TIERS})


def tier_model(tier, ws=None):
    """The model the workspace maps ``tier`` to."""
    return model_tiers(ws)[tier]


def grading_primaries(tiers, grading):
    """The effective grading primaries, as labels (``model_label``): the named
    ``grading.primaryModels`` (default ``DEFAULT_NAMED_PRIMARIES``), then the label of each tier's model from
    ``grading.minTier`` up. A tier whose model names no version (``VERSIONLESS``: a bare
    alias, or an id ``model_label`` cannot version yet) grants nothing."""
    named = grading.get("primaryModels")
    out = []
    for m in (DEFAULT_NAMED_PRIMARIES if named is None else named):
        lab = model_label(m)
        if lab and lab not in out:
            out.append(lab)
    floor = grading.get("minTier") or DEFAULT_MIN_TIER
    if floor == "none":
        return tuple(out)
    for tier in TIERS[TIERS.index(floor):]:
        lab = model_label(tiers[tier])
        if lab and lab not in VERSIONLESS and lab not in out:
            out.append(lab)
    return tuple(out)


def model_warnings(ws):
    """The floor tiers (``grading.minTier`` up) whose model names no version, and so give
    no grading authority: a bare alias (``large: opus``) or an id ``model_label`` cannot
    version yet. Name large/max by a versioned id (``claude-opus-5-5``). Printed by the
    bootstrap, the session start and ``models.py check``; not an error."""
    grading = (ws or {}).get("grading") or {}
    floor = grading.get("minTier") or DEFAULT_MIN_TIER
    if floor not in TIERS:
        return []
    tiers = model_tiers(ws or {})
    out = []
    for tier in TIERS[TIERS.index(floor):]:
        if model_label(tiers[tier]) in VERSIONLESS:
            out.append("tier %s: models.tiers.%s = %s names no version, so graders run on "
                       "it count for nothing (grading.minTier %s): name a versioned id "
                       "such as claude-opus-5-5 (docs/config.md, \"models\")"
                       % (tier, tier, tiers[tier], floor))
    return out


RE_FM_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$")


def read_agent_frontmatter(path):
    """The top-level scalar keys of an agent file's frontmatter (``name``, ``model``,
    ``tier``, ``fallback``, ...), as strings; {} when it has none."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = RE_FM_LINE.match(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def agent_files(repo=None):
    """``{"<plugin>:<name>": path}`` for every agent file of the academy plugins."""
    repo = repo or repo_root()
    out = {}
    for plugin in PLUGINS:
        d = os.path.join(repo, plugin, "agents")
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".md"):
                out["%s:%s" % (plugin, fn[:-3])] = os.path.join(d, fn)
    return out


def resolve_agent(agent, ws=None, repo=None):
    """agent -> tier -> model for the workspace: ``{agent, tier, model, launch,
    frontmatter, override, path}``. ``agent`` is ``<plugin>:<name>`` or a bare name;
    ``launch`` is the Agent-tool ``model`` value and ``override`` says whether it differs
    from the file's ``model:`` (the launcher passes it then). ConfigError when the agent
    is unknown or its file declares no valid tier."""
    files = agent_files(repo)
    key = agent if agent in files else None
    if key is None and ":" not in agent:
        hits = [k for k in files if k.split(":", 1)[1] == agent]
        key = hits[0] if len(hits) == 1 else None
    if key is None:
        raise ConfigError("unknown agent %r" % agent)
    fm = read_agent_frontmatter(files[key])
    tier = fm.get("tier")
    if tier not in TIERS:
        raise ConfigError("%s: tier %r is not one of %s" % (files[key], tier, ", ".join(TIERS)))
    model = tier_model(tier, ws if ws is not None else _workspace_or_none(None))
    launch = launch_model(model)
    return {"agent": key, "tier": tier, "model": model, "launch": launch,
            "frontmatter": fm.get("model"), "override": launch != fm.get("model"),
            "path": files[key].replace("\\", "/")}
