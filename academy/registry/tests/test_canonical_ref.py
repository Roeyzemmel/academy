"""workspace.canonical_ref: a file reference given in any of the ways agents give it
(the 2026-11-13 error-ledger round) comes back in the protocol's form."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from registry.core import workspace  # noqa: E402


class CanonicalRef(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="canon-ref-")).resolve()
        self.nb, self.lib = self.tmp / "Notebook", self.tmp / "library"
        for p, text in ((self.nb / "audits/x/A.md", "a"),
                        (self.lib / "reviews/s1/GEO-1/p/A.md", "a"),
                        (self.lib / "audits/x/A.md", "clash")):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        ws = self.tmp / "workspace.json"
        ws.write_text(json.dumps({"instances": {
            "researcher@n": {"role": "researcher", "home": str(self.nb), "ns": "s1"},
            "expert@l": {"role": "expert", "home": str(self.lib)}}}), encoding="utf-8")
        self._env = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = str(ws)

    def tearDown(self):
        if self._env is None:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        else:
            os.environ["ACADEMY_WORKSPACE"] = self._env
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def canon(self, ref):
        return workspace.canonical_ref(ref, self.nb)

    def test_forms_that_are_already_right_are_untouched(self):
        for ref in ("audits/x/A.md", "file:expert@l/reviews/s1/GEO-1/p/A.md",
                    "https://arxiv.org/abs/1", "Notebook:audits/x/A.md", "", None):
            self.assertEqual(ref, self.canon(ref))

    def test_another_homes_file_becomes_a_file_ref(self):
        want = "file:expert@l/reviews/s1/GEO-1/p/A.md"
        for ref in (str(self.lib / "reviews/s1/GEO-1/p/A.md"),      # absolute
                    "library/reviews/s1/GEO-1/p/A.md",               # from the workspace root
                    "reviews/s1/GEO-1/p/A.md",                       # relative to its home
                    "library\\reviews\\s1\\GEO-1\\p\\A.md"):
            self.assertEqual(want, self.canon(ref), ref)
        self.assertEqual(want + "#L3", self.canon("reviews/s1/GEO-1/p/A.md#L3"))

    def test_an_absolute_path_into_the_own_home_becomes_relative(self):
        self.assertEqual("audits/x/A.md", self.canon(str(self.nb / "audits/x/A.md")))

    def test_no_match_is_returned_as_given(self):
        self.assertEqual("reviews/s1/GEO-9/A.md", self.canon("reviews/s1/GEO-9/A.md"))

    def test_from_another_home_the_notebooks_audit_is_qualified(self):
        self.assertEqual("file:researcher@n/audits/x/A.md",
                         workspace.canonical_ref(str(self.nb / "audits/x/A.md"), self.lib))


if __name__ == "__main__":
    unittest.main()
