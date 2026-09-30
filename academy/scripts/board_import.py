"""board_import.py -- GitHub issue dump -> file board (the way back).

    py board_import.py --issues dump.json [--board DIR] [--dry-run]

Writes one ticket file per issue (``<to>/T-NNNN-<slug>.md``), keeping the path of a file
that already exists; placeholders are skipped. Use it to back up a GitHub board as files
or to return to the file backend. Same dump format as ``board_verify.py``. Nothing is
committed.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402


def run(board, records, dry=False):
    existing = {}
    for path, meta, _b in bd.iter_tickets(board):
        if meta is not None:
            existing[meta["id"]] = path
    wrote = []
    for r in records:
        if "placeholder" in bc.label_names(r["issue"].get("labels")):
            continue
        meta, body = bc.decode(r["issue"], r["comments"])
        probs = ac.validate_ticket(meta, body)
        if probs:
            raise SystemExit("%s: %s" % (meta["id"], "; ".join(probs)))
        path = existing.get(meta["id"]) or os.path.join(
            board, meta["to"], ac.ticket_filename(meta["id"], meta["title"]))
        wrote.append(path)
        if not dry:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            bd.write_ticket(path, meta, body)
    return wrote


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--board")
    ap.add_argument("--issues", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    with open(a.issues, encoding="utf-8") as fh:
        recs = json.load(fh)
    wrote = run(bd.resolve_board(a.board), recs, a.dry_run)
    print("%s %d ticket file(s)" % ("would write" if a.dry_run else "wrote", len(wrote)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
