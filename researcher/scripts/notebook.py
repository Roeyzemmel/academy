"""notebook.py -- the Researcher notebook: objects, directions, proof attempts, journal.

Plan section 3.3. Deterministic bookkeeping for the skills; it never sets a status above
the unsettled ones (open, conjectured, sketch): that is claim-keeper's, through
``claims_set_status``.

Usage (from a Researcher home, or with --home):

    py notebook.py ls [--kind K] [--status S] [--json]
    py notebook.py direction ID [--json]            the direction's items with their status
    py notebook.py next ID [--n N] [--json]         the next unsettled items to explore
    py notebook.py new KIND ID --title T [--statement S] [--status S] [--bears-on a,b]
                       [--depends-on a,b] [--falsifier F] [--tags a,b] [--domain D] [--by WHO]
    py notebook.py attempt ID [--create] [--by WHO]  path of the next proof attempt
    py notebook.py journal [--date YYYY-MM-DD] [--create]
    py notebook.py scaffold HOME [--dry-run]         copy templates/notebook into a home
    py notebook.py status [--json]                   counts, attempts, reviews waiting

Ids: an object's file is ``objects/<kind>/<id>.md``; a reference ``<ns>:<id>`` is accepted
wherever an id is, and the namespace is dropped when it is this instance's.

Before a home's switch-over (schema v2, plan section 6, phase R6) the objects may still
live in the legacy folders (``claims/``, ``assumptions/``, ``examples/``); ``ls``,
``direction`` and ``status`` read those too, read-only.

Exit codes: 0 success, 1 nothing found, 2 error.
"""

import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402

SCAFFOLD = os.path.join(rs.TEMPLATES, "notebook")
TEMPLATE_DIR = os.path.join(SCAFFOLD, "_templates")
RE_REF = re.compile(r"`?\b(?:([a-z0-9]+):)?([A-Za-z][A-Za-z0-9._-]*(?::[A-Za-z0-9._-]+)*)`?")
DIRECTION_SECTIONS = ("Questions", "Candidate claims", "Falsifiers", "Next steps")
EXPLORE_SECTIONS = ("Questions", "Candidate claims")


class Notebook(object):
    def __init__(self, home):
        home_, cfg, inst = rs.researcher_home(home)
        if not home_:
            raise ac.AcademyError("not in a Researcher home (give --home)")
        self.home, self.cfg, self.instance = home_, cfg, inst
        self.paths = rs.notebook_paths(home_, cfg)
        ws = rs.workspace_or_none()
        winst = (ws or {}).get("instances", {}).get(inst or "", {})
        self.ns = (cfg or {}).get("ns") or winst.get("ns") or ""
        doms = (cfg or {}).get("domains") or winst.get("domains") or [""]
        self.domain = doms[0]
        self.budget = ((cfg or {}).get("budget") or {}).get("itemsPerRun", 3)

    # -- ids ---------------------------------------------------------------
    def bare(self, ref):
        ref = str(ref).strip().strip("`")
        ns, sep, rest = ref.partition(":")
        if sep and ns == self.ns:
            return rest
        return ref

    def ref(self, oid):
        return "%s:%s" % (self.ns, oid) if self.ns else oid

    # -- objects -----------------------------------------------------------
    def object_files(self):
        """[(kind_folder, path)] for every object file, new layout first, then legacy."""
        out = []
        objs = self.paths["objects"]
        if os.path.isdir(objs):
            for kind in sorted(os.listdir(objs)):
                d = os.path.join(objs, kind)
                if not os.path.isdir(d):
                    continue
                for f in sorted(os.listdir(d)):
                    if f.endswith(".md") and not f.startswith("_") and f not in rs.NOT_RECORDS:
                        out.append((kind, os.path.join(d, f)))
        for legacy in ("claims", "assumptions", "examples"):
            d = os.path.join(self.home, legacy)
            if os.path.isdir(d) and os.path.abspath(d) != os.path.abspath(objs):
                for f in sorted(os.listdir(d)):
                    if f.endswith(".md") and not f.startswith("_") and f not in rs.NOT_RECORDS:
                        out.append((legacy, os.path.join(d, f)))
        return out

    def read_object(self, path, folder=None):
        text = rs.read_text(path) or ""
        get = lambda k: rs.frontmatter_field(text, k)[1]  # noqa: E731
        oid = get("id") or os.path.splitext(os.path.basename(path))[0]
        return {"id": oid, "ref": self.ref(oid), "kind": get("kind") or folder,
                "status": get("status"), "title": get("title"),
                "lifecycle": get("lifecycle") or "active", "proof": get("proof"),
                "path": path.replace("\\", "/")}

    def objects(self, kind=None, status=None):
        out = []
        for folder, path in self.object_files():
            o = self.read_object(path, folder)
            if kind and o["kind"] != kind:
                continue
            if status and (o["status"] or "").lower() != status.lower():
                continue
            out.append(o)
        return out

    def find(self, ref):
        oid = self.bare(ref)
        for folder, path in self.object_files():
            if os.path.splitext(os.path.basename(path))[0] == oid:
                return self.read_object(path, folder)
        return None

    # -- directions --------------------------------------------------------
    def direction(self, ref):
        d = self.find(ref)
        if not d or d["kind"] != "direction":
            raise ac.AcademyError("no direction object %s" % ref)
        text = rs.read_text(d["path"]) or ""
        items, section = [], None
        in_comment = False
        for ln in text.replace("\r\n", "\n").split("\n"):
            s = ln.strip()
            if "<!--" in s and "-->" not in s:
                in_comment = True
                continue
            if in_comment:
                if "-->" in s:
                    in_comment = False
                continue
            if s.startswith("## "):
                section = s[3:].strip()
                continue
            if section in DIRECTION_SECTIONS and s.startswith(("- ", "* ")):
                body = s[2:].strip()
                m = RE_REF.match(body)
                if not m:
                    continue
                ns, oid = m.group(1), m.group(2)
                if ns and ns != self.ns:
                    ref_ = "%s:%s" % (ns, oid)
                    obj = None
                else:
                    ref_ = self.ref(oid)
                    obj = self.find(oid)
                text_ = body[m.end():].strip(" -—:")
                items.append({"section": section, "ref": ref_, "text": text_,
                              "exists": obj is not None or bool(ns and ns != self.ns),
                              "kind": obj and obj["kind"], "status": obj and obj["status"],
                              "lifecycle": obj and obj["lifecycle"]})
        return d, items

    def next_items(self, ref, n=None):
        """The first ``n`` unsettled question / candidate-claim items of a direction."""
        n = min(n or self.budget, self.budget, 3)
        _, items = self.direction(ref)
        out = []
        for it in items:
            if it["section"] not in EXPLORE_SECTIONS:
                continue
            if it["lifecycle"] and it["lifecycle"] != "active":
                continue
            st = (it["status"] or "").lower()
            if it["exists"] and st and st not in rs.UNSETTLED:
                continue
            out.append(it)
            if len(out) >= n:
                break
        return out

    # -- writing -----------------------------------------------------------
    def _render(self, name, values):
        with open(os.path.join(TEMPLATE_DIR, name), "r", encoding="utf-8") as fh:
            text = fh.read()
        for k, v in values.items():
            text = text.replace("{{%s}}" % k, v)
        return text

    def new_object(self, kind, oid, title, statement="", status=None, bears_on=(),
                   depends_on=(), falsifier="", tags=(), domain=None, by="researcher"):
        if kind not in rs.OBJECT_KINDS:
            raise ac.AcademyError("kind must be one of %s" % ", ".join(rs.OBJECT_KINDS))
        oid = self.bare(oid)
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", oid):
            raise ac.AcademyError("bad object id %r" % oid)
        if self.find(oid):
            raise ac.AcademyError("%s already exists" % self.ref(oid))
        if kind in rs.STATUS_KINDS:
            status = status or ("conjectured" if kind == "conjecture" else "open")
            if status not in ("open", "conjectured", "sketch"):
                raise ac.AcademyError("a new object starts unsettled (open, conjectured, "
                                      "sketch); %r is set only by claim-keeper" % status)
        elif status:
            raise ac.AcademyError("a %s carries no status" % kind)
        q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
        fmt_list = lambda xs: ", ".join(x for x in xs if x)  # noqa: E731
        vals = {"id": oid, "kind": kind, "title": q(title), "status": status or "",
                "statement": q(statement or ""), "statement_body": statement or "",
                "depends_on": fmt_list(depends_on), "bears_on": fmt_list(bears_on),
                "tags": fmt_list(tags), "domain": domain or self.domain,
                "date": ac.today(), "ns": self.ns, "falsifier": falsifier or "",
                "created": "created by %s" % by}
        if kind == "direction":
            text = self._render("direction.md", vals)
        else:
            text = self._render("object.md", vals)
            if kind not in rs.STATUS_KINDS:
                text = text.replace("status: \n", "", 1)
                text = text.replace('"%s |  | ' % vals["date"], '"%s | | ' % vals["date"], 1)
            if not falsifier:
                text = text.replace("## Falsifier\n\n\n\n", "", 1)
        path = os.path.join(self.paths["objects"], kind, oid + ".md")
        ac.atomic_write(path, text)
        return path

    def attempt_path(self, ref, create=False, by="prover"):
        oid = self.bare(ref)
        d = os.path.join(self.paths["proofs"], oid)
        n = 1
        if os.path.isdir(d):
            nums = [int(m.group(1)) for f in os.listdir(d)
                    for m in [re.match(r"^attempt-(\d+)\.md$", f)] if m]
            n = max(nums) + 1 if nums else 1
        path = os.path.join(d, "attempt-%d.md" % n)
        if create:
            ac.atomic_write(path, self._render("attempt.md", {
                "ref": self.ref(oid), "n": str(n), "by": by, "date": ac.today()}))
        return path, n

    def journal_path(self, date=None, create=False):
        date = date or ac.today()
        if not ac.RE_DATE.match(date):
            raise ac.AcademyError("date must be YYYY-MM-DD")
        path = os.path.join(self.paths["journal"], date + ".md")
        if create and not os.path.exists(path):
            ac.atomic_write(path, self._render("journal.md", {"date": date}))
        return path

    def status(self):
        counts = {}
        for o in self.objects():
            key = (o["kind"] or "?", o["status"] or "-")
            counts[key] = counts.get(key, 0) + 1
        attempts = {}
        if os.path.isdir(self.paths["proofs"]):
            for oid in sorted(os.listdir(self.paths["proofs"])):
                d = os.path.join(self.paths["proofs"], oid)
                if os.path.isdir(d):
                    files = sorted(f for f in os.listdir(d) if f.startswith("attempt-"))
                    if files:
                        last = rs.read_text(os.path.join(d, files[-1])) or ""
                        attempts[oid] = {"attempts": len(files),
                                         "latest": rs.frontmatter_field(last, "outcome")[1]}
        import reviews  # local: reviews imports this module's siblings only
        waiting = reviews.pending(self.paths["audits"])
        return {"instance": self.instance, "home": self.home,
                "objects": [{"kind": k, "status": s, "count": c}
                            for (k, s), c in sorted(counts.items())],
                "attempts": attempts, "reviews_waiting_for_B": waiting}


def scaffold(home, dry_run=False):
    """Copy templates/notebook into ``home`` (never overwriting; ``_templates`` stays in
    the plugin). Returns the list of files created (or that would be)."""
    made = []
    for dirpath, dirnames, filenames in os.walk(SCAFFOLD):
        dirnames[:] = [d for d in dirnames if d != "_templates"]
        rel = os.path.relpath(dirpath, SCAFFOLD)
        for f in filenames:
            dst = os.path.normpath(os.path.join(home, rel, f))
            if os.path.exists(dst):
                continue
            made.append(dst.replace("\\", "/"))
            if not dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(os.path.join(dirpath, f), dst)
    return made


def _csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ls"); p.add_argument("--kind"); p.add_argument("--status")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("direction"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("next"); p.add_argument("id"); p.add_argument("--n", type=int)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("new"); p.add_argument("kind"); p.add_argument("id")
    p.add_argument("--title", required=True); p.add_argument("--statement", default="")
    p.add_argument("--status"); p.add_argument("--bears-on"); p.add_argument("--depends-on")
    p.add_argument("--falsifier", default=""); p.add_argument("--tags")
    p.add_argument("--domain"); p.add_argument("--by", default="researcher")
    p = sub.add_parser("attempt"); p.add_argument("id"); p.add_argument("--create", action="store_true")
    p.add_argument("--by", default="prover")
    p = sub.add_parser("journal"); p.add_argument("--date"); p.add_argument("--create", action="store_true")
    p = sub.add_parser("scaffold"); p.add_argument("target"); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("status"); p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "scaffold":
            made = scaffold(os.path.abspath(args.target), args.dry_run)
            print("%s %d file(s)" % ("would create" if args.dry_run else "created", len(made)))
            for m in made:
                print("  " + m)
            return 0
        nb = Notebook(args.home or os.getcwd())
        if args.cmd == "ls":
            objs = nb.objects(args.kind, args.status)
            if args.json:
                print(json.dumps(objs, ensure_ascii=False, indent=1))
            else:
                for o in objs:
                    print("%-28s %-11s %-18s %s" % (o["ref"], o["kind"] or "?",
                                                    o["status"] or "-", o["title"] or ""))
            return 0 if objs else 1
        if args.cmd == "direction":
            d, items = nb.direction(args.id)
            if args.json:
                print(json.dumps({"direction": d, "items": items}, ensure_ascii=False, indent=1))
            else:
                print("%s  %s" % (d["ref"], d["title"] or ""))
                for it in items:
                    print("  [%s] %-24s %-12s %s" % (it["section"], it["ref"],
                                                     it["status"] or ("-" if it["exists"]
                                                                      else "(no object)"),
                                                     it["text"]))
            return 0
        if args.cmd == "next":
            items = nb.next_items(args.id, args.n)
            if args.json:
                print(json.dumps(items, ensure_ascii=False, indent=1))
            else:
                for it in items:
                    print("%-24s %-12s %s" % (it["ref"], it["status"] or
                                              ("-" if it["exists"] else "(no object)"), it["text"]))
                if not items:
                    print("(nothing unsettled left in %s)" % args.id)
            return 0 if items else 1
        if args.cmd == "new":
            path = nb.new_object(args.kind, args.id, args.title, args.statement, args.status,
                                 _csv(args.bears_on), _csv(args.depends_on), args.falsifier,
                                 _csv(args.tags), args.domain, args.by)
            print(path.replace("\\", "/"))
            return 0
        if args.cmd == "attempt":
            path, n = nb.attempt_path(args.id, args.create, args.by)
            print(path.replace("\\", "/"))
            return 0
        if args.cmd == "journal":
            print(nb.journal_path(args.date, args.create).replace("\\", "/"))
            return 0
        if args.cmd == "status":
            st = nb.status()
            if args.json:
                print(json.dumps(st, ensure_ascii=False, indent=1))
            else:
                print("%s (%s)" % (st["instance"], st["home"]))
                for row in st["objects"]:
                    print("  %-11s %-18s %d" % (row["kind"], row["status"], row["count"]))
                for oid, a in st["attempts"].items():
                    print("  proof %s: %d attempt(s), latest %s" % (oid, a["attempts"], a["latest"]))
                print("  reviews waiting for run B: %s" % (", ".join(st["reviews_waiting_for_B"])
                                                          or "none"))
            return 0
    except (ac.AcademyError, OSError) as exc:
        sys.stderr.write("notebook.py: %s\n" % exc)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
