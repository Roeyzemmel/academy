"""Per-agent token volume of one Claude Code session, for comparing pass costs.

Usage: py session_usage.py <session-id> [--project <dir-under-~/.claude/projects>]

Reads the session transcript and its subagent transcripts, and prints for the main
session and each subagent: turns, cache-read and cache-write tokens, the model(s), and
the number of turns lost to a session or usage limit. Output-token counts in the
transcripts are streaming snapshots and undercount, so they are not shown; cache reads
are the volume that grows with turns and context, and track the cost.
"""
import argparse
import collections
import glob
import json
import os
import sys

LIMIT_MARKERS = ("session limit", "usage limit", "rate limit")


def tally(path):
    t = collections.Counter()
    models = collections.Counter()
    seen = set()
    for line in open(path, encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        if m.get("model") == "<synthetic>":
            c = m.get("content")
            text = c[0].get("text", "") if isinstance(c, list) and c else str(c)
            if any(k in text.lower() for k in LIMIT_MARKERS):
                t["limit_failures"] += 1
            continue
        u = m.get("usage")
        if not u or m.get("id") in seen:
            continue
        seen.add(m.get("id"))
        t["turns"] += 1
        models[m.get("model")] += 1
        t["read"] += u.get("cache_read_input_tokens", 0) or 0
        t["write"] += (u.get("cache_creation_input_tokens", 0) or 0) + (u.get("input_tokens", 0) or 0)
    return t, models


def row(name, t, models, extra=""):
    ms = ",".join(sorted(k.replace("claude-", "") for k in models if k))
    print(f"{name:28s} turns={t['turns']:4d} read={t['read'] // 1000:7d}k "
          f"write={t['write'] // 1000:6d}k limit={t['limit_failures']:2d} {ms:18s} {extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--project", help="directory name under ~/.claude/projects; default: the one holding the session")
    a = ap.parse_args()
    root = os.path.expanduser("~/.claude/projects")
    if a.project:
        base = os.path.join(root, a.project)
    else:
        hits = glob.glob(os.path.join(root, "*", a.session + ".jsonl"))
        if not hits:
            sys.exit(f"no transcript {a.session}.jsonl under {root}")
        base = os.path.dirname(hits[0])

    t, m = tally(os.path.join(base, a.session + ".jsonl"))
    row("MAIN", t, m)
    total = collections.Counter(t)
    by_type = collections.defaultdict(collections.Counter)
    rows = []
    for meta in glob.glob(os.path.join(base, a.session, "subagents", "*.meta.json")):
        md = json.load(open(meta, encoding="utf-8"))
        t, m = tally(meta[: -len(".meta.json")] + ".jsonl")
        rows.append((md.get("agentType", "?"), md.get("spawnDepth"), md.get("description", ""), t, m))
    for typ, depth, desc, t, m in sorted(rows, key=lambda r: -r[3]["read"]):
        row(f"{typ} d{depth}", t, m, desc[:50])
        by_type[typ].update(t)
        by_type[typ]["n"] += 1
        total.update(t)
    print("-- by agent type")
    for typ, t in sorted(by_type.items(), key=lambda x: -x[1]["read"]):
        row(f"{typ} x{t['n']}", t, {})
    print(f"-- total: {len(rows)} subagents, read={total['read'] // 1000}k "
          f"write={total['write'] // 1000}k, limit failures={total['limit_failures']}")


if __name__ == "__main__":
    main()
