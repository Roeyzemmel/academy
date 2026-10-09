#!/usr/bin/env python3
"""registry.py -- the claim-registry command line, callable from any directory.

    py <academy>/academy/scripts/registry.py [--repo PATH] <command> ...

The same as ``py -m registry`` run from ``<academy>/academy`` (see registry/cli.py for
the commands), for every registry: the repo (default: the current directory) decides
the namespace and the profile. It replaces the lab's ``scripts/claims.py``, the paper's
use of it and a notebook's ``tools/kb.py``, which were shims onto the same engine.
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_engine_root = os.path.dirname(_here)          # <academy>/academy, holds the registry package
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)

from registry.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
