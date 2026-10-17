"""usage_ledger.py -- content-free usage summaries of this machine's sessions, on the board.

Usage (normally run by ``ship.py checkpoint``, never by hand):

    py usage_ledger.py [--projects DIR] [--workspace PATH] [--days 14] [--board DIR]

Cloud and collaborator sessions leave no transcript on the human's machine, so the
weekly usage report cannot see them. ``ship.py checkpoint`` therefore appends, before it
commits the board, one *summary* per recently active session to
``<board>/.usage/<instance>.<host>.jsonl`` (one file per instance bucket and machine, so
branches written on different machines never conflict; the board's own commit carries it). A record is exactly:

    {"t": "usage", "session": ID, "ts": last-modified (UTC, ISO), "instance": bucket,
     "turns": N, "read": cache-read tokens, "write": cache-write + input tokens,
     "limit_failures": N, "models": {family: turns}, "subagents": {agent_type: runs},
     "host": 8 hex chars}

and nothing else: no prompt, no path, no tool input, no agent description, no ticket
text. ``host`` is a short hash of the hostname, so two machines are told apart without
being named. Sessions outside the workspace (bucket ``other``) are never written.

The file is append-only history with *upsert* meaning: a session's record is appended
only when its (turns, read) changed since its last record in that file, and a reader
takes the LAST record per session id (``read_all``). Nothing is rewritten. Writing never
raises: a missing board or a read-only directory is a warning (``append`` returns 0).
"""

import argparse
import calendar
import collections
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

USAGE_DIR = ".usage"
#: how far back a checkpoint looks for sessions to summarise
DEFAULT_DAYS = 14
#: a session id is a transcript file name; anything else is not summarised
RE_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
FIELDS = ("t", "session", "ts", "instance", "turns", "read", "write", "limit_failures",
          "models", "subagents", "host")


def host_hash(name=None):
    return hashlib.sha1((name if name is not None else socket.gethostname()).encode("utf-8", "replace")
                        ).hexdigest()[:8]


def _iso_utc(epoch):
    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(ts):
    """A record's ``ts`` as a naive local datetime (the report's windows are local), or None."""
    try:
        return _dt.datetime.fromtimestamp(
            calendar.timegm(_dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").timetuple()))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def summarise_sessions(projects_root, since, workspace, host=None):
    """Content-free summaries of every session transcript under ``projects_root`` modified
    since ``since`` (a naive local datetime): the record shape in the module docstring.
    Turns, tokens and limit failures cover the main session and its subagents."""
    import usage_report  # lazy: usage_report merges these records back in
    host = host or host_hash()
    out = []
    for s in usage_report.collect(projects_root, since, None, workspace):
        sid = s["session"]
        if not RE_SESSION.fullmatch(sid or ""):
            continue
        try:
            mtime = os.path.getmtime(os.path.join(projects_root, s["project"], sid + ".jsonl"))
        except OSError:
            continue
        tot = collections.Counter()
        models = collections.Counter()
        subs = collections.Counter()
        for part in [s["main"]] + s["subagents"]:
            for k in usage_report.COUNTED:
                tot[k] += part["counts"].get(k, 0)
            for model, n in part["models"].items():
                models[usage_report.model_family(model)] += n
        for sub in s["subagents"]:
            subs[str(sub.get("agent_type") or "?")] += 1
        out.append({"t": "usage", "session": sid, "ts": _iso_utc(mtime), "instance": s["instance"],
                    "turns": tot["turns"], "read": tot["read"], "write": tot["write"],
                    "limit_failures": tot["limit_failures"],
                    "models": dict(sorted(models.items())), "subagents": dict(sorted(subs.items())),
                    "host": host})
    return out


def ledger_file(board, instance, host=None):
    """``<board>/.usage/<instance>.<host>.jsonl``: one file per instance AND machine, so
    branches written on different machines never append to (and conflict on) the same file."""
    name = re.sub(r"[^A-Za-z0-9@._-]", "_", instance)
    if host:
        name += "." + re.sub(r"[^A-Za-z0-9]", "", str(host))[:16]
    return os.path.join(board, USAGE_DIR, name + ".jsonl")


def _read_file(path):
    """The usage records of one file, in file order; bad lines are skipped."""
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    rec = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("t") == "usage" and rec.get("session"):
                    out.append(rec)
    except OSError:
        pass
    return out


def append(board, instance, records):
    """Append the records whose session is new in ``<board>/.usage/<instance>.jsonl`` or whose
    (turns, read) differ from that session's last record there: one ``O_APPEND`` write of
    whole lines. Only the content-free fields are written, whatever the caller passes.
    Returns the number written; never raises (a missing board, a read-only directory or a
    full disk give 0)."""
    try:
        if not board or not os.path.isdir(board):
            return 0
        path = ledger_file(board, instance, next((r.get("host") for r in records if r.get("host")), None))
        last = {r["session"]: (r.get("turns"), r.get("read")) for r in _read_file(path)}
        lines = []
        for r in records:
            rec = {k: r[k] for k in FIELDS if k in r}
            sid = rec.get("session")
            if rec.get("t") != "usage" or not sid or last.get(sid) == (rec.get("turns"), rec.get("read")):
                continue
            last[sid] = (rec.get("turns"), rec.get("read"))
            lines.append(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        if not lines:
            return 0
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = "".join(lines).encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        return len(lines)
    except (OSError, ValueError, TypeError):
        return 0


def read_all(board):
    """The LAST record per session id over every file of ``<board>/.usage/`` (when a session
    is in several files, the one with the latest ``ts``); a dict session -> record."""
    out = {}
    try:
        names = sorted(os.listdir(os.path.join(board, USAGE_DIR)))
    except (OSError, TypeError):
        return out
    for name in names:
        if not name.endswith(".jsonl"):
            continue
        mine = {}
        for rec in _read_file(os.path.join(board, USAGE_DIR, name)):
            mine[rec["session"]] = rec          # later lines win
        for sid, rec in mine.items():
            if sid not in out or str(rec.get("ts")) >= str(out[sid].get("ts")):
                out[sid] = rec
    return out


def write_summaries(board, projects_root, since, workspace, host=None):
    """Summarise this machine's sessions and append them per instance bucket. Returns the
    number of records written. Sessions outside the workspace (``other``) are left out."""
    n = 0
    by_inst = collections.defaultdict(list)
    for rec in summarise_sessions(projects_root, since, workspace, host):
        if rec["instance"] != "other":
            by_inst[rec["instance"]].append(rec)
    for inst, recs in sorted(by_inst.items()):
        n += append(board, inst, recs)
    return n


def checkpoint(root, board, projects_root=None, days=DEFAULT_DAYS, now=None):
    """The ``ship.py checkpoint`` hook: summaries of the last ``days`` days of this machine's
    sessions into ``board``. Never raises; returns ``(written, warning)`` where warning is ''
    or one line."""
    try:
        import _academy as ac
        try:
            ws = ac.load_workspace(os.path.join(root, "workspace.json"))
        except ac.AcademyError:
            ws = None
        projects_root = projects_root or os.path.expanduser("~/.claude/projects")
        if not os.path.isdir(projects_root):
            return 0, ""
        since = (now or _dt.datetime.now()) - _dt.timedelta(days=days)
        return write_summaries(board, projects_root, since, ws), ""
    except Exception as exc:                      # noqa: BLE001 -- never fail a checkpoint
        return 0, "usage summary skipped: %s: %s" % (type(exc).__name__, exc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--projects", help="default: ~/.claude/projects")
    ap.add_argument("--workspace")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--board", help="default: the workspace's board")
    a = ap.parse_args(argv)
    import _academy as ac
    ws = ac.load_workspace(a.workspace)
    board = a.board or ws.get("board")
    n = write_summaries(board, a.projects or os.path.expanduser("~/.claude/projects"),
                        _dt.datetime.now() - _dt.timedelta(days=a.days), ws)
    print("usage_ledger: %d record(s) written under %s" % (n, os.path.join(board or "?", USAGE_DIR)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
