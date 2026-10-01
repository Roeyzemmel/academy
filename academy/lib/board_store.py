"""board_store.py -- the GitHub-backed BoardStore and an in-memory transport (docs/github-board.md).

``GithubBoardStore`` keeps the tickets as issues, through an injected *transport*; every
encoding (title, meta line, labels, state, thread comments) is ``board_codec``'s, so a
ticket read here is the ticket the file board holds. It implements the ``BoardStore`` seam
of ``academy_common`` (``as_store`` / ``open_store``), so ``inbox_core.select``, the role
inbox wrappers, ``board.py`` and the MCP ``tickets_*`` tools run on it unchanged.

The transport is any object with these methods (dicts as the REST API returns them; labels
may be names or ``{"name": ...}``; ``number`` is the issue number):

    list_issues(labels=None, state="all", page=1, per_page=100) -> [issue]
                                          one page; issue: number title body labels state
                                          state_reason (+ "pull_request" for a PR, which the
                                          REST API lists among the issues)
    get_issue(number)                     -> issue | None
    create_issue(title, body, labels)     -> issue        (GitHub assigns the number)
    update_issue(number, title=None, body=None, labels=None, state=None, state_reason=None) -> issue
    list_comments(number, page=1, per_page=100) -> [comment]
                                          one page; comment: a body string or
                                          {"body": ..., "id": ..., "created_at": ...}
    add_comment(number, body)             -> comment

**Pagination.** ``list_issues`` and ``list_comments`` return at most ``per_page`` items of
page ``page`` (1-based) and an empty list past the last page; a transport may return fewer
than ``per_page`` on any page (the REST API caps it), so the store reads pages until one is
empty. Comments are ordered by ``id`` (else ``created_at``) when the transport gives them,
otherwise as returned.

and optionally ``set_parent(number, parent_number)`` and ``add_dependency(number,
blocker_number)`` (native sub-issue and dependency links; when absent the links are not
written, but listed in ``store.skipped_relations`` and reported on stderr). The real
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


PER_PAGE = 100


def _body(c):
    return c.get("body") or "" if isinstance(c, dict) else str(c)


def pages(fetch, **kw):
    """Every item of a paginated transport call, page by page, until an empty page."""
    out, page = [], 1
    while True:
        chunk = fetch(page=page, per_page=PER_PAGE, **kw)
        if not chunk:
            return out
        out.extend(chunk)
        page += 1


def _ordered(comments):
    """Comments oldest first by ``id`` (else ``created_at``) when the transport gives them:
    the order of the pages is not trusted to be the thread's order."""
    cs = list(comments)
    for key in ("id", "created_at"):
        if cs and all(isinstance(c, dict) and c.get(key) is not None for c in cs):
            return sorted(cs, key=lambda c: c[key])
    return cs


class GithubBoardStore(ac.BoardStore):
    backend = "github"

    def __init__(self, transport, repo="", lib=None):
        self.t = transport
        self.repo = repo
        #: the academy_common module this store speaks through (its AcademyError, its
        #: ticket-id pattern): a role plugin passes its vendored copy (see open_store)
        self.lib = lib or ac
        #: native links the transport could not write (it lacks ``set_parent`` /
        #: ``add_dependency``): ``{"type", "issue", ...}`` dicts in the manifest's relation
        #: form, kept so a caller can report them or apply them later; never silent
        self.skipped_relations = []

    def describe(self):
        return "github:%s" % (self.repo or "board")

    @staticmethod
    def ref(number):
        return "github#%d" % number

    # -- reading -------------------------------------------------------------
    def _comments(self, number):
        return [_body(c) for c in _ordered(pages(self.t.list_comments, number=number))]

    def _issues(self, labels=None):
        return sorted(pages(self.t.list_issues, labels=labels, state="all"),
                      key=lambda i: i["number"])

    @staticmethod
    def _is_ticket(issue):
        return "placeholder" not in bc.label_names(issue.get("labels")) \
            and "pull_request" not in issue

    def iter_tickets(self):
        for issue in self._issues():
            if not self._is_ticket(issue):
                continue
            try:
                meta, body = bc.decode(issue, self._comments(issue["number"]))
            except (bc.CodecError, ValueError):
                meta, body = None, ""
            yield self.ref(issue["number"]), meta, body

    def iter_meta(self):
        for issue in self._issues():
            if self._is_ticket(issue):
                try:
                    yield self.ref(issue["number"]), bc.decode(issue, ())[0]
                except (bc.CodecError, ValueError):
                    continue

    def read_all(self, instance):
        out = []
        for issue in self._issues(["to:" + instance]):
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
        if not self.lib.RE_TICKET_ID.match(str(tid or "")):
            return None
        issue = self.t.get_issue(bc.ticket_number(tid))
        return issue if issue and self._is_ticket(issue) else None

    def find(self, tid):
        issue = self._issue(tid)
        return self.ref(issue["number"]) if issue else None

    def get(self, tid):
        issue = self._issue(tid)
        if not issue:
            raise self.lib.AcademyError("no ticket %s on %s" % (tid, self.describe()))
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
        """Write a ticket into its issue. Order, so that a failure half way leaves a state
        a retry repairs: the thread comments first (an entry such as ``reopened:`` exists
        before the label/state move it explains), then the native links, and the issue's
        title/body/labels/state last (the commit point)."""
        e = bc.encode(meta, body)
        n = e["number"]
        cur = self.t.get_issue(n)
        if not cur or not self._is_ticket(cur):
            raise self.lib.AcademyError("%s: issue #%d is not a ticket of %s"
                                        % (meta["id"], n, self.describe()))
        comments = self._comments(n)
        have = [c for c in comments if c.startswith(bc.THREAD_MARK)]
        if e["comments"][:len(have)] != have:
            raise self.lib.AcademyError("%s: the Thread is append-only on GitHub too"
                                        % meta["id"])
        for text in e["comments"][len(have):]:
            self.t.add_comment(n, text)
        try:
            old = bc.decode(cur, ())[0]
        except (bc.CodecError, ValueError):
            old = {}                                 # a fresh '(new ticket)' issue
        if e["parent"] and e["parent"] != old.get("parent"):
            if hasattr(self.t, "set_parent"):
                self.t.set_parent(n, bc.ticket_number(e["parent"]))
            else:
                self._skip({"type": "sub_issue", "parent": bc.ticket_number(e["parent"]),
                            "child": n})
        had = set(str(w) for w in old.get("waiting_on") or [])
        for w in e["waits_on"]:
            if w in had:
                continue
            if hasattr(self.t, "add_dependency"):
                self.t.add_dependency(n, bc.ticket_number(w))
            else:
                self._skip({"type": "dependency", "issue": n, "blocker": bc.ticket_number(w)})
        want = {"title": e["title"], "body": e["body"], "labels": e["labels"],
                "state": e["state"], "state_reason": e["state_reason"]}
        have_issue = {"title": cur.get("title"), "body": cur.get("body"),
                      "labels": sorted(bc.label_names(cur.get("labels"))),
                      "state": cur.get("state"), "state_reason": cur.get("state_reason")}
        if dict(want, labels=sorted(want["labels"])) != have_issue:
            self.t.update_issue(n, **want)
        return self.ref(n)

    def _skip(self, rel):
        if rel not in self.skipped_relations:
            self.skipped_relations.append(rel)
        sys.stderr.write("board_store: %s not written (the transport has no %s)\n" % (
            rel, "set_parent" if rel["type"] == "sub_issue" else "add_dependency"))

    def create(self, meta, body):
        """Open the issue first (GitHub assigns the number, which is the ticket id), then
        write the ticket into it. If that fails the issue is turned into a closed
        placeholder (a reserved number), never left as an open '(new ticket)'."""
        issue = self.t.create_issue("(new ticket)", "", [])
        n = issue["number"]
        meta = dict(meta)
        meta["id"] = self.lib.format_id("T", n)
        try:
            return self.save(meta, body), meta
        except BaseException:
            try:
                ph = bc.placeholder(n)
                self.t.update_issue(n, title=ph["title"], body=ph["body"],
                                    labels=ph["labels"], state="closed",
                                    state_reason=ph["state_reason"])
            except Exception:                        # the original error is the one to report
                pass
            raise


class MemoryTransport(object):
    """An in-memory GitHub issues API (the fake for tests, the reference for a real one).

    ``max_page`` caps ``per_page`` as the REST API does (tests lower it to exercise paging);
    ``add_pull_request`` puts a PR among the issues, as GitHub does; ``inject`` makes a
    method fail after some successful calls (``inject("update_issue", after=1)``).
    """

    def __init__(self, max_page=100):
        self.issues = {}
        self.comments = {}
        self.parents = {}
        self.dependencies = []
        self.calls = []
        self.max_page = max_page
        self._failures = {}
        self._comment_id = 0
        self._cids = {}

    # -- failure injection ---------------------------------------------------
    def inject(self, method, after=0, exc=None):
        """``method`` raises ``exc`` (default RuntimeError) once ``after`` calls succeeded."""
        self._failures[method] = [after, exc or RuntimeError("injected failure in " + method)]

    def _tick(self, method, *detail):
        self.calls.append((method,) + detail)
        f = self._failures.get(method)
        if f:
            if f[0] <= 0:
                del self._failures[method]
                raise f[1]
            f[0] -= 1

    def _pub(self, n):
        return copy.deepcopy(self.issues[n])

    def _page(self, items, page, per_page):
        per = max(1, min(int(per_page or self.max_page), self.max_page))
        start = (int(page or 1) - 1) * per
        return items[start:start + per]

    def add_encoded(self, e):
        """Seed one issue from a ``board_codec.encode`` payload (number, title, body, labels,
        state, state_reason, comments)."""
        n = e["number"]
        self.issues[n] = {k: copy.deepcopy(e[k]) for k in
                          ("number", "title", "body", "labels", "state", "state_reason")}
        self.comments[n] = []
        self._cids[n] = []
        for text in e["comments"]:
            self._add_comment(n, text)
        return self._pub(n)

    def add_pull_request(self, title="a pull request"):
        """A PR, which shares the issue numbers and is listed among the issues."""
        n = max(self.issues, default=0) + 1
        self.issues[n] = {"number": n, "title": title, "body": "", "labels": [],
                          "state": "open", "state_reason": None, "pull_request": {}}
        self.comments[n] = []
        self._cids[n] = []
        return self._pub(n)

    def list_issues(self, labels=None, state="all", page=1, per_page=100):
        self._tick("list_issues", tuple(labels or ()), state, page)
        out = []
        for n in sorted(self.issues):
            i = self.issues[n]
            if state != "all" and i["state"] != state:
                continue
            if labels and not set(labels) <= set(bc.label_names(i["labels"])):
                continue
            out.append(self._pub(n))
        return self._page(out, page, per_page)

    def get_issue(self, number):
        self._tick("get_issue", number)
        return self._pub(number) if number in self.issues else None

    def create_issue(self, title, body, labels):
        self._tick("create_issue", title)
        n = max(self.issues, default=0) + 1
        self.issues[n] = {"number": n, "title": title, "body": body, "labels": list(labels),
                          "state": "open", "state_reason": None}
        self.comments[n] = []
        self._cids[n] = []
        return self._pub(n)

    def update_issue(self, number, title=None, body=None, labels=None, state=None,
                     state_reason=None):
        self._tick("update_issue", number)
        i = self.issues[number]
        for k, v in (("title", title), ("body", body), ("labels", labels), ("state", state)):
            if v is not None:
                i[k] = copy.deepcopy(v)
        i["state_reason"] = state_reason if state == "closed" else None
        return self._pub(number)

    def _add_comment(self, number, body):
        self._comment_id += 1
        self.comments.setdefault(number, []).append(body)
        self._cids.setdefault(number, []).append(self._comment_id)
        return {"id": self._comment_id, "body": body}

    def list_comments(self, number, page=1, per_page=100):
        self._tick("list_comments", number, page)
        rows = [{"id": i, "body": b} for i, b in zip(self._cids.get(number, []),
                                                     self.comments.get(number, []))]
        return self._page(rows, page, per_page)

    def add_comment(self, number, body):
        self._tick("add_comment", number)
        return dict(self._add_comment(number, body))

    def set_parent(self, number, parent):
        self._tick("set_parent", number)
        self.parents[number] = parent

    def add_dependency(self, number, blocker):
        self._tick("add_dependency", number)
        if (number, blocker) not in self.dependencies:
            self.dependencies.append((number, blocker))

    def thread_comments(self, number):
        """The comment bodies of an issue, oldest first (for tests)."""
        return list(self.comments.get(number, []))


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
