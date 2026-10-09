"""domain_get: files of a domain pack, ``<root>/domains/<name>/``.

Role plugins refer to pack files only by name (plan section 6, domain pack
contract). The pack is looked for, in order (:func:`search_dirs`):

1. ``domains/`` beside the loaded ``workspace.json`` (the academy root);
2. ``$ACADEMY_ROOT/domains``;
3. ``domains/`` of the marketplace root beside this plugin (the repo layout:
   ``<marketplace>/academy`` and ``<marketplace>/domains``);
4. in the installed layout (``~/.claude/plugins/cache/<marketplace>/<plugin>/<version>``,
   where a cloud session runs the plugins from), the marketplace's source directory
   from ``~/.claude/plugins/known_marketplaces.json``, then any installed sibling
   plugin whose ``pack.json`` names the pack (the pack installed as a plugin, e.g.
   ``ts-domain``).

A miss lists every place searched and says not to retry (165 identical refusals in
the 2026-10-08 ledgers came from retrying it).
"""

import glob
import json
import os
import re

from . import Tool, ToolError, obj, S

RE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_BYTES = 200000
#: the plugin directory this module belongs to (``<plugin>/mcp/tools/domain.py``)
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _plugin_dir():
    return os.environ.get("CLAUDE_PLUGIN_ROOT") or PLUGIN_DIR


def _installed_layout(plugin):
    """``(plugins dir, marketplace cache dir, marketplace name)`` when ``plugin`` is
    ``<plugins>/cache/<marketplace>/<plugin>/<version>``, else None."""
    ver = os.path.abspath(plugin)
    mkt_dir = os.path.dirname(os.path.dirname(ver))
    cache = os.path.dirname(mkt_dir)
    if os.path.basename(cache) != "cache":
        return None
    return os.path.dirname(cache), mkt_dir, os.path.basename(mkt_dir)


def search_dirs(ctx):
    """The ``domains`` folders to look in, in order, without duplicates."""
    out = []

    def add(d):
        if d:
            d = os.path.abspath(d)
            if d not in out:
                out.append(d)

    try:
        add(os.path.join(ctx.academy_root, "domains"))
    except Exception:           # no workspace.json: the other places still count
        pass
    if os.environ.get("ACADEMY_ROOT"):
        add(os.path.join(os.environ["ACADEMY_ROOT"], "domains"))
    plugin = _plugin_dir()
    add(os.path.join(os.path.dirname(os.path.abspath(plugin)), "domains"))
    inst = _installed_layout(plugin)
    if inst:
        plugins, _mkt_dir, mkt = inst
        try:
            with open(os.path.join(plugins, "known_marketplaces.json"),
                      encoding="utf-8") as fh:
                known = json.load(fh)
            loc = (known.get(mkt) or {}).get("installLocation") \
                or ((known.get(mkt) or {}).get("source") or {}).get("path")
        except (OSError, ValueError, AttributeError):
            loc = None
        if loc:
            add(os.path.join(loc, "domains"))
    return out


def _installed_packs(plugin):
    """``{pack name: dir}`` of the installed sibling plugins that are domain packs."""
    inst = _installed_layout(plugin)
    if not inst:
        return {}
    out = {}
    for pj in sorted(glob.glob(os.path.join(inst[1], "*", "*", "pack.json"))):
        try:
            with open(pj, encoding="utf-8") as fh:
                name = json.load(fh).get("name")
        except (OSError, ValueError, AttributeError):
            continue
        if name and name not in out:
            out[name] = os.path.dirname(pj)
    return out


def pack_dir(ctx, name):
    if not name or not RE_NAME.match(name):
        raise ToolError("a pack name is lower-case words joined by hyphens (a folder under domains/), got %r" % name)
    dirs = search_dirs(ctx)
    for root in dirs:
        d = os.path.join(root, name)
        if os.path.isdir(d):
            return d
    installed = _installed_packs(_plugin_dir())
    if name in installed:
        return installed[name]
    have = set(installed)
    for root in dirs:
        if os.path.isdir(root):
            have.update(x for x in os.listdir(root) if os.path.isdir(os.path.join(root, x)))
    raise ToolError("no domain pack %r (have: %s). Searched: %s%s. Do not retry this "
                    "call: the answer will not change in this session. Read the pack's "
                    "files directly if you know where the marketplace is, or go on "
                    "without it and say so." % (
                        name, ", ".join(sorted(have)) or "none",
                        ", ".join(d.replace("\\", "/") for d in dirs),
                        "; and the installed plugins under %s"
                        % _installed_layout(_plugin_dir())[1].replace("\\", "/")
                        if _installed_layout(_plugin_dir()) else ""))


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
