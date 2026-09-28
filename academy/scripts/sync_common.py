"""Vendor academy/lib/academy_common.py into every plugin as scripts/_academy.py.

    py academy/scripts/sync_common.py            copy the lib into all five plugins
    py academy/scripts/sync_common.py --check    exit 1 and name the drifted copies

The copy is byte-for-byte (plan section 1, "Shared code"). academy/tests/test_vendored.py
fails when a copy drifts, so run this after every change to the lib.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LIB = os.path.join(REPO, "academy", "lib", "academy_common.py")
PLUGINS = ("academy", "author", "researcher", "expert", "scientist")
VENDORED = os.path.join("scripts", "_academy.py")


def targets(repo=REPO):
    """Absolute paths of the five vendored copies."""
    return [os.path.join(repo, p, VENDORED) for p in PLUGINS]


def _read(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def drifted(repo=REPO):
    """The vendored copies that are missing or differ from the lib."""
    src = _read(os.path.join(repo, "academy", "lib", "academy_common.py"))
    return [t for t in targets(repo) if _read(t) != src]


def sync(repo=REPO):
    """Copy the lib over every drifted copy; return the paths written."""
    src = _read(os.path.join(repo, "academy", "lib", "academy_common.py"))
    if src is None:
        raise SystemExit("sync_common: cannot read the lib")
    written = []
    for t in drifted(repo):
        os.makedirs(os.path.dirname(t), exist_ok=True)
        with open(t, "wb") as fh:
            fh.write(src)
        written.append(t)
    return written


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        bad = drifted()
        for t in bad:
            print("drifted: %s" % os.path.relpath(t, REPO).replace("\\", "/"))
        return 1 if bad else 0
    for t in sync():
        print("wrote %s" % os.path.relpath(t, REPO).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
