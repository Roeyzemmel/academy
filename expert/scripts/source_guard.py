"""PreToolUse hook (WebFetch): the Expert fetches only from its allowlist of sources.

The Expert's web reads (the librarian's cite runs, the related-work scout's watch) go to
an agreed list of scholarly hosts (2026-10-31): the plugin's default
``references/sources.json``, plus the library's ``expert.sources.allow`` in its
``.claude/academy.json`` (``expert.sources.only: true`` uses the library's list alone).
A host matches itself and its subdomains. A fetch of any other host by an Expert agent
is denied with the host named and how to add it; the same list is what a cloud
environment's Allowed domains needs for a scheduled Expert run (``--list`` prints it).
Silent for every other agent and for the human. The human's opt-out for a session:
``ACADEMY_ALLOW_ANY_SOURCE=1``.

    py source_guard.py            the hook (event on stdin)
    py source_guard.py --list     the effective allowlist, one host per line
"""

import json
import os
import sys
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = os.path.join(os.path.dirname(HERE), "references", "sources.json")
#: the Expert agents that fetch from the web
FETCHERS = ("librarian", "related-work-scout")


def default_hosts():
    try:
        with open(DEFAULTS, encoding="utf-8") as fh:
            return [str(h).lower() for h in json.load(fh).get("allow") or []]
    except (OSError, ValueError):
        return []


def allowlist(cfg):
    """The effective hosts for an Expert config dict (or None)."""
    src = (((cfg or {}).get("expert") or {}).get("sources") or {})
    extra = [str(h).strip().lower() for h in src.get("allow") or [] if str(h).strip()]
    hosts = extra if src.get("only") else default_hosts() + extra
    out = []
    for h in hosts:
        if h not in out:
            out.append(h)
    return out


def host_of(url):
    try:
        return (urlsplit(str(url)).hostname or "").lower()
    except ValueError:
        return ""


def allowed(host, hosts):
    return bool(host) and any(host == h or host.endswith("." + h) for h in hosts)


def _config():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import _expert as ex
    home = ex.expert_home()
    return ex.expert_config(home) if home else None


def decide(event, cfg=None):
    """The PreToolUse output for ``event``, or None to stay silent."""
    if not isinstance(event, dict) or event.get("tool_name") != "WebFetch":
        return None
    agent = ""
    for k in ("agent_type", "subagent_type", "agentType"):
        if event.get(k):
            agent = str(event[k])
            break
    ns, _, bare = agent.rpartition(":")
    if bare not in FETCHERS or ns not in ("", "expert"):
        return None
    if os.environ.get("ACADEMY_ALLOW_ANY_SOURCE") == "1":
        return None
    url = (event.get("tool_input") or {}).get("url")
    hosts = allowlist(cfg if cfg is not None else _config())
    host = host_of(url)
    if allowed(host, hosts):
        return None
    reason = ("%s is not on the Expert's allowlist of sources. Use a listed source (arXiv, "
              "the DOI resolver, zbMATH, the publisher's site, ...), or ask the human to add "
              "the host under expert.sources.allow in the library's .claude/academy.json "
              "(and, for a cloud run, to the environment's Allowed domains). Do not retry "
              "this host." % (host or "this URL"))
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--list" in argv:
        print("\n".join(allowlist(_config())))
        return 0
    raw = sys.stdin.read()
    if "WebFetch" not in raw:
        return 0
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return 0
    out = decide(event)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
