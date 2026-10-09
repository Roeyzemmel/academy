"""ship.py merge/publish against the REAL academy commit gate and check_paper.py (I1-I3).

A tiny two-section paper in a temp Author home with a tracked, stale
``Drafts/statements.md``: a gate run that rewrote it would leave the tree dirty, break the
merge rollback and make ``publish`` refuse. Needs the author plugin of this academy
checkout (``author/scripts``); skipped with a message when it is absent.

The checker needs no LaTeX build for these cases (no ``.build/``: the log summary has
nothing to read). Its real ``--strict`` does, though: without a built, fresh PDF (and
pdftohtml) R7 prints an unparseable skip warning, which under ``--strict`` is a non-zero
exit with no finding line, i.e. 'unavailable' -- ``test_real_strict_without_a_pdf_is_unavailable``
pins that down. The other tests therefore set ``author.checker.strictArgs`` to
``["--no-log"]`` (the gate still runs in mode 'strict'; only the checker's warning
promotion is off), which is what makes a clean merge possible without a LaTeX build.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import ship  # noqa: E402
from test_ship import Base  # noqa: E402  (no test methods of its own)
from ship_fixture import run  # noqa: E402

GATE_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "author", "scripts")
HAVE_GATE = all(os.path.isfile(os.path.join(GATE_DIR, f)) for f in ("commit_gate.py", "check_paper.py"))

MAIN = ("\\documentclass{amsart}\n\\begin{document}\n\\section{A}\n\\input{sections/a}\n"
        "\\section{B}\n\\input{sections/b}\n\\end{document}\n")
A = "\\begin{lem}\\label{lem:x}\nA.\n\\end{lem}\n\\begin{proof}\nOk.\n\\end{proof}\n"
B = "\\begin{thm}\\label{thm:y}\nB, by \\cref{lem:x}.\n\\end{thm}\n\\begin{proof}\nOk.\n\\end{proof}\n"
STALE = "stale registry, tracked\n"


@unittest.skipUnless(HAVE_GATE, "no academy checkout at %s: the real gate cannot run" % GATE_DIR)
class RealGateMergeTests(Base):
    def setUp(self):
        super().setUp()
        old = os.environ.get("SHIP_GATE_DIR")
        os.environ["SHIP_GATE_DIR"] = GATE_DIR
        self.addCleanup(lambda: os.environ.pop("SHIP_GATE_DIR", None) if old is None
                        else os.environ.__setitem__("SHIP_GATE_DIR", old))
        self.paper(strict_args=["--no-log"])

    def put(self, rel, text):
        path = os.path.join(self.sub, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def paper(self, strict_args):
        cfg = {"role": "author", "instance": "author@e2e",
               "gate": {"commit": "normal", "baseline": ".claude/paper-gate-baseline.txt",
                        "branches": {"????-??-??/*/*": {"commit": "warn"}}},
               "author": {"checker": {"args": [], "strictArgs": strict_args,
                                      "statements": "Drafts/statements.md"}}}
        for rel, text in ((".claude/academy.json", json.dumps(cfg, indent=2) + "\n"),
                          ("main.tex", MAIN), ("sections/a.tex", A), ("sections/b.tex", B),
                          ("Drafts/statements.md", STALE)):
            self.put(rel, text)
        run(self.sub, "add", "-A")
        run(self.sub, "commit", "-q", "-m", "paper")
        run(self.sub, "push", "-q", "origin", "main")
        self.main_before = run(self.sub, "rev-parse", "main")

    def branch_with(self, topic, files):
        name = ship.branch_name(topic, "author")
        run(self.sub, "switch", "-q", "-c", name, "main")
        for rel, text in files.items():
            self.put(rel, text)
        run(self.sub, "commit", "-q", "-am", topic)
        run(self.sub, "push", "-q", "origin", "HEAD:refs/heads/" + name)
        return name, run(self.sub, "rev-parse", "HEAD")

    def assert_clean_on(self, branch):
        self.assertEqual(run(self.sub, "status", "--porcelain"), "")
        self.assertEqual(ship.current(self.sub), branch)
        self.assertEqual(run(self.sub, "rev-parse", "main"), self.main_before)
        self.assertEqual(run(self.remote, "rev-parse", "main"), self.main_before)
        self.assertEqual(ship.git(self.sub, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False), "")
        with open(os.path.join(self.sub, "Drafts", "statements.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), STALE)

    def test_parse_error_refuses_merge_as_unavailable(self):
        name, tip = self.branch_with("broken", {"main.tex": MAIN.replace("\\section{B}", "\\section{B")})
        rc, _, err = self.ship("merge", "sub", name, "--sha", tip)
        self.assertEqual(rc, 1, err)
        self.assertIn("unavailable", err)
        self.assertIn("PARSE ERROR", err)
        self.assert_clean_on(name)

    def test_strict_refusal_rolls_back_cleanly(self):
        sketched = "\\begin{sketch}\n\\begin{lem}\\label{lem:x}\nA.\n\\end{lem}\n\\end{sketch}\n"
        name, tip = self.branch_with("sketchy", {"sections/a.tex": sketched})
        rc, _, err = self.ship("merge", "sub", name, "--sha", tip)
        self.assertEqual(rc, 1, err)
        self.assertIn("strict gate", err)
        self.assertIn("thm:y: [R1]", err)
        self.assert_clean_on(name)

    def test_merge_then_publish(self):
        more = A + "\\begin{prop}\\label{prop:z}\nC.\n\\end{prop}\n\\begin{proof}\nOk.\n\\end{proof}\n"
        name, tip = self.branch_with("more", {"sections/a.tex": more})
        rc, out, err = self.ship("merge", "sub", name, "--sha", tip)
        self.assertEqual(rc, 0, err)
        self.assertIn("gate: strict, no findings", out)
        self.assertEqual(run(self.sub, "status", "--porcelain"), "")
        merged = run(self.sub, "rev-parse", "main")
        self.assertEqual(run(self.sub, "rev-parse", "main^2"), tip)
        with open(os.path.join(self.sub, "Drafts", "statements.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), STALE)
        rc, out, err = self.ship("publish", "sub", "--sha", merged)
        self.assertEqual(rc, 0, err)
        self.assertEqual(run(self.remote, "rev-parse", "main"), merged)

    def test_real_strict_without_a_pdf_is_unavailable(self):
        cfg_path = os.path.join(self.sub, ".claude", "academy.json")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["author"]["checker"]["strictArgs"] = ["--strict"]
        name, tip = self.branch_with("strict", {".claude/academy.json": json.dumps(cfg, indent=2) + "\n"})
        rc, out, err = self.ship("merge", "sub", name, "--sha", tip)
        self.assertEqual(rc, 1, err)
        self.assertIn("unavailable", err)
        self.assertIn("[R7]", err)
        self.assertIn("gate inputs changed: .claude/academy.json", out)
        self.assert_clean_on(name)


if __name__ == "__main__":
    unittest.main()
