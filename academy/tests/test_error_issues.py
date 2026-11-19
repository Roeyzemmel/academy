"""Tests for the error ledger on GitHub issues (academy#95): error_issues.py and the
error_ledger.py CLI's sync / migrate / report / resolve / settle against a fake GitHub.

Run from the repo root:  py -m unittest discover academy/tests
"""

import contextlib
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPTS = os.path.join(PLUGIN, "scripts")
sys.path.insert(0, SCRIPTS)

import error_issues as ei  # noqa: E402
import error_ledger as el  # noqa: E402

NOW = dt.datetime(2026, 11, 19, 12, 0, 0)


def at(days_ago, seconds=0):
    return el._stamp(NOW - dt.timedelta(days=days_ago) + dt.timedelta(seconds=seconds))


def err(days_ago, sig="Bash: boom <n>", session="s1", instance="author@x", **kw):
    rec = {"t": "error", "ts": at(days_ago, kw.pop("sec", 0)), "session": session,
           "instance": instance, "tool": sig.split(":")[0], "sig": sig, "msg": sig}
    rec.update(kw)
    return rec


class FakeGitHub(object):
    """An in-memory GitHub REST API for the paths GhTransport calls, as a ``run``."""

    def __init__(self, fail_on=None):
        self.issues = {}
        self.comments = {}
        self.calls = []
        self.fail_on = fail_on      # (method, path suffix, nth): raise on that call

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]

    def __call__(self, args, stdin):
        method = args[args.index("-X") + 1]
        url = next(x for x in args if x.startswith("repos/"))
        path = url.split("/", 3)[3]
        self.calls.append((method, path))
        if self.fail_on and method == self.fail_on[0] and path.endswith(self.fail_on[1]):
            self.fail_on[2] -= 1
            if self.fail_on[2] <= 0:
                self.fail_on = None
                return 1, "", "gh: Validation Failed (HTTP 422)"
        payload = json.loads(stdin) if stdin else {}
        parts = urlsplit(path)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        seg = parts.path.split("/")
        if seg == ["issues"] and method == "GET":
            rows = sorted(self.issues.values(), key=lambda i: i["number"])
            if q.get("state", "open") != "all":
                rows = [i for i in rows if i["state"] == q.get("state", "open")]
            for lb in (q.get("labels") or "").split(","):
                if lb:
                    rows = [i for i in rows if lb in [x["name"] for x in i["labels"]]]
            per, page = int(q.get("per_page", 30)), int(q.get("page", 1))
            return 0, json.dumps(rows[(page - 1) * per:page * per]), ""
        if seg == ["issues"] and method == "POST":
            n = len(self.issues) + 1
            self.issues[n] = {"number": n, "id": 1000 + n, "title": payload["title"],
                              "body": payload["body"], "state": "open",
                              "labels": [{"name": x} for x in payload.get("labels", [])]}
            self.comments[n] = []
            return 0, json.dumps(self.issues[n]), ""
        n = int(seg[1])
        if len(seg) == 2 and method == "PATCH":
            i = self.issues[n]
            for k in ("title", "body", "state", "state_reason"):
                if k in payload:
                    i[k] = payload[k]
            if "labels" in payload:
                i["labels"] = [{"name": x} for x in payload["labels"]]
            return 0, json.dumps(i), ""
        if seg[2:] == ["comments"] and method == "GET":
            per, page = int(q.get("per_page", 30)), int(q.get("page", 1))
            return 0, json.dumps(self.comments[n][(page - 1) * per:page * per]), ""
        if seg[2:] == ["comments"] and method == "POST":
            c = {"id": len(self.comments[n]) + 1, "body": payload["body"]}
            self.comments[n].append(c)
            return 0, json.dumps(c), ""
        return 1, "", "gh: Not Found (HTTP 404)"

    # helpers for the assertions
    def labels(self, n):
        return sorted(x["name"] for x in self.issues[n]["labels"])

    def by_sig(self, sig):
        h = ei.sig_hash(sig)
        return next(i for i in self.issues.values() if ei.hash_of(i) == h)


class Case(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.spool = os.path.join(self.d, "spool")
        self.gh = FakeGitHub()
        self.t = ei.transport("me/academy", run=self.gh, write_interval=0)

    def spill(self, *recs, instance="author@x"):
        for r in recs:
            el.append_file(el.spool_file(self.spool, instance), r)


class HiddenAndTitleTests(unittest.TestCase):
    def test_hidden_json_survives_a_closing_marker_in_the_text(self):
        obj = {"msg": "a --> b <!-- c", "n": [1, 2]}
        text = "x " + ei.hidden("k", obj) + " y " + ei.hidden("k", {"z": 1})
        self.assertNotIn("-->", text.split("<!-- k ", 1)[1].split(" -->", 1)[0])
        self.assertEqual(ei.read_hidden("k", text), [obj, {"z": 1}])

    def test_signature_maps_to_a_stable_marker(self):
        body = ei.render_body(ei.merge_meta(None, "Bash: boom <n>", [err(1)], "b"))
        self.assertIn("<!-- sig:%s -->" % ei.sig_hash("Bash: boom <n>"), body)
        self.assertEqual(ei.hash_of({"body": body}), ei.sig_hash("Bash: boom <n>"))
        self.assertEqual(ei.meta_of({"body": body})["sig"], "Bash: boom <n>")

    def test_scrub_hides_home_directories_and_secrets(self):
        s = ei.scrub("C:\\Users\\bob\\x.py and /home/alice/w and token=abc123 ghp_"
                     + "a" * 24)
        self.assertNotIn("bob", s)
        self.assertNotIn("alice", s)
        self.assertNotIn("abc123", s)
        self.assertIn("~", s)


class SyncTests(Case):
    def test_one_issue_per_class_one_comment_per_sync_and_no_double_post(self):
        self.spill(err(2), err(1, session="s2"), err(1, sig="Read: eisdir <path>"))
        res = ei.sync(self.spool, self.t)
        self.assertIsNone(res["error"])
        self.assertEqual((res["records"], res["classes"]), (3, 2))
        self.assertEqual(len(self.gh.issues), 2)
        bash = self.gh.by_sig("Bash: boom <n>")
        self.assertEqual(self.gh.labels(bash["number"]), [ei.LABEL])
        self.assertEqual(len(self.gh.comments[bash["number"]]), 1)
        self.assertIn("**2 occurrence(s)**", self.gh.comments[bash["number"]][0]["body"])
        # nothing new: nothing posted
        before = len(self.gh.writes())
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 0)
        self.assertEqual(len(self.gh.writes()), before)
        # one new error: one comment on the same issue, no new issue
        self.spill(err(0))
        ei.sync(self.spool, self.t)
        self.assertEqual(len(self.gh.issues), 2)
        self.assertEqual(len(self.gh.comments[bash["number"]]), 2)
        meta = ei.meta_of(self.gh.issues[bash["number"]])
        self.assertEqual(meta["count"], 3)
        self.assertEqual(meta["last"], at(0))

    def test_an_existing_issue_is_found_by_its_marker_not_recreated(self):
        self.spill(err(2))
        ei.sync(self.spool, self.t)
        os.remove(os.path.join(self.spool, ei.CURSOR))    # another machine, its own cursor
        other = os.path.join(self.d, "spool2")
        el.append_file(el.spool_file(other, "expert@y"), err(1, instance="expert@y"))
        ei.sync(other, self.t)
        self.assertEqual(len(self.gh.issues), 1)

    def test_dry_run_posts_nothing_and_keeps_the_cursor(self):
        self.spill(err(1), err(1, sig="Read: eisdir <path>"))
        res = ei.sync(self.spool, None, dry_run=True)
        self.assertEqual((res["records"], res["classes"]), (2, 2))
        self.assertEqual(self.gh.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.spool, ei.CURSOR)))

    def test_benign_records_and_duplicates_are_not_posted(self):
        benign = err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 1", detail="nothing here")
        self.assertTrue(el.is_benign(benign))
        self.spill(benign, err(1))
        with open(el.spool_file(self.spool, "author@x"), "a") as fh:
            fh.write(json.dumps(err(1), sort_keys=True) + "\n")   # a duplicate past the tail check
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 1)

    def test_a_partial_line_waits_for_the_next_sync(self):
        self.spill(err(2))
        with open(el.spool_file(self.spool, "author@x"), "a") as fh:
            fh.write('{"t": "error", "ts": "2026-11')          # a hook mid-write
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 1)
        with open(el.spool_file(self.spool, "author@x"), "a") as fh:
            fh.write('-19T11:00:00", "sig": "Bash: boom <n>", "tool": "Bash", "msg": "m"}\n')
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 1)

    def test_a_failed_sync_resumes_without_posting_twice(self):
        self.spill(err(2, sig="A: a"), err(2, sig="B: b"), err(2, sig="C: c"))
        self.gh.fail_on = ["POST", "/comments", 2]       # the second class's comment fails
        res = ei.sync(self.spool, self.t)
        self.assertTrue(res["error"])
        self.assertEqual([p["sig"] for p in res["posted"]], ["A: a"])
        self.spill(err(1, sig="A: a"))                   # new while the batch is unfinished
        res = ei.sync(self.spool, self.t)
        self.assertIsNone(res["error"])
        counts = {i["title"]: len(self.gh.comments[n]) for n, i in self.gh.issues.items()}
        self.assertEqual(counts, {"error class: A: a": 2, "error class: B: b": 1,
                                  "error class: C: c": 1})
        self.assertEqual(len(self.gh.issues), 3)
        self.assertEqual(ei.meta_of(self.gh.by_sig("B: b"))["count"], 1)
        self.assertEqual(ei.meta_of(self.gh.by_sig("A: a"))["count"], 2)
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 0)

    def test_comments_are_redacted(self):
        self.spill(err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 2",
                       detail="cat: /home/alice/secret.txt: token=abc123",
                       cmd="cat /home/alice/secret.txt", cause="path not found"))
        ei.sync(self.spool, self.t)
        text = json.dumps([self.gh.issues, self.gh.comments])
        self.assertNotIn("alice", text)
        self.assertNotIn("abc123", text)

    def test_a_large_batch_is_split_across_comments(self):
        old = ei.PAYLOAD_MAX
        ei.PAYLOAD_MAX = 400
        self.addCleanup(setattr, ei, "PAYLOAD_MAX", old)
        self.spill(*[err(1, sec=i, session="s%d" % i) for i in range(20)])
        ei.sync(self.spool, self.t)
        bodies = [c["body"] for c in self.gh.comments[1]]
        self.assertGreater(len(bodies), 1)
        recs = ei.records_of(ei.meta_of(self.gh.issues[1]), self.gh.comments[1])
        self.assertEqual(len(recs), 20)


class ReopenTests(Case):
    def closed_with(self, **fix):
        self.spill(err(5, ver="1.0.0"))
        ei.sync(self.spool, self.t)
        ei.resolve(self.t, ["Bash: boom <n>"], note="fixed", **fix)
        n = self.gh.by_sig("Bash: boom <n>")["number"]
        self.assertEqual(self.gh.issues[n]["state"], "closed")
        return n

    def test_recurrence_after_a_fix_is_a_regression(self):
        n = self.closed_with(version="1.1.0")
        self.spill(err(1, ver="1.2.0"))
        res = ei.sync(self.spool, self.t)
        self.assertEqual(res["posted"][0]["action"], "reopened")
        self.assertEqual(self.gh.issues[n]["state"], "open")
        self.assertEqual(self.gh.labels(n), [ei.LABEL, ei.REGRESSION])
        self.assertIn("regression", self.gh.comments[n][-1]["body"])

    def test_recurrence_from_code_older_than_the_fix_is_stale_code(self):
        n = self.closed_with(version="1.1.0")
        self.spill(err(1, ver="1.0.0"), err(1, sec=5, ver="1.0.3"))
        ei.sync(self.spool, self.t)
        self.assertEqual(self.gh.labels(n), [ei.LABEL, ei.STALE])
        # then the same error from fixed code: the stale label becomes a regression
        self.spill(err(0, ver="1.1.0"))
        ei.sync(self.spool, self.t)
        self.assertEqual(self.gh.labels(n), [ei.LABEL, ei.REGRESSION])

    def test_recurrence_after_silence_reopens_without_a_tag(self):
        self.spill(err(20))
        ei.sync(self.spool, self.t)
        closed = ei.settle(self.t, 7, "P-0001", now=NOW)
        self.assertEqual(len(closed), 1)
        n = closed[0][1]
        self.assertIn("Closed by silence", self.gh.comments[n][-1]["body"])
        self.spill(err(1))
        ei.sync(self.spool, self.t)
        self.assertEqual(self.gh.issues[n]["state"], "open")
        self.assertEqual(self.gh.labels(n), [ei.LABEL])


class ReportResolveSettleTests(Case):
    def test_report_from_issues_matches_the_ledger_report(self):
        recs = [err(30, ver="1.0.0"), err(3, session="s2"), err(2, session="s3"),
                err(1, sig="Read: eisdir <path>"),
                err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 1",
                    detail="Traceback (most recent call last): x", cause="python traceback"),
                err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 2", sec=200,
                    detail="bash: unexpected EOF while looking for matching `'`",
                    cause="shell quoting")]
        self.spill(*recs)
        ei.sync(self.spool, self.t)
        start = NOW - dt.timedelta(days=7)
        rep = ei.report(self.t, start, NOW)
        ref = el.report(recs + [{"t": "settle", "ts": el._stamp(start),
                                 "upto": el._stamp(start)}], start, NOW)
        self.assertEqual(rep["open_classes"], 3)
        self.assertEqual(rep["errors_in_window"], ref["errors_in_window"])
        key = lambda r: (r["sig"], r["count"], r["in_window"], r["sessions"], r["recurring"])
        self.assertEqual(sorted(map(key, rep["classes"])), sorted(map(key, ref["classes"])))
        fams = {f["family"] for f in rep["families"]}
        self.assertIn("Bash: python traceback", fams)
        self.assertIn("Bash: shell quoting", fams)
        self.assertIn("Read: read a directory", fams)
        self.assertTrue(all(r["issue"] for r in rep["classes"]))

    def test_regression_state_survives_the_round_trip(self):
        self.spill(err(10, ver="1.0.0"))
        ei.sync(self.spool, self.t)
        ei.resolve(self.t, ["Bash: boom <n>"], commit="abc1234", version="1.1.0",
                   now=NOW - dt.timedelta(days=5))
        self.spill(err(1, ver="1.2.0"))
        ei.sync(self.spool, self.t)
        rep = ei.report(self.t, NOW - dt.timedelta(days=7), NOW)
        (row,) = rep["classes"]
        self.assertTrue(row["regression"])
        self.assertEqual(row["count"], 1)       # only the errors since the resolve

    def test_resolve_closes_with_a_comment_and_by_family(self):
        self.spill(err(2, sig="mcp__x__tickets_update: t-n: open -> closed is not a transition"),
                   err(2, sig="mcp__x__tickets_update: t-n: open -> done is not a transition"),
                   err(2, sig="Read: eisdir <path>"))
        ei.sync(self.spool, self.t)
        closed, missing = ei.resolve(self.t, ["Nope: x"], ["tickets_update: not a transition"],
                                     note="fixed the transition table", commit="abc1234",
                                     version="2.0.0")
        self.assertEqual(missing, ["Nope: x"])
        self.assertEqual(len(closed), 2)
        for _, n in closed:
            self.assertEqual(self.gh.issues[n]["state"], "closed")
            self.assertEqual(self.gh.issues[n]["state_reason"], "completed")
            body = self.gh.comments[n][-1]["body"]
            self.assertIn("fixed the transition table", body)
            self.assertIn("abc1234", body)
            self.assertEqual(ei.meta_of(self.gh.issues[n])["fix"],
                             {"commit": "abc1234", "version": "2.0.0"})
        self.assertEqual(self.gh.by_sig("Read: eisdir <path>")["state"], "open")

    def test_settle_closes_only_the_quiet(self):
        self.spill(err(20, sig="Q: quiet"), err(2, sig="B: busy"))
        ei.sync(self.spool, self.t)
        closed = ei.settle(self.t, 7, None, now=NOW)
        self.assertEqual([s for s, _ in closed], ["Q: quiet"])
        self.assertEqual(self.gh.by_sig("B: busy")["state"], "open")


class MigrateTests(Case):
    def ledger(self):
        board = os.path.join(self.d, "board")
        el.append(board, "a@x", err(30, sig="R: resolved"))
        el.append(board, "a@x", {"t": "resolve", "ts": at(25), "sig": "R: resolved",
                                 "by": "human", "note": "ok", "commit": "abc1234"})
        el.append(board, "a@x", err(20, sig="O: open"))
        el.append(board, "a@x", err(10, sig="G: regressed", ver="1.0.0"))
        el.append(board, "a@x", {"t": "resolve", "ts": at(9), "sig": "G: regressed",
                                 "by": "human", "note": "", "version": "1.1.0"})
        el.append(board, "b@x", err(2, sig="G: regressed", ver="1.2.0"))
        el.append(board, "b@x", {"t": "settle", "ts": at(15), "upto": at(15), "packet": "P-1"})
        el.append(board, "b@x", err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 1",
                                    detail="ordinary output"))           # benign: not imported
        return board

    def test_dry_run_counts_and_contacts_no_one(self):
        res = ei.migrate(el.read_all(self.ledger()), None, dry_run=True)
        self.assertEqual((res["classes"], res["open"], res["resolved"], res["regression"]),
                         (3, 2, 1, 1))
        self.assertEqual((res["errors"], res["resolves"]), (4, 2))
        self.assertEqual(self.gh.calls, [])

    def test_migrate_imports_open_and_closed_and_is_resumable(self):
        recs = el.read_all(self.ledger())
        res = ei.migrate(recs, self.t)
        self.assertEqual(res["created"], 3)
        self.assertEqual(self.gh.by_sig("R: resolved")["state"], "closed")
        self.assertEqual(self.gh.by_sig("O: open")["state"], "open")
        g = self.gh.by_sig("G: regressed")
        self.assertEqual(self.gh.labels(g["number"]), [ei.LABEL, ei.REGRESSION])
        # the report over the issues sees what the ledger's report saw
        start = NOW - dt.timedelta(days=7)
        rep = ei.report(self.t, start, NOW)
        self.assertEqual(sorted(r["sig"] for r in rep["classes"]),
                         sorted(el.classes(recs)))
        self.assertTrue(next(r for r in rep["classes"] if r["sig"] == "G: regressed")
                        ["regression"])
        # a second run duplicates nothing
        before = len(self.gh.writes())
        res = ei.migrate(recs, self.t)
        self.assertEqual((res["created"], res["existing"]), (0, 3))
        self.assertEqual(len(self.gh.writes()), before)

    def test_an_interrupted_migrate_is_completed(self):
        recs = el.read_all(self.ledger())
        self.gh.fail_on = ["POST", "/comments", 2]
        with self.assertRaises(ei.GhError):
            ei.migrate(recs, self.t)
        res = ei.migrate(recs, self.t)
        self.assertEqual(len(self.gh.issues), 3)
        self.assertTrue(all(len(c) == 1 for c in self.gh.comments.values()))
        self.assertEqual(res["completed"], 1)

    def test_skip_resolved(self):
        res = ei.migrate(el.read_all(self.ledger()), self.t, skip_resolved=True)
        self.assertEqual((res["created"], res["skipped_resolved"]), (2, 1))


class WorkspaceCase(unittest.TestCase):
    """A workspace with one author home, for the hook and the CLI."""

    def make(self, errors=None):
        d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        self.d = d
        self.home, self.board = os.path.join(d, "home"), os.path.join(d, "board")
        os.makedirs(os.path.join(self.home, ".claude"))
        os.makedirs(self.board)
        cfg = {"schema": 1, "role": "author", "instance": "author@t", "domains": ["x"],
               "paths": {k: k for k in el.ac.REQUIRED_PATHS["author"]},
               "registry": {"profile": "none"}, "author": {}}
        with open(os.path.join(self.home, ".claude", "academy.json"), "w") as fh:
            json.dump(cfg, fh)
        self.ws = os.path.join(d, "workspace.json")
        data = {"instances": {"author@t": {"role": "author", "home": self.home,
                                           "domains": ["x"]}}, "board": self.board}
        if errors is not None:
            data["errors"] = errors
        with open(self.ws, "w") as fh:
            json.dump(data, fh)
        self.spool = os.path.join(d, "spool")


class HookTests(WorkspaceCase):
    def test_the_hook_writes_the_spool_and_never_calls_gh(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        bindir = os.path.join(self.d, "bin")
        os.makedirs(bindir)
        marker = os.path.join(self.d, "gh-was-called")
        for name in ("gh", "git", "curl"):
            with open(os.path.join(bindir, name), "w") as fh:
                fh.write("#!/bin/sh\ntouch %s\nexit 1\n" % marker)
            os.chmod(os.path.join(bindir, name), 0o755)
        env = dict(os.environ, ACADEMY_WORKSPACE=self.ws,
                   PATH=bindir + os.pathsep + os.environ.get("PATH", ""))
        env.pop("ACADEMY_ENV_WORKSPACE", None)
        env.pop(el.SPOOL_ENV, None)
        ev = {"tool_name": "Bash", "error": "Exit code 1\nboom: cannot open the file",
              "cwd": self.home, "session_id": "S1"}
        run = lambda data: subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "error_ledger.py"), "hook"],
            input=data, capture_output=True, env=env, cwd=self.home, timeout=60)
        self.assertEqual(run(json.dumps(ev).encode()).returncode, 0)
        self.assertEqual(run(b"garbage").returncode, 0)
        self.assertFalse(os.path.exists(marker))
        self.assertFalse(os.path.isdir(os.path.join(self.board, el.LEDGER_DIR)))
        recs = el.read_dirs([self.spool])
        self.assertEqual([r["session"] for r in recs], ["S1"])

    def test_the_hook_does_not_load_the_network_code(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        code = ("import sys, io, json; sys.path.insert(0, %r); import error_ledger as el; "
                "el.run_hook(io.StringIO(json.dumps({'tool_name': 'Read', 'error': 'EISDIR x', "
                "'cwd': %r}))); print(json.dumps(sorted(m for m in sys.modules "
                "if m in ('error_issues', 'board_gh', 'subprocess', 'urllib.request'))))"
                % (SCRIPTS, self.home))
        env = dict(os.environ, ACADEMY_WORKSPACE=self.ws)
        env.pop("ACADEMY_ENV_WORKSPACE", None)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             env=env, cwd=self.home, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        loaded = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertNotIn("error_issues", loaded)
        self.assertNotIn("board_gh", loaded)
        self.assertEqual(len(el.read_dirs([self.spool])), 1)

    def test_without_a_repo_the_hook_writes_the_git_ledger(self):
        self.make()
        env = dict(os.environ, ACADEMY_WORKSPACE=self.ws)
        env.pop("ACADEMY_ENV_WORKSPACE", None)
        ev = {"tool_name": "Read", "error": "EISDIR: illegal operation", "cwd": self.home}
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "error_ledger.py")],
                       input=json.dumps(ev).encode(), env=env, cwd=self.home, timeout=60)
        self.assertEqual(len(el.read_all(self.board)), 1)


class CliTests(WorkspaceCase):
    def setUp(self):
        self.gh = FakeGitHub()
        self.old_t = el.TRANSPORT
        self.addCleanup(setattr, el, "TRANSPORT", self.old_t)

    def cli(self, *args):
        out, errs = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errs):
            rc = el.main(list(args) + ["--workspace", self.ws])
        return rc, out.getvalue(), errs.getvalue()

    def use_fake(self):
        el.TRANSPORT = lambda repo: ei.transport(repo, run=self.gh, write_interval=0)

    def test_no_repo_keeps_the_file_behaviour(self):
        self.make()
        el.append(self.board, "author@t", err(1))
        rc, out, _ = self.cli("sync")
        self.assertEqual(rc, 0)
        self.assertIn("no errors.repo", out)
        rc, out, _ = self.cli("report", "--json")
        self.assertEqual(json.loads(out)["open_classes"], 1)
        rc, out, _ = self.cli("resolve", "Bash: boom <n>", "--note", "x")
        self.assertEqual(rc, 0)
        self.assertEqual(el.classes(el.read_all(self.board)), {})

    def test_sync_report_resolve_settle_through_the_cli(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        self.use_fake()
        el.append_file(el.spool_file(self.spool, "author@t"), err(1))
        el.append_file(el.spool_file(self.spool, "author@t"), err(1, sig="Q: quiet"))
        rc, out, _ = self.cli("sync", "--dry-run")
        self.assertEqual((rc, self.gh.calls), (0, []))
        self.assertIn("2 record(s) of 2 class(es) would post", out)
        rc, out, _ = self.cli("report", "--json", "--brief")
        brief = json.loads(out)
        self.assertEqual((brief["open_classes"], brief["unsynced"]), (0, 2))
        rc, out, _ = self.cli("sync")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.gh.issues), 2)
        rc, out, _ = self.cli("report", "--json", "--brief")
        brief = json.loads(out)
        self.assertEqual((brief["open_classes"], brief["unsynced"], brief["source"]),
                         (2, 0, "issues"))
        self.assertTrue(all(c["issue"] for c in brief["classes"]))
        rc, out, _ = self.cli("resolve", "Q: quiet", "--note", "noise")
        self.assertEqual(rc, 0)
        self.assertEqual(self.gh.by_sig("Q: quiet")["state"], "closed")
        rc, out, _ = self.cli("settle", "--quiet-days", "30")
        self.assertEqual(rc, 0)
        self.assertIn("0 issue(s) closed", out)

    def test_report_falls_back_to_the_local_files_when_github_fails(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        self.gh.fail_on = ["GET", "", 1]
        self.use_fake()
        el.append(self.board, "author@t", err(1, sig="Old: x"))
        el.append_file(el.spool_file(self.spool, "author@t"), err(1))
        rc, out, errs = self.cli("report", "--json")
        self.assertEqual(rc, 0)
        self.assertIn("not read", errs)
        self.assertEqual(json.loads(out)["open_classes"], 2)

    def test_migrate_dry_run_on_the_cli(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        self.use_fake()
        el.append(self.board, "author@t", err(1))
        rc, out, _ = self.cli("migrate", "--dry-run")
        self.assertEqual((rc, self.gh.calls), (0, []))
        self.assertIn("classes: 1 (open 1", out)


if __name__ == "__main__":
    unittest.main()
