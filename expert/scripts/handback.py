"""handback.py -- record what a human read of a source no session could reach (#108).

A cite ticket whose source was unreachable (paywall, image-only scan, blocked host) is
parked on the human. The human hands back what they read, through
``/expert:cite --from-human <ticket> <file|text>``; this script puts it in the library,
where the card written from it (``read_from: human-supplied``) is checked by
``cards.py validate`` and ``library_verify_quote``:

* a **text** (the quoted statement, pasted) becomes one entry of ``<key>.human.md``,
  verbatim between its marker lines, with the ticket, the date and the pinpoint. The
  workflow computes the text's hash from the human's own words and passes it as
  ``--expect``: a text that reached this script altered (an agent copied it) is refused
  and nothing is written;
* a **file** (a PDF or a page image, a path inside the workspace) is copied into
  ``<key>.human/<date>-<ticket>-<name>``; a PDF's text layer is extracted beside it
  (``<name>.txt``, by ``pdftotext -layout``) when there is one. The folder gets a
  ``.gitignore`` that keeps only the texts tracked: the files are personal copies, as the
  library's PDFs are.

Recording the same text or file again changes nothing (``already``).

    py handback.py record KEY --ticket T [--pinpoint P] --text-file F --expect HASH [--home H] [--json]
    py handback.py record KEY --ticket T [--pinpoint P] --file PATH [--home H] [--json]
    py handback.py show KEY [--home H] [--json]
    py handback.py hash --text-file F

The hash is ``fnv1a32:<8 hex>:<UTF-8 bytes>`` of the text with its line ends made LF and
the blanks around it removed (cite.js computes the same in JavaScript).

Exit codes: 0 recorded (or already there), 1 refused, 2 usage error.
"""

import argparse
import hashlib
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
          "Each entry is what a human with access to the source handed back for a cite ticket,\n"
          "verbatim between its marker lines (`handback.py record`). Never edit an entry: a new\n"
          "hand-back is a new entry. A card quoting one says `read_from: human-supplied`.\n")


# ----------------------------------------------------------------------------
# The hash (the same in cite.js)
# ----------------------------------------------------------------------------

def normalise(text):
    """LF line ends, the blanks around the text removed (only spaces, tabs, newlines)."""
    return str(text).replace("\r\n", "\n").replace("\r", "\n").strip(" \t\n")


def text_hash(text):
    data = normalise(text).encode("utf-8", "surrogatepass")
    h = 0x811c9dc5
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return "fnv1a32:%08x:%d" % (h, len(data))


# ----------------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------------

def _result(key, ticket, kind):
    return {"ok": False, "key": key, "ticket": ticket, "kind": kind, "recorded": [], "texts": [],
            "already": False, "problems": [], "notes": []}


def _attr(v):
    v = re.sub(r"\s+", " ", str(v or "")).replace("--", "- -")
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _texts(home, key, rel_prefix):
    return [label for label, _ in ex.library().human_texts(home, key) if label.startswith(rel_prefix)]


def record_text(home, key, ticket, text, expect=None, pinpoint=None, date=None):
    """One entry of ``<key>.human.md``; refused when ``text`` does not hash to ``expect``."""
    r = _result(key, ticket, "text")
    if not RE_KEY.match(str(key or "")):
        r["problems"].append("%r is not a bibliography key" % key)
        return r
    t = normalise(text)
    got = text_hash(t)
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
    lib = ex.library()
    path = os.path.join(home, key + lib.HUMAN_MD)
    rel = key + lib.HUMAN_MD
    old = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            old = fh.read()
    entries = lib.parse_handbacks(old)
    if any(normalise(e["text"]) == t for e in entries):
        r.update(ok=True, already=True, recorded=[rel])
        r["texts"] = _texts(home, key, rel)
        return r
    attrs = 'ticket="%s" date="%s"' % (_attr(ticket), _attr(date or ac.today()))
    if pinpoint:
        attrs += ' pinpoint="%s"' % _attr(pinpoint)
    attrs += ' hash="%s"' % got
    entry = "%s begin %s -->\n%s\n%s\n" % (MARK, attrs, t, lib.HANDBACK_END)
    body = (old.rstrip("\n") + "\n\n") if old.strip() else HEADER % (key, key) + "\n"
    ac.atomic_write(path, body + entry)
    r.update(ok=True, recorded=[rel])
    r["texts"] = _texts(home, key, rel)
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
    """The workspace root and every instance home; the library home alone without a workspace."""
    ws = ex.load_workspace_or_none()
    roots = [home]
    if ws:
        if ws.get("_path"):
            roots.append(os.path.dirname(ws["_path"]))
        roots += [i.get("home") for i in (ws.get("instances") or {}).values() if i.get("home")]
    return [os.path.realpath(r) for r in roots if r]


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def record_file(home, key, ticket, path, pinpoint=None, date=None):
    """Copy ``path`` into ``<key>.human/``; a PDF's text is extracted beside it."""
    r = _result(key, ticket, "file")
    if not RE_KEY.match(str(key or "")):
        r["problems"].append("%r is not a bibliography key" % key)
        return r
    src = os.path.realpath(os.path.abspath(str(path or "")))
    ext = os.path.splitext(src)[1].lower()
    if not os.path.isfile(src):
        r["problems"].append("no such file: %s" % path)
    elif not any(src == root or src.startswith(root + os.sep) for root in allowed_roots(home)):
        r["problems"].append("%s is outside the workspace and its homes: put the file inside it" % path)
    elif ext not in FILE_EXT:
        r["problems"].append("%s is not a PDF, an image or a text (%s)" % (path, ", ".join(FILE_EXT)))
    if r["problems"]:
        return r
    lib = ex.library()
    dname = key + lib.HUMAN_DIR
    d = os.path.join(home, dname)
    sha = _sha(src)
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            full = os.path.join(d, f)
            if not f.startswith(".") and os.path.isfile(full) and _sha(full) == sha:
                r.update(ok=True, already=True, recorded=["%s/%s" % (dname, f)])
                stem = os.path.splitext(f)[0]
                if os.path.isfile(os.path.join(d, stem + ".txt")) and not f.endswith(".txt"):
                    r["recorded"].append("%s/%s.txt" % (dname, stem))
                r["texts"] = [x for x in _texts(home, key, dname + "/")
                              if x.split(" ")[0] in r["recorded"]]
                return r
    os.makedirs(d, exist_ok=True)
    gi = os.path.join(d, ".gitignore")
    if not os.path.isfile(gi):
        ac.atomic_write(gi, GITIGNORE)
    stem = "%s-%s-%s" % (date or ac.today(), ac.slugify(ticket, maxlen=20, default="ticket"),
                         ac.slugify(os.path.splitext(os.path.basename(src))[0], maxlen=40, default="file"))
    name = stem + ext
    n = 2
    while os.path.exists(os.path.join(d, name)):
        name = "%s-%d%s" % (stem, n, ext)
        n += 1
    shutil.copyfile(src, os.path.join(d, name))
    r["recorded"].append("%s/%s" % (dname, name))
    if ext == ".pdf":
        txt = os.path.splitext(name)[0] + ".txt"
        if extract_pdf(os.path.join(d, name), os.path.join(d, txt)):
            r["recorded"].append("%s/%s" % (dname, txt))
        else:
            r["notes"].append("no text extracted from %s (no text layer, or no pdftotext): the card's "
                              "quote is transcribed from the pages and said unchecked" % name)
    elif ext not in lib.HUMAN_TEXT_EXT:
        r["notes"].append("%s is an image: the card's quote is transcribed from it and said unchecked" % name)
    r["ok"] = True
    r["texts"] = [x for x in _texts(home, key, dname + "/") if x.split(" ")[0] in r["recorded"]]
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
    lib = ex.library()
    r = {"key": args.key, "files": lib.human_files(home, args.key),
         "texts": [label for label, _ in lib.human_texts(home, args.key)]}
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        for f in r["files"]:
            print(f)
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
