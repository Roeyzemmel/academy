"""``ship.py status`` lists the worktrees that hold work not on a remote (#101).

On 2026-11-20 three developer runs left uncommitted work in academy/.claude/worktrees/*
and nothing reported it; ten branches had commits only in the container. ``status`` now
names, per repo (each submodule and the superproject), every linked worktree with
uncommitted changes, commits on no remote branch, or a branch ahead of its upstream; a
clean, pushed one is shown only with ``--all``, as removable."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import ship  # noqa: E402
from ship_fixture import add_submodule, make_workspace, run  # noqa: E402


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

    def status(self, *extra):
        rc, out, err = self.ship("status", *extra)
        self.assertEqual(0, rc, err)
        return out

    def worktree(self, name, *add_args, repo=None):
        """A linked worktree of ``repo`` (default: the submodule) under its
        .claude/worktrees, on a new branch ``name`` unless ``add_args`` say otherwise."""
        repo = repo or self.sub
        wt = os.path.join(repo, ".claude", "worktrees", name)
        run(repo, "worktree", "add", "-q", *(add_args or ("-b", name)), wt)
        return wt

    def write(self, repo, name, text="x\n"):
        with open(os.path.join(repo, name), "w", encoding="utf-8") as f:
            f.write(text)

    def commit(self, repo, name="b.txt"):
        self.write(repo, name)
        run(repo, "add", name)
        run(repo, "commit", "-q", "-m", "work in " + name)

    def rows(self, out):
        """The lines of the worktree section (after its header)."""
        lines = out.splitlines()
        heads = [i for i, ln in enumerate(lines) if ln.startswith("worktrees ")]
        if not heads:
            return []
        return [ln for ln in lines[heads[0] + 1:] if ln.startswith("  ")]

    def row_for(self, out, path_tail):
        hits = [ln for ln in self.rows(out) if path_tail in ln]
        self.assertEqual(1, len(hits), out)
        return hits[0]


class TestListed(Base):
    def test_no_worktree_no_section(self):
        out = self.status()
        self.assertNotIn("worktrees ", out)

    def test_clean_pushed_worktree_not_listed(self):
        wt = self.worktree("clean")
        run(wt, "push", "-q", "-u", "origin", "clean")
        self.assertEqual([], self.rows(self.status()))

    def test_a_worktree_on_a_branch_at_a_pushed_commit_is_clean(self):
        """A new branch at main's pushed tip, never pushed itself: no commit is missing
        from the remote, so nothing is stranded."""
        self.worktree("fresh")
        self.assertEqual([], self.rows(self.status()))

    def test_uncommitted_changes_listed_with_count(self):
        wt = self.worktree("dirty")
        self.write(wt, "a.txt", "changed\n")            # tracked, modified
        self.write(wt, "new1.txt")                      # untracked: new work counts too
        self.write(wt, "new2.txt")
        row = self.row_for(self.status(), os.path.join(".claude", "worktrees", "dirty"))
        self.assertIn("sub", row.split()[0])
        self.assertIn("dirty", row.split())             # the branch
        self.assertIn("dirty=3", row)
        self.assertIn("unpushed=0", row)

    def test_unpushed_commit_listed(self):
        wt = self.worktree("ahead")
        self.commit(wt)
        self.commit(wt, "c.txt")
        row = self.row_for(self.status(), os.path.join(".claude", "worktrees", "ahead"))
        self.assertIn("dirty=0", row)
        self.assertIn("unpushed=2", row)

    def test_branch_ahead_of_upstream_listed_even_if_commits_on_another_remote_branch(self):
        wt = self.worktree("tracked")
        run(wt, "push", "-q", "-u", "origin", "tracked")
        self.commit(wt)
        run(wt, "push", "-q", "origin", "HEAD:refs/heads/copy")   # on a remote, not upstream
        row = self.row_for(self.status(), os.path.join(".claude", "worktrees", "tracked"))
        self.assertIn("unpushed=0", row)
        self.assertIn("ahead=1", row)

    def test_detached_worktree_with_local_commit_listed(self):
        wt = self.worktree("det", "--detach")
        self.commit(wt)
        row = self.row_for(self.status(), os.path.join(".claude", "worktrees", "det"))
        self.assertIn("(detached)", row)
        self.assertIn("unpushed=1", row)

    def test_worktree_outside_the_checkout_shown_by_absolute_path(self):
        far = tempfile.mkdtemp(prefix="ship-far-")
        self.addCleanup(shutil.rmtree, far, True)
        wt = os.path.join(far, "wt")
        run(self.sub, "worktree", "add", "-q", "-b", "far", wt)
        self.commit(wt)
        row = self.row_for(self.status(), "wt")
        self.assertTrue(any(os.path.realpath(tok) == os.path.realpath(wt) for tok in row.split()), row)

    def test_main_checkout_is_not_in_the_section(self):
        self.write(self.sub, "a.txt", "changed\n")
        self.commit(self.sub, "local.txt")
        wt = self.worktree("other")
        self.write(wt, "z.txt")
        rows = self.rows(self.status())
        self.assertEqual(1, len(rows), rows)
        self.assertIn("other", rows[0])

    def test_missing_worktree_directory_with_unpushed_commits_listed(self):
        wt = self.worktree("gone")
        self.commit(wt)
        shutil.rmtree(wt)
        row = self.row_for(self.status(), os.path.join(".claude", "worktrees", "gone"))
        self.assertIn("unpushed=1", row)
        self.assertIn("missing", row)

    def test_superproject_worktree_listed(self):
        self.write(self.root, "README.md")
        run(self.root, "add", "README.md")
        run(self.root, "commit", "-q", "-m", "root init")
        wt = self.worktree("ws", repo=self.root)
        self.write(wt, "README.md", "edited\n")
        row = self.row_for(self.status(), os.path.join(".claude", "worktrees", "ws"))
        self.assertEqual("superproject", row.split()[0])
        self.assertIn("dirty=1", row)

    def test_every_submodule_is_scanned(self):
        other, _ = add_submodule(self._tmp.name, self.root, "other")
        wt = self.worktree("o", repo=other)
        self.commit(wt)
        row = self.row_for(self.status(), os.path.join(".claude", "worktrees", "o"))
        self.assertEqual("other", row.split()[0])

    def test_the_table_is_unchanged_above_the_section(self):
        before = self.status()
        wt = self.worktree("w")
        self.commit(wt)
        after = self.status()
        self.assertTrue(after.startswith(before), (before, after))


class TestAll(Base):
    def test_all_lists_clean_pushed_worktrees_as_removable(self):
        wt = self.worktree("clean")
        run(wt, "push", "-q", "-u", "origin", "clean")
        dirty = self.worktree("busy")
        self.write(dirty, "q.txt")
        out = self.status("--all")
        clean_row = self.row_for(out, os.path.join(".claude", "worktrees", "clean"))
        self.assertIn("removable", clean_row)
        busy_row = self.row_for(out, os.path.join(".claude", "worktrees", "busy"))
        self.assertNotIn("removable", busy_row)

    def test_all_lists_a_missing_clean_worktree_as_prunable(self):
        wt = self.worktree("vanished")
        shutil.rmtree(wt)
        self.assertEqual([], self.rows(self.status()))
        row = self.row_for(self.status("--all"), os.path.join(".claude", "worktrees", "vanished"))
        self.assertIn("missing", row)
        self.assertIn("removable", row)


class TestNoLocks(Base):
    def test_status_does_not_rewrite_a_worktree_index(self):
        """Another agent may be committing in the worktree: a scan that refreshed the
        index on disk (what a plain ``git status`` does after a stat-only change) would
        take its lock and race that commit. The scan reads with --no-optional-locks."""
        wt = self.worktree("busy")
        self.write(wt, "z.txt")                                   # listed: has work
        past = 1_000_000_000
        os.utime(os.path.join(wt, "a.txt"), (past, past))         # stat changed, content not
        index = os.path.join(run(wt, "rev-parse", "--absolute-git-dir"), "index")
        with open(index, "rb") as f:
            before = f.read()
        self.row_for(self.status(), os.path.join(".claude", "worktrees", "busy"))
        with open(index, "rb") as f:
            self.assertEqual(before, f.read())
        run(wt, "status", "--porcelain")                          # the control: git would
        with open(index, "rb") as f:
            self.assertNotEqual(before, f.read())


if __name__ == "__main__":
    unittest.main()
