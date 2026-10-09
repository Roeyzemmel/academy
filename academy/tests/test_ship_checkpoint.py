"""ship.py checkpoint: at the end of an inbox ticket, commit and push every touched repo
on <date>/<ticket-id>/<role>. Temp repos and temp bare remotes only."""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import ship  # noqa: E402
from ship_fixture import STUB_GATE, add_submodule, make_workspace, run  # noqa: E402

TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"


class CheckpointBase(unittest.TestCase):
    """Two submodules, 'sub' and 'other', each on main with one commit pushed.

    Built once per class and copied per test; each copy's remote URLs point at its own
    bare remotes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tpl = tempfile.TemporaryDirectory()
        root, _, _ = make_workspace(cls._tpl.name)
        add_submodule(cls._tpl.name, root, "other")

    @classmethod
    def tearDownClass(cls):
        cls._tpl.cleanup()
        super().tearDownClass()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = self._tmp.name
        shutil.copytree(self._tpl.name, tmp, dirs_exist_ok=True)
        self.root = os.path.join(tmp, "root")
        self.sub, self.remote = os.path.join(self.root, "sub"), os.path.join(tmp, "remote.git")
        self.other, self.other_remote = os.path.join(self.root, "other"), os.path.join(tmp, "other-remote.git")
        for repo, remote in ((self.sub, self.remote), (self.other, self.other_remote)):
            run(repo, "remote", "set-url", "origin", remote)
        with open(os.path.join(self.root, ".gitmodules"), "w", encoding="utf-8") as f:
            for name, remote in (("sub", self.remote), ("other", self.other_remote)):
                f.write('[submodule "%s"]\n\tpath = %s\n\turl = %s\n' % (name, name, remote.replace("\\", "/")))
        old = ship.ROOT
        ship.ROOT = self.root
        self.addCleanup(setattr, ship, "ROOT", old)
        gate_dir = os.path.join(tmp, "gate")
        os.makedirs(gate_dir)
        with open(os.path.join(gate_dir, "commit_gate.py"), "w", encoding="utf-8") as f:
            f.write(STUB_GATE)
        self.log = os.path.join(tmp, "gate.log")
        for k, v in (("SHIP_GATE_DIR", gate_dir), ("STUB_LOG", self.log), ("STUB_MODE", ""),
                     ("STUB_FINDINGS", "{}"), ("STUB_RAISE", ""), ("SHIP_TRAILER", None),
                     ("STUB_CAUSE", ""), ("STUB_NO_DETAIL", ""), ("STUB_NO_CHECK", "")):
            self.env(k, v)
        self.main = {r: run(r, "rev-parse", "main") for r in (self.sub, self.other)}

    def env(self, k, v):
        old = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
        self.addCleanup(lambda: os.environ.pop(k, None) if old is None else os.environ.__setitem__(k, old))

    def cp(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ship.main(["checkpoint", *argv])
        return rc, out.getvalue(), err.getvalue()

    def write(self, repo, name, text="x\n"):
        path = os.path.join(repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def branch(self, role="human", ticket="T-0059"):
        return ship.branch_name(ticket, role)

    def remote_branches(self, remote):
        return run(remote, "for-each-ref", "--format=%(refname)", "refs/heads/").splitlines()

    def files(self, repo, rev="HEAD"):
        return sorted(run(repo, "show", "--name-only", "--format=", rev).splitlines())

    def author_home(self, repo, commit_mode="normal"):
        self.write(repo, os.path.join(".claude", "academy.json"),
                   json.dumps({"role": "author", "gate": {"commit": commit_mode}}))

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def assert_main_untouched(self):
        for repo, remote in ((self.sub, self.remote), (self.other, self.other_remote)):
            self.assertEqual(run(repo, "rev-parse", "main"), self.main[repo])
            self.assertEqual(run(remote, "rev-parse", "main"), self.main[repo])


class TestCheckpoint(CheckpointBase):
    def test_fixture_copy_is_isolated(self):
        for repo, remote in ((self.sub, self.remote), (self.other, self.other_remote)):
            self.assertEqual(os.path.realpath(run(repo, "remote", "get-url", "origin")), os.path.realpath(remote))
        self.assertEqual(ship.submodule_names(), ["sub", "other"])

    def test_checkpoint_commits_and_pushes_dirty_repo(self):
        self.write(self.sub, "a.txt", "changed\n")
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        name = self.branch()
        self.assertEqual(ship.current(self.sub), name)
        head = run(self.sub, "rev-parse", "HEAD")
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name), head)
        self.assertEqual(run(self.sub, "rev-parse", "HEAD~1"), self.main[self.sub])
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B"), "T-0059: checkpoint")
        self.assertEqual(self.files(self.sub), ["a.txt", "b.txt"])
        self.assertEqual(run(self.sub, "status", "--porcelain"), "")
        short = run(self.sub, "rev-parse", "--short", "HEAD")
        self.assertIn("sub %s @ %s (2 files) pushed" % (name, short), out)
        self.assert_main_untouched()

    def test_checkpoint_skips_clean_repos(self):
        self.write(self.sub, "b.txt")
        results = ship.run_checkpoint("T-0059", None, None, None)
        by = {r["sub"]: r for r in results}
        self.assertEqual(set(by), {"sub", "other"})
        self.assertEqual(by["sub"]["status"], "pushed")
        self.assertEqual(by["sub"]["files"], 1)
        self.assertEqual(by["other"]["status"], "unchanged")
        self.assertEqual(by["other"]["files"], 0)
        for r in results:
            self.assertEqual(set(r), {"sub", "branch", "sha", "files", "status", "detail", "names", "skipped"})
        self.assertEqual(by["sub"]["names"], ["b.txt"])
        self.assertEqual(by["other"]["names"], [])
        self.assertEqual(ship.current(self.other), "main")
        self.assertEqual(self.remote_branches(self.other_remote), ["refs/heads/main"])
        self.assertEqual(run(self.other, "rev-list", "--count", "HEAD"), "1")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertRegex(out, r"(?m)^other \S+ @ [0-9a-f]+ \(0 files\) unchanged$")
        self.assertRegex(out, r"(?m)^sub %s @ [0-9a-f]+ \(0 files\) unchanged$" % re.escape(self.branch()))

    def test_checkpoint_pushes_unpushed_commits_on_clean_repo(self):
        name = self.branch()
        run(self.sub, "switch", "-q", "-c", name)
        self.write(self.sub, "b.txt")
        run(self.sub, "add", "b.txt")
        run(self.sub, "commit", "-q", "-m", "done by hand")
        run(self.sub, "switch", "-q", "main")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name), run(self.sub, "rev-parse", name))
        self.assertIn("sub %s @ " % name, out)
        self.assertIn("(0 files) pushed", out)
        self.assert_main_untouched()

    def test_checkpoint_reuses_template_branch(self):
        name = self.branch()
        self.write(self.sub, "b.txt")
        self.assertEqual(self.cp("--ticket", "T-0059")[0], 0)
        first = run(self.sub, "rev-parse", "HEAD")
        # still on the branch: reused
        self.write(self.sub, "c.txt")
        rc, _, err = self.cp("--ticket", "T-0059", "--title", "second")
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.sub), name)
        self.assertEqual(run(self.sub, "rev-parse", "HEAD~1"), first)
        second = run(self.sub, "rev-parse", "HEAD")
        # switched away to main: the existing branch is switched back to, changes carried
        run(self.sub, "switch", "-q", "main")
        self.write(self.sub, "d.txt")
        rc, _, err = self.cp("--ticket", "T-0059", "--title", "third")
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.sub), name)
        self.assertEqual(run(self.sub, "rev-parse", "HEAD~1"), second)
        self.assertEqual(self.files(self.sub), ["d.txt"])
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B"), "T-0059: third")
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name), run(self.sub, "rev-parse", "HEAD"))
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/" + name, "refs/heads/main"])

    def test_checkpoint_branch_from_ticket_id_and_role(self):
        day = r"\d{4}-\d{2}-\d{2}"
        self.write(self.sub, "b.txt")
        self.write(self.other, os.path.join(".claude", "academy.json"), json.dumps({"role": "expert"}))
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertRegex(ship.current(self.sub), r"^%s/t-0059/human$" % day)
        self.assertRegex(ship.current(self.other), r"^%s/t-0059/expert$" % day)
        self.write(self.sub, "c.txt")
        self.write(self.other, "c.txt")
        rc, _, err = self.cp("--ticket", "T-0060", "--role", "researcher")
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.sub), self.branch("researcher", "T-0060"))
        self.assertEqual(ship.current(self.other), self.branch("researcher", "T-0060"))
        self.assertRegex(ship.current(self.sub), r"^%s/t-0060/researcher$" % day)

    def test_checkpoint_bad_role_refused(self):
        self.write(self.sub, "b.txt")
        rc, _, err = self.cp("--ticket", "T-0059", "--role", "wizard")
        self.assertEqual(rc, 1)
        self.assertIn("role", err)
        self.assertEqual(ship.current(self.sub), "main")
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])

    def test_checkpoint_never_pushes_main(self):
        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assert_main_untouched()
        for remote in (self.remote, self.other_remote):
            self.assertEqual(self.remote_branches(remote), ["refs/heads/" + self.branch(), "refs/heads/main"])

    def test_checkpoint_keeps_commit_when_push_fails(self):
        run(self.sub, "remote", "set-url", "origin", os.path.join(self._tmp.name, "missing.git"))
        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertRegex(out, r"(?m)^sub %s @ [0-9a-f]+ \(1 files\) PUSH FAILED: .+$" % re.escape(self.branch()))
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B"), "T-0059: checkpoint")
        self.assertEqual(ship.current(self.sub), self.branch())
        self.assertEqual(run(self.sub, "status", "--porcelain"), "")
        # the other repo still went through
        self.assertEqual(run(self.other_remote, "rev-parse", "refs/heads/" + self.branch()),
                         run(self.other, "rev-parse", "HEAD"))
        by = {r["sub"]: r for r in ship.run_checkpoint("T-0059", None, None, None)}
        self.assertEqual(by["sub"]["status"], "push-failed")
        self.assertTrue(by["sub"]["detail"])

    def test_checkpoint_honours_ship_remote(self):
        mirror = os.path.join(self._tmp.name, "mirror.git")
        run(self._tmp.name, "init", "-q", "--bare", "-b", "main", mirror)
        run(self.sub, "remote", "add", "mirror", mirror)
        with open(os.path.join(self.root, "workspace.json"), "w", encoding="utf-8") as f:
            json.dump({"instances": {}, "shipRemote": "mirror"}, f)
        self.assertEqual(ship.ship_remote(), "mirror")
        self.write(self.sub, "b.txt")
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        name = self.branch()
        self.assertEqual(run(mirror, "rev-parse", "refs/heads/" + name), run(self.sub, "rev-parse", "HEAD"))
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])
        # --remote overrides
        self.write(self.sub, "c.txt")
        rc, _, err = self.cp("--ticket", "T-0059", "--remote", "origin")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name), run(self.sub, "rev-parse", "HEAD"))

    def test_ship_remote_defaults_to_origin(self):
        self.assertEqual(ship.ship_remote(), "origin")
        with open(os.path.join(self.root, "workspace.json"), "w", encoding="utf-8") as f:
            json.dump({"instances": {}}, f)
        self.assertEqual(ship.ship_remote(), "origin")

    def test_checkpoint_bad_remote_name_refused(self):
        self.write(self.sub, "b.txt")
        rc, _, err = self.cp("--ticket", "T-0059", "--remote=--upload-pack=x")
        self.assertEqual(rc, 1)
        self.assertIn("remote", err)
        self.assertEqual(ship.current(self.sub), "main")

    def test_checkpoint_author_home_runs_gate(self):
        self.author_home(self.sub)
        self.write(self.sub, "b.txt")
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(os.path.realpath(calls[0]["home"]), os.path.realpath(self.sub))
        self.assertEqual(calls[0]["branch"], self.branch("author"))
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + self.branch("author")),
                         run(self.sub, "rev-parse", "HEAD"))
        # warn mode: findings are printed, the commit goes ahead
        self.write(self.sub, "c.txt")
        self.env("STUB_MODE", "warn")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertIn("ship: gate warning: missing label foo", err)
        self.assertEqual(self.files(self.sub), ["c.txt"])
        # off mode: no findings matter
        self.write(self.sub, "d.txt")
        self.env("STUB_MODE", "off")
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.files(self.sub), ["d.txt"])

    def test_checkpoint_blocking_gate_refuses_that_repo_only(self):
        self.author_home(self.sub)
        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertIn("missing label foo", out + err)
        self.assertRegex(out, r"(?m)^sub \S+ @ [0-9a-f]+ \(0 files\) REFUSED: ")
        self.assertEqual(run(self.sub, "rev-parse", "HEAD"), self.main[self.sub])
        self.assertIn("b.txt", run(self.sub, "status", "--porcelain"))
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])
        self.assertEqual(run(self.other_remote, "rev-parse", "refs/heads/" + self.branch()),
                         run(self.other, "rev-parse", "HEAD"))
        self.assert_main_untouched()

    def test_checkpoint_gate_failure_refuses_that_repo_only(self):
        self.author_home(self.sub)
        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        self.env("STUB_RAISE", "1")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertIn("gate failed: stub gate exploded", out + err)
        self.assertEqual(run(self.sub, "rev-parse", "HEAD"), self.main[self.sub])
        self.assertIn("pushed", out)

    def test_checkpoint_includes_untracked_new_files_not_ignored(self):
        self.write(self.sub, ".gitignore", "*.log\nbuild/\n")
        self.write(self.sub, "new.txt")
        self.write(self.sub, os.path.join("dir", "deep.txt"))
        self.write(self.sub, "junk.log")
        self.write(self.sub, os.path.join("build", "out.txt"))
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.files(self.sub), [".gitignore", "dir/deep.txt", "new.txt"])
        self.assertTrue(os.path.exists(os.path.join(self.sub, "junk.log")))

    def test_checkpoint_ignored_only_changes_are_unchanged(self):
        run(self.sub, "switch", "-q", "-c", "keep")
        self.write(self.sub, ".gitignore", "*.log\n")
        run(self.sub, "add", ".gitignore")
        run(self.sub, "commit", "-q", "-m", "ignore logs")
        run(self.sub, "switch", "-q", "main")
        run(self.sub, "merge", "-q", "--ff-only", "keep")
        run(self.sub, "push", "-q", "origin", "main")
        self.main[self.sub] = run(self.sub, "rev-parse", "main")
        self.write(self.sub, "junk.log")
        by = {r["sub"]: r for r in ship.run_checkpoint("T-0059", None, None, None)}
        self.assertEqual(by["sub"]["status"], "unchanged")
        self.assertEqual(ship.current(self.sub), "main")

    def test_checkpoint_refuses_detached_repo(self):
        run(self.sub, "checkout", "-q", "--detach")
        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertIn("detached", out + err)
        self.assertEqual(ship.current(self.sub), "")
        self.assertEqual(run(self.sub, "rev-parse", "HEAD"), self.main[self.sub])
        self.assertIn("b.txt", run(self.sub, "status", "--porcelain"))
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])
        self.assertIn("pushed", out)  # the other repo still went through

    def test_checkpoint_detached_clean_repo_is_unchanged(self):
        # a submodule left detached by 'git submodule update' that the ticket never touched
        run(self.other, "checkout", "-q", "--detach")
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.other), "")
        self.assertRegex(out, r"(?m)^other .* unchanged$")

    def test_checkpoint_refuses_merge_in_progress(self):
        run(self.sub, "switch", "-q", "-c", "side")
        self.write(self.sub, "a.txt", "side\n")
        run(self.sub, "commit", "-q", "-am", "side")
        run(self.sub, "switch", "-q", "main")
        self.write(self.sub, "a.txt", "main\n")
        run(self.sub, "commit", "-q", "-am", "main")
        self.main[self.sub] = run(self.sub, "rev-parse", "main")
        run(self.sub, "push", "-q", "origin", "main")
        ship.git(self.sub, "merge", "side", check=False)  # conflicts
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertIn("in progress", out + err)
        self.assertEqual(ship.current(self.sub), "main")
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main[self.sub])

    def test_checkpoint_bad_ticket_id_refused(self):
        self.write(self.sub, "b.txt")
        for bad in ("!!!", "", "T 59", "T-59\nx", "--ticket=-x", "T_59", "t-0059/x"):
            argv = [bad] if bad.startswith("--ticket=") else ["--ticket", bad]
            rc, _, err = self.cp(*argv)
            self.assertEqual(rc, 1, bad)
            self.assertIn("ticket", err, bad)
        self.assertEqual(ship.current(self.sub), "main")
        self.assertEqual(run(self.sub, "rev-list", "--count", "HEAD"), "1")
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])

    def test_checkpoint_needs_ticket(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ship.main(["checkpoint"])

    def test_checkpoint_trailer_from_env(self):
        self.env("SHIP_TRAILER", TRAILER)
        self.write(self.sub, "b.txt")
        rc, _, err = self.cp("--ticket", "T-0059", "--title", "prove lemma 3")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B"), "T-0059: prove lemma 3\n\n" + TRAILER)
        self.env("SHIP_TRAILER", "")
        self.write(self.sub, "c.txt")
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B"), "T-0059: checkpoint")

    def test_checkpoint_has_no_repo_flag(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ship.main(["checkpoint", "--ticket", "T-0059", "--repo", self.sub])


class TestCheckpointFixes(CheckpointBase):
    """Final fix wave: I5 (a)-(e) and I2 for checkpoint."""

    # (a) a Refuse inside one repo is that repo's result; the others go on
    def test_refuse_in_one_repo_does_not_stop_the_others(self):
        real = ship.checkpoint_repo

        def boom(sub, *args, **kw):
            if sub == "sub":
                raise ship.Refuse("git rev-parse failed in sub: boom")
            return real(sub, *args, **kw)

        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        with unittest.mock.patch.object(ship, "checkpoint_repo", boom):
            rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertRegex(out, r"(?m)^sub .*REFUSED: git rev-parse failed in sub: boom$")
        self.assertRegex(out, r"(?m)^other %s @ [0-9a-f]+ \(1 files\) pushed$" % re.escape(self.branch()))
        self.assertIn("checkpoint incomplete", err)

    # (b) nested repositories and worktrees are never swept in
    def test_nested_repo_and_worktree_skipped(self):
        nested = os.path.join(self.sub, "nested")
        run(self.sub, "init", "-q", nested)  # git init <dir> creates it
        self.write(nested, "n.txt")
        run(self.sub, "worktree", "add", "-q", "-b", "scratch", os.path.join(self.sub, ".claude", "worktrees", "wt"))
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.files(self.sub), ["b.txt"])
        self.assertEqual(run(self.sub, "ls-files", "-s", "nested", ".claude"), "")
        self.assertIn("skipped nested repo: nested/", out)
        self.assertIn("skipped nested repo: .claude/worktrees/wt/", out)

    def test_only_nested_repo_is_unchanged(self):
        run(self.sub, "init", "-q", os.path.join(self.sub, "nested"))
        by = {r["sub"]: r for r in ship.run_checkpoint("T-0059", None, None, None)}
        self.assertEqual(by["sub"]["status"], "unchanged")
        self.assertEqual(by["sub"]["skipped"], ["nested/"])
        self.assertEqual(ship.current(self.sub), "main")
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])

    # (c) the committed files are listed under the line, at most 20
    def test_committed_file_names_listed(self):
        self.write(self.sub, "b.txt")
        self.write(self.sub, os.path.join("dir", "c.txt"))
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        lines = out.splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("sub "))
        self.assertEqual(lines[i + 1:i + 3], ["    b.txt", "    dir/c.txt"])

    def test_committed_file_names_capped(self):
        for n in range(25):
            self.write(self.sub, "f%02d.txt" % n)
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertIn("    f19.txt\n    +5 more", out)
        self.assertNotIn("f20.txt", out)

    # (d) a dirty repo on a foreign branch is refused without switching
    def test_dirty_repo_on_foreign_branch_refused_without_switching(self):
        run(self.sub, "switch", "-q", "-c", "feature-x")
        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertRegex(out, r"(?m)^sub .*REFUSED: .*feature-x")
        self.assertEqual(ship.current(self.sub), "feature-x")
        self.assertIn("?? b.txt", run(self.sub, "status", "--porcelain"))
        self.assertEqual(run(self.sub, "branch", "--list", self.branch()), "")
        self.assertIn("pushed", out)  # the other repo still went through

    def test_dirty_repo_on_another_tickets_branch_notes_it(self):
        old = self.branch(ticket="T-0058")
        run(self.sub, "switch", "-q", "-c", old)
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertIn("sub is on %s (another ticket's branch); its leftover changes are committed under T-0059"
                      % old, out + err)
        self.assertEqual(ship.current(self.sub), self.branch())
        self.assertEqual(self.files(self.sub), ["b.txt"])

    # (e) where a refused repo was left
    def test_gate_refusal_after_switch_says_where_it_left_the_repo(self):
        self.author_home(self.sub)
        self.write(self.sub, "b.txt")
        self.env("STUB_FINDINGS", json.dumps({"k1": "missing label foo"}))
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertIn("left on %s, changes uncommitted" % self.branch("author"), out)
        self.assertEqual(ship.current(self.sub), self.branch("author"))

    def test_commit_failure_after_switch_says_changes_staged(self):
        hook = os.path.join(self.sub, ".git", "hooks", "pre-commit")
        with open(hook, "w", encoding="utf-8", newline="\n") as f:
            f.write("#!/bin/sh\necho no commits today >&2\nexit 1\n")
        os.chmod(hook, 0o755)
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 1)
        self.assertIn("left on %s, changes staged" % self.branch(), out)
        self.assertIn("A  b.txt", run(self.sub, "status", "--porcelain"))

    # I2: 'unavailable' is reported and the checkpoint goes on
    def test_gate_unavailable_reported_and_committed(self):
        self.author_home(self.sub)
        self.write(self.sub, "b.txt")
        self.env("STUB_MODE", "unavailable")
        self.env("STUB_CAUSE", "checker could not run: boom")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertIn("ship: gate unavailable: checker could not run: boom", err)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + self.branch("author")),
                         run(self.sub, "rev-parse", "HEAD"))


class TestCheckpointBoardDir(CheckpointBase):
    """The board as a plain directory of the superproject (the folded layout): the target
    ``board`` is the workspace repo itself limited to ``board/``. Only ``board/`` paths are
    staged and committed; whatever else is dirty or staged in the superproject -- another
    directory, a moved or staged submodule pointer -- is left exactly as it was."""

    def setUp(self):
        super().setUp()
        self.root_remote = os.path.join(self._tmp.name, "root-remote.git")
        run(self._tmp.name, "init", "-q", "--bare", "-b", "main", self.root_remote)
        run(self.root, "remote", "add", "origin", self.root_remote)
        self.write(self.root, os.path.join("board", "README.md"), "board\n")
        self.write(self.root, os.path.join("docs", "d.md"), "d\n")
        self.write(self.root, ".gitignore", "workspace.json\n")
        run(self.root, "add", ".gitignore", ".gitmodules", "board", "docs", "sub", "other")
        run(self.root, "commit", "-q", "-m", "init")
        run(self.root, "push", "-q", "-u", "origin", "main")
        self.workspace({"path": "board", "backend": "github", "repo": "o/r"})

    def workspace(self, board):
        with open(os.path.join(self.root, "workspace.json"), "w", encoding="utf-8") as f:
            json.dump({"instances": {}, "board": board}, f)

    def on_template(self):
        run(self.root, "switch", "-q", "-c", ship.branch_name("board-work", "human"))

    def drift_pointer(self):
        """Move 'sub' on its main (unstaged pointer drift in the superproject) and stage a
        move of 'other' (a staged pointer)."""
        for repo in (self.sub, self.other):
            self.write(repo, "moved.txt")
            run(repo, "add", "moved.txt")
            run(repo, "commit", "-q", "-m", "moved")
        run(self.root, "add", "other")

    def run_ship(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ship.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_board_is_a_superproject_target(self):
        self.assertEqual(ship.root_dirs(), {"board": "board"})
        self.assertEqual(ship.targets(), ["sub", "other", "board"])
        self.assertEqual(ship.repo_of("board"), self.root)
        self.workspace("board")                                    # a plain path form
        self.assertEqual(ship.root_dirs(), {"board": "board"})
        os.remove(os.path.join(self.root, "workspace.json"))       # the default
        self.assertEqual(ship.root_dirs(), {"board": "board"})

    def test_status_lists_board(self):
        self.write(self.root, os.path.join("board", "p.md"))
        self.write(self.root, os.path.join("docs", "d.md"), "changed\n")
        rc, out, err = self.run_ship("status")
        self.assertEqual(rc, 0, err)
        line = [l for l in out.splitlines() if l.startswith("board ")]
        self.assertEqual(len(line), 1, out)
        self.assertIn("superproject, board/ only", line[0])
        self.assertIn("dirty=0", line[0])        # untracked p.md; docs/ is not board's

    def test_only_board_commits_only_board_paths_and_no_gitlink(self):
        self.on_template()
        self.drift_pointer()
        self.write(self.root, os.path.join("board", "packets", "P-1.md"))
        self.write(self.root, os.path.join("board", "README.md"), "changed\n")
        self.write(self.root, os.path.join("docs", "d.md"), "dirty outside\n")
        self.write(self.root, os.path.join("docs", "staged.md"))
        run(self.root, "add", os.path.join("docs", "staged.md"))
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "board")
        self.assertEqual(rc, 0, err)
        name = self.branch()
        self.assertEqual(ship.current(self.root), name)
        self.assertEqual(self.files(self.root), ["board/README.md", "board/packets/P-1.md"])
        self.assertEqual(run(self.root_remote, "rev-parse", "refs/heads/" + name),
                         run(self.root, "rev-parse", "HEAD"))
        self.assertEqual(run(self.root, "log", "-1", "--format=%B"),
                         "T-0059: checkpoint\n\nTicket: o/r#59")
        # everything outside board/ is as it was: the pointers, the staged file, the dirt
        self.assertEqual(sorted(run(self.root, "diff", "--cached", "--name-only").splitlines()),
                         ["docs/staged.md", "other"])
        self.assertEqual(sorted(run(self.root, "diff", "--name-only").splitlines()),
                         ["docs/d.md", "sub"])
        self.assertEqual(run(self.root_remote, "rev-parse", "main"),
                         run(self.root, "rev-parse", "main"))
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])  # sub untouched
        self.assertEqual([l.split()[0] for l in out.splitlines() if not l.startswith(" ")], ["board"])

    def test_only_board_with_nothing_under_board_is_unchanged(self):
        self.on_template()
        self.drift_pointer()
        self.write(self.root, os.path.join("docs", "d.md"), "dirty outside\n")
        before = run(self.root, "rev-parse", "HEAD")
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "board")
        self.assertEqual(rc, 0, err)
        self.assertIn("unchanged", out)
        self.assertEqual(run(self.root, "rev-parse", "HEAD"), before)
        self.assertNotEqual(ship.current(self.root), self.branch())     # not even switched

    def test_a_nested_repository_under_board_is_skipped(self):
        self.on_template()
        nested = os.path.join(self.root, "board", "nested")
        run(self.root, "init", "-q", "-b", "main", nested)
        from ship_fixture import configure
        configure(nested)
        self.write(nested, "n.txt")
        run(nested, "add", "n.txt")
        run(nested, "commit", "-q", "-m", "n")
        self.write(self.root, os.path.join("board", "p.md"))
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "board")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.files(self.root), ["board/p.md"])
        self.assertIn("skipped nested repo: board/nested/", out)
        self.assertEqual(run(self.root, "diff", "--cached", "--name-only"), "")

    def test_only_board_dirty_on_main_is_refused(self):
        self.write(self.root, os.path.join("board", "p.md"))
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "board")
        self.assertEqual(rc, 1)
        self.assertIn("REFUSED: dirty on main", out)
        self.assertIn("py scripts/ship.py start board <topic>", out)
        self.assertEqual(ship.current(self.root), "main")
        self.assertEqual(self.remote_branches(self.root_remote), ["refs/heads/main"])

    def test_superproject_on_an_off_template_branch_is_refused(self):
        run(self.root, "switch", "-q", "-c", "feature")
        self.write(self.root, os.path.join("board", "p.md"))
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "board")
        self.assertEqual(rc, 1)
        self.assertIn("neither main/master nor a <date>/<topic>/<role> branch", out)
        self.assertEqual(ship.current(self.root), "feature")

    def test_manual_run_covers_board_and_the_submodules(self):
        self.drift_pointer()
        self.write(self.sub, "b.txt")
        self.write(self.root, os.path.join("board", "p.md"))
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        name = self.branch()
        self.assertEqual(self.files(self.root), ["board/p.md"])
        self.assertEqual(self.files(self.sub), ["b.txt"])
        for repo, remote in ((self.root, self.root_remote), (self.sub, self.remote)):
            self.assertEqual(run(remote, "rev-parse", "refs/heads/" + name),
                             run(repo, "rev-parse", "HEAD"))
        self.assertIn("other", run(self.root, "diff", "--cached", "--name-only"))

    def test_commit_and_ship_board(self):
        self.on_template()
        self.drift_pointer()
        self.write(self.root, os.path.join("board", "p.md"))
        self.write(self.root, os.path.join("board", "q.md"))
        self.write(self.root, os.path.join("docs", "d.md"), "dirty outside\n")
        rc, out, err = self.run_ship("commit", "board", "-m", "one", "--paths", "p.md")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.files(self.root), ["board/p.md"])
        rc, out, err = self.run_ship("commit", "board", "-m", "out", "--paths", "../docs/d.md")
        self.assertEqual(rc, 1)
        self.assertIn("outside", err)
        rc, out, err = self.run_ship("ship", "board", "-m", "rest", "--all")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.files(self.root), ["board/q.md"])
        b = ship.current(self.root)
        self.assertEqual(run(self.root_remote, "rev-parse", "refs/heads/" + b),
                         run(self.root, "rev-parse", "HEAD"))
        self.assertEqual(sorted(run(self.root, "diff", "--cached", "--name-only").splitlines()),
                         ["other"])
        self.assertIn("docs/d.md", run(self.root, "diff", "--name-only"))

    def test_start_board_branches_the_superproject(self):
        rc, out, err = self.run_ship("start", "board", "notes")
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.root), ship.branch_name("notes", "human"))

    def test_a_board_that_is_its_own_repository_is_no_superproject_target(self):
        run(self.root, "init", "-q", os.path.join(self.root, "board"))
        self.assertEqual(ship.root_dirs(), {})
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "board")
        self.assertEqual(rc, 1)
        self.assertIn("--only board", err)


class TestCheckpointBoardSubmodule(CheckpointBase):
    """The older layout, board as a submodule: ``board.backend`` in workspace.json does not
    change the scope: with ``github`` the tickets live on GitHub, but packets, deep-dives
    and renders are still files in the ``board`` repo, so checkpoint commits it like any
    repo whatever the backend."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        add_submodule(cls._tpl.name, os.path.join(cls._tpl.name, "root"), "board")

    def setUp(self):
        super().setUp()
        self.board = os.path.join(self.root, "board")
        self.board_remote = os.path.join(self._tmp.name, "board-remote.git")
        run(self.board, "remote", "set-url", "origin", self.board_remote)
        with open(os.path.join(self.root, ".gitmodules"), "a", encoding="utf-8") as f:
            f.write('[submodule "board"]\n\tpath = board\n\turl = %s\n'
                    % self.board_remote.replace("\\", "/"))
        for repo in (self.sub, self.other, self.board):
            self.write(repo, "b.txt")

    def workspace(self, board):
        with open(os.path.join(self.root, "workspace.json"), "w", encoding="utf-8") as f:
            json.dump({"instances": {}, "board": board}, f)

    def assert_all_pushed(self):
        name = self.branch()
        for repo, remote in ((self.sub, self.remote), (self.other, self.other_remote),
                             (self.board, self.board_remote)):
            self.assertEqual(run(remote, "rev-parse", "refs/heads/" + name),
                             run(repo, "rev-parse", "HEAD"))
            self.assertEqual(run(repo, "status", "--porcelain"), "")

    def checkpoint_ok(self):
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertNotIn("skipped", out)
        self.assert_all_pushed()

    def test_github_backend_still_checkpoints_board(self):
        self.workspace({"path": "board", "backend": "github", "repo": "o/r"})
        self.checkpoint_ok()

    def test_files_backend_checkpoints_board(self):
        self.workspace({"path": "board", "backend": "files"})
        self.checkpoint_ok()

    def test_board_as_plain_path_checkpoints_board(self):
        self.workspace("board")
        self.checkpoint_ok()

    def test_github_backend_links_the_commit_to_the_ticket_issue(self):
        # the commit then shows on the ticket's issue, whichever repo it lands in
        self.workspace({"path": "board", "backend": "github", "repo": "o/r"})
        rc, _, err = self.cp("--ticket", "T-0059", "--title", "prove lemma 3")
        self.assertEqual(rc, 0, err)
        for repo in (self.sub, self.board):
            self.assertEqual(run(repo, "log", "-1", "--format=%B"),
                             "T-0059: prove lemma 3\n\nTicket: o/r#59")

    def test_files_backend_adds_no_ticket_link(self):
        self.workspace({"path": "board", "backend": "files"})
        rc, _, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.sub, "log", "-1", "--format=%B"), "T-0059: checkpoint")

    def test_ticket_ref(self):
        self.workspace({"path": "board", "backend": "github", "repo": "o/r"})
        self.assertEqual("o/r#59", ship.ticket_ref("T-0059"))
        self.assertEqual("o/r#59", ship.ticket_ref("2026-10-03/t-0059/expert"))
        self.assertIsNone(ship.ticket_ref("2026-10-03/board-cutover/expert"))
        self.workspace("board")
        self.assertIsNone(ship.ticket_ref("T-0059"))

    def test_commit_messages_get_the_ticket_line_before_their_body(self):
        self.workspace({"path": "board", "backend": "github", "repo": "o/r"})
        br = "2026-10-03/t-0059/expert"
        self.assertEqual("x: y\n\nTicket: o/r#59", ship.with_ticket_ref("x: y", br))
        self.assertEqual("x\n\nTicket: o/r#59\n\nbody", ship.with_ticket_ref("x\n\nbody", br))
        once = ship.with_ticket_ref("x", br)
        self.assertEqual(once, ship.with_ticket_ref(once, br))
        self.assertEqual("x", ship.with_ticket_ref("x", "2026-10-03/cutover/expert"))

    def test_workspace_json_missing_checkpoints_board(self):
        self.assertFalse(os.path.exists(os.path.join(self.root, "workspace.json")))
        self.checkpoint_ok()

    def test_board_key_missing_checkpoints_board(self):
        with open(os.path.join(self.root, "workspace.json"), "w", encoding="utf-8") as f:
            json.dump({"instances": {}}, f)
        self.checkpoint_ok()


class TestCheckpointOnly(CheckpointBase):
    """``--only SUB...``: the automatic (inbox hook) run, scoped to the ticket's repos."""

    def test_only_unknown_name_refused_before_anything(self):
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "sub", "nope")
        self.assertEqual(rc, 1)
        self.assertIn("nope", err)
        self.assertEqual(ship.current(self.sub), "main")
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])

    def test_only_leaves_other_dirty_repos_untouched(self):
        name = self.branch()
        run(self.sub, "switch", "-q", "-c", name)
        self.write(self.sub, "b.txt")
        self.write(self.other, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "sub")
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name),
                         run(self.sub, "rev-parse", "HEAD"))
        self.assertNotIn("other", [l.split()[0] for l in out.splitlines() if l.strip()])
        self.assertEqual(ship.current(self.other), "main")
        self.assertEqual(run(self.other, "status", "--porcelain"), "?? b.txt")
        self.assertEqual(self.remote_branches(self.other_remote), ["refs/heads/main"])

    def test_only_refuses_a_dirty_repo_on_main_in_the_set(self):
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "sub")
        self.assertEqual(rc, 1)
        self.assertIn("REFUSED: dirty on main; move your work to a template branch first", out)
        self.assertIn("py scripts/ship.py start sub <topic>", out)
        self.assertEqual(ship.current(self.sub), "main")
        self.assertEqual(run(self.sub, "status", "--porcelain"), "?? b.txt")
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/main"])
        self.assert_main_untouched()

    def test_manual_run_still_moves_a_dirty_repo_on_main(self):
        self.write(self.sub, "b.txt")
        rc, out, err = self.cp("--ticket", "T-0059")
        self.assertEqual(rc, 0, err)
        self.assertEqual(ship.current(self.sub), self.branch())
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + self.branch()),
                         run(self.sub, "rev-parse", "HEAD"))

    def test_submodule_pointers_are_never_staged(self):
        # the superproject records both submodules; a nested repo inside 'sub' is a tracked
        # gitlink there; both pointers then move
        run(self.root, "add", "sub", "other")
        run(self.root, "commit", "-q", "-m", "pins")
        root_head = run(self.root, "rev-parse", "HEAD")
        nested = self.nested_repo("nested")
        run(self.sub, "switch", "-q", "-c", self.branch())
        run(self.sub, "add", "nested")
        run(self.sub, "commit", "-q", "-m", "nested pin")
        self.write(nested, "n.txt", "n2\n")
        run(nested, "commit", "-q", "-am", "n2")             # the nested pointer moves
        for new, argv in (("b.txt", ("--only", "sub")), ("c.txt", ())):   # automatic, manual
            self.write(self.sub, new)
            rc, out, err = self.cp("--ticket", "T-0059", *argv)
            self.assertEqual(rc, 0, err)
            self.assertEqual(self.files(self.sub), [new], argv)
            self.assertEqual(run(self.sub, "diff", "--name-only"), "nested")   # still moved,
            self.assertEqual(run(self.sub, "diff", "--cached", "--name-only"), "")  # unstaged
            self.assertEqual(run(self.root, "rev-parse", "HEAD"), root_head)
            self.assertEqual(run(self.root, "diff", "--cached", "--name-only"), "")

    def nested_repo(self, name):
        from ship_fixture import configure
        path = os.path.join(self.sub, name)
        run(self.sub, "init", "-q", "-b", "main", path)
        configure(path)
        self.write(path, "n.txt")
        run(path, "add", "n.txt")
        run(path, "commit", "-q", "-m", "n1")
        return path

    def test_already_staged_pointers_are_not_committed(self):
        nested = self.nested_repo("nested")
        name = self.branch()
        run(self.sub, "switch", "-q", "-c", name)
        run(self.sub, "add", "nested")
        run(self.sub, "commit", "-q", "-m", "nested pin")
        self.write(nested, "n.txt", "n2\n")
        run(nested, "commit", "-q", "-am", "n2")
        run(self.sub, "add", "nested")                     # a moved pointer, staged (M)
        self.nested_repo("fresh")
        run(self.sub, "add", "fresh")                      # a new pointer, staged (A)
        self.write(self.sub, "b.txt")
        run(self.sub, "add", "b.txt")
        self.write(self.sub, "c.txt")
        rc, out, err = self.cp("--ticket", "T-0059", "--only", "sub")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.files(self.sub), ["b.txt", "c.txt"])
        self.assertEqual(run(self.sub, "diff", "--cached", "--name-only"), "")
        self.assertEqual(run(self.sub, "diff", "--name-only"), "nested")
        self.assertIn("fresh", run(self.sub, "status", "--porcelain"))
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name),
                         run(self.sub, "rev-parse", "HEAD"))


if __name__ == "__main__":
    unittest.main()
