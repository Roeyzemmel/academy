# experiments/

One file per experiment, `YYYY-MM-DD_<slug>.py`, started from `_template.py`. The
docstring header is the contract. It is written and agreed **before** computing and
frozen once the run's `Result:` is filled in. What to do next goes in the claim's
`open:` list in the registry, never in the header. The discipline behind the kinds is
the Scientist's `experiment-method` skill; the checker (`check_experiments.py`) enforces
the shape. Scaffolded by `/academy:init` from the Scientist plugin's `templates/lab/`:
add this lab's own scope defaults below.

Checks on code (does `{{package}}.x` compute what it should) are tests in `tests/`, not
experiments. A test too slow for the laptop is still a test, run through the queue.

## Scope defaults

<!-- This lab's standing choices (which objects, which points, which arithmetic), each
with who decided it and when. A class outside them must say why in its header. -->

## Three kinds

Every header starts with `Kind:` and `Claims:` (registry ids).

### `search`: look for an example of a phenomenon

A falsifier is a search whose phenomenon is "violates claim C".

```
Kind:         search
Claims:       {{ns}}:<id>
Goal:         the phenomenon, written as a checkable property P(X)
Constraints:  - at most 16 vertices              [feasibility]
              - every corner marked              [setting]
              - cyclic covers only               [excludes non-cyclic covers]
Properties:   required: P
              recorded: the invariants worth keeping for each example
Certificate:  what is saved per example so it can be rechecked without the search
Validation:   a known example AND a known non-example that P must classify correctly
Needs Sage:   yes / no
Result:       found <k> ... / not found ...
```

- **Found** is the strong outcome: an existence statement, which a proof may follow once
  the certificate is rechecked independently (through proof review, not here).
- **Not found** means only "not found under these constraints".
- Every constraint carries a reason tag:
  - `[feasibility]`: added so the search terminates; the first thing to relax.
  - `[setting]`: part of the question itself.
  - `[excludes …]`: known to rule out part of the phenomenon, with the reason.
- **Required** properties decide "found". **Recorded** properties are what make a found
  example useful afterwards.
- The validation case needs a non-example as well as an example, because a bug in P
  shows up as a false positive.

### `measure`: compute a quantity over a class

```
Kind:         measure
Claims:       {{ns}}:<id>
Goal:         what is measured, and why
Class:        the objects measured; name what is NOT covered
Quantity:     the exact definition of what is computed
Validation:   a case whose value is known independently
Needs Sage:   yes / no
Result:       the values, or where they are in the JSON
```

### `verify`: decide whether one named object has a property

```
Kind:         verify
Claims:       {{ns}}:<id>
Goal:         the question about the object
Object:       exactly how the object is constructed
Properties:   the properties to decide
Method:       how each is decided; two independent routes where the result will be cited
Validation:   a known object on which the same method gives a known answer
Needs Sage:   yes / no
Result:       per property: holds / fails
```

A fourth kind, `probe` (is it computable, how large does it get), produces a
recommendation for a report, not evidence.

## The result JSON

`env.save_result(name, raw, script=__file__, claims=CLAIMS, outcome=...)` writes:

```
{"claims":  ["{{ns}}:..."],
 "outcome": {"kind": "search", "status": "found" | "not found", "count": k,
             "constraints": {...the parameters actually used...},
             "examples": [{"certificate": {...}, "recorded": {...}}]},
 "provenance": {...commit, versions, argv...},
 "result":  {...raw data...}}
```

- `outcome` is built by `env.search_outcome(examples, constraints)`,
  `env.measure_outcome(values, cls)` or `env.verify_outcome(obj, {prop: bool}, routes)`,
  and comes first in the file, so the answer can be read without the raw data.
- The checker requires `outcome=` in every script with a `Kind:` header (E10), a call to
  `env.banner` (E6) and to `env.save_result` (E5).
- A result JSON is evidence stamped with its commit: never edit one; rerun instead.

## From result to registry

A result is cited only after `/researcher:review-experiment` gives two `SOUND` audits,
and the status is set by claim-keeper (`academy:status-vocabulary`). Computation never
reaches `proved`:

| Outcome | Claim status |
|---|---|
| search: found, certificate rechecked | `supported` for the existence claim; a proof from the certificate goes to proof review |
| search: not found | the existence claim stays `open`, noting "not found under constraints …" (never `refuted`) |
| falsifier: a counterexample found and rechecked | the claim under test `refuted` (or `refuted-as-stated`) |
| falsifier: no counterexample | the claim, restricted to the constraints, `supported` |
| measure | `supported` (the values are in the evidence note) |
| verify: holds / fails, two routes | `supported` / `refuted` |
| verify: one route only | evidence only; the status does not move |

## Running

Where a run happens is the lab's run policy (`scientist.policy` in `.claude/academy.json`):
`env.py queue add experiments/<file>.py --label <claim-id>` files it on the queue
(`/scientist:queue`).
