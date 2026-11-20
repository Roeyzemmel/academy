"""cards.py: the card schema and the quote check (the MCP server's normaliser)."""

import os
import unittest

import fixtures
import _academy as ac
import cards
import _expert as ex


class CardTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.home = self.sb.lib

    def tearDown(self):
        self.sb.close()

    def check(self, text, rel="papers/cards/ABC21/lemma-2-1.md"):
        p = self.sb.write(rel, text)
        return cards.validate_path(p, self.home)

    def test_valid_card_quote_verified_across_hyphenation(self):
        errs, warns, q = self.check(fixtures.card_text())
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])
        self.assertEqual(q["status"], "verified")
        self.assertEqual(q["against"], "ABC21.txt (extraction)")

    def test_ligature_and_typographic_quotes(self):
        errs, warns, q = self.check(fixtures.card_text(
            pinpoint="Theorem 3.4", quote='Every "nice" surface is illuminated.'))
        self.assertEqual(q["status"], "verified", warns)
        errs, warns, q = self.check(fixtures.card_text(
            quote="Then the orbit of x is finite."))        # the .txt has the fi ligature
        self.assertEqual(q["status"], "verified", warns)

    def test_elided_quote(self):
        errs, warns, q = self.check(fixtures.card_text(
            quote="Let M be a translation surface ... the orbit of x is finite."))
        self.assertEqual(q["status"], "verified", warns)
        self.assertEqual(q["checked"], 2)

    def test_altered_quote_warns(self):
        errs, warns, q = self.check(fixtures.card_text(
            quote="Let M be a half-translation surface and let x be a periodic point."))
        self.assertEqual(errs, [])
        self.assertEqual(q["status"], "not-found")
        self.assertTrue(any("quote not found" in w for w in warns))

    def test_partial_quote(self):
        errs, warns, q = self.check(fixtures.card_text(
            quote="Let M be a translation surface ... and every point is a cone point."))
        self.assertEqual(q["status"], "partial")
        self.assertTrue(any("partly found" in w for w in warns))

    def test_source_quote_checked_against_src(self):
        errs, warns, q = self.check(fixtures.card_text(
            read_from="source", quote="Let $M$ be a translation surface and let $x$ be "
                                      "a periodic point."))
        self.assertEqual(q["status"], "verified", warns)
        self.assertEqual(q["against"], "ABC21.src/ (source)")

    def test_required_fields_and_sections(self):
        meta = {"key": "ABC21", "pinpoint": "Lemma 2.1"}
        text = ac.write_frontmatter(meta, "\n## Statement\n\nx\n")
        errs, warns, q = self.check(text)
        self.assertIn("missing version", errs)
        self.assertIn("missing read_from", errs)
        self.assertIn("missing section '## Hypotheses'", errs)
        self.assertIn("missing section '## Quote'", errs)

    def test_placeholder_is_error_unless_migrated(self):
        text = fixtures.card_text(statement="_To fill._")
        errs, warns, q = self.check(text)
        self.assertIn("## Statement not yet written", errs)
        text = fixtures.card_text(statement="_To fill._", migrated="sources.md")
        errs, warns, q = self.check(text)
        self.assertEqual(errs, [])
        self.assertIn("## Statement not yet written", warns)

    def test_text_read_needs_a_quote(self):
        errs, warns, q = self.check(fixtures.card_text(quote=""))
        self.assertTrue(any("no verbatim quote" in e for e in errs))
        errs, warns, q = self.check(fixtures.card_text(quote="", read_from="image-only"))
        self.assertEqual(errs, [])

    def test_key_must_match_folder(self):
        errs, _, _ = self.check(fixtures.card_text(key="XY20"))
        self.assertTrue(any("does not match its folder" in e for e in errs))

    def test_bad_read_from(self):
        errs, _, _ = self.check(fixtures.card_text(read_from="osmosis"))
        self.assertTrue(any("read_from" in e for e in errs))

    def test_no_cached_text(self):
        errs, warns, q = self.check(fixtures.card_text(key="ZZ99"),
                                    rel="papers/cards/ZZ99/lemma-2-1.md")
        self.assertEqual(q["status"], "no-text")

    def test_intro_notes_are_not_cards(self):
        self.sb.write("papers/cards/ABC21/_intro.md", "free text")
        self.sb.write("papers/cards/ABC21/lemma-2-1.md", fixtures.card_text())
        self.assertEqual([os.path.basename(p) for p in cards.iter_cards(self.home)],
                         ["lemma-2-1.md"])

    def test_same_normaliser_as_mcp(self):
        lib = ex.library()
        self.assertIs(cards.ex.library(), lib)
        q = "the orbit of x is finite"
        self.assertEqual(lib.find_quote(fixtures.ABC_TXT, q) is not None,
                         cards.check_quote(self.home, "ABC21", q, "extraction")["status"]
                         == "verified")

    def test_render_roundtrip(self):
        text = fixtures.card_text()
        meta, body = ac.read_frontmatter(text)
        self.assertEqual(meta["used_by"], ["paper:lem:x"])
        self.assertEqual(cards.quote_text(cards.sections(body)["## Quote"]),
                         "Let M be a translation surface and let x be a periodic point.")

    def test_cli_new_and_validate(self):
        qf = self.sb.write("quote.txt", "Any two points are finitely blocked on a Veech "
                                        "surface.")
        code, out, err = fixtures.run_script(
            "cards.py", None, ["new", "XY20", "Theorem 3", "--version", "published",
                               "--read-from", "extraction", "--quote-file", qf,
                               "--statement", "Finite blocking on Veech surfaces.",
                               "--hypotheses", "a Veech surface|two points",
                               "--home", self.home])
        self.assertEqual(code, 0, (out, err))
        path = os.path.join(self.home, "cards", "XY20", "theorem-3.md")
        self.assertTrue(os.path.isfile(path))
        code, out, err = fixtures.run_script("cards.py", None, ["validate", "--home",
                                                                self.home, "--json"])
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(out["cards"][0]["quote"], "verified")


BIB = """@article{ABC21,
  author = {Able, A.},
  title = {A paper},
  eprint = {2101.00001},
  archivePrefix = {arXiv},
}

@article{XY20,
  author = {Ex, X.},
  doi = {10.1000/XYZ},
}
"""


class DuplicateTests(unittest.TestCase):
    """#94 review: after a librarian retry, nothing checked for a second bib entry or card.
    cards.py dups counts the entries of the key (and of the same DOI / arXiv id) in the
    bibliography and the cards of the key and pinpoint; more than one is a duplicate."""

    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.home = self.sb.lib
        self.bib = self.sb.write("paperhome/references.bib", BIB)
        self.sb.write("papers/cards/ABC21/lemma-2-1.md", fixtures.card_text())

    def tearDown(self):
        self.sb.close()

    def test_one_entry_and_one_card_is_clean(self):
        r = cards.duplicates(self.home, "ABC21", "Lemma 2.1", bib=self.bib, ref="arXiv:2101.00001v2")
        self.assertEqual((r["bib_key"], r["bib_id"], r["cards"]), (1, 1, 1))
        self.assertEqual(r["problems"], [])

    def test_a_second_entry_of_the_key_is_a_duplicate(self):
        self.sb.write("paperhome/references.bib", BIB + "\n@misc{ABC21,\n  title = {again},\n}\n")
        r = cards.duplicates(self.home, "ABC21", "Lemma 2.1", bib=self.bib)
        self.assertEqual(r["bib_key"], 2)
        self.assertTrue(r["problems"])

    def test_the_same_arxiv_id_under_another_key_is_a_duplicate(self):
        self.sb.write("paperhome/references.bib", BIB + "\n@article{Able21,\n  url = {https://arxiv.org/abs/2101.00001v1},\n}\n")
        r = cards.duplicates(self.home, "ABC21", "Lemma 2.1", bib=self.bib, ref="2101.00001")
        self.assertEqual((r["bib_key"], r["bib_id"]), (1, 2))
        self.assertIn("2101.00001", " ".join(r["problems"]))

    def test_the_same_doi_any_case_and_prefix_is_a_duplicate(self):
        self.sb.write("paperhome/references.bib", BIB + '\n@article{XY20b,\n  doi = "https://doi.org/10.1000/xyz",\n}\n')
        r = cards.duplicates(self.home, "XY20", "Theorem 3", bib=self.bib, ref="doi:10.1000/xyz")
        self.assertEqual(r["bib_id"], 2)
        self.assertTrue(r["problems"])

    def test_a_ref_that_is_a_key_or_title_has_no_id_check(self):
        r = cards.duplicates(self.home, "ABC21", "Lemma 2.1", bib=self.bib, ref="A paper")
        self.assertIsNone(r["bib_id"])

    def test_a_second_card_for_the_same_pinpoint_is_a_duplicate(self):
        self.sb.write("papers/cards/ABC21/lem-2-1.md", fixtures.card_text(pinpoint="lemma  2.1"))
        self.sb.write("papers/cards/ABC21/theorem-3-4.md", fixtures.card_text(pinpoint="Theorem 3.4"))
        r = cards.duplicates(self.home, "ABC21", "Lemma 2.1", bib=self.bib)
        self.assertEqual(r["cards"], 2)
        self.assertTrue(r["problems"])

    def test_the_bib_named_as_instance_and_path(self):
        r = cards.duplicates(self.home, "ABC21", "Lemma 2.1", bib="author@main:references.bib")
        self.assertEqual(r["bib_key"], 1)
        self.assertEqual(r["bib"].replace("\\", "/"), self.bib.replace("\\", "/"))

    def test_an_unreadable_bib_is_said_not_counted(self):
        r = cards.duplicates(self.home, "ABC21", "Lemma 2.1", bib="nobody@x:references.bib")
        self.assertIsNone(r["bib_key"])
        self.assertIn("not found", " ".join(r["warnings"]))
        self.assertEqual(r["problems"], [])

    def test_the_cli_exits_1_on_a_duplicate_and_prints_json(self):
        args = ["dups", "ABC21", "Lemma 2.1", "--home", self.home, "--bib", self.bib, "--ref", "2101.00001", "--json"]
        code, out, err = fixtures.run_script("cards.py", None, args)
        self.assertEqual(code, 0, err)
        self.assertEqual(out["cards"], 1)
        self.sb.write("paperhome/references.bib", BIB + "\n@misc{ABC21,\n}\n")
        code, out, err = fixtures.run_script("cards.py", None, args)
        self.assertEqual(code, 1, err)
        self.assertEqual(out["bib_key"], 2)


if __name__ == "__main__":
    unittest.main()
