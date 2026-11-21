"""Tests for academy/scripts/weekly_review.py (behind /academy:weekly-review, #107).

Hermetic: a temp workspace with an Author home and a Researcher home as git repos whose
commits are dated inside and outside the window, an Expert library with review passes, a
file board with pending decisions, and remote-tracking refs for the merges section.

Run from the repo root:  py -m unittest discover -s academy/tests -t academy/tests
"""

import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import packets as pk  # noqa: E402
import weekly_review as wr  # noqa: E402

QUIET = {"GIT_EDITOR": "true", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}

SINCE, UNTIL = "2026-11-14", "2026-11-21"
TODAY = datetime.date(2026, 11, 21)


def git(repo, *args, date=None):
    env = dict(os.environ, **QUIET)
    if date:
        stamp = date if "T" in date else date + "T12:00:00+00:00"
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = stamp
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=env,
                       stdin=subprocess.DEVNULL, timeout=60)
    if p.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr))
    return p.stdout.strip()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def commit(repo, msg, date):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg, date=date)
    return git(repo, "rev-parse", "HEAD")


def init_repo(path):
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "commit.gpgsign", "false")


def paper_claim(label, status, where="sections/intro.tex"):
    kind = label.split(":", 1)[0]
    return ("---\nid: paper:%s\nkind: %s\ntitle: %s\nstatus: %s\nlifecycle: active\n"
            "domain: dom-a\nwhere: %s\nevidence: []\nhistory:\n  - 2026-11-01 | %s | created\n"
            "---\n" % (label, {"lem": "lemma", "thm": "theorem", "prop": "proposition"}[kind],
                       label, status, where, status))


def nb_claim(cid, status):
    return ("---\nid: %s\nkind: claim\nform: prop\ntitle: t\nstatus: %s\nlifecycle: active\n"
            "domain: dom-a\nsummary: s\nevidence: []\nhistory:\n  - 2026-11-01 | %s | created\n"
            "---\n\n## Statement\n\nIt holds.\n" % (cid, status, status))


INTRO_1 = ("Intro.\n\\begin{lemma}\\label{lem:a}\nAll is well.\n\\end{lemma}\n"
           "\\begin{lemma}\\label{lem:b}\nThe first wording.\n\\end{lemma}\n")
INTRO_2 = ("Intro.\n\\begin{lemma}\\label{lem:a}\nAll is well.\n\\end{lemma}\n"
           "\\begin{lemma}\\label{lem:b}\nThe second wording.\n\\end{lemma}\n")
MAIN_1 = "Main.\n\\begin{theorem}\\label{thm:c}\nBig.\n\\end{theorem}\n"
MAIN_2 = MAIN_1 + ("\\begin{proposition}\\label{prop:d}\nNew one.\n\\end{proposition}\n"
                   "\\begin{proposition}\\label{prop:g}\nBorn proved.\n\\end{proposition}\n")
#: lem:e gains only a margin note and a comment (note-only); lem:f loses its label
EXTRA_1 = ("Extra.\n\\begin{lemma}\\label{lem:e}\nFine.\n\\end{lemma}\n"
           "\\begin{lemma}\\label{lem:f}\nGone soon.\n\\end{lemma}\n")
EXTRA_2 = ("Extra.\n\\begin{lemma}\\label{lem:e}\nFine. \\Claude{check {this} later} % a comment\n"
           "\\end{lemma}\n\\begin{lemma}\nGone soon.\n\\end{lemma}\n")


def statements_md(colours):
    """A generated Drafts/statements.md with one row per (label, colour)."""
    return "# Statement registry\n\n| label | env | title | colour | proof |\n|---|---|---|---|---|\n" + \
        "".join("| `%s` | x |  | %s | none |\n" % kv for kv in colours)

ATTEMPT = ("---\nobject: nb:C-1\nattempt: 1\nby: prover\ndate: 2026-11-17\noutcome: complete\n"
           "inputs: [paper:lem:a, C-2, \"a plain input\"]\n---\n\n## Proof\n\nBy lem a.\n")


class Fixture:
    """The temp workspace; ``self.c`` holds the interesting commit shas."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-weekly-")
        t = self.tmp
        self.paper = os.path.join(t, "paperhome")
        self.nb = os.path.join(t, "nbhome")
        self.lib = os.path.join(t, "lib")
        self.board = os.path.join(t, "board")
        os.makedirs(self.board)
        ws = {"instances": {
            "author@main": {"role": "author", "home": self.paper, "domains": ["dom-a"],
                            "ns": "paper"},
            "researcher@r1": {"role": "researcher", "home": self.nb, "domains": ["dom-a"],
                              "ns": "nb"},
            "expert@main": {"role": "expert", "home": self.lib, "domains": ["dom-a"]}},
            "board": self.board.replace("\\", "/")}
        self.ws_path = os.path.join(t, "workspace.json")
        write(self.ws_path, json.dumps(ws))
        self.ws = ac.load_workspace(self.ws_path)
        write(os.path.join(t, ".gitmodules"),
              '[submodule "paperhome"]\n\tpath = paperhome\n\turl = x\n'
              '[submodule "nbhome"]\n\tpath = nbhome\n\turl = y\n')
        self.c = {}
        self._paper()
        self._notebook()
        self._library()

    def _paper(self):
        p = self.paper
        init_repo(p)
        write(os.path.join(p, ".claude", "academy.json"), json.dumps({
            "schema": 1, "role": "author", "instance": "author@main", "ns": "paper",
            "registry": {"profile": "paper", "root": "claims"},
            "paths": {"tex": ["main.tex", "sections/*.tex"], "records": "claims"},
            "author": {"noteMacros": {"machine": ["\\Claude"], "human": ["\\ada"]}}}))
        write(os.path.join(p, "main.tex"), "\\input{sections/intro}\n")
        write(os.path.join(p, "sections", "intro.tex"), INTRO_1)
        write(os.path.join(p, "sections", "main.tex"), MAIN_1)
        write(os.path.join(p, "sections", "extra.tex"), EXTRA_1)
        write(os.path.join(p, "Drafts", "statements.md"), statements_md([("thm:c", "conjectural")]))
        for label, st, where in (("lem:a", "sketch", "sections/intro.tex"),
                                 ("lem:b", "sketch", "sections/intro.tex"),
                                 ("lem:e", "sketch", "sections/extra.tex"),
                                 ("lem:f", "sketch", "sections/extra.tex"),
                                 ("thm:c", "conjectured", "sections/main.tex")):
            write(os.path.join(p, "claims", "paper", label.replace(":", "__") + ".md"),
                  paper_claim(label, st, where))
        self.c["p1"] = commit(p, "start", "2026-11-01")
        write(os.path.join(p, "notes.txt"), "not a tex file\n")
        self.c["p_other"] = commit(p, "unrelated file", "2026-11-15")
        write(os.path.join(p, "claims", "paper", "lem__a.md"), paper_claim("lem:a", "proved"))
        write(os.path.join(p, "sections", "intro.tex"), INTRO_2)
        write(os.path.join(p, "sections", "main.tex"), MAIN_2)
        write(os.path.join(p, "claims", "paper", "prop__d.md"),
              paper_claim("prop:d", "sketch", "sections/main.tex"))
        write(os.path.join(p, "claims", "paper", "prop__g.md"),
              paper_claim("prop:g", "proved", "sections/main.tex"))
        write(os.path.join(p, "sections", "extra.tex"), EXTRA_2)
        write(os.path.join(p, "Drafts", "statements.md"), statements_md([("thm:c", "sketch")]))
        self.c["p2"] = commit(p, "the week's paper work", "2026-11-16")
        # 01:00 at +02:00 on the 21st is the 20th in UTC
        write(os.path.join(p, "sections", "other.tex"), "Other.\n")
        self.c["p_tz"] = commit(p, "late at night, east of UTC", "2026-11-21T01:00:00+02:00")
        write(os.path.join(p, "claims", "paper", "thm__c.md"),
              paper_claim("thm:c", "proved", "sections/main.tex"))
        self.c["p3"] = commit(p, "after the window", "2026-11-25")
        # remote-tracking refs, as a fetch would leave them (nothing is fetched)
        git(p, "update-ref", "refs/remotes/origin/main", self.c["p2"])
        git(p, "update-ref", "refs/remotes/origin/2026-11-10/merged-topic/author", self.c["p1"])
        git(p, "update-ref", "refs/remotes/origin/2026-11-17/stack-low/author", self.c["p_tz"])
        git(p, "update-ref", "refs/remotes/origin/2026-11-18/open-topic/author", self.c["p3"])
        env = dict(GIT_AUTHOR_DATE="2026-11-19T12:00:00+00:00",
                   GIT_COMMITTER_DATE="2026-11-19T12:00:00+00:00")
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            self.c["side"] = git(p, "commit-tree", self.c["p2"] + "^{tree}", "-p", self.c["p2"],
                                 "-m", "a side branch")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        git(p, "update-ref", "refs/remotes/origin/2026-11-19/side/author", self.c["side"])
        git(p, "update-ref", "refs/remotes/origin/not-a-work-branch", self.c["p3"])

    def _notebook(self):
        n = self.nb
        init_repo(n)
        write(os.path.join(n, ".claude", "academy.json"), json.dumps({
            "schema": 1, "role": "researcher", "instance": "researcher@r1", "ns": "nb",
            "registry": {"profile": "notebook"}}))
        write(os.path.join(n, "objects", "claim", "C-1.md"), nb_claim("C-1", "sketch"))
        write(os.path.join(n, "objects", "claim", "C-2.md"), nb_claim("C-2", "conjectured"))
        self.c["n1"] = commit(n, "start", "2026-11-01")
        write(os.path.join(n, "objects", "claim", "C-1.md"), nb_claim("C-1", "proved-modulo"))
        write(os.path.join(n, "proofs", "C-1", "attempt-1.md"), ATTEMPT)
        write(os.path.join(n, "proofs", "C-1", "attack.md"), "not an attempt\n")
        self.c["n2"] = commit(n, "attempt and status", "2026-11-17")
        git(n, "update-ref", "refs/remotes/origin/main", self.c["n2"])

    def _library(self):
        L = self.lib
        write(os.path.join(L, ".claude", "academy.json"), json.dumps({
            "schema": 1, "role": "expert", "instance": "expert@main",
            "paths": {"reviews": "reviews"}}))
        write(os.path.join(L, "reviews", "paper", "lem-a", "2026-11-02-T-0001", "decision.md"),
              "- outcome: `gap`\n")
        write(os.path.join(L, "reviews", "paper", "lem-a", "2026-11-15-T-0002", "decision.md"),
              "# Decision\n\n- outcome: `confirmed`\n")
        write(os.path.join(L, "reviews", "nb", "C-1", "2026-11-17-T-0003", "decision.md"),
              "Outcome (decision_table.py): confirmed-modulo\n")
        write(os.path.join(L, "reviews", "paper", "prop-g", "2026-11-10-T-0004", "decision.md"),
              "- outcome: `confirmed`\n")

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class FixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = Fixture()

    @classmethod
    def tearDownClass(cls):
        cls.fx.close()


# ---------------------------------------------------------------------------- pure parts

class TestWindow(unittest.TestCase):
    def test_default_is_the_last_seven_days(self):
        self.assertEqual(wr.window(None, None, today=TODAY), ("2026-11-14", "2026-11-21"))

    def test_since_and_until_given(self):
        self.assertEqual(wr.window("2026-11-01", "2026-11-03", today=TODAY),
                         ("2026-11-01", "2026-11-03"))

    def test_bad_dates_refused(self):
        with self.assertRaises(ValueError):
            wr.window("2026-13-01", None, today=TODAY)
        with self.assertRaises(ValueError):
            wr.window("2026-11-10", "2026-11-01", today=TODAY)


class TestDiffRecords(unittest.TestCase):
    def test_added_reworded_status_and_unchanged(self):
        old = {"a": {"status": "sketch", "hash": "h1"}, "b": {"status": "sketch", "hash": "h2"},
               "e": {"status": "open", "hash": "h5"}, "gone": {"status": "open", "hash": "h9"}}
        new = {"a": {"status": "proved", "hash": "h1"}, "b": {"status": "sketch", "hash": "h3"},
               "e": {"status": "open", "hash": "h5"}, "d": {"status": "sketch", "hash": "h4"}}
        out = {c["id"]: c for c in wr.diff_records(old, new)}
        self.assertEqual(sorted(out), ["a", "b", "d", "gone"])
        self.assertEqual(out["a"]["changes"], ["status"])
        self.assertEqual((out["a"]["old_status"], out["a"]["new_status"]), ("sketch", "proved"))
        self.assertEqual(out["b"]["changes"], ["reworded"])
        self.assertEqual((out["b"]["old_hash"], out["b"]["new_hash"]), ("h2", "h3"))
        self.assertEqual(out["d"]["changes"], ["added"])
        self.assertIsNone(out["d"]["old_status"])
        self.assertEqual(out["gone"]["changes"], ["removed"])

    def test_both_status_and_wording(self):
        out = wr.diff_records({"a": {"status": "sketch", "hash": "1"}},
                              {"a": {"status": "proved", "hash": "2"}})
        self.assertEqual(out[0]["changes"], ["reworded", "status"])


class TestLabelLines(unittest.TestCase):
    def test_first_label_wins_with_its_line(self):
        texts = {"sections/x.tex": "a\n\\begin{lemma}\\label{lem:a}\n",
                 "sections/y.tex": "\\label{lem:b}\n\\label{lem:a}\n"}
        got = wr.label_lines(texts)
        self.assertEqual(got["lem:a"], ("sections/x.tex", 2))
        self.assertEqual(got["lem:b"], ("sections/y.tex", 1))


class TestDecisionSummary(unittest.TestCase):
    ITEMS = [
        {"id": "T-0001", "item_kind": "code", "source": "ticket-human", "question": "Ok?"},
        {"id": "T-0002", "item_kind": "verify", "source": "ticket-blocked", "question": "Ok?"},
        {"id": "T-0003", "item_kind": "experiment", "source": "ticket-human",
         "question": "Run the search?"},
        {"id": "T-0004", "item_kind": "decision", "source": "ticket-human",
         "question": "Which inputs?", "ruling": {"subject": "nb:C-1"}},
        {"id": "T-0005", "item_kind": "cite", "source": "ticket-blocked",
         "question": "Read the source?"},
        {"id": "P-0001/D1", "item_kind": "verification", "source": "packet", "question": "Recolour?"},
        {"id": "P-0002/D1", "item_kind": "notation", "source": "packet", "question": "Which symbol?"},
        {"id": "T-0006", "item_kind": "prove", "source": "ticket-human", "question": "Prove it?"},
    ]

    def test_counts_routine_and_groups(self):
        s = wr.summarise_decisions(self.ITEMS)
        self.assertEqual(s["total"], 8)
        self.assertEqual(s["by_kind"]["ticket:code"], 1)
        self.assertEqual(s["by_kind"]["packet:verification"], 1)
        self.assertEqual(s["routine"], 3)                 # code, verify, verification packet
        groups = {g: [i["id"] for i in rows] for g, rows in s["real"].items()}
        self.assertEqual(groups["experiment"], ["T-0003"])
        self.assertEqual(groups["ruling"], ["T-0004"])
        self.assertEqual(groups["source"], ["T-0005"])     # a cite parked on the human
        self.assertEqual(groups["notation-structure"], ["P-0002/D1"])
        self.assertEqual(groups["proof"], ["T-0006"])
        self.assertNotIn("T-0001", sum(groups.values(), []))

    def test_unknown_kind_is_real_not_dropped(self):
        s = wr.summarise_decisions([{"id": "T-0009", "source": "ticket-human", "question": "?"}])
        self.assertEqual(s["routine"], 0)
        self.assertEqual([i["id"] for i in s["real"]["other"]], ["T-0009"])


class TestParseRefs(unittest.TestCase):
    def test_work_branches_only_with_utc_age(self):
        # 2026-11-18T23:30:00Z: the 18th in UTC whatever the committer's zone said
        ts = int(datetime.datetime(2026, 11, 18, 23, 30, tzinfo=datetime.timezone.utc).timestamp())
        text = ("origin/2026-11-18/topic/author\x1f%s\x1f%d\n"
                "origin/feature\x1f%s\x1f%d\n"
                "origin/main\x1f%s\x1f%d\n"
                "origin/HEAD\x1f%s\x1f%d\n") % ("a" * 40, ts, "b" * 40, ts, "c" * 40, ts,
                                                "c" * 40, ts)
        rows = wr.parse_refs(text, TODAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["branch"], "2026-11-18/topic/author")
        self.assertEqual(rows[0]["sha"], "a" * 40)
        self.assertEqual(rows[0]["date"], "2026-11-18")
        self.assertEqual(rows[0]["age_days"], 3)


class TestStackTips(unittest.TestCase):
    def test_tips_and_depth(self):
        rows = [{"branch": "2026-11-01/a/author", "sha": "a"},
                {"branch": "2026-11-02/b/author", "sha": "b"},
                {"branch": "2026-11-03/c/author", "sha": "c"},
                {"branch": "2026-11-04/d/author", "sha": "d"}]
        # a <- b <- c is one stack; d stands alone
        unique = {"2026-11-01/a/author": {"a"}, "2026-11-02/b/author": {"a", "b"},
                  "2026-11-03/c/author": {"a", "b", "c"}, "2026-11-04/d/author": {"d"}}
        tips = wr.stack_tips(rows, unique)
        self.assertEqual([(t["branch"], t["depth"], t["ahead"]) for t in tips],
                         [("2026-11-03/c/author", 3, 3), ("2026-11-04/d/author", 1, 1)])

    def test_two_names_on_one_commit_are_one_tip(self):
        rows = [{"branch": "2026-11-01/a/author", "sha": "x"},
                {"branch": "2026-11-02/b/author", "sha": "x"}]
        unique = {r["branch"]: {"x"} for r in rows}
        tips = wr.stack_tips(rows, unique)
        self.assertEqual([(t["branch"], t["depth"]) for t in tips], [("2026-11-02/b/author", 2)])
        self.assertEqual(tips[0]["same_commit"], ["2026-11-01/a/author"])


class TestNotes(unittest.TestCase):
    def test_strip_note_macros_balanced_and_comments(self):
        text = "A \\Claude{one {nested} two} B \\ada[x]{y} C % gone\n50\\% stays \\Clauder{kept}"
        self.assertEqual(wr.strip_notes(text, ["\\Claude", "\\ada"]),
                         "A  B  C \n50\\% stays \\Clauder{kept}")

    def test_macros_of_config(self):
        cfg = {"author": {"noteMacros": {"human": ["\\ada"], "machine": ["\\Claude", "\\cl"]}}}
        self.assertEqual(wr.note_macros(cfg), ["\\Claude", "\\ada", "\\cl"])

    def test_diff_note_only(self):
        out = wr.diff_records({"a": {"status": "s", "hash": "1", "norm": "n"}},
                              {"a": {"status": "s", "hash": "2", "norm": "n"}})
        self.assertEqual(out[0]["changes"], ["note-only"])


# ---------------------------------------------------------------------- sections, on git

class TestRegistryChanges(FixtureCase):
    def test_paper_changes_by_section(self):
        out = wr.registry_changes(self.fx.ws, SINCE, UNTIL, notes=[])
        paper = next(h for h in out if h["instance"] == "author@main")
        self.assertEqual(paper["base"], self.fx.c["p1"])
        self.assertEqual(paper["head"], self.fx.c["p_tz"])
        self.assertEqual([(c["sha"], c["date"]) for c in paper["commits"]],
                         [(self.fx.c["p_tz"], "2026-11-20"), (self.fx.c["p2"], "2026-11-16")])
        by = {c["qid"]: c for c in paper["changes"]}
        self.assertEqual(sorted(by), ["paper:lem:a", "paper:lem:b", "paper:lem:e", "paper:lem:f",
                                      "paper:prop:d", "paper:prop:g", "paper:thm:c"])
        self.assertEqual(by["paper:lem:a"]["changes"], ["status"])
        self.assertEqual(by["paper:lem:a"]["new_status"], "proved")
        self.assertEqual(by["paper:lem:b"]["changes"], ["reworded"])
        self.assertEqual(by["paper:lem:b"]["where"], "sections/intro.tex:5")
        self.assertEqual(by["paper:prop:d"]["changes"], ["added"])
        self.assertEqual(by["paper:prop:d"]["section"], "main")
        self.assertEqual(by["paper:prop:d"]["where"], "sections/main.tex:5")
        self.assertEqual(by["paper:lem:e"]["changes"], ["note-only"])
        # a label gone from the tex: said so, and the old line is not printed
        self.assertEqual(by["paper:lem:f"]["changes"], ["label-removed"])
        self.assertEqual(by["paper:lem:f"]["where"], "claims/paper/lem__f.md")
        # thm:c: recoloured in the window; its status change came after the window
        self.assertEqual(by["paper:thm:c"]["changes"], ["recoloured"])
        self.assertEqual((by["paper:thm:c"]["old_colour"], by["paper:thm:c"]["new_colour"]),
                         ("conjectural", "sketch"))
        self.assertEqual(by["paper:thm:c"]["new_status"], "conjectured")

    def test_notebook_home_status_change(self):
        out = wr.registry_changes(self.fx.ws, SINCE, UNTIL, notes=[])
        nb = next(h for h in out if h["instance"] == "researcher@r1")
        self.assertEqual([(c["qid"], c["old_status"], c["new_status"]) for c in nb["changes"]],
                         [("nb:C-1", "sketch", "proved-modulo")])

    def test_empty_window_has_no_changes(self):
        out = wr.registry_changes(self.fx.ws, "2026-11-02", "2026-11-03", notes=[])
        self.assertTrue(all(h["changes"] == [] and h["commits"] == [] for h in out))

    def test_a_missing_home_is_noted(self):
        ws = json.loads(json.dumps(self.fx.ws))
        ws["instances"]["author@main"]["home"] = os.path.join(self.fx.tmp, "nowhere")
        notes = []
        out = wr.registry_changes(ws, SINCE, UNTIL, notes=notes)
        self.assertNotIn("author@main", [h["instance"] for h in out])
        self.assertTrue(any("author@main" in n for n in notes))

    def test_shallow_clone_without_base_is_noted(self):
        shallow = os.path.join(self.fx.tmp, "shallow-nb")
        git(self.fx.tmp, "clone", "-q", "--depth", "1", "file://" + self.fx.nb.replace("\\", "/"),
            shallow)
        ws = json.loads(json.dumps(self.fx.ws))
        ws["instances"]["researcher@r1"]["home"] = shallow
        notes = []
        wr.registry_changes(ws, SINCE, UNTIL, notes=notes)
        self.assertTrue(any("researcher@r1" in n and "shallow" in n for n in notes), notes)


class TestReady(FixtureCase):
    def _ready(self):
        changes = wr.registry_changes(self.fx.ws, SINCE, UNTIL, notes=[])
        return wr.ready_to_read(self.fx.ws, changes, SINCE, UNTIL, notes=[])

    def test_transitions_apart_from_added_proved(self):
        ready = self._ready()
        by = {r["qid"]: r for r in ready["statements"]}
        self.assertEqual(sorted(by), ["nb:C-1", "paper:lem:a"])
        self.assertEqual(by["paper:lem:a"]["pass"], "2026-11-15-T-0002")
        self.assertEqual(by["paper:lem:a"]["pass_date"], "2026-11-15")
        self.assertFalse(by["paper:lem:a"]["pass_before_window"])
        self.assertEqual(by["paper:lem:a"]["outcome"], "confirmed")
        self.assertTrue(by["paper:lem:a"]["decision"].endswith(
            "reviews/paper/lem-a/2026-11-15-T-0002/decision.md"))
        self.assertEqual(by["nb:C-1"]["outcome"], "confirmed-modulo")
        added = {r["qid"]: r for r in ready["added_proved"]}
        self.assertEqual(sorted(added), ["paper:prop:g"])
        self.assertEqual(added["paper:prop:g"]["pass_date"], "2026-11-10")
        self.assertTrue(added["paper:prop:g"]["pass_before_window"])

    def test_new_attempts_with_inputs_and_their_status(self):
        ready = self._ready()
        self.assertEqual(len(ready["attempts"]), 1)
        a = ready["attempts"][0]
        self.assertEqual(a["path"], "proofs/C-1/attempt-1.md")
        self.assertEqual(a["object"], "nb:C-1")
        self.assertEqual(a["outcome"], "complete")
        # a bare id is the home's own namespace's
        self.assertEqual(a["inputs"], [{"ref": "paper:lem:a", "status": "proved"},
                                       {"ref": "C-2", "status": "conjectured"},
                                       {"ref": "a plain input", "status": None}])


class TestMerges(FixtureCase):
    def test_stack_tips_of_unmerged_work_branches(self):
        notes = []
        out = wr.merges_waiting(self.fx.ws, self.fx.ws_path, today=datetime.date(2026, 11, 30),
                                notes=notes)
        by = {r["repo"]: r for r in out}
        paper = by["paperhome"]
        self.assertEqual(paper["unmerged"], 3)
        tips = {t["branch"]: t for t in paper["tips"]}
        self.assertEqual(sorted(tips), ["2026-11-18/open-topic/author", "2026-11-19/side/author"])
        top = tips["2026-11-18/open-topic/author"]
        self.assertEqual((top["sha"], top["depth"], top["ahead"]), (self.fx.c["p3"], 2, 2))
        self.assertEqual(top["age_days"], 5)
        self.assertEqual(tips["2026-11-19/side/author"]["age_days"], 11)
        # the lower branch is dated in UTC (the 20th), not the committer's 21st
        low = next(b for b in paper["branches"] if b["branch"] == "2026-11-17/stack-low/author")
        self.assertEqual(low["date"], "2026-11-20")
        self.assertEqual(by["nbhome"]["tips"], [])
        self.assertTrue(any("review state" in n for n in notes))


class TestNoGit(FixtureCase):
    def test_missing_git_is_named_not_a_crash(self):
        empty = os.path.join(self.fx.tmp, "empty-bin")
        os.makedirs(empty, exist_ok=True)
        old = os.environ["PATH"]
        os.environ["PATH"] = empty
        try:
            data = wr.gather(self.fx.ws, self.fx.ws_path, SINCE, UNTIL, today=TODAY,
                             board=self.fx.board, problems=False)
        finally:
            os.environ["PATH"] = old
        self.assertEqual(data["paper"], [])
        self.assertTrue(any("merges" in n for n in data["not_gathered"]))
        self.assertTrue(any("registry changes not gathered" in n for n in data["not_gathered"]))


class TestBoardProblems(unittest.TestCase):
    def test_delivered_without_result_and_parked(self):
        metas = [
            {"id": "T-0001", "status": "delivered", "result": "", "to": "expert@main",
             "title": "Empty", "updated": "2026-11-15"},
            {"id": "T-0002", "status": "delivered", "result": "done", "updated": "2026-11-15"},
            {"id": "T-0003", "status": "blocked", "waiting_on": ["human"], "updated": "2026-11-16",
             "title": "Needs a call"},
            {"id": "T-0004", "status": "blocked", "waiting_on": ["T-0002"], "updated": "2026-10-01"},
            {"id": "T-0005", "status": "blocked", "waiting_on": ["expert@main"],
             "updated": "2026-11-20"},
            {"id": "T-0006", "status": "open"},
        ]
        out = wr.ticket_problems(metas, SINCE, UNTIL)
        self.assertEqual([r["id"] for r in out["delivered_no_result"]], ["T-0001"])
        self.assertEqual(out["parked"]["count"], 3)
        self.assertEqual(out["parked"]["new"], 2)
        self.assertEqual(out["parked"]["by_wait"], {"human": 1, "instance": 1, "ticket": 1})

    def test_error_classes_need_a_repo(self):
        notes = []
        self.assertIsNone(wr.error_classes({"instances": {}}, SINCE, UNTIL, notes))
        self.assertTrue(any("errors.repo" in n for n in notes))

    def test_error_classes_new_in_window(self):
        issues = [{"number": 3, "title": "a", "state": "open", "created_at": "2026-11-15T10:00:00Z"},
                  {"number": 2, "title": "b", "state": "open", "created_at": "2026-11-01T10:00:00Z"},
                  {"number": 1, "title": "c", "state": "closed", "created_at": "2026-11-16T10:00:00Z"}]
        out = wr.error_classes({"errors": {"repo": "o/n"}}, SINCE, UNTIL, [],
                               lister=lambda repo: issues)
        self.assertEqual(out["open"], 2)
        self.assertEqual([i["number"] for i in out["new"]], [3, 1])


class TestRefutation(unittest.TestCase):
    def test_line_found(self):
        body = "## Ask\n\nRun it.\n\n- What would refute it: a surface with two cylinders.\n"
        self.assertEqual(wr.refutation_line(body), "What would refute it: a surface with two cylinders.")

    def test_goal_line_as_fallback_and_none(self):
        self.assertEqual(wr.refutation_line("Goal:   a falsifier\n"), "Goal:   a falsifier")
        self.assertIsNone(wr.refutation_line("nothing here"))


class TestProblems(FixtureCase):
    def test_missing_tools_are_named_not_skipped(self):
        notes = []
        tools = {"audit": os.path.join(self.fx.tmp, "no", "audit.py"),
                 "reading_list": os.path.join(self.fx.tmp, "no", "reading_list.py")}
        out = wr.gather_problems(self.fx.ws, self.fx.ws_path, tools=tools, notes=notes,
                                 run=lambda argv, cwd=None: (0, '{"items": []}', ""))
        self.assertIsNone(out["audit"])
        self.assertIsNone(out["reading_list"])
        self.assertTrue(any("audit" in n and "not present" in n for n in notes))
        self.assertTrue(any("reading_list" in n and "not present" in n for n in notes))
        self.assertEqual(out["stale"]["count"], 0)

    def test_counts_and_top_rows(self):
        audit = os.path.join(self.fx.tmp, "tools", "audit.py")
        rl = os.path.join(self.fx.tmp, "tools", "reading_list.py")
        write(audit, "")
        write(rl, "")

        def run(argv, cwd=None):
            if argv[1] == audit:
                return 0, json.dumps({"findings": [
                    {"class": "ticket-waiting-done", "id": "T-%04d" % i, "detail": "d",
                     "fix": "f"} for i in range(12)], "counts": {"ticket-waiting-done": 12},
                    "not_audited": ["x: home missing"]}), ""
            if argv[1] == rl:
                return 0, json.dumps({"rows": [{"key": "Ab12", "read": "Thm 2", "tried": "x" * 500}],
                                      "could_not_read": []}), ""
            if cwd == self.fx.paper:
                return 0, json.dumps({"items": [{"kind": "stale", "qid": "paper:lem:a",
                                                 "status": "proved"}], "board": None}), ""
            return 2, "", "stale: no reviews"
        notes = []
        out = wr.gather_problems(self.fx.ws, self.fx.ws_path,
                                 tools={"audit": audit, "reading_list": rl}, notes=notes, run=run)
        self.assertEqual(out["audit"]["count"], 12)
        self.assertEqual(len(out["audit"]["top"]), wr.TOP)
        self.assertEqual(out["audit"]["counts"], {"ticket-waiting-done": 12})
        self.assertEqual(out["reading_list"]["count"], 1)
        self.assertEqual(out["reading_list"]["top"], [{"key": "Ab12", "read": "Thm 2"}])
        self.assertEqual(out["stale"]["count"], 1)
        self.assertEqual(out["stale"]["top"][0]["qid"], "paper:lem:a")
        # the notebook home's stale run failed: named, not dropped
        self.assertTrue(any("researcher@r1" in n and "stale" in n for n in notes))
        self.assertTrue(any("x: home missing" in n for n in notes))

    def test_unparseable_output_is_named(self):
        audit = os.path.join(self.fx.tmp, "tools2", "audit.py")
        write(audit, "")
        notes = []
        out = wr.gather_problems(self.fx.ws, self.fx.ws_path,
                                 tools={"audit": audit, "reading_list": audit + ".none"},
                                 notes=notes, run=lambda argv, cwd=None: (0, "not json", ""))
        self.assertIsNone(out["audit"])
        self.assertTrue(any("audit" in n and "JSON" in n for n in notes))


class TestDecisionsFromBoard(FixtureCase):
    def test_pending_decisions_summarised(self):
        b = self.fx.board
        bd.create_ticket(b, "human", "Run the search", "Run the search?", "a result",
                         kind="experiment", as_instance="author@main", workspace=self.fx.ws,
                         date="2026-11-16", budget={"runs": 1},
                         detail="What would refute it: two cylinders of equal modulus.")
        bd.create_ticket(b, "human", "Merge the fix", "Merge it?", "a merge", kind="code",
                         as_instance="author@main", workspace=self.fx.ws, date="2026-11-16",
                         budget={"runs": 1})
        notes = []
        s = wr.decisions_section(b, self.fx.ws, notes=notes)
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["routine"], 1)
        self.assertEqual([i["title"] for i in s["real"]["experiment"]], ["Run the search"])
        self.assertEqual(s["real"]["experiment"][0]["refutes"],
                         "What would refute it: two cylinders of equal modulus.")
        self.assertEqual(notes, [])

    def test_unreadable_board_is_noted(self):
        notes = []
        s = wr.decisions_section(os.path.join(self.fx.tmp, "no-board"), self.fx.ws, notes=notes,
                                 pending=lambda *a, **k: (_ for _ in ()).throw(OSError("gone")))
        self.assertIsNone(s)
        self.assertTrue(any("decisions" in n for n in notes))


class TestReportAndCli(FixtureCase):
    def _gather(self):
        return wr.gather(self.fx.ws, self.fx.ws_path, SINCE, UNTIL, today=TODAY,
                         board=self.fx.board, problems=False)

    def test_render_has_every_section_and_not_gathered(self):
        data = self._gather()
        md = wr.render(data)
        for head in ("## 1. Paper changes by section", "## 2. Ready to read", "## 3. Decisions",
                     "## 4. Merges waiting", "## 5. Problems", "## Not gathered"):
            self.assertIn(head, md)
        self.assertIn("`paper:lem:b`", md)
        self.assertIn("sections/intro.tex:5", md)
        self.assertIn("label removed from tex", md)
        self.assertIn("note-only", md)
        self.assertIn("conjectural -> sketch", md)
        self.assertIn("2026-11-18/open-topic/author", md)
        self.assertNotIn("2026-11-17/stack-low/author", md.split("## 4.")[1].split("## 5.")[0])
        self.assertIn("problems not gathered (--no-problems)", md)
        self.assertIn("Added already proved", md)
        self.assertIn("2026-11-10 (before the window)", md)
        self.assertIn("as of %s, not as of --until" % TODAY.isoformat(), md)
        ng = md.split("## Not gathered")[1]
        for gap in ("coloured diff", "review state", "error-class"):
            self.assertIn(gap, ng)

    def test_cli_json_and_out(self):
        out_md = os.path.join(self.fx.tmp, "out", "week.md")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = wr.main(["--workspace", self.fx.ws_path, "--board", self.fx.board,
                          "--since", SINCE, "--until", UNTIL, "--json", "--no-problems",
                          "--out", out_md])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["window"], {"since": SINCE, "until": UNTIL})
        for key in ("paper", "ready", "decisions", "merges", "problems", "not_gathered"):
            self.assertIn(key, data)
        self.assertEqual(data["counts"]["paper_changes"], 7)
        self.assertEqual(data["counts"]["ready_statements"], 2)
        self.assertEqual(data["counts"]["ready_added_proved"], 1)
        self.assertEqual(data["counts"]["merge_tips"], 2)
        self.assertIn("tickets", data["problems"])
        with open(out_md, encoding="utf-8") as fh:
            self.assertIn("# Weekly review", fh.read())

    def test_reads_only(self):
        before = {r: git(r, "status", "--porcelain") for r in (self.fx.paper, self.fx.nb)}
        heads = {r: git(r, "rev-parse", "HEAD") for r in (self.fx.paper, self.fx.nb)}
        self._gather()
        for r in (self.fx.paper, self.fx.nb):
            self.assertEqual(git(r, "status", "--porcelain"), before[r])
            self.assertEqual(git(r, "rev-parse", "HEAD"), heads[r])


class TestDecisionsItemKind(unittest.TestCase):
    """decisions.py items carry the ticket's or packet's own kind (``item_kind``)."""

    def test_item_kind_on_tickets_and_packets(self):
        import decisions as dc
        tmp = tempfile.mkdtemp(prefix="academy-weekly-dc-")
        try:
            ws_path = os.path.join(tmp, "workspace.json")
            write(ws_path, json.dumps({"instances": {
                "author@main": {"role": "author", "home": os.path.join(tmp, "a"),
                                "domains": ["d"], "ns": "paper"}},
                "board": os.path.join(tmp, "board").replace("\\", "/")}))
            ws = ac.load_workspace(ws_path)
            os.makedirs(ws["board"])
            bd.create_ticket(ws["board"], "human", "Q", "Q?", "an answer", kind="question",
                             as_instance="author@main", workspace=ws, date="2026-11-16",
                             budget={"runs": 1})
            pk.create_packet(ws["board"], "author@main", "A note", by="author@main/x",
                             body=("\n## Summary\n\nx\n\n## Produced\n\nx\n\n## Established vs "
                                   "assumed\n\nx\n\n## Evidence\n\nx\n\n## Decisions needed\n\n"
                                   "### D1. Which?\n\n- (a) One.\n- (b) Two.\n- Recommendation: (a), "
                                   "shorter.\n\n## Machine "
                                   "notes\n\nNone.\n\n## Decision\n"),
                             workspace=ws, date="2026-11-16", kind="notation")
            kinds = {i["source"]: i["item_kind"] for i in dc.pending_decisions(ws["board"])}
            self.assertEqual(kinds, {"ticket-human": "question", "packet": "notation"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
