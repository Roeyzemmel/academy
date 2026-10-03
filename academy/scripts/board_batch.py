"""board_batch.py -- apply a reviewed batch of board changes as the human, resumably.

    py board_batch.py BATCH.json [--dry-run] [--board DIR] [--state STATE.json]

A batch is a JSON file ``{"title": ..., "ops": [op, ...]}`` that Roey has reviewed. Every op
goes through the same code as the academy MCP tools, called as the human (any move, any
field; every thread line says ``human``), so the protocol, validation, the append-only
thread, blocks mirroring and, on the GitHub backend, labels, native links and assignees
all apply exactly as for a tool call. Ops:

    {"op": "update", "id": "T-0056", "status": ..., "reason": ..., "fields": {...},
     "note": ..., "reopen": ...}                  -> tickets_update
    {"op": "create", "as": "referee", "to": ..., "on_behalf_of": ..., "kind": ...,
     "title": ..., "ask": ..., "deliverable": ..., "refs": [...], "parent": ...,
     "note": ...}                                   -> tickets_create (``as`` names the id)
    {"op": "packet", "id": "P-0018", "fields": {"ticket": "${referee}"}}
                                                    -> a packet frontmatter field, validated

``${name}`` anywhere in an op is replaced by the id a previous ``create`` stored under that
name, so a batch can file a ticket and then point other tickets at it. Every op may carry
``"why"`` (documentation only; not sent).

``--dry-run`` copies the file board to a temporary directory and runs the whole batch there
(files backend), which proves every op passes the rules without touching the real board.
Without it the batch runs on the workspace's board (``board.backend``: files or github),
recording each finished op in STATE.json (default ``BATCH.state.json``), so a rerun after
a failure resumes at the failed op. Exit 0 when every op is done, 2 at the first refusal.
"""

import argparse
import copy
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "mcp"))

import academy_common as ac  # noqa: E402
from tools import Context, ToolError  # noqa: E402  (the academy MCP tools, not pip's mcp)
from tools import tickets as mt  # noqa: E402

RE_VAR = re.compile(r"\$\{([A-Za-z0-9_-]+)\}")
PASS = ("op", "as", "why")


class BatchError(Exception):
    pass


def substitute(value, names):
    if isinstance(value, str):
        def one(m):
            if m.group(1) not in names:
                raise BatchError("${%s} is used before a create named it" % m.group(1))
            return names[m.group(1)]
        return RE_VAR.sub(one, value)
    if isinstance(value, list):
        return [substitute(v, names) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, names) for k, v in value.items()}
    return value


def set_packet_fields(board, pid, fields):
    path = ac.find_packet(board, pid)
    if not path:
        raise BatchError("%s: no such packet" % pid)
    with open(path, encoding="utf-8", newline="") as fh:
        meta, body = ac.read_frontmatter(fh.read())
    for k, v in fields.items():
        if k not in meta:
            raise BatchError("%s: unknown packet field %r" % (pid, k))
        meta[k] = v
    probs = ac.validate_packet(meta, body)
    if probs:
        raise BatchError("%s would be invalid: %s" % (pid, "; ".join(probs)))
    ac.atomic_write(path, ac.write_frontmatter(meta, body))
    return {"id": pid, "set": sorted(fields)}


def run_op(ctx, op, names):
    op = substitute(op, names)
    args = {k: v for k, v in op.items() if k not in PASS}
    kind = op.get("op")
    if kind == "update":
        return mt.update_ticket(ctx, args)
    if kind == "create":
        out = mt.create_ticket(ctx, args)
        if op.get("as"):
            names[op["as"]] = out["id"]
        return out
    if kind == "packet":
        return set_packet_fields(ctx.board, args["id"], args.get("fields") or {})
    raise BatchError("unknown op %r" % kind)


def run(batch, ctx, state=None, state_path=None, log=print):
    """Apply the ops not yet done; returns the state. Raises BatchError at a refusal."""
    state = state if state is not None else {"done": 0, "names": {}}
    ops = batch["ops"]
    for i in range(state["done"], len(ops)):
        try:
            out = run_op(ctx, ops[i], state["names"])
        except (ToolError, ac.AcademyError, BatchError) as e:
            raise BatchError("op %d (%s %s): %s" % (i + 1, ops[i].get("op"),
                                                    ops[i].get("id") or ops[i].get("as") or "",
                                                    e))
        state["done"] = i + 1
        if state_path:
            ac.atomic_write(state_path, json.dumps(state, indent=1) + "\n")
        log("%3d. %-6s %s" % (i + 1, ops[i]["op"], json.dumps(
            {k: out.get(k) for k in ("id", "status", "thread", "set") if k in out},
            ensure_ascii=False)))
    return state


def human_context(workspace, store):
    return Context(agent="", workspace=workspace, store=store)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("batch")
    ap.add_argument("--dry-run", action="store_true",
                    help="run the whole batch on a temporary copy of the file board")
    ap.add_argument("--board", help="the file board to copy for --dry-run (default: the "
                                    "workspace's board directory)")
    ap.add_argument("--state", help="resume state (default: BATCH.state.json)")
    ap.add_argument("--workspace")
    a = ap.parse_args(argv)
    with open(a.batch, encoding="utf-8") as fh:
        batch = json.load(fh)
    ws = ac.load_workspace(a.workspace)
    try:
        if a.dry_run:
            tmp = tempfile.mkdtemp(prefix="board-batch-")
            try:
                copy_to = os.path.join(tmp, "board")
                shutil.copytree(a.board or ws["board"], copy_to,
                                ignore=shutil.ignore_patterns(".git"))
                ws2 = copy.deepcopy(ws)
                ws2["board"], ws2["board_config"] = copy_to, {}
                run(batch, human_context(ws2, ac.FileBoardStore(copy_to)))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            print("dry run: all %d op(s) pass on a copy of the file board" % len(batch["ops"]))
            return 0
        state_path = a.state or a.batch + ".state.json"
        state = None
        if os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as fh:
                state = json.load(fh)
        state = run(batch, human_context(ws, None), state, state_path)
        print("done: %d op(s); created %s" % (state["done"], state["names"] or "nothing"))
        return 0
    except BatchError as e:
        print("STOP: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
