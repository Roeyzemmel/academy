"""The touch ledger: which files a role wrote in another role's home, so the checkpoint
after a ticket ships them (``docs/branching.md``, "After each inbox ticket").

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.

The checkpoint after a ticket is scoped to the acting role's repos (its home, ``board``,
``library`` for the Expert). Some routes legitimately write in another role's home: the
Expert's librarian adds entries to an Author home's ``references.bib``; a review chair,
a librarian or the claim-keeper writes evidence rows and statuses into the registry of
whichever home owns the claim's namespace. Those writes are recorded here, at the moment
they are made, by the two write paths that can make them:

* the ``touch_record`` PostToolUse hook (an agent's Edit / Write in a home whose role is
  not the agent's), and
* the MCP server's claims write tools (the files a ``claims_new``, ``claims_attach_evidence``
  or ``claims_set_status`` call changed in a home whose role is not the caller's).

One entry is one small JSON file in a directory of this machine, outside every repo
(``$ACADEMY_TOUCHED_DIR``, else ``~/.claude/academy/touched``), one subdirectory per
workspace root, so concurrent writers never rewrite a shared file. An entry is
``{path, role, instance, agent, via, created, ticket}``; ``ticket`` is empty until the
inbox's ``--check`` of a finished ticket of that role claims it (``claim_touches``):
the inbox works one ticket at a time per instance, so the unclaimed entries of the role
are that ticket's writes. A claimed entry stays with its ticket until its repo was
shipped (``drop_touches``), so a refused or failed ship is retried by the next
``--check`` of the same ticket and never taken by another one. Entries older than
``TOUCH_TTL_DAYS`` are pruned. Only the main session's own edits are never recorded:
it is the human, and the human's work is never swept up.
"""

import hashlib
import json
import os
import time

from ._base import _norm

#: days an entry (claimed or not) is kept before it is pruned
TOUCH_TTL_DAYS = 14


def touched_base():
    """The ledger's directory (``$ACADEMY_TOUCHED_DIR``, else ``~/.claude/academy/touched``)."""
    return os.environ.get("ACADEMY_TOUCHED_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude", "academy", "touched")


def touched_dir(root):
    """The ledger directory of the workspace at ``root`` (a hash of its real path)."""
    key = hashlib.sha256(_norm(os.path.realpath(str(root))).encode("utf-8")).hexdigest()[:16]
    return os.path.join(touched_base(), key)


def _real(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def home_of_path(workspace, path):
    """``(instance, record)`` of the workspace instance whose home holds ``path`` (the
    longest such home), or ``(None, None)``."""
    full = _real(path)
    best, best_len = (None, None), -1
    for name, inst in ((workspace or {}).get("instances") or {}).items():
        h = inst.get("home") if isinstance(inst, dict) else None
        if not h:
            continue
        hr = _real(h)
        if (full == hr or full.startswith(hr.rstrip(os.sep) + os.sep)) and len(hr) > best_len:
            best, best_len = (name, inst), len(hr)
    return best


def is_cross_home(workspace, path, role):
    """Whether ``path`` lies in the home of an instance whose role is not ``role``."""
    name, inst = home_of_path(workspace, path)
    return bool(name) and bool(role) and inst.get("role") != role


def record_touch(root, paths, role, instance=None, agent="", via="", now=None):
    """Record that ``role`` (acting for ``instance`` when known) wrote ``paths``. Returns
    the entry files written."""
    folder = touched_dir(root)
    os.makedirs(folder, exist_ok=True)
    now = time.time() if now is None else now
    written = []
    for p in paths:
        rec = {"path": os.path.abspath(str(p)), "role": role, "instance": instance or None,
               "agent": agent or "", "via": via or "", "created": now, "ticket": None}
        name = "%020d-%d-%s.json" % (int(now * 1e6), os.getpid(), os.urandom(4).hex())
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rec, fh)
        written.append(path)
    return written


def touch_entries(root, now=None):
    """``[(entry file, record)]`` of the workspace at ``root``, oldest first; entries older
    than ``TOUCH_TTL_DAYS`` are removed on the way."""
    folder = touched_dir(root)
    now = time.time() if now is None else now
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".json"))
    except OSError:
        return []
    out = []
    for n in names:
        p = os.path.join(folder, n)
        try:
            with open(p, encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(rec, dict) or not isinstance(rec.get("path"), str):
            continue
        try:
            created = float(rec.get("created") or 0)
        except (TypeError, ValueError):
            created = 0.0
        if now - created > TOUCH_TTL_DAYS * 86400:
            try:
                os.remove(p)
            except OSError:
                pass
            continue
        out.append((p, rec))
    return out


def claim_touches(root, ticket, role, instance=None, now=None):
    """The entries of ticket ``ticket``: those already claimed for it, and every unclaimed
    entry of ``role`` (whose instance is ``instance`` or unknown), which are claimed for
    it now. ``[(entry file, record)]``."""
    mine = []
    for p, rec in touch_entries(root, now):
        if rec.get("ticket") == ticket:
            mine.append((p, rec))
            continue
        if rec.get("ticket") or rec.get("role") != role:
            continue
        if instance and rec.get("instance") and rec.get("instance") != instance:
            continue
        rec = dict(rec, ticket=ticket)
        tmp = p + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(rec, fh)
            os.replace(tmp, p)
        except OSError:
            continue
        mine.append((p, rec))
    return mine


def drop_touches(files):
    """Remove these entry files (a shipped repo's entries)."""
    for p in files:
        try:
            os.remove(p)
        except OSError:
            pass
