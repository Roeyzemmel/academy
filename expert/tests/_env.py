"""The one switch for tests that read a real home of the workspace named by the environment.

The suites are hermetic: a test builds its own workspace, homes, board and library in a temp
directory, so its outcome depends on the repo and not on the machine. The exception is a
test that compares the code with the REAL data of a workspace (the real registries, the real
library). Such a test is opt-in: it runs only when ``ACADEMY_TEST_REAL=1`` is set, and never
when ``CI`` is set (the push gate sets it), because a failure caused by the state of
someone's library must not decide whether this repo may be pushed.

A test file that needs a real home takes it from ``real_home`` here, never from
``ACADEMY_WORKSPACE`` and friends directly (``test_no_real_home_leaks.py`` enforces that).
Each plugin that needs it carries its own copy of this file: plugins cannot import across
each other, so keep the copies identical (a test in the academy tree compares them).
"""
import json
import os


def enabled(environ=None):
    """True when real homes may be read: ACADEMY_TEST_REAL=1 and not on CI."""
    env = os.environ if environ is None else environ
    return env.get("ACADEMY_TEST_REAL") == "1" and not env.get("CI")


SKIP_REASON = "reads a real workspace home: set ACADEMY_TEST_REAL=1 (never on CI) to run it"


def real_home(**want):
    """The home of the first ``workspace.json`` instance matching ``want`` (role=..., ns=...),
    or '' when real homes are not enabled or the workspace has no such instance."""
    if not enabled():
        return ""
    try:
        with open(os.environ["ACADEMY_WORKSPACE"], encoding="utf-8-sig") as fh:
            ws = json.load(fh)
    except (KeyError, OSError, ValueError):
        return ""
    for inst in ws.get("instances", {}).values():
        if all(inst.get(k) == v for k, v in want.items()):
            return inst["home"]
    return ""
