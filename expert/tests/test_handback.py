"""handback.py (#108): what a human read of a source no session could reach, recorded in
the library so the card written from it can be checked by script: a pasted text as an
entry of ``<key>.human.md`` (its hash checked against the one the workflow computed from
the human's own words), a file into ``<key>.human/``."""

import hashlib
import os
import types
import unittest
from unittest import mock

import fixtures
import cards
import handback
import _expert as ex

TEXT = "Lemma 4.1. Let P be a rational polygon. Then every\ngeneralized diagonal is finite."


def setUpModule():
    unittest.addModuleCleanup(fixtures.pin_academy_root().stop)


class HashTests(unittest.TestCase):
    def test_sha256_known_values(self):
        self.assertEqual(handback.text_hash(""), "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(handback.text_hash("a"), "sha256:ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb")

    def test_line_ends_and_surrounding_blanks_do_not_count(self):
        self.assertEqual(handback.text_hash("x\r\ny\n"), handback.text_hash("  x\ny"))
        self.assertNotEqual(handback.text_hash("x y"), handback.text_hash("x  y"))

    def test_utf8_bytes_are_hashed(self):
        for t in ("\u00e9", "\U0001d4ab", "n\u00b2"):
            self.assertEqual(handback.text_hash(t), "sha256:" + hashlib.sha256(t.encode("utf-8")).hexdigest())

    def test_a_base_plugin_without_the_register_is_a_clear_exit(self):
        with mock.patch.object(ex, "library", lambda: types.SimpleNamespace()):
            with self.assertRaises(SystemExit) as cm:
                handback.text_hash("a")
        self.assertIn("predates the hand-back register", str(cm.exception))


class RecordTextTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.home = self.sb.lib

    def tearDown(self):
        self.sb.close()

    def rec(self, text=TEXT, **kw):
        kw.setdefault("expect", handback.text_hash(text))
        return handback.record_text(self.home, "HU95", "T-0904", text, pinpoint="Lemma 4.1",
                                    date="2026-11-21", **kw)

    def test_an_entry_is_written_verbatim_and_verifiable(self):
        r = self.rec()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["recorded"], ["HU95.human.md"])
        self.assertEqual(r["id"], handback.text_hash(TEXT))
        self.assertFalse(r["already"])
        entries = ex.library().parse_handbacks(self.sb.read("papers/HU95.human.md"))
        self.assertEqual([e["text"] for e in entries], [TEXT])
        self.assertEqual(entries[0]["attrs"]["hash"], r["id"])
        self.assertEqual(entries[0]["attrs"]["ticket"], "T-0904")
        self.assertEqual(entries[0]["attrs"]["pinpoint"], "Lemma 4.1")
        self.assertEqual(entries[0]["attrs"]["date"], "2026-11-21")
        q = cards.check_quote(self.home, "HU95", "every generalized diagonal is finite", "human-supplied",
                              handback=[r["id"]])
        self.assertEqual(q["status"], "verified")
        self.assertTrue(r["texts"] and "HU95.human.md entry 1" in r["texts"][0])

    def test_a_hash_mismatch_writes_nothing(self):
        r = self.rec(TEXT.replace("finite", "fnite"), expect=handback.text_hash(TEXT))
        self.assertFalse(r["ok"])
        self.assertIn("differs from the text handed back", " ".join(r["problems"]))
        self.assertFalse(os.path.exists(os.path.join(self.home, "HU95.human.md")))

    def test_the_same_text_twice_is_one_entry(self):
        self.rec()
        r = self.rec()
        self.assertTrue(r["ok"] and r["already"], r)
        self.assertEqual(len(ex.library().parse_handbacks(self.sb.read("papers/HU95.human.md"))), 1)
        r = self.rec("Page 9. Another statement entirely.")
        self.assertEqual(len(ex.library().parse_handbacks(self.sb.read("papers/HU95.human.md"))), 2)

    def test_marker_lines_and_empty_texts_are_refused(self):
        for bad in ("x\n<!-- hand-back end -->\ny", "   "):
            r = self.rec(bad)
            self.assertFalse(r["ok"], bad)
        self.assertFalse(os.path.exists(os.path.join(self.home, "HU95.human.md")))

    def test_a_bad_key_is_refused(self):
        r = handback.record_text(self.home, "../x", "T-0904", TEXT, expect=handback.text_hash(TEXT))
        self.assertFalse(r["ok"])

    def test_a_quote_in_the_attributes_survives(self):
        r = handback.record_text(self.home, "HU95", "T-0904", TEXT, expect=handback.text_hash(TEXT),
                                 pinpoint='Lemma "4.1" --> p. 3', date="2026-11-21")
        self.assertTrue(r["ok"], r)
        e = ex.library().parse_handbacks(self.sb.read("papers/HU95.human.md"))
        self.assertEqual([x["text"] for x in e], [TEXT])
        self.assertIn('Lemma "4.1"', e[0]["attrs"]["pinpoint"])


class RecordFileTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.home = self.sb.lib

    def tearDown(self):
        self.sb.close()

    def rec(self, path, **kw):
        return handback.record_file(self.home, "HU95", "T-0904", path, pinpoint="p. 808",
                                    date="2026-11-21", **kw)

    def test_an_image_is_copied_with_a_gitignore(self):
        src = self.sb.write("scratch/page 808.PNG", "not really a png")
        r = self.rec(src)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["recorded"], ["HU95.human/2026-11-21-t-0904-page-808.png"])
        self.assertEqual(r["texts"], [])
        self.assertEqual(r["id"], "sha256:" + hashlib.sha256(b"not really a png").hexdigest())
        recs = ex.library().handback_records(self.home, "HU95")
        self.assertEqual([(x["kind"], x["ok"], x["id"]) for x in recs], [("file", True, r["id"])])
        self.assertEqual(self.sb.read("papers/HU95.human/2026-11-21-t-0904-page-808.png"), "not really a png")
        gi = self.sb.read("papers/HU95.human/.gitignore")
        self.assertIn("*\n", gi)
        self.assertIn("!*.txt", gi)
        r = self.rec(src)
        self.assertTrue(r["already"], r)
        self.assertEqual(r["recorded"], ["HU95.human/2026-11-21-t-0904-page-808.png"])
        q = cards.check_quote(self.home, "HU95", "anything at all, transcribed", "human-supplied", handback=[r["id"]])
        self.assertEqual(q["status"], "unchecked")

    def test_a_text_file_counts_as_text(self):
        src = self.sb.write("scratch/lemma.txt", TEXT + "\n")
        r = self.rec(src)
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["texts"]), 1)
        q = cards.check_quote(self.home, "HU95", "every generalized diagonal is finite", "human-supplied", handback=[r["id"]])
        self.assertEqual(q["status"], "verified")

    def test_a_pdf_gets_its_text_extracted_beside_it(self):
        src = self.sb.write("scratch/scan.pdf", "%PDF-1.4")

        def fake(pdf, txt):
            with open(txt, "w", encoding="utf-8") as fh:
                fh.write(TEXT)
            return True
        with mock.patch.object(handback, "extract_pdf", fake):
            r = self.rec(src)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["recorded"], ["HU95.human/2026-11-21-t-0904-scan.pdf",
                                         "HU95.human/2026-11-21-t-0904-scan.txt"])
        self.assertEqual(len(r["texts"]), 1)
        rec = ex.library().handback_records(self.home, "HU95")[0]
        self.assertEqual(rec["attrs"]["text_sha256"], "sha256:" + hashlib.sha256(TEXT.encode()).hexdigest())

    def test_a_pdf_with_no_text_layer_is_said(self):
        src = self.sb.write("scratch/scan.pdf", "%PDF-1.4")
        with mock.patch.object(handback, "extract_pdf", lambda pdf, txt: False):
            r = self.rec(src)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["texts"], [])
        self.assertIn("no text", " ".join(r["notes"]))

    def test_refusals(self):
        outside = os.path.join(os.path.dirname(self.sb.root), "elsewhere-%d.png" % os.getpid())
        with open(outside, "w") as fh:
            fh.write("x")
        self.addCleanup(os.remove, outside)
        for path, why in ((outside, "outside the workspace"),
                          (self.sb.path("scratch/none.png"), "no such file"),
                          (self.sb.write("scratch/run.exe", "x"), "not a PDF, an image or a text")):
            r = self.rec(path)
            self.assertFalse(r["ok"], path)
            self.assertIn(why, " ".join(r["problems"]))
        self.assertFalse(os.path.isdir(os.path.join(self.home, "HU95.human")))

    def test_a_symlink_is_judged_by_its_target(self):
        outside = os.path.join(os.path.dirname(self.sb.root), "elsewhere-%d.png" % os.getpid())
        with open(outside, "w") as fh:
            fh.write("x")
        self.addCleanup(os.remove, outside)
        link = self.sb.path("scratch/inside.png")
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.symlink(outside, link)
        r = self.rec(link)
        self.assertFalse(r["ok"])
        self.assertIn("outside the workspace", " ".join(r["problems"]))
        link2 = self.sb.path("scratch/lib.txt")
        os.symlink(os.path.join(self.home, "ABC21.txt"), link2)
        r = self.rec(link2)
        self.assertFalse(r["ok"])
        self.assertIn("inside the library home", " ".join(r["problems"]))

    def test_the_librarys_own_files_are_not_a_humans_material(self):
        card = self.sb.write("papers/cards/ABC21/lemma-2-1.md", fixtures.card_text())
        for path in (os.path.join(self.home, "ABC21.txt"), card, os.path.join(self.home, "ABC21.src", "main.tex")):
            r = self.rec(path)
            self.assertFalse(r["ok"], path)
            self.assertIn("inside the library home", " ".join(r["problems"]))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()

    def tearDown(self):
        self.sb.close()

    def test_record_text_and_file_exit_codes(self):
        tf = self.sb.write("papers/.academy/handback-T-0904.txt", TEXT + "\r\n")
        args = ["record", "HU95", "--ticket", "T-0904", "--pinpoint", "Lemma 4.1", "--text-file", tf,
                "--expect", handback.text_hash(TEXT), "--home", self.sb.lib, "--json"]
        code, out, err = fixtures.run_script("handback.py", None, args)
        self.assertEqual(code, 0, (out, err))
        self.assertTrue(out["ok"])
        args[args.index("--expect") + 1] = "sha256:" + "0" * 64
        code, out, err = fixtures.run_script("handback.py", None, args)
        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])
        img = self.sb.write("scratch/p.png", "x")
        code, out, err = fixtures.run_script("handback.py", None, [
            "record", "HU95", "--ticket", "T-0904", "--file", img, "--home", self.sb.lib, "--json"])
        self.assertEqual(code, 0, (out, err))
        code, out, err = fixtures.run_script("handback.py", None, ["show", "HU95", "--home", self.sb.lib, "--json"])
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(out["files"][0], "HU95.human.md")
        self.assertEqual(len(out["files"]), 2)
        self.assertEqual([x["kind"] for x in out["records"]], ["text", "file"])
        self.assertTrue(all(x["ok"] for x in out["records"]))

    def test_record_needs_exactly_one_input_and_a_text_needs_its_hash(self):
        tf = self.sb.write("scratch/t.txt", TEXT)
        code, out, err = fixtures.run_script("handback.py", None, [
            "record", "HU95", "--ticket", "T-0904", "--text-file", tf, "--home", self.sb.lib])
        self.assertEqual(code, 2)
        code, out, err = fixtures.run_script("handback.py", None, [
            "record", "HU95", "--ticket", "T-0904", "--home", self.sb.lib])
        self.assertEqual(code, 2)

    def test_hash_prints_the_hash(self):
        tf = self.sb.write("scratch/t.txt", "a")
        code, out, err = fixtures.run_script("handback.py", None, ["hash", "--text-file", tf])
        self.assertEqual((code, out), (0, "sha256:ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"))


if __name__ == "__main__":
    unittest.main()
