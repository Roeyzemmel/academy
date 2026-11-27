"""prove_inputs.py (#126, points 2 and 4): the scoped falsifier waiver and the inputs plan."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _fixtures  # noqa: E402,F401  (puts the plugin's scripts on sys.path)
import prove_inputs as pi  # noqa: E402

LINE = "- 2026-11-19 human: none of the flat-structure falsifiers for now"


class WaiverTests(unittest.TestCase):
    def test_a_plan_line_of_the_human_waives(self):
        for words in ("none of the flat-structure falsifiers for now", "no falsifiers here",
                      "falsifiers waived", "skip the falsifiers"):
            self.assertTrue(pi.plan_waiver("# plan\n- 2026-11-19 human: %s\n" % words), words)

    def test_only_the_humans_dated_line_counts(self):
        for text in ("no falsifiers", "- 2026-11-19 main: no falsifiers",
                     "- 2026-11-19 human (via main session): no falsifiers",
                     "- human: no falsifiers", "- 2026-11-19 human: run more experiments"):
            self.assertEqual(pi.plan_waiver(text), "", text)

    def test_a_later_line_lifts_it(self):
        text = LINE + "\n- 2026-11-25 human: run the falsifiers again\n"
        self.assertEqual(pi.plan_waiver(text), "")
        self.assertEqual(pi.plan_waiver(text + "- 2026-11-26 human: no falsifiers after all\n"),
                         "- 2026-11-26 human: no falsifiers after all")

    def test_config_scope_by_id_or_prefix(self):
        cfg = {"researcher": {"falsifierWaivers": [
            {"scope": "flat:FND-", "line": LINE}, {"scope": "GEO-7", "line": LINE},
            {"scope": "flat:", "line": "no falsifiers"}]}}
        self.assertEqual(pi.config_waiver(cfg, "flat:FND-38"), ("flat:FND-", LINE))
        self.assertEqual(pi.config_waiver(cfg, "flat:GEO-7"), ("GEO-7", LINE))
        self.assertEqual(pi.config_waiver(cfg, "flat:GEO-70"), ("", ""))   # not a prefix scope
        self.assertEqual(pi.config_waiver(cfg, "flat:PER-2"), ("", ""))    # an entry without the line
        self.assertEqual(pi.config_waiver({}, "flat:FND-38"), ("", ""))

    def test_waiver_reads_the_tickets_cowork_plan_and_the_home(self):
        with tempfile.TemporaryDirectory() as d:
            board, home = os.path.join(d, "board"), os.path.join(d, "home")
            os.makedirs(os.path.join(board, "cowork"))
            os.makedirs(os.path.join(home, ".claude"))
            with open(os.path.join(board, "cowork", "2026-11-19-flat-structures.md"), "w") as fh:
                fh.write("# flat-structures\n" + LINE + "\n")
            r = pi.waiver("flat:FND-38", {"cowork": "flat-structures"}, None, home, board)
            self.assertEqual((r["waived"], r["source"], r["scope"], r["line"]),
                             (True, "cowork", "flat-structures", LINE))
            self.assertFalse(pi.waiver("flat:FND-38", {}, None, home, board)["waived"])
            self.assertFalse(pi.waiver("flat:FND-38", {"cowork": "other"}, None, home, board)["waived"])
            with open(os.path.join(home, ".claude", "academy.json"), "w") as fh:
                json.dump({"researcher": {"falsifierWaivers": [{"scope": "flat:FND-", "line": LINE}]}}, fh)
            r = pi.waiver("flat:FND-38", {}, None, home, board)
            self.assertEqual((r["waived"], r["source"]), (True, "config"))


class InputsTests(unittest.TestCase):
    INSTANCES = {"expert@t": {"role": "expert"}, "researcher@flat": {"role": "researcher", "ns": "flat"},
                 "author@t": {"role": "author", "ns": "paper"}}

    def plan(self, ids, statuses, metas=()):
        return pi.plan_inputs("flat:FND-38", ids, list(metas), statuses.get, self.INSTANCES)

    def test_each_action(self):
        statuses = {"flat:FND-1": "proved", "flat:FND-2": "sketch", "flat:FND-3": "open",
                    "flat:FND-4": "sketch", "paper:lem:x": "open"}
        metas = [{"id": "T-0007", "kind": "verify", "status": "blocked", "refs": ["flat:FND-4"]},
                 {"id": "T-0008", "kind": "verify", "status": "delivered", "refs": ["flat:FND-2"]}]
        rows = {r["id"]: r for r in self.plan(
            ["flat:FND-1", "FND-2", "flat:FND-3", "flat:FND-4", "paper:lem:x", "flat:FND-38"],
            statuses, metas)}
        self.assertNotIn("flat:FND-38", rows)                         # the claim itself
        self.assertEqual(rows["flat:FND-1"]["action"], "none")
        self.assertEqual((rows["flat:FND-2"]["action"], rows["flat:FND-2"]["to"]), ("verify", "expert@t"))
        self.assertEqual((rows["flat:FND-3"]["action"], rows["flat:FND-3"]["to"]), ("prove", "researcher@flat"))
        self.assertEqual((rows["flat:FND-4"]["action"], rows["flat:FND-4"]["ticket"]), ("link", "T-0007"))
        self.assertEqual(rows["paper:lem:x"]["action"], "none")       # no Researcher owns paper:
        self.assertIn("namespace 'paper'", rows["paper:lem:x"]["why"])

    def test_an_unreadable_registry_reads_as_unknown(self):
        def boom(_q):
            raise RuntimeError("no registry")
        rows = pi.plan_inputs("flat:FND-38", ["flat:FND-3"], [], boom, self.INSTANCES)
        self.assertEqual((rows[0]["status"], rows[0]["action"]), ("unknown", "prove"))


if __name__ == "__main__":
    unittest.main()
