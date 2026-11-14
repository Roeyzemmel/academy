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

**The listing is incremental** (2026-11-13). Every listing used to read the whole board:
1192 issues took twelve requests and 20 seconds, and a command that lists once per workplan
took minutes. A transport that sets ``since = True`` accepts ``list_issues(since=ISO)``
(the issues updated at or after that time, GitHub's ``since``); the store then keeps the
last listing (in the process, and on disk under ``cache_dir`` when one is given) and each
later listing asks only for what changed since the newest ``updated_at`` it holds, less
``SINCE_MARGIN`` seconds, **and never later than when the previous read began, less
``READ_SKEW``**. The second bound is what makes it correct: a listing is several requests,
and an issue on a page already read can change while a later page is fetched; the newest
stamp held is then past that change, and asking from it would miss the change for good
(found by review, 2026-11-14). Whatever changed during a read is at or after the read's
start, so the next read starts from there. The start is this machine's clock; ``READ_SKEW``
(five minutes) is the room for its difference from GitHub's and for a listing endpoint
that lags behind a write. A full listing is still
read when nothing is held, when an issue lacks ``updated_at``, and once every
``FULL_REFRESH`` seconds (an issue that was deleted or transferred leaves no trace in
``since``). Inside ``list_ttl`` seconds a process reuses its listing with no request;
any write through this store drops that. The cached issues keep only ``KEEP`` (a ninth of
the REST payload); a single ticket (``get``, ``status_of``, ``save``) is always read live.

and optionally ``set_parent(number, parent_number)`` and ``add_dependency(number,
blocker_number)`` (native sub-issue and dependency links; when absent the links are not
written, but listed in ``store.skipped_relations`` and reported on stderr). The real
transport (the github MCP in a session, or REST with a token) is not in this repository:
``MemoryTransport`` below is the reference behaviour and the fake the tests use.
"""

import copy
import datetime as _dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import academy_common as ac  # noqa: E402
import board_codec as bc  # noqa: E402


PER_PAGE = 100
#: seconds taken off the newest ``updated_at`` held, so an update in that same second is seen
SINCE_MARGIN = 2
#: seconds taken off the start of the previous read: this machine's clock against the
#: server's, and a listing that lags behind a write
READ_SKEW = 300
#: seconds after which the whole board is listed again (deleted or transferred issues)
FULL_REFRESH = 24 * 3600
#: seconds a process reuses its last listing without asking (dropped on its own writes)
LIST_TTL = 5.0
#: the issue fields a cached listing keeps (what the codec, this store and the board
#: scripts read; the REST payload is nine times larger)
KEEP = ("number", "id", "node_id", "title", "body", "state", "state_reason", "updated_at",
        "created_at", "closed_at", "comments", "parent_issue_url", "sub_issues_summary",
        "issue_dependencies_summary")
CACHE_VERSION = 2          # 2: the cache holds asked_at (when its last read began)


def slim(issue):
    """``issue`` with only the fields a listing needs (labels and assignees by name)."""
    out = {k: issue[k] for k in KEEP if k in issue}
    out["labels"] = [{"name": n} for n in bc.label_names(issue.get("labels"))]
    if issue.get("assignees"):
        out["assignees"] = [{"login": a.get("login")} if isinstance(a, dict) else a
                            for a in issue["assignees"]]
    if "pull_request" in issue:
        out["pull_request"] = {}
    return out


def _since(stamp, asked_at=None):
    """Where the next read starts: ``stamp`` (the newest ``updated_at`` held,
    ``2026-11-13T20:38:35Z``) less SINCE_MARGIN seconds, and no later than ``asked_at``
    (epoch seconds, when the previous read began) less READ_SKEW. None if unreadable."""
    try:
        t = _dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ") \
            - _dt.timedelta(seconds=SINCE_MARGIN)
        if asked_at is not None:
            began = _dt.datetime(1970, 1, 1) + _dt.timedelta(seconds=float(asked_at) - READ_SKEW)
            t = min(t, began)
    except (TypeError, ValueError, OverflowError):
        return None
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


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

    def __init__(self, transport, repo="", lib=None, assignee=None, cache_dir=None,
                 list_ttl=LIST_TTL, clock=time.time):
        self.t = transport
        self.repo = repo
        #: where the listing is kept between processes (None: in this process only)
        self.cache_dir = cache_dir
        self.list_ttl = list_ttl
        self.clock = clock
        self._held = None        # {"issues": {number: issue}, "full_at": epoch seconds}
        self._listed_at = None   # when this process last listed (None: must ask again)
        #: the human's GitHub login (``board.assignee``): a saved ticket is assigned to them
        #: exactly when ``board_codec.wants_human``; None leaves assignees alone
        self.assignee = assignee
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
        if not getattr(self.t, "since", False):
            return sorted(pages(self.t.list_issues, labels=labels, state="all"),
                          key=lambda i: i["number"])
        want = set(labels or ())
        return [copy.deepcopy(i) for _n, i in sorted(self._listing().items())
                if want <= set(bc.label_names(i.get("labels")))]

    def _cache_file(self):
        if not self.cache_dir or not self.repo:
            return None
        return os.path.join(self.cache_dir, self.repo.replace("/", "__") + ".json")

    def _load(self):
        path = self._cache_file()
        if not path:
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            if d.get("version") != CACHE_VERSION or d.get("repo") != self.repo:
                return None
            return {"issues": {int(n): i for n, i in d["issues"].items()},
                    "full_at": float(d["full_at"]), "asked_at": float(d["asked_at"])}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None          # an unreadable cache is no cache

    def _store_cache(self):
        path = self._cache_file()
        if not path:
            return
        tmp = "%s.%d.tmp" % (path, os.getpid())
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # the tickets of a private repository: readable by the user only (where the
            # system has file modes)
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"version": CACHE_VERSION, "repo": self.repo,
                           "full_at": self._held["full_at"],
                           "asked_at": self._held["asked_at"],
                           "issues": {str(n): i for n, i in self._held["issues"].items()}},
                          fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)
        except OSError:
            # the cache is an optimisation and the listing is in hand. On Windows the
            # replace fails while another process reads the file: leave no temp behind
            try:
                os.remove(tmp)
            except OSError:
                pass

    def _listing(self):
        """``{number: issue}`` of the whole board, asking only for what changed (see the
        module docstring)."""
        now = self.clock()
        if self._held is not None and self._listed_at is not None \
                and 0 <= now - self._listed_at < self.list_ttl:
            return self._held["issues"]
        held = self._held if self._held is not None else self._load()
        since = None
        if held and held["issues"] and 0 <= now - held["full_at"] < FULL_REFRESH:
            stamps = [i.get("updated_at") for i in held["issues"].values()]
            if all(stamps):
                since = _since(max(stamps), held.get("asked_at"))
        if since:
            changed = pages(self.t.list_issues, state="all", since=since)
            issues = dict(held["issues"])
            before = {i["number"]: issues.get(i["number"]) for i in changed}
            issues.update((i["number"], slim(i)) for i in changed)
            dirty = any(issues[n] != old for n, old in before.items())
            # asked_at moves on only with something to write: an idle board is not
            # rewritten on every listing, and an older start only asks for more
            self._held = {"issues": issues, "full_at": held["full_at"],
                          "asked_at": now if dirty else held.get("asked_at", now)}
        else:
            self._held = {"issues": {i["number"]: slim(i)
                                     for i in pages(self.t.list_issues, state="all")},
                          "full_at": now, "asked_at": now}
            dirty = True
        if dirty:
            self._store_cache()
        self._listed_at = now
        return self._held["issues"]

    def _wrote(self):
        """A write went out: the next listing asks GitHub again."""
        self._listed_at = None

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

    def search(self, text):
        """As ``BoardStore.search``, from the listing: title, ask, agenda and the issue's
        body (the ask's detail, the result), not the thread comments."""
        want = self.lib.search_key(text)
        out = []
        for issue in self._issues() if want else ():
            if not self._is_ticket(issue):
                continue
            try:
                meta, body = bc.decode(issue, ())
            except (bc.CodecError, ValueError):
                continue
            if want in self.lib.search_key(self.lib.ticket_text(meta, body)):
                out.append(str(meta.get("id")))
        return out

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
        self._wrote()
        cur = self.t.get_issue(n)
        if not cur or not self._is_ticket(cur):
            raise self.lib.AcademyError("%s: issue #%d is not a ticket of %s"
                                        % (meta["id"], n, self.describe()))
        comments = self._comments(n)
        # read as decode reads them: a session's posts carry the attribution footer
        have = [bc.strip_footer(c) for c in comments if c.startswith(bc.THREAD_MARK)]
        if e["comments"][:len(have)] != have:
            raise self.lib.AcademyError("%s: the Thread is append-only on GitHub too"
                                        % meta["id"])
        for text in e["comments"][len(have):]:
            self.t.add_comment(n, text)
        try:
            old = bc.decode(cur, ())[0]
        except (bc.CodecError, ValueError):
            old = {}                                 # a fresh '(new ticket)' issue
        # native links follow the ticket both ways: added, moved and removed
        old_parent = old.get("parent") or None
        if e["parent"] and e["parent"] != old_parent:
            if hasattr(self.t, "set_parent"):
                self.t.set_parent(n, bc.ticket_number(e["parent"]))   # replaces an old one
            else:
                self._skip({"type": "sub_issue", "parent": bc.ticket_number(e["parent"]),
                            "child": n})
        elif not e["parent"] and old_parent and ac.RE_TICKET_ID.match(str(old_parent)) \
                and hasattr(self.t, "remove_parent"):
            self.t.remove_parent(n, bc.ticket_number(old_parent))
        had = [str(w) for w in old.get("waiting_on") or [] if ac.RE_TICKET_ID.match(str(w))]
        for w in e["waits_on"]:
            if w in had:
                continue
            if hasattr(self.t, "add_dependency"):
                self.t.add_dependency(n, bc.ticket_number(w))
            else:
                self._skip({"type": "dependency", "issue": n, "blocker": bc.ticket_number(w)})
        for w in had:
            if w not in e["waits_on"] and hasattr(self.t, "remove_dependency"):
                self.t.remove_dependency(n, bc.ticket_number(w))
        want = {"title": e["title"], "body": e["body"], "labels": e["labels"],
                "state": e["state"], "state_reason": e["state_reason"]}
        have_issue = {"title": cur.get("title"), "body": bc.strip_footer(cur.get("body") or ""),
                      "labels": sorted(bc.label_names(cur.get("labels"))),
                      "state": cur.get("state"), "state_reason": cur.get("state_reason")}
        assignees = bc.assignees_for(meta, cur.get("assignees"), self.assignee) \
            if self.assignee else None
        if dict(want, labels=sorted(want["labels"])) != have_issue or assignees is not None:
            if assignees is not None:
                want["assignees"] = assignees
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
        self._wrote()
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


class RelationUnavailable(RuntimeError):
    """A native relation kind the repository does not serve (the REST API's 404/410)."""
    status = 410


class MemoryTransport(object):
    """An in-memory GitHub issues API (the fake for tests, the reference for a real one).

    ``max_page`` caps ``per_page`` as the REST API does (tests lower it to exercise paging);
    ``add_pull_request`` puts a PR among the issues, as GitHub does; ``inject`` makes a
    method fail after some successful calls (``inject("update_issue", after=1)``).

    Native links: ``parents`` maps child -> parent and ``dependencies`` holds ``(issue,
    blocker)``; a parent or blocker in another repository is an ``("owner/name", number)``
    pair. ``unavailable`` names the relation kinds the fake repository does not serve
    (``"sub_issues"``, ``"dependencies"``): their methods then fail with status 410.
    ``summaries`` makes ``list_issues`` carry ``parent_issue_url`` and
    ``issue_dependencies_summary``, as the REST listing does.
    """

    def __init__(self, max_page=100, repo="o/r"):
        self.issues = {}
        self.comments = {}
        self.parents = {}
        self.dependencies = []
        self.repo = repo
        self.unavailable = set()
        self.summaries = False
        self.labels = {}
        self.calls = []
        self.max_page = max_page
        self._failures = {}
        self._comment_id = 0
        self._cids = {}
        #: set True to serve ``list_issues(since=...)`` (the store's incremental listing);
        #: ``now`` is the fake server clock, one second per write
        self.since = False
        self.now = _dt.datetime(2026, 1, 1)

    def _touch(self, n):
        self.now += _dt.timedelta(seconds=1)
        self.issues[n]["updated_at"] = self.now.strftime("%Y-%m-%dT%H:%M:%SZ")

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
        self._touch(n)
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
        self._touch(n)
        return self._pub(n)

    def list_issues(self, labels=None, state="all", page=1, per_page=100, since=None):
        self._tick(*(("list_issues", tuple(labels or ()), state, page)
                     + ((since,) if since else ())))
        out = []
        for n in sorted(self.issues):
            i = self.issues[n]
            if state != "all" and i["state"] != state:
                continue
            if since and i.get("updated_at", "") < since:
                continue
            if labels and not set(labels) <= set(bc.label_names(i["labels"])):
                continue
            pub = self._pub(n)
            if self.summaries:
                p = self._ref(self.parents.get(n))
                pub["sub_issues_summary"] = {"total": sum(1 for v in self.parents.values()
                                                          if v == n)}
                if p:                     # GitHub leaves the key out when there is none
                    pub["parent_issue_url"] = ("https://api.github.com/repos/%s/issues/%d"
                                               % (p["repo"], p["number"]))
                k = sum(1 for m, _b in self.dependencies if m == n)
                pub["issue_dependencies_summary"] = {"blocked_by": k, "total_blocked_by": k}
            out.append(pub)
        return self._page(out, page, per_page)

    def get_issue(self, number):
        self._tick("get_issue", number)
        return self._pub(number) if number in self.issues else None

    def create_issue(self, title, body, labels, assignees=None):
        self._tick("create_issue", title)
        n = max(self.issues, default=0) + 1
        self.issues[n] = {"number": n, "title": title, "body": body, "labels": list(labels),
                          "state": "open", "state_reason": None,
                          "assignees": list(assignees or [])}
        for name in labels:
            self.labels.setdefault(name, {"name": name, "color": "ededed", "description": ""})
        self.comments[n] = []
        self._cids[n] = []
        self._touch(n)
        return self._pub(n)

    def update_issue(self, number, title=None, body=None, labels=None, state=None,
                     state_reason=None, assignees=None):
        self._tick("update_issue", number)
        i = self.issues[number]
        for k, v in (("title", title), ("body", body), ("labels", labels), ("state", state),
                     ("assignees", assignees)):
            if v is not None:
                i[k] = copy.deepcopy(v)
        i["state_reason"] = state_reason if state == "closed" else None
        self._touch(number)
        return self._pub(number)

    def _add_comment(self, number, body):
        self._comment_id += 1
        self.comments.setdefault(number, []).append(body)
        self._cids.setdefault(number, []).append(self._comment_id)
        if number in self.issues:
            self._touch(number)
        return {"id": self._comment_id, "body": body}

    def list_comments(self, number, page=1, per_page=100):
        self._tick("list_comments", number, page)
        rows = [{"id": i, "body": b} for i, b in zip(self._cids.get(number, []),
                                                     self.comments.get(number, []))]
        return self._page(rows, page, per_page)

    def add_comment(self, number, body):
        self._tick("add_comment", number)
        return dict(self._add_comment(number, body))

    def _ref(self, x):
        if x is None:
            return None
        repo, n = x if isinstance(x, tuple) else (self.repo, x)
        return {"number": n, "repo": repo}

    def _need(self, kind):
        if kind in self.unavailable:
            raise RelationUnavailable("%s: not available on this repository (HTTP 410)" % kind)

    def relations_available(self, number):
        self._tick("relations_available", number)
        return {k: k not in self.unavailable for k in ("sub_issues", "dependencies")}

    def parent_ref(self, number):
        self._tick("parent_ref", number)
        self._need("sub_issues")
        return self._ref(self.parents.get(number))

    def blocker_refs(self, number):
        self._tick("blocker_refs", number)
        self._need("dependencies")
        return [self._ref(b) for n, b in self.dependencies if n == number]

    def set_parent(self, number, parent):
        self._tick("set_parent", number)
        self._need("sub_issues")
        self.parents[number] = parent

    def get_parent(self, number):
        self._tick("get_parent", number)
        self._need("sub_issues")
        return self.parents.get(number)

    def remove_parent(self, number, parent):
        self._tick("remove_parent", number)
        self._need("sub_issues")
        if self.parents.get(number) == parent:
            del self.parents[number]

    def add_dependency(self, number, blocker):
        self._tick("add_dependency", number)
        self._need("dependencies")
        if (number, blocker) not in self.dependencies:
            self.dependencies.append((number, blocker))

    def remove_dependency(self, number, blocker):
        self._tick("remove_dependency", number)
        self._need("dependencies")
        if (number, blocker) in self.dependencies:
            self.dependencies.remove((number, blocker))

    def list_dependencies(self, number):
        self._tick("list_dependencies", number)
        self._need("dependencies")
        return [b for n, b in self.dependencies if n == number]

    def last_number(self):
        self._tick("last_number")
        return max(self.issues, default=0)

    def list_labels(self):
        self._tick("list_labels")
        return [dict(v) for _k, v in sorted(self.labels.items())]

    def create_label(self, name, color="ededed", description=""):
        self._tick("create_label", name)
        if name in self.labels:
            raise RuntimeError("label %s already exists" % name)
        self.labels[name] = {"name": name, "color": color, "description": description}
        return dict(self.labels[name])

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
