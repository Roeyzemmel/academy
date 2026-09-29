"""The registry profiles: one per rule set, chosen per namespace (core.workspace).

``fsl-claims`` (rule sets ``lab`` and ``paper``) is the lab's claims.py on the core;
``s1-kb`` (rule set ``s1``) is Slope1's kb.py on the core.
"""
from pathlib import Path

from ..core import workspace


def module(engine_profile):
    if engine_profile == "s1-kb":
        from . import s1kb
        return s1kb
    from . import fsl
    return fsl


def store_for(ns, home):
    """Load namespace ``ns`` of ``home`` through its profile (a core.model.Store)."""
    home = Path(home)
    prof = workspace.engine_profile(ns, home)
    if prof == "s1-kb":
        from .s1kb import S1Store
        return S1Store(ns, home)
    from .fsl import FslStore
    return FslStore(ns, home)
