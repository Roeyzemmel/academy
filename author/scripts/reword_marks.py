"""reword_marks.py -- the reword marks of the paper's stale settled statements (#137).

    py reword_marks.py [--home H] [--library L] [--label L ...] [--json]     dry run
    py reword_marks.py --apply [--home H] [--library L] [--label L ...]       write them

A ``proved`` / ``proved-modulo`` statement reworded after its review (``registry.py
stale`` lists it: its hash is no longer the hash of its last positive review pass) is at
the draft level **reworded** (``academy:status-vocabulary``): it keeps its status colour,
the words changed since the reviewed text are wrapped in ``\\Reworded{...}`` (violet) and
the words removed are shown struck, ``\\Struck{...}``, where they stood. It reads
"settled on its earlier wording, reword review owed". The marks are generated here, never
typed, and every statement hash ignores them (``\\Reworded{x}`` hashes as ``x``,
``\\Struck{x}`` as nothing), so writing or removing them never moves ``statement_hash``.

For every claim of kind ``stale`` (``registry.core.stale.find``):

1. **The reviewed text** is recovered exactly: the paper's git history (every commit that
   touched ``sections/``, all refs, newest first) is searched for a version of the
   statement's environment -- extracted as the registry engine extracts it -- whose
   statement hash is one the base pass's runs recorded (their ``statement_hash``; for a
   reword pass, its run R's). A statement whose reviewed text cannot be recovered (never
   committed, or a pass pinned on a hand-copied extract, T-0464) is reported and never
   touched.
2. **The current text** is the environment as the engine reads it (marks stripped); it
   must hash as the stale list says.
3. **The diff** is word by word (``reviews.py``'s ``word_diff`` is printed, the one a
   reword brief shows), on units that are balanced in LaTeX: an inline formula, a braced
   group, a bracketed optional argument is one unit, and ``\\begin``/``\\end``/``\\label``/
   ``\\item``/``\\\\``/comments are never wrapped. A change inside display math (or an
   ``array``/``tabular``-like environment) or of a structural token is reported as not
   marked; the others are marked. A struck unit that holds a macro, a formula or a group
   is boxed, ``\\mbox{...}`` (``soul``'s ``\\st`` cannot rebuild ``\\cref`` or
   ``\\textbf`` even inside braces; it takes a box as one unit).
4. The marked environment must strip back to the current text (the same hash), or
   nothing is written.

``--apply`` writes the marks of every recoverable stale statement (after removing any
marks it had), and removes the marks of every statement that is no longer stale (the
reword pass confirmed it); it refuses unless the home's ``author.statusLevels`` has the
level of kind ``mark`` (docs/config.md) and the preamble defines ``\\Reworded`` and
``\\Struck``. Marks on a stale statement whose reviewed text cannot be recovered are left
and reported. Each file is rewritten only when it changed, with its line endings kept;
a written statement is read back through the engine and must hash as before, or its file
is restored and the run fails.

Exit codes: 0 done (dry run: nothing failed to read); 1 a statement could not be
recovered or a write was undone; 2 an error (no Author home, no library, no engine).
"""

import argparse
import difflib
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _author as au  # noqa: E402

ac = au.ac

REWORDED, STRUCK = ac.REWORD_MARK_COMMANDS

#: environments inside which nothing is marked (pictures, tables, verbatim)
NO_MARK_ENVS = {"tikzcd", "tikzpicture", "picture", "tabular", "tabular*", "verbatim",
                "lstlisting", "minted"}
#: display-math environments: a changed unit is coloured (``\\textcolor`` works in math)
#: unless it holds an ``&`` or an unpaired ``\\left`` / ``\\right``; a removed one cannot
#: be struck there (``soul``'s ``\\st`` is text-mode only) and is reported
MATH_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline",
             "multline*", "eqnarray", "eqnarray*", "displaymath", "math", "flalign",
             "flalign*", "alignat", "alignat*", "array", "cases", "matrix", "pmatrix",
             "bmatrix", "vmatrix", "Bmatrix", "smallmatrix", "split", "aligned",
             "gathered", "\\["}
#: environments whose optional argument is options, not words (enumitem's ``label=``)
OPTION_ENVS = {"enumerate", "itemize", "description", "figure", "table", "minipage"}
#: tokens never wrapped: environment boundaries, labels, items (with their optional
#: argument), line breaks, display-math delimiters, comments. A ``\\begin{..}[`` opens an
#: optional argument whose words are diffed like the others, up to its ``]``.
RE_STRUCT = re.compile(r"\\begin\{[^{}]*\}(?:\[)?|\\end\{[^{}]*\}"
                       r"|\\label\{[^{}]*\}|\\item(?![A-Za-z@])(?:\s*\[[^\]]*\])?"
                       r"|\\\\(?:\*)?(?:\[[^\]]*\])?|\\\[|\\\]|(?<!\\)%[^\n]*")
RE_ENV_TOKEN = re.compile(r"\\(begin|end)\{([^{}]*)\}")


class Refused(Exception):
    pass


# --------------------------------------------------------------------------- engine

_ENGINE = {}


def engine():
    """The registry engine's modules (``registry.core.stale``, ``federation``,
    ``workspace``, ``model`` and the paper profile), from this academy repo."""
    if not _ENGINE:
        plugin = os.path.join(ac.repo_root(), "academy")
        if plugin not in sys.path:
            sys.path.insert(0, plugin)
        try:
            from registry.core import federation, model, stale, workspace
            from registry.profiles import fsl
        except ImportError as exc:
            raise Refused("the registry engine cannot be imported from %s (%s)"
                          % (plugin, exc))
        _ENGINE.update(federation=federation, model=model, stale=stale,
                       workspace=workspace, fsl=fsl)
    return _ENGINE


_WORD_DIFF = {}


def word_diff(old, new):
    """``reviews.py``'s word diff (``[-removed-]`` / ``{+added+}``), the one the reword
    brief shows; loaded by path from the Expert plugin beside this one."""
    if "fn" not in _WORD_DIFF:
        fn = None
        path = os.path.join(ac.repo_root(), "expert", "scripts", "reviews.py")
        if os.path.isfile(path):
            here = os.path.dirname(path)
            added = here not in sys.path
            if added:
                sys.path.append(here)
            try:
                spec = importlib.util.spec_from_file_location("_author_reword_reviews", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                fn = mod.word_diff
            except Exception:       # noqa: BLE001 -- the diff below is the same rule
                fn = None
        _WORD_DIFF["fn"] = fn or _word_diff
    return _WORD_DIFF["fn"](old, new)


def _word_diff(old, new):
    a, b = str(old or "").split(), str(new or "").split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False) \
            .get_opcodes():
        if op == "equal":
            out.extend(a[i1:i2])
            continue
        if i2 > i1:
            out.append("[-%s-]" % " ".join(a[i1:i2]))
        if j2 > j1:
            out.append("{+%s+}" % " ".join(b[j1:j2]))
    return " ".join(out)


def strip(text):
    return engine()["model"].strip_marks(text)


def hash_of(text):
    return engine()["model"].statement_hash_of(text)


def paper_statement(label, texts):
    """The environment carrying ``\\label{label}`` in ``texts`` (sections/*.tex in name
    order), exactly as the engine extracts it (marks stripped), or None."""
    return engine()["fsl"]._paper_statement(None, label, texts)


def env_span(text, label):
    """``(start, end)`` in ``text`` of the environment the engine reads for ``label``
    (``fsl._paper_statement``: the last ``\\begin`` before the label, to its ``\\end``),
    or None."""
    i = text.find("\\label{%s}" % label)
    if i < 0:
        return None
    begins = list(re.finditer(r"\\begin\{([A-Za-z*]+)\}", text[:i]))
    if not begins:
        return None
    b = begins[-1]
    end = text.find("\\end{%s}" % b.group(1), i)
    return (b.start(), end + len(b.group(1)) + 6 if end >= 0 else i)


# --------------------------------------------------------------------------- units

class Atom(object):
    """One unit of a statement: ``ctx`` is ``text``, ``math`` (display math) or ``none``
    (a picture, a table) at its start; ``markable`` whether it may be wrapped."""
    __slots__ = ("start", "end", "text", "key", "markable", "ctx")

    def __init__(self, start, end, text, markable, ctx):
        self.start, self.end, self.text = start, end, text
        self.key = " ".join(text.split())
        self.markable = markable
        self.ctx = ctx

    def __repr__(self):
        return "Atom(%r, %s%s)" % (self.text, self.ctx, "" if self.markable else ", fixed")


RE_LEFT = re.compile(r"\\left(?![A-Za-z@])")
RE_RIGHT = re.compile(r"\\right(?![A-Za-z@])")


def _plain_atoms(text, base, out, ctx, stop_bracket=False):
    """Whitespace-separated units of ``text`` (no structural token in it), each balanced:
    braces, brackets outside math, inline math (``$``, ``\\(``) closed. With
    ``stop_bracket``, a ``]`` at depth zero ends the text (an optional argument); the
    index of that ``]`` in ``text`` is returned (None when there is none)."""
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if stop_bracket and text[i] == "]":
            return i
        start, brace, brack, math = i, 0, 0, False
        while i < n:
            c = text[i]
            if c == "\\":
                nxt = text[i + 1:i + 2]
                if nxt == "(":
                    math = True
                elif nxt == ")":
                    math = False
                i += 2
                continue
            if c == "{":
                brace += 1
            elif c == "}":
                brace -= 1
            elif c == "$":
                math = not math
            elif c == "[" and not math and ctx == "text":
                brack += 1
            elif c == "]" and not math and ctx == "text":
                if brack > 0:
                    brack -= 1
                elif stop_bracket and brace == 0:
                    break
            elif c.isspace() and brace <= 0 and brack == 0 and not math:
                break
            i += 1
        chunk = text[start:i]
        ok = brace == 0 and brack == 0 and not math and ctx != "none"
        if ok and ctx == "math":
            ok = "&" not in chunk and len(RE_LEFT.findall(chunk)) == \
                len(RE_RIGHT.findall(chunk))
        if chunk:
            out.append(Atom(base + start, base + i, chunk, ok, ctx))
        if stop_bracket and i < n and text[i] == "]" and brace == 0 and brack == 0:
            return i
    return None


def atoms(text):
    """The units of a statement's text, in order (see :class:`Atom`)."""
    out, stack, pos = [], [], 0

    def ctx():
        if any(e in NO_MARK_ENVS for e in stack):
            return "none"
        return "math" if any(e in MATH_ENVS for e in stack) else "text"

    while True:
        m = RE_STRUCT.search(text, pos)
        if m is None:
            break
        _plain_atoms(text[pos:m.start()], pos, out, ctx())
        tok = m.group(0)
        before = ctx()
        e = RE_ENV_TOKEN.match(tok)
        if e and e.group(1) == "begin":
            stack.append(e.group(2))
        elif e and e.group(1) == "end":
            if e.group(2) in stack:
                while stack and stack.pop() != e.group(2):
                    pass
        elif tok == "\\[":
            stack.append("\\[")
        elif tok == "\\]" and "\\[" in stack:
            while stack and stack.pop() != "\\[":
                pass
        out.append(Atom(m.start(), m.end(), tok, False, before))
        pos = m.end()
        if e and e.group(1) == "begin" and tok.endswith("["):     # a title: its words
            inner = []
            close = _plain_atoms(text[pos:], pos, inner, "text", stop_bracket=True)
            if close is None or not e or e.group(2) in OPTION_ENVS | NO_MARK_ENVS | MATH_ENVS:
                for u in inner:         # a list's or a picture's options: never marked
                    u.markable = False
            if close is None:
                out += inner
                pos = len(text)
                continue
            out += inner
            out.append(Atom(pos + close, pos + close + 1, "]", False, "text"))
            pos = pos + close + 1
    _plain_atoms(text[pos:], pos, out, ctx())
    return out


def _struck_text(units):
    """The words a ``\\Struck`` shows: a unit holding a macro, a formula or a group is
    boxed (``\\mbox{...}``), since ``soul``'s ``\\st`` fails to rebuild ``\\cref``,
    ``\\textbf`` or ``\\{`` in math even inside braces (pdflatex, 2026-11-27) and takes a
    box as one unit."""
    return " ".join("\\mbox{%s}" % u.text if any(c in u.text for c in "\\${") else u.text
                    for u in units)


def mark(old, new):
    """``(marked, report)``: the current statement ``new`` (no marks) with the reword
    marks against the reviewed ``old``; ``report`` = ``{"reworded": n, "struck": n,
    "unmarked": [what was left unmarked]}``."""
    a, b = atoms(old), atoms(new)
    sm = difflib.SequenceMatcher(None, [x.key for x in a], [x.key for x in b],
                                 autojunk=False)
    wraps, inserts = [], []          # (start, end); (pos, text)
    rep = {"reworded": 0, "struck": 0, "unmarked": []}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        gone = a[i1:i2]
        if gone:
            keep = [u for u in gone if u.markable and u.ctx == "text"]
            for u in gone:
                if u not in keep:
                    rep["unmarked"].append("removed %r" % u.key[:60])
            if keep:
                # shown just before the words that replace them, else before what follows;
                # never before the environment's own \begin (outside the statement)
                k = next((j for j in range(j1, j2) if b[j].markable), j2)
                at = b[k] if 0 < k < len(b) else None
                if at is None or at.ctx != "text":
                    rep["unmarked"].append("removed %r (no place to show it)"
                                           % " ".join(u.key for u in keep)[:60])
                else:
                    # a space after it only where one stands before it (the hash
                    # collapses whitespace but does not invent it): "[\\Struck{Old }New"
                    words = _struck_text(keep)
                    spaced = at.start == 0 or new[at.start - 1].isspace()
                    inserts.append((at.start, "%s{%s} " % (STRUCK, words) if spaced
                                    else "%s{%s }" % (STRUCK, words)))
                    rep["struck"] += len(keep)
        run = []
        for u in b[j1:j2] + [None]:
            if u is not None and u.markable and (not run or run[-1].ctx == u.ctx):
                run.append(u)
                continue
            if run:
                wraps.append((run[0].start, run[-1].end))
                rep["reworded"] += len(run)
                run = []
            if u is not None and u.markable:
                run.append(u)
            elif u is not None:
                rep["unmarked"].append("added %r" % u.key[:60])
    edits = [(s, 1, "%s{" % REWORDED) for s, _e in wraps] + \
        [(e, 0, "}") for _s, e in wraps] + [(p, 2, t) for p, t in inserts]
    # at one position: a closing brace first, then a struck insert, then an opening
    edits.sort(key=lambda x: (x[0], {0: 0, 2: 1, 1: 2}[x[1]]))
    out, pos = [], 0
    for p, _k, t in edits:
        out.append(new[pos:p])
        out.append(t)
        pos = p
    out.append(new[pos:])
    return "".join(out), rep


def has_marks(text):
    return ac.RE_REWORD_MARK.search(text or "") is not None


def strip_in_place(text):
    """``text`` with its marks removed as they were written: ``\\Reworded{x}`` -> ``x``,
    ``\\Struck{x}`` and the one space after it -> nothing."""
    if not has_marks(text):
        return text
    res, i = [], 0
    while True:
        m = ac.RE_REWORD_MARK.search(text, i)
        end = ac.tex_group_end(text, m.end()) if m else None
        if m is None or end is None:
            res.append(text[i:])
            return "".join(res)
        res.append(text[i:m.start()])
        if m.group(1) == "Reworded":
            res.append(strip_in_place(text[m.end():end]))
            i = end + 1
        else:
            i = end + 1
            if text[i:i + 1] == " ":
                i += 1


# --------------------------------------------------------------------------- git

class GitTexts(object):
    """The versions of ``sections/*.tex`` in the paper's history, read through one
    ``git cat-file --batch``."""

    def __init__(self, home):
        self.home = home
        self.blobs = {}
        self.proc = None

    def _git(self, *args):
        res = subprocess.run(["git", "-C", self.home] + list(args), capture_output=True)
        if res.returncode != 0:
            raise Refused("git %s: %s" % (" ".join(args),
                                          res.stderr.decode("utf-8", "replace").strip()))
        return res.stdout.decode("utf-8", "replace")

    def commits(self):
        try:
            out = self._git("log", "--all", "--format=%H", "--", "sections")
        except Refused:
            return []
        return [c for c in out.split() if c]

    def tree(self, commit):
        """``[(path, blob)]`` of the ``sections/*.tex`` files at ``commit``, by name."""
        rows = []
        for ln in self._git("ls-tree", commit, "sections/").splitlines():
            meta, _tab, path = ln.partition("\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob" and path.endswith(".tex"):
                rows.append((path, parts[2]))
        return sorted(rows)

    def blob(self, sha):
        if sha not in self.blobs:
            if self.proc is None:
                self.proc = subprocess.Popen(["git", "-C", self.home, "cat-file", "--batch"],
                                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            self.proc.stdin.write((sha + "\n").encode())
            self.proc.stdin.flush()
            head = self.proc.stdout.readline().decode().split()
            size = int(head[2]) if len(head) == 3 else 0
            data = self.proc.stdout.read(size)
            self.proc.stdout.read(1)
            self.blobs[sha] = data.decode("utf-8", "replace")
        return self.blobs[sha]

    def close(self):
        if self.proc is not None:
            self.proc.stdin.close()
            self.proc.wait()
            self.proc = None


def recover(home, wanted):
    """``{label: {"text", "commit", "file"}}`` for the labels of ``wanted`` (label ->
    the set of hashes its base pass recorded) whose reviewed environment some version of
    ``sections/*.tex`` in the history holds; the newest such version wins."""
    found, git = {}, GitTexts(home)
    pending = dict(wanted)
    seen_trees, memo = set(), {}
    try:
        for commit in git.commits():
            if not pending:
                break
            tree = tuple(git.tree(commit))
            if tree in seen_trees:
                continue
            seen_trees.add(tree)
            for label in list(pending):
                key = None
                for path, sha in tree:
                    if ("\\label{%s}" % label) in git.blob(sha):
                        key = (path, sha)
                        break
                if key is None:
                    continue
                if (label, key) not in memo:
                    env = paper_statement(label, [git.blob(key[1])])
                    memo[(label, key)] = (env, hash_of(env) if env else None)
                env, h = memo[(label, key)]
                if h and h in pending[label]:
                    found[label] = {"text": env, "commit": commit, "file": key[0]}
                    del pending[label]
    finally:
        git.close()
    return found


# --------------------------------------------------------------------------- the plan

def _sections(home):
    d = os.path.join(home, "sections")
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(".tex"))
    except OSError:
        return []
    return [os.path.join(d, n) for n in names]


def _read(path):
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def stale_items(home, library=None):
    """``(store, stale items)`` of the paper's namespace (kind ``stale`` only), against
    the library's reviews (``library``, else the workspace's Expert home)."""
    eg = engine()
    ns = eg["workspace"].repo_ns(home) or "paper"
    store = eg["federation"].store(ns, home)
    if store is None:
        raise Refused("no registry store for `%s` at %s" % (ns, home))
    if library:
        rel = (((ac.load_config(library) if os.path.isfile(
            os.path.join(library, ".claude", "academy.json")) else {}) or {})
               .get("paths") or {}).get("reviews") or "reviews"
        root = os.path.join(library, rel[0] if isinstance(rel, list) else rel)
        from pathlib import Path
        root = Path(root) if os.path.isdir(root) else None
    else:
        root = eg["stale"].reviews_root(home)
    if root is None:
        raise Refused("no library reviews/ folder (give --library)")
    problem = eg["stale"].decision_table_problem()
    if problem:
        raise Refused(problem)
    return store, [i for i in eg["stale"].find(store, root) if i["kind"] == "stale"]


def where(home, label):
    """``(path, text, (start, end))`` of the statement of ``label`` in the first
    ``sections/*.tex`` that carries the label (the engine's rule), or None."""
    for path in _sections(home):
        text = _read(path)
        span = env_span(text, label)
        if span:
            return path, text, span
    return None


def plan(home, library=None, labels=None):
    """What a run would do: ``{"items": [...], "remove": [...], "kept": [...]}``.

    ``items``: one per stale claim (``labels``: only those), each with ``qid``, ``label``,
    ``file``, ``lines``, ``status``, ``pass``, ``pass_hash``, ``hash``, ``recovered``
    (``{commit, file}`` or None), ``reason`` (why it is not marked; '' when it is),
    ``word_diff``, ``report`` and the ``marked`` environment. ``remove``: the statements
    carrying marks that are not stale (``{label, file, lines}``). ``kept``: marked
    statements left alone (stale, not recoverable)."""
    store, items = stale_items(home, library)
    if labels:
        items = [i for i in items if i["id"] in labels]
    wanted = {i["id"]: {h for h in str(i["pass_hash"]).split("/") if h} for i in items}
    found = recover(home, wanted)
    out = []
    for it in items:
        label = it["id"]
        row = {"qid": it["qid"], "label": label, "status": it["status"],
               "pass": it["pass"], "pass_hash": it["pass_hash"], "hash": it["hash"],
               "file": "", "lines": None, "recovered": None, "reason": "",
               "word_diff": "", "report": None, "marked": None, "had_marks": False,
               "env": None}
        loc = where(home, label)
        if loc is None:
            row["reason"] = "its environment is not in sections/*.tex"
            out.append(row)
            continue
        path, text, span = loc
        row["file"] = os.path.relpath(path, home).replace("\\", "/")
        row["env"] = [row["file"], span[0]]
        row["lines"] = [_line(text, span[0]), _line(text, span[1] - 1)]
        current_raw = text[span[0]:span[1]]
        row["had_marks"] = has_marks(current_raw)
        current = strip_in_place(current_raw)
        if hash_of(current) != it["hash"]:
            row["reason"] = ("its environment hashes to %s here, not %s as the registry "
                             "reads it" % (hash_of(current), it["hash"]))
            out.append(row)
            continue
        rec = found.get(label)
        if rec is None:
            row["reason"] = ("the reviewed text cannot be recovered: no version of "
                             "sections/*.tex in the git history holds an environment of "
                             "%s hashing to %s (the base pass %s)"
                             % (label, it["pass_hash"], it["pass"]))
            out.append(row)
            continue
        row["recovered"] = {"commit": rec["commit"], "file": rec["file"]}
        row["word_diff"] = word_diff(rec["text"], strip(current))
        marked, rep = mark(rec["text"], current)
        row["report"] = rep
        if hash_of(marked) != it["hash"]:
            row["reason"] = "the marked text would not hash as the statement (a bug): left"
        elif marked == current:
            row["reason"] = "no change could be marked (%s)" % "; ".join(rep["unmarked"])
        else:
            row["marked"] = marked
        out.append(row)
    _one_per_environment(out)
    stale_labels = {i["id"] for i in items}
    remove, kept = [], []
    for path, text, span, rids in marked_statements(home, store):
        rel = os.path.relpath(path, home).replace("\\", "/")
        mine = [r for r in out if r["env"] == [rel, span[0]]]
        if any(rid in stale_labels for rid in rids):
            if mine and not any(r["marked"] is not None for r in mine):
                kept.append({"label": mine[0]["label"], "file": rel,
                             "reason": mine[0]["reason"]})
            continue
        if labels and not labels.intersection(rids):
            continue
        remove.append({"label": rids[0], "labels": rids, "file": rel, "env": [rel, span[0]],
                       "lines": [_line(text, span[0]), _line(text, span[1] - 1)]})
    return {"items": out, "remove": remove, "kept": kept}


def _one_per_environment(rows):
    """Several stale records may share one environment (a statement with an old and a new
    label). It is marked once: against the newest base pass among them (pass names start
    with their date); the others say so and are not written."""
    by_env = {}
    for r in rows:
        if r["marked"] is not None:
            by_env.setdefault(tuple(r["env"]), []).append(r)
    for group in by_env.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda r: (r["pass"], r["label"]), reverse=True)
        keep = group[0]
        for r in group[1:]:
            if r["marked"] != keep["marked"]:
                r["reason"] = ("its environment is %s's, marked against that record's base "
                               "pass %s" % (keep["label"], keep["pass"]))
            else:
                r["reason"] = "its environment is %s's, marked once" % keep["label"]
            r["marked"] = None
            r["shared"] = keep["label"]


def marked_statements(home, store):
    """``(path, text, span, [record ids])`` of every registry statement environment that
    carries a reword mark (an environment once, with every record whose label it holds)."""
    out = []
    for path in _sections(home):
        text = _read(path)
        if not has_marks(text):
            continue
        envs = {}
        for rid in sorted(store.records):
            span = env_span(text, rid)
            if span and has_marks(text[span[0]:span[1]]):
                envs.setdefault(span, []).append(rid)
        for span in sorted(envs):
            out.append((path, text, span, envs[span]))
    return out


# --------------------------------------------------------------------------- apply

def _preamble_defines(home, cfg):
    pre = ac.author_tex(cfg, "preamble")
    try:
        text = _read(os.path.join(home, pre.get("file") or "main.tex"))
    except OSError:
        return False
    head = text.split(pre.get("end") or "\\begin{document}", 1)[0]
    return all(re.search(re.escape(m) + r"(?![A-Za-z@])", head) for m in (REWORDED, STRUCK))


def apply(home, cfg, result):
    """Write the plan: marks on each markable stale statement, none on the statements no
    longer stale. A file is written only when its edits do not overlap, every edited
    statement still hashes as before and the file without its marks is the file without
    its marks before (nothing outside the marks changed); otherwise it is restored.
    Returns the problems."""
    edits = {}          # path -> {span: (new text, label)}
    for r in result["items"]:
        if r["marked"] is None:
            continue
        path, text, span = where(home, r["label"])
        edits.setdefault(path, {})[span] = (r["marked"], r["label"])
    for r in result["remove"]:
        loc = where(home, r["label"])
        if loc is None:
            continue
        path, text, span = loc
        edits.setdefault(path, {}).setdefault(
            span, (strip_in_place(text[span[0]:span[1]]), r["label"]))
    problems = []
    for path, rows in sorted(edits.items()):
        rel = os.path.relpath(path, home)
        text = _read(path)
        spans = sorted(rows)
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
            problems.append("%s: two statement environments overlap (%s); nothing written"
                            % (rel, ", ".join(rows[sp][1] for sp in spans)))
            continue
        before = {lab: hash_of(paper_statement(lab, [text]) or "")
                  for _t, lab in rows.values()}
        new = text
        for sp in reversed(spans):
            new = new[:sp[0]] + rows[sp][0] + new[sp[1]:]
        if new == text:
            continue
        moved = [lab for _t, lab in rows.values()
                 if hash_of(paper_statement(lab, [new]) or "") != before[lab]]
        if moved or strip_in_place(new) != strip_in_place(text):
            problems.append("%s: %s; nothing written" % (
                rel, "the statement hash of %s would move" % ", ".join(moved) if moved
                else "the text outside the marks would change"))
            continue
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new)
    return problems


# --------------------------------------------------------------------------- output

def render(result, applied=False):
    items = result["items"]
    marked = [r for r in items if r["marked"] is not None]
    lost = [r for r in items if r["recovered"] is None]
    lines = ["reword marks: %d stale settled statement(s); %d to mark, %d whose reviewed "
             "text cannot be recovered, %d other; %d marked statement(s) no longer stale"
             % (len(items), len(marked), len(lost), len(items) - len(marked) - len(lost),
                len(result["remove"]))]
    for r in items:
        head = "%s  %s  %s:%s  base pass %s (%s)" % (
            r["qid"], r["status"], r["file"] or "?",
            "%d-%d" % tuple(r["lines"]) if r["lines"] else "?", r["pass"], r["pass_hash"])
        lines += ["", "## " + head]
        if r["recovered"]:
            lines.append("reviewed text: %s at %s" % (r["recovered"]["file"],
                                                     r["recovered"]["commit"][:12]))
            lines.append("word diff: " + r["word_diff"])
        if r["report"]:
            rep = r["report"]
            lines.append("marks: %d unit(s) \\Reworded, %d unit(s) \\Struck%s" % (
                rep["reworded"], rep["struck"],
                "; not marked: " + "; ".join(rep["unmarked"]) if rep["unmarked"] else ""))
        if r["reason"]:
            lines.append(("left: " if r["had_marks"] else "not marked: ") + r["reason"])
        elif r["marked"] is not None:
            lines.append(("written" if applied else "would write") + ":")
            lines.append(r["marked"])
    for r in result["remove"]:
        lines.append("\n%s: %s:%d-%d is no longer stale: its marks %s" % (
            r["label"], r["file"], r["lines"][0], r["lines"][1],
            "were removed" if applied else "would be removed"))
    return "\n".join(lines)


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home", default=None)
    ap.add_argument("--library", default=None,
                    help="the Expert home whose reviews/ hold the passes (default: the "
                         "workspace's)")
    ap.add_argument("--label", action="append", default=[],
                    help="only this statement (repeatable; paper:<label> or <label>)")
    ap.add_argument("--apply", action="store_true", help="write the marks")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    home, cfg = au.author_home(a.home or os.getcwd())
    if not home:
        sys.stderr.write("reword_marks: not in an Author home (give --home)\n")
        return 2
    labels = {lab.split(":", 1)[1] if lab.startswith("paper:") else lab for lab in a.label}
    if a.apply:
        if ac.author_mark_level(cfg) is None:
            sys.stderr.write("reword_marks: refused: author.statusLevels has no level of "
                             "kind mark (the reworded level, docs/config.md): nothing "
                             "written\n")
            return 2
        if not _preamble_defines(home, cfg):
            sys.stderr.write("reword_marks: refused: the preamble defines no %s and %s: "
                             "nothing written\n" % (REWORDED, STRUCK))
            return 2
    try:
        result = plan(home, a.library, labels or None)
    except Refused as exc:
        sys.stderr.write("reword_marks: %s\n" % exc)
        return 2
    problems = apply(home, cfg, result) if a.apply else []
    if a.json:
        print(json.dumps(dict(result, problems=problems), indent=1, ensure_ascii=False))
    else:
        print(render(result, a.apply))
        if not a.apply and ac.author_mark_level(cfg) is None:
            print("\nnote: this home has no reworded level (author.statusLevels, kind "
                  "mark); --apply refuses until it does")
        for p in problems:
            print("problem: " + p)
    lost = any(r["recovered"] is None for r in result["items"])
    return 1 if (lost or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
