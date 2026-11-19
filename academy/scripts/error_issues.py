"""error_issues.py -- the error ledger's classes as GitHub issues (academy#95).

Used by ``error_ledger.py`` (``sync``, ``migrate``, and ``report`` / ``resolve`` / ``settle``
when workspace.json names ``errors.repo``); never by its hook, which stays offline.

One issue per error class, labelled ``error-class``, found by the hidden marker
``<!-- sig:<hash> -->`` in its body (``hash``: the first 12 hex digits of the sha1 of the
class signature). The body is a table for the reader plus the class's fields as hidden
JSON (``<!-- error-class {...} -->``: sig, tool, family, families, msg, first, last,
count, rev, ver, and ``fix`` once a resolve named a commit or version). Each comment of a
sync carries its occurrences as hidden JSON rows (``<!-- occurrences [...] -->``: ts,
session, instance, cause, rev, ver, agent) and a resolve or settle carries
``<!-- resolves [...] -->``, so ``records_of`` rebuilds the ledger records of a class and
``error_ledger.report`` reads them unchanged. Every text that leaves the machine is
redacted (``error_ledger.redact``) and has home-directory prefixes replaced by ``~``.

A closed issue that recurs is reopened: with label ``regression`` when its last resolve
named a fix (commit or version), or ``stale-code`` when every new error came from code
older than that fix (``error_ledger.has_fix``). The spool's cursor (``cursor.json`` in
the spool directory) holds a byte offset per spool file, so a record is posted once; a
sync that fails part-way records the batch and the classes already posted (``partial``)
and the next sync finishes that batch first, without posting those classes again.

The transport is ``board_gh.GhTransport`` (``gh api`` through a subprocess; its ``run``
is injectable, and the tests pass a fake GitHub).
"""

import collections
import datetime as _dt
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

import error_ledger as el  # noqa: E402
from board_gh import GhError, GhTransport  # noqa: E402,F401

LABEL = "error-class"
REGRESSION = "regression"
STALE = "stale-code"
TAGS = (REGRESSION, STALE)
CURSOR = "cursor.json"
#: characters of hidden JSON per comment (GitHub's limit on a comment is 65536)
PAYLOAD_MAX = 50000
TITLE_MAX = 120
RE_HOME = re.compile(r"(?i)(?:[a-z]:)?[\\/](?:users|home)[\\/][^\\/\s'\"`|]+")
RE_MARK = re.compile(r"<!-- sig:([0-9a-f]{12}) -->")


def sig_hash(sig):
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()[:12]


def scrub(text):
    """Redacted (secrets), home directories as ``~``: what may go to a public issue."""
    return el.redact(RE_HOME.sub("~", str(text or "")))


def hidden(name, obj):
    """``obj`` as JSON in an HTML comment; ``<`` and ``>`` (only ever inside strings) are
    escaped, so the comment cannot be closed early."""
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "<!-- %s %s -->" % (name, s.replace("<", "\\u003c").replace(">", "\\u003e"))


def read_hidden(name, text):
    out = []
    for m in re.finditer(r"<!-- %s (.*?) -->" % re.escape(name), text or "", re.S):
        try:
            out.append(json.loads(m.group(1)))
        except ValueError:
            continue
    return out


def meta_of(issue):
    got = read_hidden("error-class", (issue or {}).get("body") or "")
    return got[-1] if got and isinstance(got[-1], dict) else None


def hash_of(issue):
    m = RE_MARK.search((issue or {}).get("body") or "")
    return m.group(1) if m else None


def label_names(issue):
    return [lb["name"] if isinstance(lb, dict) else str(lb) for lb in issue.get("labels") or []]


def transport(repo, run=None, write_interval=None):
    kw = {} if write_interval is None else {"write_interval": write_interval}
    return GhTransport(repo, run=run, **kw)


# -- the issue's text -------------------------------------------------------------------

def _cell(text):
    return scrub(" ".join(str(text or "-").split())).replace("|", "\\|")


def _code(text):
    return "`%s`" % scrub(" ".join(str(text or "").split())).replace("`", "'")


def title(sig):
    t = "error class: " + scrub(sig)
    return t if len(t) <= TITLE_MAX else t[:TITLE_MAX - 3] + "..."


def render_body(meta):
    fix = meta.get("fix") or {}
    rows = [("signature", _code(meta["sig"])), ("tool", _code(meta.get("tool"))),
            ("family", _cell(meta.get("family"))),
            ("families seen", _cell(", ".join(meta.get("families") or []) or "-")),
            ("example message", _cell(meta.get("msg"))),
            ("first seen", _cell(meta.get("first"))), ("last seen", _cell(meta.get("last"))),
            ("occurrences", str(meta.get("count") or 0)),
            ("code of the last one", _cell("rev %s, version %s" % (meta.get("rev") or "-",
                                                                   meta.get("ver") or "-")))]
    if fix:
        rows.append(("fix", _cell("commit %s, version %s" % (fix.get("commit") or "-",
                                                            fix.get("version") or "-"))))
    out = ["<!-- sig:%s -->" % meta["hash"],
           "An error class of the academy's error ledger (`error_ledger.py`): the failed tool "
           "calls with this signature. Each sync adds a comment with the new occurrences; "
           "`error_ledger.py resolve` closes the issue, and a recurrence reopens it "
           "(`regression` after a fix, `stale-code` when the errors came from code older "
           "than the fix).", "", "| field | value |", "|---|---|"]
    out += ["| %s | %s |" % r for r in rows]
    stored = dict(meta, msg=scrub(meta.get("msg")), sig=meta["sig"])
    out += ["", hidden("error-class", stored)]
    return "\n".join(out) + "\n"


def occ_row(r):
    return [r["ts"], (r.get("session") or "?")[-16:], r.get("instance") or "?",
            r.get("cause") or "", r.get("rev") or "", r.get("ver") or "",
            scrub(r.get("agent") or "")]


def batch_id(sig, recs):
    return hashlib.sha1(json.dumps([sig] + [occ_row(r) for r in recs]).encode("utf-8")
                        ).hexdigest()[:12]


def _chunks(rows):
    out, cur, size = [], [], 0
    for row in rows:
        n = len(json.dumps(row, ensure_ascii=False)) + 1
        if cur and size + n > PAYLOAD_MAX:
            out.append(cur)
            cur, size = [], 0
        cur.append(row)
        size += n
    out.append(cur)
    return out


def summary_text(recs, header=None):
    """The readable part of an occurrence comment: count, span, sessions, instances,
    causes and the latest record's message, detail, command and path, redacted."""
    last = recs[-1] if recs else {}
    out = []
    if header:
        out += [header, ""]
    if recs:
        out.append("**%d occurrence(s)**, %s .. %s; %d session(s); instance(s): %s" % (
            len(recs), recs[0]["ts"], last["ts"], len({r.get("session") or "?" for r in recs}),
            ", ".join(sorted({r.get("instance") or "?" for r in recs}))))
        causes = collections.Counter(r.get("cause") for r in recs if r.get("cause"))
        if causes:
            out.append("Causes: " + ", ".join("%s %d" % kv for kv in causes.most_common()))
        out += ["", "Latest:", "- message: " + _code(last.get("msg"))]
        for key, name in (("detail", "detail"), ("cmd", "command"), ("path", "path"),
                          ("pattern", "pattern"), ("cwd", "cwd"), ("agent", "agent")):
            if last.get(key):
                out.append("- %s: %s" % (name, _code(last[key])))
        if last.get("rev") or last.get("ver"):
            out.append("- code: rev %s, version %s" % (last.get("rev") or "-",
                                                        last.get("ver") or "-"))
    return out


def occurrence_comments(recs, batch, header=None, resolves=()):
    """The comment bodies for ``recs`` (one class, oldest first): the summary and the
    hidden rows, split so no comment's payload passes ``PAYLOAD_MAX``; each carries
    ``<!-- batch:<id> part k/n -->`` so a retried sync can tell what is already there."""
    parts = _chunks([occ_row(r) for r in recs])
    out = []
    for k, rows in enumerate(parts, 1):
        text = summary_text(recs, header) if k == 1 else ["(continued, part %d of %d)"
                                                           % (k, len(parts))]
        text += ["", "<!-- batch:%s part %d/%d -->" % (batch, k, len(parts))]
        if rows:
            text.append(hidden("occurrences", rows))
        if k == 1 and resolves:
            text.append(hidden("resolves", [_resolve_row(r) for r in resolves]))
        out.append("\n".join(text) + "\n")
    return out


def _resolve_row(r):
    row = {"ts": r["ts"], "by": r.get("by") or "", "note": scrub(r.get("note") or "")}
    for k in ("commit", "version"):
        if r.get(k):
            row[k] = r[k]
    return row


def records_of(meta, comments):
    """The ledger records of one class, rebuilt from its comments' hidden payloads."""
    out = []
    for c in comments:
        body = c.get("body") or ""
        for rows in read_hidden("occurrences", body):
            for row in rows if isinstance(rows, list) else []:
                ts, sess, inst, cause, rev, ver, agent = (list(row) + [""] * 7)[:7]
                rec = {"t": "error", "ts": ts, "session": sess, "instance": inst,
                       "tool": meta.get("tool") or "?", "sig": meta["sig"],
                       "msg": meta.get("msg") or ""}
                for k, v in (("cause", cause), ("rev", rev), ("ver", ver), ("agent", agent)):
                    if v:
                        rec[k] = v
                out.append(rec)
        for rows in read_hidden("resolves", body):
            for r in rows if isinstance(rows, list) else []:
                if isinstance(r, dict) and r.get("ts"):
                    out.append(dict(r, t="resolve", sig=meta["sig"]))
    return out


def merge_meta(old, sig, recs, batch):
    """The class fields after adding ``recs``; unchanged when ``batch`` is already in."""
    m = dict(old or {})
    if m.get("batch") == batch:
        return m
    last = recs[-1]
    m.update(sig=sig, hash=sig_hash(sig), family=el.family(sig), batch=batch,
             tool=last.get("tool") or m.get("tool") or "?",
             msg=scrub(last.get("msg") or m.get("msg") or ""))
    m["families"] = sorted(set(m.get("families") or []) |
                           {el.family_of(sig, r) for r in recs})
    m["first"] = min([x for x in (m.get("first"), recs[0]["ts"]) if x])
    m["last"] = max([x for x in (m.get("last"), last["ts"]) if x])
    m["count"] = int(m.get("count") or 0) + len(recs)
    for k in ("rev", "ver"):
        if last.get(k):
            m[k] = last[k]
    return m


# -- reading the repo ---------------------------------------------------------------------

def _pages(fetch):
    out, page = [], 1
    while True:
        rows = fetch(page) or []
        out += rows
        if len(rows) < 100:
            return out
        page += 1


def list_classes(t, state="all"):
    """The ``error-class`` issues (pull requests left out)."""
    return [i for i in _pages(lambda p: t.list_issues(labels=[LABEL], state=state, page=p))
            if "pull_request" not in i]


def index(t, state="all"):
    """sig hash -> issue; the lowest number wins if a class has two."""
    out = {}
    for i in list_classes(t, state):
        h = hash_of(i)
        if h and (h not in out or i["number"] < out[h]["number"]):
            out[h] = i
    return out


def comments_of(t, number):
    return _pages(lambda p: t.list_comments(number, page=p))


# -- sync -----------------------------------------------------------------------------------

def load_cursor(spool):
    try:
        with open(os.path.join(spool, CURSOR), encoding="utf-8") as fh:
            cur = json.load(fh)
    except (OSError, ValueError):
        cur = {}
    if not isinstance(cur, dict):
        cur = {}
    cur.setdefault("offsets", {})
    cur.setdefault("partial", None)
    return cur


def save_cursor(spool, cur):
    os.makedirs(spool, exist_ok=True)
    tmp = os.path.join(spool, CURSOR + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cur, fh, indent=1, sort_keys=True)
    os.replace(tmp, os.path.join(spool, CURSOR))


def read_batch(spool, cur):
    """``(records, upto)``: the spool's error records from each file's cursor offset to its
    end (whole lines only), or to the unfinished batch's end when there is one; benign
    records and identical duplicates left out. ``upto`` is the new offset per file."""
    partial = cur.get("partial")
    try:
        names = sorted(n for n in os.listdir(spool) if n.endswith(".jsonl"))
    except OSError:
        names = []
    recs, upto, seen = [], {}, set()
    for name in names:
        path = os.path.join(spool, name)
        start = int(cur["offsets"].get(name, 0))
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size < start:            # the file was cut by hand: read it again from the top
            start = 0
        end = int(partial["upto"].get(name, start)) if partial else size
        with open(path, "rb") as fh:
            fh.seek(start)
            data = fh.read(max(0, end - start))
        cut = data.rfind(b"\n") + 1
        upto[name] = start + cut
        for ln in data[:cut].decode("utf-8", "replace").splitlines():
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if not (isinstance(rec, dict) and rec.get("t") == "error" and rec.get("ts")
                    and rec.get("sig")) or el.is_benign(rec):
                continue
            key = json.dumps(rec, sort_keys=True)
            if key not in seen:
                seen.add(key)
                recs.append(rec)
    recs.sort(key=lambda r: r["ts"])
    return recs, upto


def _stale(recs, fix):
    return all(el.has_fix(r, fix.get("commit") or "", fix.get("version") or "") is False
               for r in recs)


def post_class(t, issue, sig, recs):
    """Post one class's new records: create its issue, or update it (reopen a closed one,
    with ``regression`` / ``stale-code``), then the occurrence comment(s). Safe to repeat
    for the same batch: the fields merge once and a comment already there is not posted
    again. Returns ``(action, number, tag)``."""
    batch = batch_id(sig, recs)
    old = meta_of(issue) if issue else None
    retry = bool(old and old.get("batch") == batch)
    meta = merge_meta(old, sig, recs, batch)
    tag = None
    if issue is None:
        issue = t.create_issue(title(sig), render_body(meta), [LABEL])
        action = "created"
    else:
        labels = label_names(issue)
        fix = meta.get("fix") or {}
        new = list(labels)
        if issue.get("state") == "closed":
            if fix.get("commit") or fix.get("version"):
                tag = STALE if _stale(recs, fix) else REGRESSION
            new = [x for x in labels if x not in TAGS] + ([tag] if tag else [])
            action = "reopened"
        else:
            if STALE in labels and fix and not _stale(recs, fix):
                tag = REGRESSION
                new = [x for x in labels if x != STALE] + [REGRESSION]
            action = "commented"
        if LABEL not in new:
            new.append(LABEL)
        if not retry or issue.get("state") == "closed" or new != labels:
            t.update_issue(issue["number"], body=render_body(meta),
                           labels=new if new != labels else None,
                           state="open" if issue.get("state") == "closed" else None)
    header = None
    if action == "reopened":
        header = "Reopened: the class recurred%s." % (
            " after the fix (commit %s, version %s): **%s**" % (
                (meta.get("fix") or {}).get("commit") or "-",
                (meta.get("fix") or {}).get("version") or "-", tag) if tag else "")
    bodies = occurrence_comments(recs, batch, header)
    have = set()
    if retry:
        for c in comments_of(t, issue["number"]):
            have.update(re.findall(r"<!-- batch:([0-9a-f]+ part \d+/\d+) -->", c.get("body") or ""))
    for k, body in enumerate(bodies, 1):
        if "%s part %d/%d" % (batch, k, len(bodies)) not in have:
            t.add_comment(issue["number"], body)
    return action, issue["number"], tag


def sync(spool, t, dry_run=False):
    """Post the spool's new records to the repo of ``t``. Returns a summary dict:
    ``records``, ``classes``, ``posted`` ([{sig, issue, action, tag, count}]), ``dry_run``,
    ``error`` (when a call failed; the batch is finished by the next sync)."""
    cur = load_cursor(spool)
    out = {"records": 0, "classes": 0, "posted": [], "dry_run": dry_run, "error": None}
    while True:
        partial = cur.get("partial")
        recs, upto = read_batch(spool, cur)
        done = set(partial["done"]) if partial else set()
        groups = collections.OrderedDict()
        for r in recs:
            if r["sig"] not in done:
                groups.setdefault(r["sig"], []).append(r)
        out["records"] += sum(len(v) for v in groups.values())
        out["classes"] += len(groups)
        if dry_run:
            out["posted"] += [{"sig": s, "issue": None, "action": "would post", "tag": None,
                               "count": len(v)} for s, v in sorted(groups.items())]
            return out
        issues = index(t) if groups else {}
        for sig in sorted(groups):
            try:
                action, number, tag = post_class(t, issues.get(sig_hash(sig)), sig, groups[sig])
            except GhError as e:
                cur["partial"] = {"upto": upto, "done": sorted(done)}
                save_cursor(spool, cur)
                out["error"] = str(e)
                return out
            done.add(sig)
            out["posted"].append({"sig": sig, "issue": number, "action": action, "tag": tag,
                                  "count": len(groups[sig])})
        cur["offsets"].update(upto)
        cur["partial"] = None
        save_cursor(spool, cur)
        if not partial:
            return out


def pending(spool):
    """How many spool error records are not posted yet (offline)."""
    return len(read_batch(spool, dict(load_cursor(spool), partial=None))[0])


# -- report, resolve, settle -------------------------------------------------------------

def issue_records(t, start):
    """``(records, numbers, tags)``: the ledger records of every open ``error-class``
    issue, rebuilt from its comments, plus one settle record at ``start`` (a class seen
    before the window counts as reported: its issue was there to read); ``numbers``: sig
    -> issue; ``tags``: sig -> its ``regression`` / ``stale-code`` label."""
    recs, numbers, tags = [], {}, {}
    for i in list_classes(t, "open"):
        meta = meta_of(i)
        if not meta or not meta.get("sig"):
            continue
        numbers[meta["sig"]] = i["number"]
        for tag in TAGS:
            if tag in label_names(i):
                tags[meta["sig"]] = tag
        recs += records_of(meta, comments_of(t, i["number"]))
    lo = el._stamp(start)
    recs.append({"t": "settle", "ts": lo, "upto": lo})
    recs.sort(key=lambda r: r["ts"])
    return recs, numbers, tags


def report(t, start, now):
    """``error_ledger.report`` over the open issues; a reopened issue's label
    (``regression`` / ``stale-code``) sets its state. Each class row gains ``issue``."""
    recs, numbers, tags = issue_records(t, start)
    rep = el.report(recs, start, now, tags)
    for r in rep["classes"]:
        r["issue"] = numbers.get(r["sig"])
    rep["source"] = "issues"
    return rep


def _close(t, issue, meta, row, text, labels=None):
    meta = dict(meta, families=[])
    if row.get("commit") or row.get("version"):
        meta["fix"] = {k: row[k] for k in ("commit", "version") if row.get(k)}
    else:
        meta.pop("fix", None)
    t.add_comment(issue["number"], text + "\n\n" + hidden("resolves", [_resolve_row(row)]) + "\n")
    names = label_names(issue)
    keep = [x for x in names if x not in TAGS]
    t.update_issue(issue["number"], body=render_body(meta), state="closed",
                   state_reason="completed", labels=keep if keep != names else None)


def resolve(t, sigs=(), families=(), note="", by="human", commit="", version="", now=None):
    """Close the open issues of ``sigs`` and of every class of ``families`` with a comment.
    Returns ``(closed, missing)``: [(sig, number)] and the signatures with no open issue."""
    now = now or el._now()
    targets, found = [], set()
    for i in list_classes(t, "open"):
        meta = meta_of(i)
        if not meta or not meta.get("sig"):
            continue
        sig = meta["sig"]
        if sig in sigs:
            hit = True
        elif not families:
            hit = False
        elif sig in el.SHELL_EXIT_SIGS:
            fams = set(meta.get("families") or [])
            hit = bool(fams) and fams <= set(families)
        else:
            hit = el.family(sig) in families
        if hit:
            targets.append((i, meta))
            found.add(sig)
    row = {"ts": el._stamp(now), "by": by, "note": note}
    if commit:
        row["commit"] = commit
    if version:
        row["version"] = version
    closed = []
    for i, meta in targets:
        text = "Resolved by %s%s." % (by, (": " + scrub(note)) if note else "")
        if commit or version:
            text += " Fix: commit %s, version %s." % (commit or "-", version or "-")
        _close(t, i, meta, row, text)
        closed.append((meta["sig"], i["number"]))
    return closed, [s for s in sigs if s not in found]


def settle(t, quiet_days=7, packet=None, now=None):
    """Close every open ``error-class`` issue with no occurrence for ``quiet_days`` days
    ("closed by silence"). Returns [(sig, number)]."""
    now = now or el._now()
    cutoff = el._stamp(now - _dt.timedelta(days=quiet_days))
    closed = []
    for i in list_classes(t, "open"):
        meta = meta_of(i)
        if not meta or not meta.get("sig") or not meta.get("last") or meta["last"] >= cutoff:
            continue
        row = {"ts": el._stamp(now), "by": "settle",
               "note": "quiet for %d days%s" % (quiet_days, (" (%s)" % packet) if packet else "")}
        text = ("Closed by silence: no occurrence for %d days (last seen %s)%s."
                % (quiet_days, meta["last"], ("; weekly review %s" % packet) if packet else ""))
        _close(t, i, meta, row, text)
        closed.append((meta["sig"], i["number"]))
    return closed


# -- migrate -----------------------------------------------------------------------------

def migrate_plan(records):
    """One entry per class of the git ledger with at least one counted error:
    ``{sig, open, state, errors, resolves, meta}``; ``state`` is the report's
    (regression, stale code) for an open class."""
    hist = collections.defaultdict(list)
    for r in records:
        if r.get("sig") and (r["t"] == "resolve" or (r["t"] == "error" and not el.is_benign(r))):
            hist[r["sig"]].append(r)
    open_cls = el.classes(records)
    plan = []
    for sig in sorted(hist):
        errs = [r for r in hist[sig] if r["t"] == "error"]
        if not errs:
            continue
        res = [r for r in hist[sig] if r["t"] == "resolve"]
        c = open_cls.get(sig)
        meta = merge_meta(None, sig, errs, "migrate")
        meta["families"] = sorted({el.family_of(sig, r) for r in c["recs"]}) if c else []
        if res and (res[-1].get("commit") or res[-1].get("version")):
            meta["fix"] = {k: res[-1][k] for k in ("commit", "version") if res[-1].get(k)}
        tag = None
        fix = meta.get("fix") or {}
        if c and fix:           # recurred after a fix (commit or version), as sync tags it
            tag = STALE if _stale(c["recs"], fix) else REGRESSION
        plan.append({"sig": sig, "open": bool(c), "tag": tag, "errors": errs,
                     "resolves": res, "meta": meta})
    return plan


def migrate(records, t=None, dry_run=False, skip_resolved=False, log=None):
    """Import the git ledger's classes: an open class becomes an open issue, a resolved
    one a closed issue (or nothing, ``skip_resolved``), each with one comment (more for a
    large class) holding every occurrence and resolve, so the report reads them as the
    ledger did. A class whose issue exists is completed, not duplicated, so a failed run
    is resumed by running it again. Returns a summary dict."""
    plan = migrate_plan(records)
    todo = [p for p in plan if p["open"] or not skip_resolved]
    out = {"classes": len(plan), "open": sum(1 for p in plan if p["open"]),
           "resolved": sum(1 for p in plan if not p["open"]),
           "regression": sum(1 for p in plan if p["tag"] == REGRESSION),
           "stale_code": sum(1 for p in plan if p["tag"] == STALE),
           "errors": sum(len(p["errors"]) for p in plan),
           "resolves": sum(len(p["resolves"]) for p in plan),
           "to_import": len(todo), "skipped_resolved": len(plan) - len(todo),
           "comments": sum(len(_chunks([occ_row(r) for r in p["errors"]])) for p in todo),
           "dry_run": dry_run, "created": 0, "completed": 0, "existing": 0}
    out["writes"] = out["to_import"] + out["comments"] + sum(1 for p in todo if not p["open"])
    if dry_run:
        return out
    have = index(t)
    for p in todo:
        sig, meta = p["sig"], p["meta"]
        issue = have.get(sig_hash(sig))
        bodies = occurrence_comments(p["errors"], "migrate",
                                     "Imported from the git error ledger (board/.errors).",
                                     p["resolves"])
        if issue is None:
            labels = [LABEL] + ([p["tag"]] if p["tag"] else [])
            issue = t.create_issue(title(sig), render_body(meta), labels)
            got = set()
            out["created"] += 1
        else:
            got = set()
            for c in comments_of(t, issue["number"]):
                got.update(re.findall(r"<!-- batch:(migrate part \d+/\d+) -->",
                                      c.get("body") or ""))
            if len(got) >= len(bodies) and (p["open"] or issue.get("state") == "closed"):
                out["existing"] += 1
                continue
            out["completed"] += 1
        for k, body in enumerate(bodies, 1):
            if "migrate part %d/%d" % (k, len(bodies)) not in got:
                t.add_comment(issue["number"], body)
        if not p["open"] and issue.get("state") != "closed":
            t.update_issue(issue["number"], state="closed", state_reason="completed")
        if log:
            log("%s #%s %s" % ("open  " if p["open"] else "closed", issue["number"], sig))
    return out
