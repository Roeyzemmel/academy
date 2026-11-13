"""Vendor the package academy/lib/academy_common/ into every plugin as scripts/_academy/.

    py academy/scripts/sync_common.py            copy the lib into all five plugins
    py academy/scripts/sync_common.py --check    exit 1 and name the drifted copies

The copy is byte-for-byte, file by file (plan section 1, "Shared code"): every ``*.py`` of
the package and nothing else. academy/tests/test_vendored.py fails when a copy drifts, so
run this after every change to the lib. A copy has drifted when a file is missing, differs
or is extra, or when the single-file copy of before the split (``scripts/_academy.py``) is
still there; syncing removes the extras.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LIB = os.path.join(REPO, "academy", "lib", "academy_common")
PLUGINS = ("academy", "author", "researcher", "expert", "scientist")
VENDORED = os.path.join("scripts", "_academy")
#: the vendored single file of before the split; never beside the package
LEGACY = os.path.join("scripts", "_academy.py")


def lib_dir(repo=REPO):
    """The package that is vendored."""
    return os.path.join(repo, "academy", "lib", "academy_common")


def targets(repo=REPO):
    """Absolute paths of the five vendored copies (package directories)."""
    return [os.path.join(repo, p, VENDORED) for p in PLUGINS]


def _read(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def modules(directory):
    """The package's files in ``directory``: {name: bytes} of its ``*.py``."""
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".py"))
    except OSError:
        return {}
    return {n: _read(os.path.join(directory, n)) for n in names}


def _legacy(target):
    return os.path.join(os.path.dirname(os.path.dirname(target)), LEGACY)


def drifted(repo=REPO):
    """The vendored copies that are missing or differ from the lib."""
    src = modules(lib_dir(repo))
    return [t for t in targets(repo)
            if modules(t) != src or os.path.exists(_legacy(t))]


def sync(repo=REPO):
    """Copy the lib over every drifted copy; return the paths written or removed."""
    src = modules(lib_dir(repo))
    if "__init__.py" not in src or None in src.values():
        raise SystemExit("sync_common: cannot read the lib")
    changed = []
    for t in drifted(repo):
        os.makedirs(t, exist_ok=True)
        have = modules(t)
        for name, data in src.items():
            if have.get(name) != data:
                with open(os.path.join(t, name), "wb") as fh:
                    fh.write(data)
                changed.append(os.path.join(t, name))
        for extra in [os.path.join(t, n) for n in have if n not in src] + [_legacy(t)]:
            if os.path.exists(extra):
                os.remove(extra)
                changed.append(extra)
    return changed


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        bad = drifted()
        for t in bad:
            print("drifted: %s" % os.path.relpath(t, REPO).replace("\\", "/"))
        return 1 if bad else 0
    for t in sync():
        print("%s %s" % ("wrote" if os.path.exists(t) else "removed",
                         os.path.relpath(t, REPO).replace("\\", "/")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
