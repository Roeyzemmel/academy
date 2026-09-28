"""The pack is self-consistent: pack.json names files that exist, and every relative
link in the entry SKILL.md resolves. Run: py -m unittest discover domains/translation-surfaces/tests
"""

import json
import os
import re
import unittest

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(PACK, "skills", "translation-surfaces", "SKILL.md")
CONTRACT = ["notation.md", "theorems/INDEX.md", "theorems/unverified.md", "open-problems.md",
            "examples.md", "traps.md", "figures.md", "computation/README.md", "CHANGELOG.md"]
LINK = re.compile(r"\]\(([^)\s]+)\)")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class PackTest(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads(read(os.path.join(PACK, "pack.json")))

    def test_pack_json_fields(self):
        for key in ("name", "version", "summary", "keywords", "files"):
            self.assertIn(key, self.pack)
        self.assertEqual(self.pack["name"], os.path.basename(PACK))

    def test_pack_json_files_exist(self):
        for key, rel in self.pack["files"].items():
            with self.subTest(key=key):
                self.assertTrue(os.path.isfile(os.path.join(PACK, rel)), rel)

    def test_contract_files_listed(self):
        listed = set(self.pack["files"].values())
        for rel in CONTRACT:
            with self.subTest(file=rel):
                self.assertIn(rel, listed)

    def test_skill_links_resolve(self):
        text = read(SKILL)
        links = [l for l in LINK.findall(text) if not re.match(r"^[a-z]+:", l)]
        self.assertTrue(links, "SKILL.md has no relative links")
        base = os.path.dirname(SKILL)
        for link in links:
            target = link.split("#", 1)[0]
            with self.subTest(link=link):
                self.assertTrue(os.path.exists(os.path.normpath(os.path.join(base, target))), link)

    def test_skill_frontmatter(self):
        text = read(SKILL)
        self.assertTrue(text.startswith("---\nname: translation-surfaces\ndescription: "))

    def test_no_machine_records_in_computation(self):
        bad = re.compile(r"lingo|roeyzemmel|/home/roey|\(Q2\)|gapinv|gap_reverify|20260920-123729")
        api = os.path.join(PACK, "computation", "api")
        for name in sorted(os.listdir(api)):
            with self.subTest(file=name):
                self.assertIsNone(bad.search(read(os.path.join(api, name))), name)


if __name__ == "__main__":
    unittest.main()
