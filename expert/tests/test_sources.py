"""sources.py: records from the arXiv and Crossref APIs, parsed from answers kept here
(trimmed from the live ones of 2026-11-13); no network in the tests."""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import sources as src  # noqa: E402

ARXIV = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1407.2975v1</id>
    <title>Everything is
      illuminated</title>
    <updated>2014-07-10T21:41:16Z</updated>
    <summary>We study geometrical properties of translation surfaces.</summary>
    <category term="math.DS" scheme="http://arxiv.org/schemas/atom"/>
    <published>2014-07-10T21:41:16Z</published>
    <arxiv:primary_category term="math.DS"/>
    <arxiv:journal_ref>Geom. Topol. 20 (2016) 1737-1762</arxiv:journal_ref>
    <author><name>Samuel Lelievre</name></author>
    <author><name>Thierry Monteil</name></author>
    <author><name>Barak Weiss</name></author>
    <arxiv:doi>10.2140/gt.2016.20.1737</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/math/0406510v2</id>
    <title>On the finite blocking property</title>
    <updated>2026-11-05T10:00:00Z</updated>
    <published>2004-06-25T00:00:00Z</published>
    <arxiv:primary_category term="math.DS"/>
    <author><name>Thierry Monteil</name></author>
  </entry>
</feed>"""
CROSSREF = json.dumps({"status": "ok", "message": {
    "DOI": "10.2140/gt.2016.20.1737", "title": ["Everything is illuminated"],
    "container-title": ["Geometry &amp; Topology"], "short-container-title": ["Geom. Topol."],
    "volume": "20", "issue": "3", "page": "1737-1762", "type": "journal-article",
    "publisher": "Mathematical Sciences Publishers",
    "published-print": {"date-parts": [[2016, 7, 4]]},
    "author": [{"given": "Samuel", "family": "Lelièvre"}, {"given": "Barak", "family": "Weiss"}]}})


class Sources(unittest.TestCase):
    def test_classify(self):
        for ref, want in (("1407.2975", ("arxiv", "1407.2975")),
                          ("arXiv:1407.2975v3", ("arxiv", "1407.2975")),
                          ("https://arxiv.org/abs/math/0406510v1", ("arxiv", "math/0406510")),
                          ("math.DS/0406510", ("arxiv", "math.DS/0406510")),
                          ("10.2140/gt.2016.20.1737", ("doi", "10.2140/gt.2016.20.1737")),
                          ("https://doi.org/10.2140/gt.2016.20.1737.",
                           ("doi", "10.2140/gt.2016.20.1737")),
                          ("Everything is illuminated", (None, "Everything is illuminated"))):
            self.assertEqual(want, src.classify(ref), ref)

    def test_parse_arxiv(self):
        a, b = src.parse_arxiv(ARXIV)
        self.assertEqual(("1407.2975", "v1", "Everything is illuminated", "2014", "math.DS"),
                         (a["arxiv"], a["version"], a["title"], a["year"], a["category"]))
        self.assertEqual(["Samuel Lelievre", "Thierry Monteil", "Barak Weiss"], a["authors"])
        self.assertEqual("10.2140/gt.2016.20.1737", a["doi"])
        self.assertEqual(("math/0406510", "v2"), (b["arxiv"], b["version"]))
        self.assertNotIn("doi", b)
        with self.assertRaises(src.SourceError):
            src.parse_arxiv("<html>Rate exceeded")

    def test_parse_crossref(self):
        r = src.parse_crossref(CROSSREF)
        self.assertEqual(("Geometry & Topology", "20", "3", "1737-1762", "2016"),
                         (r["journal"], r["volume"], r["issue"], r["pages"], r["year"]))
        self.assertEqual("Samuel Lelièvre", r["authors"][0])
        with self.assertRaises(src.SourceError):
            src.parse_crossref("Resource not found.")

    def test_lookup_completes_an_arxiv_record_from_crossref_without_overwriting(self):
        calls = []

        def get(url):
            calls.append(url)
            return ARXIV if "arxiv" in url else CROSSREF
        rec = src.lookup("arXiv:1407.2975", get=get)
        self.assertEqual(2, len(calls))
        self.assertIn("id_list=1407.2975", calls[0])
        self.assertTrue(calls[1].endswith("/works/10.2140/gt.2016.20.1737"))
        self.assertEqual("2014", rec["year"])                    # the preprint's own
        self.assertEqual(("2016", "1737-1762"), (rec["published"]["year"],
                                                 rec["published"]["pages"]))
        text = src.render(rec)
        self.assertIn("published (Crossref): Geometry & Topology 20(3) (2016) 1737-1762", text)

    def test_lookup_survives_crossref_being_unreachable_and_says_so(self):
        def get(url):
            if "crossref" in url:
                raise src.SourceError("api.crossref.org cannot be reached")
            return ARXIV
        rec = src.lookup("1407.2975", get=get)
        self.assertIn("Crossref not consulted", rec["published_note"])
        self.assertIsNone(src.lookup("10.1234/none", get=lambda url: None))
        with self.assertRaises(src.SourceError):
            src.lookup("a title", get=get)

    def test_search_builds_the_query_and_filters_by_since(self):
        seen = {}

        def get(url):
            seen["url"] = url
            return ARXIV
        recs = src.search("finite blocking", ["math.DS", "math.GT"], "2026-11-01", 10, get=get)
        self.assertEqual(["math/0406510"], [r["arxiv"] for r in recs])   # updated 2026-11-05
        self.assertIn("all%3A%22finite+blocking%22", seen["url"])
        self.assertIn("cat%3Amath.DS+OR+cat%3Amath.GT", seen["url"])
        self.assertIn("sortBy=lastUpdatedDate", seen["url"])
        self.assertEqual(2, len(src.search("ti:illuminated", get=get)))
        with self.assertRaises(src.SourceError):
            src.search("", get=get)


if __name__ == "__main__":
    unittest.main()
