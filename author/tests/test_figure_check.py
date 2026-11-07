"""figure_check.py: the static figure rules and the caption rule (no TeX needed)."""

import os
import sys
import tempfile
import unittest

from fixtures import SCRIPTS

sys.path.insert(0, SCRIPTS)
import figure_check as fc  # noqa: E402


def tmp(text, suffix=".tex"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class StaticTikz(unittest.TestCase):
    def kinds(self, body):
        path = tmp(body)
        try:
            return [s for s, _ in fc.static_tikz(path)]
        finally:
            os.remove(path)

    def test_bare_symbols_pass(self):
        self.assertEqual(self.kinds(r"\node at ({2*cos(45)},0) {$v_1$}; \node[below] {(a)};"), [])

    def test_running_text_fails(self):
        self.assertIn("V", self.kinds(r"\node at (0,0) {copy 1: the chart of the first copy};"))

    def test_table_fails(self):
        self.assertIn("V", self.kinds(r"\node {\begin{tabular}{cc} a & b \end{tabular}};"))

    def test_tiny_warns_only(self):
        self.assertEqual(self.kinds(r"\node {\tiny $v$};"), ["W"])

    def test_comments_ignored(self):
        self.assertEqual(self.kinds("% \node {a long sentence of words here}\n"), [])


class Captions(unittest.TestCase):
    def check(self, caption):
        path = tmp(r"\begin{figure}\caption{%s}\label{fig:x}\end{figure}" % caption)
        try:
            return fc.captions(path)
        finally:
            os.remove(path)

    def test_short_passes(self):
        self.assertEqual(self.check("The double of $P$ (\cref{lem:a}). (a) The triangle."), [])

    def test_long_fails(self):
        self.assertTrue(self.check(" ".join(["Word."] * 6)))
        self.assertTrue(self.check("A " + "word " * 100 + "."))


if __name__ == "__main__":
    unittest.main()
