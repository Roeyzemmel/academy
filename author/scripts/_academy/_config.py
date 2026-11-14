"""A home's ``.claude/academy.json`` (docs/config.md): defaults, validation, loading,
the commit-gate mode, and an Author home's tex conventions and path sets.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import fnmatch
import json
import os
import re

from ._base import (
    CONFIG_REL, ConfigError, MODELS, RE_INSTANCE, ROLES, SCHEMA_VERSION, _norm, _rel_to)

# ----------------------------------------------------------------------------
# Config and workspace
# ----------------------------------------------------------------------------

#: defaults merged under every config (see docs/config.md)
CONFIG_DEFAULTS = {
    "budget": {"itemsPerRun": 3, "serial": True, "orchestratorModel": "sonnet",
               "maxModel": "fable", "ticketDefault": {"runs": 1}},
    "gate": {"commit": "normal", "build": True, "baseline": None, "branches": {}},
    "paths": {},
}

#: path keys each role must define in ``paths`` (docs/config.md). Keys not listed are
#: never rejected: an old Author config that still carries ``paths.roadmap`` (the
#: roadmap was dropped, the board is the only queue) validates and the key is ignored.
REQUIRED_PATHS = {
    "author": ("tex", "bib", "drafts", "agenda", "records", "views"),
    "researcher": ("objects", "proofs", "journal", "audits", "records", "views"),
    "expert": ("index", "cards", "ledgers", "reviews", "hot", "cache", "views"),
    "scientist": ("package", "experiments", "results", "queue", "records", "views"),
}

REGISTRY_PROFILES = ("paper", "notebook", "lab", "none")
#: older rule-set names, still accepted in ``registry.profile`` (docs/config.md)
REGISTRY_PROFILE_ALIASES = {"s1": "notebook", "s1-kb": "notebook"}


def registry_rule_set(name):
    """``registry.profile`` mapped to its rule set (``paper``, ``notebook``, ``lab``,
    ``none``), an old alias resolved; None when it names none."""
    name = REGISTRY_PROFILE_ALIASES.get(name, name)
    return name if name in REGISTRY_PROFILES else None


#: the model tiers an agent file declares (``tier:``), lightest first (docs/config.md,
#: "models"); workspace.json ``models.tiers`` maps each to a model
TIERS = ("base", "medium", "large", "max")
#: the academy's tier map, under a workspace's ``models.tiers``; an agent file's
#: ``model:`` is the Agent-tool alias of its tier here (``launch_model``)
DEFAULT_MODEL_TIERS = {"base": "haiku", "medium": "sonnet", "large": "claude-opus-5-5",
                       "max": "claude-opus-5-5"}
#: the model families, lightest first (an Agent-tool / frontmatter alias each)
MODEL_RANK = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}
#: aliases that name no version (a bare family): no grading authority from a tier
VERSIONLESS = ("haiku", "sonnet", "opus")
#: the graders' tier floor when workspace.json sets no ``grading.minTier``
DEFAULT_MIN_TIER = "large"
#: named primaries added to the floor's when workspace.json sets no ``grading.primaryModels``
DEFAULT_NAMED_PRIMARIES = ("fable",)
#: the grading primaries of a workspace that configures neither (the named ones plus the
#: label of the default map's floor models); a test keeps the two in step
DEFAULT_PRIMARY_MODELS = ("fable", "opus-5.5")
#: where the rigor review's checklist lives in a home, unless ``paths.verifyChecklist``
DEFAULT_VERIFY_CHECKLIST = ".claude/rules/verification-checklist.md"
ENV_KINDS = ("wsl", "local", "ssh")
POLICY_KEYS = ("probe", "test", "run")
COMMIT_MODES = ("strict", "normal", "warn", "off")


def _deep_merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except OSError as exc:
        raise ConfigError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise ConfigError("invalid JSON in %s: %s" % (path, exc))


def validate_config(config):
    """Return a list of human-readable problems with a loaded academy.json (empty if valid)."""
    probs = []
    if not isinstance(config, dict):
        return ["config is not a JSON object"]
    if config.get("schema") != SCHEMA_VERSION:
        probs.append("schema must be %d" % SCHEMA_VERSION)
    role = config.get("role")
    if role not in ROLES:
        probs.append("role must be one of %s" % ", ".join(ROLES))
    inst = config.get("instance")
    if not isinstance(inst, str) or not RE_INSTANCE.match(inst):
        probs.append("instance must look like '<role>@<name>' (lower-case, digits, '-')")
    elif role in ROLES and inst.split("@", 1)[0] != role:
        probs.append("instance %r does not start with role %r" % (inst, role))
    doms = config.get("domains")
    if not (isinstance(doms, list) and doms and all(isinstance(d, str) and d for d in doms)):
        probs.append("domains must be a non-empty list of pack names")
    reg = config.get("registry")
    if not isinstance(reg, dict) or registry_rule_set(reg.get("profile")) is None:
        probs.append("registry.profile must be one of %s" % ", ".join(REGISTRY_PROFILES))
    elif reg.get("profile") != "none" and not config.get("ns"):
        probs.append("ns is required when registry.profile is not 'none'")
    else:
        for key in ("prefixes", "assumptionGroups"):
            if reg.get(key) is not None and not isinstance(reg[key], (dict, list)):
                probs.append("registry.%s must be a map prefix -> name (or a list)" % key)
    paths = config.get("paths")
    if not isinstance(paths, dict):
        probs.append("paths must be an object")
    elif role in REQUIRED_PATHS:
        for key in REQUIRED_PATHS[role]:
            if key not in paths:
                probs.append("paths.%s is required for role %s" % (key, role))
    budget = config.get("budget", {})
    n = budget.get("itemsPerRun") if isinstance(budget, dict) else None
    # out of range is not an error: the inbox clamps it to 1..3 (inbox_core.clamp). Only a
    # value that is no number at all is a problem (2026-11-14: a 5 in a home's config
    # stopped its inbox with exit 2)
    if n is not None and (isinstance(n, bool) or not isinstance(n, int)):
        probs.append("budget.itemsPerRun must be an integer (it is clamped to 1..3)")
    for key in ("orchestratorModel", "maxModel"):
        if isinstance(budget, dict) and budget.get(key) not in MODELS:
            probs.append("budget.%s must be one of %s" % (key, ", ".join(MODELS)))
    gate = config.get("gate", {})
    if isinstance(gate, dict):
        if gate.get("commit") not in COMMIT_MODES:
            probs.append("gate.commit must be one of %s" % ", ".join(COMMIT_MODES))
        for br, over in (gate.get("branches") or {}).items():
            if not isinstance(over, dict) or over.get("commit", "normal") not in COMMIT_MODES:
                probs.append("gate.branches.%s.commit must be one of %s"
                             % (br, ", ".join(COMMIT_MODES)))
    if role in ROLES and not isinstance(config.get(role), dict):
        probs.append("a '%s' block is required for role %s" % (role, role))
    if role == "author" and isinstance(config.get("author"), dict):
        probs.extend(validate_author(config["author"]))
    if role == "scientist" and isinstance(config.get("scientist"), dict):
        sci = config["scientist"]
        envs = sci.get("envs")
        if not isinstance(envs, dict) or not envs:
            probs.append("scientist.envs must name at least one profile")
            envs = {}
        for name, prof in envs.items():
            kind = prof.get("kind") if isinstance(prof, dict) else None
            if isinstance(prof, dict) and "worker" in prof and kind in (None, "ssh"):
                # a remote worker of the workspace (workspace.json compute.workers),
                # resolved by the Scientist's env.py (docs/config.md, "compute")
                if not (isinstance(prof["worker"], str) and prof["worker"]):
                    probs.append("scientist.envs.%s.worker must name a worker of the "
                                 "workspace's compute.workers" % name)
                continue
            if kind not in ENV_KINDS:
                probs.append("scientist.envs.%s.kind must be one of %s"
                             % (name, ", ".join(ENV_KINDS)))
            elif kind == "ssh" and not prof.get("host"):
                probs.append("scientist.envs.%s: kind ssh needs host" % name)
            elif kind == "wsl" and not prof.get("distro"):
                probs.append("scientist.envs.%s: kind wsl needs distro" % name)
        pol = sci.get("policy")
        if not isinstance(pol, dict):
            probs.append("scientist.policy must map probe/test/run to profiles")
        else:
            for key in POLICY_KEYS:
                if pol.get(key) not in envs:
                    probs.append("scientist.policy.%s must name a profile in scientist.envs"
                                 % key)
    return probs


def load_config(home):
    """Load ``<home>/.claude/academy.json`` with defaults merged in.

    Adds ``_home`` (absolute path of the home, '/' separators). Raises ConfigError
    if the file is missing, not JSON, or fails ``validate_config``.
    """
    if not home:
        raise ConfigError("no academy home")
    path = os.path.join(str(home), CONFIG_REL)
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise ConfigError("%s is not a JSON object" % path)
    cfg = _deep_merge(CONFIG_DEFAULTS, raw)
    probs = validate_config(cfg)
    if probs:
        raise ConfigError("%s: %s" % (path, "; ".join(probs)))
    cfg["_home"] = os.path.abspath(str(home)).replace("\\", "/")
    return cfg


def default_ticket_budget(config):
    """The budget a new ticket gets when its sender gives none: ``{"runs": n}``.

    ``n`` is ``budget.ticketDefault.runs`` of ``config`` (a loaded academy.json, or
    None), else 1. A ``max_model`` there (an older convention) is ignored: the model
    an agent runs on is its agent file's, and ``budget.max_model`` on a ticket is only
    an advisory note its sender may add (docs/protocol.md section 3).
    """
    b = ((config or {}).get("budget") or {}).get("ticketDefault") or {}
    runs = b.get("runs") if isinstance(b, dict) else None
    return {"runs": runs if isinstance(runs, int) and runs >= 1 else 1}


def gate_mode(config, branch=None):
    """The effective commit-gate mode for ``branch`` ('strict'|'normal'|'warn'|'off').

    ``gate.branches`` maps a branch name or a glob (``fnmatch``, case-sensitive; ``*``
    also matches ``/``) to ``{"commit": mode}``. An exact-name key wins; otherwise the
    first glob key, in the map's order, that matches ``branch``; otherwise
    ``gate.commit`` (default 'normal'). Any configured string passes through.
    """
    gate = config.get("gate") or {}
    mode = gate.get("commit", "normal")
    if not branch:
        return mode
    branches = gate.get("branches") or {}
    over = branches.get(branch)
    if isinstance(over, dict) and "commit" in over:
        return over["commit"]
    for pattern, over in branches.items():
        if pattern == branch or not isinstance(over, dict) or "commit" not in over:
            continue
        if fnmatch.fnmatchcase(branch, str(pattern)):
            return over["commit"]
    return mode


#: the keys of ``author.provenance`` and their defaults (docs/config.md, role blocks)
PROVENANCE_DEFAULTS = {"env": "added", "command": "\\Added",
                       "kinds": ["claim", "assumption", "lead-proof"], "removedBy": "human"}


def author_provenance(config):
    """An Author home's provenance marker (``author.provenance``) with defaults filled
    in, or None when the home sets none (no marker is used)."""
    val = ((config or {}).get("author") or {}).get("provenance")
    if not isinstance(val, dict) or val.get("enabled") is False:
        return None
    out = dict(PROVENANCE_DEFAULTS)
    out.update({k: v for k, v in val.items() if k != "enabled"})
    return out


# ----------------------------------------------------------------------------
# An Author home's tex conventions (docs/config.md, "author"): draft levels, preamble
# policy, labels, notes, figures, accepted BibTeX warnings, main results. The defaults
# reproduce the conventions every Author home had before they were configurable.
# ----------------------------------------------------------------------------

#: what a draft level means: proved or cited in full; not yet (blocks R1); not a claim
LEVEL_KINDS = ("established", "unestablished", "commentary")
PREAMBLE_POLICIES = ("propose", "locked", "free")

#: the default levels, as ``author.statusLevels`` would spell them
DEFAULT_STATUS_LEVELS = (
    {"name": "established", "env": None, "command": None, "colour": "black",
     "kind": "established", "statuses": ["proved"]},
    {"name": "sketch", "env": "sketch", "command": "\\Sketch", "colour": "blue",
     "kind": "unestablished", "statuses": ["sketch", "proved-modulo"]},
    {"name": "conjectural", "env": "conjectural", "command": "\\Conjectural",
     "colour": "red", "kind": "unestablished",
     "statuses": ["open", "conjectured", "supported"]},
    {"name": "meta", "env": "meta", "command": "\\Meta", "colour": "brown",
     "kind": "commentary", "statuses": []},
)

#: ``author`` tex keys other than the levels, with their defaults (``preamble.file``
#: None means ``author.main``)
AUTHOR_TEX_DEFAULTS = {
    "preamble": {"file": None, "end": "\\begin{document}", "policy": "propose",
                 "extraFiles": []},
    "labels": {"prefixes": ["thm", "lem", "prop", "cor", "defn", "eq", "sec", "fig"],
               "refCommand": "cref"},
    "notes": {"maxLines": 3},
    "figures": {"dir": "tikz", "include": "\\includestandalone"},
    "bib": {"acceptedWarnings": []},
    "mainResults": {"file": "sections/introduction.tex", "labels": []},
}

RE_LEVEL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _author_block(config_or_block):
    """The ``author`` block of a config, or the block itself when one is passed."""
    c = config_or_block if isinstance(config_or_block, dict) else {}
    if isinstance(c.get("author"), dict) and ("role" in c or "schema" in c):
        return c["author"]
    return c


def author_status_levels(config_or_block):
    """The home's draft levels: a list of ``{name, env, command, colour, kind,
    statuses}``, the established level first.

    ``author.statusLevels`` when set; otherwise derived from the older keys ``envs``
    (env -> level), ``colourCommands`` (macro -> level) and ``colours`` (level ->
    colour) with the default meanings: a level named like a default level takes its
    kind and statuses, any other level is commentary (it never blocked R1)."""
    a = _author_block(config_or_block)
    levels = a.get("statusLevels")
    if isinstance(levels, list) and levels:
        out = [dict(lv) for lv in levels if isinstance(lv, dict)]
        for lv in out:
            lv.setdefault("env", None)
            lv.setdefault("command", None)
            lv.setdefault("colour", None)
            lv.setdefault("statuses", [])
        out.sort(key=lambda lv: lv.get("kind") != "established")
        return out
    defaults = {lv["name"]: lv for lv in DEFAULT_STATUS_LEVELS}
    envs = a.get("envs") if isinstance(a.get("envs"), dict) else None
    cmds = a.get("colourCommands") if isinstance(a.get("colourCommands"), dict) else None
    colours = a.get("colours") if isinstance(a.get("colours"), dict) else {}
    if envs is None:
        envs = {lv["env"]: lv["name"] for lv in DEFAULT_STATUS_LEVELS if lv["env"]}
    if cmds is None:
        cmds = {lv["command"]: lv["name"] for lv in DEFAULT_STATUS_LEVELS if lv["command"]}
    names = []
    for name in list(envs.values()) + list(cmds.values()):
        if str(name) != "established" and str(name) not in names:
            names.append(str(name))
    est = defaults["established"]
    out = [dict(est, colour=colours.get("established", est["colour"]))]
    for name in names:
        base = defaults.get(name) or {"kind": "commentary", "statuses": [], "colour": None}
        out.append({"name": name,
                    "env": next((str(e) for e, n in envs.items() if str(n) == name), None),
                    "command": next((str(c) for c, n in cmds.items() if str(n) == name),
                                    None),
                    "colour": colours.get(name, base["colour"]),
                    "kind": base["kind"], "statuses": list(base["statuses"])})
    return out


def author_tex(config_or_block, key):
    """``author.<key>`` (one of ``AUTHOR_TEX_DEFAULTS``) with its defaults filled in."""
    a = _author_block(config_or_block)
    out = dict(AUTHOR_TEX_DEFAULTS[key])
    val = a.get(key)
    if isinstance(val, dict):
        out.update({k: v for k, v in val.items() if v is not None})
    if key == "preamble" and not out.get("file"):
        out["file"] = str(a.get("main") or "main.tex")
    return out


def _str_list(val):
    return isinstance(val, list) and all(isinstance(x, str) and x for x in val)


def validate_author(block):
    """Problems with the tex-convention keys of an ``author`` block (docs/config.md)."""
    probs = []
    levels = block.get("statusLevels")
    if levels is not None:
        if not (isinstance(levels, list) and levels
                and all(isinstance(lv, dict) for lv in levels)):
            probs.append("author.statusLevels must be a non-empty list of objects")
        else:
            seen, kinds = set(), []
            for i, lv in enumerate(levels):
                where = "author.statusLevels[%d]" % i
                name = lv.get("name")
                if not (isinstance(name, str) and RE_LEVEL_NAME.match(name)):
                    probs.append("%s.name must be a word (letters, digits, '-', '_')" % where)
                elif name in seen:
                    probs.append("%s.name %r is repeated" % (where, name))
                seen.add(name)
                kind = lv.get("kind")
                kinds.append(kind)
                if kind not in LEVEL_KINDS:
                    probs.append("%s.kind must be one of %s" % (where, ", ".join(LEVEL_KINDS)))
                for k in ("env", "command", "colour"):
                    if lv.get(k) is not None and not (isinstance(lv[k], str) and lv[k]):
                        probs.append("%s.%s must be a string or null" % (where, k))
                if kind == "established" and (lv.get("env") or lv.get("command")):
                    probs.append("%s: the established level is the uncoloured one "
                                 "(no env, no command)" % where)
                if kind in ("unestablished", "commentary") and not (lv.get("env")
                                                                   or lv.get("command")):
                    probs.append("%s: a %s level needs an env or a command" % (where, kind))
                if lv.get("statuses") is not None and not isinstance(lv["statuses"], list):
                    probs.append("%s.statuses must be a list of registry statuses" % where)
            if kinds.count("established") != 1:
                probs.append("author.statusLevels needs exactly one level of kind "
                             "established")
    for key in AUTHOR_TEX_DEFAULTS:
        if block.get(key) is not None and not isinstance(block[key], dict):
            probs.append("author.%s must be an object" % key)
    pre = block.get("preamble") if isinstance(block.get("preamble"), dict) else {}
    if pre.get("policy") is not None and pre["policy"] not in PREAMBLE_POLICIES:
        probs.append("author.preamble.policy must be one of %s" % ", ".join(PREAMBLE_POLICIES))
    for key, sub in (("preamble", "file"), ("preamble", "end"), ("labels", "refCommand"),
                     ("figures", "dir"), ("figures", "include"), ("mainResults", "file")):
        blk = block.get(key) if isinstance(block.get(key), dict) else {}
        if blk.get(sub) is not None and not (isinstance(blk[sub], str) and blk[sub]):
            probs.append("author.%s.%s must be a non-empty string" % (key, sub))
    for key, sub in (("preamble", "extraFiles"), ("labels", "prefixes"),
                     ("bib", "acceptedWarnings"), ("mainResults", "labels")):
        blk = block.get(key) if isinstance(block.get(key), dict) else {}
        if blk.get(sub) is not None and not _str_list(blk[sub]):
            probs.append("author.%s.%s must be a list of strings" % (key, sub))
    notes = block.get("notes") if isinstance(block.get("notes"), dict) else {}
    ml = notes.get("maxLines")
    if ml is not None and not (isinstance(ml, int) and not isinstance(ml, bool) and ml >= 1):
        probs.append("author.notes.maxLines must be a positive integer")
    return probs


def verify_checklist_path(config):
    """The home-relative path of the rigor review's checklist (``paths.verifyChecklist``)."""
    val = ((config or {}).get("paths") or {}).get("verifyChecklist")
    return val if isinstance(val, str) and val else DEFAULT_VERIFY_CHECKLIST


def instance_for_home(workspace, home):
    """The instance name whose ``home`` is ``home``, or None."""
    target = _norm(home)
    for name, inst in workspace.get("instances", {}).items():
        if _norm(inst.get("home", "")) == target:
            return name
    return None


def _glob_regex(pattern):
    """Translate a path glob ('**' any segments, '*' within a segment, '?' one char)."""
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE if os.name == "nt" else 0)


def _match_path(rel, pattern):
    pattern = pattern.replace("\\", "/").strip("/")
    if pattern in ("", "."):
        return True
    if any(c in pattern for c in "*?"):
        return _glob_regex(pattern).match(rel) is not None
    a, b = (rel.lower(), pattern.lower()) if os.name == "nt" else (rel, pattern)
    return a == b or a.startswith(b + "/")


def path_in_role(path, config, role):
    """Does ``path`` belong to ``role`` in this home?

    ``role`` is either
      * a role name (``config['role']``): True iff ``path`` lies inside the home;
        a different role name gives False, since a home has exactly one role;
      * a key of ``config['paths']`` (e.g. ``"tex"``, ``"views"``): True iff the
        path, taken relative to the home, matches one of that key's patterns.
        A pattern without glob characters matches the file itself or anything
        under it as a directory; ``*`` stays within a segment, ``**`` spans them.
    Relative ``path`` values are taken relative to the home. Unknown keys give False.
    """
    home = config.get("_home")
    if not home or not path:
        return False
    full = path if os.path.isabs(str(path)) else os.path.join(home, str(path))
    rel = _rel_to(home, full)
    if rel is None:
        return False
    if role in ROLES:
        return role == config.get("role")
    pats = (config.get("paths") or {}).get(role)
    if pats is None:
        return False
    if isinstance(pats, str):
        pats = [pats]
    return any(_match_path(rel, p) for p in pats)
