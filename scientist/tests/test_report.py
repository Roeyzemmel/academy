"""report.py: the refusals, a rendered example from real FlatSurfLab results, and
filing the packet plus the review ticket on a temporary board."""

import os
import re
import unittest

from helpers import Sandbox, EW, TORUS, FIXTURES

import _common as c
import report
from _academy import read_frontmatter, validate_packet, validate_ticket

EXPECTED = os.path.join(FIXTURES, "expected", "report-%s.md" % EW)
CONCLUSION = """## Conclusion

- **Establishes:** %s -- the thing, in words.
- **Does not establish:** anything beyond the class.
- **Proposed status:** lab:q2-ew-ornithorynque -> %s
- **Next step:** review.
"""


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.lab = c.resolve_lab(self.sb.lab)

    def tearDown(self):
        self.sb.close()

    def gather(self, stem=EW, **kw):
        return report.gather("experiments/%s.py" % stem, self.lab, **kw)

    def refused(self, stem=EW, **kw):
        with self.assertRaises(report.Refused) as cm:
            self.gather(stem, **kw)
        return " | ".join(cm.exception.problems)

    def draft(self, text, stem=EW):
        return self.sb.write("reports/%s.md" % stem, text)

    # -- refusals ------------------------------------------------------------

    def test_refuses_without_experiment_type(self):
        path = os.path.join(self.sb.lab, "experiments", "%s.py" % EW)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(re.sub(r"\nKind:[^\n]*", "", text, count=1))
        msg = self.refused()
        self.assertIn("no experiment type", msg)

    def test_type_from_flag_when_header_has_none(self):
        path = os.path.join(self.sb.lab, "experiments", "%s.py" % EW)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(re.sub(r"\nKind:[^\n]*", "", text, count=1))
        ctx = self.gather(rtype="verify")
        self.assertEqual(ctx["type"], "verify")

    def test_refuses_type_flag_against_header(self):
        self.assertIn("disagrees with the header", self.refused(rtype="search"))

    def test_refuses_without_conclusion(self):
        self.draft("## Validation\n\n- Reproduced: yes\n")
        msg = self.refused()
        self.assertIn("no ## Conclusion", msg)

    def test_refuses_without_draft(self):
        os.remove(os.path.join(self.sb.lab, "reports", "%s.md" % EW))
        self.assertIn("no report draft", self.refused())

    def test_refuses_missing_conclusion_lines(self):
        self.draft("## Validation\n\n- Reproduced: yes\n\n## Conclusion\n\n"
                   "- **Establishes:** supports -- x\n")
        msg = self.refused()
        for label in ("Does not establish", "Proposed status", "Next step"):
            self.assertIn("'%s:'" % label, msg)

    def test_refuses_proved_from_a_computation(self):
        self.draft("## Validation\n\n- Reproduced: yes\n\n" + CONCLUSION % ("supports", "proved"))
        self.assertIn("cannot propose 'proved'", self.refused())

    def test_refuses_bad_establishes_word(self):
        self.draft("## Validation\n\n- Reproduced: yes\n\n" + CONCLUSION % ("confirms", "supported"))
        self.assertIn("must begin with supports, refutes or inconclusive", self.refused())

    def test_refuses_mismatched_status(self):
        self.draft("## Validation\n\n- Reproduced: yes\n\n" + CONCLUSION % ("refutes", "supported"))
        self.assertIn("does not fit the proposed status", self.refused())

    def test_failed_validation_forces_inconclusive(self):
        self.draft("## Validation\n\n- Reproduced: no\n\n" + CONCLUSION % ("supports", "supported"))
        self.assertIn("must be inconclusive", self.refused())
        self.draft("## Validation\n\n- Reproduced: no\n\n" + CONCLUSION % ("inconclusive", "open"))
        self.assertFalse(self.gather()["reproduced"])

    def test_refuses_unknown_validation(self):
        self.draft(CONCLUSION % ("supports", "supported"))
        self.assertIn("validation case reproduced is unknown", self.refused())

    def test_refuses_unknown_env_profile(self):
        self.assertIn("not in scientist.envs", self.refused(env="nowhere"))

    def test_refuses_without_result(self):
        os.remove(os.path.join(self.sb.lab, "results", "%s.json" % EW))
        self.assertIn("no result JSON", self.refused())

    def test_refuses_outcome_kind_mismatch(self):
        path = os.path.join(self.sb.lab, "experiments", "%s.py" % EW)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text.replace("Kind:           verify", "Kind:           measure", 1))
        self.draft("## Validation\n\n- Reproduced: yes\n\n## Class\n\nCannot contain: x\n\n"
                   + CONCLUSION % ("supports", "supported"))
        self.assertIn("outcome is a verify", self.refused())

    def test_refuses_unknown_draft_section(self):
        self.draft("## Validation\n\n- Reproduced: yes\n\n## Certificate\n\nx\n\n"
                   + CONCLUSION % ("supports", "supported"))
        self.assertIn("'## Certificate' a verify report does not take", self.refused())

    def test_cli_exit_code_and_message(self):
        os.remove(os.path.join(self.sb.lab, "reports", "%s.md" % EW))
        code, out, err = self.sb.run("report.py", ["check", "experiments/%s.py" % EW,
                                                   "--home", self.sb.lab])
        self.assertEqual(code, 2)
        self.assertIn("refused:", err)
        self.assertIn("no report draft", err)

    # -- rendering -----------------------------------------------------------

    def test_renders_verify_report_golden(self):
        meta, body = report.render(self.gather())
        self.assertEqual(meta["kind"], "experiment-report")
        self.assertEqual(meta["subject"], ["lab:q2-ew-ornithorynque", "s1:Q2"])
        self.assertIsNone(meta["status_proposed"])       # two claims in the subject
        heads = [ln for ln in body.splitlines() if ln.startswith("## ")]
        self.assertEqual(heads, ["## Summary", "## Produced", "## Established vs assumed",
                                 "## Evidence", "## Question", "## Class", "## Method",
                                 "## Environment", "## Validation", "## Object", "## Check",
                                 "## Raw outcome", "## Conclusion", "## Decisions needed",
                                 "## Machine notes", "## Decision"])
        self.assertIn("| EW: W complete | holds |", body)
        self.assertIn("commit `a929eca`", body)
        self.assertIn("**Cannot contain:** any other origami", body)
        with open(EXPECTED, encoding="utf-8") as fh:
            self.assertEqual(body.lstrip("\n"), fh.read())

    def test_renders_measure_report(self):
        meta, body = report.render(self.gather(TORUS))
        self.assertEqual(meta["status_proposed"], "supported")
        self.assertIn("## Quantity", body)
        self.assertIn("Distribution: values for 4 member(s)", body)
        self.assertIn("double pentagon (Fraction-only module)", body)   # outcome.class.excluded
        self.assertIn("2 distinct marked tori", body)                    # the draft's addition
        summary = body.split("## Produced")[0]
        self.assertIn("Measure experiment on four torus covers", summary)
        probs = validate_packet({"packet": "P-0001", "title": meta["title"],
                                 "instance": "scientist@ts", "kind": meta["kind"],
                                 "by": "scientist@ts", "state": "open",
                                 "created": "2026-09-28", "subject": meta["subject"],
                                 "status_proposed": meta["status_proposed"]}, body)
        self.assertEqual(probs, [])

    def test_probe_report(self):
        self.sb.write("scratch/probe_sizes.py", '"""How large do the orbits get?\n\n'
                      'Kind:           probe\nClaims:         lab:q2-ew-ornithorynque\n'
                      'Goal:           how many states the BFS visits for n <= 12\n'
                      'Decides:        whether the n = 16 search fits one lingo job\n"""\n')
        self.sb.write("reports/probe_sizes.md",
                      "## Class\n\nCannot contain: n > 12\n\n## Validation\n\n"
                      "- Reproduced: yes (n = 8 gives the known 24 states)\n\n"
                      "## Raw outcome\n\nn = 8: 24 states; n = 12: 648 states.\n\n"
                      + CONCLUSION.replace("lab:q2-ew-ornithorynque -> %s",
                                           "lab:q2-ew-ornithorynque -> open")
                      % "inconclusive")
        ctx = report.gather("scratch/probe_sizes.py", self.lab, env="laptop-wsl")
        meta, body = report.render(ctx)
        self.assertIn("## Decides", body)
        self.assertIn("648 states", body)

    def test_probe_needs_decides(self):
        self.sb.write("scratch/probe_x.py", '"""x\n\nKind: probe\nClaims: lab:x\n'
                      'Goal: y\n"""\n')
        self.sb.write("reports/probe_x.md", "## Raw outcome\n\nz\n\n## Class\n\n"
                      "Cannot contain: w\n\n## Validation\n\nReproduced: yes\n\n"
                      + CONCLUSION.replace("lab:q2-ew-ornithorynque -> %s", "lab:x -> open")
                      % "inconclusive")
        with self.assertRaises(report.Refused) as cm:
            report.gather("scratch/probe_x.py", self.lab)
        self.assertIn("Decides:", " ".join(cm.exception.problems))

    # -- filing --------------------------------------------------------------

    def test_file_writes_packet_and_review_ticket(self):
        ctx = self.gather()
        meta, body = report.render(ctx)
        res = report.file_report(ctx, meta, body, board=self.sb.board,
                                 workspace=self.sb.workspace)
        self.assertEqual(res["reviewer"], "researcher@slope1")
        self.assertIn("s1:Q2", res["reviewer_because"])
        with open(res["packet_path"], encoding="utf-8") as fh:
            pm, pb = read_frontmatter(fh.read())
        self.assertEqual(pm["kind"], "experiment-report")
        self.assertEqual(pm["by"], "scientist@ts/experimenter")
        self.assertEqual(validate_packet(pm, pb), [])
        self.assertIn(os.path.join("packets", "scientist@ts"), os.path.normpath(
            res["packet_path"]))
        with open(res["ticket_path"], encoding="utf-8") as fh:
            tm, tb = read_frontmatter(fh.read())
        self.assertEqual(validate_ticket(tm, tb), [])
        self.assertEqual(tm["kind"], "review-experiment")
        self.assertEqual(tm["from"], "scientist@ts")
        self.assertEqual(tm["to"], "researcher@slope1")
        self.assertIn(res["packet"], tm["refs"])
        self.assertIn("lab:q2-ew-ornithorynque", tm["refs"])
        self.assertEqual(tm["budget"], {"runs": 2, "max_model": "fable"})
        self.assertIn("scientist@ts/experimenter: opened", tb)

    def test_route_by_lab_config_when_no_namespace_matches(self):
        ctx = self.gather(TORUS)                   # only lab: claims
        meta, body = report.render(ctx)
        res = report.file_report(ctx, meta, body, board=self.sb.board,
                                 workspace=self.sb.workspace, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["reviewer"], "researcher@slope1")
        self.assertIn("names scientist@ts as its lab", res["reviewer_because"])
        self.assertEqual(os.listdir(os.path.join(self.sb.board, "researcher@slope1")), [])

    def test_route_refuses_non_researcher(self):
        from _academy import load_workspace
        with self.assertRaises(report.Refused):
            report.route_reviewer(load_workspace(self.sb.workspace), "scientist@ts",
                                  ["lab:x"], to="author@bi")

    def test_cli_file_links_commissioning_ticket(self):
        boardlib = report._academy_module("board")    # academy's board.py
        tpath = boardlib.create_ticket(self.sb.board, "scientist@ts", "Run the EW record",
                                       "Record (Q2) on the EW", "A report packet",
                                       kind="experiment", as_instance="researcher@slope1")
        tid = os.path.basename(tpath)[:6]
        code, out, err = self.sb.run("report.py", [
            "file", "experiments/%s.py" % EW, "--home", self.sb.lab, "--board",
            self.sb.board, "--ticket", tid])
        self.assertEqual(code, 0, err)
        with open(tpath, encoding="utf-8") as fh:
            tm, tb = read_frontmatter(fh.read())
        self.assertEqual(len(tm["packets"]), 1)
        rev = os.listdir(os.path.join(self.sb.board, "researcher@slope1"))
        self.assertEqual(len(rev), 1)
        with open(os.path.join(self.sb.board, "researcher@slope1", rev[0]),
                  encoding="utf-8") as fh:
            rm, _ = read_frontmatter(fh.read())
        self.assertEqual(rm["parent"], tid)

    def test_cli_file_ask_prefix(self):
        code, out, err = self.sb.run("report.py", [
            "file", "experiments/%s.py" % EW, "--home", self.sb.lab, "--board",
            self.sb.board, "--ask-prefix", "dry-run: migration test"])
        self.assertEqual(code, 0, err)
        rev = os.listdir(os.path.join(self.sb.board, "researcher@slope1"))
        with open(os.path.join(self.sb.board, "researcher@slope1", rev[0]),
                  encoding="utf-8") as fh:
            rm, rb = read_frontmatter(fh.read())
        self.assertTrue(rm["ask"].startswith("dry-run: migration test -- Review experiment"),
                        rm["ask"])
        self.assertEqual(validate_ticket(rm, rb), [])


if __name__ == "__main__":
    unittest.main()
