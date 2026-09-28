"""SessionStart hook: one line of academy status for the home the session runs in.

Outside an academy home (no ``.claude/academy.json`` at or above ``cwd``) it is a
silent no-op. Inside one it
  1. validates the home's academy.json, and its agreement with workspace.json
     (role, domains, ns: docs/config.md section 1);
  2. reconciles the board's id counters (``.ids/next-ticket``, ``.ids/next-packet``)
     with the highest ids on disk, under the id lock;
  3. commits pending board changes in one commit (docs/protocol.md section 2),
     unless ``ACADEMY_BOARD_COMMIT=0``;
  4. prints ONE line as additionalContext:
       academy: <instance> — N open tickets to you, M packets awaiting <human>
     followed, only when there are any, by the blocked tickets whose awaited tickets
     are all terminal ("; freed: T-0003"), by the board-wide pending-decision count
     from decisions.py ("; D decisions waiting — /academy:decide"), and by config
     problems.
"""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

#: receiver-side states counted as "open tickets to you"
INBOX_STATES = ("open", "accepted", "in-progress")
RE_TICKET_FILE = re.compile(r"^T-\d{4,}-.*\.md$")
RE_PACKET_FILE = re.compile(r"^P-\d{4,}-.*\.md$")
RESERVED = ("packets", "deep-dives", ".ids", ".git")
ATTRIBUTION = "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"


def _meta(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return ac.read_frontmatter(fh.read())[0]
    except (OSError, ac.FrontmatterError):
        return None


def tickets(board):
    """Every readable ticket on the board: list of (folder, meta)."""
    out = []
    try:
        folders = sorted(os.listdir(board))
    except OSError:
        return out
    for folder in folders:
        full = os.path.join(board, folder)
        if folder in RESERVED or not os.path.isdir(full):
            continue
        for name in sorted(os.listdir(full)):
            if RE_TICKET_FILE.match(name):
                meta = _meta(os.path.join(full, name))
                if meta is not None:
                    out.append((folder, meta))
    return out


def open_packets(board):
    """Packets (all instances) whose state is 'open', i.e. awaiting the human."""
    root = os.path.join(board, "packets")
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            if RE_PACKET_FILE.match(name):
                meta = _meta(os.path.join(dirpath, name))
                if meta is not None and meta.get("state") == "open":
                    n += 1
    return n


def freed(all_tickets, instance):
    """Ids of ``instance``'s blocked tickets whose awaited tickets are all terminal."""
    status = {str(m.get("id")): m.get("status") for _, m in all_tickets}
    out = []
    for folder, m in all_tickets:
        if m.get("to") != instance or m.get("status") != "blocked":
            continue
        waits = [str(w) for w in (m.get("waiting_on") or [])]
        tids = [w for w in waits if ac.RE_TICKET_ID.match(w)]
        if tids and len(tids) == len(waits) and \
                all(status.get(t) in ac.TERMINAL for t in tids):
            out.append(str(m.get("id")))
    return out


def reconcile_ids(board):
    """Raise each counter to at least 1 + the highest id of its kind on disk.

    Returns the list of counters changed. Never lowers a counter. Skips quietly when
    the lock cannot be taken.
    """
    changed = []
    try:
        with ac.IdLock(board, timeout=2.0):
            for kind, prefix in ac.ID_KINDS.items():
                counter = os.path.join(board, ac.IDS_DIR, "next-" + kind)
                try:
                    with open(counter, "r", encoding="utf-8") as fh:
                        cur = int(fh.read().strip() or "0")
                except (OSError, ValueError):
                    cur = 0
                want = max(cur, ac._max_id_on_disk(board, prefix) + 1, 1)
                if want != cur:
                    ac.atomic_write(counter, "%d\n" % want)
                    changed.append(kind)
    except ac.LockTimeout:
        pass
    return changed


def _git(board, *args):
    return subprocess.run(["git", "-C", board] + list(args), capture_output=True,
                          timeout=30)


def commit_board(board):
    """Commit all pending board changes as 'board: <n> change(s)'. Returns n (0: none)."""
    if os.environ.get("ACADEMY_BOARD_COMMIT", "1") == "0":
        return 0
    if not os.path.isdir(os.path.join(board, ".git")):
        return 0
    if os.path.exists(os.path.join(board, ac.IDS_DIR, ac.LOCK_NAME)):
        return 0                                     # an allocation is in flight
    try:
        st = _git(board, "status", "--porcelain", "--untracked-files=all")
        if st.returncode != 0:
            return 0
        n = len([ln for ln in st.stdout.decode("utf-8", "replace").splitlines()
                 if ln.strip()])
        if not n:
            return 0
        if _git(board, "add", "-A").returncode != 0:
            return 0
        res = _git(board, "commit", "-q", "-m", "board: %d change(s)" % n,
                   "-m", ATTRIBUTION)
        return n if res.returncode == 0 else 0
    except (OSError, subprocess.SubprocessError):
        return 0


def workspace_problems(cfg, ws):
    """Disagreements between academy.json and its workspace.json row."""
    inst = cfg.get("instance")
    row = ws.get("instances", {}).get(inst)
    if row is None:
        return ["%s is not an instance in %s" % (inst, ws.get("_path", "workspace.json"))]
    probs = []
    if ac._norm(row.get("home", "")) != ac._norm(cfg["_home"]):
        probs.append("workspace.json puts %s at %s" % (inst, row.get("home")))
    for key in ("role", "domains", "ns"):
        if row.get(key) != cfg.get(key):
            probs.append("%s differs from workspace.json (%r vs %r)"
                         % (key, cfg.get(key), row.get(key)))
    return probs


def raw_instance(home):
    """The 'instance' written in academy.json even when the file does not validate."""
    try:
        raw = ac._read_json(os.path.join(home, ac.CONFIG_REL))
        if isinstance(raw, dict) and isinstance(raw.get("instance"), str):
            return raw["instance"]
    except ac.AcademyError:
        pass
    return os.path.basename(os.path.normpath(home))


def decisions_waiting(board, all_tickets):
    """Count of pending decisions on ``board``: the same three sources as
    ``scripts/decisions.py`` ``list`` (open packet decisions with no ``## Decision``
    line yet, tickets to human that are ``open``, tickets anywhere ``blocked`` with
    ``human`` in ``waiting_on``), counted here directly against the vendored module so
    this hook stays self-contained rather than importing the scripts that sit beside
    it. Never raises: a SessionStart hook never breaks a session over an advisory
    count.
    """
    try:
        n = 0
        proot = os.path.join(board, "packets")
        for dirpath, _dirnames, filenames in os.walk(proot):
            for name in filenames:
                if not RE_PACKET_FILE.match(name):
                    continue
                meta = None
                try:
                    with open(os.path.join(dirpath, name), "r", encoding="utf-8") as fh:
                        meta, body = ac.read_frontmatter(fh.read())
                except (OSError, ac.FrontmatterError):
                    continue
                if meta.get("state") != "open":
                    continue
                asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
                n += len([k for k in asked if k not in answers])
        for _folder, m in all_tickets:
            waits = [str(w) for w in (m.get("waiting_on") or [])]
            if m.get("to") == ac.HUMAN and m.get("status") == "open":
                n += 1
            elif m.get("status") == "blocked" and ac.HUMAN in waits:
                n += 1
        return n
    except Exception:
        return None


def status_line(event):
    """The one line to print, or None outside an academy home."""
    home = ac.find_home(ac.event_cwd(event))
    if not home:
        return None
    try:
        cfg = ac.load_config(home)
    except ac.AcademyError as exc:
        return "academy: %s — invalid .claude/academy.json: %s" % (raw_instance(home), exc)
    instance = cfg["instance"]
    try:
        ws = ac.load_workspace(cfg.get("workspace"))
    except ac.AcademyError as exc:
        return "academy: %s — workspace.json unusable: %s" % (instance, exc)
    probs = workspace_problems(cfg, ws)
    human = (ws.get("human") or {}).get("name") or "the human"
    board = ws["board"]
    if not os.path.isdir(board):
        line = "academy: %s — board %s not found" % (instance, board)
    else:
        reconcile_ids(board)
        commit_board(board)
        all_t = tickets(board)
        n = sum(1 for folder, m in all_t
                if folder == instance and m.get("to") == instance
                and m.get("status") in INBOX_STATES)
        m_ = open_packets(board)
        line = "academy: %s — %d open ticket%s to you, %d packet%s awaiting %s" % (
            instance, n, "" if n == 1 else "s", m_, "" if m_ == 1 else "s", human)
        fr = freed(all_t, instance)
        if fr:
            line += "; freed: %s" % ", ".join(fr)
        d = decisions_waiting(board, all_t)
        if d:
            line += "; %d decision%s waiting — /academy:decide" % (d, "" if d == 1 else "s")
    if probs:
        line += "; config: %s" % "; ".join(probs)
    return line


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    event = ac.read_event()
    try:
        line = status_line(event)
    except Exception as exc:                     # a SessionStart hook never breaks a session
        line = "academy: session_start failed: %s" % exc
    if line:
        ac.emit_context("SessionStart", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
