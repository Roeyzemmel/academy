"""T-0361, s1 set-status and ``modulo``, tested by test-engineer from the ticket's ask and
thread (not from the code's output), on a home shaped like researcher@flat: namespace
``flat``, no id prefixes, so a bare ``FND-n`` matches no id pattern.

The rule (T-0361 ask and the 2026-10-12 thread):

* ``proved`` drops the record's ``modulo``; ``proved-modulo`` writes ``--modulo`` when
  given (replacing the record's) and otherwise keeps the record's own;
* ``--modulo`` goes only with ``proved-modulo`` (a lifecycle move or a v1 record refuses it);
* the own-namespace form ``flat:FND-n`` is written bare; another home's ``ns:id`` is kept;
* a modulo item naming this home's object, bare or own-namespace, is an id: an
  unresolvable one is an error; another home's ``ns:id`` passes; free text warns;
* nothing else in set-status changes: a lifecycle move leaves ``modulo`` alone.

Tests named ``test_finding_*`` demonstrate review findings posted on T-0361's thread
(expectedFailure until the developer fixes them).
"""
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from _util import notebook_config, write  # noqa: F401  (puts the engine on sys.path)

from registry.profiles import s1kb

REC = """---
id: {id}
kind: claim
form: lemma
title: "t {id}"
status: {status}
lifecycle: active
summary: s
statement: "X {id}."
{modulo}depends_on: [{deps}]
bears_on: []
supersedes: []
aliases: []
domain: translation-surfaces
tags: []
evidence: []
history:
  - "2026-10-12 | {status} | created"
---

## Statement

X {id}.

## Proof

Because.
"""

RUN = ("---\nsubject: flat:{s}\nrun: {r}\nrun_id: rv-{r}\nverdict: CONFIRMED\n"
       "landed_by: expert/land_verdict\n---\nreport\n")


def quiet(fn, *a, **k):
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        rc = fn(*a, **k)
    return rc, err.getvalue()


class FlatShapedHome(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modulo-flat-"))
        self.addCleanup(shutil.rmtree, str(self.root), True)
        notebook_config(self.root, ns="flat", rules={})        # no id prefixes, as flat
        self.rec("FND-2", "proved", "", "")
        self.rec("FND-3", "sketch", "", "")
        self.rec("FND-1", "sketch", "modulo: []\n", "FND-2")   # FND-20's shape
        self.verdicts("FND-1")

    def rec(self, eid, status, modulo, deps):
        write(self.root / "objects" / "claim" / (eid + ".md"),
              REC.format(id=eid, status=status, modulo=modulo, deps=deps))

    def verdicts(self, eid):
        d = self.root / "audits" / eid / "2026-10-12-T-0001"
        for r in "AB":
            write(d / (r + ".md"), RUN.format(s=eid, r=r))
        return "audits/%s/2026-10-12-T-0001/A.md" % eid

    def path(self, eid="FND-1"):
        return self.root / "objects" / "claim" / (eid + ".md")

    def set(self, *argv):
        return quiet(s1kb.main, ["set-status", *argv, "--root", str(self.root)])

    def v2(self, eid="FND-1"):
        return s1kb.load_kb(self.root).entities[eid].v2

    def checked(self):
        kb = s1kb.load_kb(self.root)
        s1kb.run_check(kb)
        return kb

    def pm(self, *modulo):
        argv = ["FND-1", "proved-modulo", "--verdict", self.verdicts("FND-1")]
        for m in modulo:
            argv += ["--modulo", m]
        return self.set(*argv)

    # the home itself is clean, so every error below is the case's own
    def test_fixture_is_clean(self):
        kb = self.checked()
        self.assertEqual(kb.errors, [])
        self.assertIsNone(kb.rules.id_re)

    def test_own_namespace_modulo_is_written_bare_and_checks_clean(self):
        rc, err = self.pm("flat:FND-2")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.v2()["status"], "proved-modulo")
        self.assertEqual(self.v2()["modulo"], ["FND-2"])
        kb = self.checked()
        self.assertEqual(kb.errors, [])
        self.assertEqual([w for w in kb.warnings if "FND-1" in w and "modulo" in w], [])

    def test_whitespace_around_an_id_is_stripped(self):
        rc, err = self.pm("  flat:FND-2 ")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.v2()["modulo"], ["FND-2"])

    def test_another_homes_id_is_kept_verbatim_and_passes(self):
        rc, err = self.pm("s1:GEO-9")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.v2()["modulo"], ["s1:GEO-9"])
        kb = self.checked()
        self.assertEqual([m for m in kb.errors + kb.warnings if "FND-1" in m
                          and "modulo" in m], [])

    def test_proved_modulo_then_proved_round_trip(self):
        self.assertEqual(self.pm("flat:FND-2")[0], 0)
        rc, err = self.set("FND-1", "proved", "--verdict", self.verdicts("FND-1"))
        self.assertEqual(rc, 0, err)
        text = self.path().read_text(encoding="utf-8")
        self.assertNotIn("modulo", text.split("\n---")[0].split("history:")[0])
        self.assertIn("depends_on: [FND-2]", text)               # the neighbour line stays
        self.assertEqual(self.checked().errors, [])

    def test_proved_modulo_without_modulo_keeps_the_records_own(self):
        self.rec("FND-1", "sketch", "modulo: [FND-2]\n", "FND-2")
        rc, err = self.pm()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.v2()["modulo"], ["FND-2"])

    def test_proved_modulo_with_neither_is_refused_and_restored(self):
        before = self.path().read_bytes()                          # modulo: []
        rc, err = self.pm()
        self.assertNotEqual(rc, 0)
        self.assertIn("does not build", err)
        self.assertEqual(self.path().read_bytes(), before)

    def test_modulo_refused_with_proved_and_lifecycle_moves(self):
        before = self.path().read_bytes()
        v = self.verdicts("FND-1")
        for argv in (("FND-1", "proved", "--verdict", v),
                     ("FND-1", "dropped", "--note", "n"),
                     ("FND-1", "superseded", "--superseded-by", "FND-3", "--note", "n"),
                     ("FND-1", "sketch", "--note", "n")):
            with self.subTest(label=argv[1]):
                rc, err = self.set(*argv, "--modulo", "FND-2")
                self.assertEqual(rc, 1)
                self.assertIn("--modulo goes only with proved-modulo", err)
                self.assertEqual(self.path().read_bytes(), before)
        self.assertNotIn("supersedes:\n", self.path("FND-3").read_text(encoding="utf-8"))

    def test_a_lifecycle_move_leaves_modulo_alone(self):
        self.assertEqual(self.pm("FND-2")[0], 0)
        rc, err = self.set("FND-1", "dropped", "--note", "n")
        self.assertEqual(rc, 0, err)
        v = self.v2()
        self.assertEqual((v["lifecycle"], v["status"], v["modulo"]),
                         ("dropped", "proved-modulo", ["FND-2"]))

    def test_check_on_records_as_written(self):
        cases = (("FND-2", None, None),
                 ("flat:FND-2", None, None),
                 ("flat:FND-99", "does not resolve", None),
                 ("s1:GEO-9", None, None),
                 ("lab:foo", None, None),
                 ("a lemma of the cited paper", None, "is not a record id"))
        for item, err, warn in cases:
            with self.subTest(item=item):
                self.rec("FND-1", "proved-modulo", 'modulo: ["%s"]\n' % item, "FND-2")
                kb = self.checked()
                mine = lambda ms: [m for m in ms if "FND-1" in m and "modulo" in m]
                self.assertEqual(bool(mine(kb.errors)), bool(err), kb.errors)
                if err:
                    self.assertIn(err, mine(kb.errors)[0])
                self.assertEqual(bool(mine(kb.warnings)), bool(warn), kb.warnings)

    # -- findings ------------------------------------------------------------------

    @unittest.expectedFailure
    def test_finding_1_unresolvable_own_namespace_modulo_is_refused(self):
        """``--modulo flat:FND-99`` names this home's object (own namespace), which does
        not exist: the ticket's rule makes that an error, so set-status must refuse and
        put the file back. On the branch the prefix is stripped before writing, the
        record gets bare ``FND-99``, which in a prefixless home is read as free text:
        a warning, and the status change stands."""
        before = self.path().read_bytes()
        rc, err = self.pm("flat:FND-99")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.path().read_bytes(), before)

    @unittest.expectedFailure
    def test_finding_2_empty_modulo_item_is_refused(self):
        """``--modulo ''`` (or ``'  '``, or ``'flat:'``) names no input. On the branch it
        writes ``modulo: [""]``, a non-empty list, so the schema's "proved-modulo needs
        `modulo`" passes and the record goes proved-modulo on nothing (one warning)."""
        for m in ("", "  ", "flat:"):
            with self.subTest(m=m):
                self.rec("FND-1", "sketch", "modulo: []\n", "FND-2")
                before = self.path().read_bytes()
                rc, err = self.pm(m)
                self.assertNotEqual(rc, 0)
                self.assertEqual(self.path().read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
