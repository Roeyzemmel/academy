"""The profile-neutral view of a registry: records and stores.

Each profile keeps its own native objects (the fsl-claims ``Claim``, the s1-kb
``Entity``), because the shims expose them unchanged. The engine's cross-namespace
layer (federation, graph, sql, the MCP tools) sees them through this interface.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class Record:
    ns: str
    type: str            # the profile's entity type: claim, assumption, example, verdict, ...
    id: str              # the id inside the namespace (no "ns:" prefix)
    fields: dict
    body: str
    file: str            # absolute path
    status: str = ""     # the raw status word, '' when the record carries none
    cls: str = "n/a"     # the projection class
    title: str = ""
    links: list = field(default_factory=list)   # [(rel, qualified target or raw)]

    @property
    def qid(self):
        return f"{self.ns}:{self.id}"


class Store:
    """One namespace loaded through its profile. Subclasses fill ``records``."""

    profile = ""

    def __init__(self, ns, home):
        self.ns, self.home = ns, home
        self.records: dict[str, Record] = {}
        self.errors: list[str] = []

    def lookup(self, name):
        """(id or None, exact): exact is False when resolved by alias or normalisation."""
        if name in self.records:
            return name, True
        return None, False

    def aliases(self, rid):
        """The old labels of record ``rid`` (none unless the profile has aliases)."""
        return []

    def get(self, name):
        rid, _ = self.lookup(name)
        return self.records.get(rid) if rid else None

    def statement_text(self, rid):
        """The text a proof review is given on, and hashed: here the title and the body.
        ``py -m registry statement <ns:id>`` prints it with its hash, so a review can be
        given on exactly this text."""
        r = self.records.get(rid)
        return (r.title + "\n" + r.body) if r else None

    def statement_hash(self, rid):
        t = self.statement_text(rid)
        return statement_hash_of(t) if t is not None else None


def statement_hash_of(text):
    """sha256 of the whitespace-normalised text, 16 hex digits."""
    norm = re.sub(r"\s+", " ", text or "").strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
