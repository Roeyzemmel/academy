"""R2: requote a fsl-claims registry once, into the dialect, proven by data equality.

For every record of the repo's registry root (lab or paper):

1. read it with the OLD claims.py reader (``core.legacy_fm``): the data as the old
   tool saw it;
2. write the frontmatter again with the dialect's serializer (``fsl.serialize``: the
   canonical field order, block lists, ``[]``/``""`` for empty values, quotes where the
   dialect needs them), keeping the body byte for byte; the file is written LF (the
   registry directories are ``eol=lf`` in ``.gitattributes``);
3. read the result with the NEW parser (``fsl.parse_strict``) and compare, field by
   field and the body: the file is written only when the two are equal.

A value the old reader kept with its quotes (``title: "x"`` read as ``"x"``) keeps them
as data; such values are listed in the report for a human to judge, never changed here.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from .core import legacy_fm
from .profiles import fsl


def requote_text(text):
    """``(new_text, old_fields, old_body, new_fields, new_body)`` for one record."""
    lf = text.lstrip("﻿").replace("\r\n", "\n")
    old_fields, old_body = legacy_fm.parse(lf, fsl.LIST_FIELDS)
    lines = lf.split("\n")
    close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    new_text = "---\n" + fsl.serialize(old_fields) + "\n".join(lines[close:])
    new_fields, new_body = fsl.parse_strict(new_text)
    return new_text, old_fields, old_body, new_fields, new_body


def _quoted_literals(fields):
    out = []
    for k, v in fields.items():
        for x in (v if isinstance(v, list) else [v]):
            if len(x) >= 2 and x[0] == x[-1] and x[0] in "\"'":
                out.append((k, x))
    return out


def run(repo, write=False):
    """Requote the registry of ``repo``; returns the per-file rows for the report."""
    root = fsl.registry_root(repo)
    rows = []
    for p in sorted(root.rglob("*.md")):
        if p.name in ("INDEX.md", "README.md"):
            continue
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        row = {"file": p.relative_to(Path(repo)).as_posix(), "path": p}
        lf_text = text.lstrip("\ufeff").replace("\r\n", "\n")
        try:
            sf, sb = fsl.parse_strict(lf_text)
            lines = lf_text.split("\n")
            close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            canonical = "---\n" + fsl.serialize(sf) + "\n".join(lines[close:]) == lf_text
        except (ValueError, StopIteration):
            canonical = False
        if canonical:
            row.update(status="equal", fields=len(sf), list_items=sum(
                len(v) for v in sf.values() if isinstance(v, list)), equal=True, diffs=[],
                changed_text=False, crlf=b"\r\n" in raw, strict_before=True, quoted=[],
                canonical=True)
            if write and row["crlf"]:
                p.write_bytes(lf_text.encode("utf-8"))
                row["written"] = True
            rows.append(row)
            continue
        try:
            new_text, of, ob, nf, nb = requote_text(text)
        except ValueError as exc:
            row.update(status="unreadable", detail=str(exc))
            rows.append(row)
            continue
        diffs = []
        for k in sorted(set(of) | set(nf)):
            if of.get(k) != nf.get(k):
                diffs.append(f"{k}: old {of.get(k)!r} != new {nf.get(k)!r}")
        if ob != nb:
            diffs.append("body differs")
        try:
            strict_before = fsl.parse_strict(text)
            already = strict_before == (of, ob)
        except ValueError:
            already = False
        lf_before = text.lstrip("﻿").replace("\r\n", "\n")
        changed = new_text != lf_before
        row.update(fields=len(of), list_items=sum(len(v) for v in of.values()
                                                  if isinstance(v, list)),
                   equal=not diffs, diffs=diffs, changed_text=changed,
                   crlf=b"\r\n" in raw, strict_before=already,
                   quoted=_quoted_literals(of))
        row["status"] = "equal" if not diffs else "DIFFERENT"
        if write and not diffs and (changed or row["crlf"]):
            p.write_bytes(new_text.encode("utf-8"))
            row["written"] = True
        rows.append(row)
    return rows


def report(sections, when=None):
    """Markdown for ``[(title, repo, rows)]``."""
    when = when or datetime.date.today().isoformat()
    out = ["# R2 requote: data-equality report", "",
           f"Generated {when} by `py -m registry requote --write --report ...` "
           "(academy/registry/requote.py).", "",
           "Each record of the lab and paper registries was read with the OLD claims.py "
           "reader, its frontmatter written again with the dialect's serializer "
           "(kb.py's; canonical field order, block lists, `[]`/`\"\"` for empty values, "
           "quotes where needed; single quotes for values with a backslash), the body kept "
           "byte for byte, and the result read with the NEW parser. A file is written only "
           "when every field and the body are equal as data. Files are written LF.", ""]
    total = {"files": 0, "equal": 0, "diff": 0, "unreadable": 0, "written": 0,
             "fields": 0, "items": 0}
    for title, repo, rows in sections:
        for r in rows:
            total["files"] += 1
            total["equal"] += r["status"] == "equal"
            total["diff"] += r["status"] == "DIFFERENT"
            total["unreadable"] += r["status"] == "unreadable"
            total["written"] += bool(r.get("written"))
            total["fields"] += r.get("fields", 0)
            total["items"] += r.get("list_items", 0)
    out += ["## Summary", "",
            "| files | equal as data | different | unreadable | rewritten | fields compared "
            "| list items compared |", "|---|---|---|---|---|---|---|",
            f"| {total['files']} | {total['equal']} | {total['diff']} | {total['unreadable']} "
            f"| {total['written']} | {total['fields']} | {total['items']} |", ""]
    for title, repo, rows in sections:
        n_text = sum(1 for r in rows if r.get("changed_text"))
        n_strict = sum(1 for r in rows if r.get("strict_before"))
        out += [f"## {title}", "", f"Repo `{repo}`; {len(rows)} records; "
                f"{n_text} with a changed frontmatter text; {n_strict} already read the same "
                "by both parsers before requoting.", "",
                "| file | fields | list items | equal | frontmatter text changed | was CRLF |",
                "|---|---|---|---|---|---|"]
        for r in rows:
            out.append(f"| `{r['file']}` | {r.get('fields', '-')} | {r.get('list_items', '-')} "
                       f"| {'yes' if r['status'] == 'equal' else r['status']} "
                       f"| {'yes' if r.get('changed_text') else 'no'} "
                       f"| {'yes' if r.get('crlf') else 'no'} |")
        bad = [r for r in rows if r["status"] != "equal"]
        if bad:
            out += ["", "**Differences (these files were NOT written):**", ""]
            for r in bad:
                out.append(f"- `{r['file']}`: " + ("; ".join(r.get("diffs") or [])
                                                   or r.get("detail", "")))
        quoted = [(r["file"], k, v) for r in rows for k, v in r.get("quoted", [])]
        out += ["", "**Values the old reader kept with their quotes** (kept as data, "
                "so the quote characters are now part of the value; a human may want "
                "to drop them):", ""]
        out += [f"- `{f}` `{k}`: `{v}`" for f, k, v in quoted] or ["- none"]
        out.append("")
    return "\n".join(out)


def main(repo, write=False, report_path=None, report=None):
    report_path = report_path or report
    rows = run(Path(repo), write=write)
    bad = [r for r in rows if r["status"] != "equal"]
    for r in rows:
        flag = "written" if r.get("written") else ("changed" if r.get("changed_text") else "same")
        print(f"{r['status']:<10} {flag:<8} {r['file']}")
    print(f"{len(rows)} records: {len(rows) - len(bad)} equal as data, {len(bad)} not"
          + ("" if write else " (dry run: nothing written)"))
    if report_path:
        Path(report_path).write_text(globals()["report"]([("registry", str(repo), rows)]),
                                     encoding="utf-8", newline="\n")
    return 1 if bad else 0
