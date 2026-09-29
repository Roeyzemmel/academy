"""library_index.py: cached files without index rows, drafted rows, apply -- on a
fixture library and on a temp copy of the real library's index (never on the real one)."""

import os
import shutil
import tempfile
import unittest

import fixtures
import library_index as li

REAL = os.environ.get("ACADEMY_LIBRARY", "")   # set by the workspace bootstrap


class FixtureLibraryTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.home = self.sb.lib
        self.sb.write("papers/NEW22.meta", "key: NEW22\nauthors: Newton, I.\ntitle: A new "
                                           "one\nversion: arXiv v1 (2 Feb 2022)\nsource: "
                                           "https://arxiv.org/pdf/2202.00002v1\ndate fetched:"
                                           " 2026-09-28\nhow read: text (extraction)\n")
        self.sb.write("papers/NEW22.txt", "text")
        os.makedirs(os.path.join(self.home, "NEW22.src"))
        self.sb.write("papers/ODD_eprint.tar.gz", "x")
        self.sb.write("papers/README.md", "# readme")

    def tearDown(self):
        self.sb.close()

    def test_cached_keys(self):
        ck = li.cached_keys(self.home)
        self.assertEqual(ck["ABC21"], [".meta", ".src/", ".txt"])
        self.assertEqual(ck["NEW22"], [".meta", ".src/", ".txt"])
        self.assertEqual(ck["ODD"], ["_eprint.tar.gz"])
        self.assertNotIn("README", ck)
        self.assertNotIn("index", ck)

    def test_missing(self):
        m = li.missing(self.home)
        self.assertEqual(sorted(m["cached_without_index_row"]), ["NEW22", "ODD"])
        self.assertEqual(m["indexed_without_files"], [])

    def test_draft_row_from_meta_never_guesses(self):
        rows = li.propose(self.home)
        new = [r for r in rows if r.startswith("| NEW22 ")][0]
        self.assertIn('Newton, I., "A new one"', new)
        self.assertIn("arXiv v1 (2 Feb 2022)", new)
        self.assertIn("`NEW22.src/`", new)
        self.assertIn("2026-09-28", new)
        odd = [r for r in rows if r.startswith("| ODD ")][0]
        self.assertEqual(odd.count("to fill"), 5)   # who, version, source, how read, date
        self.assertEqual(odd.count("|"), 9)             # eight cells

    def test_apply_appends_after_the_table_and_closes_the_gap(self):
        li.apply_rows(self.home, li.propose(self.home))
        text = self.sb.read("papers/index.md")
        self.assertLess(text.index("| ODD "), text.index("## Not cached"))
        self.assertGreater(text.index("| NEW22 "), text.index("| XY20 "))
        self.assertEqual(li.missing(self.home)["cached_without_index_row"], {})

    def test_apply_keeps_crlf(self):
        p = os.path.join(self.home, "index.md")
        self.sb.write("papers/index.md", fixtures.INDEX, newline="\r\n")
        li.apply_rows(self.home, li.propose(self.home))
        with open(p, "rb") as fh:
            data = fh.read()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertIn(b"| NEW22 ", data)

    def test_cli_exit_codes(self):
        code, out, err = fixtures.run_script("library_index.py", None,
                                             ["missing", "--home", self.home])
        self.assertEqual(code, 1, err)
        self.assertIn("no index row: NEW22", out)
        code, out, err = fixtures.run_script("library_index.py", None,
                                             ["apply", "--home", self.home])
        self.assertEqual(code, 0, err)
        code, out, err = fixtures.run_script("library_index.py", None,
                                             ["missing", "--home", self.home])
        self.assertEqual(code, 0, (out, err))


@unittest.skipUnless(os.path.isfile(os.path.join(REAL, "index.md")), "no real library")
class RealLibraryCopyTests(unittest.TestCase):
    """A temp copy of the real index.md plus empty stand-ins named like the real
    cached files (no PDF is copied). The real library is only listed and read."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="expert-lib-copy-")
        shutil.copy2(os.path.join(REAL, "index.md"), self.tmp)
        for f in os.listdir(REAL):
            full = os.path.join(REAL, f)
            if f in ("index.md", "README.md"):
                continue
            if os.path.isdir(full):
                os.makedirs(os.path.join(self.tmp, f))
            else:
                open(os.path.join(self.tmp, f), "w").close()
        for f in os.listdir(REAL):
            if f.endswith(".meta"):
                shutil.copy2(os.path.join(REAL, f), self.tmp)
        with open(os.path.join(REAL, "index.md"), "rb") as fh:
            self.before = fh.read()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_copy_gap_then_fill(self):
        m = li.missing(self.tmp)
        gaps = m["cached_without_index_row"]
        indexed = {r["key"] for r in li.index_rows(self.tmp)}
        for k in gaps:
            self.assertNotIn(k, indexed)
        self.assertEqual(li.missing(REAL)["cached_without_index_row"], gaps)
        li.apply_rows(self.tmp, li.propose(self.tmp))
        self.assertEqual(li.missing(self.tmp)["cached_without_index_row"], {})
        self.assertEqual(len(li.index_rows(self.tmp)), len(indexed) + len(gaps))
        with open(os.path.join(REAL, "index.md"), "rb") as fh:
            self.assertEqual(fh.read(), self.before)


if __name__ == "__main__":
    unittest.main()
