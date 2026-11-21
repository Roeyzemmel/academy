"""``ship.py merge`` and ``publish`` warn when a workflow run is live on the repo (#97).

A run reads its code from a pin (``run_pin.py``: ``.worktrees/run-<sha12>``), so a merge
no longer changes the scripts it calls; what still comes from the checkout (the agent
definitions, hooks and skills of a plugin loaded from it) does change, so the human is
told, and nothing is refused. A stale marker (too old, or its process gone) says nothing.
``status`` never counts a pin as work in a worktree; ``--all`` shows it as a run pin.
"""
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import run_pin  # noqa: E402
from ship_fixture import run  # noqa: E402
from test_ship import Base, MergeBase  # noqa: E402  (no test methods of their own)


class TestMergeWarnsOnALiveRun(MergeBase):
    def test_a_live_run_is_named_and_the_merge_goes_on(self):
        r = run_pin.start(self.sub, "inbox-all")
        rc, out, err = self.merge()
        self.assertEqual(0, rc, err)
        self.assertIn("1 workflow run is live", err)
        self.assertIn(r["run"], err)
        self.assertIn(r["sha"][:12], err)
        self.assertIn("run_pin.py end --run", err)
        self.assertEqual([self.main_before, self.tip],
                         run(self.sub, "log", "-1", "--format=%P", "main").split())

    def test_a_stale_run_says_nothing(self):
        run_pin.start(self.sub, "inbox-all", now=time.time() - (run_pin.RUN_MAX_HOURS + 1) * 3600)
        rc, _, err = self.merge()
        self.assertEqual(0, rc, err)
        self.assertNotIn("workflow run", err)

    def test_no_run_says_nothing(self):
        rc, _, err = self.merge()
        self.assertEqual(0, rc, err)
        self.assertNotIn("workflow run", err)

    def test_an_unreadable_marker_never_fails_the_merge(self):
        d = os.path.join(self.sub, ".worktrees", "live")
        os.makedirs(d)
        with open(os.path.join(d, "x.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        rc, _, err = self.merge()
        self.assertEqual(0, rc, err)

    def test_publish_warns_too(self):
        self.assertEqual(0, self.merge()[0])
        head = run(self.sub, "rev-parse", "main")
        r = run_pin.start(self.sub, "workplan-cowork")
        rc, _, err = self.ship("publish", "sub", "--sha", head)
        self.assertEqual(0, rc, err)
        self.assertIn(r["run"], err)
        self.assertEqual(head, run(self.remote, "rev-parse", "main"))


class TestStatusSkipsPins(Base):
    def status(self, *extra):
        rc, out, err = self.ship("status", *extra)
        self.assertEqual(0, rc, err)
        return out

    def test_a_pin_at_an_unpushed_commit_is_no_work(self):
        with open(os.path.join(self.sub, "b.txt"), "w", encoding="utf-8") as fh:
            fh.write("b\n")
        run(self.sub, "add", "b.txt")
        run(self.sub, "commit", "-q", "-m", "local only")          # a merge not yet published
        r = run_pin.start(self.sub, "inbox-all")
        name = os.path.basename(r["root"])
        self.assertNotIn(name, self.status())
        shown = [ln for ln in self.status("--all").splitlines() if name in ln]
        self.assertEqual(1, len(shown), shown)
        self.assertIn("run pin", shown[0])
        self.assertNotIn("removable", shown[0])


if __name__ == "__main__":
    unittest.main()
