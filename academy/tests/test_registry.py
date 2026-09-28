"""The registry engine's own tests (academy/registry/tests), collected here so that
``py -m unittest discover academy/tests`` runs them with the rest of the base plugin.

The nested tree is loaded through its own, fresh ``TestLoader().discover(...)`` with
an explicit ``top_level_dir=REG_TESTS`` -- never through the ``loader`` this hook is
given. ``TestLoader.discover`` records the top-level directory it is given on the
loader instance itself (``self._top_level_dir``) and reuses it for every path it
resolves afterwards; if the *outer* discovery's own loader were reused here, that
assignment would clobber the outer top-level directory for every file the outer
discovery still has to process (``test_render.py``, ``test_vendored.py``, ...),
which then fails resolving their paths against the registry's directory with
``AssertionError: Path must be within the project`` (``TestLoader._get_name_from_path``,
``unittest/loader.py``). A private loader keeps that state scoped to this call."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG_TESTS = os.path.join(os.path.dirname(HERE), "registry", "tests")


def load_tests(loader, tests, pattern):
    return unittest.TestLoader().discover(REG_TESTS, pattern=pattern or "test_*.py",
                                          top_level_dir=REG_TESTS)
