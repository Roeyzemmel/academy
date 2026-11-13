"""statement.py: one statement by its label, with its lines and proof, and a file's map
(so an agent never has to Read a whole section; the 2026-11-13 ledger review)."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import statement as st  # noqa: E402

TEX = """\\section{Flat}
Some words.

\\begin{lem}[Lifting]\\label{lem:lift}
Let $X$ be compact. Then every morphism lifts
\\begin{enumerate}
\\item\\label{it:one} uniquely;
\\end{enumerate}
\\end{lem}
% a comment between

\\begin{proof}
First \\begin{proof} nested \\end{proof} then done.
\\end{proof}

\\subsection{More}
\\begin{prop}\\label{prop:free}
No proof follows.
\\end{prop}
Text, then an unrelated proof far away.
\\begin{proof} of something else \\end{proof}
"""


class Statement(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="stmt-")
        self.addCleanup(shutil.rmtree, self.home, True)
        os.makedirs(os.path.join(self.home, "sections"))
        with open(os.path.join(self.home, "main.tex"), "w") as fh:
            fh.write("\\input{sections/flat}\n")
        with open(os.path.join(self.home, "sections", "flat.tex"), "w", newline="") as fh:
            fh.write(TEX)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = st.main(list(args) + ["--home", self.home])
        return rc, out.getvalue(), err.getvalue()

    def test_a_statement_with_its_lines_and_proof(self):
        rec = st.find(self.home, {}, "lem:lift", proof=True, context=1)
        self.assertEqual(("sections/flat.tex", "lem", [4, 9]),
                         (rec["file"], rec["env"], rec["lines"]))
        self.assertTrue(rec["text"].startswith("\\begin{lem}[Lifting]"))
        self.assertTrue(rec["text"].endswith("\\end{lem}"))
        self.assertEqual([12, 14], rec["proof"]["lines"])          # the nested proof is inside
        self.assertTrue(rec["proof"]["text"].endswith("then done.\n\\end{proof}"))
        self.assertEqual("", rec["before"])
        self.assertEqual("", rec["after"])
        # a label inside the statement finds the statement
        self.assertEqual([4, 9], st.find(self.home, {}, "it:one")["lines"])

    def test_only_a_proof_that_follows_at_once_is_the_statements(self):
        rec = st.find(self.home, {}, "prop:free", proof=True)
        self.assertNotIn("proof", rec)

    def test_cli_found_missing_and_namespace(self):
        rc, out, err = self.run_cli("paper:lem:lift", "--proof")
        self.assertEqual(0, rc, err)
        self.assertIn("lem:lift  sections/flat.tex:4-9  (lem)", out)
        self.assertIn("--- proof  lines 12-14", out)
        rc, out, err = self.run_cli("lem:lift", "lem:lfit", "--json")
        self.assertEqual(1, rc)
        data = json.loads(out)
        self.assertEqual((["lem:lift"], ["lem:lfit"]),
                         ([r["label"] for r in data["found"]], data["missing"]))
        self.assertIn("near: lem:lift", err)
        self.assertEqual(2, self.run_cli()[0])

    def test_outline_is_the_map_of_a_file(self):
        rc, out, err = self.run_cli("--outline", "sections/flat.tex")
        self.assertEqual(0, rc, err)
        rows = out.splitlines()
        self.assertIn("(21 lines)", rows[0])
        self.assertEqual(["    1        \\section{Flat}",
                          "    4-9     lem    lem:lift  + proof 12-14",
                          "   16        \\subsection{More}",
                          "   17-19    prop   prop:free"], rows[1:])
        self.assertEqual(2, self.run_cli("--outline", "sections/none.tex")[0])


if __name__ == "__main__":
    unittest.main()
