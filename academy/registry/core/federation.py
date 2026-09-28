"""Federation (part 2): load any namespace through its own profile.

A foreign id is resolved by loading its home with that home's profile, never by a
regex over the files. So ``s1:`` verdicts, runs and aliases resolve, and Unicode ids
(``GA-2T′``) pass. Stores are cached per (namespace, home) in ``CACHE``, the dict the
claims.py shim exposes as ``_cache`` (its tests clear it between cases).
"""
from __future__ import annotations

from pathlib import Path

from . import workspace

CACHE: dict = {}


def store(ns, home):
    """The namespace ``ns`` of ``home`` as a :class:`model.Store` (cached)."""
    from ..profiles import store_for   # late: the profiles import the core
    key = ("store", ns, str(Path(home).resolve()))
    if key not in CACHE:
        CACHE[key] = store_for(ns, Path(home))
    return CACHE[key]


def store_from(ns, repo):
    """The store of ``ns`` as seen from ``repo``, or None when its home is not beside it."""
    home = workspace.home_of(ns, repo)
    return store(ns, home) if home is not None else None


def reachable(repo):
    """{ns: store} for every namespace whose home is reachable from ``repo``."""
    out = {}
    for ns in workspace.namespaces():
        s = store_from(ns, repo)
        if s is not None:
            out[ns] = s
    return out


def split(qid):
    if ":" not in str(qid):
        return None, qid
    ns, rest = str(qid).split(":", 1)
    return ns, rest


def resolve(qid, repo):
    """``(state, record_or_None, detail)`` for a qualified id seen from ``repo``:
    ``ok`` (exact id), ``alias`` (resolves, but not by its id: detail names the id),
    ``missing``, or ``unchecked`` (its home is not beside ``repo``)."""
    ns, name = split(qid)
    if ns not in workspace.namespaces():
        return "missing", None, f"`{ns}:` is not a namespace of the workspace"
    s = store_from(ns, repo)
    if s is None:
        return "unchecked", None, f"the home repo of `{ns}:` is not beside this one"
    rid, exact = s.lookup(name)
    if rid is None:
        return "missing", None, ""
    rec = s.records[rid]
    return ("ok" if exact else "alias"), rec, rec.qid
