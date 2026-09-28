"""deep_dive_index.py -- where each /academy:deep-dive artifact was published.

A deep-dive is re-published to the same artifact URL every time it is re-run, so
the URL is recorded, per deep-dive id, in ``<board>/deep-dives/index.json``
(docs/protocol.md section 2: ``deep-dives/<id>.html`` holds the local copy). The
review dashboard is recorded here too, under the id ``review-dashboard``.

Usage:

    py deep_dive_index.py id <subject>              the canonical id of a subject
    py deep_dive_index.py get <id> [--json]          the recorded URL (exit 1 if none)
    py deep_dive_index.py set <id> --url U [--kind K] [--title T] [--subject S]
    py deep_dive_index.py list [--json]
    py deep_dive_index.py path <id>                  the local copy's path

Common options: ``--board DIR`` (default: workspace.json ``board``),
``--workspace PATH``.

index.json is ``{"<id>": {"subject", "kind", "title", "url", "html", "created",
"updated"}}``, 2-space indented, keys sorted, LF.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

try:
    import academy_common as ac  # noqa: E402
except ImportError:  # vendored copy
    import _academy as ac  # noqa: E402

DIR = "deep-dives"
INDEX = "index.json"
DASHBOARD_ID = "review-dashboard"
RE_ARTIFACT_URL = re.compile(r"^https://claude\.ai/\S+$")


def subject_id(subject):
    """Canonical deep-dive id: ``paper:lem:strip-bound`` -> ``paper-lem-strip-bound``.

    The same slug render_packets.py uses for ``deep-dives/<id>.html`` (a test pins
    the two together): lower-case, runs outside ``[a-z0-9]`` collapsed to ``-``,
    trimmed, at most 80 characters; ``deep-dive`` if nothing is left.
    """
    return ac.slugify(str(subject).replace(":", "-"), maxlen=80, default="deep-dive")


def resolve_board(board=None, workspace=None):
    if board:
        return os.path.abspath(board)
    return os.path.abspath(ac.load_workspace(workspace)["board"])


def index_path(board):
    return os.path.join(board, DIR, INDEX)


def html_path(board, did):
    return os.path.join(board, DIR, "%s.html" % did)


def load_index(board):
    p = index_path(board)
    if not os.path.isfile(p):
        return {}
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ac.AcademyError("%s is not a JSON object" % p)
    return data


def save_index(board, data):
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ac.atomic_write(index_path(board), text)


def get_entry(board, did):
    return load_index(board).get(did)


def set_entry(board, did, url, kind=None, title=None, subject=None, date=None):
    """Record (or update) the URL of deep-dive ``did``; returns the entry."""
    if did != subject_id(did):
        raise ac.AcademyError("bad deep-dive id %r (use `id <subject>`)" % did)
    if not RE_ARTIFACT_URL.match(url or ""):
        raise ac.AcademyError("not a claude.ai artifact URL: %r" % url)
    date = date or ac.today()
    data = load_index(board)
    old = data.get(did) or {}
    if old.get("url") and old["url"] != url:
        # A new URL for an existing deep-dive is allowed (the old artifact may have
        # been deleted), but it is recorded so the report can say so.
        old.setdefault("previous_urls", []).append(old["url"])
    entry = dict(old)
    entry.update({
        "subject": subject if subject is not None else old.get("subject", did),
        "kind": kind if kind is not None else old.get("kind", "other"),
        "title": title if title is not None else old.get("title", did),
        "url": url,
        "html": "%s/%s.html" % (DIR, did),
        "created": old.get("created", date),
        "updated": date,
    })
    data[did] = entry
    save_index(board, data)
    return entry


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--board")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("id"); p.add_argument("subject")
    p = sub.add_parser("get"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("set"); p.add_argument("id"); p.add_argument("--url", required=True)
    p.add_argument("--kind"); p.add_argument("--title"); p.add_argument("--subject")
    p = sub.add_parser("list"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("path"); p.add_argument("id")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if a.cmd == "id":
        print(subject_id(a.subject))
        return 0
    try:
        board = resolve_board(a.board, a.workspace)
        if a.cmd == "path":
            print(html_path(board, a.id).replace("\\", "/"))
        elif a.cmd == "get":
            e = get_entry(board, a.id)
            if not e:
                return 1
            print(json.dumps(e, indent=2) if a.json else e["url"])
        elif a.cmd == "set":
            e = set_entry(board, a.id, a.url, a.kind, a.title, a.subject)
            print("%s -> %s" % (a.id, e["url"]))
        elif a.cmd == "list":
            data = load_index(board)
            if a.json:
                print(json.dumps(data, indent=2, sort_keys=True))
            else:
                for k in sorted(data):
                    print("%-40s %-12s %s  %s" % (k, data[k].get("kind"), data[k].get("updated"),
                                                   data[k].get("url")))
    except (ac.AcademyError, OSError, ValueError) as exc:
        print("deep_dive_index: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
