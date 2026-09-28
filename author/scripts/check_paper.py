#!/usr/bin/env python3
"""check_paper.py -- colour-propagation check and statement registry.

The Author plugin's copy (plan section 3.6), run as

    py ${CLAUDE_PLUGIN_ROOT}/scripts/check_paper.py [--root HOME] [--strict]
        [--registry Drafts/statements.md] [--no-registry] [--no-log] [--config FILE]

Configuration
-------------
Everything paper-specific is read from the home's ``.claude/academy.json``
(``author`` block, docs/config.md section 3), found from ``--root`` upwards, or
from ``--config``: ``theorems.all/provable/commentary`` replace ``THEOREM_ENVS``,
``PROVABLE_ENVS`` and ``COMMENTARY_ENVS``; ``envs`` (env -> status) replaces
``COLOUR_ENVS``; ``colourCommands`` (macro -> status) replaces
``COLOUR_COMMANDS``; ``noteMacros.machine`` gives the machine-note macros;
``main``, ``build.dir`` and ``checker.statements`` give the root file, the build
directory and the default registry path. A missing file or key keeps the value
below, which is BilliardIllumination's, so the output is unchanged there.

What it does
------------
1. Reads ``main.tex``, follows the ``\\input{sections/...}`` lines in order, and
   parses every theorem-like environment it finds in those files.
2. Assigns each statement a draft colour --- ``sketch`` (blue), ``conjectural``
   (red), ``meta`` (brown) or ``established`` (uncoloured) --- from the innermost
   enclosing ``\\begin{sketch}`` / ``\\begin{conjectural}`` / ``\\begin{meta}``
   environment, and records inline ``\\Sketch{`` / ``\\Conjectural{`` / ``\\Meta{``
   spans as "partly" markers.
3. Attaches the first following ``proof`` environment, collects cross-references
   and citations, and applies the rules R1--R6 documented in ``CLAUDE.md``.
4. Writes the generated registry ``Drafts/statements.md`` (LF endings).
5. Summarises the last build from ``.build/main.log`` / ``.build/main.blg`` and,
   if ``pdftotext`` is on PATH, counts ``??`` in ``.build/main.pdf``.
6. **R7** (warning): scans the built PDF for a clipped fragment -- text whose box
   falls outside the page, the geometric signature of a margin note the column
   could not hold. Needs a build no older than the newest ``.tex`` under
   ``sections/``, ``tikz/`` or ``main.tex``, and ``pdftohtml`` plus ``synctex`` on
   PATH to resolve a ``file:line``; missing either, or any parse failure, is a
   single skip note rather than an error, and the scan never fails the build by
   itself.

The script never writes to any ``.tex`` file.  Section files are read with
``newline=""`` so their CRLF endings are never touched.

Exit codes: 0 clean, 1 violations (with ``--strict``, also warnings), 2 parse or
I/O error.
"""

from __future__ import annotations

import argparse
import bisect
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

# --------------------------------------------------------------------------
# Vocabulary of the preamble: defaults, overridden by academy.json (configure)
# --------------------------------------------------------------------------

#: every theorem-like environment declared by the preamble
DEFAULT_THEOREM_ENVS = (
    "thm", "prop", "lem", "fact", "cor", "conj",          # plain style
    "defn", "exc", "rmk", "ex", "exer", "quest",          # definition style
    "claim", "case",                                      # own counters
    "claim*", "problem",                                  # unnumbered
)

#: environments that R2 expects to carry a proof or a citation
DEFAULT_PROVABLE_ENVS = ("thm", "prop", "lem", "cor", "claim", "claim*")

#: environments whose cross-references are commentary, not logical dependence
DEFAULT_COMMENTARY_ENVS = ("rmk", "quest")

#: the draft-status environments of the preamble, and the colour each records
DEFAULT_COLOUR_ENVS = {"sketch": "sketch", "conjectural": "conjectural", "meta": "meta"}

#: inline command forms of the same three
DEFAULT_COLOUR_COMMANDS = {
    "\\Sketch": "sketch",
    "\\Conjectural": "conjectural",
    "\\Meta": "meta",
}

#: machine margin-note macros (R0 bookkeeping: ``claude_note`` in the registry)
DEFAULT_MACHINE_MACROS = ("\\Claude", "\\cl")

DEFAULT_MAIN = "main.tex"
DEFAULT_BUILD_DIR = ".build"
DEFAULT_BUILD_CMD = ("latexmk", "-pdf", "main.tex")
DEFAULT_REGISTRY = "Drafts/statements.md"

ESTABLISHED = "established"

# The live values, set by configure(); the parser reads these module globals.
THEOREM_ENVS: Set[str] = set()
PROVABLE_ENVS: Set[str] = set()
COMMENTARY_ENVS: Set[str] = set()
COLOUR_ENVS: Dict[str, str] = {}
COLOUR_COMMANDS: Dict[str, str] = {}
RE_CLAUDE = re.compile(r"(?!)")
MAIN_TEX = DEFAULT_MAIN
BUILD_DIR = DEFAULT_BUILD_DIR
BUILD_CMD: Tuple[str, ...] = DEFAULT_BUILD_CMD
REGISTRY_DEFAULT = DEFAULT_REGISTRY


def _macro_command(name: str) -> str:
    """``\\Sketch`` or ``Sketch`` -> the inline form ``\\Sketch{``."""
    name = name.strip()
    if name.endswith("{"):
        name = name[:-1]
    return "\\" + name.lstrip("\\") + "{"


def configure(author: Optional[dict] = None) -> None:
    """Set the vocabulary from an ``academy.json`` ``author`` block (None = defaults).

    Keys (docs/config.md section 3): ``theorems.all``, ``theorems.provable``,
    ``theorems.commentary``, ``envs`` (env -> status), ``colourCommands``
    (macro -> status), ``noteMacros.machine``, ``main``, ``build.dir``,
    ``build.cmd``, ``checker.statements``. A missing key keeps its default.
    """
    global THEOREM_ENVS, PROVABLE_ENVS, COMMENTARY_ENVS, COLOUR_ENVS
    global COLOUR_COMMANDS, RE_CLAUDE, MAIN_TEX, BUILD_DIR, BUILD_CMD
    global REGISTRY_DEFAULT
    a = author if isinstance(author, dict) else {}
    th = a.get("theorems") if isinstance(a.get("theorems"), dict) else {}
    THEOREM_ENVS = set(th.get("all") or DEFAULT_THEOREM_ENVS)
    PROVABLE_ENVS = set(th.get("provable") or DEFAULT_PROVABLE_ENVS)
    COMMENTARY_ENVS = set(th.get("commentary") or DEFAULT_COMMENTARY_ENVS)
    envs = a.get("envs") if isinstance(a.get("envs"), dict) else DEFAULT_COLOUR_ENVS
    COLOUR_ENVS = {str(k): str(v) for k, v in envs.items()}
    cmds = a.get("colourCommands")
    if not isinstance(cmds, dict):
        cmds = DEFAULT_COLOUR_COMMANDS
    COLOUR_COMMANDS = {_macro_command(k): v for k, v in cmds.items()}
    notes = a.get("noteMacros") if isinstance(a.get("noteMacros"), dict) else {}
    machine = [m.strip().lstrip("\\") for m in (notes.get("machine")
                                                or DEFAULT_MACHINE_MACROS) if m.strip()]
    RE_CLAUDE = re.compile(r"\\(%s)\s*\{" % "|".join(re.escape(m) for m in machine))
    MAIN_TEX = str(a.get("main") or DEFAULT_MAIN).replace("\\", "/")
    build = a.get("build") if isinstance(a.get("build"), dict) else {}
    BUILD_DIR = str(build.get("dir") or DEFAULT_BUILD_DIR).replace("\\", "/").rstrip("/")
    BUILD_CMD = tuple(build.get("cmd") or DEFAULT_BUILD_CMD)
    checker = a.get("checker") if isinstance(a.get("checker"), dict) else {}
    REGISTRY_DEFAULT = str(checker.get("statements") or DEFAULT_REGISTRY)


def _main_stem() -> str:
    return os.path.splitext(os.path.basename(MAIN_TEX))[0]


def _build_rel(ext: str) -> str:
    """``.build/main.<ext>``: the build artifact's path relative to the root."""
    return "%s/%s.%s" % (BUILD_DIR, _main_stem(), ext)


def _build_path(root: str, ext: str) -> str:
    return os.path.join(root, *_build_rel(ext).split("/"))


def find_config(root: str) -> Optional[str]:
    """The nearest ``.claude/academy.json`` at or above ``root``, or None."""
    cur = os.path.abspath(root)
    user_home = os.path.normcase(os.path.abspath(os.path.expanduser("~")))
    while True:
        cand = os.path.join(cur, ".claude", "academy.json")
        if os.path.normcase(cur) != user_home and os.path.isfile(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def load_author_block(path: Optional[str]) -> Tuple[Optional[dict], str]:
    """(the ``author`` block of ``path``, a note) -- (None, note) when unusable.

    The checker reads only its own block and never fails on the rest of the
    config: validation is session_start's job.
    """
    import json
    if not path:
        return None, ""
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return None, "cannot read %s (%s); using the default vocabulary" % (path, exc)
    if not isinstance(data, dict):
        return None, "%s is not a JSON object; using the default vocabulary" % path
    if data.get("role") not in (None, "author"):
        return None, ""
    block = data.get("author")
    return (block if isinstance(block, dict) else None), ""


configure(None)

# --------------------------------------------------------------------------
# Low-level LaTeX text handling
# --------------------------------------------------------------------------

RE_ENV = re.compile(r"\\(begin|end)\s*\{([A-Za-z@]+\*?)\}")
RE_REF = re.compile(r"\\(cref|Cref|ref|eqref)\*?\s*\{([^}]*)\}")
RE_CITE = re.compile(r"\\cite\s*(\[[^\]]*\])?\s*(\[[^\]]*\])?\s*\{([^}]*)\}")
RE_LABEL = re.compile(r"\\label\s*\{([^}]*)\}")
RE_SECTION = re.compile(r"\\(sub)?section\*?\s*\{")
RE_INPUT = re.compile(r"\\input\s*\{([^}]*)\}")


class ParseError(Exception):
    """Raised for an unreadable or structurally impossible source file."""


def read_tex(path: str) -> str:
    """Read a .tex file without ever rewriting it.

    ``newline=""`` keeps the file's own CRLF endings out of Python's universal
    newline translation; we then normalise to ``\\n`` in memory only, so offsets
    and line numbers stay consistent with the file's line count.
    """
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1", newline="") as handle:
            raw = handle.read()
    except OSError as exc:  # pragma: no cover - surfaced as exit code 2
        raise ParseError("cannot read %s: %s" % (path, exc))
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def blank_comments(text: str) -> str:
    """Replace every ``%`` comment by spaces, preserving all offsets.

    An escaped ``\\%`` is not a comment.  Length and newline positions are
    preserved so that offsets computed on the result still point at the right
    line of the original file.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":           # skip the escaped character
            i += 2
            continue
        if ch == "%":
            j = text.find("\n", i)
            if j == -1:
                j = n
            for k in range(i, j):
                out[k] = " "
            i = j + 1
            continue
        i += 1
    return "".join(out)


RE_VERBATIM = re.compile(
    r"\\begin\{(verbatim|lstlisting|Verbatim)\*?\}(.*?)\\end\{\1\*?\}", re.DOTALL)
RE_VERB = re.compile(r"\\verb\*?(.)(.*?)\1")


def _blank_span(chars: List[str], start: int, end: int) -> None:
    """Replace ``chars[start:end]`` by spaces, keeping newlines in place."""
    for k in range(start, end):
        if chars[k] != "\n":
            chars[k] = " "


def blank_verbatim(text: str) -> str:
    """Neutralise ``verbatim`` bodies and ``\\verb|...|`` spans.

    The colour legend in ``sections/conventions.tex`` displays a sample
    ``\\begin{prop} \\label{prop:foo}`` inside a verbatim block; without this the
    sample would be parsed as a real statement.
    """
    chars = list(text)
    for m in RE_VERBATIM.finditer(text):
        _blank_span(chars, m.start(2), m.end(2))
    for m in RE_VERB.finditer(text):
        _blank_span(chars, m.start(), m.end())
    return "".join(chars)


class LineIndex:
    """Offset -> 1-based line number, for one file."""

    def __init__(self, text: str) -> None:
        self._starts = [0]
        for m in re.finditer("\n", text):
            self._starts.append(m.end())

    def line(self, offset: int) -> int:
        return bisect.bisect_right(self._starts, offset)


def read_braced(text: str, i: int) -> Tuple[str, int]:
    """Read a balanced ``{...}`` group starting at ``text[i] == '{'``.

    Returns the content and the offset just past the closing brace.
    """
    assert text[i] == "{"
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    raise ParseError("unbalanced brace group at offset %d" % i)


def read_optional(text: str, i: int) -> Tuple[Optional[str], int]:
    """Read an optional ``[...]`` argument at ``i`` (skipping spaces first)."""
    j = i
    while j < len(text) and text[j] in " \t":
        j += 1
    if j >= len(text) or text[j] != "[":
        return None, i
    depth, k = 0, j
    while k < len(text):
        c = text[k]
        if c == "\\":
            k += 2
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[j + 1:k].strip(), k + 1
        k += 1
    return None, i


def strip_tex(s: str) -> str:
    """Flatten a short TeX fragment (a title) to plain-ish text for a table."""
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace("|", "\\|")


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class Statement:
    label: str                       # "(unlabelled)" when absent
    env: str
    title: str
    colour: str                      # sketch / conjectural / meta / established
    partly: List[str]                # inline colour spans inside the statement
    section: str
    subsection: str
    file: str                        # repo-relative, forward slashes
    line: int
    body: str = ""
    has_proof: bool = False
    proof_line: int = 0
    proof_colour: str = ESTABLISHED
    proof_partly: List[str] = field(default_factory=list)
    proof_sketched: bool = False
    claude_note: bool = False
    uses: List[str] = field(default_factory=list)        # theorem labels
    also_refers: List[str] = field(default_factory=list)  # sec:/fig:/eq:/...
    cites: List[str] = field(default_factory=list)
    used_by: List[str] = field(default_factory=list)

    @property
    def where(self) -> str:
        return "%s:%d" % (self.file, self.line)

    @property
    def colour_display(self) -> str:
        if self.partly:
            return "%s (partly %s)" % (self.colour, "/".join(sorted(set(self.partly))))
        return self.colour


@dataclass
class RefUse:
    """One ``\\cref``-style reference anywhere in a section file."""
    label: str
    file: str
    line: int
    owner: str            # enclosing statement label, or "-"


@dataclass
class Finding:
    kind: str             # "R1" ... "R6", "W1" ... "W3", "BUILD"
    severity: str         # "V" (violation) or "W" (warning)
    file: str
    line: int
    label: str
    message: str

    def render(self) -> str:
        loc = "%s:%d" % (self.file, self.line) if self.file else "(build)"
        return "%s: %s: [%s] %s" % (loc, self.label, self.kind, self.message)


# --------------------------------------------------------------------------
# Parsing one file
# --------------------------------------------------------------------------


def _env_events(text: str) -> List[Tuple[str, str, int, int]]:
    """All ``\\begin``/``\\end`` occurrences as (kind, name, start, end)."""
    return [(m.group(1), m.group(2), m.start(), m.end()) for m in RE_ENV.finditer(text)]


def _heading_map(text: str) -> List[Tuple[int, str, str]]:
    """Offsets of ``\\section``/``\\subsection`` headings in one file."""
    out = []
    for m in RE_SECTION.finditer(text):
        level = "subsection" if m.group(1) else "section"
        try:
            title, _ = read_braced(text, m.end() - 1)
        except ParseError:
            continue
        out.append((m.start(), level, strip_tex(title)))
    return out


def _heading_at(headings: Sequence[Tuple[int, str, str]], offset: int,
                default_section: str) -> Tuple[str, str]:
    """The (section, subsection) in force at ``offset``."""
    section, subsection = default_section, ""
    for off, level, title in headings:
        if off > offset:
            break
        if level == "section":
            section, subsection = title, ""
        else:
            subsection = title
    return section, subsection


def _collect_refs(fragment: str) -> Tuple[List[str], List[str]]:
    """All labels referenced in a fragment, and all citation keys with pinpoints."""
    labels: List[str] = []
    for m in RE_REF.finditer(fragment):
        for part in m.group(2).split(","):
            part = part.strip()
            if part:
                labels.append(part)
    cites: List[str] = []
    for m in RE_CITE.finditer(fragment):
        pin = m.group(2) or m.group(1)
        pin = pin[1:-1].strip() if pin else ""
        for key in m.group(3).split(","):
            key = key.strip()
            if not key:
                continue
            cites.append("%s (%s)" % (key, strip_tex(pin)) if pin else key)
    return labels, cites


def _has_colour_command(fragment: str) -> List[str]:
    """Which inline ``\\Sketch{``/``\\Conjectural{``/``\\Meta{`` spans occur."""
    return [name for cmd, name in COLOUR_COMMANDS.items() if cmd in fragment]


def parse_file(path: str, relpath: str, default_section: str) -> Tuple[
        List[Statement], List[Tuple[str, int]], List[RefUse], List[Finding]]:
    """Parse one section file.

    Returns its statements, all ``\\label`` definitions as (label, line), all
    reference uses, and any structural anomalies found while walking.
    """
    raw = read_tex(path)
    text = blank_comments(blank_verbatim(raw))
    index = LineIndex(text)
    headings = _heading_map(text)
    events = _env_events(text)

    statements: List[Statement] = []
    anomalies: List[Finding] = []
    stack: List[Tuple[str, int]] = []      # (env name, begin offset)
    # open theorem environments, as (statement, content start offset, stack depth)
    open_thms: List[Tuple[Statement, int, int]] = []
    # (statement index, statement end offset) awaiting a proof
    pending_proof: Optional[int] = None
    pending_from: int = 0
    open_proof: Optional[Tuple[int, int, str, int]] = None  # idx, start, colour, line

    def colour_now() -> str:
        for name, _ in reversed(stack):
            if name in COLOUR_ENVS:
                return COLOUR_ENVS[name]
        return ESTABLISHED

    for kind, name, start, end in events:
        if kind == "begin":
            colour_before = colour_now()
            stack.append((name, start))
            if name in THEOREM_ENVS:
                title, after = read_optional(text, end)
                section, subsection = _heading_at(headings, start, default_section)
                stmt = Statement(
                    label="(unlabelled)", env=name, title=strip_tex(title or ""),
                    colour=colour_before, partly=[], section=section,
                    subsection=subsection, file=relpath, line=index.line(start),
                )
                open_thms.append((stmt, after, len(stack)))
                pending_proof = None          # a new statement closes the window
            elif name == "proof" and pending_proof is not None:
                open_proof = (pending_proof, end, colour_before, index.line(start))
                pending_proof = None
        else:  # \end{...}
            # unwind to the matching \begin, tolerating sloppy nesting
            match_at = None
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][0] == name:
                    match_at = k
                    break
            if match_at is None:
                anomalies.append(Finding(
                    "R0", "W", relpath, index.line(start), "(structure)",
                    r"\end{%s} without a matching \begin" % name))
                continue
            if match_at != len(stack) - 1:
                anomalies.append(Finding(
                    "R0", "W", relpath, index.line(start), "(structure)",
                    r"\end{%s} closes across open %s" % (
                        name, ", ".join(n for n, _ in stack[match_at + 1:]))))
            del stack[match_at:]

            if name in THEOREM_ENVS and open_thms and open_thms[-1][0].env == name:
                stmt, content_start, _ = open_thms.pop()
                stmt.body = text[content_start:start]
                labels = RE_LABEL.findall(stmt.body)
                if labels:
                    stmt.label = labels[0].strip()
                stmt.partly = _has_colour_command(stmt.body)
                refs, cites = _collect_refs(stmt.body)
                stmt.uses = refs                      # filtered globally later
                stmt.cites = cites
                stmt.claude_note = bool(RE_CLAUDE.search(stmt.body))
                statements.append(stmt)
                pending_proof = len(statements) - 1
                pending_from = start
            elif name == "proof" and open_proof is not None:
                idx, pstart, pcolour, pline = open_proof
                open_proof = None
                stmt = statements[idx]
                body = text[pstart:start]
                stmt.has_proof = True
                stmt.proof_line = pline
                stmt.proof_colour = pcolour
                stmt.proof_partly = _has_colour_command(body)
                stmt.proof_sketched = (
                    pcolour in ("sketch", "conjectural")
                    or "sketch" in stmt.proof_partly
                    or "conjectural" in stmt.proof_partly
                )
                refs, cites = _collect_refs(body)
                stmt.uses.extend(refs)
                stmt.cites.extend(cites)
                if RE_CLAUDE.search(body):
                    stmt.claude_note = True

    # every \label in the file, and every reference use, with their lines
    labels_here = [(m.group(1).strip(), index.line(m.start()))
                   for m in RE_LABEL.finditer(text)]

    # owner of a reference = the statement whose span contains it (approximate:
    # the last statement that began at or before the reference)
    starts = [(s.line, s.label) for s in statements]
    ref_uses: List[RefUse] = []
    for m in RE_REF.finditer(text):
        line = index.line(m.start())
        owner = "-"
        for sline, slabel in starts:
            if sline <= line:
                owner = slabel
            else:
                break
        for part in m.group(2).split(","):
            part = part.strip()
            if part:
                ref_uses.append(RefUse(part, relpath, line, owner))

    del pending_from  # only used to document the proof window
    return statements, labels_here, ref_uses, anomalies


# --------------------------------------------------------------------------
# Whole-paper assembly
# --------------------------------------------------------------------------


@dataclass
class Paper:
    statements: List[Statement]
    by_label: Dict[str, Statement]
    all_labels: Dict[str, List[Tuple[str, int]]]   # label -> [(file, line)]
    ref_uses: List[RefUse]
    anomalies: List[Finding]
    order: List[str]                               # section names in input order


def collect_inputs(root: str) -> List[Tuple[str, str]]:
    """The ``\\input{sections/...}`` lines of main.tex, in order.

    Returns (relative tex path, enclosing ``\\section`` title from main.tex).
    """
    main = os.path.join(root, MAIN_TEX)
    text = blank_comments(blank_verbatim(read_tex(main)))
    events: List[Tuple[int, str, str]] = []
    for m in RE_SECTION.finditer(text):
        if m.group(1):                      # subsections in main.tex: ignore
            continue
        title, _ = read_braced(text, m.end() - 1)
        events.append((m.start(), "section", strip_tex(title)))
    for m in RE_INPUT.finditer(text):
        events.append((m.start(), "input", m.group(1).strip()))
    events.sort()

    current = "(front matter)"
    out: List[Tuple[str, str]] = []
    for _, kind, value in events:
        if kind == "section":
            current = value
        else:
            rel = value if value.endswith(".tex") else value + ".tex"
            out.append((rel.replace("\\", "/"), current))
    return out


def build_paper(root: str) -> Paper:
    """Parse main.tex and every file it inputs."""
    statements: List[Statement] = []
    all_labels: Dict[str, List[Tuple[str, int]]] = {}
    ref_uses: List[RefUse] = []
    anomalies: List[Finding] = []
    order: List[str] = []

    # labels declared in main.tex itself
    main_text = blank_comments(blank_verbatim(read_tex(os.path.join(root, MAIN_TEX))))
    main_index = LineIndex(main_text)
    for m in RE_LABEL.finditer(main_text):
        all_labels.setdefault(m.group(1).strip(), []).append(
            (MAIN_TEX, main_index.line(m.start())))

    for rel, section in collect_inputs(root):
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            anomalies.append(Finding("R0", "W", MAIN_TEX, 0, "(input)",
                                     "input file %s not found" % rel))
            continue
        stmts, labels, refs, probs = parse_file(path, rel, section)
        statements.extend(stmts)
        for label, line in labels:
            all_labels.setdefault(label, []).append((rel, line))
        ref_uses.extend(refs)
        anomalies.extend(probs)
        key = section
        if key not in order:
            order.append(key)

    by_label: Dict[str, Statement] = {}
    for stmt in statements:
        if stmt.label != "(unlabelled)" and stmt.label not in by_label:
            by_label[stmt.label] = stmt

    # split each statement's references into theorem dependencies and the rest
    for stmt in statements:
        uses, others, seen = [], [], set()
        for label in stmt.uses:
            if label in seen:
                continue
            seen.add(label)
            if label in by_label and label != stmt.label:
                uses.append(label)
            elif label != stmt.label:
                others.append(label)
        stmt.uses, stmt.also_refers = uses, others
        stmt.cites = sorted(set(stmt.cites))

    for stmt in statements:
        for dep in stmt.uses:
            target = by_label.get(dep)
            if target is not None and stmt.label != "(unlabelled)":
                target.used_by.append(stmt.label)
    for stmt in statements:
        stmt.used_by = sorted(set(stmt.used_by))

    return Paper(statements, by_label, all_labels, ref_uses, anomalies, order)


# --------------------------------------------------------------------------
# Rules R1 - R6
# --------------------------------------------------------------------------


def rule_colour_propagation(paper: Paper) -> List[Finding]:
    """R1: nothing established may rest on something blue or red."""
    out: List[Finding] = []
    for stmt in paper.statements:
        if stmt.colour != ESTABLISHED or stmt.env in COMMENTARY_ENVS:
            continue
        for dep in stmt.uses:
            target = paper.by_label.get(dep)
            if target is None or target.colour not in ("sketch", "conjectural"):
                continue
            msg = "established %s references %s %s (%s)" % (
                stmt.env, target.colour, dep, target.where)
            if stmt.env == "defn" and target.env == "defn" and target.colour == "sketch":
                out.append(Finding("W1", "W", stmt.file, stmt.line, stmt.label,
                                   msg + " -- definition on a sketched definition"))
            else:
                out.append(Finding("R1", "V", stmt.file, stmt.line, stmt.label, msg))
        if stmt.proof_sketched:
            detail = ("inside a %s environment" % stmt.proof_colour
                      if stmt.proof_colour != ESTABLISHED
                      else "contains %s spans" % "/".join(stmt.proof_partly))
            out.append(Finding(
                "R1", "V", stmt.file, stmt.proof_line or stmt.line, stmt.label,
                "established %s has a sketched proof (%s)" % (stmt.env, detail)))
    return out


def rule_no_proof(paper: Paper) -> List[Finding]:
    """R2 (warning): established result with neither proof nor citation."""
    out: List[Finding] = []
    for stmt in paper.statements:
        if stmt.colour != ESTABLISHED or stmt.env not in PROVABLE_ENVS:
            continue
        if stmt.has_proof or stmt.cites:
            continue
        out.append(Finding("W2", "W", stmt.file, stmt.line, stmt.label,
                           "established without proof or citation"))
    return out


def rule_unlabelled(paper: Paper) -> List[Finding]:
    """R3 (warning): theorem-like environment with no \\label."""
    return [Finding("W3", "W", s.file, s.line, "(unlabelled)",
                    "unlabelled %s%s" % (s.env, " [%s]" % s.title if s.title else ""))
            for s in paper.statements if s.label == "(unlabelled)"]


def rule_duplicate_labels(paper: Paper) -> List[Finding]:
    """R4: the same \\label defined twice."""
    out: List[Finding] = []
    for label, places in sorted(paper.all_labels.items()):
        if len(places) < 2:
            continue
        where = ", ".join("%s:%d" % p for p in places)
        out.append(Finding("R4", "V", places[0][0], places[0][1], label,
                           "duplicate label, defined at %s" % where))
    return out


def rule_cycles(paper: Paper) -> List[Finding]:
    """R5: a cycle in the dependency graph."""
    graph = {s.label: [d for d in s.uses if d in paper.by_label]
             for s in paper.statements if s.label != "(unlabelled)"}
    colour: Dict[str, int] = {}
    path: List[str] = []
    cycles: List[List[str]] = []

    def visit(node: str) -> None:
        colour[node] = 1
        path.append(node)
        for nxt in graph.get(node, ()):
            if colour.get(nxt, 0) == 0:
                visit(nxt)
            elif colour.get(nxt) == 1:
                cycles.append(path[path.index(nxt):] + [nxt])
        path.pop()
        colour[node] = 2

    sys.setrecursionlimit(10000)
    for node in graph:
        if colour.get(node, 0) == 0:
            visit(node)

    out: List[Finding] = []
    seen: Set[frozenset] = set()
    for cycle in cycles:
        key = frozenset(cycle)
        if key in seen:
            continue
        seen.add(key)
        head = paper.by_label[cycle[0]]
        out.append(Finding("R5", "V", head.file, head.line, cycle[0],
                           "circular dependency: " + " -> ".join(cycle)))
    return out


def rule_undefined_refs(paper: Paper) -> List[Finding]:
    """R6: a label referenced but never defined (the PDF would show ??)."""
    out: List[Finding] = []
    seen: Set[Tuple[str, str, int]] = set()
    for use in paper.ref_uses:
        if use.label in paper.all_labels:
            continue
        key = (use.label, use.file, use.line)
        if key in seen:
            continue
        seen.add(key)
        out.append(Finding("R6", "V", use.file, use.line, use.owner,
                           "reference to undefined label %s" % use.label))
    return out


# --------------------------------------------------------------------------
# R7: margin overflow (a clipped fragment in the built PDF)
# --------------------------------------------------------------------------

#: substring inline pointer notes use for a note already moved out of the
#: margin (see e.g. ``sections/markings.tex``); a clipped fragment carrying it
#: means the pointer itself is still too long for the column it landed in.
MARGIN_HINT_TEXT = "too long for the margin"

#: main.tex loads ``\usepackage[inner]{showlabels}`` for review, which prints
#: every \label as a standalone "prefix:name" token via its own \marginpar,
#: deliberately in the void outside the page's content area -- unrelated to
#: an author's margin note and not what this rule is for. A fragment whose
#: entire text is one label-shaped token (braces optional) is that debug
#: annotation, not a clipped comment, and is excluded before R7 ever sees it.
RE_SHOWLABEL_TOKEN = re.compile(r"^\{*[A-Za-z][\w]*:[\w:\-]+\}*$")


def _newest_source_mtime(root: str) -> Optional[float]:
    """Latest mtime among ``main.tex`` and every ``.tex`` under ``sections/``
    and ``tikz/`` -- the mtime gate for the R7 scan.
    """
    paths = [os.path.join(root, MAIN_TEX)]
    for sub in ("sections", "tikz"):
        d = os.path.join(root, sub)
        if os.path.isdir(d):
            for name in os.listdir(d):
                if name.endswith(".tex"):
                    paths.append(os.path.join(d, name))
    newest: Optional[float] = None
    for p in paths:
        try:
            mt = os.path.getmtime(p)
        except OSError:
            continue
        if newest is None or mt > newest:
            newest = mt
    return newest


def _pdftohtml_fragments(pdftohtml_exe: str, pdf_path: str
                         ) -> Optional[List[Tuple[int, float, float, str]]]:
    """Every clipped text fragment in the built PDF, as (page, left, top, text).

    A fragment is "clipped" when its box, as reported by ``pdftohtml -xml``,
    falls partly or wholly outside its page -- geometry only, never the text
    itself, so a relocated pointer note is not exempted just because it reads
    as prose rather than a margin comment. Returns ``None`` on any failure
    (a missing/unreadable PDF, a timeout, malformed XML): the caller then
    emits one skip note rather than a partial or wrong scan.
    """
    try:
        proc = subprocess.run(
            [pdftohtml_exe, "-xml", "-stdout", "-zoom", "1", "-i", "-q",
             pdf_path],
            capture_output=True, timeout=120)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        xml_text = proc.stdout.decode("utf-8", "replace")
    except Exception:
        return None
    try:
        root_el = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    out: List[Tuple[int, float, float, str]] = []
    for page_el in root_el.findall("page"):
        try:
            page_no = int(page_el.get("number"))
            page_w = float(page_el.get("width"))
            page_h = float(page_el.get("height"))
        except (TypeError, ValueError):
            continue
        for t in page_el.findall("text"):
            try:
                left = float(t.get("left"))
                top = float(t.get("top"))
                width = float(t.get("width"))
                height = float(t.get("height"))
            except (TypeError, ValueError):
                continue
            text = "".join(t.itertext()).strip()
            if not text or RE_SHOWLABEL_TOKEN.match(text):
                continue
            if left < 0 or top < 0 or left + width > page_w or top + height > page_h:
                out.append((page_no, left, top, text))
    return out


def _resolve_synctex(root: str, page: int, x: float, y: float) -> Tuple[str, int]:
    """(file, line) of a PDF point via ``synctex edit``, or ("", -1) on failure.

    Falls back to ("", -1) -- reported by the caller as a bare page number --
    on a missing ``synctex`` binary, a missing ``.build/main.synctex.gz``, a
    nonzero exit, unparseable output, or a resolved ``Line:-1``.
    """
    synctex_exe = shutil.which("synctex")
    synctex_db = _build_path(root, "synctex.gz")
    pdf_path = _build_path(root, "pdf")
    if not synctex_exe or not os.path.isfile(synctex_db):
        return "", -1
    try:
        proc = subprocess.run(
            [synctex_exe, "edit", "-o",
             "%d:%.2f:%.2f:%s" % (page, x, y, pdf_path)],
            capture_output=True, timeout=30, cwd=root)
    except Exception:
        return "", -1
    if proc.returncode != 0:
        return "", -1
    out = proc.stdout.decode("utf-8", "replace")
    m_input = re.search(r"^Input:(.+?)\r?$", out, re.MULTILINE)
    m_line = re.search(r"^Line:(-?\d+)\r?$", out, re.MULTILINE)
    if not m_input or not m_line:
        return "", -1
    try:
        line = int(m_line.group(1))
    except ValueError:
        return "", -1
    if line < 0:
        return "", -1
    file_path = m_input.group(1).strip()
    try:
        rel = os.path.relpath(file_path, root).replace("\\", "/")
    except ValueError:
        rel = file_path
    return rel, line


def rule_margin_overflow(root: str) -> List[Finding]:
    """R7 (warning): a clipped fragment in the built PDF.

    Requires a build no older than the newest ``.tex`` under ``sections/``,
    ``tikz/`` or ``main.tex`` (a stale PDF is skipped, not scanned), and
    ``pdftohtml``/``synctex`` on PATH to resolve a ``file:line``. Degrades to a
    single skip note -- never an error, never a nonzero exit by itself -- on
    any missing tool, missing/unreadable PDF, or parse failure.
    """
    pdf_path = _build_path(root, "pdf")

    if not os.path.isfile(pdf_path):
        return [Finding("R7", "W", "", 0, "(margin)",
                        "no %s; margin-overflow scan skipped" % _build_rel("pdf"))]
    try:
        pdf_mtime = os.path.getmtime(pdf_path)
    except OSError:
        return [Finding("R7", "W", "", 0, "(margin)",
                        "cannot stat %s; margin-overflow scan "
                        "skipped" % _build_rel("pdf"))]

    newest_source = _newest_source_mtime(root)
    if newest_source is not None and pdf_mtime < newest_source:
        return [Finding("R7", "W", "", 0, "(margin)",
                        "%s.pdf is older than the newest .tex under "
                        "sections/, tikz/ or %s; margin-overflow scan "
                        "skipped (rebuild first)" % (_main_stem(), MAIN_TEX))]

    pdftohtml_exe = shutil.which("pdftohtml")
    if not pdftohtml_exe:
        return [Finding("R7", "W", "", 0, "(margin)",
                        "pdftohtml not on PATH; margin-overflow scan skipped")]

    fragments = _pdftohtml_fragments(pdftohtml_exe, pdf_path)
    if fragments is None:
        return [Finding("R7", "W", "", 0, "(margin)",
                        "pdftohtml scan of %s.pdf failed; margin-overflow "
                        "scan skipped" % _main_stem())]
    if not fragments:
        return []

    out: List[Finding] = []
    for page, x, y, text in fragments:
        loc_file, loc_line = _resolve_synctex(root, page, x, y)
        snippet = text if len(text) <= 60 else text[:57] + "..."
        if loc_line < 0:
            file_field, line_field = "", 0
            where = " (p.%d)" % page
        else:
            file_field, line_field = loc_file, loc_line
            where = ""
        msg = "clipped text on p.%d%s: \"%s\"" % (page, where, snippet)
        if MARGIN_HINT_TEXT in text:
            msg += (" -- already a relocated pointer; the column is still "
                    "too full")
        out.append(Finding("R7", "W", file_field, line_field, "(margin)", msg))
    return out


def run_rules(paper: Paper, root: Optional[str] = None) -> List[Finding]:
    findings: List[Finding] = []
    findings.extend(paper.anomalies)
    findings.extend(rule_colour_propagation(paper))
    findings.extend(rule_no_proof(paper))
    findings.extend(rule_unlabelled(paper))
    findings.extend(rule_duplicate_labels(paper))
    findings.extend(rule_cycles(paper))
    findings.extend(rule_undefined_refs(paper))
    if root is not None:
        findings.extend(rule_margin_overflow(root))
    findings.sort(key=lambda f: (f.file, f.line, f.kind))
    return findings


# --------------------------------------------------------------------------
# Dependency closure helpers
# --------------------------------------------------------------------------


def transitive_deps(paper: Paper, label: str) -> List[str]:
    """Every theorem label reachable from ``label`` (excluding itself)."""
    out: List[str] = []
    seen = {label}
    stack = list(paper.by_label[label].uses) if label in paper.by_label else []
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        out.append(node)
        stmt = paper.by_label.get(node)
        if stmt is not None:
            stack.extend(stmt.uses)
    return sorted(out)


# --------------------------------------------------------------------------
# Build-log summary
# --------------------------------------------------------------------------


@dataclass
class BuildSummary:
    present: bool = False
    errors: int = 0
    undefined: int = 0
    multiply: int = 0
    bibtex: int = 0
    qq: int = 0
    notes: List[str] = field(default_factory=list)

    def render(self) -> str:
        if not self.present:
            return ("BUILD: nothing to check (no %s, .blg or .pdf)"
                    % _build_rel("log"))
        line = ("BUILD: errors %d, undefined %d, multiply %d, bibtex warnings %d, "
                "?? %d" % (self.errors, self.undefined, self.multiply,
                           self.bibtex, self.qq))
        if self.notes:
            line += "\n       " + "\n       ".join(self.notes)
        return line


RE_LOG_ERROR = re.compile(r"^[^ ]+\.tex:[0-9]+:")


def summarise_build(root: str) -> BuildSummary:
    """Summarise .build/main.log, .build/main.blg and ?? in the PDF."""
    summary = BuildSummary()
    log_path = _build_path(root, "log")
    if os.path.isfile(log_path):
        summary.present = True
        with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if RE_LOG_ERROR.match(line) or line.startswith("!"):
                    summary.errors += 1
                low = line.lower()
                if "undefined" in low:
                    summary.undefined += 1
                if "multiply" in low:
                    summary.multiply += 1
    else:
        summary.notes.append(
            "no %s (errors/undefined/multiply not checked; "
            "run %s)" % (_build_rel("log"), " ".join(BUILD_CMD)))
    blg_path = _build_path(root, "blg")
    if os.path.isfile(blg_path):
        summary.present = True
        with open(blg_path, "r", encoding="utf-8", errors="replace") as handle:
            summary.bibtex = sum(1 for line in handle if line.startswith("Warning--"))
    else:
        summary.notes.append("no %s (bibtex warnings not checked)" % _build_rel("blg"))

    pdf = _build_path(root, "pdf")
    if os.path.isfile(pdf):
        exe = shutil.which("pdftotext")
        if exe:
            try:
                proc = subprocess.run([exe, pdf, "-"], capture_output=True, timeout=180)
                summary.qq = proc.stdout.decode("utf-8", "replace").count("??")
                summary.present = True
            except Exception as exc:          # pragma: no cover
                summary.notes.append("pdftotext failed: %s" % exc)
        else:
            summary.notes.append("pdftotext not on PATH (?? in the PDF not checked)")
    else:
        summary.notes.append("no %s" % _build_rel("pdf"))
    return summary


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------

MERMAID_CLASSES = """    classDef established fill:#ffffff,stroke:#444444,color:#111111;
    classDef sketch fill:#dce8fb,stroke:#2c61b5,color:#10305e;
    classDef conjectural fill:#fbdcdc,stroke:#b52c2c,color:#5e1010;
    classDef meta fill:#f2e7d8,stroke:#8b5a2b,color:#4a3015;"""


def _cell(items: Sequence[str], limit: int = 8) -> str:
    """Render a list of labels into one table cell."""
    if not items:
        return ""
    shown = list(items[:limit])
    extra = len(items) - len(shown)
    text = ", ".join("`%s`" % i for i in shown)
    if extra:
        text += ", +%d more" % extra
    return text


def write_registry(paper: Paper, path: str, findings: List[Finding]) -> None:
    """Write Drafts/statements.md (generated file, LF endings)."""
    today = datetime.date.today().isoformat()
    lines: List[str] = []
    lines.append("<!-- GENERATED FILE -- do not edit by hand. "
                 "Regenerate with `py scripts/check_paper.py`. -->")
    lines.append("")
    lines.append("# Statement registry")
    lines.append("")
    lines.append("Generated by `scripts/check_paper.py` on %s. "
                 "Every edit here is overwritten on the next run." % today)
    lines.append("")

    counts: Dict[str, int] = {}
    for stmt in paper.statements:
        counts[stmt.colour] = counts.get(stmt.colour, 0) + 1
    lines.append("%d statements: %s." % (
        len(paper.statements),
        ", ".join("%d %s" % (counts[c], c) for c in sorted(counts))))
    violations = sum(1 for f in findings if f.severity == "V")
    warnings = sum(1 for f in findings if f.severity == "W")
    lines.append("")
    lines.append("Rule check: %d violations, %d warnings." % (violations, warnings))
    lines.append("")

    # ---- one table per section, in \input order -------------------------
    for section in paper.order:
        rows = [s for s in paper.statements if s.section == section]
        if not rows:
            continue
        lines.append("## %s" % section)
        lines.append("")
        lines.append("| label | env | title | colour | proof | uses | used by | "
                     "cites | Claude notes |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for s in rows:
            if s.has_proof:
                proof = "sketched" if s.proof_sketched else "yes"
            else:
                proof = "cited" if s.cites else "none"
            lines.append("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                s.label, s.env, s.title or "", s.colour_display, proof,
                _cell(s.uses), _cell(s.used_by),
                _cell(s.cites, limit=6), "yes" if s.claude_note else ""))
        lines.append("")

    # ---- what blocks the main theorems ----------------------------------
    lines.append("## Blocking the main theorem")
    lines.append("")
    lines.append("For each `thm:` of the introduction (and "
                 "`thm:main-resolvable-4k` in particular), the transitive set of "
                 "`sketch`/`conjectural` statements it rests on.")
    lines.append("")
    targets: List[str] = []
    if "thm:main-resolvable-4k" in paper.by_label:
        targets.append("thm:main-resolvable-4k")
    for stmt in paper.statements:
        if (stmt.file.endswith("introduction.tex") and stmt.env == "thm"
                and stmt.label.startswith("thm:") and stmt.label not in targets):
            targets.append(stmt.label)
    if not targets:
        lines.append("_No `thm:` statements found in `sections/introduction.tex`._")
        lines.append("")
    for label in targets:
        stmt = paper.by_label[label]
        blockers = [d for d in transitive_deps(paper, label)
                    if paper.by_label[d].colour in ("sketch", "conjectural")]
        lines.append("- **`%s`** (%s, %s) -- %d blocking statement%s" % (
            label, stmt.colour, stmt.where, len(blockers),
            "" if len(blockers) == 1 else "s"))
        for dep in blockers:
            target = paper.by_label[dep]
            lines.append("  - `%s` (%s %s, %s)" % (
                dep, target.colour, target.env, target.where))
        if not blockers and not stmt.uses:
            lines.append("  - _nothing is cross-referenced from this statement._")
        lines.append("")

    # ---- dead-end sketches ----------------------------------------------
    lines.append("## Sketches with nothing depending on them")
    lines.append("")
    orphans = [s for s in paper.statements
               if s.colour == "sketch" and not s.used_by
               and s.label != "(unlabelled)"]
    if not orphans:
        lines.append("_None._")
    for s in orphans:
        lines.append("- `%s` (%s, %s) -- %s" % (s.label, s.env, s.where,
                                                s.section))
    lines.append("")

    # ---- dependency graph ------------------------------------------------
    lines.append("## Dependency graph")
    lines.append("")
    lines.append("Edges point from a statement to what it uses; node colour is "
                 "the draft status.")
    lines.append("")
    edges: List[Tuple[str, str]] = []
    for s in paper.statements:
        if s.label == "(unlabelled)":
            continue
        for dep in s.uses:
            if dep in paper.by_label:
                edges.append((s.label, dep))
    nodes = sorted({n for edge in edges for n in edge})
    ids = {label: "n%d" % i for i, label in enumerate(nodes)}
    lines.append("```mermaid")
    lines.append("graph LR")
    lines.append(MERMAID_CLASSES)
    for label in nodes:
        lines.append('    %s["%s"]:::%s' % (
            ids[label], label, paper.by_label[label].colour))
    for src, dst in sorted(set(edges)):
        lines.append("    %s --> %s" % (ids[src], ids[dst]))
    lines.append("```")
    lines.append("")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def report(findings: List[Finding], summary: Optional[BuildSummary],
           registry_path: Optional[str], statements: int) -> int:
    """Print the findings and return the exit code."""
    violations = [f for f in findings if f.severity == "V"]
    warnings = [f for f in findings if f.severity == "W"]

    print("Parsed %d theorem-like statements." % statements)
    print("")
    print("VIOLATIONS (%d)" % len(violations))
    for f in violations:
        print("  " + f.render())
    if not violations:
        print("  none")
    print("")
    print("WARNINGS (%d)" % len(warnings))
    for f in warnings:
        print("  " + f.render())
    if not warnings:
        print("  none")
    print("")
    if summary is not None:
        print(summary.render())
    if registry_path:
        print("Registry written: %s" % registry_path)
    return len(violations)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(
        description="Colour-propagation check and statement registry for an "
                    "academy Author home (vocabulary from .claude/academy.json).")
    parser.add_argument("--strict", action="store_true",
                        help="warnings also cause a non-zero exit")
    parser.add_argument("--registry", default=None,
                        help="path of the generated registry (default: the config's "
                             "author.checker.statements, else %s)" % DEFAULT_REGISTRY)
    parser.add_argument("--no-registry", action="store_true",
                        help="do not write the registry")
    parser.add_argument("--no-log", action="store_true",
                        help="skip the build-log summary (.build/main.log)")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--self-test", action="store_true",
                        help="run the built-in test on an embedded LaTeX sample")
    parser.add_argument("--config", default=None,
                        help="an academy.json to read the vocabulary from (default: "
                             "the nearest .claude/academy.json at or above --root)")
    parser.add_argument("--defaults", action="store_true",
                        help="ignore any academy.json and use the built-in vocabulary")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    root = os.path.abspath(args.root)
    config_path = None if args.defaults else (args.config or find_config(root))
    block, note = load_author_block(config_path)
    if note:
        print("NOTE: %s" % note, file=sys.stderr)
    configure(block)
    if args.registry is None:
        args.registry = REGISTRY_DEFAULT
    try:
        paper = build_paper(root)
    except ParseError as exc:
        print("PARSE ERROR: %s" % exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print("I/O ERROR: %s" % exc, file=sys.stderr)
        return 2

    findings = run_rules(paper, root)
    summary = None if args.no_log else summarise_build(root)

    registry_path = None
    if not args.no_registry:
        registry_path = os.path.join(root, args.registry.replace("/", os.sep))
        write_registry(paper, registry_path, findings)

    violations = report(findings, summary, registry_path, len(paper.statements))
    if summary is not None:
        violations += summary.errors + summary.undefined + summary.qq
    warnings = sum(1 for f in findings if f.severity == "W")
    if violations:
        return 1
    if args.strict and warnings:
        return 1
    return 0


# --------------------------------------------------------------------------
# Self-test on an embedded sample
# --------------------------------------------------------------------------

SAMPLE_MAIN = r"""
\documentclass{amsart}
\begin{document}
\section{Alpha}
\input{sections/alpha}
\section{Beta}
\input{sections/beta}
\end{document}
"""

SAMPLE_ALPHA = r"""
\label{sec:alpha}
% a comment mentioning \begin{thm} that must be ignored
\begin{sketch}
\begin{prop}[Blue one] \label{prop:blue}
    A blue proposition, see \cref{sec:alpha}.
\end{prop}
\end{sketch}

\begin{lem} \label{lem:black}
    A black lemma.
\end{lem}
\begin{proof}
    By \cref{prop:blue,lem:cyclea} and \cite[Lemma 2.1]{Ref1}.
\end{proof}

\begin{meta}
Framing text.
\begin{sketch}
\begin{prop} \label{prop:nested}
    The innermost colour wins.
\end{prop}
\end{sketch}
\end{meta}
"""

SAMPLE_BETA = r"""
\label{sec:beta}
\subsection{Bee}

\begin{claim*} \label{claim:star}
    An unnumbered claim using \cref{lem:cyclea}.
\end{claim*}

\begin{lem} \label{lem:cyclea}
    Head of the cycle, see \cref{lem:cycleb}.
\end{lem}
\begin{proof}
    Immediate.
\end{proof}

\begin{lem} \label{lem:cycleb}
    Tail of the cycle, see \cref{lem:cyclea}.
\end{lem}
\begin{proof}
    Immediate.
\end{proof}

\begin{lem} \label{lem:black}
    A duplicate label.
\end{lem}
\begin{proof}
    Immediate.
\end{proof}

\begin{rmk}
    An unlabelled remark referring to \cref{prop:blue}, which must not be an R1.
\end{rmk}

\begin{cor} \label{cor:partly}
    A black corollary with a \Sketch{hand-waved span} inside, referring to
    \cref{thm:nowhere}. \Claude{a machine note}
\end{cor}
\begin{proof}
    \Sketch{Only a sketch.}
\end{proof}
"""


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(text)


def _utf8_stdout() -> None:
    """Make stdout/stderr UTF-8 so a finding with a non-ASCII character cannot
    crash the run on a legacy console code page (cp1255 when redirected)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):   # pragma: no cover - not a TextIOWrapper
            pass


def self_test() -> int:
    """Parse the embedded sample and assert the expected findings."""
    configure(None)
    failures: List[str] = []

    def check(condition: bool, description: str) -> None:
        print("  %s %s" % ("PASS" if condition else "FAIL", description))
        if not condition:
            failures.append(description)

    with tempfile.TemporaryDirectory() as tmp:
        _write(os.path.join(tmp, "main.tex"), SAMPLE_MAIN)
        _write(os.path.join(tmp, "sections", "alpha.tex"), SAMPLE_ALPHA)
        _write(os.path.join(tmp, "sections", "beta.tex"), SAMPLE_BETA)

        paper = build_paper(tmp)
        findings = run_rules(paper)
        kinds = [(f.kind, f.label) for f in findings]
        labels = paper.by_label          # first definition wins, as cleveref does

        print("Self-test on the embedded sample:")
        check(len(paper.statements) == 9,
              "9 statements parsed (got %d)" % len(paper.statements))
        check(labels["prop:blue"].colour == "sketch",
              "sketch environment colours the proposition blue")
        check(labels["prop:nested"].colour == "sketch",
              "innermost colour wins for meta > sketch > prop")
        check(labels["prop:blue"].title == "Blue one",
              "optional title is captured")
        check("claim:star" in labels and labels["claim:star"].env == "claim*",
              "claim* is recognised")
        check(set(labels["lem:black"].uses) >= {"prop:blue", "lem:cyclea"},
              r"\cref{a,b} list inside the proof is split")
        check("sec:alpha" in labels["prop:blue"].also_refers,
              "sec: references land in 'also refers to'")
        check(("R1", "lem:black") in kinds,
              "R1: black lemma whose proof cites the blue proposition")
        check(("R1", "cor:partly") in kinds,
              "R1: black corollary with a sketched proof")
        check(not any(k == "R1" and lab == "(unlabelled)" for k, lab in kinds),
              "R1 exemption: a remark referring to blue is not a violation")
        check(any(k == "R4" and lab == "lem:black" for k, lab in kinds),
              "R4: duplicate label lem:black")
        check(any(k == "R5" for k, _ in kinds),
              "R5: the lem:cyclea <-> lem:cycleb cycle is found")
        check(any(k == "R6" and "thm:nowhere" in f.message
                  for (k, _), f in zip(kinds, findings)),
              "R6: reference to the undefined thm:nowhere")
        check(any(k == "W3" for k, _ in kinds),
              "W3: the unlabelled remark is reported")
        check(any(k == "W2" and lab == "prop:blue" for k, lab in kinds) is False,
              "W2 only applies to established statements")
        check("sketch" in labels["cor:partly"].partly,
              r"inline \Sketch{...} marks the corollary partly sketch")
        check(labels["cor:partly"].claude_note,
              r"\Claude{...} note is detected")
        check(labels["lem:black"].cites == ["Ref1 (Lemma 2.1)"],
              "citation pinpoint is captured (got %r)" % labels["lem:black"].cites)

        registry = os.path.join(tmp, "Drafts", "statements.md")
        write_registry(paper, registry, findings)
        with open(registry, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        check("\r" not in text, "registry is written with LF endings")
        check("```mermaid" in text, "registry contains the mermaid graph")

        # the section files must be byte-identical after the run
        with open(os.path.join(tmp, "sections", "alpha.tex"), "rb") as handle:
            check(handle.read() == SAMPLE_ALPHA.encode("utf-8").replace(
                b"\n", b"\r\n"), "source file is untouched (CRLF preserved)")

    print("")
    print("Self-test: %d checks failed." % len(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
