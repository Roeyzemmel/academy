"""Acceptance (merge proposal, "fixed first, never edited to pass"), on this machine only.

* the two legacy suites, unchanged, against the shims: FlatSurfLab's tests/test_claims.py
  (21 tests) and Slope1's tools/test_kb.py (32 tests);
* the phase-0 goldens (academy/goldens): ``check`` on the three registries
  byte-identical after CRLF and worktree-path normalisation; the generated views
  byte-identical (date lines masked; the stale committed views compared with
  views_regenerated/); Slope1's views and kb.sqlite rebuilt in a temp copy.

They run against the migration worktrees (``*-academy``, branch academy-migration),
where the shims and the requoted records are, and are skipped where those are absent.

After R5 (schema v2, ``migrate_v2.py``) the worktrees' records are no longer the v1
records these goldens were taken from, so ``TestGoldens`` is skipped there and
``TestR5`` (below) is the gate: the check outputs against ``goldens/r5/`` (which differ
from phase 0 only by the listed split cases), the migration reproduced byte for byte
from the pre-migration snapshot, and the regenerated views fresh.
After R6 (the notebook layout, ``migrate_r6.py``) Slope1's records are under
``objects/<kind>/``, so ``TestR5`` is skipped in turn and ``TestR6`` is the gate: the check
outputs against ``goldens/r6/`` (R5's plus the two directions), R5 then R6 re-run from the
snapshots (``r5-pre-migration/`` and ``r6-pre-migration/``) reproducing the worktrees byte
for byte, every object in the folder of its kind, and the views fresh.
``show`` on lab/paper ids is not compared byte for byte: after the R2 requote the file
text differs by its quoting only (proved equal as data in goldens/r2-requote-equality.md);
the back-links part is compared exactly.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _util import ENGINE  # noqa: F401  (puts the engine on sys.path)

from registry.core import legacy_fm
from registry.profiles import fsl

MATH = Path(os.environ.get("ACADEMY_MATH", "C:/Work/Math"))
LAB = MATH / "FlatSurfLab-academy"
BI = MATH / "BilliardIllumination-academy"
S1 = MATH / "Slope1illuminationResearch-academy"
GOLD = Path(__file__).resolve().parents[3] / "goldens"
HAVE = LAB.is_dir() and BI.is_dir() and S1.is_dir() and GOLD.is_dir()
MIGRATED = HAVE and fsl.registry_is_v2(LAB / "claims")


def sh(argv, cwd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("ACADEMY_WORKSPACE", None)
    p = subprocess.run([sys.executable] + argv, cwd=str(cwd), capture_output=True, env=env,
                       timeout=600)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8")


def norm(text):
    text = text.replace("\r\n", "\n")
    for n in ("BilliardIllumination", "FlatSurfLab", "Slope1illuminationResearch"):
        text = text.replace(n + "-academy", n)
    return text


def gold(name):
    return (GOLD / name).read_text(encoding="utf-8")


@unittest.skipUnless(HAVE, "the migration worktrees or the goldens are not on this machine")
class TestLegacySuites(unittest.TestCase):
    def test_flatsurflab_test_claims(self):
        rc, out = sh(["-m", "unittest", "tests.test_claims"], LAB)
        self.assertEqual(rc, 0, out)
        self.assertIn("Ran 21 tests", out)

    def test_slope1_test_kb(self):
        rc, out = sh(["-m", "unittest", "test_kb"], S1 / "tools")
        self.assertEqual(rc, 0, out)
        self.assertIn("Ran 32 tests", out)


@unittest.skipUnless(HAVE, "the migration worktrees or the goldens are not on this machine")
@unittest.skipIf(MIGRATED, "the worktrees hold schema-v2 records (R5): these phase-0 goldens "
                           "are of the v1 records; TestR5 is the gate")
class TestGoldens(unittest.TestCase):
    def test_check_outputs(self):
        cases = [("registry_lab.txt", ["scripts/claims.py", "check"], LAB),
                 ("registry_paper.txt", ["scripts/claims.py", "--repo", str(BI), "check"], LAB),
                 ("registry_s1.txt", ["tools/kb.py", "check"], S1)]
        for name, argv, cwd in cases:
            with self.subTest(name):
                rc, out = sh(argv, cwd)
                self.assertEqual(norm(out) + "exit=%d\n" % rc, gold(name))

    def test_show_s1(self):
        got = ""
        for i in ("BOUND-1", "GA-2T", "EX-2x1"):
            rc, out = sh(["tools/kb.py", "show", i], S1)
            got += "### kb.py show %s\n%sexit=%d\n\n" % (i, norm(out), rc)
        self.assertEqual(got, gold("show_s1.txt"))

    def test_show_lab_and_paper(self):
        for name, repo, ids in (
                ("show_lab.txt", [], ("lab:arith-dark-pairs-pm1", "lab:descent-family-n-le-7",
                                      "lab:fact-compatible-half-translation-genus2")),
                ("show_paper.txt", ["--repo", str(BI)],
                 ("paper:conj:origami-slope", "paper:cor:arith-billiard-finite",
                  "paper:thm:moeller-primitive"))):
            blocks = gold(name).split("### ")[1:]
            for cid, blk in zip(ids, blocks):
                with self.subTest(cid):
                    rc, out = sh(["scripts/claims.py"] + repo + ["show", cid], LAB)
                    out = norm(out)
                    g_file, g_tail = blk.split("\n", 1)[1].split("\ncited", 1)
                    n_file, n_tail = out.split("\ncited", 1)
                    self.assertEqual("\ncited" + n_tail + "exit=%d\n\n" % rc,
                                     "\ncited" + g_tail)
                    self.assertEqual(fsl.parse_strict(n_file),
                                     legacy_fm.parse(g_file, fsl.LIST_FIELDS))

    def test_fsl_views(self):
        mask = lambda t: re.sub(r"on \d{4}-\d{2}-\d{2};", "on DATE;", t)  # noqa: E731
        for tag, repo in (("lab", LAB), ("bi", BI)):
            cs, _ = fsl.load(fsl.registry_root(repo))
            with self.subTest(tag + " INDEX.md"):
                self.assertEqual(fsl.render_index(cs),
                                 (GOLD / "views" / f"{tag}__claims__INDEX.md").read_bytes().decode())
            with self.subTest(tag + " index.html"):
                self.assertEqual(mask(fsl.render_html(cs)), mask(
                    (GOLD / "views_regenerated" / f"{tag}__claims__index.html").read_bytes().decode()))
        self.assertEqual(fsl.render_experiments(BI),
                         (GOLD / "views_regenerated" / "bi__Drafts__experiments.md").read_bytes().decode())

    def test_s1_views_and_database(self):
        tmp = Path(tempfile.mkdtemp(prefix="registry-s1-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        files = subprocess.run(["git", "-C", str(S1), "ls-files", "-z"],
                               capture_output=True).stdout.decode("utf-8").split("\0")
        for f in filter(None, files):
            src = S1 / f
            if src.is_file():
                dst = tmp / "s1" / f
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
        shutil.copyfile(S1 / "tools" / "kb.py", tmp / "s1" / "tools" / "kb.py")
        (tmp / "papers").mkdir()
        shutil.copyfile(MATH / "papers" / "index.md", tmp / "papers" / "index.md")
        rc, out = sh(["tools/kb.py", "build"], tmp / "s1")
        self.assertEqual(rc, 0, out)
        for v in ("STATUS.md", "INDEX.md", "OPEN.md", "assumptions/README.md",
                  "computation/verdicts.md", "computation/runs.md", "kb/claims.json",
                  "site/index.html"):
            with self.subTest(v):
                self.assertEqual((tmp / "s1" / v).read_bytes(),
                                 (GOLD / "views" / ("s1__" + v.replace("/", "__"))).read_bytes())


R5 = GOLD / "r5"
PRE = GOLD / "r5-pre-migration"


def _copy_tree_files(src_repo, dst, only=None):
    """Copy the tracked and untracked (not ignored) files of ``src_repo`` into ``dst``."""
    files = subprocess.run(["git", "-C", str(src_repo), "ls-files", "-z", "-co",
                            "--exclude-standard"], capture_output=True).stdout.decode("utf-8")
    for f in filter(None, files.split("\0")):
        if only and not any(f.startswith(o) for o in only):
            continue
        src = src_repo / f
        if src.is_file():
            d = dst / f
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, d)


R6 = GOLD / "r6"
#: Roey's decisions of 2026-09-28 on top of R6 (P-0004 D1, D2, D9; P-0005 D6, D8): the
#: files they removed, added (sha256) and changed (sha256), and the s1 check output
DECIDED = GOLD / "r6-decisions"
PRE6 = GOLD / "r6-pre-migration"
#: R6 (the notebook layout) is applied: Slope1's records are under objects/<kind>/
R6_APPLIED = HAVE and (S1 / "objects").is_dir()


@unittest.skipUnless(MIGRATED and R5.is_dir() and PRE.is_dir(),
                     "the worktrees are not migrated to schema v2 (R5), or the R5 goldens "
                     "are absent")
@unittest.skipIf(R6_APPLIED, "Slope1 is in the notebook layout (R6): these R5 comparisons "
                             "are of the claims/assumptions/examples layout; TestR6 is the "
                             "gate, and it re-runs R5 before R6")
class TestR5(unittest.TestCase):
    def test_check_outputs(self):
        cases = [("registry_lab.txt", ["scripts/claims.py", "check"], LAB),
                 ("registry_paper.txt", ["scripts/claims.py", "--repo", str(BI), "check"], LAB),
                 ("registry_s1.txt", ["tools/kb.py", "check"], S1)]
        for name, argv, cwd in cases:
            with self.subTest(name):
                rc, out = sh(argv, cwd)
                self.assertEqual(norm(out) + "exit=%d\n" % rc,
                                 (R5 / name).read_text(encoding="utf-8"))
        # against phase 0: lab and paper identical; s1 only the three split cases
        r5 = lambda n: (R5 / n).read_text(encoding="utf-8")  # noqa: E731
        self.assertEqual(gold("registry_lab.txt"), r5("registry_lab.txt"))
        self.assertEqual(gold("registry_paper.txt"), r5("registry_paper.txt"))
        self.assertEqual(gold("registry_s1.txt").replace("183 entities", "186 entities"),
                         r5("registry_s1.txt"))

    def test_the_migration_reproduces_the_worktrees(self):
        import contextlib
        import io
        from registry import migrate_v2
        tmp = Path(tempfile.mkdtemp(prefix="registry-r5-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        for ns, home in migrate_v2.HOMES.items():
            src = PRE / ns
            for f in src.rglob("*.md"):
                d = tmp / home / f.relative_to(src)
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, d)
        _copy_tree_files(S1, tmp / migrate_v2.HOMES["s1"],
                         only=("computation/verdicts/", "computation/runs/", "kb/retired.txt"))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc, recs, splits = migrate_v2.run(tmp, "2026-09-28")
        self.assertEqual(rc, 0, "the migration's own checks fail on the snapshot")
        homes = {"lab": LAB, "paper": BI, "s1": S1}
        for r in recs:
            with self.subTest(r["rel"]):
                live = (homes[r["ns"]] / r["rel"]).read_bytes().decode("utf-8")
                self.assertEqual(live, r["new_text"])
        for s in splits:
            with self.subTest(s["rel"]):
                self.assertEqual((S1 / s["rel"]).read_bytes().decode("utf-8"), s["new_text"])

    def test_the_mapping_report_passes(self):
        text = (GOLD / "r5-mapping-report.md").read_text(encoding="utf-8")
        checks = [ln for ln in text.splitlines() if ln.startswith("| ") and
                  (ln.endswith("| PASS |") or "| FAIL" in ln)]
        self.assertEqual(len(checks), 7)
        self.assertTrue(all(ln.endswith("| PASS |") for ln in checks), checks)

    def test_views_are_fresh(self):
        mask = lambda t: re.sub(r"on \d{4}-\d{2}-\d{2};", "on DATE;", t)  # noqa: E731
        for tag, repo in (("lab", LAB), ("bi", BI)):
            cs, _ = fsl.load(fsl.registry_root(repo))
            with self.subTest(tag + " INDEX.md"):
                self.assertEqual(fsl.render_index(cs),
                                 (repo / "claims" / "INDEX.md").read_bytes().decode())
            with self.subTest(tag + " index.html"):
                self.assertEqual(mask(fsl.render_html(cs)),
                                 mask((repo / "claims" / "index.html").read_bytes().decode()))
        self.assertEqual(fsl.render_experiments(BI),
                         (BI / "Drafts" / "experiments.md").read_bytes().decode())
        tmp = Path(tempfile.mkdtemp(prefix="registry-s1-r5-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        _copy_tree_files(S1, tmp / "s1")
        (tmp / "papers").mkdir()
        shutil.copyfile(MATH / "papers" / "index.md", tmp / "papers" / "index.md")
        rc, out = sh(["tools/kb.py", "build"], tmp / "s1")
        self.assertEqual(rc, 0, out)
        for v in ("STATUS.md", "INDEX.md", "OPEN.md", "assumptions/README.md",
                  "computation/verdicts.md", "computation/runs.md", "kb/claims.json"):
            with self.subTest(v):
                self.assertEqual((tmp / "s1" / v).read_bytes(), (S1 / v).read_bytes())


def _run_r5_into(tmp):
    """Re-run the R5 migration from the pre-migration snapshot into ``tmp`` and write
    its output there (records and split cases), as ``migrate_v2 --apply`` would, with
    the s1 files R5 leaves alone (notes/, computation/) from the R6 snapshot."""
    import contextlib
    import io
    from registry import migrate_v2
    for ns, home in migrate_v2.HOMES.items():
        src = PRE / ns
        for f in src.rglob("*.md"):
            d = tmp / home / f.relative_to(src)
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, d)
    s1 = tmp / migrate_v2.HOMES["s1"]
    for f in (PRE6 / "s1").rglob("*.md"):
        d = s1 / f.relative_to(PRE6 / "s1")
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, d)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc, recs, splits = migrate_v2.run(tmp, "2026-09-28")
    homes = {ns: tmp / h for ns, h in migrate_v2.HOMES.items()}
    for r in list(recs) + [dict(s, ns="s1") for s in splits]:
        with open(homes[r["ns"]] / r["rel"], "w", encoding="utf-8", newline="") as fh:
            fh.write(r["new_text"])
    return rc


@unittest.skipUnless(R6_APPLIED and R6.is_dir() and PRE.is_dir() and PRE6.is_dir(),
                     "Slope1 is not in the notebook layout (R6), or the R6 goldens are absent")
class TestR6(unittest.TestCase):
    """R6: Slope1's claims/, assumptions/, examples/ -> objects/<kind>/; notes/ -> the
    journal; the run audits -> audits/<run>/; two directions (``migrate_r6.py``)."""

    def test_check_outputs(self):
        cases = [("registry_lab.txt", ["scripts/claims.py", "check"], LAB, R6),
                 ("registry_paper.txt", ["scripts/claims.py", "--repo", str(BI), "check"], LAB,
                  R6),
                 ("registry_s1.txt", ["tools/kb.py", "check"], S1, DECIDED)]
        for name, argv, cwd, where in cases:
            with self.subTest(name):
                rc, out = sh(argv, cwd)
                self.assertEqual(norm(out) + "exit=%d\n" % rc,
                                 (where / name).read_text(encoding="utf-8"))
        # the decisions against R6: CRIT-20's free-text modulo became OPEN-14 (P-0004 D2),
        # so its warning is the only line gone; STR-6 out and OPEN-14 in keep 188 entities
        r6s1 = [ln for ln in (R6 / "registry_s1.txt").read_text(encoding="utf-8").split("\n")
                if "objects/claim/CRIT-20.md: modulo:" not in ln]
        self.assertEqual("\n".join(r6s1).replace("5 warnings", "4 warnings"),
                         (DECIDED / "registry_s1.txt").read_text(encoding="utf-8"))
        # against R5: lab and paper identical; s1 only the two directions, and the
        # modulo-is-not-an-id warnings added by the Group D review (P-0004 D2/D4)
        r5 = lambda n: (R5 / n).read_text(encoding="utf-8")  # noqa: E731
        r6 = lambda n: (R6 / n).read_text(encoding="utf-8")  # noqa: E731
        self.assertEqual(r5("registry_lab.txt"), r6("registry_lab.txt"))
        self.assertEqual(r5("registry_paper.txt"), r6("registry_paper.txt"))
        s1 = [ln for ln in r6("registry_s1.txt").split("\n")
              if not (ln.startswith("WARNING ") and ": modulo: " in ln)]
        self.assertEqual(r5("registry_s1.txt").replace("186 entities", "188 entities")
                         .replace("0 warnings", "5 warnings"), "\n".join(s1))

    def test_show_lab_and_paper_back_links(self):
        # after R5 the printed record is the v2 file (kind, lifecycle, domain, the v2
        # field order and quoting, five-cell evidence rows, the migration's history row;
        # goldens/README.md); the back-links are unchanged from phase 0
        for name, repo, ids in (
                ("show_lab.txt", [], ("lab:arith-dark-pairs-pm1", "lab:descent-family-n-le-7",
                                      "lab:fact-compatible-half-translation-genus2")),
                ("show_paper.txt", ["--repo", str(BI)],
                 ("paper:conj:origami-slope", "paper:cor:arith-billiard-finite",
                  "paper:thm:moeller-primitive"))):
            blocks = gold(name).split("### ")[1:]
            for cid, blk in zip(ids, blocks):
                with self.subTest(cid):
                    rc, out = sh(["scripts/claims.py"] + repo + ["show", cid], LAB)
                    g_tail = blk.split("\n", 1)[1].split("\ncited", 1)[1]
                    n_file, n_tail = norm(out).split("\ncited", 1)
                    self.assertEqual("\ncited" + n_tail + "exit=%d\n\n" % rc,
                                     "\ncited" + g_tail)
                    self.assertIn("lifecycle: ", n_file)

    def test_show_s1_keeps_the_statement(self):
        # phase 0's show printed the frontmatter, then the ## Statement (or the body's
        # head); a v2 record must too. What differs is what R5 moved: History into the
        # frontmatter, and the status words of the example's claim lines
        blocks = gold("show_s1.txt").split("### kb.py show ")[1:]
        for blk in blocks:
            cid, rest = blk.split("\n", 1)
            with self.subTest(cid):
                want = rest.split("\n---\n", 1)[1].rsplit("exit=", 1)[0]
                want = re.sub(r"\n## History\n.*?(?=\n## |\nclaims: |\Z)", "", want,
                              flags=re.S).replace(" · Proved · ", " · proved · ") \
                    .replace(" · Disproved · ", " · refuted · ")
                rc, out = sh(["tools/kb.py", "show", cid], S1)
                self.assertEqual(rc, 0, out)
                lines = lambda t: [ln for ln in t.split("\n") if ln.strip()]  # noqa: E731
                self.assertEqual(lines(norm(out).split("\n---\n", 1)[1]), lines(want))

    def test_the_migration_reproduces_the_worktrees(self):
        import contextlib
        import io
        from registry import migrate_r6, migrate_v2
        tmp = Path(tempfile.mkdtemp(prefix="registry-r6-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        self.assertEqual(_run_r5_into(tmp), 0, "R5 fails on the snapshot")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc, _ = migrate_r6.run(tmp, "2026-09-28", apply_=True)
        self.assertEqual(rc, 0, "migrate_r6's own checks fail on the R5 output")
        s1, lab = tmp / migrate_v2.HOMES["s1"], tmp / migrate_v2.HOMES["lab"]
        for sub in ("claims", "assumptions", "examples", "notes"):
            self.assertFalse((s1 / sub).exists(), sub)
            self.assertFalse((S1 / sub).exists(), sub)
        import hashlib
        import json
        dec = json.loads((DECIDED / "MANIFEST.json").read_text(encoding="utf-8"))
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
        for top in ("objects", "audits", "journal", "proofs"):
            made = {p.relative_to(s1).as_posix() for p in (s1 / top).rglob("*.md")}
            want = sorted((made - set(dec["removed"]))
                          | {r for r in dec["added"] if r.startswith(top + "/")})
            have = sorted(p.relative_to(S1).as_posix() for p in (S1 / top).rglob("*.md"))
            self.assertEqual(have, want, top)
            for rel in want:
                with self.subTest(rel):
                    pinned = dec["added"].get(rel) or dec["modified"].get(rel)
                    if pinned:              # a decision's edit, pinned by its hash
                        self.assertEqual(sha(S1 / rel), pinned)
                        if rel in dec["modified"]:
                            self.assertNotEqual((S1 / rel).read_bytes(),
                                                (s1 / rel).read_bytes())
                    else:
                        self.assertEqual((S1 / rel).read_bytes(), (s1 / rel).read_bytes())
        self.assertEqual((S1 / "kb" / "r6-path-map.md").read_bytes(),
                         (s1 / "kb" / "r6-path-map.md").read_bytes())
        for f in sorted((lab / "claims" / "lab").glob("*.md")):
            with self.subTest(f.name):
                self.assertEqual((LAB / "claims" / "lab" / f.name).read_bytes(), f.read_bytes())
        left = sorted(p.name for p in (s1 / "computation" / "verdicts").glob("*.md"))
        self.assertEqual(left, sorted(p.name for p in (S1 / "computation" / "verdicts")
                                      .glob("*.md")))
        self.assertEqual(len(left), 19)

    def test_every_object_is_in_the_folder_of_its_kind(self):
        from registry.core import fm
        n = 0
        for p in (S1 / "objects").rglob("*.md"):
            meta, _ = fm.split_document(p.read_text(encoding="utf-8"), str(p))
            self.assertEqual(meta.get("kind"), p.parent.name, str(p))
            n += 1
        self.assertEqual(n, 153)    # 151 records (148 + the 3 split cases) + 2 directions

    def test_views_are_fresh(self):
        mask = lambda t: re.sub(r"on \d{4}-\d{2}-\d{2};", "on DATE;", t)  # noqa: E731
        for tag, repo in (("lab", LAB), ("bi", BI)):
            cs, _ = fsl.load(fsl.registry_root(repo))
            with self.subTest(tag + " INDEX.md"):
                self.assertEqual(fsl.render_index(cs),
                                 (repo / "claims" / "INDEX.md").read_bytes().decode())
            with self.subTest(tag + " index.html"):
                self.assertEqual(mask(fsl.render_html(cs)),
                                 mask((repo / "claims" / "index.html").read_bytes().decode()))
        self.assertEqual(fsl.render_experiments(BI),
                         (BI / "Drafts" / "experiments.md").read_bytes().decode())
        tmp = Path(tempfile.mkdtemp(prefix="registry-s1-r6-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        _copy_tree_files(S1, tmp / "s1")
        (tmp / "papers").mkdir()
        shutil.copyfile(MATH / "papers" / "index.md", tmp / "papers" / "index.md")
        rc, out = sh(["tools/kb.py", "build"], tmp / "s1")
        self.assertEqual(rc, 0, out)
        self.assertFalse((tmp / "s1" / "assumptions").exists())
        for v in ("STATUS.md", "INDEX.md", "OPEN.md", "views/assumptions.md", "views/INDEX.md",
                  "views/directions.md", "views/graph.md", "views/rests-on.md",
                  "computation/verdicts.md", "computation/runs.md", "kb/claims.json"):
            with self.subTest(v):
                self.assertEqual((tmp / "s1" / v).read_bytes(), (S1 / v).read_bytes())


if __name__ == "__main__":
    unittest.main()
