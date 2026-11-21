"""reading_list.py (#108): the human's reading list of unreachable sources, built from the
parked cite tickets' last block reason, the library index and the registry's edges. Pure
functions, plus gather and main on a file board."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _env  # noqa: F401  (puts the scripts on the path)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import reading_list as rl  # noqa: E402

BLOCK = "- 2026-11-19 expert@main/inbox-clerk: status in-progress -> blocked: "
REASON = "source unreachable from this session: %s; a human with access reads %s"


def body(*lines):
    return "## Thread\n\n" + "\n".join(lines) + "\n"


def parse(reason):
    return rl.parse_reason(rl.last_block(body(BLOCK + reason)))


class ReasonTests(unittest.TestCase):
    def test_the_split_at_the_claim(self):
        h = parse(REASON % ("Ab01", "Ab01 p. 8 for Prop. 5.6; Def. 3.2 for paper:prop:x (sections/s.tex)"))
        self.assertEqual((h["keys"], h["what"], h["relying"], h["truncated"]),
                         (["Ab01"], "Ab01 p. 8 for Prop. 5.6; Def. 3.2", "paper:prop:x (sections/s.tex)", False))

    def test_a_free_text_relying(self):
        h = parse(REASON % ("Ab01", "Ab01 Thm 2 for the sentence in sec. 3 on the bound"))
        self.assertEqual((h["what"], h["relying"]), ("Ab01 Thm 2", "the sentence in sec. 3 on the bound"))
        self.assertFalse(h["truncated"])

    def test_the_real_cut_lengths(self):
        """cite.js cuts the reason at 240: one of 238-240 characters was cut, whatever it holds."""
        head = REASON % ("Ab01", "")
        for n in (238, 240):
            reason = (head + "Not yet known. Needed: the main-result statement " * 6)[:n - 8] + " for pap"
            self.assertEqual(len(reason), n)
            h = parse(reason)
            self.assertTrue(h["truncated"], n)
            self.assertTrue(h["what"].endswith("[...]"), n)
            self.assertNotIn(" for pap", h["what"])
        # a cut that falls after a claim id marks the relying part
        reason = (head + "Ab01 Lemma 4.1 for paper:lem:tok (sections/background.tex); the T-1277 Rule 9 check of the "
                  + "statement and of the hypotheses k >= 2 and the angles " * 3)[:240]
        h = parse(reason)
        self.assertTrue(h["truncated"])
        self.assertTrue(h["relying"].startswith("paper:lem:tok") and h["relying"].endswith("[...]"))
        self.assertEqual(h["what"], "Ab01 Lemma 4.1")
        # a full reason well under the cut is not marked
        self.assertFalse(parse(REASON % ("Ab01", "x " * 60 + "for the sentence"))["truncated"])

    def test_several_keys(self):
        self.assertEqual(parse(REASON % ("Er13 (Mo77, Th92 unreachable)", "the statement for paper:lem:p"))["keys"],
                         ["Er13", "Mo77", "Th92"])

    def test_only_the_last_block_counts(self):
        stale = body(BLOCK + REASON % ("Ab01", "Ab01 Thm 2 for paper:lem:a"),
                     "- 2026-11-20 human: uploaded Ab01",
                     "- 2026-11-20 expert@main/inbox-clerk: status in-progress -> blocked: a decision on the wording")
        self.assertIsNone(rl.parse_reason(rl.last_block(stale)))
        self.assertEqual(rl.parse_reason("- x: blocked: source unreachable from this session: Er13 then something"),
                         {"unparsed": "source unreachable from this session: Er13 then something"})

    def test_claims_of_refs(self):
        meta = {"refs": ["paper:lem:a", "T-0001", "file:expert@main/x.md", "bib:Ab01", "arxiv:2101.00001", "paper:lem:a"]}
        self.assertEqual(rl.claims_of(meta), ["paper:lem:a", "arxiv:2101.00001"])
        self.assertEqual(rl.claims_of(meta, lambda c: c.startswith("paper:")), (["paper:lem:a"], ["arxiv:2101.00001"]))


class GraphTests(unittest.TestCase):
    def test_breadth_first_order_does_not_matter(self):
        """Review of 699a65e: the edges, not a printed listing. C depends on A whatever comes
        first; a dependent of a bearer is not a dependent; implies is neither."""
        edges = [("x:B", "bears_on", "x:A"), ("x:C", "depends_on", "x:A"), ("x:D", "depends_on", "x:C"),
                 ("x:E", "depends_on", "x:B"), ("x:F", "bears_on", "x:D"), ("x:G", "implies", "x:A")]
        for es in (edges, list(reversed(edges))):
            self.assertEqual(rl.dependents(es, ["x:A"]), (["x:C", "x:D"], ["x:B", "x:F"]))

    def test_a_cycle_ends(self):
        self.assertEqual(rl.dependents([("x:A", "depends_on", "x:B"), ("x:B", "depends_on", "x:A")], ["x:A"]), (["x:B"], []))


class BuildTests(unittest.TestCase):
    INDEX = {"Ab01": {"key": "Ab01", "authors, short title": "Ab, \"A paper\"", "version": "journal, doi:10.1/xyz",
                      "source url": "`https://example.org/ab01` (needs a browser)", "source dir": "none: unreachable",
                      "how read": "unreachable", "used for": "publisher refused by the proxy"},
             "Er13": {"key": "Er13", "authors, short title": "Er", "version": "arXiv", "source url": "",
                      "source dir": "Er13.src", "how read": "source", "used for": "Thm 1.10"},
             "Gh04": {"key": "Gh04", "authors, short title": "Gh", "version": "Ann. 2004, doi:10.2/gh04", "source url": "",
                      "source dir": "Gh04.txt", "how read": "text", "used for": "p. 3"}}

    def tickets(self):
        return [({"id": "T-0001", "to": "expert@main", "title": "Card for Ab01", "refs": ["paper:lem:a"], "packets": ["P-0001"]},
                 body(BLOCK + REASON % ("Ab01", "Ab01 Thm 2 for paper:lem:a"))),
                ({"id": "T-0002", "to": "expert@main", "title": "Schoenflies", "refs": ["paper:lem:z"], "packets": []},
                 body(BLOCK + REASON % ("Er13 (Mo77, Th92 unreachable)", "the polygon theorem for paper:lem:z"))),
                ({"id": "T-0003", "to": "expert@main", "title": "Gh04 p. 9", "refs": ["paper:lem:g"], "packets": ["P-0007", "P-0009"]},
                 body(BLOCK + REASON % ("Gh04", "Gh04 p. 9 page image for paper:lem:g"))),
                ({"id": "T-0004", "to": "expert@main", "title": "A decision", "refs": []}, body(BLOCK + "decide something")),
                ({"id": "T-0005", "to": "expert@main", "title": "Odd", "refs": []}, body(BLOCK + "source unreachable from this session: Zz99 garbled"))]

    def test_rows(self):
        edges = [("paper:thm:b", "depends_on", "paper:lem:a"), ("paper:thm:y", "depends_on", "paper:lem:z"),
                 ("paper:thm:x", "depends_on", "paper:thm:y"), ("flat:Q-1", "bears_on", "paper:lem:z")]
        rows, unparsed = rl.build(self.tickets(), lambda inst: self.INDEX, (edges, lambda c: True),
                                  lambda pid: {"P-0009": "the page image is not in the cache"}.get(pid, ""))
        self.assertEqual([(r["ticket"], r["key"]) for r in rows],
                         [("T-0002", "Mo77"), ("T-0002", "Th92"), ("T-0001", "Ab01"), ("T-0003", "Gh04")])
        self.assertEqual(unparsed, [{"ticket": "T-0005", "reason": "source unreachable from this session: Zz99 garbled"}])
        mo = rows[0]
        self.assertEqual((mo["rests_on_it"], mo["bears_on_it"], mo["in_index"]), (["paper:thm:x", "paper:thm:y"], ["flat:Q-1"], False))
        ab = rows[2]
        self.assertEqual((ab["link"], ab["tried"]), ("https://example.org/ab01", "publisher refused by the proxy"))
        gh = rows[3]
        self.assertEqual((gh["link"], gh["tried"]), ("https://doi.org/10.2/gh04", "the page image is not in the cache"))
        text = rl.render(rows, unparsed)
        self.assertIn("do not edit", text)
        self.assertIn("4 source(s) to read; on the claims they block, 3 registry statement(s) rest", text)
        self.assertIn("- **Named as:** Er13 (Mo77, Th92 unreachable)", text)
        self.assertIn("## Could not read", text)
        self.assertIn("T-0005: source unreachable", text)

    def test_unknown_claims_and_no_graph(self):
        rows, _u = rl.build(self.tickets()[:1], lambda inst: self.INDEX, ([], lambda c: False))
        self.assertEqual((rows[0]["claims"], rows[0]["unknown_claims"]), ([], ["paper:lem:a"]))
        self.assertIn("not in the registry: paper:lem:a", rl.render(rows))
        rows, _u = rl.build(self.tickets()[:1], lambda inst: self.INDEX, None)
        self.assertIsNone(rows[0]["rests_on_it"])
        self.assertIn("not counted", rl.render(rows))

    def test_nothing_to_read(self):
        self.assertIn("Nothing to read", rl.render([]))


class GatherTests(unittest.TestCase):
    def test_gather_and_main_on_a_file_board(self):
        import fixtures  # noqa: F401
        bd = rl.ex.base_script("board")
        d = tempfile.mkdtemp(prefix="academy-rl-")
        self.addCleanup(shutil.rmtree, d, True)
        lib = os.path.join(d, "lib")
        os.makedirs(lib)
        with open(os.path.join(lib, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("| key | authors, short title | version | source URL | source dir | how read | date | used for |\n"
                     "|---|---|---|---|---|---|---|---|\n"
                     "| Ab01 | Ab, \"A paper\" | journal | `https://example.org/ab01` | none: unreachable | unreachable | 2026-11-19 | refused |\n")
        ws = {"instances": {"expert@main": {"role": "expert", "home": lib, "domains": ["d"]},
                            "author@main": {"role": "author", "home": os.path.join(d, "paper"), "domains": ["d"], "ns": "paper"}},
              "board": os.path.join(d, "board")}
        os.makedirs(ws["board"])
        wsp = os.path.join(d, "workspace.json")
        with open(wsp, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        w = rl.ac.load_workspace(wsp)
        kw = dict(workspace=w, date="2026-11-19", as_instance="author@main", budget={"runs": 1})
        t1 = bd.create_ticket(ws["board"], to="expert@main", title="Card for Ab01", ask="cite", deliverable="a card",
                              kind="cite", refs=["paper:lem:a"], **kw)
        t2 = bd.create_ticket(ws["board"], to="author@main", title="Not the Expert's", ask="x", deliverable="y", kind="write", **kw)
        tid1, tid2 = (os.path.basename(str(t)).split("-")[0] + "-" + os.path.basename(str(t)).split("-")[1] for t in (t1, t2))
        for tid, who in ((tid1, "expert@main"), (tid2, "author@main")):
            bd.transition_ticket(ws["board"], tid, "accepted", as_instance=who, workspace=w)
            bd.transition_ticket(ws["board"], tid, "in-progress", as_instance=who, workspace=w)
            bd.transition_ticket(ws["board"], tid, "blocked", as_instance=who, workspace=w, waiting_on=["human"],
                                 reason=REASON % ("Ab01", "Ab01 Thm 2 for paper:lem:a"))
        got = rl.gather(w, ws["board"])
        self.assertEqual([m["id"] for m, _b in got], [tid1])                 # to the Expert only
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(rl.main(["--workspace", wsp, "--board", ws["board"], "--json", "--no-deps"]), 0)
        out = json.loads(buf.getvalue())
        self.assertEqual([(r["ticket"], r["key"], r["link"]) for r in out["rows"]], [(tid1, "Ab01", "https://example.org/ab01")])
        with redirect_stdout(io.StringIO()):
            rl.main(["--workspace", wsp, "--board", ws["board"], "--write", "--no-deps"])
        with open(os.path.join(lib, "views", "reading-list.md"), encoding="utf-8") as fh:
            self.assertIn("## Ab01", fh.read())


if __name__ == "__main__":
    unittest.main()
