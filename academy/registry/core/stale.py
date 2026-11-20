"""Statement drift after a review (#109 part 1; the human's ruling of 2026-11-20).

A ``proved`` / ``proved-modulo`` claim is **stale** when its current statement hash (the
one ``py -m registry statement <ns:id>`` prints and ``claims_set_status`` compares)
differs from the hash of its **last positive review pass**: the newest pass folder under
the library's ``reviews/<ns>/<id-slug>/`` that is closed by a ``decision.md`` (not
``abandoned.md``) and whose run records are

* a blind (or amend) pair: two or more records, every one ``CONFIRMED``, all on one
  ``statement_hash``; or
* a reword run: exactly one record with ``mode: reword``, ``CONFIRMED``, a
  ``reword_scope`` of :data:`grounds.REWORD_SCOPES` and a ``base_pass``;

and whose ``decision.md``, when it names a decision-table outcome, names ``confirmed`` or
``confirmed-modulo``.

What follows from it:

* ``check`` warns on every stale claim (a warning: ``--strict`` fails on it);
* the generated views show its status as ``proved (stale)`` / ``proved-modulo (stale)``
  (display only: the stored status is unchanged, and the claim-keeper's own hash checks
  are unchanged);
* ``registry.py stale [--ns NS] [--section S] [--file-reword]`` lists them grouped by
  section and files one reword verify ticket per claim, titled
  ``Verify <claim> (reword of <base pass>)`` (the title the inbox passes to ``verify.js``
  as ``mode: reword``, #85). The base pass is the last positive pass itself when it is
  blind, else the base pass of that reword run (a reword is always checked against a
  CONFIRMED x2 blind pass).

A stale claim is **held** (listed, never filed) when a later closed pass already
reviewed the current statement without a positive outcome (it needs the human or a
repair, not a reword), when a pass on it is still open, when its base pass name is
not one the inbox reads, or when the base pass is filed under another id (a renamed
record, T-0476: the title route passes no ``base_subject``). Nothing here reads the board; the command line does.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import grounds, workspace

POSITIVE_STATUSES = ("proved", "proved-modulo")
OPEN_DIR = ".open"
CLOSERS = ("decision.md", "abandoned.md")
RE_RUN_FILE = re.compile(r"^[A-Z]\.md$")
#: the base pass names the inbox reads from a title (inbox.js, #85)
RE_BASE_PASS = re.compile(r"^\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?$")
#: the decision table's outcomes (expert/scripts/decision_table.py)
OUTCOMES = ("confirmed-modulo", "confirmed", "awaiting-amendment", "awaiting-b", "degraded",
            "disagreement", "disproved", "full-pass-needed", "incomplete", "invalid-amend",
            "invalid-base", "invalid-pair", "new-pass-after-amendment", "no-change",
            "settle-dependencies", "single-negative")
RE_OUTCOME = re.compile(r"\boutcome:?\s+`?(%s)\b" % "|".join(re.escape(o) for o in OUTCOMES))


def slug_id(cid):
    """A registry id as one path segment, as the Expert's ``_expert.slug_id``."""
    s = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in str(cid))
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-.") or "item"


def expert_instance():
    """The first Expert instance of the workspace (sorted by name), or None."""
    names = sorted(workspace.instances_of_role("expert"))
    return names[0] if names else None


def reviews_root(repo=None):
    """The library's ``reviews/`` folder as seen from ``repo`` (the Expert home's
    ``paths.reviews``), or None when the workspace names no Expert or its home is not
    here (a lab clone on a server)."""
    inst = expert_instance()
    home = workspace.instance_home(inst, repo) if inst else None
    if home is None:
        return None
    rel = (((workspace.read_config(home) or {}).get("paths") or {}).get("reviews")
           or "reviews")
    if isinstance(rel, list):
        rel = rel[0]
    root = Path(home) / rel
    return root if root.is_dir() else None


def is_registered_home(ns, home):
    """Whether ``home`` is the workspace's home of ``ns`` or a worktree of it (its
    directory name is the home's, or that name and a ``-suffix``). The library's passes
    are about that home's records: a copy elsewhere (a temp dir with the same ``ns``) is
    never compared against them."""
    if home is None:
        return False
    return workspace.registered(home) == ns or workspace._by_name(home)[0] == ns


def subject_dir(root, qid):
    ns, _, cid = str(qid).partition(":")
    return Path(root) / ns / slug_id(cid)


def _records(d):
    out = []
    for n in sorted(os.listdir(d)):
        if RE_RUN_FILE.match(n):
            try:
                text = (d / n).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            f = grounds.record_fields(text)
            if f.get("verdict"):
                out.append(f)
    return out


def _decided_outcome(d):
    try:
        text = (d / "decision.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = RE_OUTCOME.search(text)
    return m.group(1) if m else ""


def read_pass(d):
    """What the pass folder ``d`` says: ``{"pass", "closed", "positive", "hash", "mode",
    "base_pass", "base_subject", "hashes"}``. ``hash`` is the statement hash a positive
    pass stands on; ``hashes`` every hash its records name."""
    d = Path(d)
    info = {"pass": d.name, "closed": any((d / c).is_file() for c in CLOSERS),
            "positive": False, "hash": "", "mode": "", "base_pass": "", "base_subject": "",
            "hashes": set()}
    if not d.is_dir():
        return info
    recs = _records(d)
    info["hashes"] = {r.get("statement_hash") for r in recs if r.get("statement_hash")}
    if not (d / "decision.md").is_file() or (d / "abandoned.md").is_file():
        return info
    outcome = _decided_outcome(d)
    if outcome and not outcome.startswith("confirmed"):
        return info
    if not recs or any(grounds.norm_verdict(r.get("verdict")) != "CONFIRMED" for r in recs):
        return info
    rw = [r for r in recs if grounds.is_reword(r)]
    if rw:
        r = rw[0]
        if len(recs) != 1 or not r.get("statement_hash") or not r.get("base_pass") or \
                str(r.get("reword_scope") or "").strip().lower() not in grounds.REWORD_SCOPES:
            return info
        info.update(positive=True, hash=r["statement_hash"], mode="reword",
                    base_pass=r["base_pass"].strip(),
                    base_subject=str(r.get("base_subject") or "").strip())
        return info
    hashes = {r.get("statement_hash") or "" for r in recs}
    if len(recs) < 2 or len(hashes) != 1 or "" in hashes:
        return info
    info.update(positive=True, hash=hashes.pop(), mode="blind", base_pass=d.name)
    return info


def passes(root, qid):
    """``read_pass`` of every pass of ``qid``, oldest first (pass names start with their
    date), the open ones noted only in ``.open/`` included."""
    d = subject_dir(root, qid)
    if not d.is_dir():
        return []
    names = {n for n in os.listdir(d) if n[:1] not in ("_", ".") and (d / n).is_dir()}
    if (d / OPEN_DIR).is_dir():
        names.update(os.listdir(d / OPEN_DIR))
    return [read_pass(d / n) for n in sorted(names)]


def label(status):
    """How a view shows a stale claim's status."""
    return "%s (stale)" % status


def find(store, root, only=None):
    """The stale claims of ``store`` (a ``model.Store``) against the reviews under
    ``root`` (None: none), sorted by section then id. ``only``: record ids to look at.
    Each is ``{"qid", "id", "status", "title", "file", "section", "hash", "pass",
    "pass_hash", "mode", "base_pass", "base_subject", "hold"}``; ``hold`` says why no
    reword ticket may be filed for it ('' when one may). Nothing for a store whose home
    is not the namespace's registered home (``is_registered_home``)."""
    if root is None or not is_registered_home(store.ns, store.home):
        return []
    out = []
    for rid in sorted(store.records):
        if only is not None and rid not in only:
            continue
        rec = store.records[rid]
        if rec.status not in POSITIVE_STATUSES:
            continue
        ps = passes(root, rec.qid)
        pos = [i for i, p in enumerate(ps) if p["positive"]]
        if not pos:
            continue
        last = ps[pos[-1]]
        h = store.statement_hash(rid)
        if not h or h == last["hash"]:
            continue
        hold = []
        for p in ps[pos[-1] + 1:]:
            if not p["closed"]:
                hold.append("the pass %s is still open" % p["pass"])
            elif h in p["hashes"]:
                hold.append("the later pass %s reviewed the current statement and is not "
                            "positive: the human decides (a repair or a blind pass), not "
                            "a reword" % p["pass"])
        base = last["base_pass"]
        if not RE_BASE_PASS.match(base) or base.endswith("-reword"):
            hold.append("the base pass %r is no name the inbox reads as a reword base: "
                        "file a blind verify" % base)
        if last["base_subject"] and last["base_subject"] != rec.qid:
            hold.append("a renamed record: its base pass %s is filed under %s, which the "
                        "inbox's reword title cannot pass on; run the reword pass by hand "
                        "(/expert:verify, mode reword, base_subject %s)"
                        % (base, last["base_subject"], last["base_subject"]))
        fields = rec.fields if isinstance(rec.fields, dict) else {}
        where = fields.get("where") if isinstance(fields.get("where"), str) else ""
        out.append({"qid": rec.qid, "id": rid, "status": rec.status, "title": rec.title,
                    "file": rec.file, "section": where or "(no section)", "hash": h,
                    "pass": last["pass"], "pass_hash": last["hash"], "mode": last["mode"],
                    "base_pass": base, "base_subject": last["base_subject"],
                    "hold": "; ".join(hold)})
    out.sort(key=lambda i: (i["section"], i["qid"]))
    return out


def warning(item):
    """The ``check`` warning for a stale claim (the path is the caller's)."""
    return ("statement changed since its last positive review pass %s (statement hash %s, "
            "now %s): its status shows as `%s` until a reword pass lands; "
            "`registry.py stale --file-reword` files it"
            % (item["pass"], item["pass_hash"], item["hash"], label(item["status"])))


def ticket_title(qid, base_pass):
    """The reword verify ticket's title: the inbox reads ``(reword of <pass>)`` (#85)."""
    return "Verify %s (reword of %s)" % (qid, base_pass)


def ticket_ask(item):
    via = "" if item["mode"] == "blind" else \
        " (its last positive pass is the reword pass %s, on hash %s)" % (item["pass"],
                                                                         item["pass_hash"])
    sub = (" The base pass is filed under %s (base_subject)." % item["base_subject"]) \
        if item["base_subject"] else ""
    return ("Reword review of %s (mode reword, base_pass %s): its statement changed after "
            "its last positive review pass%s (statement hash %s, now %s, %s). Its %s "
            "status shows as %s until this pass lands. Does the proof as reviewed still "
            "prove the new wording?%s"
            % (item["qid"], item["base_pass"], via, item["pass_hash"], item["hash"],
               item["section"], item["status"], label(item["status"]), sub))


def ticket_refs(item, expert):
    ns, _, cid = item["qid"].partition(":")
    refs = [item["qid"]]
    if expert:
        refs.append("file:%s/reviews/%s/%s/%s/decision.md"
                    % (expert, ns, slug_id(item["base_subject"].partition(":")[2]
                                           if item["base_subject"] else cid),
                       item["base_pass"]))
    return refs
