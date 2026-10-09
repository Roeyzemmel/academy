"""board_templates.py: the GitHub board's issue form rendered from the workspace."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import board_project  # noqa: E402
import board_templates as bt  # noqa: E402


class TestTicketForm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-templates-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = os.path.join(self.tmp, "workspace.json")
        with open(self.ws, "w", encoding="utf-8") as fh:
            json.dump({"board": os.path.join(self.tmp, "board"), "instances": {
                "scientist@lab": {"role": "scientist", "home": "/x/lab", "domains": ["d"]},
                "author@paper": {"role": "author", "home": "/x/paper", "domains": ["d"]}}}, fh)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = bt.main(list(argv) + ["--workspace", self.ws])
        return rc, out.getvalue()

    def test_the_template_keeps_a_placeholder(self):
        with open(os.path.join(bt.TEMPLATES, bt.TICKET_FORM), encoding="utf-8") as fh:
            self.assertIn(bt.PLACEHOLDER, fh.read())

    def test_dropdown_lists_the_instances_and_human(self):
        rc, text = self.run_cli("ticket-form")
        self.assertEqual(rc, 0)
        self.assertNotIn("{{instances}}", text)
        self.assertIn('options: ["author@paper", "scientist@lab", "human"]', text)
        # the same options, in the same order, as the Project's Instance field
        spec = board_project.build(["scientist@lab", "author@paper"])
        inst = next(f for f in spec["fields"] if f["name"] == "Instance")
        names = [o["name"] for o in inst["options"]]
        self.assertEqual(sorted(names[:-1]) + names[-1:],
                         bt.instance_options(["scientist@lab", "author@paper"]))

    def test_render_and_check(self):
        out = os.path.join(self.tmp, "repo")
        rc, text = self.run_cli("render", "--out", out)
        self.assertEqual(rc, 0)
        form = os.path.join(out, ".github", "ISSUE_TEMPLATE", "ticket.yml")
        self.assertTrue(os.path.isfile(form))
        self.assertTrue(os.path.isfile(os.path.join(out, ".github", "workflows",
                                                    "board-sync.yml")))
        self.assertEqual(self.run_cli("check", "--out", out)[0], 0)
        with open(form, "a", encoding="utf-8") as fh:
            fh.write("# hand edit\n")
        rc, text = self.run_cli("check", "--out", out)
        self.assertEqual(rc, 1)
        self.assertIn("differs: .github/ISSUE_TEMPLATE/ticket.yml", text)

    def test_missing_placeholder_is_an_error(self):
        with self.assertRaises(ValueError):
            bt.render_ticket_form(["a@b"], template="options: [x]\n")


if __name__ == "__main__":
    unittest.main()
