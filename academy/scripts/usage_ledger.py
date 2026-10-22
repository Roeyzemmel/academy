"""usage_ledger.py -- content-free usage summaries of this machine's sessions, on the board.

Usage (normally run by ``ship.py checkpoint``, never by hand):

    py usage_ledger.py [--projects DIR] [--workspace PATH] [--days 14] [--board DIR]
    py usage_ledger.py compact [--workspace PATH] [--board DIR] [--keep-days 90]

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
takes the LAST record per session id (``read_all``). Writing never raises: a missing board
or a read-only directory is a warning (``append`` returns 0).

Compaction keeps the files from growing without bound: ``compact`` rewrites ONE file (temp
file + ``os.replace``) keeping only the last record per session and dropping sessions whose
last ``ts`` is older than ``keep_days`` (90; ``"usageKeepDays"`` in workspace.json, an
integer >= 7). ``checkpoint`` runs it, after the summaries, on this host's files only (the
name's host part equals ``host_hash()``; other machines' files are theirs) and only when a
file has at least twice as many records as sessions or a record older than ``keep_days``.
``usage_ledger.py compact`` does it by hand and prints the lines removed.
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


def _host_of(path):
    """The host part of ``<instance>.<host>.jsonl`` ('' when the name has none)."""
    stem = os.path.basename(path)[:-len(".jsonl")] if path.endswith(".jsonl") else ""
    return stem.rsplit(".", 1)[1] if "." in stem else ""


def _scan(path):
    """``(lines, keep)``: the non-blank lines of the file as text, and the set of line indexes
    that are the LAST valid record of their session; plus ``ts`` per such line."""
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    last = {}
    for i, ln in enumerate(lines):
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("t") == "usage" and rec.get("session"):
            last[rec["session"]] = (i, rec.get("ts"))
    return lines, last


def _cutoff(keep_days, now):
    return (now or _dt.datetime.now()) - _dt.timedelta(days=keep_days)


def needs_compaction(path, keep_days=90, now=None):
    """The cheap trigger: at least twice as many records as sessions, or any record older
    than ``keep_days``. False for an unreadable file or one without a usage record."""
    try:
        recs = _read_file(path)
        if not recs:
            return False
        if len(recs) >= 2 * len({r["session"] for r in recs}):
            return True
        cut = _cutoff(keep_days, now)
        return any((t := parse_ts(r.get("ts"))) is not None and t < cut for r in recs)
    except (OSError, ValueError, TypeError, OverflowError):
        return False


def compact(path, keep_days=90, now=None, host=None):
    """Rewrite one ledger file keeping only the LAST record per session id, in the order of
    those last records, and dropping sessions whose last ``ts`` is older than ``keep_days``
    (a record whose ts does not parse is kept). Malformed lines are dropped. Atomic (temp file
    in the same directory, ``os.replace``). Nothing is touched when nothing would go, when the
    file has no valid usage record, or when the file is not this host's (its name's host part
    differs from ``host``, default ``host_hash()``). Returns the lines removed; never raises."""
    try:
        if _host_of(path) != (host or host_hash()):
            return 0
        lines, last = _scan(path)
        if not last:
            return 0
        cut = _cutoff(keep_days, now)
        keep = []
        for i, ts in sorted(last.values()):
            t = parse_ts(ts)
            if t is None or t >= cut:
                keep.append(lines[i])
        removed = len(lines) - len(keep)
        if removed <= 0:
            return 0
        tmp = "%s.%d.tmp" % (path, os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("".join(ln + "\n" for ln in keep))
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return removed
    except (OSError, ValueError, TypeError, OverflowError):
        return 0


def valid_keep_days(value, default=90):
    """``value`` when it is an integer (not a bool) of at least 7, else ``default``."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 7 else default


def compact_board(board, keep_days=90, now=None, host=None, only_if_needed=True):
    """Compact this host's files under ``<board>/.usage/``; returns the lines removed."""
    host = host or host_hash()
    keep_days = valid_keep_days(keep_days)
    n = 0
    for path in sorted(glob.glob(os.path.join(board or "", USAGE_DIR, "*.jsonl"))):
        if _host_of(path) != host:
            continue
        if only_if_needed and not needs_compaction(path, keep_days, now):
            continue
        n += compact(path, keep_days, now, host)
    return n


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


def checkpoint(root, board, projects_root=None, days=DEFAULT_DAYS, now=None, keep_days=90, host=None):
    """The ``ship.py checkpoint`` hook: summaries of the last ``days`` days of this machine's
    sessions into ``board``, then compaction of this host's bloated or stale files (see the
    module docstring; ``keep_days`` below 7 or not an integer means 90). Never raises; returns ``(written, warning)`` where warning is ''
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
        n = write_summaries(board, projects_root, since, ws, host)
        compact_board(board, keep_days, now, host)
        return n, ""
    except Exception as exc:                      # noqa: BLE001 -- never fail a checkpoint
        return 0, "usage summary skipped: %s: %s" % (type(exc).__name__, exc)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "compact":
        cp = argparse.ArgumentParser(prog="usage_ledger.py compact",
                                     description="compact this host's usage files")
        cp.add_argument("--workspace")
        cp.add_argument("--board", help="default: the workspace's board")
        cp.add_argument("--keep-days", type=int, default=90)
        c = cp.parse_args(argv[1:])
        board = c.board
        if not board:
            import _academy as ac
            board = ac.load_workspace(c.workspace).get("board")
        n = compact_board(board, c.keep_days, only_if_needed=False)
        print("usage_ledger: %d line(s) removed under %s" % (n, os.path.join(board or "?", USAGE_DIR)))
        return 0
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
