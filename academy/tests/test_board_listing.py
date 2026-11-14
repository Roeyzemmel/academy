"""The GitHub board's listing is incremental (2026-11-13): a store whose transport serves
``since`` reads the whole board once and afterwards only what changed, in the process and
between processes (the cache file), and always returns what a full listing would."""

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import academy_common as ac  # noqa: E402
import board_codec as bc  # noqa: E402
import board_gh  # noqa: E402
import board_store as bs  # noqa: E402

INST = "researcher@r1"


def meta(n, **kw):
    m = {"id": "T-%04d" % n, "from": "human", "to": INST, "kind": "question",
         "status": "open", "priority": "normal", "created": "2026-09-30", "title": "ticket %d" % n,
         "ask": "ask %d" % n}
    m.update(kw)
    return m


class Clock(object):
    """This machine's clock, in step with the fake server's (``transport.now``)."""

    def __init__(self, transport):
        self.transport = transport

    def __call__(self):
        return (self.transport.now - dt.datetime(1970, 1, 1)).total_seconds()


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="board-cache-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.t = bs.MemoryTransport(max_page=2)
        self.t.since = True
        for n in range(1, 6):
            self.t.add_encoded(bc.encode(meta(n), "body %d" % n))
        self.t.add_pull_request()
        self.clock = Clock(self.t)
        self.t.now += dt.timedelta(seconds=2 * bs.READ_SKEW)     # the seed is not "just now"

    def store(self, **kw):
        kw.setdefault("cache_dir", self.dir)
        return bs.GithubBoardStore(self.t, "o/r", clock=self.clock, **kw)

    def plain(self):
        t = self.t
        was, t.since = t.since, False
        try:
            return list(bs.GithubBoardStore(t, "o/r").iter_meta())
        finally:
            t.since = was

    def lists(self):
        return [c for c in self.t.calls if c[0] == "list_issues"]

    def later(self, seconds=60):
        self.t.now += dt.timedelta(seconds=seconds)
        del self.t.calls[:]


class Incremental(Case):
    def test_the_first_listing_is_full_and_equals_the_plain_one(self):
        s = self.store()
        self.assertEqual(self.plain(), list(s.iter_meta()))
        del self.t.calls[:]
        self.assertEqual(5, len(list(s.iter_meta())))
        self.assertEqual([], self.lists())                       # inside list_ttl: no request

    def test_a_later_listing_asks_only_for_what_changed(self):
        s = self.store()
        list(s.iter_meta())
        self.later()
        self.assertEqual(5, len(list(s.iter_meta())))
        calls = self.lists()
        self.assertTrue(calls and all(len(c) == 5 for c in calls), calls)   # every call: since
        self.assertLessEqual(len(calls), 3)          # the margin's few issues, not the board
        # another process changes a ticket: the next listing has it
        other = bs.GithubBoardStore(self.t, "o/r")
        ref, m, body = other.get("T-0002")
        other.save(dict(m, status="accepted"), body)
        self.t.add_encoded(bc.encode(meta(7), "new"))
        self.later()
        got = dict((m["id"], m) for _r, m in s.iter_meta())
        self.assertEqual("accepted", got["T-0002"]["status"])
        self.assertIn("T-0007", got)
        self.assertEqual(self.plain(), list(s.iter_meta()))

    def test_own_writes_are_seen_at_once(self):
        s = self.store()
        list(s.iter_meta())
        ref, m, body = s.get("T-0003")
        s.save(dict(m, status="accepted"), body)
        _ref, made = s.create(meta(0, ask="made here"), "")
        got = dict((m["id"], m) for _r, m in s.iter_meta())      # no time has passed
        self.assertEqual("accepted", got["T-0003"]["status"])
        self.assertIn(made["id"], got)

    def test_the_label_filter_is_applied_to_the_listing(self):
        self.t.add_encoded(bc.encode(meta(8, to="expert@e1"), ""))
        s = self.store()
        self.assertEqual(["T-0008"], [m["id"] for m in s.read_all("expert@e1")])
        self.assertEqual(5, len(s.read_all(INST)))
        self.assertEqual(sorted(m["id"] for m in s.read_all(INST)),
                         sorted(m["id"] for m in bs.GithubBoardStore(
                             _plain(self.t), "o/r").read_all(INST)))

    def test_a_caller_cannot_spoil_the_held_listing(self):
        s = self.store()
        for i in s._issues():
            i["title"] = "spoiled"
        self.assertEqual(self.plain(), list(s.iter_meta()))


def _plain(t):
    """A view of ``t`` that does not serve ``since`` (the reference listing)."""
    class View(object):
        since = False

        def __getattr__(self, name):
            return getattr(t, name)
    return View()


class DuringARead(Case):
    """A listing is several requests. What changes on a page already read, while a later
    page is fetched, must not be lost (review, 2026-11-14: the next read started from the
    newest stamp held, which was past that change)."""

    def test_a_change_made_while_the_pages_are_read_is_seen_by_the_next_listing(self):
        t, real, done = self.t, self.t.list_issues, []

        def list_issues(labels=None, state="all", page=1, per_page=100, since=None):
            if page == 2 and not done:               # page 1 (T-0001, T-0002) is already read
                done.append(1)
                other = bs.GithubBoardStore(_plain(t), "o/r")
                _ref, m, body = other.get("T-0001")
                other.save(dict(m, status="accepted"), body)
                t.now += dt.timedelta(seconds=3)
                _ref, m, body = other.get("T-0005")   # a later page, a later stamp
                other.save(dict(m, priority="high"), body)
            return real(labels=labels, state=state, page=page, per_page=per_page, since=since)
        t.list_issues = list_issues
        s = self.store()
        first = dict((m["id"], m["status"]) for _r, m in s.iter_meta())
        self.assertEqual("open", first["T-0001"])            # read before the change: fine
        for wait in (10, 100, 3600):
            self.later(wait)
            got = dict((m["id"], m["status"]) for _r, m in s.iter_meta())
            self.assertEqual("accepted", got["T-0001"], wait)
        del t.list_issues
        self.assertEqual(self.plain(), list(self.store().iter_meta()))   # and so is the file

    def test_the_next_read_starts_no_later_than_the_previous_one_began(self):
        f = bs._since
        self.assertEqual("2026-11-13T20:38:33Z", f("2026-11-13T20:38:35Z"))
        began = (dt.datetime(2026, 11, 13, 20, 30) - dt.datetime(1970, 1, 1)).total_seconds()
        self.assertEqual("2026-11-13T20:25:00Z", f("2026-11-13T20:38:35Z", began))
        self.assertEqual("2026-11-13T20:00:58Z", f("2026-11-13T20:01:00Z", began))   # the older wins
        self.assertIsNone(f("not a stamp", began))


class BetweenProcesses(Case):
    def test_a_second_store_starts_from_the_file(self):
        list(self.store().iter_meta())
        path = os.path.join(self.dir, "o__r.json")
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertEqual(6, len(d["issues"]))                    # the pull request is held too
        self.assertNotIn("assignee", json.dumps(d))              # only KEEP is written
        self.later()
        got = list(self.store().iter_meta())
        self.assertTrue(all(len(c) == 5 for c in self.lists()), self.lists())
        self.assertEqual(self.plain(), got)

    def test_an_unreadable_or_foreign_file_means_a_full_listing(self):
        list(self.store().iter_meta())
        path = os.path.join(self.dir, "o__r.json")
        for text in ("{not json", json.dumps({"version": 0, "repo": "o/r", "issues": {}}),
                     json.dumps({"version": bs.CACHE_VERSION, "repo": "x/y", "full_at": 0,
                                 "issues": {}})):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.later()
            got = list(self.store().iter_meta())
            self.assertTrue(all(len(c) == 4 for c in self.lists()))   # no call with since
            self.assertEqual(self.plain(), got)

    def test_the_whole_board_is_read_again_after_a_day(self):
        s = self.store()
        list(s.iter_meta())
        del self.t.issues[4]                                     # deleted on GitHub
        self.later()
        self.assertEqual(5, len(list(s.iter_meta())))            # since cannot say so
        self.later(bs.FULL_REFRESH)
        self.assertEqual(4, len(list(s.iter_meta())))
        self.assertEqual(self.plain(), list(self.store().iter_meta()))

    def test_the_file_is_private_and_a_failed_write_leaves_nothing_behind(self):
        list(self.store().iter_meta())
        path = os.path.join(self.dir, "o__r.json")
        if os.name != "nt":
            self.assertEqual(0o600, os.stat(path).st_mode & 0o777)
        # the replace fails (on Windows: another process is reading the file)
        real, calls = os.replace, []

        def refuse(a, b):
            calls.append(a)
            raise PermissionError("in use")
        self.t.add_encoded(bc.encode(meta(9), "later"))
        self.later()
        os.replace = refuse
        try:
            got = list(self.store().iter_meta())
        finally:
            os.replace = real
        self.assertEqual(1, len(calls))
        self.assertEqual(self.plain(), got)                      # the listing is still right
        self.assertEqual(["o__r.json"], os.listdir(self.dir))    # and no temp file is left

    def test_no_directory_means_no_file(self):
        list(self.store(cache_dir=None).iter_meta())
        self.assertEqual([], os.listdir(self.dir))

    def test_an_issue_without_a_stamp_means_a_full_listing(self):
        s = self.store()
        list(s.iter_meta())
        del self.t.issues[1]["updated_at"]
        s._held["issues"][1].pop("updated_at")
        self.later()
        list(s.iter_meta())
        self.assertTrue(all(len(c) == 4 for c in self.lists()), self.lists())


class Wiring(unittest.TestCase):
    def test_the_cache_directory_setting(self):
        f = ac.board_cache_dir
        self.assertIsNone(f({}, {"ACADEMY_BOARD_CACHE": "off"}))
        self.assertIsNone(f({"cache": False}, {}))
        self.assertEqual("/x/y", f({"cache": False}, {"ACADEMY_BOARD_CACHE": "/x/y"}))
        self.assertEqual("/b", f({"cache": "/b"}, {}))
        if os.name != "nt":
            self.assertEqual(os.path.join("/c", "academy", "board"), f({}, {"XDG_CACHE_HOME": "/c"}))

    def test_the_gh_transport_serves_since(self):
        seen = []

        def run(args, stdin):
            seen.append(args[-1])
            return 0, "[]", ""
        t = board_gh.GhTransport("o/r", run=run)
        self.assertTrue(t.since)
        t.list_issues(since="2026-11-13T00:00:00Z")
        t.list_issues()
        self.assertIn("&since=2026-11-13T00:00:00Z", seen[0])
        self.assertNotIn("since", seen[1])

    def test_a_handed_in_transport_gets_no_file(self):
        d = tempfile.mkdtemp(prefix="board-cache-ws-")
        self.addCleanup(shutil.rmtree, d, True)
        ws = {"board": d, "board_config": {"backend": "github", "repo": "o/r"}}
        self.assertIsNone(ac.open_store(ws, transport=bs.MemoryTransport()).cache_dir)


if __name__ == "__main__":
    unittest.main()
