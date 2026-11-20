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

    def test_where_is_one_line_per_label(self):
        rc, out, _err = self.run_cli("paper:lem:lift", "--where")
        self.assertEqual(0, rc)
        rec = st.find(self.home, {}, "lem:lift", proof=True)
        self.assertEqual("lem:lift: sections/flat.tex lines 4-9, proof lines %d-%d\n"
                         % tuple(rec["proof"]["lines"]), out)
        self.assertEqual("x: f.tex lines 1-2, no proof environment follows",
                         st.where_line({"label": "x", "file": "f.tex", "lines": [1, 2]}))
        rc, out, err = self.run_cli("lem:nowhere", "--where")
        self.assertEqual((1, ""), (rc, out))

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

    def test_a_proof_in_its_own_wrapper_is_found(self):
        """#113: the statement and its proof each wrapped (\\end{lem} \\end{sketch}
        \\end{added} | \\begin{added} \\begin{sketch} \\begin{proof}); a sketch with no
        proof inside is the proof itself; another statement after a wrapper is not."""
        text = ("\\begin{added}\n\\begin{sketch}\n\\begin{lem}\\label{lem:a} A.\\end{lem}\n\\end{sketch}\n\\end{added}\n\n"
                "\\begin{added} %% lead-proof\n\\begin{sketch}\n\\begin{proof} P. \\end{proof}\n\\end{sketch}\n\\end{added}\n")
        end = text.index("\\end{lem}") + len("\\end{lem}")
        start, stop = st.proof_span(text, end)
        self.assertEqual(text[start:stop], "\\begin{proof} P. \\end{proof}")
        old = "\\begin{lem} B.\\end{lem}\n\\begin{sketch} S. \\end{sketch}\n"
        e2 = old.index("\\end{lem}") + len("\\end{lem}")
        start, stop = st.proof_span(old, e2)
        self.assertEqual(old[start:stop], "\\begin{sketch} S. \\end{sketch}")
        nxt = "\\begin{lem} C.\\end{lem}\n\\end{sketch}\n\\begin{sketch}\n\\begin{lem} D.\\end{lem}\n"
        self.assertIsNone(st.proof_span(nxt, nxt.index("\\end{lem}") + len("\\end{lem}")))
        self.assertEqual(st.wrappers({"author": {"statusLevels": [{"env": "colour"}, {"env": None}],
                                                 "provenance": {"env": "prov"}}}),
                         ("added", "colour", "conjectural", "meta", "prov", "sketch"))
        # review of e2a213a: after the statement's wrapper closed, a sketch around prose is
        # the next paragraph's colour (live: defn:marked-moduli got a paragraph as its proof)
        prose = ("\\begin{defn}\\label{a} x\\end{defn}\n\\end{sketch}\n\\begin{added}\n\\begin{sketch}\n"
                 "A remark in prose.\n\\end{sketch}\n\\end{added}")
        self.assertIsNone(st.proof_span(prose, prose.index("\\end{defn}") + len("\\end{defn}")))
        # a bare sketch proof may begin with a list or a display
        lst = "\\begin{lem} L.\\end{lem}\n\\begin{sketch}\n\\begin{itemize}\\item a\\end{itemize}\n\\end{sketch}\n"
        start, stop = st.proof_span(lst, lst.index("\\end{lem}") + len("\\end{lem}"))
        self.assertTrue(lst[start:stop].startswith("\\begin{sketch}") and lst[start:stop].endswith("\\end{sketch}"))

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

    def test_commented_out_and_verbatim_statements_are_not_statements(self):
        # 2026-11-13: ten commented-out or quoted statements were listed as live ones
        tex = ("%% \\begin{lem}\\label{lem:dead} An old version. \\end{lem}\n"
               "% \\begin{lem}\\label{lem:lift} A commented copy of a live label.\n"
               "% \\end{lem}\n"
               "\\begin{verbatim}\n  \\begin{prop} \\label{prop:foo} ... \\end{prop}\n\\end{verbatim}\n"
               "Costs 5\\% more.\n" + TEX)
        with open(os.path.join(self.home, "sections", "flat.tex"), "w", newline="") as fh:
            fh.write(tex)
        self.assertIsNone(st.find(self.home, {}, "lem:dead"))
        self.assertIsNone(st.find(self.home, {}, "prop:foo"))
        rec = st.find(self.home, {}, "lem:lift", proof=True)
        self.assertEqual([4 + 7, 9 + 7], rec["lines"])          # the live one, seven lines down
        self.assertTrue(rec["text"].startswith("\\begin{lem}[Lifting]"))
        labels = [r["label"] for r in st.outline(self.home, {}, os.path.join(
            self.home, "sections", "flat.tex"))["rows"] if "label" in r]
        self.assertEqual(["lem:lift", "prop:free"], labels)
        self.assertNotIn("lem:dead", st.all_labels(self.home, {}))

    def test_a_file_the_paper_does_not_input_is_said_to_be_so(self):
        with open(os.path.join(self.home, "sections", "old.tex"), "w", newline="") as fh:
            fh.write("\\begin{lem}\\label{lem:old} Left behind.\n\\end{lem}\n")
        rec = st.find(self.home, {}, "lem:old")
        self.assertIn("not \\input by the paper's main file", rec["note"])
        self.assertNotIn("note", st.find(self.home, {}, "lem:lift"))
        rc, out, err = self.run_cli("--outline", "sections/old.tex")
        self.assertIn("note: this file is not", out)
        self.assertNotIn("note:", self.run_cli("--outline", "sections/flat.tex")[1])

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
