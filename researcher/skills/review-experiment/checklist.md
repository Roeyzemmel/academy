# Reviewing a computed result: the checklist

The checklist for any experiment review (plan section 8): a result under
`/researcher:review-experiment` or `/researcher:settle`, read by `experiment-reviewer`.
It is generic. **The library traps of the domain are not repeated here**: they live
in the domain pack, read with `domain_get` on the instance's domain —
`computation/api/INDEX.md` routes to the per-topic trap files, and `traps.md` holds the
mathematical traps. Read the ones the script's calls touch, and check each against the
code. A trap that bit and is not in the pack is a finding, and a ticket to the
Scientist's `api-prober` afterwards.

## The questions

1. **Shadow.** What would this code still report if the claim were false? A comparison
   that survives a symmetry, a relabelling or a change of basis proves nothing about
   the thing the symmetry moves.
2. **Bounds and units.** Every bound's units as the library defines them (squared vs
   linear, inclusive vs exclusive, per-component vs total). A header's "bound 40"
   computed with a squared parameter of 40 is a result at about 6.3.
3. **Indices and labels.** Every index's base (0 or 1), and every call that relabels
   or re-normalises its output. A tracked object survives only the operations
   documented to preserve its labels.
4. **Degenerate and special points.** Singular points, multiplicities, boundary cases:
   is each counted the way the claim counts it (a point of multiplicity m may be m
   corners, cells or sheets in the library's model)?
5. **The object.** Is the object computed the object the header names, at every
   stage? Printed invariants must match the header; covers, markings and
   normalisations change them.
6. **Exactness.** No float decides a coincidence, containment or equality. Exact
   rationals, number fields or certified intervals; where a threshold is unavoidable,
   it is named and its effect on the conclusion stated.
7. **Validation.** The validation case runs before anything is trusted, raises on
   failure, and would fail on a broken pipeline: a known example **and**, for a
   search, a known non-example.
8. **Provenance.** The run is stamped first and saved last with its commit hash, its
   environment profile and the claim ids it bears on; the header's claims line
   agrees; the commit is the one whose script you read.
9. **Reuse.** No library code copied into the script; no hand-rolled version of
   something the lab's package or the upstream library already does; a slower
   fallback path carries a measured reason.
10. **The class.** What the search or measurement structurally could not contain is
    written down, in the header and in the report's `## Conclusion`.
11. **The conclusion.** The report's `## Conclusion` claims no more than the
    computation shows: "no counterexample over class C below bound B", never "true";
    a proposed status of `supported`/`refuted`, never `proved`.

A finding cites `file:line` and says what it breaks. "Looks fine" is not a review.
