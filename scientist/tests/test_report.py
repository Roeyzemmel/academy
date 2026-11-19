"""report.py: the refusals, a rendered example from real SciLab results, and
filing the packet plus the review ticket on a temporary board."""

import json
import os
import re
import sys
import unittest

from helpers import Sandbox, EW, TORUS, FIXTURES, PLUGIN

import _common as c
import report
from _academy import read_frontmatter, validate_packet, validate_ticket

#: academy/lib, where the GitHub store and its in-memory transport live
ACADEMY_LIB = os.path.join(os.path.dirname(PLUGIN), "academy", "lib")

#: a ``board.transport`` factory for the CLI test: a MemoryTransport seeded from the file
#: board at ``cfg['seed']``, written back to ``cfg['dump']`` when the process exits
FAKE_GH = """import atexit, json, board_store as bs
def transport(cfg):
    t = bs.from_file_board(cfg['seed'])
    def dump():
        rows = [dict(i, comments=list(t.comments.get(n, [])))
                for n, i in sorted(t.issues.items())]
        with open(cfg['dump'], 'w', encoding='utf-8') as fh:
            json.dump(rows, fh)
    atexit.register(dump)
    return t
"""

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
                                 "instance": "scientist@main", "kind": meta["kind"],
                                 "by": "scientist@main", "state": "open",
                                 "created": "2026-09-28", "subject": meta["subject"],
                                 "status_proposed": meta["status_proposed"]}, body)
        self.assertEqual(probs, [])

    # -- provenance written by the lab's env.save_result (T-0735) ------------------

    def provenance(self, **extra):
        path = os.path.join(self.sb.lab, "results", EW + ".json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["provenance"].update(extra)
        self.sb.write_json(path, data)

    @staticmethod
    def section(body, name):
        return body.split("## %s\n" % name, 1)[1].split("\n## ", 1)[0]

    def test_saved_is_not_listed_as_a_version(self):
        self.provenance(saved="2026-11-17T10:00:00")
        meta, body = report.render(self.gather())
        envsec = self.section(body, "Environment")
        self.assertIn("- Versions: python 3.12.14, sage 10.7", envsec)
        self.assertNotIn("saved", envsec)

    def test_git_at_save_is_shown_and_noted(self):
        self.provenance(saved="2026-11-17T10:00:00",
                        git_at_save={"commit": "b2c3d4e", "dirty": True,
                                     "modified": ["pkg/x.py"], "untracked": [],
                                     "diff_sha256": "0" * 64})
        meta, body = report.render(self.gather())
        envsec = self.section(body, "Environment")
        self.assertIn("- Commit: `a929eca`\n", envsec)
        self.assertIn("- Git state at save: commit `b2c3d4e` (dirty tree); the result "
                      "records the start state", envsec)
        notes = self.section(body, "Machine notes")
        self.assertIn("the git state changed during the run (start commit a929eca, at "
                      "save b2c3d4e)", notes)

    def test_no_git_at_save_no_line(self):
        meta, body = report.render(self.gather())
        self.assertNotIn("at save", body)

    def test_probe_report(self):
        self.sb.write("scratch/probe_sizes.py", '"""How large do the orbits get?\n\n'
                      'Kind:           probe\nClaims:         lab:q2-ew-ornithorynque\n'
                      'Goal:           how many states the BFS visits for n <= 12\n'
                      'Decides:        whether the n = 16 search fits one remote job\n"""\n')
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
        self.assertEqual(res["reviewer"], "researcher@alpha")
        self.assertIn("s1:Q2", res["reviewer_because"])
        with open(res["packet_path"], encoding="utf-8") as fh:
            pm, pb = read_frontmatter(fh.read())
        self.assertEqual(pm["kind"], "experiment-report")
        self.assertEqual(pm["by"], "scientist@main/experimenter")
        self.assertEqual(validate_packet(pm, pb), [])
        self.assertIn(os.path.join("packets", "scientist@main"), os.path.normpath(
            res["packet_path"]))
        with open(res["ticket_path"], encoding="utf-8") as fh:
            tm, tb = read_frontmatter(fh.read())
        self.assertEqual(validate_ticket(tm, tb), [])
        self.assertEqual(tm["kind"], "review-experiment")
        self.assertEqual(tm["from"], "scientist@main")
        self.assertEqual(tm["to"], "researcher@alpha")
        self.assertIn(res["packet"], tm["refs"])
        self.assertIn("lab:q2-ew-ornithorynque", tm["refs"])
        self.assertEqual(tm["budget"], {"runs": 2, "max_model": "fable"})
        self.assertIn("scientist@main/experimenter: opened", tb)

    def test_route_by_lab_config_when_no_namespace_matches(self):
        ctx = self.gather(TORUS)                   # only lab: claims
        meta, body = report.render(ctx)
        res = report.file_report(ctx, meta, body, board=self.sb.board,
                                 workspace=self.sb.workspace, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["reviewer"], "researcher@alpha")
        self.assertIn("names scientist@main as its lab", res["reviewer_because"])
        self.assertEqual(os.listdir(os.path.join(self.sb.board, "researcher@alpha")), [])

    def test_route_refuses_non_researcher(self):
        from _academy import load_workspace
        with self.assertRaises(report.Refused):
            report.route_reviewer(load_workspace(self.sb.workspace), "scientist@main",
                                  ["lab:x"], to="author@main")

    def test_cli_file_links_commissioning_ticket(self):
        boardlib = report._academy_module("board")    # academy's board.py
        tpath = boardlib.create_ticket(self.sb.board, "scientist@main", "Run the EW record",
                                       "Record (Q2) on the EW", "A report packet",
                                       kind="experiment", as_instance="researcher@alpha")
        tid = os.path.basename(tpath)[:6]
        code, out, err = self.sb.run("report.py", [
            "file", "experiments/%s.py" % EW, "--home", self.sb.lab, "--board",
            self.sb.board, "--ticket", tid])
        self.assertEqual(code, 0, err)
        with open(tpath, encoding="utf-8") as fh:
            tm, tb = read_frontmatter(fh.read())
        self.assertEqual(len(tm["packets"]), 1)
        rev = os.listdir(os.path.join(self.sb.board, "researcher@alpha"))
        self.assertEqual(len(rev), 1)
        with open(os.path.join(self.sb.board, "researcher@alpha", rev[0]),
                  encoding="utf-8") as fh:
            rm, _ = read_frontmatter(fh.read())
        self.assertEqual(rm["parent"], tid)

    def test_cli_file_ask_prefix(self):
        code, out, err = self.sb.run("report.py", [
            "file", "experiments/%s.py" % EW, "--home", self.sb.lab, "--board",
            self.sb.board, "--ask-prefix", "dry-run: migration test"])
        self.assertEqual(code, 0, err)
        rev = os.listdir(os.path.join(self.sb.board, "researcher@alpha"))
        with open(os.path.join(self.sb.board, "researcher@alpha", rev[0]),
                  encoding="utf-8") as fh:
            rm, rb = read_frontmatter(fh.read())
        self.assertTrue(rm["ask"].startswith("dry-run: migration test -- Review experiment"),
                        rm["ask"])
        self.assertEqual(validate_ticket(rm, rb), [])


    # -- filing on the GitHub backend (T-1156) --------------------------------

    def github_workspace(self, **extra):
        """Switch the sandbox workspace to ``board.backend`` github; the file board stays
        the directory of packets and ids (and, after a migration, the frozen snapshot)."""
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["board"] = dict({"path": self.sb.board, "backend": "github", "repo": "o/r"},
                           **extra)
        self.sb.write_json(self.sb.workspace, ws)

    def memory_store(self):
        if ACADEMY_LIB not in sys.path:
            sys.path.insert(0, ACADEMY_LIB)
        import board_store as bs
        transport = bs.MemoryTransport()
        boardlib = report._academy_module("board")
        return transport, boardlib.resolve_store(None, self.sb.workspace, transport=transport)

    def snapshot_tickets(self):
        return sorted(f for d in ("scientist@main", "researcher@alpha")
                      for f in os.listdir(os.path.join(self.sb.board, d)))

    def test_file_on_github_backend_uses_the_issues(self):
        self.github_workspace()
        transport, store = self.memory_store()
        boardlib = report._academy_module("board")
        cref = boardlib.create_ticket(store, "scientist@main", "Run the EW record",
                                      "Record (Q2) on the EW", "A report packet",
                                      kind="experiment", as_instance="researcher@alpha")
        self.assertEqual(cref, "github#1")
        cid = "T-0001"
        ctx = self.gather()
        meta, body = report.render(ctx)
        res = report.file_report(ctx, meta, body, workspace=self.sb.workspace, ticket=cid,
                                 transport=transport)
        self.assertEqual(res["backend"], "github")
        self.assertEqual(res["ticket"], "T-0002")
        self.assertEqual(res["ticket_path"], "github#2")
        _ref, tm, tb = store.get(res["ticket"])
        self.assertEqual(validate_ticket(tm, tb), [])
        self.assertEqual(tm["kind"], "review-experiment")
        self.assertEqual(tm["to"], "researcher@alpha")
        self.assertEqual(tm["parent"], cid)
        self.assertIn(res["packet"], tm["refs"])
        _ref, cm, cb = store.get(cid)
        self.assertEqual(cm["packets"], [res["packet"]])
        self.assertIn("packet %s filed" % res["packet"], cb)
        with open(res["packet_path"], encoding="utf-8") as fh:
            pm, pb = read_frontmatter(fh.read())
        self.assertEqual(pm["ticket"], cid)
        self.assertEqual(validate_packet(pm, pb), [])
        self.assertEqual(self.snapshot_tickets(), [])      # nothing on the file board

    def test_file_dry_run_names_the_backend_without_opening_it(self):
        self.github_workspace()                 # no transport: opening the store would fail
        ctx = self.gather()
        meta, body = report.render(ctx)
        res = report.file_report(ctx, meta, body, workspace=self.sb.workspace, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["backend"], "github")

    def test_file_on_github_backend_without_transport_is_an_error(self):
        self.github_workspace()
        ctx = self.gather()
        meta, body = report.render(ctx)
        with self.assertRaises(report.ac.AcademyError):
            report.file_report(ctx, meta, body, workspace=self.sb.workspace)
        self.assertEqual(self.snapshot_tickets(), [])
        self.assertEqual(os.listdir(os.path.join(self.sb.board, "packets")), [])

    def test_cli_file_on_github_backend_without_transport_is_an_error_not_a_traceback(self):
        self.github_workspace()
        code, out, err = self.sb.run("report.py", [
            "file", "experiments/%s.py" % EW, "--home", self.sb.lab])
        self.assertEqual(code, 2, err)
        self.assertTrue(err.startswith("error: "), err)
        self.assertIn("no transport", err)
        self.assertNotIn("Traceback", err)

    def test_library_error_from_create_ticket_names_the_orphan_packet(self):
        """An error of the academy library (not the vendored copy) from create_ticket,
        e.g. a refused edge, still becomes the 'packet written, ticket not' error."""
        self.github_workspace()
        transport, _store = self.memory_store()
        boardlib = report._academy_module("board")

        def refuse(*a, **k):
            raise boardlib.ac.ConfigError("edge refused")

        orig = boardlib.create_ticket
        boardlib.create_ticket = refuse
        try:
            ctx = self.gather()
            meta, body = report.render(ctx)
            with self.assertRaises(report.ac.AcademyError) as cm:
                report.file_report(ctx, meta, body, workspace=self.sb.workspace,
                                   transport=transport)
        finally:
            boardlib.create_ticket = orig
        msg = str(cm.exception)
        self.assertIn("but the review ticket was not: edge refused", msg)
        self.assertRegex(msg, r"packet P-\d+ was written")

    def test_cli_file_on_github_backend(self):
        """The case of T-1117: the commissioning ticket is an issue only, the file board
        is the frozen snapshot; ``report.py file`` (no --board) files on the issues."""
        seed = os.path.join(self.sb.root, "seed")
        for d in ("scientist@main", "researcher@alpha", "packets"):
            os.makedirs(os.path.join(seed, d))
        boardlib = report._academy_module("board")
        boardlib.create_ticket(seed, "scientist@main", "Run the EW record",
                               "Record (Q2) on the EW", "A report packet",
                               kind="experiment", as_instance="researcher@alpha")
        mods = os.path.join(self.sb.root, "mods")
        self.sb.write(os.path.join(mods, "fake_gh_report.py"), FAKE_GH)
        dump = os.path.join(self.sb.root, "issues.json")
        self.github_workspace(transport="fake_gh_report:transport", seed=seed, dump=dump)
        self.sb.env = dict(self.sb.env, ACADEMY_BOARD_CACHE="0", PYTHONPATH=os.pathsep.join(
            [mods, ACADEMY_LIB]))
        code, out, err = self.sb.run("report.py", [
            "file", "experiments/%s.py" % EW, "--home", self.sb.lab, "--ticket", "T-0001"])
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        self.assertEqual((res["ticket"], res["ticket_path"]), ("T-0002", "github#2"))
        self.assertEqual(self.snapshot_tickets(), [])
        if ACADEMY_LIB not in sys.path:
            sys.path.insert(0, ACADEMY_LIB)
        import board_store as bs
        transport = bs.MemoryTransport()
        with open(dump, encoding="utf-8") as fh:
            for e in json.load(fh):
                transport.add_encoded(e)
        _t, store = (transport, report._academy_module("board").resolve_store(
            None, self.sb.workspace, transport=transport))
        _r, rm, _b = store.get("T-0002")
        self.assertEqual((rm["kind"], rm["to"], rm["parent"]),
                         ("review-experiment", "researcher@alpha", "T-0001"))
        self.assertEqual(store.get("T-0001")[1]["packets"], [res["packet"]])


if __name__ == "__main__":
    unittest.main()
