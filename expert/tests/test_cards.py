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


if __name__ == "__main__":
    unittest.main()
