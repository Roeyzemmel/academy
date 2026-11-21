"""reading_list.py (#108): the human's reading list of unreachable sources, built from the
parked cite tickets' thread lines and the library index. Pure functions; no board."""

import os
import sys
import unittest

import _env  # noqa: F401  (puts the scripts on the path)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import reading_list as rl  # noqa: E402

PREFIX = "- 2026-11-19 expert@main/inbox-clerk: status in-progress -> blocked: "


def body(*reasons):
    return "## Thread\n\n" + "\n".join(PREFIX + r for r in reasons) + "\n"


class LineTests(unittest.TestCase):
    def test_the_last_line_and_the_split_at_the_claim(self):
        b = body("source unreachable from this session: Ab01; a human with access reads Ab01 Thm 2 for paper:lem:a",
                 "source unreachable from this session: Ab01; a human with access reads Ab01 p. 8 for Prop. 5.6; "
                 "Def. 3.2 for paper:prop:x (sections/s.tex)")
        h = rl.unreachable_line(b)
        self.assertEqual(h["key"], "Ab01")
        self.assertEqual(h["what"], "Ab01 p. 8 for Prop. 5.6; Def. 3.2")       # its own "for" stays in the what
        self.assertEqual(h["relying"], "paper:prop:x (sections/s.tex)")
        self.assertFalse(h["truncated"])

    def test_a_line_the_board_cut_short(self):
        what = "Not yet known. Needed: the main-result statement of the algorithm " * 3
        h = rl.unreachable_line(body("source unreachable from this session: Ab01; a human with access reads " + what + "for pap"))
        self.assertTrue(h["truncated"])
        self.assertTrue(h["what"].endswith("[...]"))
        self.assertNotIn("for pap", h["what"])
        self.assertEqual(h["relying"], "")

    def test_no_such_line(self):
        self.assertIsNone(rl.unreachable_line(body("waiting on the human: decide")))

    def test_claims_of_refs(self):
        self.assertEqual(rl.claims_of({"refs": ["paper:lem:a", "T-0001", "file:expert@main/x.md", "bib:Ab01", "s1:GEO-3", "paper:lem:a"]}),
                         ["paper:lem:a", "s1:GEO-3"])


class GraphTests(unittest.TestCase):
    def test_depends_chains_only_and_direct_bearings(self):
        text = "\n".join([
            "flat:C-1 (bears_on) [- / n/a]",
            "  flat:C-2 (depends_on) [- / n/a]",        # under a bearing: not a dependent
            "paper:lem:b (depends_on) [proved / true]",
            "  paper:thm:c (depends_on) [sketch / unsettled]",
            "  flat:D-1 (bears_on) [open / unsettled]",  # bears on a dependent: counted as bearing
            "    flat:D-2 (depends_on) [open / unsettled]",
        ])
        deps, near = rl.depends_tree(text)
        self.assertEqual(deps, {"paper:lem:b", "paper:thm:c"})
        self.assertEqual(near, {"flat:C-1", "flat:D-1"})


class BuildTests(unittest.TestCase):
    INDEX = [{"key": "Ab01", "authors, short title": "Ab, \"A paper\"", "version": "journal, doi:10.1/xyz",
              "source url": "`https://example.org/ab01` (needs a browser)", "source dir": "none: unreachable",
              "how read": "unreachable", "used for": "publisher refused by the proxy"},
             {"key": "Cd02", "authors, short title": "Cd", "version": "arXiv", "source url": "",
              "source dir": "Cd02.src", "how read": "source", "used for": "Thm 1 for lem:z"}]

    def tickets(self):
        line = "source unreachable from this session: %s; a human with access reads %s for %s"
        return [({"id": "T-0001", "title": "Card for Ab01", "refs": ["paper:lem:a"], "packets": ["P-0001"]},
                 body(line % ("Ab01", "Ab01 Thm 2", "paper:lem:a"))),
                ({"id": "T-0002", "title": "Card for Cd02", "refs": ["paper:lem:z"], "packets": []},
                 body(line % ("Cd02 (Ef03 unreachable)", "Cd02 Lemma 4", "paper:lem:z"))),
                ({"id": "T-0003", "title": "A decision", "refs": []}, body("decide something"))]

    def test_rows_sorted_by_what_rests_on_them(self):
        deps = {"paper:lem:a": ({"paper:thm:b"}, set()), "paper:lem:z": ({"paper:thm:y", "paper:thm:x"}, {"flat:Q-1"})}
        rows = rl.build(self.tickets(), self.INDEX, lambda c: deps[c])
        self.assertEqual([r["ticket"] for r in rows], ["T-0002", "T-0001"])    # T-0003 is no unreachable source
        a = rows[1]
        self.assertEqual(a["link"], "https://example.org/ab01")
        self.assertEqual(a["tried"], "publisher refused by the proxy")       # the index row of an unread source
        self.assertEqual(rows[0]["tried"], "")                                # a read source: its use is not "tried"
        self.assertEqual(rows[0]["key"], "Cd02 (Ef03 unreachable)")
        self.assertEqual((rows[0]["rests_on_it"], rows[0]["bears_on_it"]), (["paper:thm:x", "paper:thm:y"], ["flat:Q-1"]))
        text = rl.render(rows)
        self.assertIn("do not edit", text)
        self.assertIn("2 source(s) to read; on the claims they block, 3 registry statement(s) rest", text)
        self.assertIn("2 rest on them (depends_on), 1 more bear on them", text)

    def test_a_failed_count_is_said(self):
        def boom(c):
            raise RuntimeError("no graph")
        rows = rl.build(self.tickets()[:1], self.INDEX, boom)
        self.assertIsNone(rows[0]["rests_on_it"])
        self.assertIn("could not be read", rl.render(rows))
        self.assertIsNone(rl.build(self.tickets()[:1], self.INDEX, None)[0]["rests_on_it"])

    def test_nothing_to_read(self):
        self.assertIn("Nothing to read", rl.render([]))


if __name__ == "__main__":
    unittest.main()
