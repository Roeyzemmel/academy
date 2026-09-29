"""Tests for render_packets.py (dashboard, deep dives) and gather_deep_dive.py.

Run from the repo root:  py -m unittest discover academy/tests
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import packets as pk  # noqa: E402
import render_packets as rp  # noqa: E402
import gather_deep_dive as gd  # noqa: E402
from test_board import DECISION_BODY, INFO_BODY  # noqa: E402

DATE = "2026-09-28"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class Tags(HTMLParser):
    """Collects start tags with attributes and checks elements are balanced."""
    VOID = {"meta", "link", "br", "img", "hr", "input", "source", "wbr"}

    def __init__(self):
        super().__init__()
        self.tags, self.stack, self.errors = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append("unexpected </%s> (open: %s)" % (tag, self.stack[-3:]))
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()


def parse(page):
    t = Tags()
    t.feed(page)
    t.close()
    return t


class PageContract(object):
    """Mixin: the artifact page contract, checked on any rendered page."""

    def check_contract(self, page):
        t = parse(page)
        self.assertEqual(t.errors, [])
        self.assertEqual(t.stack, [])
        self.assertLess(page.find("<title>"), 8192)
        for tag in ("html", "head", "body"):
            self.assertNotIn(tag, [x for x, _ in t.tags])
        # external resources: scripts only from jsdelivr/npm, stylesheets only Google Fonts
        for tag, attrs in t.tags:
            if tag == "script" and attrs.get("src"):
                self.assertTrue(attrs["src"].startswith("https://cdn.jsdelivr.net/npm/katex@"),
                                attrs["src"])
            if tag == "link" and attrs.get("rel") == "stylesheet":
                self.assertTrue(attrs["href"].startswith("https://fonts.googleapis.com/"))
            if tag == "img":
                self.assertTrue(attrs.get("src", "").startswith("data:"))
        self.assertIn("katex.min.js", page)
        self.assertIn("auto-render.min.js", page)
        self.assertIn('"output": "mathml"', page)
        # theme tokens: light on :root, dark under the media query and data-theme
        css = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
        self.assertRegex(css, r":root\s*\{[^}]*--bg:")
        self.assertIn('@media (prefers-color-scheme: dark)', css)
        self.assertIn(':root:not([data-theme="light"])', css)
        self.assertIn(':root[data-theme="dark"]', css)
        self.assertRegex(css, r"body\s*\{[^}]*background:\s*var\(--bg\)")
        self.assertRegex(css, r"body\s*\{[^}]*padding-inline:\s*16px")
        # every token used is defined on bare :root
        root = re.search(r"^:root\s*\{(.*?)\}", css, re.S | re.M).group(1)
        defined = set(re.findall(r"(--[a-z0-9-]+):", root))
        used = set(re.findall(r"var\((--[a-z0-9-]+)\)", css))
        self.assertEqual(used - defined, set())
        self.assertNotRegex(css, r"min-width:\s*\d{3,}px")


class TestMarkdown(unittest.TestCase):
    def test_math_is_left_for_katex(self):
        out = rp.inline(r"bound $|h| \le 2*x*y$ and **bold** and *em*")
        self.assertIn(r"$|h| \le 2*x*y$", out)
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("<em>em</em>", out)

    def test_escaping(self):
        out = rp.inline("<script>alert(1)</script> & `a<b`")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<code>a&lt;b</code>", out)
        self.assertIn("$a &lt; b$", rp.inline("$a < b$"))

    def test_links_only_http(self):
        self.assertIn('href="https://arxiv.org/abs/1"', rp.inline("[x](https://arxiv.org/abs/1)"))
        self.assertNotIn("href", rp.inline("[x](javascript:alert(1))"))

    def test_chips_carry_status(self):
        ctx = rp.Ctx({"paper:lem:x": "sketch"})
        out = rp.inline("see [[paper:lem:x]] and [[s1:Q2]]", ctx)
        self.assertIn("st-sketch", out)
        self.assertIn("no status recorded", out)

    def test_idrefs_link_when_on_page(self):
        ctx = rp.Ctx(anchors=["P-0001"])
        out = rp.inline("see P-0001 and T-0007", ctx)
        self.assertIn('<a class="ref" href="#P-0001">P-0001</a>', out)
        self.assertIn('<span class="ref">T-0007</span>', out)

    def test_blocks(self):
        md = ("# Head\n\nPara one\ncontinues.\n\n- item one\n  continued\n- item two\n\n"
              "1. first\n2. second\n\n```\ncode <x>\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
              "> quoted\n")
        out = rp.markdown(md)
        self.assertIn("<h3>Head</h3>", out)
        self.assertIn("<p>Para one continues.</p>", out)
        self.assertIn("<li>item one continued</li>", out)
        self.assertIn("<ol>", out)
        self.assertIn("code &lt;x&gt;", out)
        self.assertIn("<td>1</td>", out)
        self.assertIn("<blockquote>", out)
        self.assertEqual(parse(out).errors, [])

    def test_status_classes(self):
        self.assertEqual(rp.status_class("proved"), "proved")
        self.assertEqual(rp.status_class("Proved"), "proved")
        self.assertEqual(rp.status_class("proved-modulo"), "modulo")
        self.assertEqual(rp.status_class("Disproved"), "refuted")
        self.assertEqual(rp.status_class(None), "unknown")
        self.assertEqual(rp.status_class("weird"), "other")
        for s in ac.CLAIM_STATUSES:
            self.assertNotIn(rp.status_class(s), ("unknown", "other"), s)


class BoardFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-render-")
        self.board = os.path.join(self.tmp, "board")
        os.makedirs(self.board)
        self.ws = None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def packet(self, instance, title, body=DECISION_BODY, **kw):
        return pk.create_packet(self.board, instance, title, kind=kw.pop("kind", "other"),
                                body=body, date=DATE, **kw)


class TestDashboard(BoardFixture, PageContract):
    def test_groups_open_packets_by_instance(self):
        self.packet("scientist@main", "Report on the <search>", kind="experiment-report")
        self.packet("expert@main", "Verify lem x", kind="verification",
                    status_before="sketch", status_proposed="proved")
        self.packet("author@main", "Informational", body=INFO_BODY)
        self.packet("expert@main", "Already decided")
        pk.decide_packet(self.board, "P-0004", "a", 1, date=DATE)
        pk.decide_packet(self.board, "P-0004", "a", 2, date=DATE)
        ws = {"instances": {"expert@main": {}, "author@main": {}, "scientist@main": {}}}
        page = rp.render_dashboard(self.board, ws, date=DATE)
        self.check_contract(page)
        # grouped in workspace order; decided packets left out
        heads = re.findall(r'<section class="group" id="([^"]+)"', page)
        self.assertEqual(heads, ["expert@main", "author@main", "scientist@main"])
        self.assertNotIn("Already decided", page)
        self.assertIn('id="P-0002"', page)
        self.assertIn("Report on the &lt;search&gt;", page)
        self.assertIn("Status legend", page)
        for s in ac.CLAIM_STATUSES:
            self.assertIn(">%s<" % s, page)                 # every status in the legend
        self.assertIn("st-sketch", page)
        self.assertIn("st-proved", page)
        self.assertIn("awaiting your answer", page)
        self.assertIn(r"$|h| \le 2$", page)
        self.assertIn("<strong>3</strong> open packets", page)
        self.assertIn("<strong>4</strong> decisions awaiting you", page)
        with_all = rp.render_dashboard(self.board, ws, include_decided=True)
        self.assertIn("Already decided", with_all)

    def test_answered_decision_shown(self):
        self.packet("expert@main", "Half answered")
        pk.decide_packet(self.board, "P-0001", "b", 1, comment="later", date=DATE)
        page = rp.render_dashboard(self.board, None, date=DATE)
        self.assertIn("answered %s" % DATE, page)
        self.assertIn("(b) Wait.", page)
        self.assertIn("1 decision pending", page)

    def test_empty_board(self):
        page = rp.render_dashboard(self.board, None, date=DATE)
        self.check_contract(page)
        self.assertIn("No open packets", page)

    def test_malformed_packet_is_flagged_not_fatal(self):
        write(os.path.join(self.board, "packets", "expert@main", "P-0007-bad.md"),
              "---\npacket: P-0007\ntitle: Bad\ninstance: expert@main\nkind: other\nby: x y\n"
              "state: open\ncreated: 2026-09-28\n---\n\n## Summary\n\nshort\n")
        page = rp.render_dashboard(self.board, None)
        self.assertIn("Packet format:", page)

    def test_cli_writes_default_path(self):
        self.packet("expert@main", "One")
        with redirect_stdout(io.StringIO()):
            rc = rp.main(["--board", self.board, "--workspace",
                          os.path.join(self.tmp, "missing.json")])
        self.assertEqual(rc, 0)
        out = os.path.join(self.board, ".render", "review.html")
        with open(out, "r", encoding="utf-8", newline="") as fh:
            text = fh.read()
        self.assertNotIn("\r", text)
        self.assertIn("One", text)


def sample_bundle(kind):
    stmts = [
        {"id": "paper:lem:x", "title": "Strip bound", "status": "sketch", "role": "subject",
         "statement": "For all $x \\in X$ the bound holds.", "where": "sections/a.tex"},
        {"id": "paper:lem:y", "title": "Input", "status": "proved", "role": "dependency",
         "depth": 1, "statement": "Base lemma."},
        {"id": "paper:lem:z", "title": "Deeper", "status": None, "role": "dependency",
         "depth": 2},
        {"id": "s1:Q2", "title": "Open question", "status": "open", "role": "modulo"},
        {"id": "paper:thm:main", "status": "conjectured", "role": "rests_on"},
        {"id": "lab:ew", "status": "supported", "role": "evidence_for"},
        {"id": "s1:D1", "status": "open", "role": "member"},
        {"id": "paper:rmk:c", "status": "proved", "role": "cites"},
        {"id": "lab:bear", "status": "open", "role": "bears_on"},
        {"id": "paper:ex:e", "status": "proved", "role": "example"},
        {"id": "paper:defn:d", "status": "proved", "role": "definition"},
        {"id": "paper:x:odd", "status": "proved", "role": "some_new_role"},
    ]
    return {"schema": 1, "kind": kind, "subject": "paper:lem:x", "title": "Strip bound",
            "generated": DATE, "object": dict(stmts[0]), "statements": stmts,
            "sections": [{"heading": "Why it matters",
                          "markdown": "It feeds [[paper:thm:main]] via $\\R$."}],
            "cards": [{"key": "LMW16", "pinpoint": "Thm1.3", "text": "> quoted *text*"}],
            "reviews": [{"path": "reviews/paper/lem-x/A.md", "text": "CONFIRMED"}],
            "reports": [{"packet": "P-0003", "title": "EW", "status_proposed": "supported",
                         "text": "#### Conclusion\n\nsupports"}],
            "results": [{"path": "results/r.json", "text": "{\"a\": \"<b>\"}", "raw": True}],
            "notes": ["no card for XYZ"], "macros": {"\\R": "\\mathbb{R}"}}


def complete_bundle(kind="claim"):
    b = sample_bundle(kind)
    for st in b["statements"]:
        if not st.get("status"):
            st["status"] = "open"
    return b


class TestDeepDive(unittest.TestCase, PageContract):
    def test_every_kind_renders_with_a_badge_on_every_statement(self):
        for kind in rp.DEEP_DIVE_KINDS:
            with self.subTest(kind=kind):
                self.assertTrue(os.path.isfile(os.path.join(rp.TEMPLATE_DIR, kind + ".html")))
                page = rp.render_deep_dive(sample_bundle(kind))
                self.check_contract(page)
                self.assertNotRegex(page, r"\{\{[^}]*\}\}")
                stmts = re.findall(r'<div class="stmt"[^>]*>.*?<div class="stmt-head">(.*?)'
                                   r'</div>', page, re.S)
                self.assertGreater(len(stmts), 0)
                for head in stmts:
                    self.assertIn('class="badge st-', head)
                # every statement in the bundle appears, each once
                for s in sample_bundle(kind)["statements"]:
                    self.assertIn('id="s-%s"' % re.sub(r"[^A-Za-z0-9_-]", "-", s["id"]),
                                  page, s["id"])
                self.assertIn("no status recorded", page)        # paper:lem:z
                self.assertIn('"\\\\R": "\\\\mathbb{R}"', page)  # macros passed to KaTeX
                if kind == "experiment":
                    self.assertIn("&lt;b&gt;", page)              # raw result escaped
                self.assertIn("Why it matters", page)
                self.assertIn("no card for XYZ", page)

    def test_chip_in_prose_has_status(self):
        page = rp.render_deep_dive(sample_bundle("claim"))
        chip = re.search(r'<span class="chip"[^>]*><code class="nomath">paper:thm:main</code>'
                         r'(<span class="badge[^"]*">[^<]*</span>)', page)
        self.assertIsNotNone(chip)
        self.assertIn("st-conj", chip.group(1))

    def test_unknown_kind_refused(self):
        with self.assertRaises(ac.AcademyError):
            rp.render_deep_dive(sample_bundle("claim"), kind="poem")

    def test_fill_template_headings(self):
        blocks = {"cards": "<p>x</p>", "reviews": "", "_roles": ["a", "b"],
                  "statements:a": "<p>A</p>", "statements:b": "<p>B</p>"}
        out = rp.fill_template("{{cards|Sources}}{{reviews|Reviews}}{{statements:a|Alpha}}"
                               "{{statements:rest}}", blocks)
        self.assertIn("<h2>Sources</h2><p>x</p>", out)
        self.assertNotIn("Reviews", out)
        self.assertEqual(out.count("<p>A</p>"), 1)
        self.assertIn("<p>B</p>", out)

    def test_check_passes_a_complete_bundle(self):
        self.assertEqual(rp.check_deep_dive(complete_bundle()), [])

    def test_check_names_every_missing_status(self):
        probs = rp.check_deep_dive(sample_bundle("claim"))
        self.assertEqual(probs, ["statement paper:lem:z has no status"])
        b = complete_bundle()
        b["sections"].append({"heading": "More", "markdown": "See [[lab:ghost]]."})
        b["statements"][1]["modulo"] = ["s1:nowhere"]
        probs = rp.check_deep_dive(b)
        self.assertEqual(len(probs), 2, probs)
        self.assertIn("[[lab:ghost]]", probs[0])
        self.assertIn("[[s1:nowhere]]", probs[1])

    def test_paper_subject_needs_no_status(self):
        b = complete_bundle()
        b["object"] = {"id": "bib:K1", "title": "A paper"}
        b["subject"] = "bib:K1"
        self.assertEqual(rp.check_deep_dive(b, "paper"), [])
        self.assertEqual(rp.check_deep_dive(b, "claim"), ["the subject bib:K1 has no status"])

    def test_cli_refuses_a_bundle_without_statuses(self):
        tmp = tempfile.mkdtemp(prefix="academy-dd-")
        try:
            bpath = os.path.join(tmp, "b.json")
            write(bpath, json.dumps(sample_bundle("claim")))
            out = os.path.join(tmp, "out.html")
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(rp.main(["--deep-dive", bpath, "--out", out]), 2)
            self.assertIn("paper:lem:z has no status", err.getvalue())
            self.assertFalse(os.path.exists(out))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cli_default_path_is_slug(self):
        tmp = tempfile.mkdtemp(prefix="academy-dd-")
        try:
            bpath = os.path.join(tmp, "b.json")
            write(bpath, json.dumps(complete_bundle()))
            wsp = os.path.join(tmp, "ws.json")
            write(wsp, json.dumps({"instances": {}, "board": os.path.join(tmp, "board")}))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(rp.main(["--workspace", wsp, "--deep-dive", bpath]), 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "board", "deep-dives",
                                                        "paper-lem-x.html")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------
# gather_deep_dive on a fixture workspace
# ----------------------------------------------------------------------------

DEF2 = """---
id: DEF-2
title: A definition
kind: definition
---

## Statement

A thing is *nice* when it is.
"""

BOUND2 = """---
id: BOUND-2
title: A bound
kind: claim
status: proved
depends_on: [DEF-2]
---

## Statement

Nice things are bounded.
"""


class TestReportCard(unittest.TestCase):
    def test_a_report_without_a_proposed_status_shows_its_kind(self):
        item = {"packet": "P-0002", "title": "EW report", "kind": "experiment-report",
                "status_proposed": None, "text": "x", "path": "p.md"}
        html_ = rp._text_block([item], rp.Ctx(), "report")
        self.assertIn('<span class="pill">experiment-report</span>', html_)
        self.assertNotIn("no status recorded", html_)
        html_ = rp._text_block([dict(item, status_proposed="supported")], rp.Ctx(), "report")
        self.assertIn('class="badge st-supported">supported<', html_)


class TestGather(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-gather-")
        t = self.tmp
        self.homes = {n: os.path.join(t, n) for n in ("paperhome", "lab", "nb", "lib")}
        ws = {"instances": {
            "author@main": {"role": "author", "home": self.homes["paperhome"], "domains": ["dom"],
                          "ns": "paper"},
            "scientist@main": {"role": "scientist", "home": self.homes["lab"],
                             "domains": ["dom"], "ns": "lab"},
            "researcher@nb": {"role": "researcher", "home": self.homes["nb"],
                              "domains": ["dom"], "ns": "s1"},
            "expert@main": {"role": "expert", "home": self.homes["lib"], "domains": ["dom"]}},
            "board": os.path.join(t, "board")}
        write(os.path.join(t, "workspace.json"), json.dumps(ws))
        self.ws = ac.load_workspace(os.path.join(t, "workspace.json"))
        paperhome = self.homes["paperhome"]
        write(os.path.join(paperhome, "main.tex"),
              "\\newcommand{\\R}{\\mathbb{R}}\n\\DeclareMathOperator{\\Aut}{Aut}\n")
        write(os.path.join(paperhome, "sections", "a.tex"),
              "\\begin{lem}\\label{lem:x}\n  For $x \\in \\R$ we have \\emph{this},\n"
              "  by \\cite[Thm 1.3]{LMW16}.\n\\end{lem}\n"
              "\\begin{thm}\\label{thm:main}\n  Main.\n\\end{thm}\n")
        write(os.path.join(paperhome, "references.bib"),
              "@article{LMW16,\n  title={Something},\n  year={2016}\n}\n")
        write(os.path.join(paperhome, "claims", "paper", "lem__x.md"),
              "---\nid: paper:lem:x\ntitle: lem:x\nstatus: sketch\nwhere: sections/a.tex\n"
              "depends_on: [paper:lem:y, s1:Q2]\n---\n")
        write(os.path.join(paperhome, "claims", "paper", "lem__y.md"),
              "---\nid: paper:lem:y\ntitle: lem:y\nstatus: proved\ndepends_on: [lem:w]\n---\n")
        write(os.path.join(paperhome, "claims", "paper", "thm__main.md"),
              "---\nid: paper:thm:main\ntitle: thm:main\nstatus: conjectured\n"
              "where: sections/a.tex\ndepends_on:\n  - paper:lem:x\n---\n")
        write(os.path.join(paperhome, "claims", "paper", "defn__marking.md"),
              "---\nid: paper:defn:marking\ntitle: Marking of a surface\nstatus: proved\n---\n")
        lab = self.homes["lab"]
        write(os.path.join(lab, "claims", "lab", "ew.md"),
              "---\nid: lab:ew\ntitle: EW search\nstatus: supported\n"
              "where: experiments/2026-09-18_ew.py\nbears_on:\n  - paper:lem:x\n"
              "evidence:\nhistory:\n  - 2026-09-24 | open | created\n---\n")
        write(os.path.join(lab, "results", "2026-09-18_ew.json"),
              json.dumps({"script": "experiments/2026-09-18_ew.py", "found": 0}))
        nb = self.homes["nb"]
        write(os.path.join(nb, "claims", "Q2.md"),
              "---\nid: Q2\naliases: [R2 Q2]\ntitle: \"Q2: the question\"\nkind: question\n"
              "status: Not settled\n---\n\n## Statement\n\nIs $K \\le 2$?\n")
        write(os.path.join(nb, "claims", "D1.md"),
              "---\nid: D1\ntitle: A direction\nkind: direction\nstatus: open\n---\n")
        write(os.path.join(nb, "claims", "Q3.md"),
              "---\nid: Q3\ntitle: Q3\nkind: question\nstatus: open\n"
              "bears_on: [D1]\n---\n")
        lib = self.homes["lib"]
        write(os.path.join(lib, "cards", "LMW16", "Thm1.3.md"),
              "> The verbatim quote.\n")
        write(os.path.join(lib, "index.md"), "| LMW16 | Lelievre-Monteil-Weiss | cached |\n")
        write(os.path.join(lib, "LMW16.txt"), "Page one of the extraction.\n")
        write(os.path.join(lib, "reviews", "paper", "lem-x", "A.md"), "CONFIRMED (run A)\n")
        pk.create_packet(os.path.join(t, "board"), "scientist@main", "EW report",
                         kind="experiment-report", subject=["lab:ew"], body=DECISION_BODY,
                         date=DATE)
        self.snapshot = self._snapshot()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snapshot(self):
        out = {}
        for dp, _dn, fn in os.walk(self.tmp):
            for f in fn:
                p = os.path.join(dp, f)
                out[p] = os.path.getmtime(p)
        return out

    def assert_read_only(self):
        self.assertEqual(self._snapshot(), self.snapshot)

    def ids(self, b, role=None):
        return [s["id"] for s in b["statements"] if role is None or s["role"] == role]

    def test_claim_closure_and_reverse_links(self):
        b = gd.gather("paper:lem:x", self.ws)
        self.assertEqual(b["kind"], "claim")
        self.assertEqual(b["object"]["status"], "sketch")
        self.assertIn("For $x \\in \\R$ we have *this*", b["object"]["statement"])
        self.assertIn("[LMW16, Thm 1.3]", b["object"]["statement"])
        self.assertEqual(self.ids(b, "dependency"), ["paper:lem:y", "s1:Q2", "paper:lem:w"])
        dep = {s["id"]: s for s in b["statements"]}
        self.assertEqual(dep["paper:lem:w"]["depth"], 2)
        self.assertIsNone(dep["paper:lem:w"]["status"])
        self.assertTrue(any("paper:lem:w" in n for n in b["notes"]))
        self.assertEqual(dep["s1:Q2"]["statement"], "Is $K \\le 2$?")
        self.assertEqual(self.ids(b, "rests_on"), ["paper:thm:main"])
        self.assertEqual(self.ids(b, "evidence_for"), ["lab:ew"])
        self.assertEqual([c["pinpoint"] for c in b["cards"] if c["key"] == "LMW16"],
                         ["Thm1.3", "index", "bib"])
        self.assertEqual(len(b["reviews"]), 1)
        self.assertEqual([r["packet"] for r in b["reports"]], ["P-0001"])
        self.assertEqual(b["macros"]["\\R"], "\\mathbb{R}")
        self.assertEqual(b["macros"]["\\Aut"], "\\operatorname{Aut}")
        page = rp.render_deep_dive(json.loads(json.dumps(b, default=str)))
        self.assertNotIn("{{", page)
        self.assert_read_only()

    def test_a_definition_gets_an_na_badge_and_renders(self):
        # verification Group G: a claim resting on a definition object (schema v2 gives
        # definitions no status) could not get a deep-dive page
        nb = self.homes["nb"]
        write(os.path.join(nb, "claims", "DEF-2.md"), DEF2)
        write(os.path.join(nb, "claims", "BOUND-2.md"), BOUND2)
        b = gd.gather("s1:BOUND-2", self.ws)
        dep = {s["id"]: s for s in b["statements"]}
        self.assertEqual(dep["s1:DEF-2"]["status"], "n/a — definition")
        self.assertEqual(rp.check_deep_dive(json.loads(json.dumps(b, default=str))), [])
        page = rp.render_deep_dive(json.loads(json.dumps(b, default=str)))
        self.assertIn('class="badge st-na">n/a — definition<', page)
        self.assertEqual(gd.status_of({"kind": "example"}), "n/a — example")
        self.assertEqual(gd.status_of({"kind": "claim"}), None)
        self.assertEqual(gd.status_of({"kind": "definition", "status": "open"}), "open")

    def test_depth_limits_closure(self):
        b = gd.gather("paper:lem:x", self.ws, depth=1)
        self.assertNotIn("paper:lem:w", self.ids(b))

    def test_notebook_ids_are_qualified(self):
        b = gd.gather("s1:Q2", self.ws)
        self.assertEqual(b["object"]["status"], "Not settled")
        self.assertEqual(self.ids(b, "rests_on"), ["paper:lem:x"])
        b2 = gd.gather("R2 Q2", self.ws)          # alias
        self.assertEqual(b2["subject"], "s1:Q2")

    def test_direction(self):
        b = gd.gather("s1:D1", self.ws)
        self.assertEqual(b["kind"], "direction")
        self.assertEqual(self.ids(b, "member"), ["s1:Q3"])

    def test_paper(self):
        b = gd.gather("bib:LMW16", self.ws)
        self.assertEqual(b["kind"], "paper")
        pins = [c["pinpoint"] for c in b["cards"]]
        self.assertIn("Thm1.3", pins)
        self.assertTrue(any(p.startswith("extraction") for p in pins))
        self.assertEqual(self.ids(b, "cites"), ["paper:lem:x"])
        self.assertEqual(gd.gather("LMW16", self.ws)["kind"], "paper")
        self.assert_read_only()

    def test_experiment_from_result_path(self):
        b = gd.gather("results/2026-09-18_ew.json", self.ws)
        self.assertEqual(b["kind"], "experiment")
        self.assertEqual(b["object"]["id"], "lab:ew")
        self.assertEqual(self.ids(b, "bears_on"), ["paper:lem:x"])
        self.assertEqual(len(b["results"]), 1)
        self.assertEqual([r["packet"] for r in b["reports"]], ["P-0001"])
        self.assertEqual(gd.gather("lab:ew", self.ws)["kind"], "experiment")
        missing = gd.gather("results/none.json", self.ws)
        self.assertTrue(missing["notes"])

    def test_concept(self):
        b = gd.gather("concept:marking", self.ws)
        self.assertEqual(b["kind"], "concept")
        self.assertEqual(self.ids(b, "definition"), ["paper:defn:marking"])
        self.assertEqual(gd.gather("paper:defn:marking", self.ws)["kind"], "concept")

    def test_unknown_subject(self):
        b = gd.gather("paper:lem:nope", self.ws)
        self.assertTrue(b["notes"])
        rp.render_deep_dive(b)

    def test_cli_to_stdout_and_file(self):
        out = os.path.join(self.tmp, "..", os.path.basename(self.tmp) + "-bundle.json")
        try:
            with redirect_stdout(io.StringIO()):
                rc = gd.main(["paper:lem:x", "--workspace",
                              os.path.join(self.tmp, "workspace.json"), "--out", out])
            self.assertEqual(rc, 0)
            with open(out, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["subject"], "paper:lem:x")
        finally:
            if os.path.exists(out):
                os.remove(out)


if __name__ == "__main__":
    unittest.main()
