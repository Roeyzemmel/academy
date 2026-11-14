"""statement.py -- one statement of the paper by its label, or the map of a tex file.

    py statement.py <label> [<label> ...] [--proof] [--context N] [--home H] [--json]
    py statement.py --outline <file.tex> [--home H] [--json]

A section file of a long paper is larger than one Read allows (25,000 tokens; the error
ledger of 2026-10-31..11-08 has nine whole-file reads of a 1,000-line section refused).
An agent that works on one statement does not need the file: this prints the statement's
environment (from ``\\begin{<env>}`` to ``\\end{<env>}`` around ``\\label{<label>}``,
found as ``pinned.py`` finds it) with its file and line range, with ``--proof`` the
``proof`` (or ``sketch``) environment that follows it, and with ``--context N`` the N
lines before and after. Edit with the Edit tool on that text; to read more of the file,
Read it with ``offset`` and ``limit`` from the line numbers given here.

``--outline FILE`` lists every labelled statement of one file in order -- lines, environment,
label, and whether a proof follows -- together with the ``\\section`` / ``\\subsection``
lines: the map to choose a range from.

Read-only. Exit 0 when every label was found; 1 when one was not (the others are still
printed; a miss names the near labels); 2 on an error.
"""

import argparse
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _author as au  # noqa: E402
import pinned  # noqa: E402

RE_LABEL = re.compile(r"\\label\{([^}]+)\}")
RE_PROOF = re.compile(r"\s*(?:%[^\n]*\n\s*)*\\begin\{(proof|sketch)\}")
RE_HEADING = re.compile(r"^\s*\\((?:sub){0,2}section\*?)\{(.*)$")


def _read(path):
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def proof_span(text, end):
    """``(start, end)`` of the proof or sketch environment that follows position ``end``
    (only blank lines and comments between), or None."""
    m = RE_PROOF.match(text, end)
    if not m:
        return None
    env, depth = m.group(1), 0
    for b in pinned.RE_BEGIN_END.finditer(text, m.start(1) - len("\\begin{")):
        if b.group(2) != env:
            continue
        depth += 1 if b.group(1) == "begin" else -1
        if depth == 0:
            return (text.index("\\begin{%s}" % env, end), b.end())
    return None


RE_INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")


def included_files(home, cfg):
    """The tex files the paper reads: the main file and what it (transitively) inputs,
    relative to ``home``; None when the main file cannot be read (then nothing is said)."""
    main = ((cfg or {}).get("paths") or {}).get("main") or "main.tex"
    seen, todo = set(), [main]
    while todo:
        rel = todo.pop()
        rel = rel if rel.endswith(".tex") else rel + ".tex"
        rel = os.path.normpath(rel).replace(os.sep, "/")
        if rel in seen:
            continue
        try:
            text = pinned.live_text(_read(os.path.join(home, rel)))
        except OSError:
            if rel == os.path.normpath(main).replace(os.sep, "/"):
                return None
            continue
        seen.add(rel)
        todo += RE_INPUT.findall(text)
    return seen


NOT_INPUT = "this file is not \\input by the paper's main file: not part of the paper as built"


def find(home, cfg, label, proof=False, context=0):
    """The statement of ``label``: ``{label, file, env, lines: [a, b], text, proof?:
    {lines, text}, before?, after?}``, or None."""
    envs = pinned.statement_envs(cfg)
    for path in pinned.tex_files(home, cfg):
        try:
            text = _read(path)
        except OSError:
            continue
        span = pinned.statement_env(text, label, envs)
        if not span:
            continue
        m = pinned.RE_BEGIN_END.match(text, span[0])
        out = {"label": label, "file": os.path.relpath(path, home).replace("\\", "/"),
               "env": m.group(2) if m else "",
               "lines": [_line(text, span[0]), _line(text, span[1] - 1)],
               "text": text[span[0]:span[1]]}
        inc = included_files(home, cfg)
        if inc is not None and out["file"] not in inc:
            out["note"] = NOT_INPUT
        last = out["lines"][1]
        if proof:
            ps = proof_span(text, span[1])
            if ps:
                out["proof"] = {"lines": [_line(text, ps[0]), _line(text, ps[1] - 1)],
                                "text": text[ps[0]:ps[1]]}
                last = out["proof"]["lines"][1]
        if context > 0:
            rows = text.split("\n")
            a = out["lines"][0]
            out["before"] = "\n".join(rows[max(0, a - 1 - context):a - 1])
            out["after"] = "\n".join(rows[last:last + context])
        return out
    return None


def all_labels(home, cfg):
    out = []
    for path in pinned.tex_files(home, cfg):
        try:
            out += RE_LABEL.findall(pinned.live_text(_read(path)))
        except OSError:
            continue
    return out


def outline(home, cfg, path):
    """The labelled statements and the headings of one tex file, in file order."""
    text = _read(path)
    envs = pinned.statement_envs(cfg)
    rows, seen = [], set()
    for n, ln in enumerate(pinned.live_text(text).split("\n"), 1):
        h = RE_HEADING.match(ln)
        if h:
            rows.append({"lines": [n, n], "kind": h.group(1),
                         "title": h.group(2).rstrip().rstrip("}")[:80]})
    live = pinned.live_text(text)
    for m in RE_LABEL.finditer(live):
        span = pinned.statement_env(text, m.group(1), envs)
        if not span or span[0] in seen:
            continue                    # a label inside a statement already listed
        seen.add(span[0])
        b = pinned.RE_BEGIN_END.match(text, span[0])
        first = RE_LABEL.search(live, span[0], span[1])
        ps = proof_span(text, span[1])
        rows.append({"lines": [_line(text, span[0]), _line(text, span[1] - 1)],
                     "kind": b.group(2) if b else "", "label": first.group(1),
                     "proof": [_line(text, ps[0]), _line(text, ps[1] - 1)] if ps else None})
    rows.sort(key=lambda r: r["lines"][0])
    out = {"file": os.path.relpath(path, home).replace("\\", "/"),
           "total_lines": len(text.splitlines()), "rows": rows}
    inc = included_files(home, cfg)
    if inc is not None and out["file"] not in inc:
        out["note"] = NOT_INPUT
    return out


def render(rec):
    head = "%s  %s:%d-%d  (%s)" % (rec["label"], rec["file"], rec["lines"][0],
                                   rec["lines"][1], rec["env"])
    parts = [head]
    if rec.get("note"):
        parts.append("note: " + rec["note"])
    if rec.get("before"):
        parts += ["--- %d line(s) before" % (rec["before"].count("\n") + 1), rec["before"]]
    parts += ["--- statement", rec["text"]]
    if rec.get("proof"):
        parts += ["--- proof  lines %d-%d" % tuple(rec["proof"]["lines"]), rec["proof"]["text"]]
    if rec.get("after"):
        parts += ["--- %d line(s) after" % (rec["after"].count("\n") + 1), rec["after"]]
    return "\n".join(parts)


def render_outline(o):
    lines = ["%s  (%d lines)" % (o["file"], o["total_lines"])]
    if o.get("note"):
        lines.append("note: " + o["note"])
    for r in o["rows"]:
        if "label" not in r:
            lines.append("%5d        \\%s{%s}" % (r["lines"][0], r["kind"], r["title"]))
        else:
            lines.append("%5d-%-5d %-6s %s%s" % (
                r["lines"][0], r["lines"][1], r["kind"], r["label"],
                "  + proof %d-%d" % tuple(r["proof"]) if r["proof"] else ""))
    return "\n".join(lines)


def where_line(rec):
    """``<label>: <file> lines A-B, proof lines C-D`` (``no proof environment follows``
    when there is none)."""
    proof = rec.get("proof")
    return "%s: %s lines %d-%d, %s" % (
        rec["label"], rec["file"], rec["lines"][0], rec["lines"][1],
        "proof lines %d-%d" % tuple(proof["lines"]) if proof
        else "no proof environment follows")


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("labels", nargs="*")
    ap.add_argument("--outline", metavar="FILE")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--context", type=int, default=0)
    ap.add_argument("--home", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--where", action="store_true",
                    help="only where it is: '<label>: <file> lines A-B, proof lines C-D' "
                         "(for a brief that sends a reader to the lines, not the file)")
    a = ap.parse_args(argv)
    home, cfg = au.author_home(a.home or os.getcwd())
    if not home:
        if a.home and os.path.isdir(a.home):
            home, cfg = os.path.abspath(a.home), {}
        else:
            sys.stderr.write("statement: not in an Author home (give --home)\n")
            return 2
    if a.outline:
        path = a.outline if os.path.isabs(a.outline) else os.path.join(home, a.outline)
        if not os.path.isfile(path):
            sys.stderr.write("statement: no file %s\n" % a.outline)
            return 2
        o = outline(home, cfg, path)
        print(json.dumps(o, indent=1, ensure_ascii=False) if a.json else render_outline(o))
        return 0
    if not a.labels:
        sys.stderr.write("statement: give a label, or --outline FILE\n")
        return 2
    found, missed = [], []
    for lab in a.labels:
        lab = lab.split(":", 1)[1] if lab.startswith("paper:") else lab
        rec = find(home, cfg, lab, a.proof or a.where, a.context)
        (found if rec else missed).append(rec or lab)
    if a.where:
        for r in found:
            print(where_line(r))
    elif a.json:
        print(json.dumps({"found": found, "missing": missed}, indent=1, ensure_ascii=False))
    else:
        print("\n\n".join(render(r) for r in found))
    if missed:
        known = all_labels(home, cfg)
        for lab in missed:
            near = difflib.get_close_matches(lab, known, n=3, cutoff=0.6)
            sys.stderr.write("statement: no statement labelled %s%s\n" % (
                lab, " (near: %s)" % ", ".join(near) if near else ""))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
