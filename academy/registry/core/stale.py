"""Statement drift after a review (#109 part 1; the human's ruling of 2026-11-20).

A ``proved`` / ``proved-modulo`` claim is **stale** when its current statement hash (the
one ``py -m registry statement <ns:id>`` prints and ``claims_set_status`` compares)
differs from the hash of its **last positive review pass**: the newest pass folder under
the library's ``reviews/<ns>/<id-slug>/`` that is closed by a ``decision.md`` (not
``abandoned.md``) and that the Expert's own decision table
(``expert/scripts/decision_table.py``) gives ``confirmed`` or ``confirmed-modulo``:

* a blind (or amend) pass: ``decide`` on the latest record of runs A and B (so the
  primary-model rule and differing modulo lists count as the table counts them);
* a reword pass: ``decide`` on its latest ``R`` record (``mode: reword``) with its base
  pass's records.

``decision.md``'s wording is not read. The latest record of a run letter is the one with
the greatest ``run_id``: a relaunch lands as ``A-2.md`` and the like (``land_verdict.py``),
and it is the run the pass kept. Without the decision table (an Expert plugin not beside
this one) nothing is flagged.

The reword ticket is filed only for a base pass the reword route accepts:
``reviews.base_decision`` (``base_records`` + ``decide`` on the base pass's ``A.md`` and
``B.md``, never a relaunch file) must give ``confirmed`` / ``confirmed-modulo``; otherwise
the claim is held and the reason says so.

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

import importlib
import os
import re
import sys
from pathlib import Path

from . import workspace

POSITIVE_STATUSES = ("proved", "proved-modulo")
OPEN_DIR = ".open"
CLOSERS = ("decision.md", "abandoned.md")
#: a run record: ``A.md``, a relaunch ``A-2.md``, ``R-rv-....md`` (land_verdict.py)
RE_RUN_FILE = re.compile(r"^([A-Z])(?:-[A-Za-z0-9._-]+)?\.md$")
#: the base pass names the inbox reads from a title (inbox.js, #85)
RE_BASE_PASS = re.compile(r"^\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?$")



def slug_id(cid):
    """A registry id as one path segment, as the Expert's ``_expert.slug_id``."""
    s = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in str(cid))
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-.") or "item"


_DT = {}


def decision_table():
    """The Expert plugin's ``decision_table`` module (``<academy repo>/expert/scripts``,
    beside this plugin), or None when it is not there."""
    if "dt" not in _DT:
        here = Path(__file__).resolve().parents[3] / "expert" / "scripts"
        mod = None
        if (here / "decision_table.py").is_file():
            if str(here) not in sys.path:
                sys.path.insert(0, str(here))
            try:
                mod = importlib.import_module("decision_table")
            except Exception:       # noqa: BLE001 -- an unusable plugin: nothing flagged
                mod = None
        _DT["dt"] = mod
    return _DT["dt"]


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


def latest_records(d):
    """{run letter: (path, record fields)} of the pass folder ``d``: per letter (the
    record's ``run``, else the file's), the record with the greatest ``run_id``."""
    dt = decision_table()
    out = {}
    for n in sorted(os.listdir(d)):
        m = RE_RUN_FILE.match(n)
        if not m:
            continue
        try:
            rec = dt.read_record(str(d / n))
        except (OSError, ValueError):
            continue
        if not rec.get("verdict"):
            continue
        letter = (rec.get("run") or m.group(1)).strip().upper()[:1] or m.group(1)
        key = (rec.get("run_id") or "", n)
        if letter not in out or key > out[letter][0]:
            out[letter] = (key, d / n, rec)
    return {k: (v[1], v[2]) for k, v in out.items()}


def _outcome(res):
    return str((res or {}).get("outcome") or "")


def read_pass(d):
    """What the pass folder ``d`` says: ``{"pass", "decided", "abandoned", "hashes"}``
    (``hashes``: the statement hashes of its latest records)."""
    d = Path(d)
    info = {"pass": d.name, "decided": (d / "decision.md").is_file(),
            "abandoned": (d / "abandoned.md").is_file(), "hashes": set()}
    if d.is_dir() and decision_table() is not None:
        info["hashes"] = {r.get("statement_hash") for _p, r in latest_records(d).values()
                          if r.get("statement_hash")}
    return info


def positive(d):
    """``{"hash", "hashes", "mode", "base_pass", "base_subject"}`` when the decision table
    gives the closed pass ``d`` ``confirmed`` / ``confirmed-modulo``, else None."""
    d = Path(d)
    dt = decision_table()
    if dt is None or not (d / "decision.md").is_file() or (d / "abandoned.md").is_file():
        return None
    recs = latest_records(d)
    try:
        r = recs.get("R")
        if r is not None and dt.is_reword(r[1]):
            rec = r[1]
            ba, bb, notes = dt.base_records(str(r[0]), rec.get("base_pass"), None,
                                            rec.get("base_subject") or None)
            res = dt.decide(rec, None, base=(ba, bb), base_notes=notes)
            if not _outcome(res).startswith("confirmed") or not rec.get("statement_hash"):
                return None
            return {"hash": rec["statement_hash"], "hashes": {rec["statement_hash"]},
                    "mode": "reword", "base_pass": str(rec.get("base_pass") or "").strip(),
                    "base_subject": str(rec.get("base_subject") or "").strip()}
        a, b = (recs.get(k, (None, None))[1] for k in ("A", "B"))
        if a is None or b is None or not _outcome(dt.decide(a, b)).startswith("confirmed"):
            return None
    except Exception:               # noqa: BLE001 -- an unreadable pass is not positive
        return None
    hashes = {rr.get("statement_hash") for k, (_p, rr) in recs.items()
              if k in ("A", "B") and rr.get("statement_hash")}
    if not hashes:
        return None
    return {"hash": "/".join(sorted(hashes)), "hashes": hashes, "mode": "blind",
            "base_pass": d.name, "base_subject": ""}


def reword_base_refusal(root, subject, base_pass):
    """Why the reword route would refuse ``base_pass`` of ``subject`` as its base ('' when
    it accepts it): the check of ``reviews.base_decision``, on the base pass's ``A.md``
    and ``B.md``."""
    dt = decision_table()
    d = subject_dir(root, subject) / base_pass
    try:
        a, b, notes = dt.base_records(None, base_pass, str(d))
        if a is None or b is None:
            return "; ".join(notes) or "its runs A and B are missing"
        out = _outcome(dt.decide(a, b))
    except Exception as exc:        # noqa: BLE001 -- said as the refusal
        return "its records cannot be read (%s)" % exc
    return "" if out.startswith("confirmed") else \
        "the decision table gives %s on its A.md and B.md" % (out or "no outcome")


def passes(root, qid):
    """``read_pass`` of every pass of ``qid``, oldest first (pass names start with their
    date), the open ones noted only in ``.open/`` included."""
    d = subject_dir(root, qid)
    if not d.is_dir():
        return []
    names = {n for n in os.listdir(d) if n[:1] not in ("_", ".") and (d / n).is_dir()}
    if (d / OPEN_DIR).is_dir():
        names.update(os.listdir(d / OPEN_DIR))
    return [d / n for n in sorted(names)]


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
    if root is None or decision_table() is None or \
            not is_registered_home(store.ns, store.home):
        return []
    out = []
    for rid in sorted(store.records):
        if only is not None and rid not in only:
            continue
        rec = store.records[rid]
        if rec.status not in POSITIVE_STATUSES:
            continue
        ps = passes(root, rec.qid)
        last, k = None, len(ps)
        while last is None and k > 0:            # newest first: stop at the first positive
            k -= 1
            last = positive(ps[k])
        if last is None:
            continue
        h = store.statement_hash(rid)
        if not h or h in last["hashes"]:
            continue
        last["pass"] = ps[k].name
        hold = []
        for p in map(read_pass, ps[k + 1:]):
            if p["abandoned"]:
                continue
            if not p["decided"]:
                hold.append("the pass %s is still open" % p["pass"])
            elif h in p["hashes"]:
                hold.append("the later pass %s reviewed the current statement and is not "
                            "positive: the human decides (a repair or a blind pass), not "
                            "a reword" % p["pass"])
        base = last["base_pass"]
        if not RE_BASE_PASS.match(base) or base.endswith("-reword"):
            hold.append("the base pass %r is no name the inbox reads as a reword base: "
                        "file a blind verify" % base)
        else:
            why = reword_base_refusal(root, last["base_subject"] or rec.qid, base)
            if why:
                hold.append("the reword route (reviews.base_decision) would refuse the base "
                            "pass %s: %s; a blind verify instead" % (base, why))
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
