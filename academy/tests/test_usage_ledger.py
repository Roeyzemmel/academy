"""usage_ledger: content-free session summaries on the board (U5). Temp dirs only."""
import datetime as _dt
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
import usage_ledger  # noqa: E402
import usage_report  # noqa: E402

SECRET = "sk-SECRETSECRETSECRET1234"
PATH = "/home/someone/hidden/thesis/draft.tex"


def assistant(mid, model, read, write_):
    return json.dumps({"type": "assistant", "message": {
        "id": mid, "model": model, "content": [{"type": "text", "text": "reply " + SECRET}],
        "usage": {"cache_read_input_tokens": read, "cache_creation_input_tokens": write_,
                  "input_tokens": 0}}})


def user(text):
    return json.dumps({"type": "user", "cwd": "/home/someone/hidden", "message": {"role": "user", "content": text}})


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class LedgerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="usage-ledger-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "ws", "PaperHome")
        os.makedirs(self.home)
        self.ws = {"instances": {"author@p": {"role": "author", "home": self.home}},
                   "_path": os.path.join(self.tmp, "ws", "workspace.json")}
        self.projects = os.path.join(self.tmp, "projects")
        self.board = os.path.join(self.tmp, "board")
        os.makedirs(self.board)
        self.since = _dt.datetime.now() - _dt.timedelta(days=7)

    def transcript(self, name="s1", n=2, extra_text=""):
        base = os.path.join(self.projects, usage_report.encode_home(self.home))
        lines = [user("please fix %s using token %s %s" % (PATH, SECRET, extra_text))]
        lines += [assistant("m%d" % i, "claude-opus-5-5", 1000 * (i + 1), 100) for i in range(n)]
        put(os.path.join(base, name + ".jsonl"), "\n".join(lines) + "\n")
        sub = os.path.join(base, name, "subagents")
        put(os.path.join(sub, "a.meta.json"), json.dumps(
            {"agentType": "academy:concierge", "spawnDepth": 1, "description": "TOP SECRET " + PATH}))
        put(os.path.join(sub, "a.jsonl"), assistant("x", "claude-haiku-4-5", 50, 5) + "\n")
        return base


class TestSummaries(LedgerBase):
    def test_summary_shape_and_numbers(self):
        self.transcript()
        recs = usage_ledger.summarise_sessions(self.projects, self.since, self.ws, host="h")
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(sorted(r), sorted(usage_ledger.FIELDS))
        self.assertEqual((r["t"], r["session"], r["instance"], r["host"]), ("usage", "s1", "author@p", "h"))
        self.assertEqual((r["turns"], r["read"], r["write"]), (3, 1000 + 2000 + 50, 205))
        self.assertEqual(r["models"], {"opus": 2, "haiku": 1})
        self.assertEqual(r["subagents"], {"academy:concierge": 1})
        self.assertRegex(r["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertRegex(usage_ledger.host_hash(), r"^[0-9a-f]{8}$")

    def test_nothing_from_the_transcript_leaks(self):
        self.transcript()
        text = json.dumps(usage_ledger.summarise_sessions(self.projects, self.since, self.ws))
        for leak in (SECRET, "SECRET", PATH, "hidden", "thesis", "draft.tex", "TOP SECRET", "please fix"):
            self.assertNotIn(leak, text)
        # and what is written to the board
        usage_ledger.write_summaries(self.board, self.projects, self.since, self.ws)
        with open(usage_ledger.ledger_file(self.board, "author@p", usage_ledger.host_hash()), encoding="utf-8") as fh:
            disk = fh.read()
        for leak in (SECRET, PATH, "hidden", "TOP SECRET", "please fix"):
            self.assertNotIn(leak, disk)

    def test_append_drops_extra_fields_a_caller_passes(self):
        rec = {"t": "usage", "session": "s9", "turns": 1, "read": 2, "prompt": SECRET, "cwd": PATH}
        self.assertEqual(usage_ledger.append(self.board, "i", [rec]), 1)
        with open(usage_ledger.ledger_file(self.board, "i"), encoding="utf-8") as fh:
            disk = fh.read()
        self.assertNotIn(SECRET, disk)
        self.assertNotIn(PATH, disk)

    def test_other_bucket_is_never_written(self):
        base = os.path.join(self.projects, "C--elsewhere")
        put(os.path.join(base, "o1.jsonl"), assistant("m", "claude-opus-5-5", 5, 0) + "\n")
        self.assertEqual(usage_ledger.write_summaries(self.board, self.projects, self.since, self.ws), 0)
        self.assertFalse(os.path.exists(os.path.join(self.board, ".usage")))

    def test_old_sessions_are_out_of_the_window(self):
        base = self.transcript()
        old = os.path.join(base, "s1.jsonl")
        t = time.time() - 30 * 86400
        os.utime(old, (t, t))
        self.assertEqual(usage_ledger.summarise_sessions(self.projects, self.since, self.ws), [])


class TestAppendRead(LedgerBase):
    def rec(self, sid, turns, read, ts="2026-10-17T10:00:00Z"):
        return {"t": "usage", "session": sid, "ts": ts, "instance": "author@p", "turns": turns,
                "read": read, "write": 0, "limit_failures": 0, "models": {}, "subagents": {}, "host": "h"}

    def lines(self):
        with open(usage_ledger.ledger_file(self.board, "author@p", "h"), encoding="utf-8") as fh:
            return fh.read().splitlines()

    def test_upsert_without_rewriting_history(self):
        self.assertEqual(usage_ledger.append(self.board, "author@p", [self.rec("a", 1, 10)]), 1)
        self.assertEqual(usage_ledger.append(self.board, "author@p", [self.rec("a", 1, 10)]), 0)  # unchanged
        first = self.lines()[0]
        self.assertEqual(usage_ledger.append(self.board, "author@p",
                                             [self.rec("a", 3, 90, "2026-10-17T11:00:00Z"), self.rec("b", 1, 5)]), 2)
        self.assertEqual(self.lines()[0], first)           # history untouched
        self.assertEqual(len(self.lines()), 3)
        got = usage_ledger.read_all(self.board)
        self.assertEqual((got["a"]["turns"], got["b"]["turns"]), (3, 1))   # last record wins
        # an older state re-offered after a newer one is a change too, but equal state is not
        self.assertEqual(usage_ledger.append(self.board, "author@p", [self.rec("a", 3, 90)]), 0)

    def test_missing_board_and_readonly_never_raise(self):
        self.assertEqual(usage_ledger.append(os.path.join(self.tmp, "nope"), "i", [self.rec("a", 1, 1)]), 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "nope")))
        self.assertEqual(usage_ledger.append(None, "i", [self.rec("a", 1, 1)]), 0)
        # a path where .usage cannot be a directory
        with open(os.path.join(self.board, ".usage"), "w") as fh:
            fh.write("file")
        self.assertEqual(usage_ledger.append(self.board, "i", [self.rec("a", 1, 1)]), 0)
        self.assertEqual(usage_ledger.read_all(self.board), {})
        self.assertEqual(usage_ledger.read_all(os.path.join(self.tmp, "nope")), {})

    def test_bad_lines_are_skipped_and_latest_ts_wins_across_files(self):
        put(os.path.join(self.board, ".usage", "x.jsonl"),
            "garbage\n" + json.dumps(self.rec("a", 1, 1, "2026-10-17T09:00:00Z")) + "\n")
        put(os.path.join(self.board, ".usage", "y.jsonl"),
            json.dumps(self.rec("a", 7, 7, "2026-10-17T12:00:00Z")) + "\n")
        self.assertEqual(usage_ledger.read_all(self.board)["a"]["turns"], 7)

    def test_checkpoint_hook_never_raises(self):
        written, warning = usage_ledger.checkpoint(self.tmp, self.board, os.path.join(self.tmp, "no-projects"))
        self.assertEqual((written, warning), (0, ""))
        with unittest.mock.patch.object(usage_ledger, "write_summaries", side_effect=RuntimeError("boom")):
            os.makedirs(self.projects)
            written, warning = usage_ledger.checkpoint(self.tmp, self.board, self.projects)
        self.assertEqual(written, 0)
        self.assertIn("boom", warning)


class TestCompact(LedgerBase):
    NOW = _dt.datetime(2026, 10, 17, 12, 0, 0)

    def ts(self, days_ago):
        t = self.NOW - _dt.timedelta(days=days_ago)
        return _dt.datetime.fromtimestamp(t.timestamp(), _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def rec(self, sid, turns=1, days_ago=1, ts=None):
        return {"t": "usage", "session": sid, "ts": ts or self.ts(days_ago), "instance": "i", "turns": turns,
                "read": turns * 10, "write": 0, "limit_failures": 0, "models": {}, "subagents": {}, "host": "h"}

    def make(self, recs, host="h", extra=""):
        path = usage_ledger.ledger_file(self.board, "i", host)
        put(path, extra + "".join(json.dumps(r, sort_keys=True) + "\n" for r in recs))
        return path

    def sessions(self, path):
        with open(path, encoding="utf-8") as fh:
            return [(json.loads(l)["session"], json.loads(l)["turns"]) for l in fh if l.strip()]

    def test_last_wins_and_order_follows_last_record(self):
        path = self.make([self.rec("a", 1), self.rec("b", 1), self.rec("a", 2), self.rec("c", 1), self.rec("b", 3)])
        self.assertEqual(usage_ledger.compact(path, now=self.NOW, host="h"), 2)
        self.assertEqual(self.sessions(path), [("a", 2), ("c", 1), ("b", 3)])

    def test_old_sessions_dropped_recent_kept_unparseable_kept(self):
        path = self.make([self.rec("old", days_ago=120), self.rec("new", days_ago=5),
                          self.rec("odd", ts="not-a-time"), self.rec("old2", days_ago=91)])
        self.assertEqual(usage_ledger.compact(path, keep_days=90, now=self.NOW, host="h"), 2)
        self.assertEqual([s for s, _ in self.sessions(path)], ["new", "odd"])
        # a session whose LAST record is recent survives even if an earlier one was old
        path = self.make([self.rec("a", 1, days_ago=200), self.rec("a", 2, days_ago=1)])
        self.assertEqual(usage_ledger.compact(path, now=self.NOW, host="h"), 1)
        self.assertEqual(self.sessions(path), [("a", 2)])

    def test_nothing_to_remove_leaves_file_untouched(self):
        path = self.make([self.rec("a"), self.rec("b")])
        os.utime(path, (1000000000, 1000000000))
        before = open(path, "rb").read()
        self.assertEqual(usage_ledger.compact(path, now=self.NOW, host="h"), 0)
        self.assertEqual(open(path, "rb").read(), before)
        self.assertEqual(os.stat(path).st_mtime, 1000000000)
        self.assertEqual(os.listdir(os.path.dirname(path)), [os.path.basename(path)])

    def test_other_hosts_file_is_never_rewritten(self):
        path = self.make([self.rec("a", 1), self.rec("a", 2)], host="zzzzzzzz")
        before = open(path, "rb").read()
        self.assertEqual(usage_ledger.compact(path, now=self.NOW, host="h"), 0)
        self.assertEqual(open(path, "rb").read(), before)

    def test_garbage_only_file_untouched_garbage_dropped_otherwise(self):
        path = usage_ledger.ledger_file(self.board, "i", "h")
        put(path, "junk\n{not json\n[1]\n")
        self.assertEqual(usage_ledger.compact(path, now=self.NOW, host="h"), 0)
        self.assertEqual(open(path).read(), "junk\n{not json\n[1]\n")
        path = self.make([self.rec("a")], extra="junk\n")
        self.assertEqual(usage_ledger.compact(path, now=self.NOW, host="h"), 1)
        self.assertEqual(self.sessions(path), [("a", 1)])

    def test_missing_file_and_unwritable_never_raise(self):
        self.assertEqual(usage_ledger.compact(os.path.join(self.board, "nope.h.jsonl"), host="h"), 0)
        path = self.make([self.rec("a", 1), self.rec("a", 2)])
        with unittest.mock.patch.object(usage_ledger.os, "replace", side_effect=OSError("ro")):
            self.assertEqual(usage_ledger.compact(path, now=self.NOW, host="h"), 0)
        self.assertEqual(len(self.sessions(path)), 2)
        self.assertEqual(os.listdir(os.path.dirname(path)), [os.path.basename(path)])  # temp cleaned

    def test_read_all_same_before_and_after(self):
        path = self.make([self.rec("a", 1), self.rec("b", 4), self.rec("a", 2), self.rec("b", 5)])
        before = usage_ledger.read_all(self.board)
        usage_ledger.compact(path, now=self.NOW, host="h")
        self.assertEqual(usage_ledger.read_all(self.board), before)

    def test_checkpoint_compacts_bloated_and_leaves_lean_alone(self):
        os.makedirs(self.projects)
        bloated = self.make([self.rec("a", 1), self.rec("a", 2), self.rec("b", 1), self.rec("b", 2)])
        lean_path = usage_ledger.ledger_file(self.board, "lean", "h")
        put(lean_path, json.dumps(self.rec("x")) + "\n" + json.dumps(self.rec("y")) + "\n")
        os.utime(lean_path, (1000000000, 1000000000))
        other = self.make([self.rec("a", 1), self.rec("a", 2)], host="zzzzzzzz")
        other_bytes = open(other, "rb").read()
        self.assertEqual(usage_ledger.checkpoint(self.tmp, self.board, self.projects, now=self.NOW, host="h"), (0, ""))
        self.assertEqual(self.sessions(bloated), [("a", 2), ("b", 2)])
        self.assertEqual(os.stat(lean_path).st_mtime, 1000000000)
        self.assertEqual(open(other, "rb").read(), other_bytes)

    def test_checkpoint_stale_trigger_and_keep_days_override(self):
        os.makedirs(self.projects)
        path = self.make([self.rec("a", days_ago=40), self.rec("b", days_ago=1)])
        usage_ledger.checkpoint(self.tmp, self.board, self.projects, now=self.NOW, host="h")
        self.assertEqual(len(self.sessions(path)), 2)                      # 90 days: nothing old
        usage_ledger.checkpoint(self.tmp, self.board, self.projects, now=self.NOW, host="h", keep_days=30)
        self.assertEqual([s for s, _ in self.sessions(path)], ["b"])
        for bad in ("30", 3, True, 6, None, 2.5):
            path = self.make([self.rec("a", days_ago=40), self.rec("b", days_ago=1)])
            usage_ledger.checkpoint(self.tmp, self.board, self.projects, now=self.NOW, host="h", keep_days=bad)
            self.assertEqual(len(self.sessions(path)), 2, bad)             # fell back to 90

    def test_cli_compact_prints_lines_removed(self):
        import io
        import contextlib
        host = usage_ledger.host_hash()
        path = self.make([self.rec("a", 1), self.rec("a", 2)], host=host)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = usage_ledger.main(["compact", "--board", self.board])
        self.assertEqual(rc, 0)
        self.assertIn("1 line(s) removed", buf.getvalue())
        self.assertEqual(self.sessions(path), [("a", 2)])


if __name__ == "__main__":
    unittest.main()
