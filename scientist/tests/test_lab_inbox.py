"""lab.py (resolution, frontend commands, status) and inbox.py (selection, routes)."""

import os
import unittest

from helpers import Sandbox, EW, TORUS

import _common as c
import inbox
import lab as labmod
import report


class LabTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.close()

    def test_resolve_from_cwd_and_workspace(self):
        lab = c.resolve_lab(None, os.path.join(self.sb.lab, "experiments"))
        self.assertEqual((lab["instance"], lab["switched"]), ("scientist@main", True))
        lab = c.resolve_lab(None, self.sb.other)       # not a lab: falls back to workspace
        self.assertEqual(os.path.normcase(lab["home"]), os.path.normcase(self.sb.lab))

    def test_pre_switch_home_uses_defaults(self):
        os.remove(os.path.join(self.sb.lab, ".claude", "academy.json"))
        lab = c.resolve_lab(self.sb.lab)
        self.assertFalse(lab["switched"])
        self.assertEqual(lab["instance"], "scientist@main")
        self.assertEqual(c.results_dir(lab["cfg"]), "results")

    def test_command_legacy_then_env_py(self):
        lab = c.resolve_lab(self.sb.lab)
        fake = os.path.join(self.sb.root, "plugin")          # a plugin copy without env.py
        os.makedirs(os.path.join(fake, "scripts"))
        with self.assertRaises(c.ac.AcademyError):
            labmod.command_for(lab, "queue", ["-List"], plugin=fake)  # no scripts/queue.ps1
        self.sb.write("scripts/queue.ps1", "# stub\n")
        runner, cmd = labmod.command_for(lab, "queue", ["-List"], plugin=fake)
        self.assertEqual(runner, "legacy")
        self.assertTrue(cmd.endswith("scripts\\queue.ps1 -List"), cmd)
        self.sb.write("scripts/env.py", "", base=fake)
        runner, cmd = labmod.command_for(lab, "queue", ["-List"], plugin=fake)
        self.assertEqual(runner, "env.py")
        self.assertIn('env.py" --home "%s" queue -List' % self.sb.lab.replace("\\", "/"), cmd)
        # the real plugin: env.py for queue/run/vpn, its own checker for check
        self.assertEqual(labmod.command_for(lab, "vpn", ["-Quiet"])[0], "env.py")
        runner, cmd = labmod.command_for(lab, "check", ["--strict"])
        self.assertEqual(runner, "plugin")
        self.assertIn('check_experiments.py" --home "%s" --strict'
                      % self.sb.lab.replace("\\", "/"), cmd)

    def test_status_lists_unreported_results(self):
        lab = c.resolve_lab(self.sb.lab)
        s = labmod.status(lab, self.sb.board)
        self.assertEqual(s["unreported_total"], 2)
        ctx = report.gather("experiments/%s.py" % EW, lab)
        meta, body = report.render(ctx)
        report.file_report(ctx, meta, body, board=self.sb.board, workspace=self.sb.workspace)
        s = labmod.status(lab, self.sb.board)
        self.assertEqual(s["unreported_results"], ["results/%s.json" % TORUS])
        self.assertEqual(s["open_packets"], 1)


class InboxTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.board = report._academy_module("board")

    def tearDown(self):
        self.sb.close()

    def ticket(self, kind, title, priority="normal", max_model="sonnet"):
        return self.board.create_ticket(self.sb.board, "scientist@main", title, "ask", "done",
                                        kind=kind, priority=priority,
                                        budget={"runs": 1, "max_model": max_model},
                                        as_instance="researcher@alpha")

    def test_order_cut_and_routes(self):
        self.ticket("code", "refactor the runner", max_model="sonnet")
        self.ticket("experiment", "run EW")
        self.ticket("verify", "not ours")
        self.ticket("test", "falsifier", priority="high")
        rows, total = inbox.select(self.sb.board, "scientist@main", 3)
        self.assertEqual(total, 4)
        self.assertEqual([r["kind"] for r in rows], ["test", "code", "experiment"])
        self.assertEqual(rows[0]["route"], "experimenter")
        self.assertEqual(rows[1]["route"], "developer")
        self.assertIn("over_budget", rows[1])                  # developer is opus
        rows, _ = inbox.select(self.sb.board, "scientist@main", 3, take_all=True)
        self.assertEqual(rows[-1]["route"], "reject")

    def test_upstream_code_ticket_goes_to_upstream_contributor(self):
        self.ticket("code", "Upstream: saddle_connections ignores the bound")
        rows, _ = inbox.select(self.sb.board, "scientist@main", 3)
        self.assertEqual(rows[0]["route"], "upstream-contributor")
        self.assertNotIn("over_budget", rows[0])

    def test_empty_inbox_exit_1(self):
        code, out, err = self.sb.run("inbox.py", ["--home", self.sb.lab, "--board",
                                                  self.sb.board])
        self.assertEqual(code, 1)
        self.assertIn("0 taken", out)


if __name__ == "__main__":
    unittest.main()
