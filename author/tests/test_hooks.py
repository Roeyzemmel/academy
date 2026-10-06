"""The Author plugin's hooks, run as Claude Code runs them (JSON event on stdin).

commit_gate (scoping by the repo actually committed, bash and PowerShell, git -C),
build_gate (namespace-stripped identity, writers, the dirty marker, the lock),
bib_gate (only expert:librarian) and tex_edit_check (scoping, dirty marker).
Run from the repo root:  py -m unittest discover author/tests
"""

import json
import os
import sys
import time
import unittest

from fixtures import SCRIPTS, HAVE_GIT, Sandbox, run_hook

sys.path.insert(0, SCRIPTS)
import commit_gate  # noqa: E402

FINDING = "  sections/a.tex:12: lem:x: [R1] rests on a sketch\n"
KEY = "sections/a.tex|lem:x|R1"


# ----------------------------------------------------------------------------
# commit_gate: the parser
# ----------------------------------------------------------------------------

class CommitTargetsTests(unittest.TestCase):
    base = os.path.abspath(os.sep.join(["", "work", "paper"])) if os.name != "nt" \
        else "C:\\Work\\Math\\paper"

    def targets(self, cmd, cwd=None):
        return [os.path.normcase(d) for d in commit_gate.commit_targets(cmd, cwd or self.base)]

    def at(self, *parts):
        return os.path.normcase(os.path.normpath(os.path.join(self.base, *parts)))

    def test_plain_commit_uses_the_tool_cwd(self):
        self.assertEqual(self.targets('git commit -m "x"'), [self.at()])

    def test_git_dash_C_absolute_and_relative(self):
        self.assertEqual(self.targets("git -C ../lab commit -m x"), [self.at("..", "lab")])
        self.assertEqual(self.targets("git -C a -C b commit"), [self.at("a", "b")])

    def test_git_dash_C_quoted_with_spaces(self):
        self.assertEqual(self.targets('git -C "../my lab" commit -m x'),
                         [self.at("..", "my lab")])

    def test_cd_and_then_commit(self):
        self.assertEqual(self.targets("cd ../lab && git commit -m x"), [self.at("..", "lab")])
        self.assertEqual(self.targets("cd ../lab; git add -A; git commit -m x"),
                         [self.at("..", "lab")])

    @unittest.skipUnless(os.name == "nt", "a backslash separates paths only on Windows")
    def test_powershell_set_location_and_call_operator(self):
        self.assertEqual(self.targets("Set-Location ..\\lab; git commit -m x"),
                         [self.at("..", "lab")])
        self.assertEqual(self.targets("Set-Location -Path '..\\lab'; & git.exe commit"),
                         [self.at("..", "lab")])
        self.assertEqual(self.targets("Push-Location ..\\lab; git commit; Pop-Location"),
                         [self.at("..", "lab")])

    def test_powershell_here_string_is_data(self):
        cmd = "git commit -m @'\nfix; git commit elsewhere\n'@"
        self.assertEqual(self.targets(cmd), [self.at()])

    def test_bash_heredoc_is_data(self):
        cmd = "git commit -F - <<'EOF'\ncd ../lab\ngit commit inside the message\nEOF"
        self.assertEqual(self.targets(cmd), [self.at()])

    def test_not_a_commit(self):
        self.assertEqual(self.targets("git log --grep commit"), [])
        self.assertEqual(self.targets('echo "git commit"'), [])
        self.assertEqual(self.targets("git -c commit.gpgsign=false status"), [])

    def test_global_options_before_commit(self):
        self.assertEqual(self.targets("git -c user.name=x --no-pager commit -m y"), [self.at()])
        self.assertEqual(self.targets("git --work-tree=../lab --git-dir=../lab/.git commit"),
                         [self.at("..", "lab")])

    def test_nested_shells(self):
        self.assertEqual(self.targets('bash -c "cd ../lab && git commit -m y"'),
                         [self.at("..", "lab")])
        self.assertEqual(self.targets('powershell -Command "git -C ../lab commit -m z"'),
                         [self.at("..", "lab")])

    @unittest.skipUnless(os.name == "nt", "Git Bash drive paths are a Windows form")
    def test_git_bash_drive_path(self):
        self.assertEqual(self.targets("git -C /c/Work/Math/lab commit"),
                         [os.path.normcase("C:\\Work\\Math\\lab")])
        self.assertEqual(self.targets("cd /d/x && git commit"), [os.path.normcase("D:\\x")])

    def test_unbalanced_quote_raises(self):
        with self.assertRaises(commit_gate.ParseFailure):
            commit_gate.commit_targets('git commit -m "oops', self.base)


# ----------------------------------------------------------------------------
# commit_gate: the hook
# ----------------------------------------------------------------------------

class CommitGateHookTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.sb.set_checker(FINDING, 1)

    def tearDown(self):
        self.sb.cleanup()

    def gate(self, command, cwd, tool="Bash"):
        ev = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": cwd,
              "tool_input": {"command": command}}
        return run_hook("commit_gate.py", ev, self.sb.env, cwd=cwd)

    def test_commit_in_author_home_blocked_on_new_finding(self):
        self.sb.set_baseline(["sections/b.tex|lem:y|R1"])
        code, _out, err = self.gate('git commit -m "x"', self.sb.home)
        self.assertEqual(code, 2, err)
        self.assertIn("not in the recorded baseline", err)
        self.assertIn("lem:x", err)

    def test_no_baseline_blocks_and_says_how_to_record_one(self):
        code, _out, err = self.gate('git commit -m "x"', self.sb.home)
        self.assertEqual(code, 2, err)
        self.assertIn("no baseline is recorded", err)
        self.assertIn("--write-baseline", err)

    def test_finding_in_baseline_passes(self):
        self.sb.set_baseline([KEY])
        code, _out, err = self.gate('git commit -m "x"', self.sb.home)
        self.assertEqual(code, 0, err)

    def test_clean_checker_passes(self):
        self.sb.set_checker("", 0)
        self.assertEqual(self.gate("git commit -m x", self.sb.home)[0], 0)

    def test_commit_to_other_repo_from_author_cwd_is_not_gated(self):
        # the misfire: a BI session committing to SciLab ran BI's checker
        code, _out, err = self.gate("git -C %s commit -m x" % self.sb.other, self.sb.home)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sb.calls("checker_calls.txt"), [])

    def test_cd_to_other_repo_is_not_gated(self):
        code, _o, err = self.gate('cd "%s" && git commit -m x' % self.sb.other, self.sb.home)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sb.calls("checker_calls.txt"), [])

    def test_commit_into_author_home_from_elsewhere_is_gated(self):
        code, _o, err = self.gate('git -C "%s" commit -m x' % self.sb.home, self.sb.other)
        self.assertEqual(code, 2, err)

    def test_powershell_commit_is_gated(self):
        code, _o, err = self.gate("Set-Location '%s'; git commit -m x" % self.sb.home,
                                  self.sb.other, tool="PowerShell")
        self.assertEqual(code, 2, err)
        code, _o, err = self.gate("& git -C '%s' commit -m x" % self.sb.home,
                                  self.sb.other, tool="PowerShell")
        self.assertEqual(code, 2, err)

    def test_non_commit_is_ignored(self):
        self.assertEqual(self.gate("git status", self.sb.home)[0], 0)
        self.assertEqual(self.sb.calls("checker_calls.txt"), [])

    def test_mode_off_in_config(self):
        self.sb.write_config(gate={"commit": "off", "build": True, "branches": {}})
        self.assertEqual(self.gate("git commit -m x", self.sb.home)[0], 0)

    def test_strict_mode_passes_strict_args(self):
        self.sb.write_config(gate={"commit": "strict", "build": True, "branches": {},
                                   "baseline": ".claude/paper-gate-baseline.txt"})
        self.gate("git commit -m x", self.sb.home)
        self.assertIn("--strict", self.sb.calls("checker_calls.txt")[-1])

    @unittest.skipUnless(HAVE_GIT, "git not on PATH")
    def test_branch_override_turns_the_gate_off(self):
        self.sb.git_init(self.sb.home, branch="academy-migration")
        self.assertEqual(self.gate("git commit -m x", self.sb.home)[0], 0)
        self.sb.git_init(self.sb.other, branch="main")

    @unittest.skipUnless(HAVE_GIT, "git not on PATH")
    def test_main_branch_is_gated(self):
        self.sb.git_init(self.sb.home, branch="main")
        self.assertEqual(self.gate("git commit -m x", self.sb.home)[0], 2)

    @unittest.skipUnless(HAVE_GIT, "git not on PATH")
    def test_warn_mode_exit_zero_with_findings_on_stderr(self):
        self.sb.write_config(gate={"commit": "normal", "build": True,
                                   "baseline": ".claude/paper-gate-baseline.txt",
                                   "branches": {"????-??-??/*/*": {"commit": "warn"}}})
        self.sb.set_baseline(["sections/b.tex|lem:y|R1"])
        self.sb.git_init(self.sb.home, branch="2026-09-30/t-0059/author")
        code, _out, err = self.gate('git commit -m "x"', self.sb.home)
        self.assertEqual(code, 0, err)
        self.assertIn("commit gate (warn):", err)
        self.assertIn("lem:x", err)

    def test_warn_mode_in_config_exit_zero(self):
        self.sb.write_config(gate={"commit": "warn", "build": True, "branches": {},
                                   "baseline": ".claude/paper-gate-baseline.txt"})
        code, _out, err = self.gate('git commit -m "x"', self.sb.home)
        self.assertEqual(code, 0, err)
        self.assertIn("commit gate (warn):", err)
        self.assertIn("lem:x", err)

    @unittest.skipUnless(HAVE_GIT, "git not on PATH")
    def test_normal_mode_still_blocks_exit_two(self):
        self.sb.write_config(gate={"commit": "normal", "build": True,
                                   "baseline": ".claude/paper-gate-baseline.txt",
                                   "branches": {"????-??-??/*/*": {"commit": "warn"}}})
        self.sb.set_baseline(["sections/b.tex|lem:y|R1"])
        self.sb.git_init(self.sb.home, branch="main")
        code, _out, err = self.gate('git commit -m "x"', self.sb.home)
        self.assertEqual(code, 2, err)
        self.assertIn("not in the recorded baseline", err)
        self.assertNotIn("commit gate (warn):", err)

    # -- gate_check, the importable core (scripts/ship.py calls it) ----------

    def loaded(self):
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace
        try:
            home, cfg = commit_gate.au.author_home(self.sb.home)
        finally:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        self.assertIsNotNone(home)
        return home, cfg

    def test_off_mode_skips_checker(self):
        self.sb.write_config(gate={"commit": "off", "build": True, "branches": {}})
        home, cfg = self.loaded()
        self.assertEqual(commit_gate.gate_check(home, cfg, "main"), ("off", {}))
        self.assertEqual(self.sb.calls("checker_calls.txt"), [])
        self.assertEqual(self.gate("git commit -m x", self.sb.home)[0], 0)
        self.assertEqual(self.sb.calls("checker_calls.txt"), [])

    def test_gate_check_returns_new_findings_only(self):
        self.sb.set_checker(FINDING + "  sections/b.tex:3: lem:y: [R1] rests on a sketch\n",
                            1)
        self.sb.set_baseline(["sections/b.tex|lem:y|R1"])
        home, cfg = self.loaded()
        mode, new = commit_gate.gate_check(home, cfg, "main")
        self.assertEqual(mode, "normal")
        self.assertEqual(list(new), [KEY])
        self.assertIn("lem:x", new[KEY])
        # glob override: same findings, mode warn
        cfg["gate"]["branches"] = {"????-??-??/*/*": {"commit": "warn"}}
        self.assertEqual(commit_gate.gate_check(home, cfg, "2026-09-30/t-0059/author"),
                         ("warn", {KEY: new[KEY]}))
        # everything in the baseline -> no new findings
        self.sb.set_baseline([KEY, "sections/b.tex|lem:y|R1"])
        self.assertEqual(commit_gate.gate_check(home, cfg, "main"), ("normal", {}))
        # a clean checker exit -> nothing, whatever it printed
        self.sb.set_checker(FINDING, 0)
        self.sb.set_baseline([])
        self.assertEqual(commit_gate.gate_check(home, cfg, "main"), ("normal", {}))

    def test_gate_check_no_baseline_counts_all_findings(self):
        home, cfg = self.loaded()
        mode, new = commit_gate.gate_check(home, cfg, None)
        self.assertEqual((mode, list(new)), ("normal", [KEY]))

    def test_gate_check_strict_passes_strict_args(self):
        home, cfg = self.loaded()
        cfg["gate"]["commit"] = "strict"
        self.assertEqual(commit_gate.gate_check(home, cfg, "main")[0], "strict")
        self.assertIn("--strict", self.sb.calls("checker_calls.txt")[-1])

    def test_gate_check_unavailable_when_checker_cannot_run(self):
        from unittest import mock
        home, cfg = self.loaded()
        with mock.patch.object(commit_gate.au, "run_checker",
                               return_value=(None, "checker could not run: boom")):
            self.assertEqual(commit_gate.gate_check(home, cfg, "main"), ("unavailable", {}))
        # and for real: a home whose directory vanished cannot be the checker's cwd
        gone = os.path.join(self.sb.root, "gone")
        self.assertEqual(commit_gate.gate_check(gone, cfg, "main"), ("unavailable", {}))
        mode, new, cause = commit_gate.gate_check_detail(gone, cfg, "main")
        self.assertEqual((mode, new), ("unavailable", {}))
        self.assertIn("checker could not run", cause)

    # -- I1: a non-zero exit with no parseable finding is 'unavailable', not clean --

    def assert_unavailable(self, needle):
        home, cfg = self.loaded()
        mode, new, cause = commit_gate.gate_check_detail(home, cfg, "main")
        self.assertEqual((mode, new), ("unavailable", {}))
        self.assertTrue(cause.strip())
        self.assertIn(needle, cause)
        self.assertEqual(commit_gate.gate_check(home, cfg, "main"), ("unavailable", {}))

    def test_missing_checker_script_is_unavailable(self):
        cfg =json.loads(self.sb.read(os.path.join(self.sb.home, ".claude", "academy.json")))
        author = cfg["author"]
        author["checker"]["script"] = os.path.join(self.sb.tools, "no_such_checker.py")
        self.sb.write_config(author=author)
        self.assert_unavailable("no_such_checker.py")

    def test_parse_error_exit_two_is_unavailable(self):
        self.sb.set_checker("PARSE ERROR: unbalanced braces in sections/a.tex\n", 2)
        self.assert_unavailable("PARSE ERROR")

    def test_exit_one_without_finding_lines_is_unavailable(self):
        # undefined references / ?? are counted in the exit code but not printed
        self.sb.set_checker("Build log: 2 undefined reference(s)\n", 1)
        self.assert_unavailable("undefined reference")

    def test_cause_is_the_last_twenty_lines(self):
        self.sb.set_checker("".join("noise %d\n" % i for i in range(40)), 2)
        home, cfg = self.loaded()
        _mode, _new, cause = commit_gate.gate_check_detail(home, cfg, "main")
        self.assertIn("noise 39", cause)
        self.assertNotIn("noise 5\n", cause + "\n")
        self.assertLessEqual(len(cause.strip().splitlines()), 20)

    def test_findings_all_in_baseline_stay_normal(self):
        # exit 1 with parseable findings, all accepted -> normal, not unavailable
        self.sb.set_baseline([KEY])
        home, cfg = self.loaded()
        mode, new, cause = commit_gate.gate_check_detail(home, cfg, "main")
        self.assertEqual((mode, new), ("normal", {}))

    def test_hook_allows_unavailable_with_a_warning(self):
        self.sb.set_checker("PARSE ERROR: unbalanced braces\n", 2)
        code, _out, err = self.gate('git commit -m "x"', self.sb.home)
        self.assertEqual(code, 0, err)
        self.assertIn("commit gate: checker unavailable (PARSE ERROR: unbalanced braces)"
                      " - not checked", err)

    def test_write_baseline(self):
        import contextlib
        import io
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = commit_gate.main(["--write-baseline", "--root", self.sb.home])
        finally:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        self.assertIn("wrote 1 baseline findings", out.getvalue())
        self.assertEqual(code, 0)
        text = self.sb.read(os.path.join(self.sb.home, ".claude", "paper-gate-baseline.txt"))
        self.assertIn(KEY, text)


# ----------------------------------------------------------------------------
# build_gate
# ----------------------------------------------------------------------------

class BuildGateTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.sb.env["ACADEMY_BUILD_LOCK_WAIT"] = "1"
        self.dirty = os.path.join(self.sb.home, ".build", ".dirty")
        self.sb.write(self.dirty, "tex edited\n")

    def tearDown(self):
        self.sb.cleanup()

    def stop(self, agent, cwd=None):
        ev = {"hook_event_name": "SubagentStop", "cwd": cwd or self.sb.home}
        if agent is not None:
            ev["agent_type"] = agent
        return run_hook("build_gate.py", ev, self.sb.env, cwd=cwd or self.sb.home)

    def built(self):
        return len(self.sb.calls("build_calls.txt"))

    def test_namespaced_writers_trigger_the_build(self):
        for n, agent in enumerate(("author:math-writer", "author:math-editor",
                                   "author:tex-engineer", "expert:librarian",
                                   "math-writer"), 1):
            with self.subTest(agent=agent):
                self.sb.write(self.dirty, "tex edited\n")
                code, _o, err = self.stop(agent)
                self.assertEqual(code, 0, err)
                self.assertEqual(self.built(), n)
                self.assertFalse(os.path.exists(self.dirty))

    def test_non_writers_and_main_session_do_not_build(self):
        for agent in ("expert:clerk", "expert:rigor-reviewer", None):
            code, _o, _e = self.stop(agent)
            self.assertEqual(code, 0)
        self.assertEqual(self.built(), 0)
        self.assertTrue(os.path.exists(self.dirty))

    def test_clean_home_does_not_build(self):
        os.remove(self.dirty)
        self.stop("author:math-writer")
        self.assertEqual(self.built(), 0)

    def test_failing_build_blocks_the_stop(self):
        self.sb.set_build(1)
        code, _o, err = self.stop("author:math-editor")
        self.assertEqual(code, 2)
        self.assertIn("the build exited 1", err)

    def test_new_checker_finding_blocks_but_baseline_does_not(self):
        self.sb.set_checker(FINDING, 1)
        code, _o, err = self.stop("author:math-writer")
        self.assertEqual(code, 2)
        self.assertIn("outside the baseline", err)
        self.sb.set_baseline([KEY])
        self.sb.write(self.dirty, "x\n")
        self.assertEqual(self.stop("author:math-writer")[0], 0)

    def test_librarian_from_another_home_builds_the_dirty_author_home(self):
        code, _o, err = self.stop("expert:librarian", cwd=self.sb.other)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.built(), 1)

    def test_lock_held_means_no_build(self):
        lock = os.path.join(self.sb.home, ".build", ".lock")
        self.sb.write(lock, "999 %d\n" % int(time.time()))
        code, _o, err = self.stop("author:math-writer")
        self.assertEqual(code, 0)
        self.assertEqual(self.built(), 0)
        self.assertIn("is held", err)
        self.assertTrue(os.path.exists(lock))

    def test_stale_lock_is_broken_and_released(self):
        lock = os.path.join(self.sb.home, ".build", ".lock")
        self.sb.write(lock, "999 0\n")
        old = time.time() - 3600
        os.utime(lock, (old, old))
        self.assertEqual(self.stop("author:math-writer")[0], 0)
        self.assertEqual(self.built(), 1)
        self.assertFalse(os.path.exists(lock))

    def test_stop_hook_active_is_silent(self):
        ev = {"hook_event_name": "SubagentStop", "cwd": self.sb.home,
              "agent_type": "author:math-writer", "stop_hook_active": True}
        self.assertEqual(run_hook("build_gate.py", ev, self.sb.env)[0], 0)
        self.assertEqual(self.built(), 0)


# ----------------------------------------------------------------------------
# bib_gate
# ----------------------------------------------------------------------------

class BibGateTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.bib = os.path.join(self.sb.home, "references.bib")

    def tearDown(self):
        self.sb.cleanup()

    def edit(self, path, agent):
        ev = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": self.sb.home,
              "tool_input": {"file_path": path, "old_string": "a", "new_string": "b"}}
        if agent:
            ev["agent_type"] = agent
        code, out, _err = run_hook("bib_gate.py", ev, self.sb.env)
        self.assertEqual(code, 0)
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def test_expert_librarian_allowed(self):
        self.assertIsNone(self.edit(self.bib, "expert:librarian"))
        self.assertIsNone(self.edit(self.bib, "librarian"))

    def test_everyone_else_denied(self):
        for agent in ("author:math-writer", "math-editor", "author:librarian",
                      "paper:source-checker", None):
            with self.subTest(agent=agent):
                self.assertEqual(self.edit(self.bib, agent), "deny")

    def test_scope(self):
        other_bib = os.path.join(self.sb.other, "references.bib")
        self.assertIsNone(self.edit(other_bib, "author:math-writer"))
        self.assertIsNone(self.edit(os.path.join(self.sb.home, "main.tex"),
                                    "author:math-writer"))


# ----------------------------------------------------------------------------
# notation_scope_guard
# ----------------------------------------------------------------------------

class NotationScopeGuardTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.decisions = os.path.join(self.sb.home, ".claude", "rules",
                                      "notation-decisions.md")

    def tearDown(self):
        self.sb.cleanup()

    def edit(self, path, agent="author:notation-auditor", tool="Edit"):
        ev = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": self.sb.home,
              "tool_input": {"file_path": path, "old_string": "a", "new_string": "b"}}
        if agent:
            ev["agent_type"] = agent
        code, out, _err = run_hook("notation_scope_guard.py", ev, self.sb.env)
        self.assertEqual(code, 0)
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def test_decisions_file_allowed(self):
        self.assertIsNone(self.edit(self.decisions))
        self.assertIsNone(self.edit(self.decisions, agent="notation-auditor", tool="Write"))
        self.assertIsNone(self.edit(".claude/rules/notation-decisions.md"))

    def test_everything_else_denied(self):
        for p in (os.path.join(self.sb.home, "sections", "a.tex"),
                  os.path.join(self.sb.home, "references.bib"),
                  os.path.join(self.sb.other, ".claude", "rules", "notation-decisions.md"),
                  os.path.join(self.sb.root, "domains", "d", "notation.md")):
            with self.subTest(path=p):
                self.assertEqual(self.edit(p), "deny")

    def test_other_agents_silent(self):
        p = os.path.join(self.sb.home, "sections", "a.tex")
        for agent in ("author:math-editor", None, "expert:notation-auditor"):
            with self.subTest(agent=agent):
                self.assertIsNone(self.edit(p, agent=agent))


# ----------------------------------------------------------------------------
# tex_edit_check
# ----------------------------------------------------------------------------

class TexEditCheckTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.sb.set_checker(FINDING, 1)
        self.dirty = os.path.join(self.sb.home, ".build", ".dirty")

    def tearDown(self):
        self.sb.cleanup()

    def edit(self, path):
        ev = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "cwd": self.sb.home,
              "tool_input": {"file_path": path}, "agent_type": "author:math-editor"}
        return run_hook("tex_edit_check.py", ev, self.sb.env)

    def test_section_edit_runs_checker_and_marks_dirty(self):
        code, out, err = self.edit(os.path.join(self.sb.home, "sections", "a.tex"))
        self.assertEqual(code, 0, err)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("sections/a.tex: violations", ctx)
        self.assertIn("lem:x", ctx)
        self.assertTrue(os.path.exists(self.dirty))

    def test_bib_edit_only_marks_dirty(self):
        code, out, _e = self.edit(os.path.join(self.sb.home, "references.bib"))
        self.assertEqual((code, out), (0, None))
        self.assertTrue(os.path.exists(self.dirty))
        self.assertEqual(self.sb.calls("checker_calls.txt"), [])

    def test_outside_the_tex_paths_or_home_is_silent(self):
        for p in (os.path.join(self.sb.home, "Drafts", "notes.tex"),
                  os.path.join(self.sb.other, "x.tex")):
            code, out, _e = self.edit(p)
            self.assertEqual((code, out), (0, None))
        self.assertFalse(os.path.exists(self.dirty))


class HooksJsonTests(unittest.TestCase):
    def test_hooks_json_wires_each_script(self):
        path = os.path.join(os.path.dirname(SCRIPTS), "hooks", "hooks.json")
        with open(path, encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        seen = {}
        for event, groups in hooks.items():
            for g in groups:
                for h in g["hooks"]:
                    script = h["command"].split("/scripts/")[1].rstrip('"')
                    seen[script] = (event, g.get("matcher"))
        self.assertEqual(seen["commit_gate.py"], ("PreToolUse", "Bash|PowerShell"))
        self.assertEqual(seen["bib_gate.py"], ("PreToolUse", "Edit|Write|MultiEdit"))
        self.assertEqual(seen["notation_scope_guard.py"],
                         ("PreToolUse", "Edit|Write|MultiEdit|NotebookEdit"))
        self.assertEqual(seen["tex_edit_check.py"], ("PostToolUse", "Edit|Write|MultiEdit"))
        self.assertEqual(seen["build_gate.py"], ("SubagentStop", None))
        for script in seen:
            self.assertTrue(os.path.isfile(os.path.join(SCRIPTS, script)), script)


if __name__ == "__main__":
    unittest.main()
