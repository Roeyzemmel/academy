"""board_store.py -- the GitHub-backed BoardStore and an in-memory transport (docs/github-board.md).

``GithubBoardStore`` keeps the tickets as issues, through an injected *transport*; every
encoding (title, meta line, labels, state, thread comments) is ``board_codec``'s, so a
ticket read here is the ticket the file board holds. It implements the ``BoardStore`` seam
of ``academy_common`` (``as_store`` / ``open_store``), so ``inbox_core.select``, the role
inbox wrappers, ``board.py`` and the MCP ``tickets_*`` tools run on it unchanged.

The transport is any object with these methods (dicts as the REST API returns them; labels
may be names or ``{"name": ...}``; ``number`` is the issue number):

    list_issues(labels=None, state="all") -> [issue]     issue: number title body labels state state_reason
    get_issue(number)                     -> issue | None
    create_issue(title, body, labels)     -> issue        (GitHub assigns the number)
    update_issue(number, title=None, body=None, labels=None, state=None, state_reason=None) -> issue
    list_comments(number)                 -> [comment]    comment: a body string or {"body": ...}, oldest first
    add_comment(number, body)             -> comment

and optionally ``set_parent(number, parent_number)`` and ``add_dependency(number,
blocker_number)`` (native sub-issue and dependency links; skipped when absent). The real
transport (the github MCP in a session, or REST with a token) is not in this repository:
``MemoryTransport`` below is the reference behaviour and the fake the tests use.
"""

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import academy_common as ac  # noqa: E402
import board_codec as bc  # noqa: E402


def _body(c):
    return c.get("body") or "" if isinstance(c, dict) else str(c)


class GithubBoardStore(ac.BoardStore):
    backend = "github"

    def __init__(self, transport, repo=""):
        self.t = transport
        self.repo = repo

    def describe(self):
        return "github:%s" % (self.repo or "board")

    @staticmethod
    def ref(number):
        return "github#%d" % number

    # -- reading -------------------------------------------------------------
    def _comments(self, number):
        return [_body(c) for c in self.t.list_comments(number)]

    @staticmethod
    def _is_ticket(issue):
        return "placeholder" not in bc.label_names(issue.get("labels")) \
            and "pull_request" not in issue

    def iter_tickets(self):
        for issue in sorted(self.t.list_issues(state="all"), key=lambda i: i["number"]):
            if not self._is_ticket(issue):
                continue
            try:
                meta, body = bc.decode(issue, self._comments(issue["number"]))
            except (bc.CodecError, ValueError):
                meta, body = None, ""
            yield self.ref(issue["number"]), meta, body

    def iter_meta(self):
        for issue in sorted(self.t.list_issues(state="all"), key=lambda i: i["number"]):
            if self._is_ticket(issue):
                try:
                    yield self.ref(issue["number"]), bc.decode(issue, ())[0]
                except (bc.CodecError, ValueError):
                    continue

    def read_all(self, instance):
        out = []
        for issue in sorted(self.t.list_issues(labels=["to:" + instance], state="all"),
                            key=lambda i: i["number"]):
            if not self._is_ticket(issue):
                continue
            try:
                meta = bc.decode(issue, ())[0]     # meta needs no comments
            except (bc.CodecError, ValueError):
                continue
            if not meta.get("id") or meta.get("to", instance) != instance:
                continue
            meta = dict(meta)
            meta["_path"] = self.ref(issue["number"])
            out.append(meta)
        return out

    def _issue(self, tid):
        if not ac.RE_TICKET_ID.match(str(tid or "")):
            return None
        issue = self.t.get_issue(bc.ticket_number(tid))
        return issue if issue and self._is_ticket(issue) else None

    def find(self, tid):
        issue = self._issue(tid)
        return self.ref(issue["number"]) if issue else None

    def get(self, tid):
        issue = self._issue(tid)
        if not issue:
            raise ac.AcademyError("no ticket %s on %s" % (tid, self.describe()))
        meta, body = bc.decode(issue, self._comments(issue["number"]))
        return self.ref(issue["number"]), meta, body

    def status_of(self, tid):
        issue = self._issue(tid)
        if not issue:
            return None
        try:
            return bc.decode(issue, ())[0].get("status")
        except (bc.CodecError, ValueError):
            return None

    # -- writing -------------------------------------------------------------
    def save(self, meta, body, ref=None, relocate=False):
        e = bc.encode(meta, body)
        n = e["number"]
        have = [c for c in self._comments(n) if c.startswith(bc.THREAD_MARK)]
        if e["comments"][:len(have)] != have:
            raise ac.AcademyError("%s: the Thread is append-only on GitHub too" % meta["id"])
        cur = self.t.get_issue(n) or {}
        want = {"title": e["title"], "body": e["body"], "labels": e["labels"],
                "state": e["state"], "state_reason": e["state_reason"]}
        have_issue = {"title": cur.get("title"), "body": cur.get("body"),
                      "labels": sorted(bc.label_names(cur.get("labels"))),
                      "state": cur.get("state"), "state_reason": cur.get("state_reason")}
        if dict(want, labels=sorted(want["labels"])) != have_issue:
            self.t.update_issue(n, **want)
        for text in e["comments"][len(have):]:
            self.t.add_comment(n, text)
        if e["parent"] and hasattr(self.t, "set_parent"):
            self.t.set_parent(n, bc.ticket_number(e["parent"]))
        if hasattr(self.t, "add_dependency"):
            for w in e["waits_on"]:
                self.t.add_dependency(n, bc.ticket_number(w))
        return self.ref(n)

    def create(self, meta, body):
        """Open the issue first (GitHub assigns the number, which is the ticket id), then
        write the ticket into it."""
        issue = self.t.create_issue("(new ticket)", "", [])
        meta = dict(meta)
        meta["id"] = ac.format_id("T", issue["number"])
        return self.save(meta, body), meta


class MemoryTransport(object):
    """An in-memory GitHub issues API (the fake for tests, the reference for a real one)."""

    def __init__(self):
        self.issues = {}
        self.comments = {}
        self.parents = {}
        self.dependencies = []
        self.calls = []

    def _pub(self, n):
        return copy.deepcopy(self.issues[n])

    def add_encoded(self, e):
        """Seed one issue from a ``board_codec.encode`` payload (number, title, body, labels,
        state, state_reason, comments)."""
        n = e["number"]
        self.issues[n] = {k: copy.deepcopy(e[k]) for k in
                          ("number", "title", "body", "labels", "state", "state_reason")}
        self.comments[n] = list(e["comments"])
        return self._pub(n)

    def list_issues(self, labels=None, state="all"):
        self.calls.append(("list_issues", tuple(labels or ()), state))
        out = []
        for n in sorted(self.issues):
            i = self.issues[n]
            if state != "all" and i["state"] != state:
                continue
            if labels and not set(labels) <= set(bc.label_names(i["labels"])):
                continue
            out.append(self._pub(n))
        return out

    def get_issue(self, number):
        self.calls.append(("get_issue", number))
        return self._pub(number) if number in self.issues else None

    def create_issue(self, title, body, labels):
        self.calls.append(("create_issue", title))
        n = max(self.issues, default=0) + 1
        self.issues[n] = {"number": n, "title": title, "body": body, "labels": list(labels),
                          "state": "open", "state_reason": None}
        self.comments[n] = []
        return self._pub(n)

    def update_issue(self, number, title=None, body=None, labels=None, state=None,
                     state_reason=None):
        self.calls.append(("update_issue", number))
        i = self.issues[number]
        for k, v in (("title", title), ("body", body), ("labels", labels), ("state", state)):
            if v is not None:
                i[k] = copy.deepcopy(v)
        i["state_reason"] = state_reason if state == "closed" else None
        return self._pub(number)

    def list_comments(self, number):
        self.calls.append(("list_comments", number))
        return [{"body": c} for c in self.comments.get(number, [])]

    def add_comment(self, number, body):
        self.calls.append(("add_comment", number))
        self.comments.setdefault(number, []).append(body)
        return {"body": body}

    def set_parent(self, number, parent):
        self.parents[number] = parent

    def add_dependency(self, number, blocker):
        if (number, blocker) not in self.dependencies:
            self.dependencies.append((number, blocker))


def from_file_board(board, transport=None):
    """A MemoryTransport holding the tickets of a file board, encoded by the codec (gaps
    become closed placeholders, as the migration does)."""
    t = transport or MemoryTransport()
    tickets = {}
    for _p, meta, body in ac.FileBoardStore(board).iter_tickets():
        if meta is not None:
            tickets[bc.ticket_number(meta["id"])] = (meta, body)
    for n in range(1, max(tickets, default=0) + 1):
        t.add_encoded(bc.encode(*tickets[n]) if n in tickets else bc.placeholder(n))
    return t
