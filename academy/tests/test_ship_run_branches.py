"""ship.py checkpoint, one branch per run (#102): the tickets of one inbox run commit onto
``<date>/run-<run slug>/<role>`` in turn, each ticket's checkpoint its own commit with an
annotated tag ``ticket/<T-NNNN>/<n>``, pushed with the branch. Without a run the ticket's
own ``<date>/<ticket-id>/<role>`` branch, as before. Temp repos and bare remotes only."""
import contextlib
import io
import json
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import ship  # noqa: E402
from ship_fixture import run  # noqa: E402
import test_ship_checkpoint as tsc  # noqa: E402
from test_ship_checkpoint import CheckpointBase  # noqa: E402

RUN = "inbox-scientist@t-20261127T231500-ab12"
RUN_BRANCH = "2026-11-27/run-inbox-scientist-t-20261127t231500-ab12/human"


class RunBranchNameTests(CheckpointBase):
    def test_the_run_id_gives_slug_and_start_date(self):
        self.assertEqual(ship.run_branch_name(RUN, "human"), RUN_BRANCH)
        self.assertTrue(ship.BRANCH.match(RUN_BRANCH))
        # past midnight: the run's start date (from its id), not today's
        self.assertEqual(ship.run_date(RUN), "2026-11-27")
        self.assertEqual(ship.run_branch_name("inbox-A+B.c-20261231T235959-0f0f", "expert"),
                         "2026-12-31/run-inbox-a-b-c-20261231t235959-0f0f/expert")

    def test_without_a_stamp_the_leases_started_else_today(self):
        tsc.TestCheckpointLeases.lease(self, "sub", "inbox-mine", heartbeat=time.time())
        path = os.path.join(self.root, ".academy", "leases", "sub.json")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        doc["started"] = 1795000000.0                   # 2026-11-18 UTC
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        self.assertEqual(ship.run_date("inbox-mine"), "2026-11-18")
        today = ship.datetime.datetime.now(ship.datetime.timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(ship.run_date("inbox-unleased"), today)

    def test_a_bad_role_or_an_empty_run_is_refused(self):
        with self.assertRaises(ship.Refuse):
            ship.run_branch_name(RUN, "wizard")
        rc, out, err = self.cp("--ticket", "T-0001", "--run", "@@@")
        self.assertEqual(rc, 1)
        self.assertIn("no usable characters", err)


class RunBranchCheckpointTests(CheckpointBase):
    def tags(self, repo, ticket=""):
        return run(repo, "tag", "-l", "ticket/%s*" % ticket).splitlines()

    def test_two_tickets_of_one_run_land_on_one_branch_one_commit_and_tag_each(self):
        self.write(self.sub, "one.txt")
        rc, out, err = self.cp("--ticket", "T-0001", "--title", "first", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(ship.current(self.sub), RUN_BRANCH)
        self.write(self.sub, "two.txt")
        rc, out, err = self.cp("--ticket", "T-0002", "--title", "second", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(ship.current(self.sub), RUN_BRANCH)
        log = run(self.sub, "log", "--format=%s", "main.." + RUN_BRANCH).splitlines()
        self.assertEqual(log, ["T-0002: second", "T-0001: first"])
        self.assertEqual(self.tags(self.sub), ["ticket/T-0001/1", "ticket/T-0002/1"])
        self.assertEqual(run(self.sub, "rev-parse", "ticket/T-0001/1^{commit}"),
                         run(self.sub, "rev-parse", RUN_BRANCH + "~1"))
        self.assertEqual(run(self.sub, "rev-parse", "ticket/T-0002/1^{commit}"),
                         run(self.sub, "rev-parse", RUN_BRANCH))
        self.assertEqual(run(self.sub, "cat-file", "-t", "ticket/T-0001/1"), "tag")   # annotated
        self.assertIn("T-0001: first", run(self.sub, "tag", "-l", "-n9", "ticket/T-0001/1"))
        # pushed with the branch, tags included; the other repo is untouched; no ticket branch
        self.assertEqual(self.remote_branches(self.remote), ["refs/heads/" + RUN_BRANCH, "refs/heads/main"])
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + RUN_BRANCH),
                         run(self.sub, "rev-parse", RUN_BRANCH))
        self.assertEqual(run(self.remote, "tag", "-l").splitlines(), ["ticket/T-0001/1", "ticket/T-0002/1"])
        self.assertEqual(self.tags(self.other), [])
        self.assertIn("tag ticket/T-0002/1", out)
        self.assert_main_untouched()

    def test_a_second_checkpoint_of_a_ticket_gets_tag_2(self):
        self.write(self.sub, "half.txt")
        rc, out, err = self.cp("--ticket", "T-0001", "--wip", "blocked", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.write(self.sub, "rest.txt")
        rc, out, err = self.cp("--ticket", "T-0001", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.tags(self.sub), ["ticket/T-0001/1", "ticket/T-0001/2"])
        self.assertEqual(run(self.sub, "log", "-1", "--format=%s", "ticket/T-0001/1"),
                         "WIP: T-0001 unfinished (blocked)")
        self.assertEqual(run(self.sub, "rev-parse", "ticket/T-0001/2^{commit}"),
                         run(self.sub, "rev-parse", RUN_BRANCH))
        # an unchanged third checkpoint makes no commit and no tag
        rc, out, err = self.cp("--ticket", "T-0001", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(len(self.tags(self.sub)), 2)

    def test_the_number_counts_the_remotes_tags_too(self):
        # another clone checkpointed the ticket and pushed its tag: this one is /2
        run(self.sub, "tag", "-a", "-m", "elsewhere", "ticket/T-0001/1", "main")
        run(self.sub, "push", "-q", "origin", "refs/tags/ticket/T-0001/1")
        run(self.sub, "tag", "-d", "ticket/T-0001/1")
        self.write(self.sub, "x.txt")
        rc, out, err = self.cp("--ticket", "T-0001", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.tags(self.sub), ["ticket/T-0001/2"])

    def test_without_a_run_the_tickets_own_branch_as_before_and_a_tag(self):
        self.write(self.sub, "one.txt")
        rc, out, err = self.cp("--ticket", "T-0001")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(ship.current(self.sub), self.branch(ticket="T-0001"))
        self.assertEqual(self.tags(self.sub), ["ticket/T-0001/1"])
        self.assertEqual(run(self.remote, "tag", "-l"), "ticket/T-0001/1")

    def test_a_topic_that_is_no_ticket_id_gets_no_tag(self):
        # a standalone skill run checkpoints its topic (--ticket campaign-x): no ticket tag
        self.write(self.sub, "c.txt")
        rc, out, err = self.cp("--ticket", "campaign-x")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(ship.current(self.sub), self.branch(ticket="campaign-x"))
        self.assertEqual(run(self.sub, "tag", "-l"), "")

    def test_the_manifests_run_names_the_branch(self):
        name = ship.run_branch_name(RUN, "expert")
        run(self.sub, "switch", "-q", "-c", name)
        self.write(self.sub, "m.txt")
        m = os.path.join(self._tmp.name, "m.json")
        with open(m, "w", encoding="utf-8") as f:
            json.dump({"run": RUN, "repos": {"sub": ["m.txt"]}}, f)
        rc, out, err = self.cp("--ticket", "T-0003", "--role", "expert", "--manifest", m)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + name),
                         run(self.sub, "rev-parse", "ticket/T-0003/1^{commit}"))

    def test_a_failed_push_is_retried_tags_included(self):
        url = run(self.sub, "remote", "get-url", "origin")
        run(self.sub, "remote", "set-url", "origin", os.path.join(self._tmp.name, "missing.git"))
        self.write(self.sub, "one.txt")
        rc, out, err = self.cp("--ticket", "T-0001", "--run", RUN)
        self.assertEqual(rc, 1)
        self.assertEqual(self.tags(self.sub), ["ticket/T-0001/1"])
        run(self.sub, "remote", "set-url", "origin", url)
        rc, out, err = self.cp("--ticket", "T-0001", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(run(self.remote, "tag", "-l"), "ticket/T-0001/1")
        self.assertEqual(run(self.remote, "rev-parse", "refs/heads/" + RUN_BRANCH),
                         run(self.sub, "rev-parse", RUN_BRANCH))
        self.assertEqual(self.tags(self.sub), ["ticket/T-0001/1"])      # no second tag

    def test_tickets_lists_the_tags_of_a_run_branch(self):
        for tid, name in (("T-0001", "one.txt"), ("T-0002", "two.txt"), ("T-0001", "three.txt")):
            self.write(self.sub, name)
            self.assertEqual(self.cp("--ticket", tid, "--title", name, "--run", RUN)[0], 0)
        run(self.sub, "switch", "-q", "main")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ship.main(["tickets", "sub", RUN_BRANCH])
        self.assertEqual(rc, 0)
        lines = out.getvalue().splitlines()
        self.assertIn("3 ticket commit(s)", lines[0])
        body = "\n".join(lines)
        for tag, subject in (("ticket/T-0001/1", "T-0001: one.txt"), ("ticket/T-0002/1", "T-0002: two.txt"),
                             ("ticket/T-0001/2", "T-0001: three.txt")):
            self.assertRegex(body, r"(?m)^\s*%s @ [0-9a-f]{7,}\s+%s" % (tag, subject))
        self.assertLess(body.index("ticket/T-0001/1"), body.index("ticket/T-0002/1"))
        self.assertLess(body.index("ticket/T-0002/1"), body.index("ticket/T-0001/2"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ship.main(["tickets", "sub", RUN_BRANCH, "--json"])
        rows = json.loads(out.getvalue())
        self.assertEqual([r["tag"] for r in rows], ["ticket/T-0001/1", "ticket/T-0002/1", "ticket/T-0001/2"])
        self.assertEqual(rows[1]["ticket"], "T-0002")
        self.assertEqual(rows[0]["files"], ["one.txt"])
        # the current branch by default
        run(self.sub, "switch", "-q", RUN_BRANCH)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ship.main(["tickets", "sub"])
        self.assertIn("ticket/T-0002/1", out.getvalue())

    def test_merge_forks_still_stacks_one_run_on_another(self):
        self.write(self.sub, "one.txt")
        self.assertEqual(self.cp("--ticket", "T-0001", "--run", RUN)[0], 0)
        first = run(self.sub, "rev-parse", RUN_BRANCH)
        run(self.sub, "switch", "-q", "main")
        later = "inbox-scientist@t-20261128T010000-cd34"
        name = ship.run_branch_name(later, "human")
        run(self.sub, "switch", "-q", "-c", name)
        self.write(self.sub, "two.txt")
        rc, out, err = self.cp("--ticket", "T-0002", "--only", "sub", "--run", later)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("merged %s" % RUN_BRANCH, out)
        self.assertTrue(ship._is_ancestor(self.sub, first, run(self.sub, "rev-parse", name)))
        # the tag is on the ticket's commit, not on the merge
        self.assertEqual(run(self.sub, "log", "-1", "--format=%s", "ticket/T-0002/1"),
                         "T-0002: checkpoint")

    def test_a_run_branch_merges_as_any_template_branch(self):
        self.write(self.sub, "one.txt")
        self.assertEqual(self.cp("--ticket", "T-0001", "--run", RUN)[0], 0)
        run(self.sub, "switch", "-q", "main")
        tip = run(self.sub, "rev-parse", RUN_BRANCH)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ship.main(["merge", "sub", RUN_BRANCH, "--sha", tip])
        self.assertEqual(rc, 0, out.getvalue() + err.getvalue())
        self.assertTrue(ship._is_ancestor(self.sub, tip, "main"))


class RunBranchBoardTests(CheckpointBase):
    """The board's plumbing path (#96) writes the run branch and its tags too (the board
    as a plain directory of the superproject, as in ``TestCheckpointBoardDir``)."""

    setUp = tsc.TestCheckpointBoardDir.setUp
    workspace = tsc.TestCheckpointBoardDir.workspace
    on_template = tsc.TestCheckpointBoardDir.on_template
    foreign_run = tsc.TestCheckpointBoardDir.foreign_run
    checkout_state = tsc.TestCheckpointBoardDir.checkout_state

    def test_plumbing_writes_the_run_branch_and_its_tags(self):
        self.foreign_run()
        self.on_template()
        before = self.checkout_state()
        name = ship.run_branch_name(RUN, "human")
        for tid, path in (("T-0001", "p.md"), ("T-0002", "q.md")):
            self.write(self.root, os.path.join("board", path))
            rc, out, err = self.cp("--ticket", tid, "--only", "board", "--run", RUN)
            self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.checkout_state()[:2], before[:2])        # HEAD and branch kept
        self.assertEqual(run(self.root, "log", "--format=%s", before[0] + ".." + name).splitlines()[:2],
                         ["T-0002: checkpoint", "T-0001: checkpoint"])
        self.assertEqual(self.files(self.root, "ticket/T-0001/1^{commit}"), ["board/p.md"])
        self.assertEqual(self.files(self.root, "ticket/T-0002/1^{commit}"), ["board/q.md"])
        self.assertEqual(run(self.root_remote, "rev-parse", "refs/heads/" + name),
                         run(self.root, "rev-parse", name))
        self.assertEqual(run(self.root_remote, "tag", "-l").splitlines(),
                         ["ticket/T-0001/1", "ticket/T-0002/1"])

    def test_the_switching_path_writes_the_run_branch_too(self):
        self.on_template()
        self.write(self.root, os.path.join("board", "p.md"))
        rc, out, err = self.cp("--ticket", "T-0001", "--only", "board", "--run", RUN)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(ship.current(self.root), ship.run_branch_name(RUN, "human"))
        self.assertEqual(run(self.root_remote, "tag", "-l"), "ticket/T-0001/1")


if __name__ == "__main__":
    unittest.main()
