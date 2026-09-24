# Reviewing Sage / flatsurf code

The checklist for any review of code that builds or measures translation surfaces:
`fslab/` changes, experiment scripts, a result under audit. It replaces the planned
`sage-audit` / `sage-reviewer` agents: hand it to whatever reviewer runs (in FlatSurfLab,
`superpowers:requesting-code-review`; for a result, `flatsurf:result-auditor`).

**The API traps are not repeated here.** They live in FlatSurfLab's `docs/api-traps.md`
(the ones this project hit) and the `flatsurf-computation` skill's `references/api/` (the
general list; `INDEX.md` routes, `quick-reference.md` has the removed API). Read the first before reviewing; check each trap against the code.

## The questions

1. **Shadow.** What would this code still report if the claim were false? A comparison
   of sets survives a relabelling, so it proves nothing about labels being fixed.
2. **Bounds.** Every bound's units: `saddle_connections(squared_length_bound=B)` is
   squared. A header "length 40" from `B = 40` is a result at length 6.3.
3. **Labels.** Every index's base (0 or 1) and every call that relabels
   (`cylinder_decomposition()`, the SL(2,Z) twists). Tracked points survive only a
   generator-at-a-time walk (`fslab/vh.py`).
4. **Cone points.** A cone point of multiplicity `m` is `m` fine-grid corners; "touches
   this cylinder" unions over the whole `vertex_class`.
5. **Stratum.** Printed at every stage, and equal to what the header says. Marked points
   and unfolding covers change it.
6. **Exactness.** No float decides a coincidence, containment or equality. `Fraction`,
   number fields, exact reals.
7. **Validation.** `validate()` raises, runs before anything is trusted, and would fail
   on a broken pipeline: a known example *and* a known non-example for a search.
8. **Provenance.** `env.banner(__file__)` first, `env.save_result(...)` last, with
   `claims=[...]` naming registry ids; the header's `Claims:` line agrees.
9. **Reuse.** No `fslab` code copied into a script; no hand-rolled version of something
   sage-flatsurf or surface_dynamics does (FlatSurfLab's `docs/code-audit.md` lists the
   known duplicates). A pure-Python path needs a measured runtime reason in the header.
10. **The class.** What the search structurally could not contain is written down.

A finding cites `file:line` and says what it breaks. "Looks fine" is not a review.
