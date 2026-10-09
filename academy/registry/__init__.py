"""academy/registry: one engine for every claim registry (plan section 6; the merge
proposal <lab>/docs/design/2026-09-27-claim-registry-merge.md).

Layout:

* ``core/``: the dialect (``fm``, kb.py's strict parser and serializer), records and
  stores (``model``), homes and profiles from workspace.json (``workspace``),
  federation, the status projection, the cross-namespace graph, line-preserving edits
  (``edit``) and the grounds rules of plan section 8 (``grounds``);
* ``profiles/``: ``fsl-claims`` (``fsl.py``: lab and paper, the lab's claims.py)
  and ``s1-kb`` (``s1kb.py``: the notebook rule set, the first notebook's kb.py);
* ``cli.py``: ``py -m registry`` (run from ``academy/academy``, or with that directory
  on ``PYTHONPATH``), the union of both command lines, dispatched by the repo's profile;
* ``requote.py``: the one-time R2 requote with its data-equality report;
* ``core/schema.py``: the academy object schema (schema v2, R5): one field set, one
  status vocabulary, the lifecycle, evidence and history rows, and the generic rules
  every profile applies before its home rules; both profiles read v1 and v2 records.
  (The one-time R5 and R6 migrations, ``migrate_v2.py`` and ``migrate_r6.py``, moved out
  of the marketplace with their goldens once every home had run them.)

The command line is ``academy/scripts/registry.py`` (the lab's ``scripts/claims.py`` and
the first notebook's ``tools/kb.py`` shims were removed 2026-09-28). Standard library only.
"""
from pathlib import Path

from .core import federation, workspace


def ns_of(repo):
    return workspace.repo_ns(Path(repo))


def profile_module(repo):
    """The profile module (``fsl`` or ``s1kb``) serving ``repo``'s own namespace."""
    from .profiles import module
    ns = ns_of(repo)
    return module(workspace.engine_profile(ns, Path(repo)) if ns else "fsl-claims")


def store(ns, repo):
    """Namespace ``ns`` as seen from ``repo`` (None when its home is not beside it)."""
    return federation.store_from(ns, Path(repo))


def clear_cache():
    federation.CACHE.clear()


def hook_policy(home, ns=None):
    """What the record-edit hook does in ``home``: ``{"ns", "profile", "watched",
    "build"}``. ``watched`` are the directories (relative, ``/``) whose ``.md`` files are
    records of the home's profile; ``build`` says whether an edit there must be followed
    by a blocking ``build`` (the s1-kb profile asks for it, as the first notebook's kb_hook did; a
    home's academy.json may turn it off with ``registry.build: false``)."""
    home = Path(home)
    ns = ns or workspace.repo_ns(home)
    prof = workspace.engine_profile(ns, home) if ns else "fsl-claims"
    cfg = workspace.read_config(home) or {}
    reg = cfg.get("registry") or {}
    if prof == "s1-kb":
        from .profiles import s1kb
        watched = [d for d, _, _ in s1kb.entity_dirs(home)]  # objects/<kind>/ after R6
        build = True
    else:
        from .profiles import fsl
        root = fsl.registry_root(home)
        try:
            watched = [root.resolve().relative_to(home.resolve()).as_posix()]
        except ValueError:
            watched = []
        build = False
    if reg.get("build") is False:
        build = False
    return {"ns": ns, "profile": prof, "watched": watched, "build": build}
