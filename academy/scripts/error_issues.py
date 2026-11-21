"""error_issues.py -- the error ledger's FAMILIES as GitHub issues (academy#95).

Used by ``error_ledger.py`` (``sync``, ``migrate``, and ``report`` / ``resolve`` / ``settle``
when workspace.json names ``errors.repo``); never by its hook, which stays offline.

**What may leave the machine (the human's decision of 2026-11-21).** The errors repo is
public, and no redaction of free text makes a message safe (claim labels, slugs, ids,
experiment names, bib keys, search terms and hosts leak through every blocklist). So an
issue carries only the coarse error *family* (``error_ledger.family_of``: the tool and the
reason, the target masked), and per occurrence only its time, the instance's ROLE (never
the instance), the coarse cause of a shell failure (a fixed vocabulary) and the code it
came from (``rev``, ``ver``). No message, detail, command, path, pattern, cwd, agent,
signature, session id, instance name, packet id or resolve note is posted; they stay in
the local spool and the private git ledger.

Two checks stand between a record and GitHub, and posting cannot skip either:

- ``public_family``: a family is posted as itself only if every token has an allowed
  shape (a word whose ``_``-parts are all in ``VOCAB``, a placeholder ``<n> <q> <path>
  <claim> <id> <host> <instance> <redacted>``, punctuation) and its tool is made of
  ``VOCAB`` words; otherwise as ``<tool>: (unlisted family <hash>)`` (the tool as
  ``unlisted`` when it fails too). ``VOCAB`` is a fixed list of generic words: a person's
  name, a slug or a search term is not in it, so a family carrying one is unlisted;
- ``Gate``: the only transport this module writes through. Every title, body, comment and
  label passes ``check_public`` (the same token rule over the whole text, plus dates,
  numbers, hex hashes and the comment markers) or raises ``Unsafe`` and nothing is sent.

One issue per family, labelled ``error-family``, found by the hidden marker ``<!--
family:<hash> -->`` (``hash``: the first 12 hex digits of the sha1 of the posted family).
The body is a table (tool, family, occurrences, first and last seen, the code of the last
one, roles) and the same fields as hidden JSON (``<!-- error-family {...} -->``). Each
sync adds one comment: the new count, the date span, counts by role and by cause, and the
occurrences as hidden rows ``[time, role, cause, rev, ver]`` (``<!-- occurrences [...]
-->``); a resolve or settle adds ``<!-- resolves [...] -->`` rows ``{at, by, commit,
version}``, so ``records_of`` rebuilds the records ``error_ledger.report`` reads (one
"class" per family; with no session id, sessions count as one).

A closed issue that recurs is reopened: with label ``regression`` when its last resolve
named a fix (commit or version), or ``stale-code`` when every new error came from code
older than that fix (``error_ledger.has_fix``). The spool's cursor (``cursor.json`` in the
spool directory) holds a byte offset per spool file, so a record is posted once; a sync
that fails part-way records the batch and the families already posted (``partial``), and
the next sync finishes that batch first without posting those again.

The transport is ``board_gh.GhTransport`` (``gh api`` through a subprocess; its ``run``
is injectable, and the tests pass a fake GitHub), always wrapped in ``Gate``.
"""

import collections
import datetime as _dt
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

import error_ledger as el  # noqa: E402
from board_gh import GhError, GhTransport  # noqa: E402,F401

LABEL = "error-family"
REGRESSION = "regression"
STALE = "stale-code"
TAGS = (REGRESSION, STALE)
CURSOR = "cursor.json"
#: characters of hidden JSON per comment (GitHub's limit on a comment is 65536)
PAYLOAD_MAX = 50000
TITLE_MAX = 120
RE_MARK = re.compile(r"<!-- family:([0-9a-f]{12}) -->")
ROLES = ("author", "expert", "researcher", "scientist")
#: the coarse causes of a failed shell command (``error_ledger.bash_cause``)
CAUSES = frozenset([c for _, c in el.BASH_CAUSES] + ["killed or timed out", el.BENIGN_CAUSE,
                                                     "other"])
#: who may be named as having resolved an issue; anyone else is ``other``
RESOLVERS = frozenset(("human", "settle") + ROLES)
RE_REV = re.compile(r"[0-9a-f]{7,40}")
RE_VER = re.compile(r"\d+(?:\.\d+){0,3}")
RE_TS = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")

#: the only words a posted text may use: generic error words, tool words, the words of
#: this module's own text. A word outside it makes a family unlisted and a text unsafe.
#: Add a word only if it can name nothing private (no person, project, claim, slug,
#: host, file or search term).
VOCAB = frozenset("""
a about absolute academy accepted access accessible act action add added address addressed
adds after again against agent agents all allowed already altnames an and another answer
any api applies are argument arguments artifact as ask at attach attribute attributeerror
audit author available back bad bare bash batch be before belongs beyond block blocked
board body both budget build but by cached call calls came cannot carry cause causes cell
certificate chain change changed changes characters citation claim claims close closed
closes cmd coarse code column comment comments commit complete completed computation config connecting
connection connectors contain content continued could count counts create created cwd dates days
dead decisions decode deliver deliverable delivered denied design detail did directory do
does domain done dropped due each early edit else empty encoding end endpoint error errors
evidence every everything exactly exceed exceeded exist existing exists exit expected
experiment expert failed family fetch field fields file files final first fix for found
from frontmatter fts get gherror git github give gives glob goes got grep grounds hand has
hash have here holds home hops host https human id if imported in inbox inconsistent input
instance internal invalid is issue issues it its job json kb key killed kind label labels
land large last latex launch launcher lead leave leaving ledger library lie like limit line
lines list log lookup looks machine made many mark match matched math maximum may mcp
mechanism merge merging messages migrate missing modulo module more move must name names namespace
need needed needs network new no non none not notebook notes nothing ns null number object
occurrence occurrences of older omit on once one only open options or organization other
out output own owned pack packet packets parameter parent part party pass path pattern
pending permission personal planned post posted power private problem problems produced profile
progress proof property propose proved prover prs public published pull put py python
python3 query queue quote quoting rate reached read ready reason receiver recommendation
record records recurred recurrence refs refusal refused registry regression rejected relay
reopen reopened reopens reply request required researcher resolve resolved resolves
resource result rev review reviewer rigor ripgrep role roles root route run runs same
schema scientist script scripts search searching seconds section seen sender session set
settle sha shell show silence since so stacked stale status stay still stop structured
subagent such support switch sync syntax terminated text than the this ticket tickets
timed timeout title to too tool traceback transition trigger true type under unexpected unknown
unless unlisted unreachable update usage validation value valueerror ver verbatim verdict
verdicts verify version versions via waiting waits web weekly what when why with without
workspace would write writer written you your
""".split())

PLACEHOLDER = r"<(?:n|q|path|claim|id|host|instance|redacted)>"
#: the tokens of a family's message part; the whole part must be made of them
RE_FAMILY_TOKEN = re.compile(PLACEHOLDER + r"|->|<-|(?P<word>[a-z][a-z0-9_]*)|[ .,;:()\[\]{}/=+*#!?|&%~—-]")
RE_TOOL = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?::[A-Za-z][A-Za-z0-9_]*)?")
RE_UNLISTED = re.compile(r"\(unlisted family [0-9a-f]{12}\)")
#: the tokens of a posted text (``check_public``), tried in this order
RE_GATE_TOKEN = re.compile(
    r"<!--|-->|->|<-|" + PLACEHOLDER +
    r"|\d{4}-\d\d-\d\d(?:T\d\d:\d\d:\d\d)?"
    r"|(?<![\w])(?:[0-9a-f]{40}|[0-9a-f]{12}|(?=[0-9a-f]*\d)[0-9a-f]{7,39})(?![\w])"
    r"|\d+(?:\.\d+)*|(?P<word>[A-Za-z][A-Za-z0-9_]*)|[\s.,;:()\[\]{}/=+*#!?|&%~—'\"`\\-]")


#: a number like an arXiv id (``2101.12345``): no count, date or version looks like it
RE_LONG_DECIMAL = re.compile(r"\d\.\d{5}")


class Unsafe(ValueError):
    """A text that may not go to a public issue; nothing was sent."""


def word_ok(word):
    """Every ``_``-part (and camel-case part) of ``word`` is a ``VOCAB`` word."""
    parts = [q for p in word.split("_") for q in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", p)]
    return bool(parts) and all(q.lower() in VOCAB for q in parts)


def tool_ok(tool):
    return bool(RE_TOOL.fullmatch(tool or "")) and all(word_ok(w) for w in tool.split(":"))


def family_ok(fam):
    """Whether ``fam`` passes the allowlist: ``<tool>: <message>``, the tool made of
    ``VOCAB`` words and the message of allowed tokens only (``RE_FAMILY_TOKEN``, every
    word in ``VOCAB``); or an unlisted family already."""
    tool, sep, msg = str(fam or "").partition(": ")
    if not (sep and tool_ok(tool) and msg.strip()):
        return tool == "unlisted" and bool(sep) and bool(RE_UNLISTED.fullmatch(msg))
    if RE_UNLISTED.fullmatch(msg):
        return True
    pos = 0
    while pos < len(msg):
        m = RE_FAMILY_TOKEN.match(msg, pos)
        if not m:
            return False
        if m.group("word") and not word_ok(m.group("word")):
            return False
        pos = m.end()
    return True


class PublicFamily(str):
    """A family string that passed ``public_family``; only it may name an issue."""


def public_family(fam):
    """``fam`` if it passes ``family_ok``, else ``<tool>: (unlisted family <hash>)`` with
    the sha1 of ``fam`` (the tool ``unlisted`` when the tool fails the check too)."""
    fam = str(fam or "")
    if family_ok(fam):
        return PublicFamily(fam)
    tool = fam.partition(": ")[0]
    return PublicFamily("%s: (unlisted family %s)" % (
        tool if tool_ok(tool) else "unlisted", hashlib.sha1(fam.encode("utf-8")).hexdigest()[:12]))


def family_of(rec):
    """The public family of a ledger record."""
    return public_family(el.family_of(rec["sig"], rec))


def check_public(text):
    """Raise ``Unsafe`` unless every token of ``text`` is an allowed shape: a ``VOCAB``
    word, a placeholder, a date, a number or version, a hex hash, a comment marker or
    punctuation (JSON's ``\\u003c`` / ``\\u003e`` read as ``<`` / ``>``)."""
    s = str(text or "").replace("\\u003c", "<").replace("\\u003e", ">")
    if RE_LONG_DECIMAL.search(s):
        raise Unsafe("a number with a long decimal part (an arXiv id?)")
    pos = 0
    while pos < len(s):
        m = RE_GATE_TOKEN.match(s, pos)
        if not m:
            raise Unsafe("character %d (%r) is no allowed token" % (pos, s[pos]))
        if m.group("word") and not word_ok(m.group("word")):
            raise Unsafe("word %r is not in the vocabulary" % m.group("word"))
        pos = m.end()
    return text


class Gate(object):
    """The transport every write of this module goes through: each text is checked by
    ``check_public`` before the inner transport sees it."""

    STATES = (None, "open", "closed")
    REASONS = (None, "completed", "not_planned")

    def __init__(self, inner):
        self._inner = inner

    def list_issues(self, *a, **kw):
        return self._inner.list_issues(*a, **kw)

    def list_comments(self, *a, **kw):
        return self._inner.list_comments(*a, **kw)

    def _labels(self, labels):
        for lb in labels or ():
            check_public(lb)

    def create_issue(self, title, body, labels):
        check_public(title)
        check_public(body)
        self._labels(labels)
        return self._inner.create_issue(title, body, list(labels))

    def add_comment(self, number, body):
        check_public(body)
        return self._inner.add_comment(int(number), body)

    def update_issue(self, number, body=None, labels=None, state=None, state_reason=None):
        if state not in self.STATES or state_reason not in self.REASONS:
            raise Unsafe("state %r / %r" % (state, state_reason))
        if body is not None:
            check_public(body)
        self._labels(labels)
        return self._inner.update_issue(int(number), body=body, labels=labels, state=state,
                                        state_reason=state_reason)


def gated(t):
    return t if isinstance(t, Gate) or t is None else Gate(t)


def family_hash(fam):
    return hashlib.sha1(str(fam).encode("utf-8")).hexdigest()[:12]


def hidden(name, obj):
    """``obj`` as JSON in an HTML comment; ``<`` and ``>`` (only ever inside strings) are
    escaped, so the comment cannot be closed early."""
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "<!-- %s %s -->" % (name, s.replace("<", "\\u003c").replace(">", "\\u003e"))


def read_hidden(name, text):
    out = []
    for m in re.finditer(r"<!-- %s (.*?) -->" % re.escape(name), text or "", re.S):
        try:
            out.append(json.loads(m.group(1)))
        except ValueError:
            continue
    return out


def meta_of(issue):
    got = read_hidden("error-family", (issue or {}).get("body") or "")
    return got[-1] if got and isinstance(got[-1], dict) else None


def hash_of(issue):
    m = RE_MARK.search((issue or {}).get("body") or "")
    return m.group(1) if m else None


def label_names(issue):
    return [lb["name"] if isinstance(lb, dict) else str(lb) for lb in issue.get("labels") or []]


def transport(repo, run=None, write_interval=None):
    kw = {} if write_interval is None else {"write_interval": write_interval}
    return Gate(GhTransport(repo, run=run, **kw))


# -- the fields of an occurrence ----------------------------------------------------------

def role_of(instance):
    """The role of an instance id (``author@x`` -> ``author``); ``other`` for anything
    else (``workspace``, ``other``, an unknown string). Never the instance itself."""
    role = str(instance or "").split("@", 1)[0]
    return role if role in ROLES else "other"


def cause_of(rec):
    """The coarse cause of a shell record, from the fixed vocabulary ``CAUSES``, or ''."""
    c = rec.get("cause")
    if not c and rec.get("tool") in el.SHELL_TOOLS and rec.get("detail"):
        c = el.bash_cause(rec)
    return c if c in CAUSES else ""


def clean_rev(v):
    v = str(v or "")
    return v if RE_REV.fullmatch(v) else ""


def clean_ver(v):
    v = str(v or "")
    return v if RE_VER.fullmatch(v) else ""


def clean_ts(v):
    v = str(v or "")
    return v if RE_TS.fullmatch(v) else ""


def occ_row(r):
    return [clean_ts(r.get("ts")), role_of(r.get("instance")), cause_of(r),
            clean_rev(r.get("rev")), clean_ver(r.get("ver"))]


# -- the issue's text ---------------------------------------------------------------------

def _code(text):
    return "`%s`" % str(text or "").replace("`", "'").replace("|", "\\|")


def title(fam):
    t = "error family: " + str(fam)
    if len(t) <= TITLE_MAX:
        return t
    return t[:TITLE_MAX - 4].rsplit(" ", 1)[0] + " ..."


def _counts(counter):
    return ", ".join("%s %d" % kv for kv in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def render_body(meta):
    fam = meta["family"]
    if not isinstance(fam, PublicFamily):
        raise Unsafe("the family of an issue must come from public_family")
    fix = meta.get("fix") or {}
    rows = [("tool", _code(meta.get("tool"))), ("family", _code(fam)),
            ("occurrences", str(int(meta.get("count") or 0))),
            ("first seen", meta.get("first") or "-"), ("last seen", meta.get("last") or "-"),
            ("code of the last one", "rev %s, version %s" % (meta.get("rev") or "-",
                                                             meta.get("ver") or "-")),
            ("roles", _counts(meta.get("roles") or {}) or "-")]
    if fix:
        rows.append(("fix", "commit %s, version %s" % (fix.get("commit") or "-",
                                                        fix.get("version") or "-")))
    out = ["<!-- family:%s -->" % meta["hash"],
           "An error family of the error ledger of the academy (`error_ledger.py`): failed "
           "tool calls of one coarse kind. Only the family, counts, dates, code versions and "
           "roles are posted here; the messages stay in the private ledger. Each sync adds a "
           "comment with the new occurrences; `error_ledger.py resolve --family` closes the "
           "issue, and a recurrence reopens it (`regression` after a fix, `stale-code` when "
           "the errors came from code older than the fix).", "",
           "| field | value |", "|---|---|"]
    out += ["| %s | %s |" % r for r in rows]
    stored = {k: meta[k] for k in ("family", "hash", "tool", "count", "first", "last", "rev",
                                   "ver", "roles", "fix", "batch") if meta.get(k)}
    stored["family"] = str(fam)
    out += ["", hidden("error-family", stored)]
    return check_public("\n".join(out) + "\n")


def batch_id(fam, recs):
    return hashlib.sha1(json.dumps([str(fam)] + [occ_row(r) for r in recs]).encode("utf-8")
                        ).hexdigest()[:12]


def _chunks(rows):
    out, cur, size = [], [], 0
    for row in rows:
        n = len(json.dumps(row, ensure_ascii=False)) + 1
        if cur and size + n > PAYLOAD_MAX:
            out.append(cur)
            cur, size = [], 0
        cur.append(row)
        size += n
    out.append(cur)
    return out


def summary_text(rows, header=None):
    """The readable part of an occurrence comment, from the public rows only: the count,
    the date span, the counts by role and by cause, the code of the last one."""
    out = []
    if header:
        out += [header, ""]
    if rows:
        out.append("Occurrences: **%d**, %s .. %s" % (len(rows), rows[0][0], rows[-1][0]))
        out.append("By role: " + _counts(collections.Counter(r[1] for r in rows)))
        causes = collections.Counter(r[2] for r in rows if r[2])
        if causes:
            out.append("By cause: " + _counts(causes))
        if rows[-1][3] or rows[-1][4]:
            out.append("Code of the last one: rev %s, version %s" % (rows[-1][3] or "-",
                                                                     rows[-1][4] or "-"))
    return out


def occurrence_comments(recs, batch, header=None, resolves=()):
    """The comment bodies for ``recs`` (one family, oldest first): the summary and the
    hidden rows, split so no comment's payload passes ``PAYLOAD_MAX``; each carries
    ``<!-- batch:<id> part k/n -->`` so a retried sync can tell what is already there."""
    rows = [occ_row(r) for r in recs]
    parts = _chunks(rows)
    out = []
    for k, chunk in enumerate(parts, 1):
        text = summary_text(rows, header) if k == 1 else ["(continued, part %d of %d)"
                                                          % (k, len(parts))]
        text += ["", "<!-- batch:%s part %d/%d -->" % (batch, k, len(parts))]
        if chunk:
            text.append(hidden("occurrences", chunk))
        if k == 1 and resolves:
            text.append(hidden("resolves", [_resolve_row(r) for r in resolves]))
        out.append(check_public("\n".join(text) + "\n"))
    return out


def _resolve_row(r):
    """A resolve as it may be posted: when, by whom (a role, ``human``, ``settle`` or
    ``other``), the fix's commit and version. Never the note."""
    by = str(r.get("by") or "")
    row = {"at": clean_ts(r.get("ts")), "by": by if by in RESOLVERS else "other"}
    if clean_rev(r.get("commit")):
        row["commit"] = clean_rev(r["commit"])
    if clean_ver(r.get("version")):
        row["version"] = clean_ver(r["version"])
    return row


def records_of(meta, comments):
    """The records of one family, rebuilt from its comments' hidden payloads: one
    ledger "class" whose signature is the family; the session is unknown (``?``) and the
    instance is the role."""
    fam = meta.get("family") or "?"
    out = []
    for c in comments:
        body = c.get("body") or ""
        for rows in read_hidden("occurrences", body):
            for row in rows if isinstance(rows, list) else []:
                ts, role, cause, rev, ver = (list(row) + [""] * 5)[:5]
                if not ts:
                    continue
                rec = {"t": "error", "ts": ts, "session": "?", "instance": role or "other",
                       "tool": meta.get("tool") or "?", "sig": fam, "msg": fam}
                for k, v in (("cause", cause), ("rev", rev), ("ver", ver)):
                    if v:
                        rec[k] = v
                out.append(rec)
        for rows in read_hidden("resolves", body):
            for r in rows if isinstance(rows, list) else []:
                if isinstance(r, dict) and r.get("at"):
                    rec = {"t": "resolve", "ts": r["at"], "sig": fam, "by": r.get("by") or ""}
                    for k in ("commit", "version"):
                        if r.get(k):
                            rec[k] = r[k]
                    out.append(rec)
    return out


def merge_meta(old, fam, recs, batch):
    """The family's fields after adding ``recs``; unchanged when ``batch`` is already in."""
    if not isinstance(fam, PublicFamily):
        raise Unsafe("the family of an issue must come from public_family")
    m = dict(old or {})
    if m.get("batch") == batch:
        m["family"] = fam
        return m
    rows = [occ_row(r) for r in recs]
    m.update(family=fam, hash=family_hash(fam), batch=batch, tool=fam.partition(": ")[0])
    m["first"] = min([x for x in (m.get("first"), rows[0][0]) if x])
    m["last"] = max([x for x in (m.get("last"), rows[-1][0]) if x])
    m["count"] = int(m.get("count") or 0) + len(rows)
    roles = collections.Counter({k: int(v) for k, v in (m.get("roles") or {}).items()
                                 if k in ROLES + ("other",)})
    roles.update(r[1] for r in rows)
    m["roles"] = dict(roles)
    if rows[-1][3]:
        m["rev"] = rows[-1][3]
    if rows[-1][4]:
        m["ver"] = rows[-1][4]
    return m


def _meta_family(meta):
    """The issue's family, read back and checked again."""
    return public_family((meta or {}).get("family") or "")


# -- reading the repo ---------------------------------------------------------------------

def _pages(fetch):
    out, page = [], 1
    while True:
        rows = fetch(page) or []
        out += rows
        if len(rows) < 100:
            return out
        page += 1


def list_families(t, state="all"):
    """The ``error-family`` issues (pull requests left out)."""
    return [i for i in _pages(lambda p: t.list_issues(labels=[LABEL], state=state, page=p))
            if "pull_request" not in i]


def index(t, state="all"):
    """family hash -> issue; the lowest number wins if a family has two."""
    out = {}
    for i in list_families(t, state):
        h = hash_of(i)
        if h and (h not in out or i["number"] < out[h]["number"]):
            out[h] = i
    return out


def comments_of(t, number):
    return _pages(lambda p: t.list_comments(number, page=p))


# -- sync -----------------------------------------------------------------------------------

def load_cursor(spool):
    try:
        with open(os.path.join(spool, CURSOR), encoding="utf-8") as fh:
            cur = json.load(fh)
    except (OSError, ValueError):
        cur = {}
    if not isinstance(cur, dict):
        cur = {}
    cur.setdefault("offsets", {})
    cur.setdefault("partial", None)
    return cur


def save_cursor(spool, cur):
    os.makedirs(spool, exist_ok=True)
    tmp = os.path.join(spool, CURSOR + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cur, fh, indent=1, sort_keys=True)
    os.replace(tmp, os.path.join(spool, CURSOR))


def read_batch(spool, cur):
    """``(records, upto)``: the spool's error records from each file's cursor offset to its
    end (whole lines only), or to the unfinished batch's end when there is one; benign
    records and identical duplicates left out. ``upto`` is the new offset per file."""
    partial = cur.get("partial")
    try:
        names = sorted(n for n in os.listdir(spool) if n.endswith(".jsonl"))
    except OSError:
        names = []
    recs, upto, seen = [], {}, set()
    for name in names:
        path = os.path.join(spool, name)
        start = int(cur["offsets"].get(name, 0))
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size < start:            # the file was cut by hand: read it again from the top
            start = 0
        end = int(partial["upto"].get(name, start)) if partial else size
        with open(path, "rb") as fh:
            fh.seek(start)
            data = fh.read(max(0, end - start))
        cut = data.rfind(b"\n") + 1
        upto[name] = start + cut
        for ln in data[:cut].decode("utf-8", "replace").splitlines():
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if not (isinstance(rec, dict) and rec.get("t") == "error" and rec.get("ts")
                    and rec.get("sig")) or el.is_benign(rec):
                continue
            key = json.dumps(rec, sort_keys=True)
            if key not in seen:
                seen.add(key)
                recs.append(rec)
    recs.sort(key=lambda r: r["ts"])
    return recs, upto


def group(recs):
    """public family -> its records, oldest first."""
    out = collections.OrderedDict()
    for r in recs:
        out.setdefault(family_of(r), []).append(r)
    return out


def _stale(recs, fix):
    return all(el.has_fix(r, fix.get("commit") or "", fix.get("version") or "") is False
               for r in recs)


def post_family(t, issue, fam, recs):
    """Post one family's new records: create its issue, or update it (reopen a closed one,
    with ``regression`` / ``stale-code``), then the occurrence comment(s). Safe to repeat
    for the same batch: the fields merge once and a comment already there is not posted
    again. Returns ``(action, number, tag)``."""
    t = gated(t)
    batch = batch_id(fam, recs)
    old = meta_of(issue) if issue else None
    retry = bool(old and old.get("batch") == batch)
    meta = merge_meta(old, fam, recs, batch)
    tag = None
    if issue is None:
        issue = t.create_issue(title(fam), render_body(meta), [LABEL])
        action = "created"
    else:
        labels = label_names(issue)
        fix = meta.get("fix") or {}
        new = list(labels)
        if issue.get("state") == "closed":
            if fix.get("commit") or fix.get("version"):
                tag = STALE if _stale(recs, fix) else REGRESSION
            new = [x for x in labels if x not in TAGS] + ([tag] if tag else [])
            action = "reopened"
        else:
            if STALE in labels and fix and not _stale(recs, fix):
                tag = REGRESSION
                new = [x for x in labels if x != STALE] + [REGRESSION]
            action = "commented"
        if LABEL not in new:
            new.append(LABEL)
        if not retry or issue.get("state") == "closed" or new != labels:
            t.update_issue(issue["number"], body=render_body(meta),
                           labels=new if new != labels else None,
                           state="open" if issue.get("state") == "closed" else None)
    header = None
    if action == "reopened":
        header = "Reopened: the family recurred%s." % (
            " after the fix (commit %s, version %s): **%s**" % (
                (meta.get("fix") or {}).get("commit") or "-",
                (meta.get("fix") or {}).get("version") or "-", tag) if tag else "")
    bodies = occurrence_comments(recs, batch, header)
    have = set()
    if retry:
        for c in comments_of(t, issue["number"]):
            have.update(re.findall(r"<!-- batch:([0-9a-f]+ part \d+/\d+) -->", c.get("body") or ""))
    for k, body in enumerate(bodies, 1):
        if "%s part %d/%d" % (batch, k, len(bodies)) not in have:
            t.add_comment(issue["number"], body)
    return action, issue["number"], tag


def sync(spool, t, dry_run=False):
    """Post the spool's new records to the repo of ``t``, one issue per public family.
    Returns a summary dict: ``records``, ``families``, ``posted`` ([{family, issue,
    action, tag, count}]), ``dry_run``, ``error`` (when a call failed or a text was
    refused; the batch is finished by the next sync)."""
    t = gated(t)
    cur = load_cursor(spool)
    out = {"records": 0, "families": 0, "posted": [], "dry_run": dry_run, "error": None}
    while True:
        partial = cur.get("partial")
        recs, upto = read_batch(spool, cur)
        done = set(partial["done"]) if partial else set()
        groups = collections.OrderedDict((f, v) for f, v in group(recs).items()
                                         if str(f) not in done)
        out["records"] += sum(len(v) for v in groups.values())
        out["families"] += len(groups)
        if dry_run:
            out["posted"] += [{"family": str(f), "issue": None, "action": "would post",
                               "tag": None, "count": len(v)}
                              for f, v in sorted(groups.items())]
            return out
        issues = index(t) if groups else {}
        for fam in sorted(groups):
            try:
                action, number, tag = post_family(t, issues.get(family_hash(fam)), fam,
                                                  groups[fam])
            except (GhError, Unsafe) as e:
                cur["partial"] = {"upto": upto, "done": sorted(done)}
                save_cursor(spool, cur)
                out["error"] = "%s: %s" % (type(e).__name__, e)
                return out
            done.add(str(fam))
            out["posted"].append({"family": str(fam), "issue": number, "action": action,
                                  "tag": tag, "count": len(groups[fam])})
        cur["offsets"].update(upto)
        cur["partial"] = None
        save_cursor(spool, cur)
        if not partial:
            return out


def pending(spool):
    """How many spool error records are not posted yet (offline)."""
    return len(read_batch(spool, dict(load_cursor(spool), partial=None))[0])


# -- report, resolve, settle -------------------------------------------------------------

def issue_records(t, start):
    """``(records, numbers, tags)``: the records of every open ``error-family`` issue,
    rebuilt from its comments, plus one settle record at ``start`` (a family seen before
    the window counts as reported: its issue was there to read); ``numbers``: family ->
    issue; ``tags``: family -> its ``regression`` / ``stale-code`` label."""
    recs, numbers, tags = [], {}, {}
    for i in list_families(t, "open"):
        meta = meta_of(i)
        if not meta or not meta.get("family"):
            continue
        fam = meta["family"]
        numbers[fam] = i["number"]
        for tag in TAGS:
            if tag in label_names(i):
                tags[fam] = tag
        recs += records_of(meta, comments_of(t, i["number"]))
    lo = el._stamp(start)
    recs.append({"t": "settle", "ts": lo, "upto": lo})
    recs.sort(key=lambda r: r["ts"])
    return recs, numbers, tags


def report(t, start, now):
    """``error_ledger.report`` over the open issues, one class per family; a reopened
    issue's label (``regression`` / ``stale-code``) sets its state. Each class row gains
    ``issue`` and ``family``."""
    recs, numbers, tags = issue_records(t, start)
    rep = el.report(recs, start, now, tags)
    for r in rep["classes"]:
        r["issue"] = numbers.get(r["sig"])
        r["family"] = r["sig"]
    rep["source"] = "issues"
    return rep


def _close(t, issue, meta, row, text):
    meta = dict(meta, family=_meta_family(meta))
    meta["hash"] = family_hash(meta["family"])
    pub = _resolve_row(row)
    if pub.get("commit") or pub.get("version"):
        meta["fix"] = {k: pub[k] for k in ("commit", "version") if pub.get(k)}
    else:
        meta.pop("fix", None)
    t.add_comment(issue["number"], check_public(text + "\n\n" + hidden("resolves", [pub]) + "\n"))
    names = label_names(issue)
    keep = [x for x in names if x not in TAGS]
    t.update_issue(issue["number"], body=render_body(meta), state="closed",
                   state_reason="completed", labels=keep if keep != names else None)


def wanted(names):
    """The posted family of each name (a family of the report, or a signature)."""
    return {str(public_family(el.family(n))): n for n in names}


def resolve(t, sigs=(), families=(), by="human", commit="", version="", now=None):
    """Close the open issues of ``families`` (and of the family of each of ``sigs``) with a
    comment naming who resolved it and the fix; the note is never posted (the CLI keeps it
    in the local spool). Returns ``(closed, missing)``: [(family, number)] and the names
    with no open issue."""
    t = gated(t)
    now = now or el._now()
    want = wanted(list(sigs) + list(families))
    targets, found = [], set()
    for i in list_families(t, "open"):
        meta = meta_of(i)
        if meta and meta.get("family") in want:
            targets.append((i, meta))
            found.add(meta["family"])
    row = {"ts": el._stamp(now), "by": by, "commit": commit, "version": version}
    pub = _resolve_row(row)
    closed = []
    for i, meta in targets:
        text = "Resolved by %s." % pub["by"]
        if pub.get("commit") or pub.get("version"):
            text += " Fix: commit %s, version %s." % (pub.get("commit") or "-",
                                                      pub.get("version") or "-")
        _close(t, i, meta, row, text)
        closed.append((meta["family"], i["number"]))
    return closed, [n for f, n in want.items() if f not in found]


def settle(t, quiet_days=7, now=None):
    """Close every open ``error-family`` issue with no occurrence for ``quiet_days`` days
    ("closed by silence"). Returns [(family, number)]."""
    t = gated(t)
    now = now or el._now()
    cutoff = el._stamp(now - _dt.timedelta(days=quiet_days))
    closed = []
    for i in list_families(t, "open"):
        meta = meta_of(i)
        if not meta or not meta.get("family") or not meta.get("last") or meta["last"] >= cutoff:
            continue
        row = {"ts": el._stamp(now), "by": "settle"}
        text = ("Closed by silence: no occurrence for %d days (last seen %s)."
                % (int(quiet_days), clean_ts(meta["last"]) or "-"))
        _close(t, i, meta, row, text)
        closed.append((meta["family"], i["number"]))
    return closed


# -- migrate -----------------------------------------------------------------------------

def migrate_plan(records):
    """One entry per public family of the git ledger with at least one counted error:
    ``{family, open, tag, errors, resolves, meta}``. A family is open when one of its
    errors is in an open class (``error_ledger.classes``); an open family posts its open
    errors, a resolved one all its errors and the resolves of its classes. ``tag`` is
    ``regression`` / ``stale-code`` for an open family whose classes' last resolve named
    a fix, as sync tags it."""
    errs = collections.defaultdict(list)
    fams_of_sig = collections.defaultdict(set)
    for r in records:
        if r["t"] == "error" and r.get("sig") and not el.is_benign(r):
            f = family_of(r)
            errs[f].append(r)
            fams_of_sig[r["sig"]].add(f)
    open_ids = {id(x) for c in el.classes(records).values() for x in c["recs"]}
    res = collections.defaultdict(list)
    for r in records:
        if r["t"] == "resolve" and r.get("sig"):
            for f in fams_of_sig.get(r["sig"], ()):
                res[f].append(r)
    plan = []
    for fam in sorted(errs):
        live = [r for r in errs[fam] if id(r) in open_ids]
        rs = sorted(res[fam], key=lambda r: r["ts"])
        posted = live or errs[fam]
        meta = merge_meta(None, fam, posted, "migrate")
        fixed = [r for r in rs if r.get("commit") or r.get("version")]
        pub = _resolve_row(fixed[-1]) if fixed else {}
        if pub.get("commit") or pub.get("version"):
            meta["fix"] = {k: pub[k] for k in ("commit", "version") if pub.get(k)}
        tag = None
        fix = meta.get("fix") or {}
        if live and fix:
            tag = STALE if _stale(live, fix) else REGRESSION
        plan.append({"family": fam, "open": bool(live), "tag": tag, "errors": posted,
                     "resolves": [] if live else rs, "meta": meta})
    return plan


def migrate(records, t=None, dry_run=False, skip_resolved=False, log=None):
    """Import the git ledger by family: an open family becomes an open issue, a resolved
    one a closed issue (or nothing, ``skip_resolved``), each with one comment (more for a
    large family) holding its occurrences and resolves. A family whose issue exists is
    completed, not duplicated, so a failed run is resumed by running it again. Returns a
    summary dict."""
    t = gated(t)
    plan = migrate_plan(records)
    todo = [p for p in plan if p["open"] or not skip_resolved]
    out = {"families": len(plan), "open": sum(1 for p in plan if p["open"]),
           "resolved": sum(1 for p in plan if not p["open"]),
           "regression": sum(1 for p in plan if p["tag"] == REGRESSION),
           "stale_code": sum(1 for p in plan if p["tag"] == STALE),
           "unlisted": sum(1 for p in plan if RE_UNLISTED.search(p["family"])),
           "errors": sum(len(p["errors"]) for p in plan),
           "resolves": sum(len(p["resolves"]) for p in plan),
           "to_import": len(todo), "skipped_resolved": len(plan) - len(todo),
           "comments": sum(len(_chunks([occ_row(r) for r in p["errors"]])) for p in todo),
           "dry_run": dry_run, "created": 0, "completed": 0, "existing": 0}
    out["writes"] = out["to_import"] + out["comments"] + sum(1 for p in todo if not p["open"])
    # every text is built (and so checked) before anything is sent, also on a dry run
    texts = [(p, render_body(p["meta"]),
              occurrence_comments(p["errors"], "migrate", "Imported from the git error ledger.",
                                  p["resolves"])) for p in todo]
    if dry_run:
        return out
    have = index(t)
    for p, body, bodies in texts:
        fam = p["family"]
        issue = have.get(family_hash(fam))
        got = set()
        if issue is None:
            labels = [LABEL] + ([p["tag"]] if p["tag"] else [])
            issue = t.create_issue(title(fam), body, labels)
            out["created"] += 1
        else:
            for c in comments_of(t, issue["number"]):
                got.update(re.findall(r"<!-- batch:(migrate part \d+/\d+) -->",
                                      c.get("body") or ""))
            if len(got) >= len(bodies) and (p["open"] or issue.get("state") == "closed"):
                out["existing"] += 1
                continue
            out["completed"] += 1
        for k, text in enumerate(bodies, 1):
            if "migrate part %d/%d" % (k, len(bodies)) not in got:
                t.add_comment(issue["number"], text)
        if not p["open"] and issue.get("state") != "closed":
            t.update_issue(issue["number"], state="closed", state_reason="completed")
        if log:
            log("%s #%s %s" % ("open  " if p["open"] else "closed", issue["number"], fam))
    return out
