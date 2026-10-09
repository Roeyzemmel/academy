"""Line-preserving edits of a record's frontmatter (the mutation path).

A mutation touches only the lines it must: every other byte of the file, its line
endings included, is kept. The file is read and written as bytes; each line keeps its
own CR, and an inserted line gets the file's line ending (that of its first line).
"""
from __future__ import annotations

import re
from pathlib import Path

from .fm import FrontmatterError, format_list, format_scalar, parse_scalar, parse_value, \
    _is_skippable


class Doc:
    """A record file split into lines, with the closing fence located."""

    def __init__(self, path, fmt=None):
        self.path = Path(path)
        self.fmt = fmt or format_scalar
        raw = self.path.read_bytes()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        self.lines = text.split("\n")
        self.eol = "\r" if self.lines and self.lines[0].endswith("\r") else ""
        if not self.lines or self.lines[0].rstrip("\r") != "---":
            raise FrontmatterError(f"{path}:1: no frontmatter", str(path), 1, "no frontmatter")
        self.close = next((i for i in range(1, len(self.lines))
                           if self.lines[i].rstrip("\r") == "---"), None)
        if self.close is None:
            raise FrontmatterError(f"{path}:1: frontmatter is not closed", str(path), 1,
                                   "frontmatter is not closed")

    def text(self):
        return "\n".join(self.lines)

    def save(self):
        data = self.text().encode("utf-8")
        self.path.write_bytes((b"\xef\xbb\xbf" if self.bom else b"") + data)

    # -- locating ---------------------------------------------------------
    def find(self, key):
        rx = re.compile(rf"^{re.escape(key)}:")
        return next((i for i in range(1, self.close) if rx.match(self.lines[i])), None)

    def block_end(self, i):
        """Index after the last line of key ``i``'s block (items, blanks, comments)."""
        j, last = i + 1, i
        while j < self.close:
            ln = self.lines[j]
            if ln[:1] in (" ", "\t", "-") or _is_skippable(ln.rstrip("\r")):
                if ln.strip():
                    last = j
                j += 1
            else:
                break
        return last + 1

    def _line(self, text):
        return text + self.eol

    def insert(self, at, text):
        self.lines.insert(at, self._line(text))
        if at <= self.close:
            self.close += 1

    def _after(self, keys):
        """Insertion point after the block of the last present key in ``keys``."""
        for k in reversed(list(keys or ())):
            i = self.find(k)
            if i is not None:
                return self.block_end(i)
        return self.close

    # -- edits ------------------------------------------------------------
    def set_scalar(self, key, value, after=()):
        text = f"{key}: {self.fmt(value)}"
        i = self.find(key)
        if i is not None:
            end = self.block_end(i)
            self.lines[i:end] = [self._line(text)]
            self.close -= (end - i - 1)
            return
        self.insert(self._after(after), text)

    def remove(self, key):
        """Drop field ``key`` with its block; a missing field is left alone."""
        i = self.find(key)
        if i is None:
            return
        end = self.block_end(i)
        del self.lines[i:end]
        self.close -= end - i

    def set_list(self, key, items, after=()):
        """Make list field ``key`` exactly ``items`` (a block list); no items drops it."""
        at = None
        i = self.find(key)
        if i is not None:
            at = i
            self.remove(key)
        items = list(items or [])
        if not items:
            return
        if at is None:
            at = self._after(after)
        self.insert(at, f"{key}:")
        for n, it in enumerate(items, 1):
            self.insert(at + n, f"  - {self.fmt(it)}")

    def list_items(self, key):
        """The items of list field ``key`` as written (inline or block), or None."""
        i = self.find(key)
        if i is None:
            return None
        rest = self.lines[i].rstrip("\r")[len(key) + 1:]
        if not _is_skippable(rest):
            v = parse_value(rest, str(self.path), i + 1)
            return v if isinstance(v, list) else [v]
        return [parse_scalar(self.lines[k].rstrip("\r").strip()[2:], str(self.path), k + 1)
                for k in range(i + 1, self.block_end(i))
                if self.lines[k].lstrip().startswith("- ")]

    def add_item(self, key, item, first=False, after=()):
        """Add ``item`` to list field ``key``: first (newest-first history) or last.
        A block list gets one new ``  - item`` line; an inline list is rewritten on its
        one line; a missing or empty field becomes a one-item block list."""
        i = self.find(key)
        if i is None:
            at = self._after(after)
            self.insert(at, f"{key}:")
            self.insert(at + 1, f"  - {self.fmt(item)}")
            return
        rest = self.lines[i].rstrip("\r")[len(key) + 1:]
        if not _is_skippable(rest):
            items = parse_value(rest, str(self.path), i + 1)
            items = items if isinstance(items, list) else [items]
            if not items:
                self.lines[i] = self._line(f"{key}:")
                self.insert(i + 1, f"  - {self.fmt(item)}")
                return
            items = [item] + items if first else items + [item]
            self.lines[i] = self._line(f"{key}: {format_list(items, self.fmt)}")
            return
        end = self.block_end(i)
        item_lines = [k for k in range(i + 1, end) if self.lines[k].lstrip().startswith("-")]
        ref = self.lines[item_lines[0]] if item_lines else "  - x"
        indent = ref[:len(ref) - len(ref.lstrip())]
        new = f"{indent}- {self.fmt(item)}"
        if first:
            self.insert(item_lines[0] if item_lines else i + 1, new)
        else:
            self.insert((item_lines[-1] + 1) if item_lines else i + 1, new)
