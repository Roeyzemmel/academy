"""agenda_migrate.py -- a legacy comment_roadmap.md -> agenda.md + roadmap.md (plan 4, 9.5).

    py agenda_migrate.py --roadmap OLD.md --out DIR [--paper-root HOME]
        [--statuses FILE.json | --claims-cmd "py ../<lab>/scripts/claims.py --repo ."]
        [--instance author@main] [--ns paper] [--date YYYY-MM-DD]

Writes ``DIR/agenda.md``, ``DIR/roadmap.md`` and ``DIR/migration-report.md``. Reads
only: the old roadmap, the paper sources (through check_paper's parser) and the
registry. It never writes into the home; the output is for Roey's review (plan 9b:
"paper roadmap -> agenda" is a review-gated step).

The agenda
----------
The paper's labelled statements in ``\\input`` order (check_paper.build_paper), one
entry per statement that has a registry record ``<ns>:<label>`` or is of a provable
environment, a conjecture or a definition. ``depends_on`` is the statement's
theorem references (statement and proof) that are themselves entries; commentary
environments (``rmk``, ``quest``) carry none, as in the checker's R1. ``required`` is
``conjectured`` for a conjecture or a claim now recorded as conjectured, and
``proved`` otherwise. ``status`` is the registry's (``missing`` when there is no
record, ``?`` when no registry was read). Without ``--paper-root`` the agenda is the
labels the live items mention, in order of first mention.

The roadmap
-----------
Only live work moves: every numbered item (``N. ...`` at column 0) of each ``## Tier``
section and every tagged bullet (``- **[tag]** ...``) of the other sections, whose
block carries no final ``**[done ...]**`` or ``[dropped ...]`` marker, plus one
``[verify]`` item per line of ``## Verification queue``. Each keeps its original text
verbatim as its body and its origin in ``source``. Tags map as: apply, write, lead,
verify (and any other new-vocabulary tag, e.g. ``notation``) as they are; a
``[verify]`` whose text names a pinpoint, ``sources.md`` or ``source-checker`` ->
``[cite]``; ``[needs Roey]`` (also inside ``[needs Roey / notation]``) -> status
``needs-human``, the tag coming from the rest of the brackets, else ``write``; a done marker qualified by "blocked", "in part", "partly",
"pending" or "except" is not done. The agenda entry is the first backticked label in
the item that is an agenda entry, else ``global``. Every such call is listed in the
report, which is what Roey reviews.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agenda_lib as al  # noqa: E402

LABEL_PREFIXES = ("thm", "prop", "lem", "cor", "conj", "defn", "fact", "ex", "rmk", "quest",
                  "claim", "exer", "exc", "problem", "case")
RE_LABEL_REF = re.compile(r"`((?:%s):[A-Za-z0-9:_\-]+)`" % "|".join(LABEL_PREFIXES))
RE_NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")
RE_TAGGED_BULLET = re.compile(r"^-\s+\*\*\[([^\]]+)\]\*\*\s*(.*)$")
RE_BOLD_TAG = re.compile(r"\*\*\[([^\]]+)\]\*\*")
RE_PLAIN_TAG = re.compile(r"\[(apply|write|verify|lead|needs Roey|dropped|done)[^\]]*\]")
RE_DONE_MARK = re.compile(r"\*\*\[(done|dropped)([^\]]*)\]\*\*", re.IGNORECASE)
RE_QUEUE_LINE = re.compile(r"^-\s+`([^`]+)`\s+—\s+(.*)$")
PARTIAL_WORDS = ("blocked", "in part", "partly", "pending", "except", "outcome pending")
CITE_WORDS = ("source-checker", "pinpoint", "/paper:cite", "sources.md", "cite ")
BASE_TAGS = ("apply", "write", "verify", "lead")


class Legacy(object):
    """One live item found in the old roadmap."""

    def __init__(self, section, number, first, lines):
        self.section = section
        self.number = number
        self.first = first
        self.lines = lines
        self.tag = None
        self.status = "open"
        self.calls = []

    @property
    def text(self):
        return "\n".join(self.lines)


# ----------------------------------------------------------------------------
# Reading the legacy roadmap
# ----------------------------------------------------------------------------

def sections(text):
    """[(title, [lines])] for every '## ' section."""
    out, cur, title = [], [], None
    for ln in text.replace("\r\n", "\n").split("\n"):
        if ln.startswith("## "):
            if title is not None:
                out.append((title, cur))
            title, cur = ln[3:].strip(), []
        elif title is not None:
            cur.append(ln)
    if title is not None:
        out.append((title, cur))
    return out


def section_name(title):
    """'Tier 5b — Roey's replies ... **[...]**' -> 'Tier 5b'; others unchanged (short)."""
    m = re.match(r"^(Tier\s+\S+)", title)
    if m:
        return m.group(1)
    return re.sub(r"\s*\*\*\[.*$", "", title).strip()


def blocks(lines, numbered):
    """Split a section's lines into item blocks: (number|None, first line, lines)."""
    out, cur = [], None
    for ln in lines:
        m_num = RE_NUMBERED.match(ln) if numbered else None
        m_tag = RE_TAGGED_BULLET.match(ln)
        if m_num or m_tag:
            if cur:
                out.append(cur)
            cur = [m_num.group(1) if m_num else None, ln, [ln]]
            continue
        if cur is None:
            continue
        if ln.strip() and not ln[:1].isspace():
            out.append(cur)            # a column-0 line that is not an item ends it
            cur = None
            continue
        cur[2].append(ln)
    if cur:
        out.append(cur)
    for b in out:
        while b[2] and not b[2][-1].strip():
            b[2].pop()
    return out


def classify(item):
    """Set item.tag and item.status from its markers; record the calls made."""
    first = item.first
    tags = RE_BOLD_TAG.findall(first) or RE_PLAIN_TAG.findall(first)
    tagtxt = [t.strip() for t in tags]
    status = "open"
    tag = None
    for t in tagtxt:
        low = t.lower()
        if low.startswith("done") or low.startswith("dropped"):
            continue
        for part in re.split(r"\s*/\s*", low):
            if part.startswith("needs roey"):
                status = "needs-human"
                continue
            word = re.split(r"[,\s]", part.strip(), 1)[0]
            if word in al.TAGS and tag is None:
                tag = word
                if "optional" in part:
                    item.calls.append("tag [%s] marked optional; priority set low" % t)
    marks = RE_DONE_MARK.findall(item.text)
    if marks:
        kind, rest = marks[-1]
        kind = kind.lower()
        qualified = any(w in rest.lower() for w in PARTIAL_WORDS)
        if kind == "dropped":
            status = "dropped"
        elif qualified:
            item.calls.append("done marker qualified (%r): kept open" % ("[done" + rest + "]"))
        else:
            status = "done"
    if tag is None:
        tag = "write"
        if status in ("open", "needs-human"):
            item.calls.append("no apply/write/verify/lead tag on the first line: tagged "
                              "[write]")
    low_text = item.text.lower()
    if tag == "verify" and any(w in low_text for w in CITE_WORDS):
        tag = "cite"
        item.calls.append("[verify] of a source (mentions a pinpoint, sources.md or "
                          "source-checker): tagged [cite]")
    item.tag, item.status = tag, status
    return item


def read_legacy(text):
    """(live items, counts) from a legacy roadmap's text."""
    live, counts = [], {"done": 0, "dropped": 0, "open": 0, "needs-human": 0, "queue": 0}
    for title, lines in sections(text):
        name = section_name(title)
        if title.lower().startswith("verification queue"):
            for ln in lines:
                m = RE_QUEUE_LINE.match(ln)
                if not m:
                    if ln.startswith("- `"):
                        it = Legacy(name, None, ln, [ln])
                        it.tag, it.status = "verify", "open"
                        it.calls.append("queue line not in the '`label` — `file` — why' "
                                        "shape; kept verbatim")
                        live.append(it)
                        counts["queue"] += 1
                    continue
                it = Legacy(name, None, ln, [ln])
                it.tag, it.status = "verify", "open"
                it.queue_label = m.group(1)
                live.append(it)
                counts["queue"] += 1
            continue
        numbered = title.lower().startswith("tier")
        for number, first, blines in blocks(lines, numbered):
            it = classify(Legacy(name, number, first, blines))
            counts[it.status] = counts.get(it.status, 0) + 1
            if it.status in ("done", "dropped"):
                continue
            live.append(it)
    return live, counts


def item_title(it):
    s = it.first
    s = RE_NUMBERED.sub(r"\2", s) if RE_NUMBERED.match(s) else s
    s = re.sub(r"^-\s+", "", s)
    s = RE_BOLD_TAG.sub("", s)
    s = RE_PLAIN_TAG.sub("", s)
    s = s.replace("**", "").strip(" .:—-")
    if getattr(it, "queue_label", None):
        return "Verify %s" % it.queue_label
    s = " ".join(s.split())
    if len(s) > 90:
        cut = s[:90]
        s = cut[:cut.rfind(" ")] + " ..." if " " in cut else cut + "..."
    return s or "(untitled)"


def dedent(lines):
    ind = [len(l) - len(l.lstrip(" ")) for l in lines[1:] if l.strip()]
    k = min(ind) if ind else 0
    return "\n".join([lines[0]] + [l[k:] if len(l) >= k else l.strip() for l in lines[1:]])


# ----------------------------------------------------------------------------
# The agenda
# ----------------------------------------------------------------------------

def registry_statuses(cmd, cwd):
    argv = shlex.split(cmd, posix=False)
    if argv and argv[0].lower() in ("py", "python", "python3"):
        argv = [sys.executable] + argv[1:]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.run(argv + ["sql", "select id, status from claims"], cwd=cwd,
                       capture_output=True, timeout=120, env=env)
    if p.returncode != 0:
        raise SystemExit("claims command exited %d: %s" % (
            p.returncode, p.stderr.decode("utf-8", "replace")[:300]))
    out = {}
    for ln in p.stdout.decode("utf-8", "replace").splitlines()[1:]:
        parts = [x.strip() for x in ln.split(" | ")]
        if len(parts) == 2 and parts[0]:
            out[parts[0]] = parts[1]
    return out


def paper_entries(root, ns, instance, statuses):
    """Agenda entries from the paper's statements, in \\input order."""
    import check_paper as cp
    block, _note = cp.load_author_block(cp.find_config(root))
    cp.configure(block)
    paper = cp.build_paper(root)
    keep = set(cp.PROVABLE_ENVS) | {"conj", "defn"}
    chosen = []
    seen = set()
    for st in paper.statements:
        if st.label == "(unlabelled)" or st.label in seen:
            continue
        cid = "%s:%s" % (ns, st.label)
        if cid not in statuses and st.env not in keep:
            continue
        seen.add(st.label)
        chosen.append(st)
    labels = {s.label for s in chosen}
    entries = []
    for st in chosen:
        cid = "%s:%s" % (ns, st.label)
        cur = statuses.get(cid, "missing" if statuses else "?")
        required = "conjectured" if (st.env == "conj" or cur == "conjectured") else "proved"
        if cur in al.FALSE_STATUSES:
            required = cur
        deps = [] if st.env in cp.COMMENTARY_ENVS else [u for u in st.uses if u in labels]
        entries.append(al.Entry(st.label, cid, required, deps, instance, cur))
    return entries


def attach(it, agenda, ns):
    """(agenda ref, note) for a live item."""
    if getattr(it, "queue_label", None):
        e = agenda.lookup(it.queue_label, ns)
        if e is not None:
            return e.claim if e.claim != "-" else "%s:%s" % (ns, e.label), None
        return "global", "queue label %s is not an agenda entry" % it.queue_label
    for lab in RE_LABEL_REF.findall(it.text):
        e = agenda.lookup(lab, ns)
        if e is not None:
            return e.claim if e.claim != "-" else "%s:%s" % (ns, e.label), None
    return "global", None


def migrate(legacy_text, instance, ns, paper_root=None, statuses=None, date=""):
    statuses = statuses or {}
    live, counts = read_legacy(legacy_text)
    if paper_root:
        entries = paper_entries(paper_root, ns, instance, statuses)
    else:
        entries, seen = [], set()
        for it in live:
            for lab in RE_LABEL_REF.findall(it.text):
                if lab not in seen:
                    seen.add(lab)
                    cid = "%s:%s" % (ns, lab)
                    entries.append(al.Entry(lab, cid, "proved", [], instance,
                                            statuses.get(cid, "?")))
    for n, e in enumerate(entries, 1):
        e.position = n
    agenda = al.Agenda("Agenda: " + instance, "", entries, "")
    items, report_rows = [], []
    for n, it in enumerate(live, 1):
        ref, note = attach(it, agenda, ns)
        if note:
            it.calls.append(note)
        src = it.section + (" item %s" % it.number if it.number else "")
        if getattr(it, "queue_label", None):
            src = "Verification queue: %s" % it.queue_label
        fields = {"status": it.status, "agenda": ref,
                  "priority": "low" if any("optional" in c for c in it.calls) else "normal",
                  "depends_on": "[]", "source": "comment_roadmap.md, " + src}
        if date:
            fields["created"] = date
        low = it.text.lower()
        if it.tag == "write" and ("figure-maker" in low or "illustration" in low):
            fields["route"] = "figure-maker"
            it.calls.append("illustration: route figure-maker")
        iid = "R-%04d" % n
        items.append(al.Item(iid, it.tag, item_title(it), fields, dedent(it.lines)))
        report_rows.append((iid, it.tag, it.status, ref, src, it.calls))
    agenda_text = al.new_agenda_text(instance, entries)
    roadmap_text = al.new_roadmap_text(
        instance, items,
        preface="Migrated %sfrom `Drafts/comment_roadmap.md` by agenda_migrate.py; the "
                "old file stays as the record of the settled tiers. Each item keeps its "
                "original text; `source` says where it came from." % (
                    ("on %s " % date) if date else ""))
    return agenda_text, roadmap_text, items, entries, counts, report_rows


def report(items, entries, counts, rows, legacy_path, paper_root, statuses_src):
    by_tag, by_status, global_n = {}, {}, 0
    for it in items:
        by_tag[it.tag] = by_tag.get(it.tag, 0) + 1
        by_status[it.status] = by_status.get(it.status, 0) + 1
        global_n += it.agenda == "global"
    missing = [e.label for e in entries if e.status == "missing"]
    out = ["# Agenda migration report", "",
           "Source: `%s`. Paper: `%s`. Statuses: %s." % (
               legacy_path, paper_root or "(none)", statuses_src), "",
           "## Counts", "",
           "- Agenda entries: %d (%d below their required status; %d with no registry "
           "record)." % (len(entries), sum(1 for e in entries if not e.done), len(missing)),
           "- Legacy items read: done %d, dropped %d, open %d, needs-human %d; "
           "verification-queue lines %d." % (counts.get("done", 0), counts.get("dropped", 0),
                                              counts.get("open", 0),
                                              counts.get("needs-human", 0),
                                              counts.get("queue", 0)),
           "- Roadmap items written: %d (by tag: %s; by status: %s); %d attached to "
           "`global`." % (len(items), ", ".join("%s %d" % kv for kv in sorted(by_tag.items())),
                          ", ".join("%s %d" % kv for kv in sorted(by_status.items())),
                          global_n), "",
           "## Items", "", "| id | tag | status | agenda | source | calls |",
           "|---|---|---|---|---|---|"]
    for iid, tag, st, ref, src, calls in rows:
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            iid, tag, st, ref, src.replace("|", "/"),
            "; ".join(c.replace("|", "/") for c in calls) or "-"))
    out += ["", "## Judgement calls for review", "",
            "- Only live items moved; done and dropped items stay in the old roadmap and "
            "its archive, which remain the record.",
            "- Item dependencies (\"issue 2 needs issue 1\", \"verify after X\") were "
            "not parsed from prose: every `depends_on` is `[]`. A `[verify]` item still "
            "waits for its entry's inputs through the agenda (inbox.py).",
            "- Every entry that is not a conjecture has `required: proved`; lower it (to "
            "`sketch`) for results the paper will state as sketches, or set milestones.",
            "- Agenda membership: a labelled statement with a registry record, or of a "
            "provable environment, a conjecture or a definition.",
            "- Priorities are all `normal` (optional items `low`): tier order is replaced "
            "by agenda position."]
    if missing:
        out += ["", "## Entries with no registry record", "",
                ", ".join("`%s`" % m for m in missing)]
    return "\n".join(out) + "\n"


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="Legacy comment_roadmap.md -> agenda + roadmap.")
    p.add_argument("--roadmap", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--paper-root", default=None)
    p.add_argument("--statuses", default=None)
    p.add_argument("--claims-cmd", default=None)
    p.add_argument("--claims-cwd", default=None)
    p.add_argument("--instance", default="author@main")
    p.add_argument("--ns", default="paper")
    p.add_argument("--date", default="")
    a = p.parse_args(argv)
    statuses, src = {}, "none read"
    if a.statuses:
        with open(a.statuses, "r", encoding="utf-8") as fh:
            statuses = json.load(fh)
        src = "`%s`" % a.statuses
    elif a.claims_cmd:
        statuses = registry_statuses(a.claims_cmd, a.claims_cwd or a.paper_root or ".")
        src = "`%s sql ...`" % a.claims_cmd
    legacy = al.read_text(a.roadmap)
    agenda_text, roadmap_text, items, entries, counts, rows = migrate(
        legacy, a.instance, a.ns, a.paper_root, statuses, a.date)
    os.makedirs(a.out, exist_ok=True)
    al.write_text(os.path.join(a.out, "agenda.md"), agenda_text)
    al.write_text(os.path.join(a.out, "roadmap.md"), roadmap_text)
    al.write_text(os.path.join(a.out, "migration-report.md"),
                  report(items, entries, counts, rows, a.roadmap, a.paper_root, src))
    print("agenda: %d entries; roadmap: %d items; written to %s" % (
        len(entries), len(items), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
