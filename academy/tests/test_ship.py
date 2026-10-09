import argparse
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import ship  # noqa: E402
from ship_fixture import STUB_GATE, make_workspace, run  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root, self.sub, self.remote = make_workspace(self._tmp.name)
        old = ship.ROOT
        ship.ROOT = self.root
        self.addCleanup(setattr, ship, "ROOT", old)

    def ship(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ship.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def write(self, name, text="x\n"):
        with open(os.path.join(self.sub, name), "w", encoding="utf-8") as f:
            f.write(text)

    def on_branch(self):
        self.assertEqual(self.ship("start", "sub", "topic", "--role", "human")[0], 0)
        return ship.current(self.sub)


class TestNames(unittest.TestCase):
    def test_branch_name_slugs_topic(self):
        self.assertEqual(ship.branch_name("Coimage Proof!", "human", today="2026-09-30"),
                         "2026-09-30/coimage-proof/human")

    def test_empty_topic_refused(self):
        with self.assertRaises(ship.Refuse):
            ship.branch_name("!!!", "human", today="2026-09-30")

    def test_bad_role_refused(self):
        with self.assertRaises(ship.Refuse):
            ship.branch_name("x", "wizard", today="2026-09-30")

    def test_role_from_academy_json(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ship.default_role(d), "human")
            os.makedirs(os.path.join(d, ".claude"))
            with open(os.path.join(d, ".claude", "academy.json"), "w") as f:
                json.dump({"role": "expert"}, f)
            self.assertEqual(ship.default_role(d), "expert")


class TestShip(Base):
    def test_commit_refused_on_main(self):
        self.write("b.txt")
        rc, _, err = self.ship("commit", "sub", "-m", "m", "--all")
        self.assertEqual(rc, 1)
        self.assertIn("ship: refused", err)
        self.assertEqual(run(self.sub, "rev-list", "--count", "HEAD"), "1")

    def test_commit_refused_off_template(self):
        run(self.sub, "switch", "-q", "-c", "feature-x")
        self.write("b.txt")
        rc, _, err = self.ship("commit", "sub", "-m", "m", "--all")
        self.assertEqual(rc, 1)
        self.assertIn("ship: refused", err)

    def test_commit_needs_paths_or_all(self):
        self.on_branch()
        self.write("b.txt")
        self.assertEqual(self.ship("commit", "sub", "-m", "m")[0], 1)
        self.assertEqual(self.ship("commit", "sub", "-m", "m", "--all", "--paths", "b.txt")[0], 1)

    def test_paths_outside_repo_refused(self):
        self.on_branch()
        outside = os.path.join(self._tmp.name, "outside.txt")
        with open(outside, "w") as f:
            f.write("o\n")
        for p in (outside, "../outside.txt"):
            rc, _, err = self.ship("commit", "sub", "-m", "m", "--paths", p)
            self.assertEqual(rc, 1, p)
            self.assertIn("outside", err)

    def test_empty_commit_refused(self):
        self.on_branch()
        rc, _, err = self.ship("commit", "sub", "-m", "m", "--all")
        self.assertEqual(rc, 1)
        self.assertIn("nothing", err)

    def test_commit_paths_stages_only_named_no_trailer(self):
        self.on_branch()
        self.write("b.txt")
        self.write("c.txt")
        msg = "do it\n\nCo-Authored-By: X <x@y>"
        self.assertEqual(self.ship("commit", "sub", "-m", msg, "--paths", "b.txt")[0], 0)
        self.assertEqual(run(self.sub, "show", "--name-only", "--format=", "HEAD"), "b.txt")
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B"), msg)

    def test_ship_pushes_same_named_branch_not_main(self):
        main_before = run(self.remote, "rev-parse", "main")
        name = self.on_branch()
        self.write("b.txt")
        rc, _, err = self.ship("ship", "sub", "-m", "m", "--paths", "b.txt")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name), run(self.sub, "rev-parse", "HEAD"))
        self.assertEqual(run(self.remote, "rev-parse", "main"), main_before)

    def test_push_refused_on_main(self):
        self.assertEqual(self.ship("push", "sub")[0], 1)

    def test_start_reuses_existing_branch(self):
        name = self.on_branch()
        run(self.sub, "switch", "-q", "main")
        rc, _, err = self.ship("start", "sub", "topic", "--role", "human")
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.sub), name)

    def test_detached_head_refused(self):
        run(self.sub, "checkout", "-q", "--detach")
        self.write("b.txt")
        rc, _, err = self.ship("commit", "sub", "-m", "m", "--all")
        self.assertEqual(rc, 1)
        self.assertIn("detached", err)

    def test_missing_checkout_refused(self):
        rc, _, err = self.ship("commit", "nope", "-m", "m", "--all")
        self.assertEqual(rc, 1)
        self.assertIn("not a checked-out repo", err)

    def test_status_flags(self):
        rc, out, _ = self.ship("status")
        self.assertEqual(rc, 0)
        self.assertIn("PROTECTED", out)
        run(self.sub, "switch", "-q", "-c", "feature-x")
        self.assertIn("off-template", self.ship("status")[1])
        run(self.sub, "switch", "-q", "main")
        self.on_branch()
        self.assertIn("[ok]", self.ship("status")[1])


class GateEnv(Base):
    def setUp(self):
        super().setUp()
        self.gate_setup()

    def gate_setup(self):
        self.gate_dir = os.path.join(self._tmp.name, "gate")
        os.makedirs(self.gate_dir, exist_ok=True)
        with open(os.path.join(self.gate_dir, "commit_gate.py"), "w", encoding="utf-8") as f:
            f.write(STUB_GATE)
        self.log = os.path.join(self._tmp.name, "gate.log")
        self.env("SHIP_GATE_DIR", self.gate_dir)
        self.env("STUB_LOG", self.log)
        self.env("STUB_MODE", "")  # empty: the mode follows the cfg's gate.commit, as the real gate
        self.env("STUB_FINDINGS", "{}")
        self.env("STUB_RAISE", "")
        for k in ("STUB_CAUSE", "STUB_NO_DETAIL", "STUB_NO_CHECK"):
            self.env(k, "")

    def env(self, k, v):
        old = os.environ.get(k)
        os.environ[k] = v
        self.addCleanup(lambda: os.environ.pop(k, None) if old is None else os.environ.__setitem__(k, old))

    def author_home(self):
        os.makedirs(os.path.join(self.sub, ".claude"), exist_ok=True)
        with open(os.path.join(self.sub, ".claude", "academy.json"), "w", encoding="utf-8") as f:
            json.dump({"role": "author", "gate": {"commit": "normal", "branches": {"x": "warn"}}}, f)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def commit_b(self, *extra):
        self.write("b.txt")
        return self.ship("commit", "sub", "-m", "m", "--paths", "b.txt", *extra)

    def count(self):
        return int(run(self.sub, "rev-list", "--count", "HEAD"))


class TestGate(GateEnv):
    def test_commit_runs_gate_in_author_home(self):
        self.author_home()
        name = self.on_branch()
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(os.path.realpath(calls[0]["home"]), os.path.realpath(self.sub))
        self.assertEqual(calls[0]["branch"], name)

    def test_warn_mode_commits_and_prints_findings(self):
        self.author_home()
        self.on_branch()
        self.env("STUB_MODE", "warn")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)
        self.assertIn("ship: gate warning:", err)
        self.assertIn("missing label foo", err)
        self.assertEqual(self.count(), 2)

    def test_normal_mode_blocks_commit(self):
        self.author_home()
        self.on_branch()
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("ship: refused", err)
        self.assertIn("missing label foo", err)
        self.assertEqual(self.count(), 1)

    def test_off_mode_commits(self):
        self.author_home()
        self.on_branch()
        self.env("STUB_MODE", "off")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.count(), 2)

    def test_non_author_home_skips_gate(self):
        self.on_branch()
        self.env("STUB_FINDINGS", json.dumps({"k1": "x"}))
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.calls(), [])
        self.assertEqual(ship.run_gate(self.sub), ("skip", {}))

    def test_missing_gate_module_refused_in_author_home(self):
        self.author_home()
        self.on_branch()
        self.env("SHIP_GATE_DIR", os.path.join(self._tmp.name, "nowhere"))
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("gate", err)
        self.assertIn("missing", err)
        self.assertEqual(self.count(), 1)

    def test_unknown_gate_mode_fails_closed(self):
        self.author_home()
        self.on_branch()
        self.env("STUB_MODE", "bogus")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("unknown gate mode bogus", err)
        self.assertEqual(self.count(), 1)

    def test_gate_exception_refused(self):
        self.author_home()
        self.on_branch()
        self.env("STUB_RAISE", "1")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 1)
        self.assertIn("gate failed: stub gate exploded", err)
        self.assertEqual(self.count(), 1)

    def test_malformed_gate_findings_refused(self):
        self.author_home()
        self.on_branch()
        for bad in ('["a"]', '"text"', '{"k1": 1}', '[["k", "v"]]'):
            self.env("STUB_FINDINGS", bad)
            rc, _, err = self.commit_b()
            self.assertEqual(rc, 1, bad)
            self.assertIn("gate returned malformed findings", err, bad)
            self.assertNotIn("Traceback", err)
            self.assertEqual(self.count(), 1)

    def test_null_gate_findings_mean_none(self):
        self.author_home()
        self.on_branch()
        self.env("STUB_FINDINGS", "null")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)

    def test_git_env_never_prompts(self):
        with mock.patch.dict(os.environ):
            for k in ("GCM_INTERACTIVE", "GIT_TERMINAL_PROMPT"):
                os.environ.pop(k, None)  # the fixture sets them process-wide
            env = ship.git_env()
        self.assertEqual(env["GCM_INTERACTIVE"], "never")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")

    def test_gate_module_registered_in_sys_modules(self):
        mod = ship.load_gate()
        self.assertIs(sys.modules.get("commit_gate"), mod)

    def test_ship_verb_runs_gate(self):
        self.author_home()
        name = self.on_branch()
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        self.write("b.txt")
        rc, _, err = self.ship("ship", "sub", "-m", "m", "--paths", "b.txt")
        self.assertEqual(rc, 1)
        self.assertIn("missing label foo", err)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.count(), 1)
        self.assertEqual(run(self.remote, "branch", "--list", name), "")
        self.env("STUB_FINDINGS", "{}")
        rc, _, err = self.ship("ship", "sub", "-m", "m", "--paths", "b.txt")
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name), run(self.sub, "rev-parse", "HEAD"))

    def test_accept_baseline_shows_stderr(self):
        self.author_home()
        self.on_branch()
        rc, out, err = self.ship("accept-baseline", "sub")
        self.assertEqual(rc, 0, err)
        self.assertIn("baseline note on stderr", out + err)

    def test_no_gate_flag_bypasses_with_warning(self):
        self.author_home()
        self.on_branch()
        self.env("SHIP_GATE_DIR", os.path.join(self._tmp.name, "nowhere"))
        rc, _, err = self.commit_b("--no-gate")
        self.assertEqual(rc, 0, err)
        self.assertIn("--no-gate", err)
        self.assertEqual(self.count(), 2)

    def test_strict_ignores_branch_override(self):
        self.author_home()
        self.on_branch()
        ship.run_gate(self.sub, strict=True)
        cfg = self.calls()[-1]["cfg"]
        self.assertEqual(cfg["gate"]["commit"], "strict")
        self.assertFalse(cfg["gate"].get("branches"))

    def test_accept_baseline_refused_on_main(self):
        self.author_home()
        rc, _, err = self.ship("accept-baseline", "sub")
        self.assertEqual(rc, 1)
        self.assertIn("ship: refused", err)
        self.assertEqual(self.calls(), [])

    def test_accept_baseline_runs_write_baseline(self):
        self.author_home()
        self.on_branch()
        rc, out, err = self.ship("accept-baseline", "sub")
        self.assertEqual(rc, 0, err)
        self.assertIn("baseline written", out)
        argv = self.calls()[-1]["argv"]
        self.assertEqual(argv[0], "--write-baseline")
        self.assertEqual(os.path.realpath(argv[argv.index("--root") + 1]), os.path.realpath(self.sub))

    def test_accept_baseline_refused_in_non_author_home(self):
        self.on_branch()
        self.assertEqual(self.ship("accept-baseline", "sub")[0], 1)

    def test_paths_commit_excludes_prestaged_other_file(self):
        self.on_branch()
        self.write("other.txt")
        run(self.sub, "add", "other.txt")
        rc, _, err = self.commit_b()
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.sub, "show", "--name-only", "--format=", "HEAD"), "b.txt")
        self.assertIn("other.txt", run(self.sub, "diff", "--cached", "--name-only"))


class MergeBase(GateEnv):
    """A reviewed branch pushed to the remote; the checkout sits on that branch.

    The workspace is built once per class (setUpClass) and copied per test; the copy's
    remote URLs are pointed at the copy's own bare remote, so no test touches another's."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tpl = tempfile.TemporaryDirectory()
        root, sub, remote = make_workspace(cls._tpl.name)
        cls.branch = ship.branch_name("topic", "human")
        run(sub, "switch", "-q", "-c", cls.branch)
        with open(os.path.join(sub, "b.txt"), "w", encoding="utf-8") as f:
            f.write("b\n")
        run(sub, "add", "b.txt")
        run(sub, "commit", "-q", "-m", "add b")
        run(sub, "push", "-q", "-u", "origin", "HEAD:refs/heads/" + cls.branch)
        cls.tip = run(sub, "rev-parse", "HEAD")
        cls.main_before = run(sub, "rev-parse", "main")
        cls.remote_main_before = run(remote, "rev-parse", "main")

    @classmethod
    def tearDownClass(cls):
        cls._tpl.cleanup()
        super().tearDownClass()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        shutil.copytree(self._tpl.name, self._tmp.name, dirs_exist_ok=True)
        self.root = os.path.join(self._tmp.name, "root")
        self.sub = os.path.join(self.root, "sub")
        self.remote = os.path.join(self._tmp.name, "remote.git")
        run(self.sub, "remote", "set-url", "origin", self.remote)
        with open(os.path.join(self.root, ".gitmodules"), "w", encoding="utf-8") as f:
            f.write('[submodule "sub"]\n\tpath = sub\n\turl = %s\n' % self.remote.replace("\\", "/"))
        old = ship.ROOT
        ship.ROOT = self.root
        self.addCleanup(setattr, ship, "ROOT", old)
        self.gate_setup()


    def other_clone(self):
        """A second clone of the remote, as someone else pushing."""
        other = os.path.join(self._tmp.name, "other")
        if not os.path.isdir(other):
            run(self._tmp.name, "clone", "-q", self.remote, other)
            run(other, "config", "user.name", "Other")
            run(other, "config", "user.email", "o@example.com")
            run(other, "config", "commit.gpgsign", "false")
        return other

    def push_from_other(self, ref, name="o.txt"):
        other = self.other_clone()
        run(other, "fetch", "-q", "origin")
        run(other, "switch", "-q", "-C", "w", "origin/" + ref)
        with open(os.path.join(other, name), "w", encoding="utf-8") as f:
            f.write("o\n")
        run(other, "add", name)
        run(other, "commit", "-q", "-m", "other")
        run(other, "push", "-q", "origin", "HEAD:refs/heads/" + ref)
        return run(other, "rev-parse", "HEAD")

    def merge(self, *extra, sha=None, branch=None):
        return self.ship("merge", "sub", branch or self.branch, "--sha", sha or self.tip, *extra)

    def assert_untouched(self, branch=None):
        """A refused merge leaves the repo exactly as it was."""
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)
        self.assertEqual(ship.current(self.sub), branch or self.branch)
        self.assertEqual(run(self.sub, "status", "--porcelain", "--untracked-files=no"), "")
        self.assertEqual(ship.git(self.sub, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False), "")
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.remote_main_before)


class TestMerge(MergeBase):
    def test_template_copy_is_isolated(self):
        self.assertEqual(os.path.realpath(run(self.sub, "remote", "get-url", "origin")),
                         os.path.realpath(self.remote))
        self.assertEqual(ship.current(self.sub), self.branch)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + self.branch), self.tip)
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)

    def conflicting_main(self):
        """A local commit on main that conflicts with the branch; back on the branch after."""
        run(self.sub, "switch", "-q", "main")
        self.write("b.txt", "conflicting\n")
        run(self.sub, "add", "b.txt")
        run(self.sub, "commit", "-q", "-m", "main side")
        self.main_before = run(self.sub, "rev-parse", "main")
        run(self.sub, "switch", "-q", self.branch)

    def test_merge_conflict_rolls_back_from_feature_branch(self):
        self.conflicting_main()
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assert_untouched()

    def test_merge_conflict_rolls_back_from_detached_head(self):
        self.conflicting_main()
        run(self.sub, "checkout", "-q", "--detach", self.tip)
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertEqual(ship.current(self.sub), "")
        self.assertEqual(run(self.sub, "rev-parse", "HEAD"), self.tip)
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)
        self.assertEqual(run(self.sub, "status", "--porcelain", "--untracked-files=no"), "")
        self.assertEqual(ship.git(self.sub, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False), "")
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.remote_main_before)

    def test_merge_refuses_non_strict_gate_mode(self):
        self.author_home()
        for mode in ("normal", "warn", "off"):
            self.env("STUB_MODE", mode)
            rc, _, err = self.merge()
            self.assertEqual(rc, 1, mode)
            self.assertIn("strict", err, mode)
            self.assertIn(mode, err)
            self.assert_untouched()

    def test_rollback_warns_when_switch_back_fails(self):
        self.author_home()
        self.env("STUB_RAISE", "1")
        real = ship.git

        def no_switch_back(repo, *args, **kw):
            if args[:1] == ("switch",) and self.branch in args:
                return ""  # the switch back silently does nothing
            return real(repo, *args, **kw)

        with mock.patch.object(ship, "git", no_switch_back):
            rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("WARNING", err)
        self.assertIn(self.branch, err)
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)

    def test_merge_bump_failure_after_merge_says_merge_done(self):
        self.root_with_history()
        lock = os.path.join(self.root, ".git", "index.lock")
        with open(lock, "w") as f:
            f.write("")
        self.addCleanup(lambda: os.path.exists(lock) and os.remove(lock))
        rc, _, err = self.merge("--bump")
        self.assertEqual(rc, 1)
        self.assertIn("merge done; bump failed: ", err)
        self.assertEqual(run(self.sub, "rev-parse", "main^2"), self.tip)

    def test_merge_refuses_non_template_branch(self):
        run(self.sub, "switch", "-q", "-c", "feature-x")
        run(self.sub, "push", "-q", "origin", "feature-x")
        for b in ("feature-x", "main", "origin/" + self.branch):
            rc, _, err = self.merge(branch=b)
            self.assertEqual(rc, 1, b)
            self.assertIn("template", err)
        self.assert_untouched("feature-x")

    def test_merge_refuses_branch_missing_on_remote(self):
        rc, _, err = self.merge(branch="2026-09-30/nothing-here/human")
        self.assertEqual(rc, 1)
        self.assertIn("does not exist on origin", err)
        self.assert_untouched()

    def test_remote_tip_returns_full_sha(self):
        self.assertEqual(ship.remote_tip(self.sub, self.branch), self.tip)
        with self.assertRaises(ship.Refuse):
            ship.remote_tip(self.sub, "2026-09-30/nothing-here/human")

    def test_merge_refuses_stale_sha(self):
        moved = self.push_from_other(self.branch)
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("branch moved since review: %s" % moved, err)
        self.assert_untouched()

    def test_merge_accepts_sha_prefix(self):
        rc, _, err = self.merge(sha=self.tip[:6])
        self.assertEqual(rc, 1)
        self.assertIn("--sha %r must be a full SHA or a hex prefix of at least 7 characters"
                      % self.tip[:6], err)
        self.assert_untouched()
        rc, _, err = self.merge(sha=self.tip[:7])
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.sub, "rev-parse", "main^2"), self.tip)

    def test_merge_refuses_dirty_tree(self):
        self.write("a.txt", "changed\n")
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("clean", err)
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)
        self.assertEqual(ship.current(self.sub), self.branch)
        self.assertEqual(run(self.sub, "status", "--porcelain", "--untracked-files=no"), "M a.txt")

    def test_merge_refuses_staged_change(self):
        self.write("a.txt", "changed\n")
        run(self.sub, "add", "a.txt")
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("clean", err)

    def test_merge_refuses_diverged_main(self):
        # local main behind origin/main
        self.push_from_other("main")
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("origin/main", err)
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)
        self.assertEqual(ship.current(self.sub), self.branch)
        self.assertEqual(run(self.sub, "status", "--porcelain"), "")
        self.assertEqual(ship.git(self.sub, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False), "")
        # and diverged: a local commit on main as well
        run(self.sub, "switch", "-q", "main")
        self.write("l.txt")
        run(self.sub, "add", "l.txt")
        run(self.sub, "commit", "-q", "-m", "local")
        local = run(self.sub, "rev-parse", "HEAD")
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("origin/main", err)
        self.assertEqual(run(self.sub, "rev-parse", "main"), local)
        self.assertEqual(ship.current(self.sub), "main")
        self.assertEqual(run(self.sub, "status", "--porcelain"), "")
        self.assertEqual(ship.git(self.sub, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False), "")

    def test_merge_refuses_already_merged(self):
        self.assertEqual(self.merge()[0], 0)
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("nothing to merge", err)

    def test_merge_creates_noff_merge_commit(self):
        rc, out, err = self.merge()
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.sub), "main")
        parents = run(self.sub, "log", "-1", "--format=%P", "main").split()
        self.assertEqual(parents, [self.main_before, self.tip])
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B", "main"), "Merge %s into main" % self.branch)
        self.assertIn("1 commit", out)
        self.assertIn("1 file changed", out)
        self.assertIn("gate", out)
        self.assertEqual(run(self.sub, "status", "--porcelain", "--untracked-files=no"), "")

    def test_merge_custom_message(self):
        rc, _, err = self.merge("-m", "Take the b work")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B", "main"), "Take the b work")

    def test_merge_does_not_push(self):
        rc, _, err = self.merge()
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.remote_main_before)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + self.branch), self.tip)

    def test_merge_blocks_on_strict_gate_findings_author_home(self):
        self.author_home()
        self.env("STUB_MODE", "strict")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("missing label foo", err)
        self.assert_untouched()
        cfg = self.calls()[-1]["cfg"]
        self.assertEqual(cfg["gate"]["commit"], "strict")
        self.assertFalse(cfg["gate"].get("branches"))

    def test_merge_gate_sees_merged_tree(self):
        self.author_home()
        seen = os.path.join(self._tmp.name, "seen.txt")
        gate = os.path.join(self.gate_dir, "commit_gate.py")
        with open(gate, "a", encoding="utf-8") as f:
            f.write('\n_orig = gate_check\n'
                    'def gate_check(home, cfg, branch):\n'
                    '    with open(%r, "w") as g:\n'
                    '        g.write(str(os.path.exists(os.path.join(home, "b.txt"))) + " " + str(branch))\n'
                    '    return _orig(home, cfg, branch)\n' % seen)
        run(self.sub, "switch", "-q", "main")
        rc, _, err = self.merge()
        self.assertEqual(rc, 0, err)
        with open(seen) as f:
            self.assertEqual(f.read(), "True main")

    def test_merge_warn_mode_findings_still_block(self):
        self.author_home()
        self.env("STUB_MODE", "warn")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("missing label foo", err)
        self.assert_untouched()

    def test_merge_gate_exception_rolls_back(self):
        self.author_home()
        self.env("STUB_RAISE", "1")
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("gate failed", err)
        self.assert_untouched()

    def test_merge_conflict_rolls_back(self):
        run(self.sub, "switch", "-q", "main")
        self.write("b.txt", "conflicting\n")
        run(self.sub, "add", "b.txt")
        run(self.sub, "commit", "-q", "-m", "main side")
        self.main_before = run(self.sub, "rev-parse", "main")
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assert_untouched("main")

    def test_merge_refuses_when_branch_drops_author_role(self):
        # main tracks an Author config; the branch rewrites the role to dodge the gate
        run(self.sub, "switch", "-q", "main")
        os.makedirs(os.path.join(self.sub, ".claude"), exist_ok=True)
        cfg = os.path.join(self.sub, ".claude", "academy.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"role": "author"}, f)
        run(self.sub, "add", cfg)
        run(self.sub, "commit", "-q", "-m", "author cfg")
        run(self.sub, "push", "-q", "origin", "main")
        run(self.sub, "switch", "-q", self.branch)
        run(self.sub, "merge", "-q", "--no-edit", "main")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"role": "expert"}, f)
        run(self.sub, "commit", "-q", "-am", "dodge")
        run(self.sub, "push", "-q", "origin", self.branch)
        self.tip = run(self.sub, "rev-parse", "HEAD")
        self.main_before = run(self.sub, "rev-parse", "main")
        self.remote_main_before = run(self.remote, "rev-parse", "main")
        self.env("STUB_FINDINGS", json.dumps({"k1": "x"}))
        rc, _, err = self.merge()
        self.assertEqual(rc, 1)
        self.assertIn("role", err)
        self.assert_untouched()

    def test_merge_non_author_home_skips_gate(self):
        self.env("STUB_FINDINGS", json.dumps({"k1": "x"}))
        rc, out, err = self.merge()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.calls(), [])
        self.assertIn("gate: skipped", out)

    def root_with_history(self):
        run(self.root, "add", ".gitmodules")
        with open(os.path.join(self.root, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("n\n")
        run(self.root, "add", "notes.txt")
        run(self.root, "commit", "-q", "-m", "root init")
        with open(os.path.join(self.root, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("dirty\n")
        with open(os.path.join(self.root, "staged.txt"), "w", encoding="utf-8") as f:
            f.write("s\n")
        run(self.root, "add", "staged.txt")
        return run(self.root, "rev-parse", "HEAD")

    def test_merge_bump_makes_separate_superproject_commit(self):
        root_before = self.root_with_history()
        status_before = run(self.root, "status", "--porcelain", "--", "notes.txt", "staged.txt")
        rc, out, err = self.merge("--bump")
        self.assertEqual(rc, 0, err)
        merged = run(self.sub, "rev-parse", "main")
        self.assertEqual(run(self.root, "rev-parse", "HEAD~1"), root_before)
        short = run(self.sub, "rev-parse", "--short", "main")
        self.assertEqual(run(self.root, "log", "-1", "--format=%B"), "Bump sub to %s" % short)
        self.assertEqual(run(self.root, "show", "--name-only", "--format=", "HEAD"), "sub")
        self.assertEqual(run(self.root, "ls-tree", "HEAD", "sub").split()[2], merged)
        self.assertEqual(run(self.root, "status", "--porcelain", "--", "notes.txt", "staged.txt"), status_before)

    def test_merge_without_bump_leaves_superproject_alone(self):
        root_before = self.root_with_history()
        status_before = run(self.root, "status", "--porcelain")
        rc, _, err = self.merge()
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.root, "rev-parse", "HEAD"), root_before)
        self.assertEqual(run(self.root, "diff", "--cached", "--name-only"), "staged.txt")
        self.assertEqual(run(self.root, "status", "--porcelain"), status_before)

    def test_merge_bump_refused_for_other_checkout_before_merging(self):
        self.root_with_history()
        wt = os.path.join(self._tmp.name, "wt")
        run(self.sub, "worktree", "add", "-q", wt, "main")
        rc, _, err = self.ship("merge", "sub", self.branch, "--sha", self.tip, "--bump", "--repo", wt)
        self.assertEqual(rc, 1)
        self.assertIn("--bump", err)
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)

    def test_merge_has_no_no_gate_flag(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ship.main(["merge", "sub", self.branch, "--sha", self.tip, "--no-gate"])
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)


class TestPublish(MergeBase):
    def merged(self):
        rc, _, err = self.merge()
        self.assertEqual(rc, 0, err)
        return run(self.sub, "rev-parse", "main")

    def test_publish_refuses_wrong_sha(self):
        self.merged()
        rc, _, err = self.ship("publish", "sub", "--sha", self.tip)
        self.assertEqual(rc, 1)
        self.assertIn("HEAD", err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.remote_main_before)

    def test_publish_refuses_short_prefix(self):
        head = self.merged()
        rc, _, _ = self.ship("publish", "sub", "--sha", head[:6])
        self.assertEqual(rc, 1)
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.remote_main_before)

    def test_publish_refuses_off_main(self):
        rc, _, err = self.ship("publish", "sub", "--sha", self.tip)
        self.assertEqual(rc, 1)
        self.assertIn("main", err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.remote_main_before)

    def test_publish_refuses_dirty_tree(self):
        head = self.merged()
        self.write("a.txt", "changed\n")
        rc, _, err = self.ship("publish", "sub", "--sha", head)
        self.assertEqual(rc, 1)
        self.assertIn("clean", err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.remote_main_before)

    def test_publish_pushes_main_when_sha_matches(self):
        head = self.merged()
        other_before = run(self.remote, "for-each-ref", "--format=%(refname) %(objectname)")
        rc, out, err = self.ship("publish", "sub", "--sha", head[:9])
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), head)
        after = run(self.remote, "for-each-ref", "--format=%(refname) %(objectname)")
        changed = set(after.splitlines()) ^ set(other_before.splitlines())
        self.assertEqual({l.split()[0] for l in changed}, {"refs/heads/main"})

    def test_publish_pushes_the_verified_sha_not_the_ref(self):
        head = self.merged()

        def main_moves(repo, **_kw):
            # main moves between the SHA check and the push
            self.write("late.txt")
            run(self.sub, "add", "late.txt")
            run(self.sub, "commit", "-q", "-m", "late")

        with mock.patch.object(ship, "require_clean", main_moves):
            rc, _, err = self.ship("publish", "sub", "--sha", head)
        self.assertEqual(rc, 0, err)
        self.assertNotEqual(run(self.sub, "rev-parse", "main"), head)
        self.assertEqual(run(self.remote, "rev-parse", "main"), head)

    def test_publish_does_not_push_tags(self):
        head = self.merged()
        run(self.sub, "config", "push.followTags", "true")
        run(self.sub, "tag", "-a", "v1", "-m", "annotated", "main")
        rc, _, err = self.ship("publish", "sub", "--sha", head)
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), head)
        self.assertEqual(run(self.remote, "tag", "--list"), "")

    def test_publish_reports_remote_rejection(self):
        head = self.merged()
        moved = self.push_from_other("main")
        rc, _, err = self.ship("publish", "sub", "--sha", head)
        self.assertEqual(rc, 1)
        self.assertIn("rejected", err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), moved)


class TestParser(unittest.TestCase):
    def test_no_force_flag_exists(self):
        p = ship.parser()
        subs = [a for a in p._actions if isinstance(a, argparse._SubParsersAction)]
        self.assertTrue(subs)
        for name, sp in subs[0].choices.items():
            for action in sp._actions:
                for opt in action.option_strings:
                    self.assertNotIn(opt, ("--force", "-f"), name)
                    self.assertNotIn("force", opt, name)
        self.assertIn("merge", subs[0].choices)
        self.assertIn("publish", subs[0].choices)

    def test_source_never_forces(self):
        with open(ship.__file__, encoding="utf-8") as f:
            src = f.read()
        for bad in ("--force", "+refs/", "+HEAD", '"-f", "push"', "--delete", '"-D"'):
            self.assertFalse(bad in src, "ship.py contains %r" % bad)


if __name__ == "__main__":
    unittest.main()
