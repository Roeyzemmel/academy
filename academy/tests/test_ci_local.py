"""ci_local.py: a repo's push-triggered workflow files run locally, and as ship.py's push
gate (2026-11-13: the workflow files stay the one description of the checks)."""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import ci_local as ci  # noqa: E402
import ship  # noqa: E402
from ship_fixture import run as git_run  # noqa: E402
from test_ship import Base  # noqa: E402

BASH = shutil.which("bash")

WORKFLOW = """# a comment
name: tests
on:
  push:
  workflow_dispatch:
permissions:
  contents: read   # trailing comment
concurrency:
  group: tests-${{ github.ref }}
env:
  ALL: "1"
jobs:
  unittest:
    runs-on: ubuntu-latest
    env: {}
    steps:
      - uses: actions/checkout@v4
        with:
          path: Lab
      - uses: actions/checkout@v4
        with:
          repository: someone/tools
          path: tools
      - name: git identity
        run: |
          git config --global user.name "ci"
          git config --global user.email "ci@example.com"
      - name: first
        working-directory: Lab
        run: python -c "import os, sys; sys.exit(0 if os.environ['CI'] == 'true' and os.environ['ALL'] == '1' else 9)"
      - name: second
        if: ${{ !cancelled() }}
        env:
          STEP: 'yes # not a comment'
        run: |
          test "$STEP" = "yes # not a comment"
          echo second ran
  lint:
    steps:
      - run: pip install some-linter==1.2.3
      - run: some-linter-that-is-not-installed check .
      - name: needs a secret
        run: deploy
        env:
          TOKEN: ${{ secrets.TOKEN }}
"""
ISSUES = """name: sync
on:
  issues:
    types: [opened, edited]
  workflow_dispatch:
jobs:
  sync:
    steps:
      - run: python -c "raise SystemExit('must never run on a push')"
"""


def write(top, name, text):
    d = os.path.join(top, ".github", "workflows")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class Parse(unittest.TestCase):
    def test_the_subset_workflow_files_use(self):
        d = ci.parse_yaml(WORKFLOW)
        self.assertEqual("tests", d["name"])
        self.assertTrue(ci.triggered_by_push(d))
        self.assertEqual({"contents": "read"}, d["permissions"])
        steps = d["jobs"]["unittest"]["steps"]
        self.assertEqual({"uses": "actions/checkout@v4", "with": {"path": "Lab"}}, steps[0])
        self.assertEqual('git config --global user.name "ci"\n'
                         'git config --global user.email "ci@example.com"\n', steps[2]["run"])
        self.assertEqual("yes # not a comment", steps[4]["env"]["STEP"])
        self.assertEqual("${{ !cancelled() }}", steps[4]["if"])
        self.assertEqual(["opened", "edited"], ci.parse_yaml(ISSUES)["on"]["issues"]["types"])
        self.assertFalse(ci.triggered_by_push(ci.parse_yaml(ISSUES)))
        self.assertTrue(ci.triggered_by_push({"on": ["push", "pull_request"]}))
        self.assertTrue(ci.triggered_by_push({"on": "push"}))
        with self.assertRaises(ci.WorkflowError):
            ci.parse_yaml("jobs:\n  a: 1\n    b: 2\n")

    def test_this_repos_own_workflows_are_readable_and_planned(self):
        steps, problems = ci.plan(REPO)
        self.assertEqual([], problems)
        ran = [s["label"] for s in steps if not s["skip"]]
        self.assertTrue(any(lbl.endswith(": academy") for lbl in ran), ran)
        self.assertTrue(any("ruff check" in lbl for lbl in ran), ran)
        self.assertTrue(all("git identity" not in lbl and "pip install" not in lbl for lbl in ran))


class Plan(unittest.TestCase):
    def setUp(self):
        self.top = tempfile.mkdtemp(prefix="ci-local-")
        self.addCleanup(shutil.rmtree, self.top, True)
        write(self.top, "tests.yml", WORKFLOW)
        write(self.top, "sync.yml", ISSUES)

    def test_the_plan_takes_push_workflows_and_says_why_a_step_is_skipped(self):
        steps, problems = ci.plan(self.top)
        self.assertEqual([], problems)
        by = {s["label"].split(": ", 1)[1]: s for s in steps}
        self.assertEqual(["git identity", "first", "second", "pip install some-linter==1.2.3",
                          "some-linter-that-is-not-installed check .", "needs a secret"], list(by))
        self.assertIn("setup step", by["git identity"]["skip"])
        self.assertIn("setup step", by["pip install some-linter==1.2.3"]["skip"])
        self.assertIn("GitHub's context", by["needs a secret"]["skip"])
        self.assertIsNone(by["first"]["skip"])
        self.assertEqual(self.top, by["first"]["cwd"])            # Lab is the repo itself
        self.assertEqual((False, True), (by["first"]["always"], by["second"]["always"]))
        self.assertEqual({"ALL": "1", "STEP": "yes # not a comment"}, by["second"]["env"])
        # the issue-triggered workflow is planned only when named
        self.assertEqual(1, len(ci.plan(self.top, workflow="sync.yml")[0]))

    def test_an_unreadable_workflow_is_a_problem_not_a_pass(self):
        write(self.top, "bad.yml", "on: push\njobs:\n  a: 1\n     b: 2\n")
        steps, problems = ci.plan(self.top)
        self.assertEqual(1, len(problems))
        self.assertIn("bad.yml", problems[0])
        ok, lines = ci.run(self.top) if BASH else (False, [])
        self.assertFalse(ok)

    @unittest.skipUnless(BASH, "bash is not installed")
    def test_run_ok_skipped_and_failed(self):
        ok, lines = ci.run(self.top)
        text = "\n".join(lines)
        self.assertTrue(ok, text)
        self.assertIn("first ok", text)
        self.assertIn("second ok", text)
        self.assertIn("skipped: a tool the workflow installs is not on this machine", text)
        self.assertNotIn("must never run", text)
        # a failing step fails the run; a later step of the job runs only with !cancelled()
        write(self.top, "tests.yml", WORKFLOW.replace("sys.exit(0 if", "sys.exit(4 if")
              .replace("      - name: second", "      - name: between\n        run: echo no\n"
                                               "      - name: second"))
        ok, lines = ci.run(self.top)
        text = "\n".join(lines)
        self.assertFalse(ok)
        self.assertIn("first failed (exit 4)", text)
        self.assertIn("between skipped: an earlier step of its job failed", text)
        self.assertIn("second ok", text)


@unittest.skipUnless(BASH, "bash is not installed")
class GateRunsTheWorkflows(Base):
    def branch_with_workflow(self, body):
        self.on_branch()
        write(self.sub, "tests.yml", "on: push\njobs:\n  t:\n    steps:\n      - name: suite\n"
                                     "        run: %s\n" % body)
        self.write("a2.txt")
        rc, out, err = self.ship("commit", "sub", "-m", "x", "--all")
        self.assertEqual(0, rc, err)

    def remote_has(self):
        return bool(git_run(self.root, "ls-remote", self.remote,
                            "refs/heads/" + ship.current(self.sub)))

    def test_a_failing_workflow_step_refuses_the_push(self):
        self.branch_with_workflow("python -c \"print('3 failures'); raise SystemExit(1)\"")
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(1, rc)
        self.assertIn("tests.yml/t: suite failed (exit 1)", err)
        self.assertIn("3 failures", err)
        self.assertFalse(self.remote_has())

    def test_a_passing_workflow_lets_the_push_through_once_per_tree(self):
        self.branch_with_workflow("python -c \"print('fine')\"")
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(0, rc, err)
        self.assertIn("push gate: ci: tests.yml/t: suite ok", err)
        self.assertTrue(self.remote_has())
        self.assertIn("passed before", ship.run_push_gate(self.sub)[1][0])

    def test_a_repo_can_declare_it_has_no_gate(self):
        self.branch_with_workflow("python -c \"raise SystemExit(1)\"")
        with open(os.path.join(self.sub, "ship.json"), "w", encoding="utf-8") as f:
            json.dump({"pushGate": False}, f)
        self.ship("commit", "sub", "-m", "no gate", "--all")
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(0, rc, err)


if __name__ == "__main__":
    unittest.main()
