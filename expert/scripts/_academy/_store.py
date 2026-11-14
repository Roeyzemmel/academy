"""The board store (docs/github-board.md): the ``BoardStore`` seam, the file board,
``open_store``, and the ticket rules that walk other tickets through a store.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import os
import re
import sys

from ._base import AcademyError, ConfigError, FrontmatterError, RE_TICKET_ID, _PKG_DIR
from ._workspace import load_workspace
from ._files import allocate_id, atomic_write, read_frontmatter, write_frontmatter
from ._tickets import TICKET_KEY_ORDER, find_ticket, ticket_filename

# ----------------------------------------------------------------------------
# The board store (docs/github-board.md): tickets behind one seam
# ----------------------------------------------------------------------------

class BoardStore(object):
    """The tickets of a board, wherever they live. A *ref* names one ticket in its store
    (a file path, or ``github#<number>``) and is what rows report as ``path``.

    ``FileBoardStore`` (here) is the file board; ``board_store.GithubBoardStore`` keeps the
    same tickets as issues through an injected transport. Both hand out and take
    ``(meta, body)`` pairs, so the ticket rules (``validate_ticket``, transitions) do not
    know which one they run on.
    """

    backend = "abstract"

    def describe(self):
        return self.backend

    def iter_tickets(self):
        """Yield ``(ref, meta, body)``; an unreadable ticket has ``meta = None``."""
        raise NotImplementedError

    def iter_meta(self):
        """Yield ``(ref, meta)`` of every readable ticket (a store may skip the bodies)."""
        for ref, meta, _body in self.iter_tickets():
            if meta is not None:
                yield ref, meta

    def read_all(self, instance):
        """The metas (with ``_path`` = ref) of the tickets addressed to ``instance``."""
        raise NotImplementedError

    def search(self, text):
        """The ids of the tickets whose id, title, ask, agenda or body holds ``text``
        (words in that order, any case, any spacing). The body is the ticket's text as
        this store can read it in one pass: with its thread on the file board, without
        it on a board where the thread is a request per ticket."""
        want = search_key(text)
        if not want:
            return []
        return [str(meta.get("id")) for _ref, meta, body in self.iter_tickets()
                if meta is not None and want in search_key(ticket_text(meta, body))]

    def find(self, tid):
        """The ref of ticket ``tid``, or None."""
        raise NotImplementedError

    def get(self, tid):
        """``(ref, meta, body)`` of ticket ``tid``; AcademyError when there is none."""
        raise NotImplementedError

    def save(self, meta, body, ref=None, relocate=False):
        """Write an existing ticket (``ref`` given) or a new one; returns its ref.
        ``relocate``: the ticket's ``to`` changed, so it moves to its new addressee."""
        raise NotImplementedError

    def create(self, meta, body):
        """Give a new ticket its id, store it; returns ``(ref, meta)``."""
        raise NotImplementedError

    def status_of(self, tid):
        """The status of ticket ``tid``, or None when missing or unreadable."""
        try:
            return self.get(tid)[1].get("status")
        except (AcademyError, OSError, ValueError):
            return None


class FileBoardStore(BoardStore):
    """The file board: ``<board>/<instance or human>/T-NNNN-slug.md`` (docs/protocol.md 2)."""

    backend = "files"
    RESERVED = ("packets", "deep-dives", ".ids", ".render", ".git")
    _RE_FILE = re.compile(r"^T-\d{4,}(?:-.*)?\.md$")

    def __init__(self, board):
        self.board = str(board)

    def describe(self):
        return self.board

    @staticmethod
    def read_path(path):
        """``(meta, body)`` of the ticket file at ``path``."""
        with open(path, "r", encoding="utf-8") as fh:
            return read_frontmatter(fh.read())

    @staticmethod
    def write_path(path, meta, body):
        """Write ``meta`` (canonical key order) and ``body`` to the ticket file ``path``."""
        ordered = {k: meta[k] for k in TICKET_KEY_ORDER if k in meta}
        atomic_write(path, write_frontmatter(ordered, body))

    _read = read_path

    def iter_tickets(self):
        board = self.board
        if not os.path.isdir(board):
            return
        for folder in sorted(os.listdir(board)):
            full = os.path.join(board, folder)
            if folder in self.RESERVED or folder.startswith(".") or not os.path.isdir(full):
                continue
            for f in sorted(os.listdir(full)):
                if not self._RE_FILE.match(f):
                    continue
                p = os.path.join(full, f)
                try:
                    meta, body = self._read(p)
                except (FrontmatterError, OSError, UnicodeDecodeError):
                    meta, body = None, ""
                yield p, meta, body

    def read_all(self, instance):
        folder = os.path.join(self.board, instance)
        out = []
        if not os.path.isdir(folder):
            return out
        for f in sorted(os.listdir(folder)):
            if not self._RE_FILE.match(f):
                continue
            path = os.path.join(folder, f)
            try:
                meta = self._read(path)[0]
            except (OSError, AcademyError, UnicodeDecodeError):
                continue
            if not meta.get("id") or meta.get("to", instance) != instance:
                continue
            meta = dict(meta)
            meta["_path"] = path.replace("\\", "/")
            out.append(meta)
        return out

    def find(self, tid):
        return find_ticket(self.board, tid)

    def get(self, tid):
        path = find_ticket(self.board, tid)
        if not path:
            raise AcademyError("no ticket %s on %s" % (tid, self.board))
        meta, body = self._read(path)
        return path, meta, body

    def status_of(self, tid):
        path = find_ticket(self.board, tid)
        if not path:
            return None
        try:
            return self._read(path)[0].get("status")
        except (OSError, AcademyError):
            return None

    def save(self, meta, body, ref=None, relocate=False):
        path = ref
        if ref is None:
            path = os.path.join(self.board, meta["to"],
                                ticket_filename(meta["id"], meta["title"]))
        elif relocate:
            path = os.path.join(self.board, meta["to"], os.path.basename(ref))
        self.write_path(path, meta, body)
        if ref is not None and path != ref:
            os.remove(ref)
        return path

    def create(self, meta, body):
        meta = dict(meta)
        meta["id"] = allocate_id(self.board, "ticket")
        return self.save(meta, body), meta


STORE_METHODS = ("iter_tickets", "iter_meta", "read_all", "find", "get", "save", "create",
                 "status_of")


def search_key(text):
    """``text`` lower-cased with every run of whitespace one space."""
    return " ".join(str(text or "").lower().split())


def ticket_text(meta, body):
    """What a text search of a ticket reads: its id, title, ask, agenda and body."""
    return "\n".join([str(meta.get(k) or "") for k in ("id", "title", "ask", "agenda")]
                     + [body or ""])


def is_store(obj):
    """Whether ``obj`` speaks the BoardStore protocol. Duck-typed on purpose: the library is
    vendored into every plugin as its own module object, so ``isinstance`` against one
    copy's ``BoardStore`` fails for a store built from another copy (the github store is
    built from the lib's, a role plugin runs on its ``_academy``)."""
    return isinstance(obj, BoardStore) or (
        not isinstance(obj, (str, bytes, os.PathLike))
        and all(callable(getattr(obj, m, None)) for m in STORE_METHODS))


def as_store(board):
    """``board`` as a BoardStore: a store is returned as it is, a path (str or PathLike)
    becomes a file store; anything else is an error, never a silent file store."""
    if is_store(board):
        return board
    if isinstance(board, (str, os.PathLike)):
        return FileBoardStore(board)
    raise AcademyError("not a board: %r (a directory or a BoardStore)" % (board,))


def board_dir(board):
    """The board directory behind ``board`` (a path or a store): where packets, deep dives
    and ids live, files on every backend. A github store carries it as ``.board`` (set by
    ``open_store`` from workspace.json's ``board.path``)."""
    if isinstance(board, (str, os.PathLike)):
        return str(board)
    path = getattr(board, "board", None)
    if not path:
        raise AcademyError("this board store has no directory for packets (board.path)")
    return str(path)


def status_lookup(store):
    """``status_of`` for many tickets: a function from a ticket id to its status (None
    when it is not on the board).

    On the file board that is the store's own ``status_of``. On a board where one ticket
    is one request (``backend`` ``github``) it answers from one listing, made on the
    first question: an inbox that asks about each ticket a blocked one waits on made a
    request per ticket (2026-11-13: 23 of them, 9 of the Expert inbox's 10 seconds)."""
    if getattr(store, "backend", "files") == "files":
        return store.status_of
    held = {}

    def number(tid):
        # by number, as the store's own status_of finds an issue: T-00012 is T-0012
        m = RE_TICKET_ID.match(str(tid))
        digits = re.search(r"\d+", str(tid)) if m else None
        return int(digits.group()) if digits else str(tid)

    def status_of(tid):
        if not held:
            held["by_id"] = {number(m.get("id")): m.get("status")
                             for _ref, m in store.iter_meta() if m}
        return held["by_id"].get(number(tid))
    return status_of


def board_cache_dir(cfg=None, environ=None):
    """Where the GitHub board's listing is kept between processes, or None for nowhere.

    ``ACADEMY_BOARD_CACHE`` wins: a directory, or ``0`` / ``off`` / ``no`` for none; then
    ``board.cache`` of workspace.json (``false``, or a directory); else the user's cache
    directory (``%LOCALAPPDATA%`` on Windows, ``$XDG_CACHE_HOME`` or ``~/.cache``
    elsewhere), under ``academy/board``. The cache holds what the board's readers may read
    anyway; deleting it only costs the next listing a full read."""
    env = os.environ if environ is None else environ
    val = env.get("ACADEMY_BOARD_CACHE")
    if val is None:
        val = (cfg or {}).get("cache")
    if val is False or str(val).strip().lower() in ("0", "off", "no", "false"):
        return None
    if val and val is not True and str(val).strip().lower() not in ("1", "on", "yes", "true"):
        return os.path.expanduser(str(val))
    base = env.get("LOCALAPPDATA") if os.name == "nt" else env.get("XDG_CACHE_HOME")
    base = base or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "academy", "board")


def open_store(workspace=None, transport=None, board=None):
    """The board store of a workspace: ``board.backend`` of workspace.json, ``files`` by default.

    ``board`` (an explicit path) always opens the file board there. ``github`` needs a
    transport: the object passed in, or the one ``board.transport`` (``"module:factory"``,
    called with the board's config dict) names, e.g. ``board_gh:transport`` (REST through gh,
    academy/lib/board_gh.py); without either it is a ConfigError. A github backend never
    degrades to the file board: anything that cannot be opened raises.
    """
    if board:
        return FileBoardStore(board)
    ws = workspace if isinstance(workspace, dict) else load_workspace(workspace)
    cfg = ws.get("board_config") or {}
    backend = cfg.get("backend", "files")
    if backend == "files":
        return FileBoardStore(ws["board"])
    cache_dir = None
    if transport is None and cfg.get("transport"):
        import importlib
        cache_dir = board_cache_dir(cfg)      # only for the configured transport, never
                                              # for one a caller (a test) hands in
        _import_board_store()         # puts academy/lib, where board_gh lives, on the path
        mod, _, fn = str(cfg["transport"]).partition(":")
        transport = getattr(importlib.import_module(mod), fn or "transport")(cfg)
    if transport is None:
        raise ConfigError("board.backend is github but no transport is available: pass one "
                          "to open_store or set board.transport to 'module:factory'")
    board_store = _import_board_store()
    # the store speaks through THIS copy of the library (its errors, its helpers)
    store = board_store.GithubBoardStore(transport, cfg.get("repo", ""),
                                         lib=sys.modules[__package__],
                                         assignee=cfg.get("assignee"), cache_dir=cache_dir)
    store.board = ws["board"]         # packets, deep dives and ids stay files (board_dir)
    return store


def _import_board_store():
    """``board_store`` (academy/lib), found next to the academy plugin when this copy is
    vendored elsewhere; sys.path is extended only when it is not importable already."""
    try:
        import board_store
        return board_store
    except ImportError:
        pass
    here = os.path.dirname(os.path.abspath(_PKG_DIR))
    for cand in (os.path.join(here, os.pardir, os.pardir, "academy", "lib"),
                 os.path.join(here, os.pardir, "lib")):
        cand = os.path.abspath(cand)
        if os.path.isfile(os.path.join(cand, "board_store.py")):
            sys.path.append(cand)
            try:
                import board_store
                return board_store
            except ImportError:
                break
    raise ConfigError("the github board store lives in the academy plugin "
                      "(academy/lib/board_store.py), which is not next to this plugin")


# Ticket rules that read other tickets through a store (docs/protocol.md)


def relay_depth(board, parent):
    """How many consecutive ancestors, starting at ``parent``, carry ``final_to``.

    Only relay links count toward the hop limit; an ordinary ``parent`` (a review
    ticket filed against the ticket that commissioned the experiment) stops the count.
    """
    n, seen, tid = 0, set(), parent
    store = as_store(board)
    while tid and tid not in seen:
        seen.add(tid)
        if not store.find(tid):
            break
        meta = store.get(tid)[1]
        if not meta.get("final_to"):
            break
        n += 1
        tid = meta.get("parent")
    return n


def mirror_blocks(store, tid, waiting_on, date):
    """Add ``tid`` to the ``blocks`` list of every ticket it waits on; returns the ids
    changed (docs/protocol.md, "Blocking bookkeeping")."""
    store = as_store(store)
    done = []
    for w in waiting_on or []:
        if not RE_TICKET_ID.match(str(w)):
            continue
        ref = store.find(w)
        if not ref:
            continue
        _r, m, b = store.get(w)
        blocks = list(m.get("blocks") or [])
        if tid not in blocks:
            m["blocks"] = blocks + [tid]
            m["updated"] = date
            store.save(m, b, ref)
            done.append(w)
    return done
