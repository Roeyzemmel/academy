"""ship.py, final fix wave: the gate's 'unavailable' mode (I2), --no-registry on every gate
run (I3, unit level; the end-to-end run with the real checker is test_ship_gate_e2e.py),
the merge summary's "gate inputs changed" line (I4), --repo must be a checkout of the
same repository (M2) and start --worktree (M3). Temp repos only."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import ship  # noqa: E402
from ship_fixture import run  # noqa: E402
from test_ship import Base, GateEnv, MergeBase  # noqa: E402  (no test methods of their own)


# ----------------------------------------------------------------------------
# I2: mode 'unavailable'
# ----------------------------------------------------------------------------

class TestGateUnavailable(GateEnv):
    def setUp(self):
        super().setUp()
        self.author_home()
        self.name = self.on_branch()
        self.env("STUB_MODE", "unavailable")
        self.env("STUB_CAUSE", "PARSE ERROR: unbalanced brace group at offset 7")

    def test_commit_continues_and_shows_the_cause(self):
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)
        self.assertIn("ship: gate unavailable: PARSE ERROR: unbalanced brace group at offset 7", err)
        self.assertEqual(self.count(), 2)

    def test_ship_continues_and_pushes(self):
        self.write("b.txt")
        rc, _, err = self.ship("ship", "sub", "-m", "m", "--paths", "b.txt")
        self.assertEqual(rc, 0, err)
        self.assertIn("ship: gate unavailable: PARSE ERROR", err)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + self.name),
                         run(self.sub, "rev-parse", "HEAD"))

    def test_old_academy_without_detail_falls_back_to_gate_check(self):
        self.env("STUB_NO_DETAIL", "1")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)
        self.assertIn("ship: gate unavailable: academy checkout predates gate_check_detail", err)
        self.assertEqual(len(self.calls()), 1)

    def test_old_academy_fallback_still_blocks_findings(self):
        self.env("STUB_NO_DETAIL", "1")
        self.env("STUB_MODE", "")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("missing label foo", err)

    def test_academy_without_gate_check_is_refused_clearly(self):
        self.env("STUB_NO_DETAIL", "1")
        self.env("STUB_NO_CHECK", "1")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("academy checkout predates gate_check: update the academy submodule", err)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("AttributeError", err)
        self.assertEqual(self.count(), 1)

    def test_malformed_cause_refused(self):
        gate = os.path.join(self.gate_dir, "commit_gate.py")
        with open(gate, "a", encoding="utf-8") as f:
            f.write("\ndef gate_check_detail(home, cfg, branch):\n"
                    "    return 'unavailable', {}, 42\n")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("malformed", err)

    def test_unknown_mode_still_fails_closed(self):
        self.env("STUB_MODE", "bogus")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("unknown gate mode bogus", err)


class TestMergeUnavailable(MergeBase):
    def test_merge_refuses_unavailable_and_shows_the_cause(self):
        self.author_home()
        self.env("STUB_MODE", "unavailable")
        self.env("STUB_CAUSE", "PARSE ERROR: unbalanced brace group at offset 7")
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("unavailable", err)
        self.assertIn("PARSE ERROR: unbalanced brace group at offset 7", err)
        self.assert_untouched()


# ----------------------------------------------------------------------------
# I3: every gate run passes --no-registry (the tracked Drafts/statements.md stays put)
# ----------------------------------------------------------------------------

class TestNoRegistry(GateEnv):
    def home_with_args(self, args):
        os.makedirs(os.path.join(self.sub, ".claude"), exist_ok=True)
        self.cfg_path = os.path.join(self.sub, ".claude", "academy.json")
        cfg = {"role": "author", "gate": {"commit": "normal"},
               "author": {"checker": {"args": args, "statements": "Drafts/statements.md"}}}
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        with open(self.cfg_path, encoding="utf-8") as f:
            self.cfg_text = f.read()

    def test_gate_run_appends_no_registry_keeping_args(self):
        self.home_with_args(["--no-log"])
        self.on_branch()
        ship.run_gate(self.sub)
        self.assertEqual(self.calls()[-1]["cfg"]["author"]["checker"]["args"], ["--no-log", "--no-registry"])
        ship.run_gate(self.sub, strict=True)
        cfg = self.calls()[-1]["cfg"]
        self.assertEqual(cfg["author"]["checker"]["args"], ["--no-log", "--no-registry"])
        self.assertEqual(cfg["gate"]["commit"], "strict")
        with open(self.cfg_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), self.cfg_text)  # only the in-memory copy changes

    def test_no_duplicate_and_no_author_block(self):
        self.home_with_args(["--no-registry"])
        ship.run_gate(self.sub)
        self.assertEqual(self.calls()[-1]["cfg"]["author"]["checker"]["args"], ["--no-registry"])
        self.author_home()  # no "author" block at all
        ship.run_gate(self.sub)
        self.assertEqual(self.calls()[-1]["cfg"]["author"]["checker"]["args"], ["--no-registry"])


# ----------------------------------------------------------------------------
# I4: the merge summary names changed gate inputs
# ----------------------------------------------------------------------------

class TestGateInputsChanged(MergeBase):
    def branch_commit(self, files):
        run(self.sub, "switch", "-q", self.branch)
        for rel, text in files.items():
            path = os.path.join(self.sub, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            run(self.sub, "add", rel)
        run(self.sub, "commit", "-q", "-m", "touch gate inputs")
        run(self.sub, "push", "-q", "origin", self.branch)
        self.tip = run(self.sub, "rev-parse", "HEAD")

    def test_academy_json_and_configured_baseline(self):
        self.branch_commit({".claude/academy.json": json.dumps({"role": "expert", "gate": {"baseline": "gate/base.txt"}}),
                            "gate/base.txt": "k\n"})
        rc, out, err = self.merge()
        self.assertEqual(rc, 0, err)
        self.assertIn("gate inputs changed: .claude/academy.json, gate/base.txt", out)

    def test_default_baseline(self):
        self.branch_commit({".claude/paper-gate-baseline.txt": "k\n"})
        rc, out, err = self.merge()
        self.assertEqual(rc, 0, err)
        self.assertIn("gate inputs changed: .claude/paper-gate-baseline.txt", out)

    def test_quiet_when_untouched(self):
        rc, out, err = self.merge()
        self.assertEqual(rc, 0, err)
        self.assertNotIn("gate inputs changed", out + err)


# ----------------------------------------------------------------------------
# M2: --repo must be a checkout of <ROOT>/<sub>'s repository
# ----------------------------------------------------------------------------

class TestRepoFlag(Base):
    def test_superproject_as_repo_refused_on_every_verb(self):
        root_head = run(self.root, "symbolic-ref", "HEAD")
        for argv in (["start", "sub", "topic", "--role", "human"],
                     ["commit", "sub", "-m", "m", "--all"],
                     ["ship", "sub", "-m", "m", "--all"],
                     ["push", "sub"],
                     ["accept-baseline", "sub"],
                     ["merge", "sub", "2026-09-30/topic/human", "--sha", "0" * 40],
                     ["publish", "sub", "--sha", "0" * 40]):
            rc, _, err = self.ship(*(argv + ["--repo", self.root]))
            self.assertEqual(rc, 1, argv)
            self.assertIn("--repo", err, argv)
            self.assertIn("not a checkout of", err, argv)
        self.assertEqual(run(self.root, "symbolic-ref", "HEAD"), root_head)
        self.assertEqual(run(self.root, "branch", "--list"), "")

    def test_other_clone_refused(self):
        clone = os.path.join(self._tmp.name, "clone")
        run(self._tmp.name, "clone", "-q", self.remote, clone)
        rc, _, err = self.ship("start", "sub", "topic", "--role", "human", "--repo", clone)
        self.assertEqual(rc, 1)
        self.assertIn("not a checkout of", err)
        self.assertEqual(run(clone, "branch", "--show-current"), "main")

    def test_worktree_of_the_submodule_accepted(self):
        wt = os.path.join(self._tmp.name, "wt")
        run(self.sub, "worktree", "add", "-q", "-b", "scratch", wt)
        rc, _, err = self.ship("start", "sub", "topic", "--role", "human", "--repo", wt)
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(wt), ship.branch_name("topic", "human"))
        self.assertEqual(ship.current(self.sub), "main")

    def test_the_checkout_itself_accepted(self):
        rc, _, err = self.ship("start", "sub", "topic", "--role", "human", "--repo", self.sub)
        self.assertEqual(rc, 0, err)


# ----------------------------------------------------------------------------
# M3: start --worktree
# ----------------------------------------------------------------------------

class TestStartWorktree(Base):
    def test_start_worktree_creates_removable_checkout_on_branch(self):
        rc, out, err = self.ship("start", "sub", "topic", "--role", "human", "--worktree")
        self.assertEqual(rc, 0, err)
        name = ship.branch_name("topic", "human")
        wt = os.path.join(self.sub, ".claude", "worktrees", name.replace("/", "-"))
        self.assertTrue(os.path.isdir(wt))
        self.assertIn(wt, out)
        self.assertEqual(ship.current(wt), name)
        self.assertEqual(ship.current(self.sub), "main")
        # a second start --worktree for the same branch reuses it? no: the branch exists and
        # is checked out there, so git refuses a second worktree -- a clean refusal
        rc, _, err = self.ship("start", "sub", "topic", "--role", "human", "--worktree")
        self.assertEqual(rc, 1)
        run(self.sub, "worktree", "remove", wt)
        self.assertFalse(os.path.exists(wt))
        self.assertTrue(run(self.sub, "rev-parse", "--verify", "refs/heads/" + name))


if __name__ == "__main__":
    unittest.main()
