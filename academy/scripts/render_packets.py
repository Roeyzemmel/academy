"""render_packets.py -- the review dashboard and the deep-dive pages.

Usage:

    py render_packets.py [--board DIR] [--out FILE] [--all]
        Render every open packet on the board into ONE self-contained HTML file,
        grouped by instance, with the status legend (default out:
        <board>/.render/review.html). ``--all`` also shows decided packets.

    py render_packets.py --deep-dive BUNDLE.json [--kind K] [--templates DIR] [--out FILE]
        Render a deep-dive bundle (from gather_deep_dive.py, plus the explainer's
        prose ``sections``) through academy/templates/deep-dive/<kind>.html
        (default out: <board>/deep-dives/<slug of the subject>.html).
        Refused (exit 2, nothing written) when a statement has no status or a
        [[ns:id]] chip names an id the bundle gives no status (check_deep_dive).

The pages follow the artifact page contract: no <html>/<head>/<body> of their own
(the publish skeleton adds them), a <title> first, colour tokens on :root with the
dark palette under prefers-color-scheme and [data-theme], a body background, a 16px
gutter and no horizontal page scroll. Mathematics in $...$ / $$...$$ is typeset by
KaTeX from cdn.jsdelivr.net/npm in MathML output mode, so no KaTeX stylesheet is
needed (external stylesheets are only allowed from Google Fonts).

Markdown is rendered by a small stdlib converter (headings, lists, paragraphs,
quotes, fenced code, simple tables, **bold**, *em*, `code`, links). In prose,
``[[ns:id]]`` becomes a chip carrying that statement's status, and ``T-NNNN`` /
``P-NNNN`` link to the packet on the same page when it is there.

Bundle format (all keys optional except ``subject``)::

    {"schema": 1, "kind": "claim|concept|paper|experiment|direction",
     "subject": "paper:lem:x", "title": "...", "generated": "YYYY-MM-DD",
     "object": {"id", "title", "status", "kind", "statement", "where", ...},
     "statements": [{"id", "title", "status", "statement", "where", "role", "depth"}],
     "sections": [{"heading": "...", "markdown": "..."}],      # the explainer's prose
     "cards": [{"key", "pinpoint", "path", "text"}],
     "reviews": [{"path", "text"}],
     "reports": [{"packet", "title", "state", "status_proposed", "path", "text"}],
     "results": [{"path", "text"}],
     "notes": ["what the gatherer could not find"],
     "macros": {"\\\\R": "\\\\mathbb{R}"}}
"""

import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402

TEMPLATE_DIR = os.path.join(PLUGIN, "templates", "deep-dive")
DEEP_DIVE_KINDS = ("concept", "claim", "paper", "experiment", "direction")
KATEX_VERSION = "0.16.11"
KATEX_BASE = "https://cdn.jsdelivr.net/npm/katex@%s/dist" % KATEX_VERSION

# ----------------------------------------------------------------------------
# Status vocabulary for badges
# ----------------------------------------------------------------------------

#: (status, css class, meaning) in legend order; one registry vocabulary
STATUS_LEGEND = (
    ("proved", "proved", "Established: two agreeing verdicts or Roey's word (black in the draft)"),
    ("proved-modulo", "modulo", "Proved from inputs that are still open (see modulo)"),
    ("sketch", "sketch", "An argument exists but is not verified (blue in the draft)"),
    ("conjectured", "conj", "Believed, no proof (red in the draft)"),
    ("supported", "supported", "Computation supports it; never a proof"),
    ("open", "open", "Unsettled"),
    ("refuted", "refuted", "Shown false"),
    ("refuted-as-stated", "refuted", "False as stated; a variant may hold"),
)
STATUS_CLASS = {s: c for s, c, _ in STATUS_LEGEND}
#: older vocabularies still found in records, mapped for colour only (text kept)
LEGACY_STATUS = {"established": "proved", "disproved": "refuted",
                 "reduced": "proved-modulo", "not settled": "open", "partial": "open",
                 "conjectural": "conjectured", "cited": "cited"}


def status_class(status):
    if status is None or str(status).strip() == "":
        return "unknown"
    s = str(status).strip().lower()
    s = LEGACY_STATUS.get(s, s)
    if s == "cited":
        return "cited"
    return STATUS_CLASS.get(s, "other")


def badge(status, extra=""):
    """A status pill. A missing status is shown as such, never omitted."""
    text = "no status recorded" if status_class(status) == "unknown" else str(status)
    return '<span class="badge st-%s%s">%s</span>' % (
        status_class(status), (" " + extra) if extra else "", html.escape(text))


# ----------------------------------------------------------------------------
# A small Markdown renderer
# ----------------------------------------------------------------------------

class Ctx(object):
    """What inline rendering needs to know: statuses by id, anchors on the page."""

    def __init__(self, statuses=None, anchors=None, titles=None):
        self.statuses = dict(statuses or {})
        self.anchors = set(anchors or ())
        self.titles = dict(titles or {})


RE_MATH = re.compile(r"\$\$.+?\$\$|(?<![\\$])\$(?!\s)[^$\n]+?(?<![\s\\])\$", re.S)
RE_CODE = re.compile(r"`([^`\n]+)`")
RE_CHIP = re.compile(r"\[\[([^\]\s]+)\]\]")
RE_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
RE_EM = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
RE_IDREF = re.compile(r"\b([TP]-\d{4,})\b")


def chip(ref, ctx):
    st = ctx.statuses.get(ref)
    title = ctx.titles.get(ref, "")
    return '<span class="chip" title="%s"><code class="nomath">%s</code>%s</span>' % (
        html.escape(title, quote=True), html.escape(ref), badge(st))


def inline(text, ctx=None):
    """Render one run of inline Markdown to HTML, leaving $...$ math intact."""
    ctx = ctx or Ctx()
    stash = []

    def keep(s):
        stash.append(s)
        return "\x00%d\x00" % (len(stash) - 1)

    text = RE_CODE.sub(lambda m: keep('<code>%s</code>' % html.escape(m.group(1))), text)
    text = RE_CHIP.sub(lambda m: keep(chip(m.group(1), ctx)), text)
    text = RE_MATH.sub(lambda m: keep(html.escape(m.group(0), quote=False)), text)
    text = html.escape(text, quote=False)
    text = RE_LINK.sub(lambda m: keep('<a href="%s" target="_blank" rel="noopener">%s</a>'
                                      % (html.escape(m.group(2), quote=True), m.group(1))),
                       text)
    text = RE_BOLD.sub(r"<strong>\1</strong>", text)
    text = RE_EM.sub(r"<em>\1</em>", text)

    def idref(m):
        x = m.group(1)
        if x in ctx.anchors:
            return keep('<a class="ref" href="#%s">%s</a>' % (x, x))
        return keep('<span class="ref">%s</span>' % x)

    text = RE_IDREF.sub(idref, text)
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
    return text


RE_ITEM = re.compile(r"^(\s*)(?:[-*]|\d+[.)])\s+(.*)$")
RE_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")


def markdown(text, ctx=None, base_level=3):
    """Render a Markdown fragment. ``#`` maps to <h{base_level}>."""
    ctx = ctx or Ctx()
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.lstrip().startswith("```"):
            j = i + 1
            buf = []
            while j < n and not lines[j].lstrip().startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append('<div class="scroll"><pre><code>%s</code></pre></div>'
                       % html.escape("\n".join(buf)))
            i = j + 1
            continue
        m = RE_HEAD.match(ln)
        if m:
            lvl = min(6, base_level + len(m.group(1)) - 1)
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2).strip(), ctx), lvl))
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                head = "".join("<th>%s</th>" % inline(c, ctx) for c in rows[0])
                body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c, ctx)
                                                        for c in r) for r in rows[1:])
                out.append('<div class="scroll"><table><thead><tr>%s</tr></thead>'
                           '<tbody>%s</tbody></table></div>' % (head, body))
            continue
        if ln.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].lstrip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % markdown("\n".join(buf), ctx,
                                                                base_level))
            continue
        m = RE_ITEM.match(ln)
        if m and len(m.group(1)) == 0:
            ordered = bool(re.match(r"^\s*\d", ln))
            items = []
            while i < n:
                cur = lines[i]
                mi = RE_ITEM.match(cur)
                if mi and len(mi.group(1)) == 0:
                    if bool(re.match(r"^\d", cur)) != ordered:
                        break                   # a list of the other type starts
                    items.append([mi.group(2)])
                elif cur.startswith("  ") and items:
                    items[-1].append(cur[2:])
                elif not cur.strip() and i + 1 < n and (lines[i + 1].startswith("  ")
                                                        or RE_ITEM.match(lines[i + 1])):
                    if RE_ITEM.match(lines[i + 1]) and not lines[i + 1].startswith(" "):
                        pass
                    elif items:
                        items[-1].append("")
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            lis = []
            for it in items:
                first, rest = it[0], it[1:]
                if any(RE_ITEM.match(r) for r in rest) or any(not r.strip() for r in rest):
                    lis.append("<li>%s%s</li>" % (inline(first, ctx),
                                                  markdown("\n".join(rest), ctx, base_level)))
                else:
                    lis.append("<li>%s</li>" % inline(" ".join([first] + rest), ctx))
            out.append("<%s>%s</%s>" % (tag, "".join(lis), tag))
            continue
        buf = []
        while i < n and lines[i].strip() and not RE_HEAD.match(lines[i]) and \
                not (RE_ITEM.match(lines[i]) and not RE_ITEM.match(lines[i]).group(1)) and \
                not lines[i].lstrip().startswith(("```", "|")) and not lines[i].startswith(">"):
            buf.append(lines[i].strip())
            i += 1
        if not buf:            # an indented list item with nothing before it
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(buf), ctx))
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Page chrome shared by the dashboard and the deep dives
# ----------------------------------------------------------------------------

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:ital,wght@0,400;0,500;'
         '0,600;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;'
         '1,8..60,400&display=swap">')

CSS = r"""
:root {
  --bg: #f4f6f8; --surface: #ffffff; --surface-2: #eef1f5; --ink: #18202b;
  --muted: #5b6676; --line: #d8dde5; --accent: #255d80; --accent-weak: #e2ecf3;
  --warn: #9a5b00; --warn-weak: #fbf0dc;
  --st-proved: #18202b; --st-modulo: #475669; --st-sketch: #1f56c4;
  --st-conj: #b3261e; --st-supported: #23784a; --st-open: #69727f;
  --st-refuted: #74399a; --st-cited: #255d80; --st-unknown: #9a5b00; --st-other: #5b6676;
  --sans: "IBM Plex Sans", "Segoe UI", system-ui, -apple-system, sans-serif;
  --serif: "Source Serif 4", "Cambria", Georgia, serif;
  --mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #10151c; --surface: #18202a; --surface-2: #1e2733; --ink: #e5e9ef;
    --muted: #9aa5b4; --line: #2d3744; --accent: #86b8d6; --accent-weak: #1d2f3c;
    --warn: #e4b35a; --warn-weak: #33291a;
    --st-proved: #e5e9ef; --st-modulo: #b3c0d0; --st-sketch: #8db2ff;
    --st-conj: #ff8f85; --st-supported: #7fd3a1; --st-open: #a3abb7;
    --st-refuted: #cfa6ec; --st-cited: #86b8d6; --st-unknown: #e4b35a; --st-other: #9aa5b4;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #10151c; --surface: #18202a; --surface-2: #1e2733; --ink: #e5e9ef;
  --muted: #9aa5b4; --line: #2d3744; --accent: #86b8d6; --accent-weak: #1d2f3c;
  --warn: #e4b35a; --warn-weak: #33291a;
  --st-proved: #e5e9ef; --st-modulo: #b3c0d0; --st-sketch: #8db2ff;
  --st-conj: #ff8f85; --st-supported: #7fd3a1; --st-open: #a3abb7;
  --st-refuted: #cfa6ec; --st-cited: #86b8d6; --st-unknown: #e4b35a; --st-other: #9aa5b4;
}
* { box-sizing: border-box; }
.page, .group, .packet, .decisions, .decision, .stmts, .stmt, .subject, .dd-section, .card,
.prose, .masthead { grid-template-columns: minmax(0, 1fr); }
.page *, .page { min-width: 0; }
body {
  margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.55 var(--sans);
  padding-inline: 16px; padding-block: 24px 48px; overflow-wrap: anywhere;
}
.page { max-width: 58rem; margin-inline: auto; display: grid; gap: 28px; }
h1, h2, h3, h4, h5 { text-wrap: balance; line-height: 1.25; margin: 0; }
h1 { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.01em; }
h2 { font-size: 1.2rem; font-weight: 600; }
h3 { font-size: 1.05rem; font-weight: 600; }
h4, h5 { font-size: 0.95rem; font-weight: 600; }
p, ul, ol, blockquote { margin: 0; }
.prose { display: grid; gap: 10px; max-width: 68ch; }
.prose ul, .prose ol { padding-left: 1.3em; display: grid; gap: 4px; }
.serif, .statement { font-family: var(--serif); font-size: 1.02rem; }
a { color: var(--accent); }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
code, .mono { font-family: var(--mono); font-size: 0.86em; }
.scroll { overflow-x: auto; max-width: 100%; }
pre { margin: 0; padding: 10px 12px; background: var(--surface-2); border-radius: 6px;
      font: 0.82rem/1.5 var(--mono); }
table { border-collapse: collapse; font-size: 0.9rem; }
th, td { border: 1px solid var(--line); padding: 4px 8px; text-align: left; vertical-align: top; }
blockquote { border-left: 3px solid var(--line); padding-left: 12px; color: var(--muted); }
.eyebrow { font: 500 0.72rem/1.2 var(--mono); letter-spacing: 0.08em; text-transform: uppercase;
           color: var(--muted); }
.muted { color: var(--muted); }
.masthead { display: grid; gap: 8px; }
.counts { display: flex; flex-wrap: wrap; gap: 8px 20px; font-variant-numeric: tabular-nums;
          color: var(--muted); }
.counts strong { color: var(--ink); font-size: 1.1rem; }
.badge { display: inline-block; font: 500 0.72rem/1.3 var(--mono); padding: 1px 7px;
         border-radius: 999px; border: 1px solid currentColor; white-space: nowrap;
         background: color-mix(in srgb, currentColor 9%, transparent); vertical-align: 0.1em; }
.st-proved { color: var(--st-proved); } .st-modulo { color: var(--st-modulo); border-style: dashed; }
.st-sketch { color: var(--st-sketch); } .st-conj { color: var(--st-conj); }
.st-supported { color: var(--st-supported); } .st-open { color: var(--st-open); }
.st-refuted { color: var(--st-refuted); } .st-cited { color: var(--st-cited); }
.st-unknown { color: var(--st-unknown); border-style: dotted; } .st-other { color: var(--st-other); }
.pill { display: inline-block; font: 500 0.72rem/1.3 var(--mono); padding: 1px 7px;
        border-radius: 4px; background: var(--surface-2); color: var(--muted); }
.pill.warn { background: var(--warn-weak); color: var(--warn); }
.pill.accent { background: var(--accent-weak); color: var(--accent); }
.chip { display: inline-flex; gap: 5px; align-items: baseline; flex-wrap: wrap; }
.ref { font-family: var(--mono); font-size: 0.86em; }
.legend { background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
          padding: 12px 14px; }
.legend summary { cursor: pointer; font-weight: 600; }
.legend dl { display: grid; grid-template-columns: max-content 1fr; gap: 6px 12px;
             margin: 10px 0 0; font-size: 0.88rem; }
.legend dd { margin: 0; color: var(--muted); }
.group { display: grid; gap: 14px; }
.group-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
              border-bottom: 1px solid var(--line); padding-bottom: 6px; }
.packet { background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
          padding: 16px; display: grid; gap: 12px; scroll-margin-top: 16px; }
.packet:target { border-color: var(--accent); }
.packet-top { display: flex; flex-wrap: wrap; gap: 6px 8px; align-items: center; }
.packet-top .id { font: 600 0.85rem var(--mono); margin-right: 4px; }
.meta { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 0.84rem; color: var(--muted); }
.meta b { font-weight: 500; color: var(--ink); }
.transition { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; font-size: 0.85rem; }
.decisions { display: grid; gap: 10px; }
.decision { border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px;
            display: grid; gap: 6px; background: var(--bg); }
.decision.pending { border-left: 3px solid var(--warn); }
.decision ol { list-style: none; padding: 0; margin: 0; display: grid; gap: 3px; }
.decision li.rec { font-weight: 500; }
.decision .letter { font-family: var(--mono); color: var(--muted); margin-right: 6px; }
.decision .reco { font-size: 0.88rem; color: var(--muted); }
.answer { font-size: 0.88rem; }
details.more > summary { cursor: pointer; font-size: 0.88rem; color: var(--muted); }
details.more[open] > summary { margin-bottom: 8px; }
.problems { background: var(--warn-weak); color: var(--warn); border-radius: 6px;
            padding: 8px 10px; font-size: 0.85rem; }
.source { font: 0.75rem var(--mono); color: var(--muted); }
.empty { color: var(--muted); font-style: italic; }
.stmts { display: grid; gap: 10px; }
.stmt { background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
        padding: 12px 14px; display: grid; gap: 6px; }
.stmt-head { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: baseline; }
.stmt-head .id { font: 500 0.82rem var(--mono); }
.stmt[data-depth="2"] { margin-left: 16px; } .stmt[data-depth="3"] { margin-left: 32px; }
.stmt[data-depth="4"], .stmt[data-depth="5"], .stmt[data-depth="6"] { margin-left: 48px; }
.subject { background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
           padding: 18px; display: grid; gap: 10px; }
.subject > .stmt { border: 0; padding: 0; background: none; }
.dd-section { display: grid; gap: 12px; }
.card { border-left: 3px solid var(--accent); padding: 6px 12px; display: grid; gap: 6px;
        background: var(--surface); border-radius: 0 6px 6px 0; }
.card pre { white-space: pre-wrap; }
@media (max-width: 480px) {
  body { font-size: 14px; }
  h1 { font-size: 1.4rem; }
  .packet, .stmt, .subject { padding: 12px; }
  .stmt[data-depth] { margin-left: 0; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""


def katex_block(macros=None):
    opts = {
        "delimiters": [{"left": "$$", "right": "$$", "display": True},
                       {"left": "$", "right": "$", "display": False},
                       {"left": "\\(", "right": "\\)", "display": False},
                       {"left": "\\[", "right": "\\]", "display": True}],
        "output": "mathml", "throwOnError": False, "ignoredClasses": ["nomath"],
        "macros": dict(macros or {}),
    }
    return (
        '<script defer src="%s/katex.min.js"></script>\n'
        '<script defer src="%s/contrib/auto-render.min.js"></script>\n'
        '<script>(function () {\n'
        '  var done = false;\n'
        '  function typeset() {\n'
        '    if (done || !window.renderMathInElement) return;\n'
        '    done = true;\n'
        '    try { renderMathInElement(document.body, %s); }\n'
        '    catch (e) { window.__katexError = String(e); }\n'
        '  }\n'
        '  document.addEventListener("DOMContentLoaded", typeset);\n'
        '  window.addEventListener("load", typeset);\n'
        '})();</script>' % (KATEX_BASE, KATEX_BASE, json.dumps(opts))
    )


#: KaTeX refuses to typeset in quirks mode, so the local file needs a doctype. When the
#: page is published as an artifact the skeleton supplies its own; this stray doctype
#: and these metas then land in <body>, where the HTML parser ignores them.
PREAMBLE = ('<!doctype html>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, '
            'viewport-fit=cover">\n')


def head(title, macros=None):
    return "%s<title>%s</title>\n%s\n<style>%s</style>\n%s\n" % (
        PREAMBLE, html.escape(title), FONTS, CSS, katex_block(macros))


def legend_html(open_=False):
    rows = "".join("<dt>%s</dt><dd>%s</dd>" % (badge(s), html.escape(m))
                   for s, _c, m in STATUS_LEGEND)
    rows += "<dt>%s</dt><dd>%s</dd>" % (badge("cited"), "A published result, quoted from "
                                        "its source")
    rows += "<dt>%s</dt><dd>%s</dd>" % (badge(None), "The record carries no status; treat "
                                        "it as unsettled")
    return ('<details class="legend"%s><summary>Status legend</summary><dl>%s</dl>'
            '</details>' % (" open" if open_ else "", rows))


# ----------------------------------------------------------------------------
# The dashboard
# ----------------------------------------------------------------------------

def _sections(body):
    out, cur, order = {}, None, []
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("## "):
            cur = ln[3:].strip()
            out.setdefault(cur, [])
            order.append(cur)
        elif cur is not None:
            out[cur].append(ln)
    return order, {k: "\n".join(v).strip() for k, v in out.items()}


STANDARD = ("Summary", "Produced", "Established vs assumed", "Evidence",
            "Decisions needed", "Machine notes", "Decision")


def _decisions_html(body, ctx):
    asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
    if not asked:
        if 0 in answers:
            return '<p class="answer">Acknowledged %s.</p>' % html.escape(answers[0][1])
        return ('<div class="decision pending"><p>Informational; nothing to decide. '
                'Acknowledge with <code>D0: ack</code>.</p></div>')
    parts = []
    for k in sorted(asked):
        d = asked[k]
        rec = (d["recommendation"] or "")
        rec_letter = re.match(r"^\(([a-d])\)", rec)
        rec_letter = rec_letter.group(1) if rec_letter else None
        opts = "".join('<li class="%s"><span class="letter">(%s)</span>%s</li>' % (
            "rec" if L == rec_letter else "", L, inline(t, ctx))
            for L, t in sorted(d["options"].items()))
        ans = answers.get(k)
        if ans:
            choice, date, who, note = ans
            text = choice
            m = re.match(r"^\(([a-d])\)$", choice)
            if m and m.group(1) in d["options"]:
                text = "%s %s" % (choice, d["options"][m.group(1)])
            ans_html = '<p class="answer"><span class="pill accent">answered %s</span> %s%s</p>' % (
                html.escape(date), inline(text, ctx),
                (" &middot; " + inline(note, ctx)) if note else "")
        else:
            ans_html = '<p class="answer"><span class="pill warn">awaiting your answer</span></p>'
        parts.append(
            '<div class="decision%s"><h4>D%d. %s</h4><ol>%s</ol>'
            '<p class="reco">Recommendation: %s</p>%s</div>' % (
                "" if ans else " pending", k, inline(d["question"], ctx), opts,
                inline(rec, ctx), ans_html))
    return '<div class="decisions">%s</div>' % "".join(parts)


def packet_html(path, meta, body, ctx, board=None):
    order, secs = _sections(body)
    pid = str(meta.get("packet", "P-????"))
    asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
    pending = [k for k in asked if k not in answers]
    top = ['<span class="id">%s</span>' % html.escape(pid),
           '<span class="pill">%s</span>' % html.escape(str(meta.get("kind", "other"))),
           '<span class="pill%s">%s</span>' % (" accent" if meta.get("state") == "open" else "",
                                               html.escape(str(meta.get("state", "?"))))]
    if pending:
        top.append('<span class="pill warn">%d decision%s pending</span>' % (
            len(pending), "" if len(pending) == 1 else "s"))
    metas = []
    for key, label in (("by", "by"), ("ticket", "ticket"), ("agenda", "agenda"),
                       ("created", "created")):
        if meta.get(key):
            metas.append("<span>%s <b>%s</b></span>" % (label, inline(str(meta[key]), ctx)))
    subj = meta.get("subject") or []
    if subj:
        metas.append("<span>subject %s</span>" % " ".join(
            '<code class="nomath">%s</code>' % html.escape(str(s)) for s in subj))
    trans = ""
    if meta.get("status_before") or meta.get("status_proposed"):
        trans = ('<div class="transition"><span class="muted">status</span> %s '
                 '<span aria-hidden="true">&rarr;</span><span class="muted">proposed</span> %s'
                 '</div>' % (badge(meta.get("status_before")), badge(meta.get("status_proposed"))))
    probs = ac.validate_packet(meta, body)
    parts = [
        '<article class="packet" id="%s">' % html.escape(pid, quote=True),
        '<div class="packet-top">%s</div>' % "".join(top),
        "<h3>%s</h3>" % inline(str(meta.get("title", "")), ctx),
        '<div class="meta">%s</div>' % "".join(metas), trans,
    ]
    if secs.get("Summary"):
        parts.append('<div class="prose">%s</div>' % markdown(secs["Summary"], ctx, 4))
    if secs.get("Established vs assumed"):
        parts.append('<div class="prose"><h4>Established vs assumed</h4>%s</div>'
                     % markdown(secs["Established vs assumed"], ctx, 5))
    parts.append(_decisions_html(body, ctx))
    for name in ["Produced", "Evidence"] + [s for s in order if s not in STANDARD] + \
            ["Machine notes"]:
        if secs.get(name):
            parts.append('<details class="more"><summary>%s</summary><div class="prose">%s'
                         '</div></details>' % (html.escape(name),
                                               markdown(secs[name], ctx, 5)))
    if probs:
        parts.append('<div class="problems">Packet format: %s</div>'
                     % html.escape("; ".join(probs)))
    rel = path
    if board:
        try:
            rel = os.path.relpath(path, board).replace("\\", "/")
        except ValueError:
            pass
    parts.append('<div class="source">board/%s</div>' % html.escape(rel))
    parts.append("</article>")
    return "\n".join(p for p in parts if p)


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def collect_packets(board, include_decided=False):
    """[(path, meta, body)] of the packets to show, open ones only by default."""
    root = os.path.join(board, "packets")
    out = []
    if not os.path.isdir(root):
        return out
    rx = re.compile(r"^P-\d{4,}(?:-.*)?\.md$")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for f in sorted(filenames):
            if not rx.match(f):
                continue
            p = os.path.join(dirpath, f)
            try:
                meta, body = ac.read_frontmatter(_read(p))
            except (ac.FrontmatterError, OSError, UnicodeDecodeError) as e:
                meta, body = {"packet": f[:6], "title": f, "state": "open",
                              "instance": os.path.basename(dirpath)}, \
                    "## Summary\n\nUnreadable packet: %s\n" % e
            if meta.get("state", "open") != "open" and not include_decided:
                continue
            out.append((p, meta, body))
    return out


def registry_statuses(workspace):
    """({id: status}, {id: title}) over the workspace's registries, for [[id]] chips.

    Read-only; returns empty maps when there is no workspace or a registry is absent.
    """
    if not workspace:
        return {}, {}
    try:
        import gather_deep_dive as gd
        index = gd.load_index(workspace)
    except Exception:           # a broken record must not stop the dashboard
        return {}, {}
    st, ti = {}, {}
    for rid, rec in index.items():
        if rid.startswith("alias:"):
            continue
        st[rid] = rec["meta"].get("status")
        ti[rid] = str(rec["meta"].get("title") or "")
    return st, ti


def _instance_order(workspace):
    return list((workspace or {}).get("instances", {}).keys())


def render_dashboard(board, workspace=None, include_decided=False, date=None):
    """The whole dashboard as one HTML string."""
    items = collect_packets(board, include_decided)
    statuses, titles = registry_statuses(workspace)
    ctx = Ctx(statuses, anchors=[str(m.get("packet")) for _p, m, _b in items], titles=titles)
    groups = {}
    for p, m, b in items:
        inst = str(m.get("instance") or os.path.basename(os.path.dirname(p)))
        groups.setdefault(inst, []).append((p, m, b))
    order = [i for i in _instance_order(workspace) if i in groups] + \
        sorted(i for i in groups if i not in _instance_order(workspace))
    n_pending = sum(len([k for k in ac.packet_decisions(b) if k not in ac.packet_answers(b)])
                    for _p, _m, b in items)
    counts = ['<span><strong>%d</strong> open packet%s</span>' % (
        len(items), "" if len(items) == 1 else "s"),
        '<span><strong>%d</strong> decision%s awaiting you</span>' % (
            n_pending, "" if n_pending == 1 else "s")]
    counts += ['<span>%s <strong>%d</strong></span>' % (html.escape(i), len(groups[i]))
               for i in order]
    body = ['<main class="page">',
            '<header class="masthead"><div class="eyebrow">Academy board &middot; %s</div>'
            '<h1>Review desk</h1><div class="counts">%s</div></header>' % (
                html.escape(date or ac.today()), "".join(counts)),
            legend_html()]
    if not items:
        body.append('<p class="empty">No open packets. Nothing needs a decision.</p>')
    for inst in order:
        body.append('<section class="group" id="%s"><div class="group-head"><h2>%s</h2>'
                    '<span class="muted">%d packet%s</span></div>' % (
                        html.escape(inst, quote=True), html.escape(inst), len(groups[inst]),
                        "" if len(groups[inst]) == 1 else "s"))
        for p, m, b in groups[inst]:
            body.append(packet_html(p, m, b, ctx, board))
        body.append("</section>")
    body.append('<footer class="source">Generated by academy/scripts/render_packets.py from '
                '%s. Answer in /academy:review or under ## Decision in the packet file.'
                '</footer></main>' % html.escape(board.replace("\\", "/")))
    return head("Academy Review Desk") + "\n".join(body) + "\n"


# ----------------------------------------------------------------------------
# Deep dives
# ----------------------------------------------------------------------------

ROLE_HEADINGS = {
    "dependency": "What it rests on",
    "modulo": "Open inputs (modulo)",
    "rests_on": "What rests on it",
    "bears_on": "Claims this bears on",
    "evidence_for": "Evidence from computation",
    "member": "Questions and claims in this direction",
    "example": "Examples",
    "related": "Related statements",
    "cites": "Our statements citing it",
    "bears_on_subject": "Statements that bear on it",
    "definition": "Definitions",
}


def statement_html(s, ctx):
    sid = str(s.get("id", ""))
    head_ = ['<span class="id">%s</span>' % html.escape(sid), badge(s.get("status"))]
    if s.get("kind"):
        head_.append('<span class="pill">%s</span>' % html.escape(str(s["kind"])))
    if s.get("title") and s.get("title") != sid:
        head_.append('<span>%s</span>' % inline(str(s["title"]), ctx))
    parts = ['<div class="stmt" data-depth="%d" id="%s">' % (
        int(s.get("depth") or 1), html.escape("s-" + re.sub(r"[^A-Za-z0-9_-]", "-", sid),
                                              quote=True)),
        '<div class="stmt-head">%s</div>' % "".join(head_)]
    if s.get("statement"):
        parts.append('<div class="statement prose">%s</div>' % markdown(s["statement"], ctx, 5))
    if s.get("modulo"):
        parts.append('<div class="meta">modulo %s</div>' % " ".join(
            chip(m, ctx) for m in s["modulo"]))
    if s.get("where"):
        parts.append('<div class="source">%s</div>' % html.escape(str(s["where"])))
    parts.append("</div>")
    return "".join(parts)


def _section(heading, inner, cls="dd-section"):
    if not inner:
        return ""
    return '<section class="%s"><h2>%s</h2>%s</section>' % (cls, html.escape(heading), inner)


def _text_block(items, ctx, kind):
    out = []
    for it in items or []:
        label = it.get("packet") or it.get("key") or it.get("path") or ""
        extra = ""
        if kind == "card":
            extra = badge("cited")
            if it.get("pinpoint"):
                label = "%s#%s" % (label, it["pinpoint"])
        elif kind == "report":
            extra = badge(it.get("status_proposed")) if "status_proposed" in it else ""
            if it.get("title"):
                label = "%s %s" % (label, it["title"])
        text = str(it.get("text") or "")
        if kind in ("result",) or it.get("raw"):
            content = '<div class="scroll"><pre><code class="nomath">%s</code></pre></div>' % \
                html.escape(text)
        else:
            content = '<div class="prose">%s</div>' % markdown(text, ctx, 4)
        src = it.get("path") if it.get("path") and it.get("path") != label else ""
        out.append('<div class="card"><div class="stmt-head"><span class="id">%s</span>%s</div>'
                   '%s%s</div>' % (html.escape(str(label)), extra, content,
                                   ('<div class="source">%s</div>' % html.escape(src))
                                   if src else ""))
    return "".join(out)


def deep_dive_blocks(bundle):
    """The placeholder values for a deep-dive template."""
    stmts = list(bundle.get("statements") or [])
    obj = dict(bundle.get("object") or {})
    subject = str(bundle.get("subject") or obj.get("id") or "")
    if obj and not any(s.get("id") == obj.get("id") for s in stmts):
        stmts.insert(0, dict(obj, role="subject"))
    statuses = {str(s.get("id")): s.get("status") for s in stmts if s.get("id")}
    titles = {str(s.get("id")): str(s.get("title") or "") for s in stmts if s.get("id")}
    ctx = Ctx(statuses, titles=titles)
    title = str(bundle.get("title") or obj.get("title") or subject)
    kind = str(bundle.get("kind") or "claim")
    blocks = {
        "title": html.escape(title),
        "title_inline": inline(title, ctx),
        "subject_id": html.escape(subject),
        "kind": html.escape(kind),
        "generated": html.escape(str(bundle.get("generated") or ac.today())),
        "head": head(title, bundle.get("macros")),
        "legend": legend_html(),
    }
    subj = next((s for s in stmts if s.get("role") == "subject"), obj or None)
    blocks["subject_status"] = badge((subj or {}).get("status")) if subj is not None else \
        badge("cited") if kind == "paper" else badge(None)
    blocks["subject"] = ('<div class="subject">%s</div>' % statement_html(subj, ctx)) \
        if subj else ""
    blocks["sections"] = "".join(
        '<section class="dd-section"><h2>%s</h2><div class="prose serif">%s</div></section>'
        % (inline(str(s.get("heading", "")), ctx), markdown(s.get("markdown", ""), ctx, 3))
        for s in bundle.get("sections") or [])
    by_role = {}
    for s in stmts:
        if s.get("role") == "subject":
            continue
        by_role.setdefault(s.get("role") or "related", []).append(s)
    for role, items in by_role.items():
        blocks["statements:" + role] = '<div class="stmts">%s</div>' % "".join(
            statement_html(s, ctx) for s in items)
    blocks["cards"] = _text_block(bundle.get("cards"), ctx, "card")
    blocks["reviews"] = _text_block(bundle.get("reviews"), ctx, "review")
    blocks["reports"] = _text_block(bundle.get("reports"), ctx, "report")
    blocks["results"] = _text_block(bundle.get("results"), ctx, "result")
    notes = bundle.get("notes") or []
    blocks["notes"] = ('<div class="prose"><ul>%s</ul></div>' % "".join(
        "<li>%s</li>" % inline(str(n), ctx) for n in notes)) if notes else ""
    blocks["_roles"] = sorted(by_role)
    return blocks


RE_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)(?::([a-z_]+))?(?:\|([^}]*))?\s*\}\}")


def fill_template(template, blocks):
    """Substitute ``{{name}}``, ``{{name|Heading}}`` and ``{{statements:role|Heading}}``.

    With a heading, a non-empty value is wrapped in a titled <section> and an empty
    one disappears. ``{{statements:rest|Heading}}`` collects every role the template
    did not name explicitly.
    """
    named = set(m.group(2) for m in RE_PLACEHOLDER.finditer(template)
                if m.group(1) == "statements" and m.group(2) and m.group(2) != "rest")

    def sub(m):
        name, arg, heading = m.group(1), m.group(2), m.group(3)
        if name == "statements":
            if arg == "rest":
                parts = []
                for role in blocks.get("_roles", []):
                    if role not in named:
                        parts.append(_section(ROLE_HEADINGS.get(role, role.replace("_", " ")
                                                                .capitalize()),
                                              blocks.get("statements:" + role, "")))
                return "".join(parts)
            val = blocks.get("statements:%s" % arg, "")
            heading = heading or ROLE_HEADINGS.get(arg, arg)
        else:
            val = blocks.get(name, "")
        if heading is not None and heading != "":
            return _section(heading, val)
        return val

    return RE_PLACEHOLDER.sub(sub, template)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            for s in _strings(v):
                yield s
    elif isinstance(value, (list, tuple)):
        for v in value:
            for s in _strings(v):
                yield s


def check_deep_dive(bundle, kind=None):
    """Problems that forbid publishing a deep-dive: [] when every status is shown.

    Every statement (and the subject, unless the subject is a paper, which is shown
    as cited) must carry a status, and every ``[[ns:id]]`` chip anywhere in the
    prose, statements, notes, cards, reviews and reports, and every ``modulo`` id,
    must name an id the bundle gives a status. Raw results are not scanned.
    """
    kind = kind or bundle.get("kind") or "claim"
    stmts = list(bundle.get("statements") or [])
    obj = dict(bundle.get("object") or {})
    probs = []
    statuses = {}
    for s in stmts + ([obj] if obj else []):
        sid = str(s.get("id") or "")
        st = s.get("status")
        if sid and st:
            statuses[sid] = st
    for s in stmts:
        if not s.get("status"):
            probs.append("statement %s has no status" % (s.get("id") or "(no id)"))
    if obj and not obj.get("status") and kind != "paper" \
            and str(obj.get("id")) not in statuses:
        probs.append("the subject %s has no status" % (obj.get("id") or "(no id)"))
    scanned = [bundle.get("sections"), bundle.get("notes"), bundle.get("cards"),
               bundle.get("reviews"), bundle.get("reports"),
               [{k: v for k, v in s.items() if k in ("title", "statement")}
                for s in stmts + ([obj] if obj else [])]]
    refs = set()
    for text in _strings(scanned):
        refs.update(RE_CHIP.findall(text))
    for s in stmts + ([obj] if obj else []):
        refs.update(str(m) for m in s.get("modulo") or [])
    for ref in sorted(refs):
        if not statuses.get(ref):
            probs.append("[[%s]] is shown without a status (add it to the bundle's "
                         "statements with its registry status)" % ref)
    return probs


def render_deep_dive(bundle, kind=None, template_dir=TEMPLATE_DIR):
    kind = kind or bundle.get("kind") or "claim"
    if kind not in DEEP_DIVE_KINDS:
        raise ac.AcademyError("deep-dive kind must be one of %s" % ", ".join(DEEP_DIVE_KINDS))
    tpath = os.path.join(template_dir, "%s.html" % kind)
    template = _read(tpath)
    return fill_template(template, deep_dive_blocks(dict(bundle, kind=kind)))


def deep_dive_slug(subject):
    return ac.slugify(str(subject).replace(":", "-"), maxlen=80, default="deep-dive")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="render_packets.py", description=__doc__.split("\n")[0])
    ap.add_argument("--board"); ap.add_argument("--workspace")
    ap.add_argument("--out"); ap.add_argument("--all", action="store_true",
                                              help="include decided packets")
    ap.add_argument("--deep-dive", metavar="BUNDLE", help="render a deep-dive bundle JSON")
    ap.add_argument("--kind", choices=DEEP_DIVE_KINDS)
    ap.add_argument("--templates", default=TEMPLATE_DIR)
    a = ap.parse_args(argv)
    try:
        ws = None
        try:
            ws = ac.load_workspace(a.workspace)
        except ac.ConfigError:
            pass
        board = os.path.abspath(a.board) if a.board else (ws or {}).get("board")
        if a.deep_dive:
            with open(a.deep_dive, "r", encoding="utf-8") as fh:
                bundle = json.load(fh)
            problems = check_deep_dive(bundle, a.kind)
            if problems:
                sys.stderr.write("render_packets: refused, the deep-dive would show "
                                 "statements without a status:\n- %s\n"
                                 % "\n- ".join(problems))
                return 2
            page = render_deep_dive(bundle, a.kind, a.templates)
            out = a.out
            if not out:
                if not board:
                    raise ac.AcademyError("no --out and no board to write deep-dives/ into")
                out = os.path.join(board, "deep-dives",
                                   deep_dive_slug(bundle.get("subject", "")) + ".html")
        else:
            if not board:
                raise ac.AcademyError("no board: pass --board or provide workspace.json")
            page = render_dashboard(board, ws, a.all)
            out = a.out or os.path.join(board, ".render", "review.html")
        ac.atomic_write(out, page)
        print(os.path.abspath(out))
    except (ac.AcademyError, OSError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
