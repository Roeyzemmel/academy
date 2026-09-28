"""domain_get: files of a domain pack, ``<academy root>/domains/<name>/``.

The academy root is the directory of the loaded ``workspace.json``. Role plugins
refer to pack files only by name (plan section 6, domain pack contract).
"""

import os
import re

from . import Tool, ToolError, obj, S

RE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_BYTES = 200000


def pack_dir(ctx, name):
    if not name or not RE_NAME.match(name):
        raise ToolError("a pack name is lower-case words joined by hyphens (a folder under domains/), got %r" % name)
    d = os.path.join(ctx.academy_root, "domains", name)
    if not os.path.isdir(d):
        have = sorted(os.listdir(os.path.join(ctx.academy_root, "domains"))) \
            if os.path.isdir(os.path.join(ctx.academy_root, "domains")) else []
        raise ToolError("no domain pack %r (have: %s)" % (name, ", ".join(have) or "none"))
    return d


def _get(ctx, a):
    name = a.get("name")
    d = pack_dir(ctx, name)
    f = (a.get("file") or "").replace("\\", "/").strip("/")
    if not f:
        files = sorted(os.path.relpath(os.path.join(dp, x), d).replace("\\", "/")
                       for dp, dn, fn in os.walk(d) for x in fn
                       if ".git" not in dp and "__pycache__" not in dp)
        return {"pack": name, "dir": d.replace("\\", "/"), "files": files}
    full = os.path.normpath(os.path.join(d, f))
    if os.path.commonpath([os.path.abspath(full), os.path.abspath(d)]) != os.path.abspath(d):
        raise ToolError("file must stay inside the pack")
    if os.path.isdir(full):
        return {"pack": name, "dir": full.replace("\\", "/"),
                "files": sorted(os.listdir(full))}
    if not os.path.isfile(full):
        raise ToolError("pack %s has no file %s" % (name, f))
    with open(full, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read(MAX_BYTES + 1)
    out = {"pack": name, "file": f, "text": text[:MAX_BYTES]}
    if len(text) > MAX_BYTES:
        out["truncated"] = True
    return out


TOOLS = [
    Tool("domain_get", "Read a domain pack file (notation.md, traps.md, theorems/INDEX.md, "
         "...) by pack name; without file, list the pack's files.",
         obj({"name": S, "file": S}, ["name"]), _get),
]
