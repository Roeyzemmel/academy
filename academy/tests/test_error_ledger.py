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


def err(days_ago, sig, session="s1", instance="author@bi"):
    return {"t": "error", "ts": at(days_ago), "session": session, "instance": instance,
            "tool": "Bash", "sig": sig, "msg": sig}


class SignatureTests(unittest.TestCase):
    def test_normalises_paths_numbers_and_ids(self):
        a = el.signature("Bash", "cat: /home/u/x/file1.txt: No such file (exit 2)")
        b = el.signature("Bash", "cat: /tmp/y/other.txt: No such file (exit 7)")
        self.assertEqual(a, b)
        self.assertNotEqual(a, el.signature("Read", "cat: /a/b: No such file (exit 2)"))

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


class HookRecordTests(unittest.TestCase):
    def test_record_has_no_tool_input(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "curl -H 'Bearer supersecrettoken1'"},
              "error": "Exit code 22\ncurl failed", "session_id": "S"}
        rec = el.hook_record(ev, "author@bi", NOW)
        self.assertEqual(rec["tool"], "Bash")
        self.assertEqual(rec["instance"], "author@bi")
        self.assertNotIn("supersecrettoken1", json.dumps(rec))

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
        rec = el.hook_record(ev, "author@bi", NOW)
        self.assertIn("Traceback", rec["detail"])
        self.assertIn("ValueError: bad thing", rec["detail"])
        self.assertTrue(rec["cmd"].startswith("py scripts/x.py"))
        self.assertNotIn("second line", rec["cmd"])
        self.assertNotIn("abc123secret", json.dumps(rec))

    def test_file_tools_record_cwd_and_path(self):
        ev = {"tool_name": "Read", "session_id": "S", "cwd": "/w/BilliardIllumination",
              "tool_input": {"file_path": "/w/board"},
              "error": "EISDIR: illegal operation on a directory, read"}
        rec = el.hook_record(ev, "author@bi", NOW)
        self.assertEqual((rec["cwd"], rec["path"]), ("/w/BilliardIllumination", "/w/board"))
        ev = {"tool_name": "Glob", "cwd": "/w/library",
              "tool_input": {"pattern": "**/*.tex", "path": "/w/library/Mo06.src"},
              "error": "Directory does not exist"}
        rec = el.hook_record(ev, "expert@ts", NOW)
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


if __name__ == "__main__":
    unittest.main()
