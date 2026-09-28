"""Where each namespace lives, and which profile reads it (federation, part 1).

The namespaces and their homes come from the academy's ``workspace.json`` (every
instance with an ``ns``); nothing here names a namespace except the fallback used when
no workspace file can be read at all.

**Which home serves a namespace, seen from a repo.** A registry resolves ids of other
namespaces in the home repos *beside it*, as claims.py always did ("a link into a home
repo that is not beside this one, on lingo say, is not checked"):

1. the repo itself, when it is that namespace's home;
2. when the repo is a registered home (its path is a ``home`` in workspace.json), the
   registered home of the other namespace;
3. otherwise a sibling directory named like the other home, carrying the repo's own
   suffix first: from ``FlatSurfLab-academy`` (a worktree of ``FlatSurfLab``), the
   ``paper`` home is ``BilliardIllumination-academy`` if it exists, else
   ``BilliardIllumination``. A temp directory named ``FlatSurfLab`` (the tests) sees its
   temp siblings.

**Which namespace a repo is.** Its ``.claude/academy.json`` ``ns``; else the registered
home equal to it; else the registered home whose directory name is the repo's name or
a prefix of it followed by ``-`` (worktrees); else the layout.

**Which profile.** ``registry.profile`` of the home's academy.json (``lab``, ``paper``,
``s1``: the rule sets of docs/config.md), else the namespace's own name when it is one
of those, else ``lab``. The engine profile behind a rule set is ``fsl-claims`` for
``lab`` and ``paper`` and ``s1-kb`` for ``s1``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_ACADEMY = "C:/Work/Math/academy"

#: only when workspace.json cannot be read at all (a lab clone on a server)
FALLBACK_NAMESPACES = {"lab": "FlatSurfLab", "paper": "BilliardIllumination",
                       "s1": "Slope1illuminationResearch"}

#: rule set (academy.json registry.profile) -> engine profile
ENGINE_PROFILE = {"lab": "fsl-claims", "paper": "fsl-claims", "s1": "s1-kb"}

_ws_cache = {}


def academy_root() -> Path:
    env = os.environ.get("ACADEMY_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    # <academy>/academy/registry/core/workspace.py
    return here.parents[3]


def workspace_path():
    env = os.environ.get("ACADEMY_WORKSPACE")
    if env:
        return Path(env)
    for cand in (academy_root() / "workspace.json", Path(DEFAULT_ACADEMY) / "workspace.json"):
        if cand.is_file():
            return cand
    return None


def load_workspace():
    """The workspace dict, or None when there is none (read once per path and mtime)."""
    p = workspace_path()
    if p is None or not p.is_file():
        return None
    try:
        key = (str(p), p.stat().st_mtime)
    except OSError:
        return None
    if key not in _ws_cache:
        try:
            _ws_cache.clear()
            _ws_cache[key] = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None
    return _ws_cache[key]


def _norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p))).replace("\\", "/").rstrip("/")


def namespaces() -> dict:
    """{ns: {"home": Path or None, "name": home directory name, "instance": name}}."""
    ws = load_workspace()
    out = {}
    if ws:
        for name, inst in (ws.get("instances") or {}).items():
            ns = inst.get("ns")
            if ns and inst.get("home"):
                home = Path(inst["home"])
                out[ns] = {"home": home, "name": home.name, "instance": name}
    if not out:
        for ns, base in FALLBACK_NAMESPACES.items():
            out[ns] = {"home": None, "name": base, "instance": None}
    return out


def read_config(home):
    """The home's ``.claude/academy.json`` as a dict, or None."""
    p = Path(home) / ".claude" / "academy.json"
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def registered(repo):
    """The ns whose registered home is exactly ``repo``, else None."""
    r = _norm(repo)
    for ns, info in namespaces().items():
        if info["home"] is not None and _norm(info["home"]) == r:
            return ns
    return None


def _by_name(repo):
    """(ns, suffix) of the registered home whose directory name is repo's name or a
    ``-``-separated prefix of it; the longest name wins."""
    name, best = Path(repo).name, None
    for ns, info in namespaces().items():
        base = info["name"]
        if name == base or name.startswith(base + "-"):
            if best is None or len(base) > len(best[2]):
                best = (ns, name[len(base):], base)
    return (best[0], best[1]) if best else (None, "")


def repo_ns(repo):
    """The namespace whose home ``repo`` is, or None."""
    repo = Path(repo)
    cfg = read_config(repo)
    if cfg and isinstance(cfg.get("ns"), str) and cfg["ns"]:
        return cfg["ns"]
    ns = registered(repo)
    if ns:
        return ns
    ns, _ = _by_name(repo)
    if ns:
        return ns
    return sniff_ns(repo)


def sniff_ns(repo):
    """Last resort: the namespace from the layout of the repo."""
    repo = Path(repo)
    if (repo / "tools" / "kb.py").is_file() or (repo / "assumptions").is_dir()             or (repo / "objects" / "assumption").is_dir():
        for ns in namespaces():
            if rule_set(ns) == "s1":
                return ns
    claims = repo / "claims"
    if claims.is_dir():
        subs = sorted(d.name for d in claims.iterdir() if d.is_dir())
        if len(subs) == 1 and subs[0] in namespaces():
            return subs[0]
    return None


def home_name(ns):
    info = namespaces().get(ns)
    return info["name"] if info else ns


def home_of(ns, repo):
    """The home repo of namespace ``ns`` as seen from ``repo``, or None when it is not
    beside it (see the module docstring)."""
    repo = Path(repo)
    info = namespaces().get(ns)
    if info is None:
        return None
    if repo_ns(repo) == ns:
        return repo
    if registered(repo) and info["home"] is not None:
        return info["home"] if info["home"].exists() else None
    _, suffix = _by_name(repo)
    cands = ([repo.parent / (info["name"] + suffix)] if suffix else []) + \
        [repo.parent / info["name"]]
    for c in cands:
        if c.exists():
            return c
    return None


def instance_home(instance, repo=None):
    """The home of workspace instance ``instance`` (``expert@ts``: instances with no
    namespace too) as seen from ``repo``, or None when workspace.json does not name it
    or no candidate exists. As for ``home_of``: the sibling carrying ``repo``'s worktree
    suffix first, then the registered home, then a sibling of the same name."""
    ws = load_workspace()
    info = ((ws or {}).get("instances") or {}).get(instance) or {}
    if not info.get("home"):
        return None
    home = Path(info["home"])
    cands = []
    if repo is not None:
        repo = Path(repo)
        _, suffix = _by_name(repo)
        if suffix:
            cands.append(repo.parent / (home.name + suffix))
    cands.append(home)
    if repo is not None:
        cands.append(Path(repo).parent / home.name)
    return next((c for c in cands if c.exists()), None)


def instances_of_role(role):
    """The workspace instance names whose role is ``role``."""
    ws = load_workspace()
    return [n for n, i in ((ws or {}).get("instances") or {}).items()
            if (i or {}).get("role") == role]


def rule_set(ns, home=None):
    """The rule set (``lab``, ``paper``, ``s1``) of namespace ``ns``."""
    if home is not None:
        cfg = read_config(home)
        prof = ((cfg or {}).get("registry") or {}).get("profile")
        if prof in ENGINE_PROFILE:
            return prof
    return ns if ns in ENGINE_PROFILE else "lab"


def engine_profile(ns, home=None):
    return ENGINE_PROFILE[rule_set(ns, home)]
