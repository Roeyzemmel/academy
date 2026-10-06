"""board_gh.py -- a board_store transport over the GitHub REST API, through the gh CLI.

``GhTransport(repo)`` implements the transport of ``board_store`` (list/get/create/update
issues, list/add comments) plus what the migration needs: ``last_number``, labels
(``list_labels``, ``create_label``), native relations (``set_parent``, ``get_parent``,
``add_dependency``, ``remove_dependency``, ``list_dependencies``) and assignees on
``create_issue``. It shells out to ``gh api`` (stdlib only; gh carries the credentials, so
no token is handled here) and sends every payload on stdin as JSON, so bodies reach GitHub
byte for byte -- unlike the github MCP, which appends an attribution footer to comments and
decodes ``\\uXXXX`` text in parameters.

``run`` is injectable: ``run(args, stdin_text) -> (returncode, stdout, stderr)``; the tests
pass a fake. Transient failures (HTTP 5xx, 429, connection errors) are retried up to four
times with backoff 2, 4, 8, 16 s; a secondary rate limit (GitHub blocks bursts of content
creation: the live run met it after ~350 writes in 7 minutes) is waited out for 1, 2, 4, 8
and 15 minutes; any other failure raises ``GhError``. Writes are spaced ``write_interval``
seconds apart (default 1 s, GitHub's guidance for content creation).
"""

import json
import shutil
import subprocess
import time

API_VERSION = "2022-11-28"
RETRY_DELAYS = (2, 4, 8, 16)
#: waits after a secondary rate limit ("blocked from content creation"), which lasts minutes
RATE_LIMIT_DELAYS = (60, 120, 240, 480, 900)
#: seconds between writes (GitHub: at least one second between content-creating requests)
WRITE_INTERVAL = 1.0
RATE_LIMITED = ("secondary rate limit", "rate limit exceeded")
TRANSIENT = ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "HTTP 429",
             "connection reset", "connection refused", "timeout", "EOF", "TLS handshake")


class GhError(RuntimeError):
    def __init__(self, msg, status=None):
        RuntimeError.__init__(self, msg)
        self.status = status


GH_MISSING = ("gh is not installed: the board is on GitHub (board.backend github) and its "
              "transport runs 'gh api'; install the GitHub CLI and log in (gh auth login), "
              "or in a cloud session check that the environment provides gh")


def _run_gh(args, stdin_text):
    try:
        p = subprocess.run(["gh"] + args, input=stdin_text, capture_output=True, text=True,
                           encoding="utf-8")
    except FileNotFoundError:
        raise GhError(GH_MISSING)
    return p.returncode, p.stdout, p.stderr


def _status(err):
    for tok in err.replace("(", " ").replace(")", " ").split():
        if tok.isdigit() and len(tok) == 3 and ("HTTP " + tok) in err:
            return int(tok)
    return None


class GhTransport(object):
    def __init__(self, repo, run=None, sleep=time.sleep, clock=time.monotonic,
                 write_interval=WRITE_INTERVAL):
        if repo.count("/") != 1:
            raise ValueError("repo must be OWNER/NAME, got %r" % repo)
        self.repo = repo
        self.run = run or _run_gh
        self.sleep = sleep
        self.clock = clock
        self.write_interval = write_interval
        self._last_write = None
        self._ids = {}

    # -- plumbing -------------------------------------------------------------
    def api(self, method, path, payload=None, missing_ok=False):
        """One REST call; ``path`` is relative to ``repos/OWNER/NAME``. None on a 404 when
        ``missing_ok``."""
        args = ["api", "-X", method, "-H", "X-GitHub-Api-Version: " + API_VERSION,
                "repos/%s/%s" % (self.repo, path)]
        stdin = None
        if payload is not None:
            args += ["--input", "-"]
            stdin = json.dumps(payload, ensure_ascii=False)
        transient = limited = 0
        while True:
            if method != "GET":
                self._space()
            code, out, err = self.run(args, stdin)
            if code == 0:
                return json.loads(out) if out.strip() else None
            text = err + out
            status = _status(text)
            if status == 404 and missing_ok:
                return None
            if any(t in text.lower() for t in RATE_LIMITED) and limited < len(RATE_LIMIT_DELAYS):
                self.sleep(RATE_LIMIT_DELAYS[limited])
                limited += 1
                continue
            if any(t in text for t in TRANSIENT) and transient < len(RETRY_DELAYS):
                self.sleep(RETRY_DELAYS[transient])
                transient += 1
                continue
            raise GhError("%s %s: %s" % (method, path, (err or out).strip()), status)

    def _space(self):
        now = self.clock()
        if self._last_write is not None and self.write_interval:
            wait = self.write_interval - (now - self._last_write)
            if wait > 0:
                self.sleep(wait)
                now += wait
        self._last_write = now

    def _id(self, number):
        if number not in self._ids:
            self._ids[number] = self.api("GET", "issues/%d" % number)["id"]
        return self._ids[number]

    # -- the board_store transport -------------------------------------------
    def list_issues(self, labels=None, state="all", page=1, per_page=100):
        q = "issues?state=%s&sort=created&direction=asc&per_page=%d&page=%d" % (
            state, per_page, page)
        if labels:
            q += "&labels=" + ",".join(labels)
        return self.api("GET", q)

    def get_issue(self, number):
        return self.api("GET", "issues/%d" % number, missing_ok=True)

    def create_issue(self, title, body, labels, assignees=None):
        payload = {"title": title, "body": body, "labels": list(labels)}
        if assignees:
            payload["assignees"] = list(assignees)
        issue = self.api("POST", "issues", payload)
        self._ids[issue["number"]] = issue["id"]
        return issue

    def update_issue(self, number, title=None, body=None, labels=None, state=None,
                     state_reason=None, assignees=None):
        payload = {k: v for k, v in (("title", title), ("body", body), ("labels", labels),
                                     ("state", state), ("assignees", assignees))
                   if v is not None}
        if state == "closed" and state_reason:
            payload["state_reason"] = state_reason
        return self.api("PATCH", "issues/%d" % number, payload)

    def list_comments(self, number, page=1, per_page=100):
        return self.api("GET", "issues/%d/comments?per_page=%d&page=%d" % (number, per_page, page))

    def add_comment(self, number, body):
        return self.api("POST", "issues/%d/comments" % number, {"body": body})

    # -- migration extras -----------------------------------------------------
    def last_number(self):
        """The highest issue or PR number in the repo (0 when it has none)."""
        rows = self.api("GET", "issues?state=all&sort=created&direction=desc&per_page=1")
        return rows[0]["number"] if rows else 0

    def list_labels(self):
        out, page = [], 1
        while True:
            chunk = self.api("GET", "labels?per_page=100&page=%d" % page)
            out += chunk
            if len(chunk) < 100:
                return out
            page += 1

    def create_label(self, name, color="ededed", description=""):
        return self.api("POST", "labels", {"name": name, "color": color,
                                           "description": description})

    def set_parent(self, number, parent):
        """Make ``number`` a sub-issue of ``parent``, replacing any parent it had."""
        self.api("POST", "issues/%d/sub_issues" % parent,
                 {"sub_issue_id": self._id(number), "replace_parent": True})

    def remove_parent(self, number, parent):
        self.api("DELETE", "issues/%d/sub_issue" % parent, {"sub_issue_id": self._id(number)})

    def get_parent(self, number):
        p = self.api("GET", "issues/%d/parent" % number, missing_ok=True)
        return p["number"] if p else None

    def add_dependency(self, number, blocker):
        self.api("POST", "issues/%d/dependencies/blocked_by" % number,
                 {"issue_id": self._id(blocker)})

    def remove_dependency(self, number, blocker):
        self.api("DELETE", "issues/%d/dependencies/blocked_by/%d" % (number, self._id(blocker)))

    def list_dependencies(self, number):
        rows = self.api("GET", "issues/%d/dependencies/blocked_by?per_page=100" % number,
                        missing_ok=True)
        return [r["number"] for r in rows or []]


def transport(cfg):
    """The ``board.transport`` factory of workspace.json (``"board_gh:transport"``): a
    GhTransport on ``board.repo``. Needs ``gh`` installed and authenticated on the machine."""
    import academy_common as ac
    repo = (cfg or {}).get("repo")
    if not repo or repo.count("/") != 1:
        raise ac.ConfigError("board.transport board_gh:transport needs board.repo as "
                             "OWNER/NAME (got %r)" % (repo,))
    if not shutil.which("gh"):
        raise ac.ConfigError(GH_MISSING)
    return GhTransport(repo)
