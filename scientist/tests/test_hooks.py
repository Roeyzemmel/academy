"""The two hooks: commit_gate (which repo a commit runs in, and only the lab's) and
experiment_edit_check (only experiment scripts inside the lab)."""

import json
import os
import unittest

from helpers import Sandbox

import _common as c

FAKE_CHECKER = '''import sys
bad = [a for a in sys.argv[1:] if a.endswith(".py") and "bad" in a]
for a in bad:
    print("%s:3: ERROR: [E3] a header field is still the template's <placeholder>" % a)
for a in sys.argv[1:]:
    if a.endswith(".py") and "warn" in a:
        print("%s:5: WARN: [W1] Needs Sage: yes but no env.require_sage guard" % a)
sys.exit(1 if bad or any("warn" in a for a in sys.argv[1:]) else 0)
'''


def bash(command, cwd):
    return json.dumps({"tool_name": "Bash", "cwd": cwd,
                       "tool_input": {"command": command}})


def powershell(command, cwd):
    return json.dumps({"tool_name": "PowerShell", "cwd": cwd,
                       "tool_input": {"command": command}})


def edit(path, cwd):
    return json.dumps({"tool_name": "Edit", "cwd": cwd, "tool_input": {"file_path": path}})


class CommitTargetsTest(unittest.TestCase):
    def setUp(self):
        self.base = os.path.abspath(os.sep + "work")

    def t(self, cmd):
        return [os.path.normcase(p) for p in c.commit_targets(cmd, self.base)]

    def n(self, *parts):
        return os.path.normcase(os.path.abspath(os.path.join(self.base, *parts)))

    def test_plain_commit_uses_cwd(self):
        self.assertEqual(self.t('git commit -m "x"'), [self.n()])

    def test_bash_cd(self):
        self.assertEqual(self.t('cd lab && git add -A && git commit -m y'), [self.n("lab")])

    def test_powershell_set_location(self):
        self.assertEqual(self.t('Set-Location -Path ..\\lab; git commit -m y'),
                         [os.path.normcase(os.path.abspath(os.path.join(self.base, "..",
                                                                        "lab")))])

    def test_git_dash_c(self):
        self.assertEqual(self.t('git -C other commit -m "z"'), [self.n("other")])

    def test_git_exe_and_call_operator(self):
        self.assertEqual(self.t('& git.exe commit -m z'), [self.n()])

    def test_not_a_commit(self):
        self.assertEqual(self.t('git log --grep commit; git status'), [])
        self.assertEqual(self.t('echo "git commit"'), [])

    def test_two_repos(self):
        self.assertEqual(self.t('cd a; git commit -m 1; cd ../b; git commit -m 2'),
                         [self.n("a"), self.n("b")])

    @unittest.skipUnless(os.name == "nt", "Git Bash drive paths are a Windows form")
    def test_git_bash_drive_paths(self):
        # the Group B review's reproducer: these used to resolve to C:\c\Work\...
        want = [os.path.normcase("C:\\Work\\Math\\SciLab")]
        self.assertEqual(self.t("cd /c/Work/Math/SciLab && git commit -m x"), want)
        self.assertEqual(self.t("git -C /c/Work/Math/SciLab commit -m x"), want)

    def test_work_tree_and_heredoc(self):
        self.assertEqual(self.t("git --work-tree=lab --git-dir=lab/.git commit -m x"),
                         [self.n("lab")])
        cmd = "git commit -F - <<'EOF'\ncd elsewhere\ngit commit in the message\nEOF"
        self.assertEqual(self.t(cmd), [self.n()])

    def test_unbalanced_quote_falls_back_to_cwd(self):
        self.assertEqual(self.t('git commit -m "oops'), [self.n()])


class HookTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.sb.write("scripts/check_experiments.py", FAKE_CHECKER)
        for repo in (self.sb.lab, self.sb.other):
            self.sb.git("init", "-q", "-b", "main", cwd=repo)
        self.sb.write(".claude/academy.json", json.dumps({
            "schema": 1, "role": "author", "instance": "author@main",
            "domains": ["translation-surfaces"], "ns": "paper",
            "paths": {"tex": "x", "bib": "b", "drafts": "d", "agenda": "a",
                      "records": "c", "views": []},
            "registry": {"profile": "paper", "root": "c"}, "author": {}}),
            base=self.sb.other)

    def tearDown(self):
        self.sb.close()

    def gate(self, event):
        return self.sb.run("commit_gate.py", [], stdin=event)

    def stage_orphan(self, repo=None):
        repo = repo or self.sb.lab
        self.sb.write("results/orphan.json", "{}", base=repo)
        self.sb.git("add", "results/orphan.json", cwd=repo)

    # -- commit_gate ---------------------------------------------------------

    def test_orphan_result_blocked_in_lab(self):
        self.stage_orphan()
        code, out, err = self.gate(bash('git commit -m "x"', self.sb.lab))
        self.assertEqual(code, 2)
        self.assertIn("results/orphan.json is staged but experiments/orphan.py", err)

    def test_powershell_commit_gated(self):
        self.stage_orphan()
        code, out, err = self.gate(powershell("git commit -m @'\nx\n'@", self.sb.lab))
        self.assertEqual(code, 2)

    def test_commit_into_lab_from_elsewhere_is_gated(self):
        self.stage_orphan()
        code, out, err = self.gate(bash('cd "%s" && git commit -m x' % self.sb.lab,
                                        self.sb.other))
        self.assertEqual(code, 2)
        code, out, err = self.gate(bash('git -C "%s" commit -m x' % self.sb.lab,
                                        self.sb.root))
        self.assertEqual(code, 2)

    @unittest.skipUnless(os.name == "nt", "Git Bash drive paths are a Windows form")
    def test_git_bash_path_into_lab_is_gated(self):
        self.stage_orphan()
        lab = os.path.abspath(self.sb.lab).replace("\\", "/")
        gitbash = "/" + lab[0].lower() + lab[2:]
        code, out, err = self.gate(bash("cd %s && git commit -m x" % gitbash, self.sb.other))
        self.assertEqual(code, 2)
        code, out, err = self.gate(bash("git -C %s commit -m x" % gitbash, self.sb.root))
        self.assertEqual(code, 2)

    def test_commit_elsewhere_from_the_lab_passes(self):
        self.stage_orphan(self.sb.other)
        self.stage_orphan()
        code, out, err = self.gate(bash('git -C "%s" commit -m x' % self.sb.other,
                                        self.sb.lab))
        self.assertEqual((code, err), (0, ""))

    def test_non_scientist_home_passes(self):
        self.stage_orphan(self.sb.other)
        code, out, err = self.gate(bash("git commit -m x", self.sb.other))
        self.assertEqual((code, err), (0, ""))

    def test_workspace_must_list_the_instance_as_scientist(self):
        self.stage_orphan()
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        del ws["instances"]["scientist@main"]
        self.sb.write_json(self.sb.workspace, ws)
        code, out, err = self.gate(bash("git commit -m x", self.sb.lab))
        self.assertEqual((code, err), (0, ""))

    def test_branch_override_off(self):
        self.stage_orphan()
        self.sb.git("checkout", "-q", "-b", "academy-migration")
        code, out, err = self.gate(bash("git commit -m x", self.sb.lab))
        self.assertEqual((code, err), (0, ""))

    def test_header_errors_block_warnings_pass_in_normal_mode(self):
        self.sb.write("experiments/2026-09-28_bad.py", '"""x"""\n')
        self.sb.write("experiments/2026-09-28_warn.py", '"""x"""\n')
        self.sb.git("add", "experiments")
        code, out, err = self.gate(bash("git commit -m x", self.sb.lab))
        self.assertEqual(code, 2)
        self.assertIn("[E3]", err)
        self.assertNotIn("[W1]", err)
        self.sb.git("rm", "-q", "--cached", "experiments/2026-09-28_bad.py")
        code, out, err = self.gate(bash("git commit -m x", self.sb.lab))
        self.assertEqual((code, err), (0, ""))

    def test_strict_mode_blocks_warnings(self):
        cfg_path = os.path.join(self.sb.lab, ".claude", "academy.json")
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        cfg["gate"]["commit"] = "strict"
        self.sb.write_json(cfg_path, cfg)
        self.sb.write("experiments/2026-09-28_warn.py", '"""x"""\n')
        self.sb.git("add", "experiments")
        code, out, err = self.gate(bash("git commit -m x", self.sb.lab))
        self.assertEqual(code, 2)
        self.assertIn("[W1]", err)

    def test_not_a_commit_is_silent(self):
        self.stage_orphan()
        code, out, err = self.gate(bash("git status", self.sb.lab))
        self.assertEqual((code, err), (0, ""))

    # -- experiment_edit_check -----------------------------------------------

    def check(self, path, cwd=None):
        return self.sb.run("experiment_edit_check.py", [],
                           stdin=edit(path, cwd or self.sb.root))

    def test_edit_of_lab_experiment_is_checked(self):
        p = self.sb.write("experiments/2026-09-28_bad.py", '"""x"""\n')
        code, out, err = self.check(p)
        self.assertEqual(code, 2)
        self.assertIn("[E3]", err)
        self.assertIn("experiments/2026-09-28_bad.py", err)

    def test_clean_experiment_is_silent(self):
        p = self.sb.write("experiments/2026-09-28_good.py", '"""x"""\n')
        self.assertEqual(self.check(p)[0], 0)

    def test_edit_outside_experiments_is_silent(self):
        p = self.sb.write("fslab/bad.py", '"""x"""\n')
        self.assertEqual(self.check(p), (0, "", ""))
        p = self.sb.write("experiments/_template.py", '"""bad"""\n')
        self.assertEqual(self.check(p), (0, "", ""))

    def test_edit_in_other_home_is_silent(self):
        self.sb.write("scripts/check_experiments.py", FAKE_CHECKER, base=self.sb.other)
        p = self.sb.write("experiments/2026-09-28_bad.py", '"""x"""\n', base=self.sb.other)
        self.assertEqual(self.check(p, self.sb.lab), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
