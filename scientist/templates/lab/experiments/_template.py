#!/usr/bin/env python3
"""<One-line title of the experiment.>

Kind:           search      (or measure / verify -- fields for each in experiments/README.md)
Claims:         <registry ids, comma-separated, e.g. {{ns}}:foo, paper:prop:bar>
Goal:           <the phenomenon, as a checkable property P(X); a falsifier: "violates claim C">
Constraints:    - <constraint> [<feasibility | setting | excludes ...>]
                - <constraint> [<feasibility | setting | excludes ...>]
Properties:     <required: P; recorded: the extra properties saved for each example>
Certificate:    <what is saved per example so it can be rechecked without the search>
Validation:     <a known example AND a known non-example that P must classify correctly>
Needs Sage:     yes / no

Result:         <after the run: "found k ..." or "not found ...", over the constraints>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make `{{package}}` importable

from {{package}} import env  # noqa: E402

# env.require_sage(__doc__.splitlines()[0])   # uncomment for Sage experiments

CLAIMS = []   # the ids on the `Claims:` line; save_result stores them in the JSON


def validate():
    """Reproduce something known: a known example AND a known non-example.
    Raise if either comes out wrong; nothing below is trusted otherwise."""
    raise NotImplementedError


def run(bound):
    """Return (examples, raw): each example a dict {"certificate": ..., "recorded": {...}},
    and `raw`, whatever else is worth keeping (counts, timings, per-member data)."""
    raise NotImplementedError


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bound", type=float, default=20.0)
    args = ap.parse_args()

    env.banner(__file__)
    validate()
    examples, raw = run(args.bound)
    # measure: env.measure_outcome(values, cls); verify: env.verify_outcome(obj, {prop: bool}, routes)
    outcome = env.search_outcome(examples, constraints={"bound": args.bound})
    print(outcome["status"], outcome["count"])
    env.save_result(Path(__file__).stem, raw, script=__file__, claims=CLAIMS,
                    outcome=outcome)
