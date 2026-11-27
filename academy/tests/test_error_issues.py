"""Tests for the error ledger's families as GitHub issues (academy#95): error_issues.py
and the error_ledger.py CLI's sync / migrate / report / resolve / settle against a fake
GitHub. The errors repo is public: only the coarse family, counts, dates, roles, causes
and code versions may reach it (``LeakTests`` scans every write).

Run from the repo root:  py -m unittest discover academy/tests
"""

import contextlib
import datetime as dt
import io
import json
import os
import re
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
TU = "mcp__plugin_x_x__tickets_update"
#: signatures whose families pass the allowlist
NT = TU + ": refused: open -> closed is not a transition"          # tickets_update: not a transition
DIR = "Read: eisdir: illegal operation on a directory, read <path>"  # Read: read a directory
GONE = "Glob: directory does not exist: <path>"                    # Glob: path does not exist
F_NT, F_DIR, F_GONE = ("tickets_update: not a transition", "Read: read a directory",
                       "Glob: path does not exist")


def at(days_ago, seconds=0):
    return el._stamp(NOW - dt.timedelta(days=days_ago) + dt.timedelta(seconds=seconds))


def err(days_ago, sig=NT, session="s1", instance="author@x", **kw):
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
        self.sent = []              # (method, path, payload) of every write
        self.login = "poster"       # the transport's own account
        self.fail_on = fail_on      # (method, path suffix, nth): raise on that call

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]

    def __call__(self, args, stdin):
        method = args[args.index("-X") + 1]
        url = next(x for x in args if x.startswith("repos/") or x == "user")
        if url == "user":
            self.calls.append((method, "user"))
            return 0, json.dumps({"login": self.login}), ""
        path = url.split("/", 3)[3]
        self.calls.append((method, path))
        if self.fail_on and method == self.fail_on[0] and path.endswith(self.fail_on[1]):
            self.fail_on[2] -= 1
            if self.fail_on[2] <= 0:
                self.fail_on = None
                return 1, "", "gh: Validation Failed (HTTP 422)"
        payload = json.loads(stdin) if stdin else {}
        if method != "GET":
            self.sent.append((method, path, payload))
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
                              "user": {"login": self.login},
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
            c = {"id": len(self.comments[n]) + 1, "body": payload["body"],
                 "user": {"login": self.login}, "author_association": "OWNER"}
            self.comments[n].append(c)
            return 0, json.dumps(c), ""
        return 1, "", "gh: Not Found (HTTP 404)"

    # helpers for the assertions
    def labels(self, n):
        return sorted(x["name"] for x in self.issues[n]["labels"])

    def stranger_comment(self, n, body, login="stranger", association="NONE"):
        self.comments[n].append({"id": len(self.comments[n]) + 1, "body": body,
                                 "user": {"login": login}, "author_association": association})

    def add_label(self, n, name):
        self.issues[n]["labels"].append({"name": name})

    def by_family(self, fam):
        h = ei.family_hash(fam)
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


class AllowlistTests(unittest.TestCase):
    def test_rule_and_shell_families_pass(self):
        for fam in (F_NT, F_DIR, F_GONE, "claims_set_status: grounds do not support",
                    "Bash: python traceback", "Bash: exit code (unknown cmd)",
                    "Bash: exit code (python3)", "WebFetch: host unreachable",
                    "tickets_update: blocked_by must be a ticket or registry id (<id>, <claim>)"):
            self.assertTrue(ei.family_ok(fam), fam)
            self.assertEqual(ei.public_family(fam), fam)

    def test_every_rule_and_cause_family_passes(self):
        for _, reason in el.FAMILY_RULES:
            self.assertTrue(ei.family_ok("Read: " + reason), reason)
        for cause in ei.CAUSES:
            self.assertTrue(ei.family_ok("Bash: " + cause), cause)

    def test_private_words_make_a_family_unlisted(self):
        bad = ["tickets_update: approved by ada lovelace",          # a person
               "queue_log: no job <n>-<n>_hidden_orbit in <path>",   # a slug with _
               "claims_new: strip-bound is open",                    # a two-part slug
               "library_search: no such column: manifold",           # a search term
               "tickets_update: <q> is \"quoted\"",                  # a quote
               "Read: x@y",                                          # an instance
               "Read: 12"]                                           # a bare number
        for fam in bad:
            self.assertFalse(ei.family_ok(fam), fam)
            pub = ei.public_family(fam)
            self.assertRegex(pub, r"^[A-Za-z_]+: \(unlisted family [0-9a-f]{12}\)$")
            self.assertTrue(ei.family_ok(pub))
            self.assertEqual(ei.public_family(pub), pub)        # stable when read back
        self.assertEqual(ei.public_family("adalovelace_tool: x").split(": ")[0], "unlisted")

    def test_the_unlisted_family_survives_error_ledger_family(self):
        pub = ei.public_family("library_search: manifold")
        self.assertEqual(el.family(pub), pub)

    def test_check_public_refuses_raw_text(self):
        for text in ("cat: /home/ada/x.txt: No such file", "no claim nb:GEO-12",
                     "arXiv 2101.12345", "approved by Ada", "session_01ABCdef",
                     "\u00e9t\u00e9"):
            with self.assertRaises(ei.Unsafe, msg=text):
                ei.check_public(text)
        ei.check_public("**3 occurrences**, 2026-11-01T10:00:00 .. 2026-11-02T10:00:00, "
                        "rev 0123abc, version 0.2.10 <!-- batch:0a1b2c3d4e5f part 1/2 -->")

    def test_the_gate_refuses_before_the_transport_sees_anything(self):
        gh = FakeGitHub()
        t = ei.transport("me/academy", run=gh, write_interval=0)
        with self.assertRaises(ei.Unsafe):
            t.create_issue("error family: x", "raw message from /home/ada", [ei.LABEL])
        with self.assertRaises(ei.Unsafe):
            t.add_comment(1, "approved by Ada")
        with self.assertRaises(ei.Unsafe):
            t.update_issue(1, body="nb:GEO-12")
        with self.assertRaises(ei.Unsafe):
            t.update_issue(1, labels=["ada"])
        self.assertEqual(gh.calls, [])
        self.assertIsInstance(ei.gated(object()), ei.Gate)

    def test_a_body_needs_a_public_family(self):
        with self.assertRaises(ei.Unsafe):
            ei.render_body({"family": "Read: raw", "hash": "0" * 12})
        with self.assertRaises(ei.Unsafe):
            ei.merge_meta(None, "Read: raw", [err(1)], "b")

    def test_fields_are_coarse(self):
        self.assertEqual([ei.role_of(x) for x in ("author@x", "scientist@lab", "workspace",
                                                  "other", "ada@x", "")],
                         ["author", "scientist", "other", "other", "other", "other"])
        self.assertEqual(ei.cause_of({"cause": "python traceback"}), "python traceback")
        self.assertEqual(ei.cause_of({"cause": "made up by ada"}), "")
        self.assertEqual(ei.cause_of({"tool": "Bash", "detail": "Traceback (most recent call "
                                                                 "last): x"}),
                         "python traceback")
        self.assertEqual((ei.clean_rev("0123abcdef12"), ei.clean_rev("main")), ("0123abcdef12", ""))
        self.assertEqual((ei.clean_ver("0.2.10"), ei.clean_ver("0.2.10-ada")), ("0.2.10", ""))
        self.assertEqual(ei._resolve_row({"ts": at(1), "by": "Ada", "note": "x",
                                          "commit": "abc1234"}),
                         {"at": at(1)[:10], "by": "other", "commit": "abc1234"})

    def test_hidden_json_survives_a_closing_marker_in_the_text(self):
        obj = {"msg": "a --> b <!-- c", "n": [1, 2]}
        text = "x " + ei.hidden("k", obj) + " y " + ei.hidden("k", {"z": 1})
        self.assertNotIn("-->", text.split("<!-- k ", 1)[1].split(" -->", 1)[0])
        self.assertEqual(ei.read_hidden("k", text), [obj, {"z": 1}])

    def test_a_family_maps_to_a_stable_marker(self):
        fam = ei.public_family(F_NT)
        body = ei.render_body(ei.merge_meta(None, fam, [err(1)], "0a1b2c3d4e5f"))
        self.assertIn("<!-- family:%s -->" % ei.family_hash(fam), body)
        self.assertEqual(ei.hash_of({"body": body}), ei.family_hash(fam))
        self.assertEqual(ei.meta_of({"body": body})["family"], F_NT)
        self.assertEqual(ei.meta_of({"body": body})["roles"], {"author": 1})

    def test_a_long_title_is_cut_at_a_word(self):
        fam = ei.public_family("tickets_update: " + " ".join(["transition"] * 20))
        t = ei.title(fam)
        self.assertLessEqual(len(t), ei.TITLE_MAX)
        self.assertTrue(t.endswith(" transition ..."))
        ei.check_public(t)


class SyncTests(Case):
    def test_one_issue_per_family_one_comment_per_sync_and_no_double_post(self):
        other = TU + ": refused: blocked -> open is not a transition"   # same family
        self.spill(err(2), err(1, session="s2", sig=other), err(1, sig=DIR))
        res = ei.sync(self.spool, self.t)
        self.assertIsNone(res["error"])
        self.assertEqual((res["records"], res["families"]), (3, 2))
        self.assertEqual(len(self.gh.issues), 2)
        nt = self.gh.by_family(F_NT)
        self.assertEqual(nt["title"], "error family: " + F_NT)
        self.assertEqual(self.gh.labels(nt["number"]), [ei.LABEL])
        self.assertEqual(len(self.gh.comments[nt["number"]]), 1)
        body = self.gh.comments[nt["number"]][0]["body"]
        self.assertIn("Occurrences: **2**", body)
        self.assertIn("By role: author 2", body)
        # nothing new: nothing posted
        before = len(self.gh.writes())
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 0)
        self.assertEqual(len(self.gh.writes()), before)
        # one new error: one comment on the same issue, no new issue
        self.spill(err(0, instance="expert@y"), instance="expert@y")
        ei.sync(self.spool, self.t)
        self.assertEqual(len(self.gh.issues), 2)
        self.assertEqual(len(self.gh.comments[nt["number"]]), 2)
        meta = ei.meta_of(self.gh.issues[nt["number"]])
        self.assertEqual((meta["count"], meta["last"]), (3, at(0)[:10]))
        self.assertEqual(meta["roles"], {"author": 2, "expert": 1})

    def test_counts_by_cause(self):
        self.spill(err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 1",
                       detail="Traceback (most recent call last): x", cause="python traceback"),
                   err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 1", sec=9,
                       detail="Traceback (most recent call last): y"))
        ei.sync(self.spool, self.t)
        i = self.gh.by_family("Bash: python traceback")
        self.assertIn("By cause: python traceback 2", self.gh.comments[i["number"]][0]["body"])

    def test_an_unlisted_family_posts_as_its_hash(self):
        self.spill(err(1, sig="Bash: boom <n>"))
        ei.sync(self.spool, self.t)
        (issue,) = self.gh.issues.values()
        self.assertRegex(issue["title"], r"^error family: Bash: \(unlisted family [0-9a-f]{12}\)$")
        self.assertNotIn("boom", json.dumps(self.gh.sent))

    def test_an_existing_issue_is_found_by_its_marker_not_recreated(self):
        self.spill(err(2))
        ei.sync(self.spool, self.t)
        other = os.path.join(self.d, "spool2")      # another machine, its own cursor
        el.append_file(el.spool_file(other, "expert@y"), err(1, instance="expert@y"))
        ei.sync(other, self.t)
        self.assertEqual(len(self.gh.issues), 1)

    def test_dry_run_posts_nothing_and_keeps_the_cursor(self):
        self.spill(err(1), err(1, sig=DIR))
        res = ei.sync(self.spool, None, dry_run=True)
        self.assertEqual((res["records"], res["families"]), (2, 2))
        self.assertEqual(sorted(p["family"] for p in res["posted"]), sorted([F_NT, F_DIR]))
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
            fh.write('-19T11:00:00", "sig": "%s", "tool": "Read", "msg": "m"}\n' % DIR)
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 1)

    def test_a_failed_sync_resumes_without_posting_twice(self):
        self.spill(err(2, sig=GONE), err(2, sig=DIR), err(2, sig=NT))
        self.gh.fail_on = ["POST", "/comments", 2]       # the second family's comment fails
        res = ei.sync(self.spool, self.t)
        self.assertTrue(res["error"])
        self.assertEqual([p["family"] for p in res["posted"]], [F_GONE])
        self.spill(err(1, sig=GONE))                     # new while the batch is unfinished
        res = ei.sync(self.spool, self.t)
        self.assertIsNone(res["error"])
        counts = {i["title"]: len(self.gh.comments[n]) for n, i in self.gh.issues.items()}
        self.assertEqual(counts, {"error family: " + F_GONE: 2, "error family: " + F_DIR: 1,
                                  "error family: " + F_NT: 1})
        self.assertEqual(ei.meta_of(self.gh.by_family(F_DIR))["count"], 1)
        self.assertEqual(ei.meta_of(self.gh.by_family(F_GONE))["count"], 2)
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 0)

    def test_a_refused_text_stops_the_sync_and_keeps_the_batch(self):
        self.spill(err(1))
        old = ei.VOCAB
        ei.VOCAB = frozenset(w for w in old if w != "occurrences")
        self.addCleanup(setattr, ei, "VOCAB", old)
        res = ei.sync(self.spool, self.t)
        self.assertIn("Unsafe", res["error"])
        self.assertEqual(self.gh.writes(), [])
        ei.VOCAB = old
        self.assertIsNone(ei.sync(self.spool, self.t)["error"])
        self.assertEqual(len(self.gh.issues), 1)

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
        ei.resolve(self.t, families=[F_NT], **fix)
        n = self.gh.by_family(F_NT)["number"]
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
        closed = ei.settle(self.t, 7, now=NOW)
        self.assertEqual(len(closed), 1)
        n = closed[0][1]
        self.assertIn("Closed by silence", self.gh.comments[n][-1]["body"])
        self.spill(err(1))
        ei.sync(self.spool, self.t)
        self.assertEqual(self.gh.issues[n]["state"], "open")
        self.assertEqual(self.gh.labels(n), [ei.LABEL])


class ReportResolveSettleTests(Case):
    def test_report_from_issues_is_by_family(self):
        recs = [err(30, ver="1.0.0"), err(3, session="s2"), err(2, session="s3"),
                err(1, sig=DIR),
                err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 1",
                    detail="Traceback (most recent call last): x", cause="python traceback"),
                err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 2", sec=200,
                    detail="bash: unexpected EOF while looking for matching `'`",
                    cause="shell quoting")]
        self.spill(*recs)
        ei.sync(self.spool, self.t)
        start = NOW - dt.timedelta(days=7)
        rep = ei.report(self.t, start, NOW)
        self.assertEqual(rep["open_classes"], 4)      # one per family
        self.assertEqual(rep["errors_in_window"], 5)
        rows = {r["family"]: r for r in rep["classes"]}
        self.assertEqual(set(rows), {F_NT, F_DIR, "Bash: python traceback", "Bash: shell quoting"})
        self.assertEqual((rows[F_NT]["count"], rows[F_NT]["in_window"]), (3, 2))
        self.assertEqual(rows[F_NT]["instances"], ["author"])
        self.assertTrue(rows[F_NT]["recurring"])      # two calendar weeks
        fams = {f["family"] for f in rep["families"]}
        self.assertEqual(fams, set(rows))
        self.assertTrue(all(r["issue"] for r in rep["classes"]))

    def test_regression_state_survives_the_round_trip(self):
        self.spill(err(10, ver="1.0.0"))
        ei.sync(self.spool, self.t)
        ei.resolve(self.t, families=[F_NT], commit="abc1234", version="1.1.0",
                   now=NOW - dt.timedelta(days=5))
        self.spill(err(1, ver="1.2.0"))
        ei.sync(self.spool, self.t)
        rep = ei.report(self.t, NOW - dt.timedelta(days=7), NOW)
        (row,) = rep["classes"]
        self.assertTrue(row["regression"])
        self.assertEqual(row["count"], 1)       # only the errors since the resolve

    def test_resolve_by_family_or_signature_posts_no_note(self):
        self.spill(err(2), err(2, sig=GONE), err(2, sig=DIR))
        ei.sync(self.spool, self.t)
        closed, missing = ei.resolve(self.t, [GONE, "Nope: x"], [F_NT], by="Ada",
                                     commit="abc1234", version="2.0.0")
        self.assertEqual(missing, ["Nope: x"])
        self.assertEqual(sorted(f for f, _ in closed), sorted([F_NT, F_GONE]))
        for _, n in closed:
            self.assertEqual(self.gh.issues[n]["state"], "closed")
            self.assertEqual(self.gh.issues[n]["state_reason"], "completed")
            body = self.gh.comments[n][-1]["body"]
            self.assertIn("Resolved by other.", body)
            self.assertIn("abc1234", body)
            self.assertEqual(ei.meta_of(self.gh.issues[n])["fix"],
                             {"commit": "abc1234", "version": "2.0.0"})
        self.assertEqual(self.gh.by_family(F_DIR)["state"], "open")
        self.assertNotIn("Ada", json.dumps(self.gh.sent))

    def test_settle_closes_only_the_quiet(self):
        self.spill(err(20, sig=GONE), err(2, sig=DIR))
        ei.sync(self.spool, self.t)
        closed = ei.settle(self.t, 7, now=NOW)
        self.assertEqual([f for f, _ in closed], [F_GONE])
        self.assertEqual(self.gh.by_family(F_DIR)["state"], "open")


class MigrateTests(Case):
    def ledger(self):
        board = os.path.join(self.d, "board")
        el.append(board, "a@x", err(30, sig=GONE))
        el.append(board, "a@x", {"t": "resolve", "ts": at(25), "sig": GONE,
                                 "by": "human", "note": "ok", "commit": "abc1234"})
        el.append(board, "a@x", err(20, sig=DIR))
        el.append(board, "a@x", err(10, sig=NT, ver="1.0.0"))
        el.append(board, "a@x", {"t": "resolve", "ts": at(9), "sig": NT,
                                 "by": "human", "note": "", "version": "1.1.0"})
        el.append(board, "b@x", err(2, sig=NT, ver="1.2.0"))
        el.append(board, "b@x", {"t": "settle", "ts": at(15), "upto": at(15), "packet": "P-1"})
        el.append(board, "b@x", err(1, sig=el.BASH_EXIT_SIG, msg="Exit code 1",
                                    detail="ordinary output"))           # benign: not imported
        return board

    def test_dry_run_counts_and_contacts_no_one(self):
        res = ei.migrate(el.read_all(self.ledger()), None, dry_run=True)
        self.assertEqual((res["families"], res["open"], res["resolved"], res["regression"]),
                         (3, 2, 1, 1))
        self.assertEqual((res["errors"], res["resolves"]), (3, 1))
        self.assertEqual(self.gh.calls, [])

    def test_families_merge_their_classes(self):
        board = os.path.join(self.d, "board")
        el.append(board, "a@x", err(3, sig=NT))
        el.append(board, "a@x", err(2, sig=TU + ": refused: x -> y is not a transition"))
        (p,) = ei.migrate_plan(el.read_all(board))
        self.assertEqual((p["family"], len(p["errors"]), p["open"]), (F_NT, 2, True))

    def test_migrate_imports_open_and_closed_and_is_resumable(self):
        recs = el.read_all(self.ledger())
        res = ei.migrate(recs, self.t)
        self.assertEqual(res["created"], 3)
        self.assertEqual(self.gh.by_family(F_GONE)["state"], "closed")
        self.assertEqual(self.gh.by_family(F_DIR)["state"], "open")
        g = self.gh.by_family(F_NT)
        self.assertEqual(self.gh.labels(g["number"]), [ei.LABEL, ei.REGRESSION])
        start = NOW - dt.timedelta(days=7)
        rep = ei.report(self.t, start, NOW)
        self.assertEqual(sorted(r["family"] for r in rep["classes"]), sorted([F_DIR, F_NT]))
        self.assertTrue(next(r for r in rep["classes"] if r["family"] == F_NT)["regression"])
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


#: one example of every leak class the 2026-11-21 dry run found; (tool, message, extra)
LEAKS = [
    ("mcp__plugin_x_x__claims_set_status",
     "refused: the verdict file does not carry nb:lem:strip-bound to proved", {}),
    ("mcp__plugin_x_x__claims_attach_evidence", "refused: no claim `nb:GEO-12` in nb", {}),
    ("mcp__plugin_x_x__claims_attach_evidence", "refused: no claim 'nb:EX-7' in claims", {}),
    ("mcp__plugin_x_x__claims_new", "refused: GEO-12 and ex-7 and Geo-12 are taken", {}),
    ("mcp__plugin_x_x__claims_new", "refused: the verdict file does not carry hidden-orbit-count", {}),
    ("Read", "File not readable: audits/secretslug/A.md", {"path": "audits/secretslug/A.md",
                                                          "cwd": "/home/ada/lab"}),
    ("mcp__plugin_x_x__claims_attach_evidence",
     "refused: results/2026-11-03_secret_experiment.json is not an existing file", {}),
    ("mcp__plugin_x_x__queue_log", "no job 2026-11-03_secret_experiment* in queue", {}),
    ("mcp__plugin_x_x__library_verify_quote", "Smith2019sec.txt is not cached", {}),
    ("mcp__plugin_x_x__library_lookup", "a library key looks like abc19, got Smith2019sec", {}),
    ("WebFetch", "getaddrinfo ENOTFOUND private.example.org", {}),
    ("WebFetch", "connect ECONNREFUSED host.internal.lan:443", {}),
    ("Bash", "Exit code 2\ncat: C:\\Users\\ada\\proj\\x.py: No such file or directory",
     {"cmd": "cat C:/Users/ada/proj/x.py", "detail": "cat: C:\\Users\\ada\\proj\\x.py: No such file"}),
    ("Read", "Cannot read C:/Users/ada/proj and C:\\Users\\ada\\proj today", {}),
    ("mcp__plugin_x_x__tickets_update", "no ticket for session_01ABCdefGHI in 3f2a9c1e-77aa-4bb2-9c1d-0e5f6a7b8c9d", {}),
    ("mcp__plugin_x_x__tickets_update", "refused: only Ada Lovelace may close this", {}),
    ("mcp__plugin_x_x__library_search", "bad fts query: no such column: manifold", {}),
    ("mcp__plugin_x_x__config_get", "unknown instance author@main (have: expert@remote-a)", {}),
    ("Grep", "search failed on pattern hidden_orbit_count", {"pattern": "hidden_orbit_count"}),
]
#: what must never reach GitHub (case-insensitive, whole words where it matters)
PRIVATE = re.compile(
    r"(?i)strip-bound|\bstrip\b|geo-?12|\bex-?7\b|nb:|secretslug|secret|smith|abc19|"
    r"private\.example|internal\.lan|\bada\b|lovelace|users|session_|3f2a9c1e|"
    r"hidden.orbit|\borbit\b|manifold|@main|remote-a|author@|expert@|\bproj\b|"
    r"\bcat\b|2026-11-03_|\blab\b|\bnote\b|lovely|a fix by|lan:443")


class LeakTests(Case):
    """End to end: a ledger with every leak class goes through sync, migrate, resolve and
    settle; every write's payload is scanned."""

    def records(self, days=1):
        out = []
        for k, (tool, msg, extra) in enumerate(LEAKS):
            rec = {"t": "error", "ts": at(days, k), "session": "session_01ABCdefGHI",
                   "instance": ["author@main", "expert@remote-a", "workspace"][k % 3],
                   "tool": tool, "sig": el.signature(tool, msg), "msg": el.clean_message(msg),
                   "agent": "nb:ada-agent", "rev": "0123abcdef12", "ver": "0.2.10"}
            rec.update(extra)
            if tool == "Bash":
                rec["cause"] = el.bash_cause(rec)
            out.append(rec)
            # the same message as an old hook recorded it: the raw text as its signature
            out.append(dict(rec, ts=at(days, 100 + k),
                            sig="%s: %s" % (tool, el.first_line(msg).lower()[:100])))
        return out

    def scan(self):
        self.assertTrue(self.gh.sent)
        text = json.dumps(self.gh.sent, ensure_ascii=False)
        self.assertIsNone(re.search(r"\d\d:\d\d", text), "a time of day was posted")
        hits = sorted(set(m.group(0) for m in PRIVATE.finditer(text)))
        self.assertEqual(hits, [], "private text reached GitHub")
        for _, _, payload in self.gh.sent:
            for v in payload.values():
                for s in (v if isinstance(v, list) else [v]):
                    ei.check_public(s)

    def test_sync_resolve_settle_leak_nothing(self):
        self.spill(*self.records())
        res = ei.sync(self.spool, self.t)
        self.assertIsNone(res["error"])
        self.assertGreater(len(self.gh.issues), 5)
        ei.resolve(self.t, families=[r["family"] for r in res["posted"][:3]], by="Ada Lovelace",
                   commit="abc1234", version="0.2.11")
        self.spill(*self.records(0))                      # recurrences reopen
        ei.sync(self.spool, self.t)
        ei.settle(self.t, 0, now=NOW + dt.timedelta(days=30))
        self.scan()

    def test_migrate_leaks_nothing(self):
        board = os.path.join(self.d, "board")
        for r in self.records(20):
            el.append(board, "author@main", r)
        el.append(board, "author@main", {"t": "resolve", "ts": at(15), "by": "Ada Lovelace",
                                         "sig": self.records()[0]["sig"],
                                         "note": "a fix by Ada for nb:GEO-12 (lovely)",
                                         "commit": "abc1234"})
        for r in self.records(1):
            el.append(board, "expert@remote-a", r)
        res = ei.migrate(el.read_all(board), self.t)
        self.assertGreater(res["created"], 5)
        self.scan()


#: what an id or a path looks like in a posted text (the real-ledger scan)
RE_IDLIKE = re.compile(r"(?i:\b[a-z]{1,10}-\d+\b)|(?<![\w:])[a-z][a-z0-9]*:[a-z][\w.-]*:"
                       r"|(?i:[\w.-]+/[\w.-]+\.[a-z]{1,5}\b|\b[a-z]:\\|\w@\w|session_"
                       r"|\b[\w-]+\.(?:com|org|net|edu|io)\b)")


class RealLedgerTests(unittest.TestCase):
    """Opt in: ``ACADEMY_ERRORS_LEDGER=<board>/.errors`` migrates a real ledger, read-only,
    into a fake GitHub and scans every text it would post."""

    def test_every_real_family_posts_safely(self):
        where = os.environ.get("ACADEMY_ERRORS_LEDGER")
        if not where:
            self.skipTest("ACADEMY_ERRORS_LEDGER not set")
        gh = FakeGitHub()
        res = ei.migrate(el.read_dirs([where]), ei.transport("me/academy", run=gh,
                                                             write_interval=0))
        self.assertEqual(res["created"], res["to_import"])
        self.assertTrue(gh.sent)
        for _, _, payload in gh.sent:
            for v in payload.values():
                for text in (v if isinstance(v, list) else [v]):
                    ei.check_public(text)
                    plain = str(text).replace("\\u003c", "<").replace("\\u003e", ">")
                    self.assertIsNone(RE_IDLIKE.search(plain), RE_IDLIKE.search(plain))


class ReviewFindingTests(Case):
    """The 2026-11-21 review of the family issues."""

    def test_the_unlisted_hash_is_of_the_skeleton(self):
        a = ei.public_family("library_search: bad fts query <q>: no such column: manifold")
        b = ei.public_family("library_search: bad fts query <q>: no such column: lattice")
        self.assertEqual(a, b)
        self.assertRegex(a, r"^library_search: \(unlisted family [0-9a-f]{12}\)$")
        c = ei.public_family("library_search: bad fts query <q>: no such table: lattice")
        self.assertNotEqual(a, c)
        self.assertEqual(ei.public_family("adalovelace_tool: x"),
                         ei.public_family("adabyron_tool: x"))
        raws = ["library_search: bad fts query <q>: no such column: manifold",
                "adalovelace_tool: x"] + [el.family(el.signature(t, m)) for t, m, _ in LEAKS]
        hashes = {re.search(r"[0-9a-f]{12}", ei.public_family(r)).group(0)
                  for r in raws if ei.RE_UNLISTED.search(ei.public_family(r))}
        self.assertTrue(hashes)
        for r in raws:
            self.assertNotIn(ei.hashlib.sha1(r.encode("utf-8")).hexdigest()[:12], hashes)

    def test_a_malformed_time_is_skipped_not_fatal(self):
        self.spill(err(2, ts="2026-11-17T10:00:00.123Z"), err(1))
        bad = dict(err(1, sec=5), ts="2026-11-18T10:00:00Z")
        self.spill(bad)
        res = ei.sync(self.spool, self.t)
        self.assertIsNone(res["error"])
        self.assertEqual((res["records"], res["skipped"]), (1, 2))
        self.assertEqual(ei.sync(self.spool, self.t)["records"], 0)
        board = os.path.join(self.d, "board")
        el.append(board, "a@x", bad)
        el.append(board, "a@x", err(1, sig=DIR))
        self.assertEqual(len(el.read_all(board)), 1)         # the reader skips it too
        res = ei.migrate(el.read_all(board) + [bad], None, dry_run=True)
        self.assertEqual((res["families"], res["skipped"]), (1, 1))

    def test_a_maintainer_label_passes_through(self):
        self.spill(err(5, ver="1.0.0"))
        ei.sync(self.spool, self.t)
        n = self.gh.by_family(F_NT)["number"]
        self.gh.add_label(n, "p1")
        self.gh.add_label(n, "Ada-todo")
        closed, _ = ei.resolve(self.t, families=[F_NT], version="1.1.0")
        self.assertEqual(len(closed), 1)
        self.spill(err(1, ver="1.2.0"))
        self.assertIsNone(ei.sync(self.spool, self.t)["error"])
        self.assertEqual(self.gh.labels(n), sorted(["Ada-todo", ei.LABEL, "p1", ei.REGRESSION]))
        self.assertEqual(ei.settle(self.t, 0, now=NOW + dt.timedelta(days=9))[0][1], n)
        with self.assertRaises(ei.Unsafe):          # a label the module adds is gated
            self.t.create_issue("error family: x", "x", ["Ada-todo"])

    def test_a_shell_signature_is_resolved_by_cause(self):
        closed, missing = ei.resolve(self.t, [el.BASH_EXIT_SIG])
        self.assertEqual((closed, missing), ([], [el.BASH_EXIT_SIG]))
        hint = ei.shell_hint(el.BASH_EXIT_SIG)
        self.assertIn('--family "Bash: <cause>"', hint)
        self.assertIn("python traceback", hint)

    def test_a_strangers_comment_is_not_read(self):
        self.spill(err(2))
        ei.sync(self.spool, self.t)
        n = self.gh.by_family(F_NT)["number"]
        self.gh.stranger_comment(n, ei.hidden("occurrences", [["2026-11-18", "author", "", "", ""]] * 50))
        rep = ei.report(self.t, NOW - dt.timedelta(days=7), NOW)
        self.assertEqual(rep["classes"][0]["count"], 1)
        # nor does a stranger's batch marker stop a post
        self.gh.stranger_comment(n, "<!-- batch:%s part 1/1 -->" % ei.batch_id(
            ei.public_family(F_NT), [err(1)]))
        self.spill(err(1))
        ei.sync(self.spool, self.t)
        self.assertEqual(len([c for c in self.gh.comments[n] if c["user"]["login"] == "poster"]), 2)

    def test_a_second_account_of_the_repo_is_trusted(self):
        self.spill(err(2))
        ei.sync(self.spool, self.t)
        n = self.gh.by_family(F_NT)["number"]
        row = ei.hidden("occurrences", [["2026-11-18", "expert", "", "", ""]])
        self.gh.stranger_comment(n, row, login="laptop", association="COLLABORATOR")
        self.gh.stranger_comment(n, row, login="member", association="MEMBER")
        self.gh.stranger_comment(n, row, login="drive-by", association="CONTRIBUTOR")
        self.gh.stranger_comment(n, row, login="listed", association="NONE")
        start = NOW - dt.timedelta(days=7)
        self.assertEqual(ei.report(self.t, start, NOW)["classes"][0]["count"], 3)
        t = ei.transport("me/academy", run=self.gh, write_interval=0, posters=["listed"])
        self.assertEqual(ei.report(t, start, NOW)["classes"][0]["count"], 4)
        # a retry from the other account's machine sees the first one's batch marker
        self.gh.login = "laptop"
        other = ei.transport("me/academy", run=self.gh, write_interval=0)
        self.assertEqual(len(ei.comments_of(other, self.gh.issues[n])), 3)   # not drive-by, not listed

    def test_the_batch_id_is_salted(self):
        fam = ei.public_family(F_NT)
        recs = [err(1)]
        self.assertNotEqual(ei.batch_id(fam, recs, "a" * 32), ei.batch_id(fam, recs, "b" * 32))
        self.spill(err(1))
        self.gh.fail_on = ["POST", "/comments", 1]
        self.assertTrue(ei.sync(self.spool, self.t)["error"])
        salt = ei.load_cursor(self.spool)["salt"]
        self.assertRegex(salt, r"^[0-9a-f]{32}$")
        first = ei.meta_of(self.gh.by_family(F_NT))["batch"]
        self.assertIsNone(ei.sync(self.spool, self.t)["error"])     # the retry
        self.assertEqual(ei.load_cursor(self.spool)["salt"], salt)
        self.assertEqual(ei.meta_of(self.gh.by_family(F_NT))["batch"], first)
        self.assertEqual(len(self.gh.comments[1]), 1)
        other = os.path.join(self.d, "spool2")
        el.append_file(el.spool_file(other, "author@x"), err(1))
        ei.sync(other, self.t)
        self.assertNotEqual(ei.load_cursor(other)["salt"], salt)

    def test_a_mid_day_window_keeps_that_day_and_says_bursts_are_daily(self):
        self.spill(err(7, sec=-3600))                   # 11:00, seven days back
        ei.sync(self.spool, self.t)
        start = NOW - dt.timedelta(days=7)              # 12:00 that day
        rep = ei.report(self.t, start, NOW)
        self.assertEqual(rep["classes"][0]["in_window"], 1)
        self.assertIn("per day", rep["note"])
        self.assertIn("per day", el.render_markdown(rep))

    def test_read_dirs_says_what_it_dropped(self):
        d = os.path.join(self.d, "ledger")
        el.append_file(os.path.join(d, "a.jsonl"), dict(err(1), ts="2026-11-18T10:00:00Z"))
        el.append_file(os.path.join(d, "a.jsonl"), err(1))
        errs = io.StringIO()
        with contextlib.redirect_stderr(errs):
            self.assertEqual(len(el.read_dirs([d])), 1)
        self.assertIn("1 record(s) with a malformed time", errs.getvalue())

    def test_settle_keeps_the_fix(self):
        self.spill(err(10, ver="1.0.0"))
        ei.sync(self.spool, self.t)
        ei.resolve(self.t, families=[F_NT], commit="abc1234", version="1.1.0",
                   now=NOW - dt.timedelta(days=9))
        self.spill(err(8, ver="1.2.0"))
        ei.sync(self.spool, self.t)
        n = self.gh.by_family(F_NT)["number"]
        ei.settle(self.t, 7, now=NOW)
        self.assertEqual(self.gh.issues[n]["state"], "closed")
        self.assertEqual(ei.meta_of(self.gh.issues[n])["fix"],
                         {"commit": "abc1234", "version": "1.1.0"})

    def test_migrate_onto_an_existing_issue_merges_its_fields(self):
        self.spill(err(1))
        ei.sync(self.spool, self.t)
        board = os.path.join(self.d, "board")
        el.append(board, "a@x", err(3, instance="expert@y"))
        el.append(board, "a@x", err(2, instance="expert@y"))
        res = ei.migrate(el.read_all(board), self.t)
        self.assertEqual((res["created"], res["completed"]), (0, 1))
        meta = ei.meta_of(self.gh.by_family(F_NT))
        self.assertEqual((meta["count"], meta["roles"], meta["first"]),
                         (3, {"author": 1, "expert": 2}, at(3)[:10]))

    def test_versions_and_rows_are_coarse(self):
        self.assertEqual([ei.clean_ver(v) for v in ("0.2.10", "1234.1", "1.2.3.4", "1.2.3.4.5")],
                         ["0.2.10", "", "1.2.3.4", ""])
        self.spill(err(1))
        ei.sync(self.spool, self.t)
        (rows,) = ei.read_hidden("occurrences", self.gh.comments[1][0]["body"])
        self.assertRegex(rows[0][0], r"^\d{4}-\d\d-\d\d$")


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
        rc, out, _ = self.cli("resolve", NT, "--note", "x")
        self.assertEqual(rc, 0)
        self.assertEqual(el.classes(el.read_all(self.board)), {})

    def test_sync_report_resolve_settle_through_the_cli(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        self.use_fake()
        el.append_file(el.spool_file(self.spool, "author@t"), err(1))
        el.append_file(el.spool_file(self.spool, "author@t"), err(1, sig=GONE))
        rc, out, _ = self.cli("sync", "--dry-run")
        self.assertEqual((rc, self.gh.calls), (0, []))
        self.assertIn("2 record(s) of 2 family(ies) would post", out)
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
        rc, out, _ = self.cli("resolve", "--family", F_GONE, "--note", "noise from nb:GEO-12",
                              "--by", "Ada")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.gh.by_family(F_GONE)["state"], "closed")
        self.assertNotIn("GEO", json.dumps(self.gh.sent))
        local = [r for r in el.read_dirs([self.spool]) if r["t"] == "resolve"]
        self.assertEqual([(r["family"], r["note"], r["by"]) for r in local],
                         [(F_GONE, "noise from nb:GEO-12", "Ada")])
        rc, out, _ = self.cli("report", "--json", "--local")
        self.assertEqual([r["sig"] for r in json.loads(out)["classes"]], [NT])
        rc, out, _ = self.cli("settle", "--quiet-days", "30", "--packet", "P-0042")
        self.assertEqual(rc, 0)
        self.assertIn("0 issue(s) closed", out)
        self.assertNotIn("P-0042", json.dumps(self.gh.sent))
        rc, out, _ = self.cli("settle", "--quiet-days", "0", "--packet", "P-0043")
        self.assertIn("1 issue(s) closed", out)
        rc, out, _ = self.cli("report", "--json", "--local")
        self.assertEqual(json.loads(out)["classes"], [])           # closed locally too
        rc, out, errs = self.cli("resolve", el.BASH_EXIT_SIG)
        self.assertEqual(rc, 1)
        self.assertIn('--family "Bash: <cause>"', errs)

    def test_report_falls_back_to_the_local_files_when_github_fails(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        self.gh.fail_on = ["GET", "", 1]
        self.use_fake()
        el.append(self.board, "author@t", err(1, sig=DIR))
        el.append_file(el.spool_file(self.spool, "author@t"), err(1))
        rc, out, errs = self.cli("report", "--json")
        self.assertEqual(rc, 0)
        self.assertIn("not read", errs)
        self.assertEqual(json.loads(out)["open_classes"], 2)

    def test_report_local_reads_the_local_files_with_their_detail(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        self.use_fake()
        el.append_file(el.spool_file(self.spool, "author@t"), err(1))
        rc, out, _ = self.cli("report", "--json", "--local")
        self.assertEqual(rc, 0)
        self.assertEqual(self.gh.calls, [])
        (row,) = json.loads(out)["classes"]
        self.assertEqual((row["sig"], row["instances"]), (NT, ["author@x"]))

    def test_migrate_dry_run_on_the_cli(self):
        self.make({"repo": "me/academy", "spool": "spool"})
        self.use_fake()
        el.append(self.board, "author@t", err(1))
        el.append(self.board, "author@t", err(1, sig="Bash: boom <n>"))
        rc, out, _ = self.cli("migrate", "--dry-run")
        self.assertEqual((rc, self.gh.calls), (0, []))
        self.assertIn("families: 2 (open 2", out)
        self.assertIn("unlisted 1", out)


if __name__ == "__main__":
    unittest.main()
