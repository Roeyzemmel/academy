"""Tests for error_ledger.py: accumulation by the hook, the weekly report and settle.

Run from the repo root:  py -m unittest discover academy/tests
"""

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPTS = os.path.join(PLUGIN, "scripts")
sys.path.insert(0, SCRIPTS)

import error_ledger as el  # noqa: E402

NOW = dt.datetime(2026, 9, 30, 12, 0, 0)


def at(days_ago):
    return el._stamp(NOW - dt.timedelta(days=days_ago))


def err(days_ago, sig, session="s1", instance="author@x"):
    return {"t": "error", "ts": at(days_ago), "session": session, "instance": instance,
            "tool": "Bash", "sig": sig, "msg": sig}


class SignatureTests(unittest.TestCase):
    def test_normalises_paths_numbers_and_ids(self):
        a = el.signature("Bash", "cat: /home/u/x/file1.txt: No such file (exit 2)")
        b = el.signature("Bash", "cat: /tmp/y/other.txt: No such file (exit 7)")
        self.assertEqual(a, b)
        self.assertNotEqual(a, el.signature("Read", "cat: /a/b: No such file (exit 2)"))

    def test_reason_on_the_next_line_is_kept(self):
        msg = "refused: the grounds do not support x -> proved:\n- statement hash A is not current B\n- more"
        self.assertEqual(el.clean_message(msg),
                         "refused: the grounds do not support x -> proved: statement hash A is not current B")
        self.assertEqual(el.signature("t", msg), el.signature("t", msg.split("\n")[0]))

    def test_first_line_only(self):
        self.assertEqual(el.signature("Bash", "boom\ntraceback line"),
                         el.signature("Bash", "boom\nother"))

    def test_redacts_secrets(self):
        m = el.clean_message("auth failed token=abc123secret and ghp_" + "a" * 30)
        self.assertNotIn("abc123secret", m)
        self.assertNotIn("ghp_", m)

    def test_declined_call_is_noise(self):
        self.assertTrue(el.is_noise("The user doesn't want to proceed with this tool use."))
        self.assertFalse(el.is_noise("exit code 1"))


class FamilyTests(unittest.TestCase):
    def fam(self, tool, msg):
        return el.family(el.signature(tool, msg))

    def test_folds_variants_of_one_reason(self):
        t = "mcp__plugin_academy_academy__claims_set_status"
        a = self.fam(t, "refused: the grounds do not support paper:lem:a -> proved:")
        b = self.fam(t, "refused: the grounds do not support flat:per-3 -> sketch:")
        self.assertEqual(a, b)
        self.assertEqual(a, "claims_set_status: grounds do not support")
        t = "mcp__plugin_academy_academy__tickets_update"
        self.assertEqual(self.fam(t, "refused: open -> delivered is not a transition"),
                         "tickets_update: not a transition")
        self.assertEqual(self.fam(t, "refused: blocked -> open is not a transition"),
                         "tickets_update: not a transition")

    def test_kb_path_and_web_families(self):
        t = "mcp__plugin_academy_academy__claims_set_status"
        self.assertEqual(
            self.fam(t, "refused: set-status: refused: the kb does not build with fnd-3 at proved"),
            self.fam(t, "refused: set-status: refused: the kb does not build with per-9 at sketch"))
        self.assertEqual(self.fam("Read", "File does not exist. Note: your cwd is /a/b"),
                         "Read: path does not exist")
        self.assertEqual(self.fam("Glob", "Directory does not exist: /a/b"),
                         "Glob: path does not exist")
        self.assertEqual(self.fam("WebFetch", "getaddrinfo ENOTFOUND arxiv.org"),
                         "WebFetch: host unreachable")
        self.assertEqual(self.fam("WebFetch",
                         '{"error_type":"EGRESS_BLOCKED","domain":"x.org","message":"blocked"}'),
                         "WebFetch: host unreachable")

    def test_three_more_families(self):
        t = "mcp__plugin_academy_academy__"
        self.assertEqual(self.fam(t + "domain_get", "no domain pack 'translation-surfaces' (have: none)"),
                         "domain_get: no domain pack")
        self.assertEqual(self.fam(t + "tickets_update", "delivered needs result (fields.result)"),
                         "tickets_update: delivered needs result")
        a = self.fam(t + "claims_set_status", "refused: T-0187 does not contain the quote 'Yes' verbatim")
        b = self.fam(t + "claims_set_status", "refused: T-0001 does not contain the quote 'No' verbatim")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("claims_set_status: "))

    def test_fallback_is_the_signature(self):
        sig = el.signature("Bash", "Exit code 1")
        self.assertEqual(el.family(sig), sig)


class TopFamiliesTests(unittest.TestCase):
    def test_section_precedes_class_table_and_folds(self):
        t = "mcp__plugin_academy_academy__claims_set_status"
        recs = []
        for i in range(3):
            m = "refused: the grounds do not support paper:lem:x%s -> proved:" % "abc"[i]
            recs.append({"t": "error", "ts": at(1), "session": "s%d" % i, "instance": "i",
                         "tool": t, "sig": el.signature(t, m), "msg": m})
        recs.append(err(1, "Bash: exit code <n>"))
        rep = el.report(recs, NOW - dt.timedelta(days=7), now=NOW)
        top = rep["families"][0]
        self.assertEqual((top["family"], top["in_window"], top["classes"], top["sessions"]),
                         ("claims_set_status: grounds do not support", 3, 3, 3))
        md = el.render_markdown(rep)
        self.assertIn("## Top families", md)
        self.assertLess(md.index("## Top families"), md.index("| class |"))
        self.assertIn("Example messages:", md)

    def test_bash_exit_code_splits_by_command_word(self):
        recs = []
        for i, cmd in enumerate(["git status", "git push", "py x.py", "python3 -c 1",
                                 "ls -l", None]):
            r = err(1, "Bash: exit code <n>", session="s%d" % i)
            if cmd:
                r["cmd"] = cmd
            recs.append(r)
        fams = {f["family"]: f for f in
                el.report(recs, NOW - dt.timedelta(days=7), now=NOW)["families"]}
        self.assertEqual({k: v["in_window"] for k, v in fams.items()},
                         {"Bash: exit code (git)": 2, "Bash: exit code (py)": 1,
                          "Bash: exit code (python3)": 1, "Bash: exit code (other)": 1,
                          "Bash: exit code (unknown cmd)": 1})
        self.assertEqual(el.family("Bash: exit code <n>"), "Bash: exit code <n>")
        self.assertEqual(el.family_of("Bash: exit code <n>", {"cmd": "git x"}),
                         "Bash: exit code (git)")

    def test_at_most_ten(self):
        recs = [err(1, "Tool%d: boom" % i) for i in range(15)]
        md = el.render_markdown(el.report(recs, NOW - dt.timedelta(days=7), now=NOW))
        sect = md.split("## Top families")[1].split("| class |")[0]
        self.assertEqual(sect.count("\n| `"), 10)


class BurstTests(unittest.TestCase):
    SIG = "Bash: boom"

    def _rec(self, secs, session="s1", sig=None):
        ts = el._stamp(NOW - dt.timedelta(days=1) + dt.timedelta(seconds=secs))
        return {"t": "error", "ts": ts, "session": session, "instance": "i", "tool": "Bash",
                "sig": sig or self.SIG, "msg": "boom"}

    def _rep(self, recs):
        return el.report(recs, NOW - dt.timedelta(days=7), now=NOW)

    def test_retry_burst_counts_once(self):
        rep = self._rep([self._rec(2 * i) for i in range(8)])  # 8 records in 14 s
        c = rep["classes"][0]
        self.assertEqual((c["count"], c["in_window"], c["bursts"]), (8, 8, 1))
        f = rep["families"][0]
        self.assertEqual((f["count"], f["in_window"], f["bursts"]), (8, 8, 1))

    def test_two_sessions_two_bursts(self):
        rep = self._rep([self._rec(0, "a"), self._rec(1, "b"), self._rec(2, "a")])
        self.assertEqual(rep["classes"][0]["bursts"], 2)
        self.assertEqual(rep["families"][0]["bursts"], 2)

    def test_gap_over_sixty_seconds_splits(self):
        self.assertEqual(self._rep([self._rec(0), self._rec(61)])["classes"][0]["bursts"], 2)
        self.assertEqual(self._rep([self._rec(0), self._rec(60)])["classes"][0]["bursts"], 1)

    def test_families_rank_by_bursts_then_count(self):
        noisy = [self._rec(i, sig="Bash: noisy") for i in range(20)]       # 20 raw, 1 burst
        spread = [self._rec(1000 * i, "s%d" % i, sig="Bash: spread") for i in range(3)]
        rep = self._rep(noisy + spread)
        self.assertEqual([f["family"] for f in rep["families"]], ["Bash: spread", "Bash: noisy"])
        md = el.render_markdown(rep)
        self.assertIn("| family | in window | bursts |", md)

    def test_bursts_outside_window_not_counted_in_window(self):
        old = self._rec(0)
        old["ts"] = at(30)
        rep = self._rep([old, self._rec(0)])
        self.assertEqual((rep["classes"][0]["count"], rep["classes"][0]["bursts"]), (2, 1))


class HookRecordTests(unittest.TestCase):
    def test_record_has_no_tool_input(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "curl -H 'Bearer supersecrettoken1'"},
              "error": "Exit code 22\ncurl failed", "session_id": "S"}
        rec = el.hook_record(ev, "author@x", NOW)
        self.assertEqual(rec["tool"], "Bash")
        self.assertEqual(rec["instance"], "author@x")
        self.assertNotIn("supersecrettoken1", json.dumps(rec))

    def test_record_carries_the_agent(self):
        # U2: a subagent's failure names the agent (namespaced, redacted); the main
        # session is MAIN, so a missing field means an old record, not the main session
        ev = {"tool_name": "Bash", "error": "Exit code 1\nx", "session_id": "S",
              "agent_type": "author:math-writer"}
        self.assertEqual(el.hook_record(ev, "author@x", NOW)["agent"], "author:math-writer")
        ev = {"tool_name": "Bash", "error": "Exit code 1\nx", "session_id": "S"}
        self.assertEqual(el.hook_record(ev, "author@x", NOW)["agent"], "MAIN")
        ev["agent_type"] = "x:tok token=abcdefghijklmnop"
        self.assertNotIn("abcdefghijklmnop", el.hook_record(ev, "i", NOW)["agent"])

    def test_interrupt_and_empty_are_skipped(self):
        self.assertIsNone(el.hook_record({"tool_name": "Bash", "error": "x",
                                          "is_interrupt": True}, "i", NOW))
        self.assertIsNone(el.hook_record({"tool_name": "Bash", "error": ""}, "i", NOW))


class ContextTests(unittest.TestCase):
    """2026-10-09 fix 9: Bash errors say what failed, file errors where."""

    def test_bash_records_stderr_and_command_heads(self):
        ev = {"tool_name": "Bash", "session_id": "S",
              "tool_input": {"command": "py scripts/x.py --token=abc123secret\nsecond line"},
              "error": "Exit code 2\nTraceback (most recent call last):\n  File x\n"
                       "ValueError: bad thing"}
        rec = el.hook_record(ev, "author@x", NOW)
        self.assertIn("Traceback", rec["detail"])
        self.assertIn("ValueError: bad thing", rec["detail"])
        self.assertTrue(rec["cmd"].startswith("py scripts/x.py"))
        self.assertNotIn("second line", rec["cmd"])
        self.assertNotIn("abc123secret", json.dumps(rec))

    def test_search_with_no_match_is_not_a_fault(self):
        """grep/rg/diff exit 1 with no output is an answer, not an error."""
        for cmd in ("git status --short | grep Billiard", "rg -n foo academy", "diff a b"):
            ev = {"tool_name": "Bash", "tool_input": {"command": cmd}, "error": "Exit code 1"}
            self.assertIsNone(el.hook_record(ev, "i", NOW), cmd)
        ev = {"tool_name": "Bash", "tool_input": {"command": "grep x f"},
              "error": "Exit code 2\ngrep: f: No such file or directory"}
        self.assertIsNotNone(el.hook_record(ev, "i", NOW))
        ev = {"tool_name": "Bash", "tool_input": {"command": "py x.py"}, "error": "Exit code 1"}
        self.assertIsNotNone(el.hook_record(ev, "i", NOW))

    def test_file_tools_record_cwd_and_path(self):
        ev = {"tool_name": "Read", "session_id": "S", "cwd": "/w/PaperHome",
              "tool_input": {"file_path": "/w/board"},
              "error": "EISDIR: illegal operation on a directory, read"}
        rec = el.hook_record(ev, "author@x", NOW)
        self.assertEqual((rec["cwd"], rec["path"]), ("/w/PaperHome", "/w/board"))
        ev = {"tool_name": "Glob", "cwd": "/w/library",
              "tool_input": {"pattern": "**/*.tex", "path": "/w/library/Mo06.src"},
              "error": "Directory does not exist"}
        rec = el.hook_record(ev, "expert@x", NOW)
        self.assertEqual(rec["path"], "/w/library/Mo06.src")
        self.assertEqual(rec["pattern"], "**/*.tex")

    def test_identical_entries_are_written_once(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        rec = el.hook_record({"tool_name": "Bash", "error": "Exit code 1\nx",
                              "session_id": "S"}, "i@x", NOW)
        self.assertTrue(el.append(d, "i@x", rec))
        self.assertFalse(el.append(d, "i@x", dict(rec)))
        self.assertTrue(el.append(d, "i@x", dict(rec, msg="Exit code 2")))
        with open(el.ledger_file(d, "i@x"), encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().splitlines()), 2)
        # duplicates already in a ledger (before the fix) count once
        with open(el.ledger_file(d, "i@x"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        self.assertEqual(len(el.read_all(d)), 2)


class WeeklyCycleTests(unittest.TestCase):
    def test_open_classes_and_resolve(self):
        recs = [err(10, "A"), err(3, "A", "s2"), err(2, "B"),
                {"t": "resolve", "ts": at(2), "sig": "A"}, err(1, "A", "s3")]
        cls = el.classes(recs)
        self.assertEqual(cls["A"]["count"], 1)  # only the error after the resolve
        self.assertEqual(cls["B"]["count"], 1)

    def test_report_recurring_and_carried(self):
        recs = [err(20, "old"), err(9, "old", "s2"), err(1, "new")]
        rep = el.report(recs, NOW - dt.timedelta(days=7), NOW)
        by = {r["sig"]: r for r in rep["classes"]}
        self.assertEqual(by["old"]["in_window"], 0)
        self.assertTrue(by["old"]["recurring"])  # seen in two calendar weeks
        self.assertEqual(by["old"]["weeks_open"], 3)
        self.assertFalse(by["new"]["recurring"])
        self.assertEqual(rep["errors_in_window"], 1)
        self.assertIn("`new`", el.render_markdown(rep))

    def test_three_sessions_is_recurring(self):
        recs = [err(1, "X", "a"), err(1, "X", "b"), err(1, "X", "c")]
        self.assertTrue(el.report(recs, NOW - dt.timedelta(days=7), NOW)["classes"][0]["recurring"])


class LedgerFileTests(unittest.TestCase):
    def setUp(self):
        self.board = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.board, True)

    def test_settle_closes_only_reported_and_quiet(self):
        el.append(self.board, "i@x", err(20, "quiet"))
        el.append(self.board, "i@x", err(2, "busy"))
        # first week's settle: nothing has been reported yet, so nothing closes
        self.assertEqual(el.settle(self.board, "i@x", "P-0001", 7, NOW - dt.timedelta(days=14)), [])
        el.append(self.board, "i@x", err(1, "fresh"))
        closed = el.settle(self.board, "i@x", "P-0002", 7, NOW)
        self.assertEqual(closed, ["quiet"])  # reported by P-0001, silent for 20 days
        cls = el.classes(el.read_all(self.board))
        self.assertNotIn("quiet", cls)
        self.assertIn("busy", cls)  # carried over
        self.assertTrue(cls["fresh"]["count"] == 1)

    def test_bad_lines_and_missing_board_are_tolerated(self):
        self.assertEqual(el.read_all(os.path.join(self.board, "nope")), [])
        el.append(self.board, "i@x", err(1, "A"))
        with open(el.ledger_file(self.board, "i@x"), "a") as fh:
            fh.write("not json\n")
        self.assertEqual(len(el.read_all(self.board)), 1)


class RegressionTests(unittest.TestCase):
    WIN = NOW - dt.timedelta(days=7)

    def rep(self, recs):
        return el.report(recs, self.WIN, NOW)

    def test_resolve_with_commit_then_quiet_is_closed(self):
        recs = [err(10, "A"), {"t": "resolve", "ts": at(5), "sig": "A", "commit": "abc1234"}]
        self.assertEqual(self.rep(recs)["classes"], [])

    def test_error_after_resolve_with_commit_is_regression_and_open(self):
        recs = [err(10, "A"), {"t": "resolve", "ts": at(5), "sig": "A", "commit": "abc1234"},
                err(1, "A", "s2")]
        rep = self.rep(recs)
        row = rep["classes"][0]
        self.assertEqual((row["sig"], row["count"], row["regression"]), ("A", 1, True))
        self.assertTrue(rep["families"][0]["regression"])
        self.assertEqual(row["regression_commit"], "abc1234")
        self.assertEqual(json.loads(json.dumps(rep))["classes"][0]["regression_commit"], "abc1234")
        md = el.render_markdown(rep)
        self.assertIn("| regression |", md)
        self.assertNotIn("| new |", md)

    def test_resolve_without_commit_is_as_before(self):
        recs = [err(10, "A"), {"t": "resolve", "ts": at(5), "sig": "A"}, err(1, "A", "s2")]
        rep = self.rep(recs)
        self.assertFalse(rep["classes"][0]["regression"])
        self.assertFalse(rep["families"][0]["regression"])
        self.assertIn("| new |", el.render_markdown(rep))

    def test_later_plain_resolve_clears_regression_basis(self):
        recs = [err(10, "A"), {"t": "resolve", "ts": at(8), "sig": "A", "commit": "abc"},
                {"t": "resolve", "ts": at(5), "sig": "A"}, err(1, "A", "s2")]
        self.assertFalse(self.rep(recs)["classes"][0]["regression"])

    def test_commit_in_json_and_cli(self):
        board = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, board, True)
        ws = os.path.join(board, "workspace.json")
        with open(ws, "w") as fh:
            json.dump({"board": board, "instances": {}}, fh)
        el.append(board, "i@x", {**err(10, "A"), "instance": "i@x"})
        main = lambda *a: el.main(list(a) + ["--workspace", ws])
        old = el.ac.load_workspace
        el.ac.load_workspace = lambda path=None: {"board": board, "_path": ws}
        self.addCleanup(setattr, el.ac, "load_workspace", old)
        self.assertEqual(main("resolve", "A", "--instance", "i@x", "--commit", "deadbee"), 0)
        recs = [r for r in el.read_all(board) if r["t"] == "resolve"]
        self.assertEqual(recs[0]["commit"], "deadbee")
        self.assertEqual(recs[0]["by"], "human")
        self.assertEqual(main("resolve", "B", "--instance", "i@x"), 0)
        recs = [r for r in el.read_all(board) if r["t"] == "resolve" and r["sig"] == "B"]
        self.assertNotIn("commit", recs[0])


class HookProcessTests(unittest.TestCase):
    def test_hook_end_to_end_and_never_fails(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        home, board = os.path.join(d, "home"), os.path.join(d, "board")
        os.makedirs(os.path.join(home, ".claude"))
        os.makedirs(board)
        cfg = {"schema": 1, "role": "author", "instance": "author@t", "domains": ["x"],
               "paths": {k: k for k in el.ac.REQUIRED_PATHS["author"]}, "registry": {"profile": "none"}, "author": {}}
        with open(os.path.join(home, ".claude", "academy.json"), "w") as fh:
            json.dump(cfg, fh)
        ws = os.path.join(d, "workspace.json")
        with open(ws, "w") as fh:
            json.dump({"instances": {"author@t": {"role": "author", "home": home,
                                                  "domains": ["x"]}}, "board": board}, fh)
        env = dict(os.environ, ACADEMY_WORKSPACE=ws)
        env.pop("ACADEMY_ENV_WORKSPACE", None)
        ev = {"tool_name": "Bash", "error": "Exit code 1\nboom", "cwd": home, "session_id": "S1"}
        run = lambda data: subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "error_ledger.py"), "hook"],
            input=data, capture_output=True, env=env, cwd=home, timeout=60)
        self.assertEqual(run(json.dumps(ev).encode()).returncode, 0)
        self.assertEqual(run(b"garbage").returncode, 0)
        recs = el.read_all(board)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["instance"], "author@t")
        self.assertEqual(recs[0]["session"], "S1")
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "error_ledger.py"), "report",
                              "--json"], capture_output=True, env=env, cwd=home, timeout=60)
        self.assertEqual(json.loads(out.stdout)["open_classes"], 1)


class InstanceForTests(unittest.TestCase):
    def test_workspace_root_is_not_other(self):
        d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        home = os.path.join(d, "home")
        os.makedirs(os.path.join(home, ".claude"))
        os.makedirs(os.path.join(d, "board", "sub"))
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, True)
        cfg = {"schema": 1, "role": "author", "instance": "author@t", "domains": ["x"],
               "paths": {k: k for k in el.ac.REQUIRED_PATHS["author"]},
               "registry": {"profile": "none"}, "author": {}}
        with open(os.path.join(home, ".claude", "academy.json"), "w") as fh:
            json.dump(cfg, fh)
        ws = os.path.join(d, "workspace.json")
        with open(ws, "w") as fh:
            json.dump({"instances": {"author@t": {"role": "author", "home": home,
                                                  "domains": ["x"]}},
                       "board": os.path.join(d, "board")}, fh)
        old = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = ws
        os.environ.pop("ACADEMY_ENV_WORKSPACE", None)
        try:
            f = lambda cwd: el._instance_for({"cwd": cwd})
            self.assertEqual(f(home), "author@t")
            self.assertEqual(f(d), "workspace")
            self.assertEqual(f(os.path.join(d, "board", "sub")), "workspace")
            self.assertEqual(f(outside), "other")
        finally:
            if old is None:
                os.environ.pop("ACADEMY_WORKSPACE", None)
            else:
                os.environ["ACADEMY_WORKSPACE"] = old


if __name__ == "__main__":
    unittest.main()
