"""handback.py -- record what a human read of a source no session could reach (#108).

A cite ticket whose source was unreachable (paywall, image-only scan, blocked host) is
parked on the human. The human hands back what they read, through
``/expert:cite --from-human <ticket> <file|text>``; this script puts it in the library,
where the card written from it (``read_from: human-supplied``) is checked by
``cards.py validate`` and ``library_verify_quote``:

``<key>.human.md`` is the register of the hand-backs (its format: the MCP library module,
"What a human supplied"); every record carries a sha256, checked whenever it is read:

* a **text** (the quoted statement, pasted) becomes one entry, verbatim between its
  marker lines, with the ticket, the date, the pinpoint and its digest. The workflow
  computes the digest from the human's own words and passes it as ``--expect``: a text
  that reached this script altered (an agent copied it) is refused and nothing is written;
* a **file** (a PDF or a page image, a path inside the workspace and outside the library)
  is copied into ``<key>.human/<date>-<ticket>-<name>``; a PDF's text layer is extracted
  beside it (``<name>.txt``, by ``pdftotext -layout``) when there is one; one record line
  names both, with the sha256 of each. The folder gets a ``.gitignore`` that keeps only the
  texts tracked: the files are personal copies, as the library's PDFs are.

Each record's id is its digest (printed as ``id``): the card written from it names it
(``cards.py new ... --handback <id>``). Recording the same text or file again changes
nothing (``already``).

    py handback.py record KEY --ticket T [--pinpoint P] --text-file F --expect HASH [--home H] [--json]
    py handback.py record KEY --ticket T [--pinpoint P] --file PATH [--home H] [--json]
    py handback.py show KEY [--home H] [--json]
    py handback.py hash --text-file F

The digest is ``sha256:<hex>`` of the text's UTF-8 bytes, its line ends made LF and the
blanks around it removed (cite.js computes the same in JavaScript).

Exit codes: 0 recorded (or already there), 1 refused, 2 usage error.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402

RE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
FILE_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".txt", ".md")
MARK = "<!-- hand-back"
GITIGNORE = ("# What a human supplied (handback.py): personal copies, never committed, as the\n"
             "# library's PDFs; the texts (pasted, or extracted from a PDF) stay tracked.\n"
             "*\n!.gitignore\n!*.txt\n!*.md\n")
HEADER = ("---\nkey: %s\nkind: human-supplied\n---\n\n# %s: read by a human\n\n"
          "The register of what a human with access to the source handed back for cite tickets\n"
          "(`handback.py record`): a text verbatim between its marker lines, a file of the folder\n"
          "beside this one, each with its sha256. Never edit a record: a new hand-back is a new\n"
          "record. A card quoting one says `read_from: human-supplied` and names it (`handback:`).\n")


# ----------------------------------------------------------------------------
# The library module (the register's one implementation) and the digest
# ----------------------------------------------------------------------------

def _lib():
    """The MCP library module, refused clearly when it predates the hand-back register."""
    lib = ex.library()
    if not all(hasattr(lib, n) for n in ("handback_records", "text_digest", "file_digest", "HUMAN_DIR")):
        raise SystemExit("handback: the academy base plugin at %s predates the hand-back register (#108; "
                         "library.handback_records is missing): update it, or set ACADEMY_ROOT to a checkout "
                         "that has it" % ex.academy_plugin())
    return lib


def normalise(text):
    return _lib().normalise_handback(text)


def text_hash(text):
    return _lib().text_digest(text)


# ----------------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------------

def _result(key, ticket, kind):
    return {"ok": False, "key": key, "ticket": ticket, "kind": kind, "id": None, "recorded": [],
            "texts": [], "already": False, "problems": [], "notes": []}


def _attr(v):
    v = re.sub(r"\s+", " ", str(v or "")).replace("--", "- -")
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _attrs(pairs):
    return " ".join('%s="%s"' % (k, _attr(v)) for k, v in pairs if v not in (None, ""))


def _append(home, key, entry):
    """Append one record to ``<key>.human.md`` (created with its header)."""
    lib = _lib()
    path = os.path.join(home, key + lib.HUMAN_MD)
    old = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            old = fh.read()
    body = (old.rstrip("\n") + "\n\n") if old.strip() else HEADER % (key, key) + "\n"
    ac.atomic_write(path, body + entry)


def _labels(home, key, rid):
    return [r["label"] for r in _lib().handback_records(home, key) if r["ok"] and r["id"] == rid and r["text"] is not None]


def record_text(home, key, ticket, text, expect=None, pinpoint=None, date=None):
    """One text entry of ``<key>.human.md``; refused when ``text`` does not hash to ``expect``."""
    r = _result(key, ticket, "text")
    if not RE_KEY.match(str(key or "")):
        r["problems"].append("%r is not a bibliography key" % key)
        return r
    lib = _lib()
    t = lib.normalise_handback(text)
    got = lib.text_digest(t)
    r["hash"] = got
    if not t:
        r["problems"].append("the text is empty")
    if MARK in t:
        r["problems"].append("the text holds a hand-back marker line (%s ...): not recordable" % MARK)
    if expect and got != expect:
        r["problems"].append("the text received differs from the text handed back (hash %s, expected %s): "
                             "write it again, byte for byte, and record it again" % (got, expect))
    if r["problems"]:
        return r
    r["id"] = got
    rel = key + lib.HUMAN_MD
    if any(x["ok"] and x["kind"] == "text" and x["id"] == got for x in lib.handback_records(home, key)):
        r.update(ok=True, already=True, recorded=[rel], texts=_labels(home, key, got))
        return r
    attrs = _attrs([("ticket", ticket), ("date", date or ac.today()), ("pinpoint", pinpoint), ("hash", got)])
    _append(home, key, "%s begin %s -->\n%s\n%s\n" % (MARK, attrs, t, lib.HANDBACK_END))
    r.update(ok=True, recorded=[rel], texts=_labels(home, key, got))
    return r


def extract_pdf(pdf, txt):
    """``pdftotext -layout``; True when it wrote a non-empty text, else no file is left."""
    exe = shutil.which("pdftotext")
    if not exe:
        return False
    try:
        subprocess.run([exe, "-layout", pdf, txt], capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        pass
    if os.path.isfile(txt):
        with open(txt, "r", encoding="utf-8", errors="replace") as fh:
            if fh.read().strip():
                return True
        os.remove(txt)
    return False


def allowed_roots(home):
    """The workspace root and every instance home (the library's own files excepted, below);
    the library home alone without a workspace."""
    ws = ex.load_workspace_or_none()
    roots = [home]
    if ws:
        if ws.get("_path"):
            roots.append(os.path.dirname(ws["_path"]))
        roots += [i.get("home") for i in (ws.get("instances") or {}).values() if i.get("home")]
    return [os.path.realpath(r) for r in roots if r]


def _under(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def record_file(home, key, ticket, path, pinpoint=None, date=None):
    """Copy ``path`` into ``<key>.human/`` and record it (and a PDF's text) with their sha256."""
    r = _result(key, ticket, "file")
    if not RE_KEY.match(str(key or "")):
        r["problems"].append("%r is not a bibliography key" % key)
        return r
    src = os.path.realpath(os.path.abspath(str(path or "")))     # a symlink is judged by its target
    ext = os.path.splitext(src)[1].lower()
    lib_home = os.path.realpath(home)
    if not os.path.isfile(src):
        r["problems"].append("no such file: %s" % path)
    elif _under(src, lib_home):
        r["problems"].append("%s is inside the library home (%s): its cached files, cards and records are not a "
                             "human's material; hand back a file from outside the library (the workspace's "
                             "scratch, say)" % (path, src))
    elif not any(_under(src, root) for root in allowed_roots(home) if root != lib_home):
        r["problems"].append("%s is outside the workspace and its homes (%s): put the file inside it" % (path, src))
    elif ext not in FILE_EXT:
        r["problems"].append("%s is not a PDF, an image or a text (%s)" % (path, ", ".join(FILE_EXT)))
    if r["problems"]:
        return r
    lib = _lib()
    dname = key + lib.HUMAN_DIR
    d = os.path.join(home, dname)
    sha = lib.file_digest(src)
    r["id"] = sha
    for x in lib.handback_records(home, key):
        if x["ok"] and x["kind"] == "file" and x["id"] == sha:
            r.update(ok=True, already=True, recorded=list(x["files"]), texts=[x["label"]] if x["text"] is not None else [])
            return r
    os.makedirs(d, exist_ok=True)
    gi = os.path.join(d, ".gitignore")
    if not os.path.isfile(gi):
        ac.atomic_write(gi, GITIGNORE)
    stem = "%s-%s-%s" % (date or ac.today(), ac.slugify(ticket, maxlen=20, default="ticket"),
                         ac.slugify(os.path.splitext(os.path.basename(src))[0], maxlen=40, default="file"))
    n, base = 2, stem
    while os.path.exists(os.path.join(d, stem + ext)) or os.path.exists(os.path.join(d, stem + ".txt")):
        stem = "%s-%d" % (base, n)
        n += 1
    name = stem + ext
    shutil.copyfile(src, os.path.join(d, name))
    rel = "%s/%s" % (dname, name)
    r["recorded"].append(rel)
    text_rel = text_sha = None
    if ext in lib.HUMAN_TEXT_EXT:
        text_rel, text_sha = rel, lib.file_digest(os.path.join(d, name))
    elif ext == ".pdf":
        txt = stem + ".txt"
        if extract_pdf(os.path.join(d, name), os.path.join(d, txt)):
            text_rel, text_sha = "%s/%s" % (dname, txt), lib.file_digest(os.path.join(d, txt))
            r["recorded"].append(text_rel)
        else:
            r["notes"].append("no text extracted from %s (no text layer, or no pdftotext): the card's "
                              "quote is transcribed from the pages, and the card says status unverified" % name)
    else:
        r["notes"].append("%s is an image: the card's quote is transcribed from it, and the card says status "
                          "unverified" % name)
    attrs = _attrs([("ticket", ticket), ("date", date or ac.today()), ("pinpoint", pinpoint), ("path", rel),
                    ("sha256", sha), ("text", text_rel), ("text_sha256", text_sha)])
    _append(home, key, "%s file %s -->\n" % (MARK, attrs))
    r["ok"] = True
    r["texts"] = _labels(home, key, sha)
    if pinpoint:
        r["pinpoint"] = pinpoint
    return r


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _home(args):
    home = ex.expert_home(home=args.home)
    if not home:
        raise SystemExit("handback: no library home (pass --home or add an expert instance)")
    return home


def _print(r, as_json):
    if as_json:
        print(json.dumps(r, ensure_ascii=False))
        return
    for p in r.get("recorded") or []:
        print(("already " if r.get("already") else "recorded ") + p)
    for t in r.get("texts") or []:
        print("text " + t)
    for n in r.get("notes") or []:
        print("note: " + n)
    for p in r.get("problems") or []:
        print("refused: " + p)


def cmd_record(args):
    if bool(args.text_file) == bool(args.file):
        sys.stderr.write("handback: give one of --text-file or --file\n")
        return 2
    if args.text_file and not args.expect:
        sys.stderr.write("handback: a text needs --expect <the hash of the text handed back>\n")
        return 2
    home = _home(args)
    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8", newline="") as fh:
            text = fh.read()
        r = record_text(home, args.key, args.ticket, text, expect=args.expect, pinpoint=args.pinpoint,
                        date=args.date)
    else:
        r = record_file(home, args.key, args.ticket, args.file, pinpoint=args.pinpoint, date=args.date)
    _print(r, args.json)
    return 0 if r["ok"] else 1


def cmd_show(args):
    home = _home(args)
    lib = _lib()
    recs = lib.handback_records(home, args.key)
    r = {"key": args.key, "files": lib.human_files(home, args.key),
         "records": [{"id": x["id"], "kind": x["kind"], "ok": x["ok"], "problem": x["problem"],
                      "label": x["label"], "ticket": x["attrs"].get("ticket")} for x in recs]}
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        for x in r["records"]:
            print("%s\t%s\t%s" % (x["id"], "ok" if x["ok"] else "BAD: " + x["problem"], x["label"]))
    return 0


def cmd_hash(args):
    with open(args.text_file, "r", encoding="utf-8", newline="") as fh:
        print(text_hash(fh.read()))
    return 0


def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("key")
    r.add_argument("--ticket", required=True)
    r.add_argument("--pinpoint")
    r.add_argument("--text-file")
    r.add_argument("--expect", help="the hash of the text as the human gave it (cite.js computes it)")
    r.add_argument("--file")
    r.add_argument("--date", help="YYYY-MM-DD (default today)")
    r.add_argument("--home")
    r.add_argument("--json", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("key")
    s.add_argument("--home")
    s.add_argument("--json", action="store_true")
    h = sub.add_parser("hash")
    h.add_argument("--text-file", required=True)
    args = ap.parse_args(argv)
    return {"record": cmd_record, "show": cmd_show, "hash": cmd_hash}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
