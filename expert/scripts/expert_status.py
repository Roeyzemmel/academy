"""expert_status.py -- one screen on an Expert instance. Read-only.

    py expert_status.py [--instance expert@main] [--no-quotes] [--json]

Reports: the home and whether its ``.claude/academy.json`` is valid; the library
(cached keys, index rows, keys without a row); the cards (count, errors, warnings,
quotes verified against the cached text); the review passes (and which wait for
run B or for a decision record); ``hot.md`` (present, age); the board (tickets to
the instance by status, the instance's open packets).
"""

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
import cards as cardlib  # noqa: E402
import library_index as li  # noqa: E402
import decision_table as dt  # noqa: E402


def review_state(home):
    root = ex.home_path(home, ex.expert_config(home), "reviews", "reviews")
    passes, waiting_b, undecided = 0, [], []
    if not os.path.isdir(root):
        return {"passes": 0, "awaiting_b": [], "undecided": []}
    for dp, dn, fn in os.walk(root):
        if "A.md" not in fn:
            continue
        passes += 1
        rel = os.path.relpath(dp, root).replace("\\", "/")
        a = dt.read_record(os.path.join(dp, "A.md"))
        b = dt.read_record(os.path.join(dp, "B.md")) if "B.md" in fn else None
        if b is None and dt.should_launch_b(a):
            waiting_b.append(rel)
        elif "decision.md" not in fn:
            undecided.append(rel)
    return {"passes": passes, "awaiting_b": waiting_b, "undecided": undecided}


def status(ws, instance, quotes=True):
    inst = ws["instances"][instance]
    home = os.path.abspath(inst["home"])
    out = {"instance": instance, "home": home.replace("\\", "/"),
           "domains": inst.get("domains")}
    cfg = None
    if not os.path.isfile(os.path.join(home, ac.CONFIG_REL)):
        out["config"] = "not switched over (no .claude/academy.json)"
    else:
        try:
            cfg = ac.load_config(home)
            out["config"] = "valid"
        except ac.AcademyError as exc:
            out["config"] = "invalid: %s" % exc
    if not os.path.isdir(home):
        out["library"] = "home missing"
        return out
    m = li.missing(home, cfg)
    out["library"] = {"cached": m["cached"], "indexed": m["indexed"],
                      "without_row": sorted(m["cached_without_index_row"]),
                      "indexed_without_files": m["indexed_without_files"]}
    n = err = warn = verified = 0
    cache = {}
    for p in cardlib.iter_cards(home):
        n += 1
        e, w, q = cardlib.validate_path(p, home, quotes, cache)
        err += bool(e)
        warn += bool(w)
        verified += bool(q and q.get("status") == "verified")
    out["cards"] = {"count": n, "with_errors": err, "with_warnings": warn,
                    "quotes_verified": verified if quotes else None}
    out["reviews"] = review_state(home)
    hot = ex.home_path(home, cfg, "hot", "hot.md")
    if os.path.isfile(hot):
        age = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(hot))
        out["hot"] = "present, %d day(s) old" % age.days
    else:
        out["hot"] = "missing (py hot.py builds it)"
    log = ex.library().access_log_path(home)   # the path the MCP server writes
    out["access_log_lines"] = sum(1 for _ in open(log, encoding="utf-8", errors="replace")) \
        if os.path.isfile(log) else 0
    board = ws["board"]
    if os.path.isdir(board):
        bl = ex.base_script("board")
        counts = {}
        for t in bl.list_tickets(board, to=instance, include_terminal=False):
            counts[t.get("status")] = counts.get(t.get("status"), 0) + 1
        out["tickets"] = counts
        pk = ex.base_script("packets")
        out["open_packets"] = [p.get("packet") for p in
                               pk.list_packets(board, only_open=True, instance=instance)]
    return out


def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instance")
    ap.add_argument("--no-quotes", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    ws = ex.load_workspace_or_none()
    if not ws:
        sys.stderr.write("expert_status: workspace.json not found\n")
        return 2
    names = [args.instance] if args.instance else ex.expert_instances(ws)
    res = [status(ws, n, not args.no_quotes) for n in names if n in ws["instances"]]
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    for r in res:
        print("%s  home %s  config: %s" % (r["instance"], r["home"], r["config"]))
        lib = r.get("library")
        if isinstance(lib, dict):
            print("  library: %d cached, %d index rows; no row: %s" % (
                lib["cached"], lib["indexed"], ", ".join(lib["without_row"]) or "none"))
            c = r["cards"]
            print("  cards: %d (%d with errors, %d with warnings%s)" % (
                c["count"], c["with_errors"], c["with_warnings"],
                "" if c["quotes_verified"] is None else ", %d quotes verified"
                % c["quotes_verified"]))
            rv = r["reviews"]
            print("  reviews: %d pass(es); awaiting B: %s; no decision record: %s" % (
                rv["passes"], ", ".join(rv["awaiting_b"]) or "none",
                ", ".join(rv["undecided"]) or "none"))
            print("  hot.md: %s; access log: %d line(s)" % (r["hot"], r["access_log_lines"]))
        else:
            print("  library: %s" % lib)
        if "tickets" in r:
            print("  tickets to %s: %s; open packets: %s" % (
                r["instance"], ", ".join("%s %d" % kv for kv in sorted(r["tickets"].items()))
                or "none", ", ".join(r["open_packets"]) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
