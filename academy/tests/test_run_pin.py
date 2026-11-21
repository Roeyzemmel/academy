"""run_pin.py: a workflow run reads its code from a worktree pinned at the commit HEAD
pointed to when it started (#97).

A merge, a branch switch or a publish during an inbox run changed the scripts it called
half-way. ``start`` pins the checkout's HEAD in ``.worktrees/run-<sha12>`` (reused for the
same commit) and writes a live marker; ``end`` removes it; ``live`` lists the live runs (a
marker too old, or naming a process of this host that is gone, is stale); ``clean`` removes
the pins no live run uses and nothing used for ``keep_days``. A directory that is no git
checkout is left as it is. The checkout stays clean (``.worktrees/`` ignores itself).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import run_pin  # noqa: E402
from ship_fixture import configure, run  # noqa: E402

DAY = 86400.0


def dead(_pid, _start=None):
    return False


def alive(_pid, _start=None):
    return True


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="run-pin-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "academy")
        os.makedirs(self.repo)
        run(self.repo, "init", "-q", "-b", "main")
        configure(self.repo)
        self.commit("a.txt", "one\n")

    def commit(self, name, text):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        run(self.repo, "add", name)
        run(self.repo, "commit", "-q", "-m", "c " + name)
        return run(self.repo, "rev-parse", "HEAD")

    def head(self):
        return run(self.repo, "rev-parse", "HEAD")

    def worktrees(self):
        return [ln.split(" ", 1)[1] for ln in run(self.repo, "worktree", "list", "--porcelain").splitlines()
                if ln.startswith("worktree ")]


class TestStart(Base):
    def test_start_pins_head_in_a_detached_worktree(self):
        sha = self.head()
        r = run_pin.start(self.repo, "inbox-all", alive=alive)
        self.assertTrue(r["pinned"])
        self.assertEqual(sha, r["sha"])
        self.assertEqual(os.path.join(self.repo, ".worktrees", "run-" + sha[:12]), r["root"])
        self.assertEqual(sha, run(r["root"], "rev-parse", "HEAD"))
        self.assertEqual("", run(r["root"], "branch", "--show-current"))      # detached
        self.assertFalse(r["reused"])
        self.assertTrue(run_pin.is_pin_path(r["root"]))
        with open(os.path.join(r["root"], "a.txt"), encoding="utf-8") as fh:
            self.assertEqual("one\n", fh.read())

    def test_the_pin_does_not_move_with_the_checkout(self):
        r = run_pin.start(self.repo, "x", alive=alive)
        self.commit("a.txt", "two\n")                      # a merge, a branch switch
        with open(os.path.join(r["root"], "a.txt"), encoding="utf-8") as fh:
            self.assertEqual("one\n", fh.read())

    def test_a_second_run_at_the_same_commit_reuses_the_pin(self):
        a = run_pin.start(self.repo, "a", alive=alive)
        b = run_pin.start(self.repo, "b", alive=alive)
        self.assertEqual(a["root"], b["root"])
        self.assertTrue(b["reused"])
        self.assertNotEqual(a["run"], b["run"])
        self.assertEqual(2, len(self.worktrees()))

    def test_a_new_commit_gets_a_new_pin(self):
        a = run_pin.start(self.repo, "a", alive=alive)
        sha = self.commit("b.txt", "b\n")
        b = run_pin.start(self.repo, "b", alive=alive)
        self.assertNotEqual(a["root"], b["root"])
        self.assertEqual(sha, b["sha"])

    def test_the_checkout_stays_clean(self):
        run_pin.start(self.repo, "a", alive=alive)
        self.assertEqual("", run(self.repo, "status", "--porcelain"))

    def test_the_marker_names_the_run_sha_root_and_host(self):
        r = run_pin.start(self.repo, "inbox-author@t", now=1000.0, alive=alive)
        f = os.path.join(self.repo, ".worktrees", "live", r["run"] + ".json")
        with open(f, encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertEqual((r["sha"], r["root"], 1000.0, socket.gethostname()),
                         (m["sha"], m["root"], m["started"], m["host"]))
        self.assertTrue(r["run"].startswith("inbox-author@t-"), r["run"])

    def test_uncommitted_changes_are_counted_and_not_pinned(self):
        with open(os.path.join(self.repo, "a.txt"), "w", encoding="utf-8") as fh:
            fh.write("edited\n")
        r = run_pin.start(self.repo, "a", alive=alive)
        self.assertEqual(1, r["dirty"])
        self.assertIn("not in the pin", r["why"])
        with open(os.path.join(r["root"], "a.txt"), encoding="utf-8") as fh:
            self.assertEqual("one\n", fh.read())

    def test_from_a_linked_worktree_the_pin_goes_under_the_main_checkout(self):
        wt = os.path.join(self.repo, ".claude", "worktrees", "dev")
        run(self.repo, "worktree", "add", "-q", "-b", "dev", wt)
        with open(os.path.join(wt, "c.txt"), "w", encoding="utf-8") as fh:
            fh.write("c\n")
        run(wt, "add", "c.txt")
        run(wt, "commit", "-q", "-m", "dev work")
        r = run_pin.start(wt, "a", alive=alive)
        self.assertEqual(run(wt, "rev-parse", "HEAD"), r["sha"])     # that worktree's HEAD
        self.assertEqual(os.path.join(self.repo, ".worktrees"), os.path.dirname(r["root"]))

    def test_started_from_a_pin_it_is_that_pin(self):
        a = run_pin.start(self.repo, "a", alive=alive)
        b = run_pin.start(a["root"], "b", alive=alive)
        self.assertEqual(a["root"], b["root"])
        self.assertFalse(os.path.exists(os.path.join(a["root"], ".worktrees")))

    def test_a_directory_that_is_no_checkout_is_left_as_it_is(self):
        d = os.path.join(self.tmp, "cache", "0.2.10")
        os.makedirs(d)
        r = run_pin.start(d, "a")
        self.assertFalse(r["pinned"])
        self.assertEqual(d, r["root"])
        self.assertIsNone(r["sha"])
        self.assertEqual(["0.2.10"], os.listdir(os.path.dirname(d)))
        self.assertEqual([], os.listdir(d))

    def test_a_broken_pin_directory_is_replaced(self):
        sha = self.head()
        path = os.path.join(self.repo, ".worktrees", "run-" + sha[:12])
        os.makedirs(path)
        with open(os.path.join(path, "junk"), "w", encoding="utf-8") as fh:
            fh.write("x")
        r = run_pin.start(self.repo, "a", alive=alive)
        self.assertEqual(sha, run(r["root"], "rev-parse", "HEAD"))
        self.assertFalse(os.path.exists(os.path.join(path, "junk")))


class TestEndAndLive(Base):
    def test_end_removes_the_marker_and_keeps_the_pin(self):
        r = run_pin.start(self.repo, "a", alive=alive)
        self.assertEqual(1, len(run_pin.live(self.repo, alive=alive)))
        e = run_pin.end(self.repo, r["run"])
        self.assertTrue(e["ended"])
        self.assertEqual([], run_pin.live(self.repo, alive=alive))
        self.assertTrue(os.path.isdir(r["root"]))
        self.assertFalse(run_pin.end(self.repo, r["run"])["ended"])     # twice: nothing to end

    def test_end_refuses_a_run_id_that_is_no_file_name(self):
        with self.assertRaises(run_pin.PinError):
            run_pin.end(self.repo, "../x")

    def test_a_marker_older_than_the_limit_is_stale(self):
        r = run_pin.start(self.repo, "a", now=1000.0, alive=alive)
        later = 1000.0 + run_pin.RUN_MAX_HOURS * 3600 + 1
        self.assertEqual([], run_pin.live(self.repo, now=later, alive=alive))
        self.assertEqual([r["run"]], [m["run"] for m in run_pin.live(self.repo, now=1001.0, alive=alive)])

    def test_a_marker_whose_process_is_gone_is_stale(self):
        m = {"started": 1000.0, "host": socket.gethostname(), "pid": 4242, "pid_start": "7"}
        self.assertFalse(run_pin.marker_live(m, now=1001.0, alive=dead))
        self.assertTrue(run_pin.marker_live(m, now=1001.0, alive=alive))
        # another host's process cannot be checked here: the age alone decides
        self.assertTrue(run_pin.marker_live(dict(m, host="elsewhere"), now=1001.0, alive=dead))
        self.assertTrue(run_pin.marker_live(dict(m, pid=None), now=1001.0, alive=dead))
        self.assertFalse(run_pin.marker_live({"host": "x"}, now=1001.0))

    def test_the_session_pid_is_the_first_ancestor_that_is_no_shell(self):
        if not os.path.isdir("/proc"):
            self.skipTest("no /proc")
        here = run_pin._proc_stat(os.getpid())
        self.assertIsNotNone(here)
        p = subprocess.run([sys.executable, "-c",
                            "import sys; sys.path.insert(0, %r); import run_pin; print(run_pin.session_pid())"
                            % os.path.dirname(run_pin.__file__)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(0, p.returncode, p.stderr)
        # python -> this test process (python too, skipped) -> whatever ran the tests
        self.assertNotIn(str(os.getpid()) + ",", p.stdout.replace(" ", ""))

    def test_a_live_process_is_alive_and_a_reused_pid_is_not(self):
        if not os.path.isdir("/proc"):
            self.skipTest("no /proc")
        me = run_pin._proc_stat(os.getpid())
        self.assertTrue(run_pin.pid_alive(os.getpid(), me[2]))
        self.assertFalse(run_pin.pid_alive(os.getpid(), "not-" + str(me[2])))
        self.assertFalse(run_pin.pid_alive(2 ** 22 + 12345))

    def test_the_command_line_start_live_end(self):
        script = os.path.join(os.path.dirname(HERE), "scripts", "run_pin.py")

        def cli(*a):
            p = subprocess.run([sys.executable, script, "--repo", self.repo] + list(a),
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(0, p.returncode, p.stderr)
            return p.stdout
        r = json.loads(cli("start", "--label", "inbox-all", "--json"))
        self.assertTrue(r["pinned"])
        self.assertIn(r["run"], cli("live"))
        self.assertEqual(True, json.loads(cli("end", "--run", r["run"], "--json"))["ended"])
        self.assertEqual("no live run\n", cli("live"))


class TestClean(Base):
    def pin_at(self, now, label="a"):
        self.commit("n%s.txt" % label, label)
        return run_pin.start(self.repo, label, now=now, alive=alive)

    def test_an_unused_old_pin_is_removed_at_the_next_start(self):
        old = self.pin_at(1000.0, "a")
        run_pin.end(self.repo, old["run"], now=1000.0)
        new = self.pin_at(1000.0 + 3 * DAY, "b")
        self.assertEqual([os.path.basename(old["root"])], new["cleaned"])
        self.assertFalse(os.path.exists(old["root"]))
        self.assertEqual(2, len(self.worktrees()))                     # main + the new pin

    def test_a_recently_used_pin_is_kept_for_a_hand_back(self):
        old = self.pin_at(1000.0, "a")
        run_pin.end(self.repo, old["run"], now=1000.0 + DAY)
        new = self.pin_at(1000.0 + 2.5 * DAY, "b")                     # 1.5 days after its end
        self.assertEqual([], new["cleaned"])
        self.assertTrue(os.path.isdir(old["root"]))

    def test_a_pin_a_live_run_uses_is_kept_however_old(self):
        old = self.pin_at(1000.0, "a")                                 # never ended
        gone = run_pin.clean(self.repo, now=1000.0 + 5 * 3600, keep_days=0.0, alive=alive)
        self.assertEqual([], gone)
        self.assertTrue(os.path.isdir(old["root"]))

    def test_a_pin_whose_only_run_is_stale_is_removed(self):
        old = self.pin_at(1000.0, "a")                                 # crashed: never ended
        later = 1000.0 + run_pin.RUN_MAX_HOURS * 3600 + 3 * DAY
        self.assertEqual([os.path.basename(old["root"])], run_pin.clean(self.repo, now=later, alive=alive))
        self.assertEqual([], os.listdir(os.path.join(self.repo, ".worktrees", "live")))

    def test_the_pin_being_started_is_never_removed(self):
        a = run_pin.start(self.repo, "a", now=1000.0, alive=alive)
        run_pin.end(self.repo, a["run"], now=1000.0)
        b = run_pin.start(self.repo, "b", now=1000.0 + 9 * DAY, alive=alive)
        self.assertEqual(a["root"], b["root"])
        self.assertEqual([], b["cleaned"])
        self.assertTrue(os.path.isdir(b["root"]))


class TestLibraryRoot(Base):
    """A script run from a pin reads the pin's library and plugins, whatever
    ``$ACADEMY_ROOT`` says, and still finds the workspace beside the main checkout."""

    def test_repo_root_of_a_pinned_library_is_the_pin(self):
        src = os.path.join(os.path.dirname(HERE), "lib", "academy_common")
        pin = os.path.join(self.repo, ".worktrees", "run-" + "a" * 12)
        shutil.copytree(src, os.path.join(pin, "academy", "lib", "academy_common"))
        with open(os.path.join(self.tmp, "workspace.json"), "w", encoding="utf-8") as fh:
            json.dump({"instances": {}, "board": "board"}, fh)
        code = ("import sys, json; sys.path.insert(0, %r); import academy_common as ac; "
                "print(json.dumps([ac.repo_root(), ac.run_pin_source()]))"
                % os.path.join(pin, "academy", "lib"))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ACADEMY_")}
        env["ACADEMY_WORKSPACE_TAG"] = "no-such-tag"                    # no machine-wide workspace
        env["ACADEMY_ROOT"] = self.repo                                 # the live checkout
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           timeout=30, env=env, cwd=self.tmp)
        self.assertEqual(0, p.returncode, p.stderr)
        root, source = json.loads(p.stdout)
        self.assertEqual(os.path.realpath(pin), os.path.realpath(root))
        self.assertEqual(os.path.realpath(self.repo), os.path.realpath(source))
        code2 = ("import sys; sys.path.insert(0, %r); import academy_common as ac; "
                 "print(ac.load_workspace()['board'])" % os.path.join(pin, "academy", "lib"))
        env.pop("ACADEMY_ROOT")
        p = subprocess.run([sys.executable, "-c", code2], capture_output=True, text=True,
                           timeout=30, env=env, cwd=self.tmp)
        self.assertEqual(0, p.returncode, p.stderr)
        self.assertEqual("board", p.stdout.strip())

    def test_the_library_and_the_script_agree_on_what_a_pin_is(self):
        import academy_common as ac
        for p, want in ((os.path.join("x", ".worktrees", "run-" + "0" * 12), True),
                        (os.path.join("x", ".worktrees", "run-abc"), False),
                        (os.path.join("x", ".claude", "worktrees", "run-" + "0" * 12), False),
                        (os.path.join("x", ".worktrees", "dev"), False)):
            self.assertEqual(want, run_pin.is_pin_path(p), p)
            self.assertEqual(want, ac.is_run_pin(p), p)


if __name__ == "__main__":
    unittest.main()
