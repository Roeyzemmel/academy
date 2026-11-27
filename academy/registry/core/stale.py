"""Statement drift after a review (#109 part 1; the human's ruling of 2026-11-20).

A ``proved`` / ``proved-modulo`` claim is **stale** when its current statement hash (the
one ``py -m registry statement <ns:id>`` prints and ``claims_set_status`` compares)
differs from the hash of its **last positive review pass**: the newest pass folder under
the library's ``reviews/<ns>/<id-slug>/`` that is closed by a ``decision.md`` (not
``abandoned.md``) and that the Expert's own decision table
(``expert/scripts/decision_table.py``) gives ``confirmed`` or ``confirmed-modulo``:

* a blind (or amend) pass: ``decide`` on the latest record of runs A and B (so the
  primary-model rule and differing modulo lists count as the table counts them). When
  the table gives ``settle-dependencies`` the settlement decides: the pass's settler
  record (``S.json``, or the JSON block of ``S.md``) checked and applied by
  ``settle_deps.py`` (``confirmed-settled``), else, with no such record (the passes
  settled before it existed, T-1461), the outcome ``decision.md`` records
  (``confirmed`` / ``confirmed-modulo``);
* a reword pass: ``decide`` on its latest ``R`` record (``mode: reword``) with its base
  pass's records; when the table gives ``invalid-base`` because the base was settled,
  the reword pass stands if its base pass is positive by the rule above, run R is
  ``CONFIRMED`` within a reword scope and ``decision.md`` records a confirmed outcome.

Otherwise ``decision.md``'s wording is not read. The latest record of a run letter is the one with
the greatest ``run_id``: a relaunch lands as ``A-2.md`` and the like (``land_verdict.py``),
and it is the run the pass kept. Without the decision table (an Expert plugin not beside
this one) nothing is flagged.

The reword ticket is filed only for a base pass the reword route accepts:
``reviews.base_decision`` (``base_records`` + ``decide`` on the base pass's ``A.md`` and
``B.md``, or on a reword base's ``R.md`` and its chain back to the blind root, never a
relaunch file) must give ``confirmed`` / ``confirmed-modulo``; otherwise the claim is
held and the reason says so.

What follows from it:

* ``check`` warns on every stale claim (a warning: ``--strict`` fails on it);
* the generated views show its status as ``proved (stale)`` / ``proved-modulo (stale)``
  (display only: the stored status is unchanged, and the claim-keeper's own hash checks
  are unchanged);
* ``registry.py stale [--ns NS] [--section S] [--file-reword]`` lists them grouped by
  section and files one reword verify ticket per claim, titled
  ``Verify <claim> (reword of <base pass>)`` (the title the inbox passes to ``verify.js``
  as ``mode: reword``, #85). The base pass is the last positive pass itself, blind or
  reword (#127, the human's ruling of 2026-11-27: a reword has the previous confirmed
  statement as reference; a reword base's chain ends in a CONFIRMED x2 blind pass).

A stale claim is **held** (listed, never filed) when a later closed pass already
reviewed the current statement without a positive outcome (it needs the human or a
repair, not a reword), when a pass on it is still open, or when its base pass name is
not one the inbox reads. The base pass is always one of the claim's own passes, so the
title route needs no ``base_subject`` (a renamed record's earlier passes are reached
through the chain). Nothing here reads the board; the command line does.

A ``proved`` / ``proved-modulo`` claim that has review passes but **no positive one** is
reported too (kind ``unreviewed``): ``check`` warns "proved without a positive review
pass on record" and ``stale`` lists it as held; the views do not mark it.

The Expert's ``decision_table.py`` and ``settle_deps.py`` are loaded by file path from
``<academy repo>/expert/scripts`` (:data:`DT_PATH`) under private module names, so no
other module of that name on ``sys.path`` stands in for them. When the table is missing,
``check`` and ``stale`` say so (:func:`decision_table_problem`).
"""
from __future__ import annotations

import importlib.util
import json
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
#: the Expert plugin's decision table, beside this plugin
DT_PATH = Path(__file__).resolve().parents[3] / "expert" / "scripts" / "decision_table.py"


def _load(key, path, name):
    if key not in _DT:
        mod = None
        path = Path(path)
        if path.is_file():
            here = str(path.parent)
            if here not in sys.path:
                sys.path.insert(0, here)        # its own imports (_academy)
            try:
                spec = importlib.util.spec_from_file_location(name, str(path))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            except Exception:   # noqa: BLE001 -- unusable: decision_table_problem says so
                mod = None
        _DT[key] = mod
    return _DT[key]


def decision_table():
    """The Expert plugin's ``decision_table`` module (:data:`DT_PATH`), loaded by path
    under a private name, or None when it is not there or does not load."""
    return _load("dt", DT_PATH, "_academy_stale_decision_table")


def settle_deps():
    """The Expert plugin's ``settle_deps`` module (beside :data:`DT_PATH`), or None."""
    return _load("sd", Path(DT_PATH).parent / "settle_deps.py", "_academy_stale_settle_deps")


def decision_table_problem():
    """'' when the decision table loads, else the one line ``check`` and ``stale`` say."""
    if decision_table() is not None:
        return ""
    return ("the statement-drift check did not run: the Expert's decision table %s %s"
            % (Path(DT_PATH).as_posix(), "does not load" if Path(DT_PATH).is_file()
               else "is missing (expected at <academy repo>/expert/scripts/decision_table.py)"))


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


_WORDS = ("confirmed-settled", "confirmed-modulo", "confirmed", "settle-dependencies",
          "disagreement", "single-negative", "disproved", "degraded", "invalid-base",
          "invalid-pair", "invalid-amend", "incomplete", "awaiting-amendment", "awaiting-b",
          "full-pass-needed", "no-change", "new-pass-after-amendment")
#: the outcome a decision.md records, in its spellings ("- outcome: `confirmed`",
#: "Outcome (decision_table.py): confirmed-modulo", "## Outcome" then "`confirmed`;")
RE_RECORDED = re.compile(r"outcome\W{0,6}(?:\(decision_table\.py[^)\n]*\)\W{0,4})?\s*`?(%s)\b"
                         % "|".join(re.escape(w) for w in _WORDS), re.I)


def recorded_confirmed(d):
    """Whether the pass's decision.md records a confirmed outcome (any of its outcome
    lines says ``confirmed``, ``confirmed-modulo`` or ``confirmed-settled``)."""
    try:
        text = (Path(d) / "decision.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(m.group(1).lower().startswith("confirmed") for m in RE_RECORDED.finditer(text))


def _settler_record(d):
    """The pass's settler record (S.json, or the first JSON block of S.md), or None."""
    p = Path(d) / "S.json"
    try:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
        md = Path(d) / "S.md"
        if md.is_file():
            m = re.search(r"```json\s*\n(.*?)\n```", md.read_text(encoding="utf-8"), re.S)
            if m:
                return json.loads(m.group(1))
    except (OSError, ValueError):
        return {}
    return None


def settled(d, table):
    """Whether a ``settle-dependencies`` pass was settled to a confirmed outcome: its
    settler record, checked and applied by ``settle_deps.py``, decides; without one, the
    outcome decision.md records."""
    rec = _settler_record(d)
    if rec is None:
        return recorded_confirmed(d)
    sd = settle_deps()
    if sd is None or not isinstance(rec, dict) or sd.check(rec, table):
        return False
    return _outcome(sd.apply(rec, table)).startswith("confirmed")


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
            ok = _outcome(res).startswith("confirmed")
            if not ok and _outcome(res) == "invalid-base" and rec.get("base_pass"):
                # a settled base (a reword over a settle-dependencies pass): the table does not
                # read settlements, so the base is judged here
                bs = str(rec.get("base_subject") or "").strip()
                base_dir = (d.parent.parent.parent / bs.split(":", 1)[0] /
                            slug_id(bs.split(":", 1)[1]) if ":" in bs else d.parent) \
                    / str(rec["base_pass"]).strip()
                ok = (positive(base_dir) is not None and rec.get("verdict") == "CONFIRMED"
                      and bool(rec.get("reword_scope")) and recorded_confirmed(d))
            if not ok or not rec.get("statement_hash"):
                return None
            return {"hash": rec["statement_hash"], "hashes": {rec["statement_hash"]},
                    "mode": "reword", "base_pass": str(rec.get("base_pass") or "").strip(),
                    "base_subject": str(rec.get("base_subject") or "").strip()}
        a, b = (recs.get(k, (None, None))[1] for k in ("A", "B"))
        if a is None or b is None:
            return None
        res = dt.decide(a, b)
        if not (_outcome(res).startswith("confirmed") or
                _outcome(res) == "settle-dependencies" and settled(d, res)):
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
    and ``B.md``, or (#127) on a reword base's ``R.md`` with its chain."""
    dt = decision_table()
    d = subject_dir(root, subject) / base_pass
    try:
        a, b, notes = dt.base_records(None, base_pass, str(d))
        if dt.is_link(a, b):
            sub = a.get("_base") or (None, None, [])
            res = dt.decide(a, None, base=sub[:2], base_notes=sub[2])
            out = _outcome(res)
            return "" if out.startswith("confirmed") else \
                "the decision table gives %s on its R.md and its chain (%s)" % (
                    out or "no outcome", "; ".join(res.get("anomalies") or []) or
                    res.get("summary") or "no reason")
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
    Each is ``{"kind", "qid", "id", "status", "title", "file", "section", "hash", "pass",
    "pass_hash", "mode", "base_pass", "base_subject", "hold"}``, ``kind`` ``stale`` or
    ``unreviewed`` (passes on record, none positive); ``hold`` says why no
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
        fields = rec.fields if isinstance(rec.fields, dict) else {}
        where = fields.get("where") if isinstance(fields.get("where"), str) else ""
        base_item = {"qid": rec.qid, "id": rid, "status": rec.status, "title": rec.title,
                     "file": rec.file, "section": where or "(no section)"}
        if last is None:
            if ps:
                out.append(dict(base_item, **{
                    "kind": "unreviewed", "hash": "", "pass": "", "pass_hash": "",
                    "mode": "", "base_pass": "", "base_subject": "",
                    "hold": "%s without a positive review pass on record (%d pass(es), "
                            "the last %s): the status rests on no confirmed pass; the "
                            "human decides (a blind verify)"
                            % (rec.status, len(ps), ps[-1].name)}))
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
        # #127: the next reword stands on the last positive pass itself, blind or reword
        base = last["pass"]
        if not RE_BASE_PASS.match(base):
            hold.append("the base pass %r is no name the inbox reads as a reword base: "
                        "file a blind verify" % base)
        else:
            why = reword_base_refusal(root, rec.qid, base)
            if why:
                hold.append("the reword route (reviews.base_decision) would refuse the base "
                            "pass %s: %s; a blind verify instead" % (base, why))
        out.append(dict(base_item, **{
            "kind": "stale", "hash": h, "pass": last["pass"], "pass_hash": last["hash"],
            "mode": last["mode"], "base_pass": base, "base_subject": "",
            "hold": "; ".join(hold)}))
    out.sort(key=lambda i: (i["section"], i["qid"]))
    return out


def warning(item):
    """The ``check`` warning for a stale or unreviewed claim (the path is the
    caller's)."""
    if item.get("kind") == "unreviewed":
        return "%s without a positive review pass on record (the last pass is %s)" % (
            item["status"], item["hold"].rsplit("the last ", 1)[-1].split(")", 1)[0])
    return ("statement changed since its last positive review pass %s (statement hash %s, "
            "now %s): its status shows as `%s` until a reword pass lands; "
            "`registry.py stale --file-reword` files it"
            % (item["pass"], item["pass_hash"], item["hash"], label(item["status"])))


def ticket_title(qid, base_pass):
    """The reword verify ticket's title: the inbox reads ``(reword of <pass>)`` (#85)."""
    return "Verify %s (reword of %s)" % (qid, base_pass)


def ticket_ask(item):
    via = "" if item["mode"] == "blind" else \
        (" (its last positive pass is the reword pass %s, on hash %s: the new reword is "
         "checked against the wording it confirmed)" % (item["pass"], item["pass_hash"]))
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
