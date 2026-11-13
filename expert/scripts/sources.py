"""sources.py -- bibliographic records and new-paper listings from the scholarly APIs.

    py sources.py lookup <arXiv id | DOI> [--json]
    py sources.py search "<query>" [--cat math.DS,math.GT] [--since YYYY-MM-DD] [--max 25] [--json]

The librarian's cite runs and the related-work scout's watch used to read arXiv and
publisher pages through a web fetch and take the record from the HTML. The arXiv API
(``export.arxiv.org/api/query``) and Crossref's REST API (``api.crossref.org/works``)
return the same record as data: one request, no page to interpret, an id to deduplicate
by. Both hosts are on the Expert's source allowlist (``references/sources.json``); a
cloud environment needs only these two for this script.

``lookup`` prints one record: title, authors, year, the arXiv id with its latest version
and primary category, the journal reference and DOI. An arXiv record that names a DOI is
completed from Crossref (journal, volume, issue, pages, year), and says which fields came
from where. ``search`` lists arXiv records matching a query, newest first; with ``--since``
only those submitted or updated on or after that day (the watch).

A record is a bibliographic fact, not a citation: the statement, its hypotheses and the
verbatim quote still come from the source itself (the citation card). Nothing here is
cached, written to the library or added to a bibliography.

Exit 0 with records; 1 when nothing was found; 2 on an error (a host that cannot be
reached is named, with the allowlist to check). stdlib only.
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ARXIV_API = "https://export.arxiv.org/api/query"
CROSSREF_API = "https://api.crossref.org/works/"
ATOM = "{http://www.w3.org/2005/Atom}"
ARX = "{http://arxiv.org/schemas/atom}"
RE_ARXIV_NEW = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?$", re.I)
RE_ARXIV_OLD = re.compile(r"^(?:arxiv:)?([a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?$", re.I)
RE_DOI = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$", re.I)
TIMEOUT = 30
AGENT = "academy-expert-sources/1 (stdlib urllib)"


class SourceError(Exception):
    pass


def classify(ref):
    """``("arxiv", id)``, ``("doi", doi)`` or ``(None, ref)`` for a reference string."""
    ref = str(ref or "").strip()
    ref = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", ref, flags=re.I)
    for pat in (RE_ARXIV_NEW, RE_ARXIV_OLD):
        m = pat.match(ref)
        if m:
            return "arxiv", m.group(1)
    m = RE_DOI.match(ref)
    if m:
        return "doi", m.group(1).rstrip(".,;")
    return None, ref


def fetch(url, retry_after=4):
    """The body of ``url`` as text. Raises SourceError naming the host on any failure;
    a 404 returns None (nothing there). A 429 or 503 (the API's rate limit) is tried
    once more after ``retry_after`` seconds, never in a loop."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENT,
                                               "Accept": "application/json, application/atom+xml"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code in (429, 503) and retry_after:
            time.sleep(retry_after)
            return fetch(url, retry_after=0)
        if exc.code in (429, 503):
            raise SourceError("%s is rate-limiting (HTTP %s); wait a minute, do not retry "
                              "in a loop" % (urllib.parse.urlsplit(url).hostname, exc.code))
        raise SourceError("%s answered %s" % (urllib.parse.urlsplit(url).hostname, exc.code))
    except (urllib.error.URLError, OSError) as exc:
        host = urllib.parse.urlsplit(url).hostname
        raise SourceError("%s cannot be reached (%s); in a cloud session it must be among "
                          "the environment's allowed hosts (source_guard.py --list)"
                          % (host, getattr(exc, "reason", exc)))


def _text(node, tag):
    el = node.find(tag)
    return " ".join((el.text or "").split()) if el is not None else ""


def parse_arxiv(xml_text):
    """The records of an arXiv API feed, in feed order."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceError("the arXiv API answer is not XML (%s)" % exc)
    for e in root.findall(ATOM + "entry"):
        m = re.search(r"arxiv\.org/abs/(.+?)(v\d+)?$", _text(e, ATOM + "id"))
        if not m:
            continue                    # an error entry
        prim = e.find(ARX + "primary_category")
        rec = {"source": "arxiv", "arxiv": m.group(1), "version": m.group(2) or "",
               "title": _text(e, ATOM + "title"),
               "authors": [_text(a, ATOM + "name") for a in e.findall(ATOM + "author")],
               "year": _text(e, ATOM + "published")[:4],
               "submitted": _text(e, ATOM + "published")[:10],
               "updated": _text(e, ATOM + "updated")[:10],
               "category": prim.get("term") if prim is not None else "",
               "categories": [c.get("term") for c in e.findall(ATOM + "category")],
               "journal_ref": _text(e, ARX + "journal_ref"),
               "doi": _text(e, ARX + "doi"),
               "abstract": _text(e, ATOM + "summary")}
        out.append({k: v for k, v in rec.items() if v not in ("", [], None)})
    return out


def parse_crossref(json_text):
    """One record from a Crossref ``works/<doi>`` answer."""
    try:
        m = json.loads(json_text)["message"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SourceError("the Crossref answer is not a work record (%s)" % exc)

    def first(key):
        v = m.get(key)
        return html.unescape(" ".join(str(v[0]).split())) if isinstance(v, list) and v else ""

    year = ""
    for key in ("published-print", "issued", "published-online"):
        parts = ((m.get(key) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            year = str(parts[0])
            break
    rec = {"source": "crossref", "doi": m.get("DOI") or "", "title": first("title"),
           "authors": [" ".join(x for x in (a.get("given"), a.get("family")) if x)
                       for a in m.get("author") or []],
           "year": year, "journal": first("container-title"),
           "journal_short": first("short-container-title"),
           "volume": m.get("volume") or "", "issue": m.get("issue") or "",
           "pages": m.get("page") or "", "publisher": m.get("publisher") or "",
           "type": m.get("type") or ""}
    return {k: v for k, v in rec.items() if v not in ("", [], None)}


def merge(arxiv_rec, crossref_rec):
    """The arXiv record completed by the published one: the published fields are added
    under ``published`` and nothing of the preprint is overwritten (the two can differ:
    a title changed in print, a year)."""
    out = dict(arxiv_rec)
    if crossref_rec:
        out["published"] = {k: v for k, v in crossref_rec.items()
                            if k in ("title", "year", "journal", "journal_short", "volume",
                                     "issue", "pages", "publisher", "doi")}
    return out


def lookup(ref, get=fetch):
    kind, key = classify(ref)
    if kind == "arxiv":
        body = get(ARXIV_API + "?" + urllib.parse.urlencode({"id_list": key}))
        recs = parse_arxiv(body) if body else []
        if not recs:
            return None
        rec = recs[0]
        if rec.get("doi"):
            try:
                body = get(CROSSREF_API + urllib.parse.quote(rec["doi"], safe="/"))
                rec = merge(rec, parse_crossref(body) if body else None)
            except SourceError as exc:
                rec["published_note"] = "Crossref not consulted: %s" % exc
        return rec
    if kind == "doi":
        body = get(CROSSREF_API + urllib.parse.quote(key, safe="/"))
        return parse_crossref(body) if body else None
    raise SourceError("%r is neither an arXiv id (1407.2975, math/0501001) nor a DOI "
                      "(10.xxxx/...); use search for a title" % ref)


def search(query, cats=(), since=None, limit=25, get=fetch):
    terms = []
    q = " ".join(str(query or "").split())
    if q:
        terms.append('all:"%s"' % q.replace('"', "") if " " in q and ":" not in q else
                     (q if ":" in q else "all:" + q))
    if cats:
        terms.append("(" + " OR ".join("cat:" + c for c in cats) + ")")
    if not terms:
        raise SourceError("search needs a query or --cat")
    params = {"search_query": " AND ".join(terms), "start": 0, "max_results": int(limit),
              "sortBy": "lastUpdatedDate" if since else "relevance",
              "sortOrder": "descending"}
    body = get(ARXIV_API + "?" + urllib.parse.urlencode(params))
    recs = parse_arxiv(body) if body else []
    if since:
        recs = [r for r in recs if max(r.get("updated", ""), r.get("submitted", "")) >= since]
    return recs


def render(rec):
    lines = ["%s%s  %s" % (rec.get("arxiv") or rec.get("doi") or "?", rec.get("version", ""),
                          rec.get("title", "")),
             "  " + ", ".join(rec.get("authors") or []) + (" (%s)" % rec["year"]
                                                           if rec.get("year") else "")]
    bits = [rec.get(k) for k in ("category", "journal_ref") if rec.get(k)]
    if rec.get("journal"):
        bits.append("%s %s%s (%s) %s" % (rec["journal"], rec.get("volume", ""),
                                        "(%s)" % rec["issue"] if rec.get("issue") else "",
                                        rec.get("year", ""), rec.get("pages", "")))
    if rec.get("doi") and rec.get("arxiv"):
        bits.append("doi:" + rec["doi"])
    if bits:
        lines.append("  " + "; ".join(bits))
    p = rec.get("published")
    if p:
        lines.append("  published (Crossref): %s %s%s (%s) %s"
                     % (p.get("journal", ""), p.get("volume", ""),
                        "(%s)" % p["issue"] if p.get("issue") else "", p.get("year", ""),
                        p.get("pages", "")))
        if p.get("title") and p["title"] != rec.get("title"):
            lines.append("  published title differs: %s" % p["title"])
    if rec.get("published_note"):
        lines.append("  " + rec["published_note"])
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lookup")
    p.add_argument("ref")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("search")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--cat", default="", help="arXiv categories, comma-separated")
    p.add_argument("--since", help="YYYY-MM-DD: submitted or updated on or after")
    p.add_argument("--max", type=int, default=25)
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        if a.cmd == "lookup":
            rec = lookup(a.ref)
            recs = [rec] if rec else []
        else:
            if a.since and not re.match(r"^\d{4}-\d{2}-\d{2}$", a.since):
                raise SourceError("--since is YYYY-MM-DD")
            recs = search(a.query, [c for c in a.cat.split(",") if c.strip()], a.since, a.max)
    except SourceError as exc:
        print("sources: %s" % exc, file=sys.stderr)
        return 2
    if not recs:
        print("sources: nothing found", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(recs[0] if a.cmd == "lookup" else recs, indent=2, ensure_ascii=False))
    else:
        for r in recs:
            r = dict(r)
            r.pop("abstract", None)
            print(render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
