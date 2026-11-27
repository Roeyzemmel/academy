"""#137: the reword marks never move a statement hash.

A settled statement reworded after its review carries generated marks (``\\Reworded{x}``
for the words changed since the reviewed text, ``\\Struck{x}`` for the words removed;
``author/scripts/reword_marks.py``). Every hash of a statement ignores them --
``\\Reworded{x}`` hashes as ``x``, ``\\Struck{x}`` as nothing -- so generating or removing
them changes no ``statement_hash``: the engine's ``statement_hash_of``, the paper store's
statement text and item hashes, the Expert's ``decision_table.statement_hash`` (and its
fallback) and the Author's ``pinned.statement_hash`` agree on a marked statement and its
unmarked current text. Nothing else is ignored (#136 item 3 is the human's to decide).
"""
import importlib.util
import sys
import unittest
from pathlib import Path

from _util import Homes, write, ENGINE

import registry
from registry.core import federation, model

REPO = ENGINE.parent
UNMARKED = ("\\begin{prop}\\label{prop:foo}\n"
            "Every closed $x$ is very fine, and $y \\in \\{0, 1\\}$.\n"
            "\\end{prop}")
MARKED = ("\\begin{prop}\\label{prop:foo}\n"
          "Every \\Reworded{closed} $x$ is \\Struck{quite} \\Reworded{very fine,} and "
          "\\Reworded{$y \\in \\{0, 1\\}$.}\n"
          "\\end{prop}")
#: the same with a mark at the very end and one at the very start of a line
MARKED_EDGES = ("\\begin{prop}\\label{prop:foo}\n"
                "\\Reworded{Every} closed $x$ is very fine, and $y \\in \\{0, 1\\}$. "
                "\\Struck{It is {nice}.}\n"
                "\\end{prop}")


def _load(name, path):
    here = str(Path(path).parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestStripMarks(unittest.TestCase):
    def test_reworded_keeps_its_text_and_struck_drops_it(self):
        self.assertEqual(model.strip_marks("a \\Reworded{b c} d"), "a b c d")
        self.assertEqual(model.strip_marks("a \\Struck{b c} d"), "a  d")

    def test_nested_braces_and_math_inside_a_mark(self):
        self.assertEqual(model.strip_marks("\\Reworded{$\\{x\\}$ and {y}}"),
                         "$\\{x\\}$ and {y}")
        self.assertEqual(model.strip_marks("p \\Struck{$\\frac{1}{2}$} q"), "p  q")

    def test_a_marked_statement_hashes_as_its_unmarked_text(self):
        h = model.statement_hash_of(UNMARKED)
        self.assertEqual(model.statement_hash_of(MARKED), h)
        self.assertEqual(model.statement_hash_of(MARKED_EDGES), h)

    def test_nothing_else_is_ignored(self):
        # a different word, or another macro, still moves the hash
        self.assertNotEqual(model.statement_hash_of(UNMARKED.replace("closed", "open")),
                            model.statement_hash_of(UNMARKED))
        self.assertNotEqual(model.statement_hash_of("a \\Sketch{b} c"),
                            model.statement_hash_of("a b c"))
        # a name that only starts like a mark is not one
        self.assertEqual(model.strip_marks("\\Rewordedx{b}"), "\\Rewordedx{b}")

    def test_an_unbalanced_mark_is_left_as_written(self):
        self.assertEqual(model.strip_marks("a \\Reworded{b"), "a \\Reworded{b")

    def test_the_vendored_copies_agree_with_the_engine(self):
        sys.path.insert(0, str(REPO / "academy" / "lib"))
        import academy_common as ac
        for text in (UNMARKED, MARKED, MARKED_EDGES, "a \\Reworded{b", "\\Struck{}x"):
            self.assertEqual(ac.strip_reword_marks(text), model.strip_marks(text), text)

    def test_decision_table_and_pinned_hash_like_the_engine(self):
        dt = _load("_t137_decision_table", REPO / "expert" / "scripts" / "decision_table.py")
        pn = _load("_t137_pinned", REPO / "author" / "scripts" / "pinned.py")
        h = model.statement_hash_of(UNMARKED)
        for text in (MARKED, MARKED_EDGES):
            self.assertEqual(dt.statement_hash(text), h)
            self.assertEqual(pn.statement_hash(text), h)
            self.assertEqual(pn.norm(text), pn.norm(UNMARKED).replace("  ", " "))
        # the decision table's fallback (the engine not importable) ignores them too
        dt._CACHE.pop("fn", None)
        saved = sys.modules.get("registry.core.model")
        sys.modules["registry.core.model"] = None       # the import raises ImportError
        try:
            fn = dt._engine_statement_hash_of()
            self.assertNotEqual(getattr(fn, "__module__", ""), "registry.core.model")
            self.assertEqual(fn(MARKED), h)
        finally:
            sys.modules["registry.core.model"] = saved
            dt._CACHE.pop("fn", None)


class TestPaperStore(Homes):
    def setUp(self):
        super().setUp()
        registry.clear_cache()
        write(self.bi / "claims" / "paper" / "prop__foo.md",
              "---\nid: paper:prop:foo\ntitle: prop:foo\nstatus: proved\n"
              "where: sections/a.tex\nhistory:\n  - 2026-11-02 | proved | x\n---\n")

    def _store(self, tex):
        write(self.bi / "sections" / "a.tex", tex + "\n")
        registry.clear_cache()
        return federation.store("paper", self.bi)

    def test_the_paper_statement_hash_ignores_the_marks(self):
        h = self._store(UNMARKED).statement_hash("prop:foo")
        st = self._store(MARKED)
        self.assertEqual(st.statement_hash("prop:foo"), h)
        # and the text a review is given on carries no marks
        self.assertNotIn("\\Reworded", st.statement_text("prop:foo"))
        self.assertNotIn("quite", st.statement_text("prop:foo"))

    def test_item_hashes_ignore_the_marks(self):
        items = ("\\begin{prop}\\label{prop:foo}\n\\begin{enumerate}\n"
                 "\\item\\label{it:one} One %s holds.\n\\item\\label{it:two} Two.\n"
                 "\\end{enumerate}\n\\end{prop}")
        write(self.bi / "claims" / "paper" / "prop__foo.md",
              "---\nid: paper:prop:foo\ntitle: prop:foo\nstatus: proved\n"
              "where: sections/a.tex\nitems:\n  one: [proved]\n  two: [proved]\n"
              "history:\n  - 2026-11-02 | proved | x\n---\n")
        plain = self._store(items % "thing").item_hash("prop:foo", "one")
        self.assertIsNotNone(plain)
        marked = self._store(items % "\\Reworded{thing} \\Struck{stuff}").item_hash(
            "prop:foo", "one")
        self.assertEqual(marked, plain)

    def test_cli_statement_prints_the_unmarked_hash(self):
        h = self._store(UNMARKED).statement_hash("prop:foo")
        self._store(MARKED)
        import contextlib
        import io
        from registry import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(["--repo", str(self.bi), "statement", "paper:prop:foo"])
        self.assertIn("hash: %s" % h, out.getvalue())


if __name__ == "__main__":
    unittest.main()
