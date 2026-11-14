"""maintain.py -- the measured parts of a maintenance round on the academy's own code.

    py maintain.py survey [--days 7] [--json] [--workspace W] [--no-probes]
    py maintain.py union --base BRANCH --branches B1 B2 ... [--repo DIR] [--json]

A maintenance round (``/academy:maintain``, ``academy/workflows/maintain.js``) finds what
is worth doing in the plugins, does each thing on its own branch, and proves the branches
work together. The judgement is the agents'; what can be measured is here, so that a round
starts from numbers and ends on a tested tree (the round of 2026-11-13 was done by hand:
docs/error-ledger-review-2026-11-13.md).

``survey`` lists **candidates**, each with its evidence:

* ``error``: the families of the error ledger with an error in the window or a
  regression (``error_ledger.brief``), regressions and recurring ones first;
* ``slow`` / ``large``: the commands a session runs or reads every day (``PROBES``, and
  each instance's ``inbox.py --json``), run against the live board and held to a budget
  of seconds and of characters. A command over budget costs every session that runs it;
* ``definition``: an agent, skill or command frontmatter value that YAML would not read
  whole (``frontmatter_problems``: an undoubled apostrophe, an unclosed quote, `` #``,
  ``: ``). The harness drops such a definition silently (2026-11-13: a grader ran two
  weeks without its tool list);
* ``hygiene``: a worktree of the academy repo left behind.

A probe only reads. ``--no-probes`` skips them (no board, or a run that must be quick).

``union`` answers "do these branches work together": in a throwaway worktree at ``--base``
(detached, removed afterwards) it merges each branch in turn and runs the repo's push
gate (``ci_local.run``) on the result. Branches made side by side from one base are each
gated alone; the union is what will be on ``main`` once all are merged. It creates no
branch, pushes nothing and leaves the checkout untouched. Exit 0 when every merge was
clean and the gate passed, 1 otherwise, 2 on an error.

It stands alone: it imports no other script, reads ``workspace.json`` itself, and runs
``error_ledger.py`` and ``ci_local.py`` (beside it) as commands.

Standard library only.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
BASE_SCRIPTS = HERE


class MaintainError(Exception):
    pass


def load_workspace(path=None, environ=None, cwd=None):
    """The workspace map as this script needs it: ``{"_path", "board", "instances"}``.
    ``path``, else ``ACADEMY_WORKSPACE``, else the first ``workspace.json`` found going up
    from the current directory. ``board`` is its directory (``board.path`` when the board
    is an object); an instance is ``{"role", "home"}``."""
    env = os.environ if environ is None else environ
    path = path or env.get("ACADEMY_WORKSPACE")
    d = os.path.abspath(cwd or os.getcwd())
    while not path:
        if os.path.isfile(os.path.join(d, "workspace.json")):
            path = os.path.join(d, "workspace.json")
        elif os.path.dirname(d) == d:
            raise MaintainError("no workspace.json here or above (give --workspace)")
        d = os.path.dirname(d)
    try:
        with open(path, encoding="utf-8-sig") as fh:
            ws = json.load(fh)
    except (OSError, ValueError) as exc:
        raise MaintainError("cannot read %s: %s" % (path, exc))
    board = ws.get("board")
    if isinstance(board, dict):
        board = board.get("path")
    root = os.path.dirname(os.path.abspath(path))
    if isinstance(board, str) and not os.path.isabs(board):
        board = os.path.join(root, board)
    return {"_path": os.path.abspath(path), "board": board,
            "instances": {k: v for k, v in (ws.get("instances") or {}).items()
                          if isinstance(v, dict)}}

#: a command a session waits for: seconds before it is a candidate
BUDGET_SECONDS = 5.0
#: a command a session reads: characters before it is a candidate (about 5 000 tokens)
BUDGET_CHARS = 20000
PROBE_TIMEOUT = 180
#: (name, script relative to the academy repo, arguments): read-only, run from the
#: workspace root against the live board
PROBES = (
    ("academy_status", "academy/scripts/academy_status.py", []),
    ("cowork list", "academy/scripts/cowork.py", ["list"]),
    ("board list", "academy/scripts/board.py", ["list"]),
    ("packets list --open", "academy/scripts/packets.py", ["list", "--open"]),
    ("packets list --open --json --brief", "academy/scripts/packets.py",
     ["list", "--open", "--json", "--brief"]),
    ("decisions batches --json", "academy/scripts/decisions.py", ["batches", "--json"]),
    ("error_ledger report", "academy/scripts/error_ledger.py", ["report"]),
    ("error_ledger report --json --brief", "academy/scripts/error_ledger.py",
     ["report", "--json", "--brief"]),
    ("usage_report", "academy/scripts/usage_report.py", ["--days", "7"]),
)


# ----------------------------------------------------------------------------
# Definitions the harness must be able to read
# ----------------------------------------------------------------------------

def scalar_problem(value):
    """Why YAML would not read ``value`` (the text after ``key:``) whole, or None.

    Not a YAML parser (the suites are standard-library only): the ways a one-line value
    goes wrong. A plain value holding ``: `` is refused too (strict YAML reads a mapping
    there), although the harness has tolerated it."""
    v = value.strip()
    if not v or v[0] in "[{|>":
        return None
    if v[0] == "'":
        i, inner = 0, v[1:]
        while i < len(inner):
            if inner[i] == "'":
                if inner[i + 1:i + 2] == "'":
                    i += 2
                    continue
                rest = inner[i + 1:].strip()
                if not rest or rest.startswith("#"):
                    return None
                return ("the single-quoted text ends at an apostrophe that is not doubled: "
                        "...%s" % inner[max(0, i - 25):i + 12])
            i += 1
        return "the single-quoted text never closes"
    if v[0] == '"':
        if re.match(r'"(?:[^"\\]|\\.)*"\s*(#.*)?$', v):
            return None
        return "the double-quoted text is not closed exactly once"
    if " #" in v:
        return "a plain value holds ' #', where a comment starts: quote the value"
    if ": " in v or v.endswith(":"):
        return "a plain value holds ': ', where a mapping starts: quote the value"
    if v[0] in "&*!%@`":
        return "a plain value starts with %r: quote the value" % v[0]
    return None


def frontmatter_files(repo=REPO):
    out = []
    for pat in ("*/agents/*.md", "*/skills/*/SKILL.md", "domains/*/skills/*/SKILL.md",
                "*/commands/*.md"):
        out += glob.glob(os.path.join(repo, pat))
    return sorted(out)


def frontmatter_problems(repo=REPO):
    """``["<file>: <key>: <why>"]`` for every agent, skill and command of ``repo``."""
    problems = []
    for path in frontmatter_files(repo):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if not m:
            problems.append("%s: no frontmatter" % rel)
            continue
        for ln in m.group(1).splitlines():
            km = re.match(r"^([A-Za-z_-]+):(.*)$", ln)
            if not km:
                if ln.strip() and not ln.startswith((" ", "-", "#")):
                    problems.append("%s: not a 'key: value' line: %s" % (rel, ln[:60]))
                continue
            why = scalar_problem(km.group(2))
            if why:
                problems.append("%s: %s: %s" % (rel, km.group(1), why))
    return problems


# ----------------------------------------------------------------------------
# Survey
# ----------------------------------------------------------------------------

def run_probe(argv, cwd, timeout=PROBE_TIMEOUT, clock=time.time):
    """``{"seconds", "chars", "exit"}`` of one read-only command (``exit`` None on a
    timeout or when it could not start)."""
    start = clock()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL,
                           timeout=timeout)
        out, code = len(p.stdout.decode("utf-8", "replace")), p.returncode
    except (subprocess.TimeoutExpired, OSError):
        out, code = 0, None
    return {"seconds": round(clock() - start, 2), "chars": out, "exit": code}


def probe_plan(ws, repo=REPO):
    """``[(name, argv, cwd)]``: the fixed probes and each instance's inbox listing."""
    root = os.path.dirname(os.path.abspath(ws.get("_path") or ws.get("path") or ""))
    cwd = root if os.path.isdir(root) else os.getcwd()
    plan = [(name, [sys.executable, os.path.join(repo, rel)] + args, cwd)
            for name, rel, args in PROBES]
    for inst, row in sorted((ws.get("instances") or {}).items()):
        script = os.path.join(repo, str(row.get("role")), "scripts", "inbox.py")
        if os.path.isfile(script) and os.path.isdir(str(row.get("home"))):
            plan.append(("inbox %s" % inst, [sys.executable, script, "--json", "--home",
                                             row["home"]], row["home"]))
    return plan


def probe_candidates(results, seconds=BUDGET_SECONDS, chars=BUDGET_CHARS):
    """Candidates from ``[(name, result)]``: over the time budget, over the size budget,
    or a probe that failed (a daily command that does not run is the first thing to fix)."""
    out = []
    for name, r in results:
        if r["exit"] is None:
            out.append({"kind": "slow", "id": "probe:" + name, "title": "%s did not finish" % name,
                        "evidence": "no result within %d s" % PROBE_TIMEOUT})
            continue
        if r["exit"] not in (0, 1):
            out.append({"kind": "error", "id": "probe:" + name,
                        "title": "%s exits %s" % (name, r["exit"]),
                        "evidence": "a command sessions run daily fails on this board"})
        if r["seconds"] > seconds:
            out.append({"kind": "slow", "id": "slow:" + name,
                        "title": "%s takes %.1f s" % (name, r["seconds"]),
                        "evidence": "budget %.0f s; measured %.1f s" % (seconds, r["seconds"])})
        if r["chars"] > chars:
            out.append({"kind": "large", "id": "large:" + name,
                        "title": "%s prints %d characters" % (name, r["chars"]),
                        "evidence": "budget %d; a session reads all of it" % chars})
    return out


def ledger_brief(ws_path, days=7, scripts=BASE_SCRIPTS):
    """The base plugin's ``error_ledger.py report --json --brief``, as a dict."""
    p = subprocess.run([sys.executable, os.path.join(scripts, "error_ledger.py"), "report",
                        "--days", str(days), "--json", "--brief", "--workspace", ws_path],
                       capture_output=True, text=True, timeout=PROBE_TIMEOUT,
                       stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    if p.returncode:
        raise MaintainError((p.stderr or p.stdout).strip()[-300:] or "exit %d" % p.returncode)
    return json.loads(p.stdout)


def error_candidates(ws_path, days=7, brief=ledger_brief):
    try:
        rep = brief(ws_path, days)
    except Exception as exc:        # the ledger is optional; the survey goes on without it
        return [], "error ledger not read: %s" % exc
    rank = {"regression": 0, "recurring": 1}
    fams = sorted(rep["families"], key=lambda f: (rank.get(f["state"], 2), -f["bursts"]))
    return [{"kind": "error", "id": "ledger:" + f["family"],
             "title": "%s (%s)" % (f["family"], f["state"]),
             "evidence": "%d in the window, %d burst(s), %d session(s); e.g. %s"
                         % (f["in_window"], f["bursts"], f["sessions"], f["example"])}
            for f in fams], None


def worktree_candidates(repo=REPO):
    try:
        out = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo,
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    trees = [ln[len("worktree "):] for ln in out.splitlines() if ln.startswith("worktree ")]
    return [{"kind": "hygiene", "id": "worktree:" + os.path.basename(t),
             "title": "a worktree is left at %s" % t,
             "evidence": "remove it once its branch is pushed and clean (git worktree remove)"}
            for t in trees[1:]]


def survey(ws=None, days=7, probes=True, repo=REPO, run=run_probe, brief=ledger_brief):
    """``{"candidates": [...], "probes": [...], "notes": [...]}``."""
    notes, cands, measured = [], [], []
    for p in frontmatter_problems(repo):
        cands.append({"kind": "definition", "id": "definition:" + p.split(":")[0],
                      "title": "the harness cannot read " + p.split(":")[0], "evidence": p})
    board = (ws or {}).get("board")
    if isinstance(board, str) and os.path.isdir(board):
        found, note = error_candidates(ws["_path"], days, brief)
        cands += found
        if note:
            notes.append(note)
    else:
        notes.append("no board directory: the error ledger was not read")
    if probes and ws:
        for name, argv, cwd in probe_plan(ws, repo):
            measured.append((name, run(argv, cwd)))
        cands += probe_candidates(measured)
    elif not probes:
        notes.append("probes skipped (--no-probes)")
    cands += worktree_candidates(repo)
    return {"candidates": cands, "notes": notes,
            "probes": [dict(r, name=name) for name, r in measured]}


def render_survey(s):
    out = ["%d candidate(s)" % len(s["candidates"])]
    for c in s["candidates"]:
        out.append("%-10s %s\n           %s" % (c["kind"], c["title"], c["evidence"][:200]))
    if s["probes"]:
        out.append("probes (seconds, characters):")
        out += ["  %6.1f %8d  %s" % (r["seconds"], r["chars"], r["name"]) for r in s["probes"]]
    out += ["note: " + n for n in s["notes"]]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# Union
# ----------------------------------------------------------------------------

def _git(cwd, *args):
    p = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True,
                       timeout=300, stdin=subprocess.DEVNULL)
    return p.returncode, (p.stdout + p.stderr).strip()


def push_gate(tree, scripts=BASE_SCRIPTS):
    """The repo's push gate on ``tree`` (the base plugin's ``ci_local.py run``):
    ``(ok, lines)``."""
    p = subprocess.run([sys.executable, os.path.join(scripts, "ci_local.py"), "run", "--repo",
                        tree], capture_output=True, text=True, timeout=3600,
                       stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    return p.returncode == 0, (p.stdout + p.stderr).strip().splitlines()


def union(repo, base, branches, gate=push_gate):
    """Merge ``branches`` in turn onto ``base`` in a throwaway detached worktree and run
    the push gate there. Returns ``{"ok", "merged", "conflict", "gate_ok", "gate"}``."""
    res = {"ok": False, "base": base, "merged": [], "conflict": None, "gate_ok": None,
           "gate": []}
    holder = tempfile.mkdtemp(prefix="academy-union-")
    tree = os.path.join(holder, "tree")
    code, out = _git(repo, "worktree", "add", "--detach", tree, base)
    if code:
        shutil.rmtree(holder, ignore_errors=True)
        raise MaintainError("cannot check out %s: %s" % (base, out))
    try:
        for b in branches:
            code, out = _git(tree, "-c", "user.name=union", "-c", "user.email=union@localhost",
                             "merge", "--no-ff", "--no-edit", b)
            if code:
                _git(tree, "merge", "--abort")
                res["conflict"] = {"branch": b, "detail": out[-600:]}
                return res
            res["merged"].append(b)
        ok, lines = gate(tree)
        res["gate_ok"], res["gate"] = bool(ok), [ln for ln in lines if "skipped" not in ln]
        res["ok"] = bool(ok)
        return res
    finally:
        _git(repo, "worktree", "remove", "--force", tree)
        shutil.rmtree(holder, ignore_errors=True)


def render_union(r):
    out = ["union on %s: %s" % (r["base"], "ok" if r["ok"] else "NOT ok")]
    out += ["  merged " + b for b in r["merged"]]
    if r["conflict"]:
        out.append("  CONFLICT merging %s:\n    %s" % (r["conflict"]["branch"],
                                                      r["conflict"]["detail"].replace("\n", "\n    ")))
    out += ["  " + ln for ln in r["gate"]]
    return "\n".join(out) + "\n"


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("survey", help="candidates for a maintenance round, with evidence")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    p.add_argument("--workspace")
    p.add_argument("--no-probes", action="store_true")
    p = sub.add_parser("union", help="merge branches in a throwaway worktree and gate the result")
    p.add_argument("--base", required=True)
    p.add_argument("--branches", nargs="+", required=True)
    p.add_argument("--repo", default=REPO)
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "survey":
            try:
                ws = load_workspace(a.workspace)
            except MaintainError:
                ws = None
            s = survey(ws, a.days, not a.no_probes)
            print(json.dumps(s, ensure_ascii=False) if a.json else render_survey(s), end="")
            return 0
        r = union(os.path.abspath(a.repo), a.base, a.branches)
        print(json.dumps(r, ensure_ascii=False) if a.json else render_union(r), end="")
        return 0 if r["ok"] else 1
    except (MaintainError, OSError) as exc:
        print("maintain: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
