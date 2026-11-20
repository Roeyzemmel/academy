"""The inbox core: one implementation behind every role's ``inbox.py``.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import json
import os
import re
import sys
import tempfile

from ._base import (
    AcademyError, CONFIG_REL, ConfigError, ROLES, _PKG_DIR, _norm, _same_file, find_home)
from ._config import instance_for_home, load_config
from ._workspace import load_workspace
from ._touched import claim_touches, drop_touches
from ._manifest import (ManifestError, find_claim, load_pending, manifest_changed,
                        manifest_targets, merge_manifest, prune_claims, release_claim,
                        save_pending)
from ._tickets import is_dead_route, relay_return_ready
from ._store import FileBoardStore, as_store, board_dir, open_store, status_lookup

# ----------------------------------------------------------------------------
# The inbox core (docs/protocol.md section 4; campaign-mode design sections 8, 10)
# ----------------------------------------------------------------------------

class inbox_core(object):
    """Selection, ordering, return legs, the blocked filter and the serial checkpoint.

    Every role's ``inbox.py`` is a thin wrapper over this: it resolves its instance and
    its limit, and supplies ``route(meta) -> {how, target, why}`` (its routing table,
    ``routes.py``); ``how`` is ``skill``, ``agent``, ``human`` or ``reject``. A route may
    add ``over_budget`` (a reason string), which the row carries at top level.

    ``select`` takes, in order: the instance's in-progress tickets (unfinished work is
    resumed before anything new starts), relay parents ready for their return leg
    (``relay_return_ready``), then ``open`` and ``accepted`` tickets. Each group is
    ordered by priority, then agenda position (a ticket that has an ``agenda`` field
    first, or ``position(meta)`` when the wrapper knows the agenda), then id. Dead-route
    blocked tickets (both ``blocked_by`` and ``reopen_if``) and pending blocked ones
    are never taken. The limit is at most 3, except for a workplan: a campaign
    (``campaign`` names its target; only tickets carrying ``campaign: <target>`` are
    listed) or a cowork (``cowork``, its slug, the same way; academy/lib/workplan.py).
    """

    TAKE = ("open", "accepted")
    SHOW = ("open", "accepted", "in-progress", "blocked")
    MAX = 3
    PRIORITY = {"high": 0, "normal": 1, "low": 2}
    RETURN_WHY = ("return leg: the child is back; close it and deliver this ticket "
                  "with a result pointing at it")

    is_dead_route = staticmethod(is_dead_route)

    @staticmethod
    def num(x):
        """The number of a ticket id, or of a meta's ``id`` (0 when there is none)."""
        tid = x.get("id", "T-0") if isinstance(x, dict) else x
        try:
            return int(str(tid).split("-")[1])
        except (IndexError, ValueError):
            return 0

    _num = num

    @staticmethod
    def prio(meta):
        """Sort rank of a ticket's priority (high first)."""
        return inbox_core.PRIORITY.get(meta.get("priority") or "normal", 1)

    @staticmethod
    def clamp(n):
        """An items-per-run setting as a count: at least 1, at most ``MAX`` (3)."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = inbox_core.MAX
        return max(1, min(n or inbox_core.MAX, inbox_core.MAX))

    @staticmethod
    def unfinished(rows):
        """Ids of the in-progress rows: work started and not yet settled."""
        return [r["id"] for r in rows if r.get("status") == "in-progress"]

    @staticmethod
    def select(board, instance, limit=3, all=False, route=None, campaign=None,
               position=None, return_legs=True, position_first=False, extra=None,
               cowork=None):
        """``(rows, total)``: the tickets to handle, and how many were eligible.

        ``all`` lists every open, accepted, in-progress and blocked ticket without the
        cut, in-progress first, then blocked, then open and accepted (blocked ones carry
        ``blocked``: ``pending`` or ``dead-route``). ``position_first`` orders by agenda
        position before priority (the Author's precedence is the paper's order).
        ``extra`` is a list of finished rows the wrapper builds itself (the Author's
        landing legs, see ``extra_row``); they follow the in-progress rows and count
        against the cut. With ``campaign`` only tickets carrying that campaign are
        listed, so a non-campaign in-progress ticket is not among them: ``outside_campaign``
        finds those.
        """
        pos = position or (lambda m: 0 if m.get("agenda") else 10 ** 9)
        store = as_store(board)
        status_of = status_lookup(store)
        pool = []
        for m in store.read_all(instance):
            st = m.get("status")
            if campaign and m.get("campaign") != campaign:
                continue
            if cowork and m.get("cowork") != cowork:
                continue
            dead = is_dead_route(m)
            ret = False
            if all:
                if st not in inbox_core.SHOW:
                    continue
                group = 0 if st == "in-progress" else 2 if st in inbox_core.TAKE else 1
                # a listing without the cut still marks a relay ready for its return leg
                # (live run 2026-10-31: --ids showed T-0900 pending after its child was delivered)
                ret = bool(st == "blocked" and return_legs and not dead
                           and relay_return_ready(m, status_of))
            elif dead:
                continue
            elif st == "in-progress":
                group = 0
            elif st in inbox_core.TAKE:
                group = 2
            elif (st == "blocked" and return_legs
                  and relay_return_ready(m, status_of)):
                group, ret = 1, True
            else:
                continue
            m["_group"] = group
            m["_return"] = ret
            m["_blocked"] = ("dead-route" if dead else "pending") if st == "blocked" else None
            pool.append(m)
        prio, num = inbox_core.prio, inbox_core.num
        pool.sort(key=lambda m: ((m["_group"], pos(m), prio(m), num(m))
                                 if position_first else
                                 (m["_group"], prio(m), pos(m), num(m))))
        rows = [inbox_core._row(m, route) for m in pool]
        if extra:
            first = next((i for i, r in enumerate(rows) if r["status"] != "in-progress"),
                         len(rows))
            rows[first:first] = list(extra)
        total = len(rows)
        if not all:
            n = max(1, int(limit))
            rows = rows[:n if (campaign or cowork) else min(n, inbox_core.MAX)]
        return rows, total

    @staticmethod
    def takeable(row):
        """True for a row the inbox may take: open, accepted or in-progress, a relay's
        return leg, or a released or landing row a wrapper built (``extra_row``)."""
        return (row.get("status") in inbox_core.TAKE + ("in-progress",)
                or bool(row.get("return")) or bool(row.get("released")))

    @staticmethod
    def outside_campaign(board, instance, campaign, field="campaign"):
        """Ids of the instance's in-progress tickets that do not carry ``campaign`` (in
        ``field``: ``campaign`` or ``cowork``): the workplan listing leaves them out,
        but they are unfinished work all the same."""
        return [m["id"] for m in as_store(board).read_all(instance)
                if m.get("status") == "in-progress" and m.get(field) != campaign]

    @staticmethod
    def _row(m, route):
        """The inbox row of ticket ``m`` (``route``: a callable on the meta, or a route dict)."""
        r = dict(route(m) if callable(route) else route) if route else {
            "how": "human", "target": "human", "why": "no routing table"}
        over = r.pop("over_budget", None)
        if m.get("_return"):
            r["why"] = inbox_core.RETURN_WHY
        return {"id": m.get("id"), "kind": m.get("kind"), "status": m.get("status"),
                "priority": m.get("priority") or "normal", "from": m.get("from"), "to": m.get("to"),
                "parent": m.get("parent") or "", "final_to": m.get("final_to") or "",
                "title": m.get("title"), "agenda": m.get("agenda"),
                "budget": m.get("budget"), "refs": m.get("refs") or [],
                "campaign": m.get("campaign"), "cowork": m.get("cowork"), "route": r, "return": bool(m.get("_return")),
                "over_budget": over, "blocked": m.get("_blocked"), "path": m.get("_path")}

    @staticmethod
    def extra_row(m, route, returned=False, released=False, **override):
        """The row of a ticket a wrapper selects itself (``extra`` of ``select``): the core's
        row shape, ``route`` the already-decided route dict, ``returned`` a landing leg
        (``return: true``), ``released`` a blocked ticket whose waits are all back
        (``released: true``). ``override`` replaces any field of the row (the Author's landing
        rows are ``from`` the landing instance and ``delivered``)."""
        m = dict(m, _return=False, _blocked=None)
        row = inbox_core._row(m, route)
        row["return"] = bool(returned)
        if released:
            row["released"] = True
        row.update(override)
        return row

    @staticmethod
    def serial_checkpoint(meta):
        """Where a ticket stands after its route ran, and whether it is settled.

        Settled: delivered (with a result), blocked with its reason, rejected. A ticket
        still open, accepted or in-progress is *unfinished*: report it, do not take
        another ticket while it is (it comes first in the next run).
        """
        st = meta.get("status")
        problem = None
        if st in ("delivered", "closed"):
            state = "delivered"
            if not meta.get("result"):
                problem = "delivered without a result"
        elif st in ("rejected", "cancelled"):
            state = "rejected"
        elif st == "blocked":
            state = "blocked"
            if not (meta.get("waiting_on") or inbox_core.is_dead_route(meta)):
                problem = "blocked without a reason (waiting_on, or blocked_by and reopen_if)"
        else:
            state = "unfinished"
        return {"id": meta.get("id"), "status": st, "state": state, "problem": problem,
                "unfinished": state == "unfinished" or problem is not None}

    @staticmethod
    def check(board, tid):
        return inbox_core.serial_checkpoint(as_store(board).get(tid)[1])

    #: seconds the workspace's ship.py checkpoint may take before it is abandoned: below
    #: the agent shell's default command timeout (120 s), so the --check call that runs it
    #: still returns its own result in time
    SHIP_TIMEOUT = 90
    #: the ticket states (``serial_checkpoint``) after which the role's work is finished
    SHIP_STATES = ("delivered", "rejected")

    @staticmethod
    def ship_checkpoint(args, instance, board, r, role=None, out=None):
        """After ``--check`` found ticket ``r`` finished (delivered or closed, rejected or
        cancelled, with no problem), run the academy's ``ship.py --workspace <root>
        checkpoint --ticket <id> --role <role> --only <the ticket's repos>`` in the
        workspace root, so the ticket's work is committed and pushed on its own branch
        (``ship_script``: this academy checkout's ``academy/scripts/ship.py``, else
        ``$ACADEMY_ROOT``'s, else the workspace's ``scripts/ship.py`` shim).

        Only for the workspace's own board, when ship.py exists, workspace.json does not
        say ``"shipCheckpoint": false``, and the session (``$CLAUDE_PROJECT_DIR``, else the
        cwd) is inside the workspace root and not in a worktree under it
        (``_session_inside``); otherwise one line gives the scoped command to run by hand.
        ``role``: given, else the role of ``instance``, else of the ticket's addressee. The
        repos (``--only``): the instance's home submodule, ``board`` (a submodule, or the
        workspace's own ``board/`` directory), and ``library`` for the Expert; a home that
        is no submodule leaves ``board`` only, said on stderr. Plus ``--touched``: the
        files the role wrote in another role's home while it worked this ticket, from the
        touch ledger (``_touched_scope``; ship.py commits those paths only, and an entry
        is dropped once its repo's line says pushed or unchanged). Never
        fatal and never raises: anything that goes wrong is one warning line on stderr; the
        --check result is unchanged."""
        try:
            return inbox_core._ship_checkpoint(args, instance, board, r, role, out)
        except Exception as exc:                     # noqa: BLE001 -- never break --check
            try:
                sys.stderr.write("warning: ship.py checkpoint for %s failed: %s: %s\n"
                                 % (r.get("id"), type(exc).__name__, exc))
            except Exception:                        # noqa: BLE001
                pass
            return None

    #: tests point this (or ``$ACADEMY_SHIP_SCRIPT``) at a stub; None: looked up
    SHIP_SCRIPT = None

    @staticmethod
    def ship_script(root):
        """The ship.py to run for the workspace at ``root``: ``SHIP_SCRIPT`` or
        ``$ACADEMY_SHIP_SCRIPT`` if set, else ``academy/scripts/ship.py`` of the academy
        checkout this module belongs to (the lib module and every plugin's vendored copy
        sit two levels below it), else of ``$ACADEMY_ROOT``, else the workspace's own
        ``scripts/ship.py`` (a shim); None if none exists."""
        given = inbox_core.SHIP_SCRIPT or os.environ.get("ACADEMY_SHIP_SCRIPT")
        if given:
            return given if os.path.isfile(given) else None
        mine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_PKG_DIR))))
        for base in (mine, os.environ.get("ACADEMY_ROOT")):
            if base:
                cand = os.path.join(base, "academy", "scripts", "ship.py")
                if os.path.isfile(cand):
                    return cand
        cand = os.path.join(root, "scripts", "ship.py")
        return cand if os.path.isfile(cand) else None

    @staticmethod
    def _gitmodule_paths(root):
        """The submodule paths of the workspace at ``root`` (its ``.gitmodules``)."""
        subs = []
        try:
            with open(os.path.join(root, ".gitmodules"), encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"^\s*path\s*=\s*(.+?)\s*$", line)
                    if m:
                        subs.append(m.group(1).replace("\\", "/"))
        except OSError:
            pass
        return subs

    @staticmethod
    def _touched_scope(root, ticket, role, name, only):
        """``(touched, by_sub, stray)`` for the checkpoint of ``ticket``: the touch-ledger
        entries of this ticket (``claim_touches``: those already claimed for it, and the
        unclaimed ones of ``role`` / instance ``name``), grouped by the submodule holding
        each file. ``touched``: the ``SUB:PATH`` arguments for the submodules outside
        ``only`` (a submodule in ``only`` is committed whole anyway); ``by_sub``: ``{sub:
        [entry files]}``, dropped once that sub's line says pushed or unchanged; ``stray``:
        the entry files of paths in no submodule (nothing can ship them; dropped, and
        said)."""
        def real(p):
            return os.path.normcase(os.path.realpath(p))
        subs = sorted(inbox_core._gitmodule_paths(root), key=len, reverse=True)
        top = real(root)
        touched, by_sub, stray = [], {}, []
        for f, rec in claim_touches(root, ticket, role, name):
            full = real(rec["path"])
            hit = None
            for s in subs:
                sp = real(os.path.join(root, s))
                if full.startswith(sp.rstrip(os.sep) + os.sep):
                    hit = s
                    break
            if not hit or not full.startswith(top.rstrip(os.sep) + os.sep):
                stray.append((f, rec["path"]))
                continue
            by_sub.setdefault(hit, []).append(f)
            if hit not in only:
                rel = os.path.relpath(full, real(os.path.join(root, hit))).replace(os.sep, "/")
                arg = "%s:%s" % (hit, rel)
                if arg not in touched:
                    touched.append(arg)
        return touched, by_sub, stray

    #: a ship.py checkpoint result line whose repo needs nothing more
    SHIPPED_LINE = re.compile(r"^(\S+) \S+ @ \S+ \(\d+ files\) (?:pushed|unchanged)\s*$")

    @staticmethod
    def _ship_scope(root, ws, name, role):
        """``(only, note)``: the targets of ``root`` a checkpoint of instance ``name``
        touches -- its home's submodule (``.gitmodules``), ``board`` (a submodule, or the
        workspace's board when that is a plain directory inside ``root``: ship.py then
        commits ``board/`` paths of the workspace repo only) and, for the Expert,
        ``library`` -- and a note when its home is not a submodule."""
        subs = inbox_core._gitmodule_paths(root)

        def real(p):
            return os.path.normcase(os.path.realpath(p))
        home = ((ws.get("instances") or {}).get(name) or {}).get("home") or ""
        home_sub = None
        if home:
            h = real(home)
            for s in subs:
                sp = real(os.path.join(root, s))
                if (h == sp or h.startswith(sp + os.sep)) and (
                        home_sub is None or len(s) > len(home_sub)):
                    home_sub = s
        only = [home_sub] if home_sub else []
        board_path = ws.get("board")
        if isinstance(board_path, dict):
            board_path = board_path.get("path")
        plain_board = False
        if isinstance(board_path, str) and board_path:
            b, top = real(board_path if os.path.isabs(board_path)
                          else os.path.join(root, board_path)), real(root)
            plain_board = (b.startswith(top.rstrip(os.sep) + os.sep) and os.path.isdir(b)
                           and not os.path.exists(os.path.join(b, ".git"))
                           and os.path.relpath(b, top).replace(os.sep, "/") not in subs)
        for s in ("board",) + (("library",) if role == "expert" else ()):
            if (s in subs or (s == "board" and plain_board)) and s not in only:
                only.append(s)
        note = None
        if not home_sub:
            note = ("the home of %s (%s) is not a submodule of %s"
                    % (name or "the instance", home or "unknown", root))
        return only, note

    @staticmethod
    def _ship_checkpoint(args, instance, board, r, role, out):
        try:
            ws = load_workspace(getattr(args, "workspace", None))
            if not _same_file(board_dir(board), ws["board"]):
                return None
        except AcademyError:
            return None
        if ws.get("shipCheckpoint") is False:
            return None
        root = os.path.realpath(os.path.dirname(ws["_path"]))
        # #101 part 1: a ticket the inbox snapshotted is shipped by its manifest, finished or not
        try:
            claim_file, claim = find_claim(root, r["id"])
            pending = load_pending(root, r["id"])
        except (ManifestError, OSError):
            claim_file, claim, pending = None, None, None
        by_manifest = bool(claim or pending)
        if not by_manifest and (r["unfinished"] or r["state"] not in inbox_core.SHIP_STATES):
            return None
        ship = inbox_core.ship_script(root)
        if not ship:
            return None
        insts = ws.get("instances", {})
        name = instance if instance in insts else None
        if not name:
            try:
                to = as_store(board).get(r["id"])[1].get("to") or ""
            except (AcademyError, OSError):
                to = ""
            if not role or (insts.get(to) or {}).get("role") == role:
                name = to
            else:
                mine = sorted(n for n, i in insts.items() if i.get("role") == role)
                name = mine[0] if len(mine) == 1 else None
        if not role:
            role = (insts.get(name) or {}).get("role") or (name or "").split("@", 1)[0]
        if role not in ROLES:
            sys.stderr.write("warning: ship.py checkpoint not run for %s: no role (%r)\n"
                             % (r["id"], role))
            return None
        if by_manifest:
            return inbox_core._ship_manifest(r, root, ws, ship, role, name, claim_file, claim,
                                             pending, out)
        only, note = inbox_core._ship_scope(root, ws, name, role)
        # the files this ticket's role wrote in another role's home (the touch ledger)
        touched, by_sub, stray = inbox_core._touched_scope(root, r["id"], role, name, only)
        if stray:
            drop_touches([f for f, _ in stray])
            sys.stderr.write("checkpoint for %s cannot ship %s: in no submodule of %s; "
                             "commit it by hand\n"
                             % (r["id"], ", ".join(p for _, p in stray), root))
        # every by-hand command is scoped: the unscoped manual run sweeps every dirty
        # submodule and is for the human or cloud session that owns the checkout
        by_hand = "py scripts/ship.py checkpoint --ticket %s --role %s --only %s" % (
            r["id"], role, " ".join(only) or "<your home submodule> board")
        if touched:
            by_hand += " --touched " + " ".join(touched)
        if not inbox_core._session_inside(root):
            sys.stderr.write("checkpoint not run: session is outside %s; run it by hand: %s\n"
                             % (root, by_hand))
            return None
        if not only:
            sys.stderr.write("checkpoint not run: no submodule of %s holds %s's work (%s); "
                             "run it by hand: %s\n" % (root, r["id"], note, by_hand))
            return None
        if note:
            sys.stderr.write("checkpoint for %s scoped to %s only: %s\n"
                             % (r["id"], " and ".join(only), note))
        if touched:
            sys.stderr.write("checkpoint for %s also ships what %s wrote in another role's "
                             "home: %s (those paths only)\n"
                             % (r["id"], role, " ".join(touched)))
        import subprocess
        cmd = [sys.executable, ship, "--workspace", root, "checkpoint", "--ticket", r["id"],
               "--role", role, "--only"] + only + (["--touched"] + touched if touched else [])
        # output goes to a file, not a pipe: a git grandchild holding a pipe open would
        # outlive the timeout's kill and hang the read
        with tempfile.TemporaryFile() as log:
            try:
                p = subprocess.run(cmd, cwd=root, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, timeout=inbox_core.SHIP_TIMEOUT)
            except subprocess.TimeoutExpired:
                sys.stderr.write("warning: ship.py checkpoint for %s timed out after %ss; "
                                 "run it by hand: %s\n"
                                 % (r["id"], inbox_core.SHIP_TIMEOUT, by_hand))
                return None
            except OSError as exc:
                sys.stderr.write("warning: ship.py checkpoint for %s could not start: %s; "
                                 "run it by hand: %s\n" % (r["id"], exc, by_hand))
                return None
            log.seek(0)
            text = log.read().decode("utf-8", "replace")
        if out is not None and text:
            out.write(text if text.endswith("\n") else text + "\n")
        done = set()
        for line in text.splitlines():
            m = inbox_core.SHIPPED_LINE.match(line)
            if m:
                done.add(m.group(1))
        # a shipped repo's entries are spent; a refused or failed one's stay with this
        # ticket, for its next --check
        drop_touches([f for sub, files in by_sub.items() if sub in done for f in files])
        if p.returncode != 0:
            sys.stderr.write("warning: checkpoint for %s exited %d (see its output). If a "
                             "repo is dirty on main: start a branch first with py "
                             "scripts/ship.py start <sub> <topic>, then re-run: %s\n"
                             % (r["id"], p.returncode, by_hand))
        return p.returncode

    @staticmethod
    def _manifest_target(targets, path):
        """``(target, relative path)`` of the home among ``targets`` (``manifest_targets``)
        holding ``path``, the longest match; ``(None, None)`` outside every home."""
        full = os.path.normcase(os.path.realpath(path))
        best = (None, None, -1)
        for target, repo, prefix in targets:
            base = os.path.normcase(os.path.realpath(os.path.join(repo, prefix) if prefix else repo))
            if full.startswith(base.rstrip(os.sep) + os.sep) and len(base) > best[2]:
                best = (target, os.path.relpath(full, base).replace(os.sep, "/"), len(base))
        return best[0], best[1]

    @staticmethod
    def _ship_manifest(r, root, ws, ship, role, name, claim_file, claim, pending, out):
        """The checkpoint of a ticket the inbox snapshotted (#101 part 1): its manifest is
        the claim's snapshot diff (``_manifest.manifest_changed``), plus a pending manifest
        a previous --check could not ship, plus the touch-ledger entries of the ticket; it
        is saved as the pending manifest, the claim is released (the ticket's run is over),
        and ``ship.py checkpoint --manifest`` commits exactly those paths in every home that
        has any. A finished ticket's commit is ``<id>: checkpoint``; an unfinished,
        blocked or problem one's is ``WIP: <id> unfinished (<outcome>)``. A target whose
        line says pushed or unchanged leaves the pending manifest (and its touch entries
        are dropped); the rest wait for the next --check of the ticket."""
        tid = r["id"]
        finished = not r["unfinished"] and r["state"] in inbox_core.SHIP_STATES
        wip = None if finished else (r.get("problem") or r.get("status") or r.get("state") or "unfinished")
        b = ws.get("board") or "board"
        targets = manifest_targets(root, b)
        touches, by_target = {}, {}
        for f, rec in claim_touches(root, tid, role, name):
            target, rel = inbox_core._manifest_target(targets, rec["path"])
            if target:
                touches.setdefault(target, []).append(rel)
                by_target.setdefault(target, []).append(f)
        prune_claims(root)
        changed = manifest_changed(root, claim) if claim else {}
        for target in (claim or {}).get("failed") or []:
            msg = ("checkpoint for %s: %s was unreadable at the snapshot (git status failed); "
                   "nothing of it is claimed: commit its part by hand\n" % (tid, target))
            (out or sys.stderr).write(msg)
        repos = merge_manifest(changed, (pending or {}).get("repos"), touches)
        path = save_pending(root, tid, repos)
        if claim_file:
            release_claim(claim_file)
        if not repos:
            drop_touches([f for fs in by_target.values() for f in fs])
            return 0
        by_hand = "py scripts/ship.py checkpoint --ticket %s --role %s --manifest %s%s" % (
            tid, role, path, (' --wip "%s"' % wip) if wip else "")
        if not inbox_core._session_inside(root):
            sys.stderr.write("checkpoint not run: session is outside %s; run it by hand: %s\n"
                             % (root, by_hand))
            return None
        sys.stderr.write("checkpoint for %s by its manifest%s: %s\n" % (
            tid, " (WIP: %s)" % wip if wip else "",
            " ".join("%s:%d" % (t, len(ps)) for t, ps in repos.items())))
        import subprocess
        cmd = [sys.executable, ship, "--workspace", root, "checkpoint", "--ticket", tid,
               "--role", role, "--manifest", path] + (["--wip", wip] if wip else [])
        with tempfile.TemporaryFile() as log:
            try:
                p = subprocess.run(cmd, cwd=root, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, timeout=inbox_core.SHIP_TIMEOUT)
            except subprocess.TimeoutExpired:
                sys.stderr.write("warning: ship.py checkpoint for %s timed out after %ss; "
                                 "run it by hand: %s\n" % (tid, inbox_core.SHIP_TIMEOUT, by_hand))
                return None
            except OSError as exc:
                sys.stderr.write("warning: ship.py checkpoint for %s could not start: %s; "
                                 "run it by hand: %s\n" % (tid, exc, by_hand))
                return None
            log.seek(0)
            text = log.read().decode("utf-8", "replace")
        if out is not None and text:
            out.write(text if text.endswith("\n") else text + "\n")
        done = set()
        for line in text.splitlines():
            m = inbox_core.SHIPPED_LINE.match(line)
            if m:
                done.add(m.group(1))
        if p.returncode == 0:
            done |= set(repos)
        save_pending(root, tid, {t: ps for t, ps in repos.items() if t not in done})
        drop_touches([f for t, fs in by_target.items() if t in done for f in fs])
        if p.returncode != 0:
            sys.stderr.write("warning: checkpoint for %s exited %d (see its output); its "
                             "manifest is kept for the next --check. If a repo is dirty on "
                             "main: start a branch first with py scripts/ship.py start <sub> "
                             "<topic>, then re-run: %s\n" % (tid, p.returncode, by_hand))
        return p.returncode

    #: a ticket id, for the branches that name it (``ticket_branch_re``)
    TICKET_ID = re.compile(r"^T-(\d+)$", re.I)
    #: a ship.py template branch: ``ship.py push`` can push it
    TEMPLATE_BRANCH = re.compile(r"^\d{4}-\d{2}-\d{2}/[a-z0-9][a-z0-9-]*/"
                                 r"(author|expert|researcher|scientist|human)$")

    @staticmethod
    def ticket_branch_re(ticket):
        """The pattern of the branch names that name ticket ``ticket`` (``T-0007``):
        ``t-0007``, ``t0007``, any case, the board's four-digit form only, as a word of the
        name (not preceded by a letter or digit, not followed by one): an academy issue
        branch such as ``t121-...`` must not hold board ticket T-0121 (review of 9f53a6e);
        None for anything but a ticket id."""
        m = inbox_core.TICKET_ID.match(str(ticket or "").strip())
        if not m:
            return None
        return re.compile(r"(?<![A-Za-z0-9])t-?%04d(?![A-Za-z0-9])" % int(m.group(1)), re.I)

    @staticmethod
    def _git(repo, *args):
        """``git --no-optional-locks -C repo args`` -> (returncode, stdout); never prompts,
        never refreshes an index on disk (a scan must not race a commit in a worktree)."""
        import subprocess
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat",
                   GCM_INTERACTIVE="never")
        for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(k, None)
        try:
            p = subprocess.run(["git", "--no-optional-locks", "-C", repo] + list(args),
                               capture_output=True, text=True, env=env,
                               stdin=subprocess.DEVNULL, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return 1, ""
        return p.returncode, p.stdout

    @staticmethod
    def unpushed_branches(root, ticket):
        """The work of ticket ``ticket`` that is on no remote, in the workspace at
        ``root``: for each checked-out submodule (``.gitmodules``) and the superproject,
        every local branch whose name names the ticket (``ticket_branch_re``; never
        main/master) with commits on no remote-tracking branch (no fetch: the refs as
        they are), or checked out in a linked worktree with uncommitted changes (untracked
        files included). ``[{label, repo, branch, unpushed, dirty, worktree}]``; label is
        the ship.py target (the submodule's path, ``workspace`` for the superproject).
        A git call that fails counts as nothing found."""
        pat = inbox_core.ticket_branch_re(ticket)
        if not pat:
            return []
        repos = [(s, os.path.join(root, s)) for s in inbox_core._gitmodule_paths(root)]
        repos.append(("workspace", root))
        found = []
        for label, repo in repos:
            if not os.path.exists(os.path.join(repo, ".git")):
                continue
            rc, out = inbox_core._git(repo, "for-each-ref", "--format=%(refname:lstrip=2)",
                                      "refs/heads")
            names = [b for b in out.splitlines() if not rc and b and b not in ("main", "master")
                     and pat.search(b)]
            if not names:
                continue
            # the linked worktrees on those branches (the first entry is the main one)
            rc, out = inbox_core._git(repo, "worktree", "list", "--porcelain")
            where, cur, first = {}, None, True
            for line in (out.splitlines() if not rc else []) + [""]:
                if line.startswith("worktree "):
                    cur = line[len("worktree "):]
                elif line.startswith("branch refs/heads/") and cur and not first:
                    where[line[len("branch refs/heads/"):]] = cur
                elif not line:
                    if cur is not None:
                        first = False
                    cur = None
            for b in names:
                rc, out = inbox_core._git(repo, "rev-list", "--count", "refs/heads/" + b,
                                          "--not", "--remotes")
                ahead = int(out.strip() or 0) if not rc else 0
                wt = where.get(b)
                dirty = 0
                if wt and os.path.isdir(wt):
                    rc, out = inbox_core._git(wt, "status", "--porcelain")
                    dirty = len(out.splitlines()) if not rc else 0
                if ahead or dirty:
                    found.append({"label": label, "repo": repo, "branch": b,
                                  "unpushed": ahead, "dirty": dirty, "worktree": wt or ""})
        return found

    @staticmethod
    def unpushed_check(args, board, r):
        """After the checkpoint of a *delivered* ticket ``r`` (delivered or closed, no
        problem): the lines that hold its delivery back, one per branch of
        ``unpushed_branches`` with how to push it; [] when nothing is unpushed. Only for
        the workspace's own board; ``"unpushedCheck": false`` in workspace.json switches
        it off. Never raises (a failure is one warning line on stderr and no hold)."""
        if r.get("unfinished") or r.get("state") != "delivered":
            return []
        try:
            ws = load_workspace(getattr(args, "workspace", None))
            if not _same_file(board_dir(board), ws["board"]) or ws.get("unpushedCheck") is False:
                return []
            root = os.path.realpath(os.path.dirname(ws["_path"]))
            found = inbox_core.unpushed_branches(root, r["id"])
        except AcademyError:
            return []
        except Exception as exc:                     # noqa: BLE001 -- never break --check
            sys.stderr.write("warning: unpushed-branch scan for %s failed: %s: %s\n"
                             % (r.get("id"), type(exc).__name__, exc))
            return []
        lines = []
        for f in found:
            lines.append("  %s %s unpushed=%d dirty=%d%s" % (
                f["label"], f["branch"], f["unpushed"], f["dirty"],
                (" " + f["worktree"]) if f["worktree"] else ""))
            push = "py scripts/ship.py push %s --repo %s" % (f["label"], f["worktree"])
            if not (f["worktree"] and inbox_core.TEMPLATE_BRANCH.match(f["branch"])):
                lines.append("    -> not a <date>/<topic>/<role> branch in a worktree: ship.py "
                             "cannot push it; the human pushes it or moves its commits to one")
            elif f["dirty"]:
                lines.append("    -> commit it first (py scripts/ship.py commit %s -m MSG "
                             "--paths ... --repo %s), then %s" % (f["label"], f["worktree"], push))
            else:
                lines.append("    -> " + push)
        if lines:
            lines.append("  (delivered is reported once this work is pushed; then run "
                         "--check %s again)" % r["id"])
        return lines

    @staticmethod
    def _session_inside(root):
        """Whether this session (``$CLAUDE_PROJECT_DIR``, else the cwd) works in the
        checkout at ``root``: at or under it, and not inside a worktree kept under it
        (a ``.claude/worktrees`` segment: Claude Code's workspace worktrees and
        ``ship.py start --worktree``'s submodule worktrees are separate checkouts)."""
        here = os.path.normcase(os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR")
                                                 or os.getcwd()))
        top = os.path.normcase(os.path.realpath(root))
        if here != top and not here.startswith(top.rstrip(os.sep) + os.sep):
            return False
        parts = os.path.relpath(here, top).split(os.sep)
        return not any(a == os.path.normcase(".claude") and b == "worktrees"
                       for a, b in zip(parts, parts[1:]))

    @staticmethod
    def parser(description, prog=None):
        import argparse
        ap = argparse.ArgumentParser(prog=prog, description=description)
        ap.add_argument("--instance")
        ap.add_argument("--board")
        ap.add_argument("--home")
        ap.add_argument("--workspace")
        ap.add_argument("--n", "--limit", dest="n", type=int,
                        help="tickets to take (at most 3 outside a campaign; a campaign has "
                             "no cap of its own to lower: without --n it takes them all); "
                             "--limit is an alias")
        ap.add_argument("--all", action="store_true", help="list without taking or cutting")
        ap.add_argument("--ids", metavar="T-a,T-b",
                        help="only these tickets and the tickets whose parent is one of them, "
                             "listed without the cut (as --all), so a workflow need not "
                             "transcribe the whole inbox")
        ap.add_argument("--json", action="store_true")
        wp = ap.add_mutually_exclusive_group()
        wp.add_argument("--campaign", metavar="TARGET",
                        help="only tickets carrying `campaign: TARGET`")
        wp.add_argument("--cowork", metavar="SLUG",
                        help="only tickets carrying `cowork: SLUG` (/academy:cowork)")
        ap.add_argument("--check", metavar="T-NNNN",
                        help="the serial checkpoint of one ticket (exit 3 if unfinished); a "
                             "finished ticket also runs the workspace's ship.py checkpoint "
                             "(commit and push the ticket's repos; docs/protocol.md section 4)")
        return ap

    @staticmethod
    def run(args, instance, board, budget_limit, route, out=None, position=None,
            return_legs=True, position_first=False, extra=None, header=None, role=None):
        """Print the inbox of ``instance``; exit 0 with rows, 1 empty, 3 for --check
        on an unfinished ticket. ``header`` = ``{"json": {...}, "text": [lines]}`` is what
        a wrapper reports before the rows (the Author's sweep step, its waiting lists).
        A --check that finds the ticket finished runs ``ship_checkpoint`` (``role`` is the
        wrapper's role when ``instance`` is not resolved)."""
        out = out or sys.stdout
        if args.check:
            r = inbox_core.check(board, args.check)
            # the status line comes after the checkpoint and the unpushed scan, so that it
            # can say unfinished: the workflow reads the first "<id>: <state> (<status>)"
            inbox_core.ship_checkpoint(args, instance, board, r, role=role, out=out)
            held = inbox_core.unpushed_check(args, board, r)
            if held:
                r = dict(r, state="unfinished", unfinished=True,
                         problem="work of %s is not on a remote" % r["id"])
                status = "%s, unpushed" % r["status"]
            else:
                status = r["status"]
            out.write("%s: %s (%s)%s\n" % (r["id"], r["state"], status,
                                           ("; " + r["problem"]) if r["problem"] else ""))
            for line in held:
                out.write(line + "\n")
            return 3 if r["unfinished"] else 0
        cowork = getattr(args, "cowork", None)
        field, plan = ("cowork", cowork) if cowork else ("campaign", args.campaign)
        if plan:
            # a workplan lifts the cap of 3 (docs/protocol.md): --n alone bounds it
            limit = max(1, int(args.n)) if args.n else None
        else:
            limit = min(max(1, int(args.n)) if args.n else inbox_core.MAX,
                        inbox_core.clamp(budget_limit))
        ids = [t.strip() for t in (getattr(args, "ids", None) or "").split(",") if t.strip()]
        rows, total = inbox_core.select(board, instance, limit or 10 ** 9, all=args.all or bool(ids),
                                        route=route, campaign=args.campaign,
                                        position=position, return_legs=return_legs,
                                        position_first=position_first, extra=extra,
                                        cowork=cowork)
        if ids:
            rows = [r for r in rows if r.get("id") in ids or (r.get("parent") or "") in ids]
            if not args.all:
                # #92: --ids picks among the tickets the inbox may take; it does not widen
                # them to a blocked ticket still waiting (taken and parked again, T-1613,
                # T-1216, T-1305). A return leg and a released row are takes.
                rows = [r for r in rows if inbox_core.takeable(r)]
        header = header or {}
        left = 0 if (args.all or ids) else max(0, total - len(rows))
        unfinished = inbox_core.unfinished(rows)
        outside = []
        if plan and not args.all:
            outside = inbox_core.outside_campaign(board, instance, plan, field)
            unfinished = unfinished + [t for t in outside if t not in unfinished]
        if args.json:
            doc = {"instance": instance, "home": inbox_core.home_of(instance, args),
                   "limit": limit, "waiting": total,
                   "take": rows, "remaining": left, "unfinished": unfinished}
            if plan:
                doc["outside_campaign"] = outside
            doc.update(header.get("json") or {})
            out.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
            return 0 if rows else 1
        for line in header.get("text") or []:
            out.write(line + "\n")
        for r in rows:
            rt = r["route"]
            out.write("%s  %-17s %-11s %-6s from %-18s -> %-8s %-24s %s%s%s\n" % (
                r["id"], r["kind"], r["status"], r["priority"], r["from"], rt["how"],
                (rt["target"] or "") + (" (return)" if r["return"] else ""), r["title"],
                ("  [over budget: %s]" % r["over_budget"]) if r["over_budget"] else "",
                ("  [blocked: %s]" % r["blocked"]) if r["blocked"] else ""))
        if not rows:
            out.write("(inbox of %s is empty)\n" % instance)
        if unfinished:
            out.write("unfinished: %s; resume before taking anything new\n"
                      % ", ".join(unfinished))
        if outside:
            out.write("(%s are in progress outside %s %s: the %s list leaves "
                      "them out; resume them first)\n" % (", ".join(outside), field, plan,
                                                            field))
        out.write("%d taken, %d remaining\n" % (len(rows), left))
        for line in header.get("text_after") or []:
            out.write(line + "\n")
        return 0 if rows else 1

    @staticmethod
    def resolve_instance(args, role, cwd=None):
        """``(instance, config_or_None)`` a role wrapper acts for, from its arguments.

        Honours ``--instance`` (its home found in workspace.json, so its config is loaded
        too), ``--home``, ``--workspace``; otherwise the ``role`` home containing ``cwd``
        (by its academy.json, else by workspace.json for a home not yet switched over), or
        the only instance of the role. Raises AcademyError when none is found.
        """
        try:
            ws = load_workspace(args.workspace)
        except ConfigError:
            ws = None
        insts = (ws or {}).get("instances", {})
        home, inst = args.home, args.instance
        if not home and inst and inst in insts:
            home = insts[inst].get("home")
        cwd = cwd or os.getcwd()
        if not home:
            home = find_home(cwd)
            if not home and ws:
                best = None
                for name, i in insts.items():
                    h = _norm(i.get("home", ""))
                    if i.get("role") == role and h and (_norm(cwd) == h
                                                        or _norm(cwd).startswith(h + "/")):
                        if best is None or len(h) > len(best[0]):
                            best = (h, i["home"])
                home = best[1] if best else None
        cfg = None
        if home and os.path.isfile(os.path.join(home, CONFIG_REL)):
            cfg = load_config(home)                  # an invalid one is an error, not a default
            if cfg and cfg.get("role") != role:
                if not inst:
                    raise AcademyError("%s is a %s home, not a %s home"
                                       % (home, cfg.get("role"), role))
                cfg = None
        if not inst:
            inst = (cfg or {}).get("instance") or (instance_for_home(ws, home)
                                                   if ws and home else None)
            if not inst:
                mine = sorted(n for n, i in insts.items() if i.get("role") == role)
                inst = mine[0] if len(mine) == 1 else None
        if not inst:
            raise AcademyError("not in a %s home; give --instance" % role)
        return inst, cfg

    @staticmethod
    def home_of(instance, args=None):
        """The instance's home as workspace.json gives it (the checkout this workspace uses),
        '' when it cannot be read. The inbox workflow hands it back verbatim (#116: a clerk
        that filled the home itself named an attached checkout outside the workspace)."""
        given = getattr(args, "home", None)
        fallback = os.path.abspath(given).replace("\\", "/") if given else ""
        try:
            ws = load_workspace(getattr(args, "workspace", None))
        except (AcademyError, OSError):
            return fallback
        # an instance workspace.json does not list: the --home the script was given
        return str(((ws or {}).get("instances") or {}).get(instance, {}).get("home") or fallback)

    @staticmethod
    def open_inbox_store(args):
        """The board the inbox reads: ``--board`` (the file board there), else workspace.json's
        ``board.backend``. Raises for a github board that cannot be opened."""
        if args.board:
            return FileBoardStore(os.path.abspath(args.board))
        st = open_store(load_workspace(args.workspace))
        return FileBoardStore(os.path.abspath(st.board)) if isinstance(st, FileBoardStore) \
            else st

    @staticmethod
    def main(argv, description, resolve, route, prog="inbox.py", out=None, **run_kw):
        """The body of every role's ``inbox.py``: parse, resolve the instance and its config
        (``resolve(args) -> (instance, cfg)``; ``resolve_instance`` is the usual one), open the
        board, clamp ``budget.itemsPerRun``, run; an error is one line on stderr and exit 2."""
        args = inbox_core.parser(description, prog).parse_args(argv)
        try:
            inst, cfg = resolve(args)
            board = inbox_core.open_inbox_store(args)
            limit = ((cfg or {}).get("budget") or {}).get("itemsPerRun")
            return inbox_core.run(args, inst, board, limit, route, out=out, **run_kw)
        except (AcademyError, OSError) as exc:
            sys.stderr.write("%s: %s\n" % (prog, exc))
            return 2
