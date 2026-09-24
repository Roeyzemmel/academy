# Sources, and the original status note of api-recipes.md

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

# Computational Tools for Translation Surfaces and Illumination

**Status of this document.** Every API call below was checked against the *current* official
documentation (sage-flatsurf 0.8.0 and surface-dynamics 0.7.0) on **2026-09-08**. Wherever a
snippet is reproduced from an official tutorial or doctest, it is tagged **[VERIFIED-DOC]** and
the source page is named. Snippets that I composed myself out of verified primitives, but could
not execute, are tagged **[UNVERIFIED]**. The two pure-Python fallback programs in §7 were
**actually executed** in this session and their test output is reproduced verbatim.

I did **not** have a SageMath installation available, so nothing Sage-flavoured here has been run
end to end. The verification standard is "every identifier and keyword appears in current
upstream docs", which is enough to avoid the main failure mode (silently calling a removed API),
but not enough to guarantee a whole script runs.

---

### Sources

- [sage-flatsurf documentation (0.8.0)](https://flatsurf.github.io/sage-flatsurf/)
- [sage-flatsurf: Defining Surfaces](https://flatsurf.github.io/sage-flatsurf/examples/defining_surfaces.html)
- [sage-flatsurf: Tour of the flatsurf suite](https://flatsurf.github.io/sage-flatsurf/examples/tour.html)
- [sage-flatsurf: Working with Saddle Connections](https://flatsurf.github.io/sage-flatsurf/examples/saddle_connections.html)
- [sage-flatsurf: Straight-Line Flow](https://flatsurf.github.io/sage-flatsurf/examples/straight_line_flow.html)
- [sage-flatsurf: Exploring Orbit Closures](https://flatsurf.github.io/sage-flatsurf/examples/apisa_wright.html)
- [sage-flatsurf: Boshernitzan's Conjectures](https://flatsurf.github.io/sage-flatsurf/examples/boshernitzan_conjecture.html)
- [sage-flatsurf: Siegel–Veech constants](https://flatsurf.github.io/sage-flatsurf/examples/siegel_veech.html)
- [sage-flatsurf: linear action and Delaunay](https://flatsurf.github.io/sage-flatsurf/examples/linear_action_and_delaunay.html)
- [sage-flatsurf: installation](https://flatsurf.github.io/sage-flatsurf/install.html)
- [sage-flatsurf: similarity_surfaces category](https://flatsurf.github.io/sage-flatsurf/geometry/categories/similarity_surfaces.html)
- [sage-flatsurf: translation_surfaces category](https://flatsurf.github.io/sage-flatsurf/geometry/categories/translation_surfaces.html)
- [sage-flatsurf: surface_objects (SurfacePoint, SaddleConnection)](https://flatsurf.github.io/sage-flatsurf/geometry/surface_objects.html)
- [sage-flatsurf: straight_line_trajectory](https://flatsurf.github.io/sage-flatsurf/geometry/straight_line_trajectory.html)
- [sage-flatsurf: gl2r_orbit_closure](https://flatsurf.github.io/sage-flatsurf/geometry/gl2r_orbit_closure.html)
- [sage-flatsurf: veech_group module](https://flatsurf.github.io/sage-flatsurf/geometry/veech_group.html)
- [sage-flatsurf releases](https://github.com/flatsurf/sage-flatsurf/releases)
- [sage-flatsurf on PyPI](https://pypi.org/project/sage-flatsurf/)
- [surface-dynamics documentation (0.7.0)](https://flatsurf.github.io/surface-dynamics/)
- [surface-dynamics: Square-tiled Surfaces](https://flatsurf.github.io/surface-dynamics/examples/square_tiled_surfaces.html)
- [surface-dynamics: Origamis](https://flatsurf.github.io/surface-dynamics/origamis.html)
- [surface-dynamics: strata](https://flatsurf.github.io/surface-dynamics/flat_surfaces/strata.html)
- [surface-dynamics: teichmueller_curve source](https://github.com/flatsurf/surface-dynamics/blob/master/surface_dynamics/flat_surfaces/origamis/teichmueller_curve.py)
- [surface-dynamics releases](https://github.com/flatsurf/surface-dynamics/releases)
- [surface-dynamics on PyPI](https://pypi.org/project/surface-dynamics/)
- [SageMath: arithmetic subgroups defined by permutations](https://doc.sagemath.org/html/en/reference/arithgroup/sage/modular/arithgroup/arithgroup_perm.html)
- [The GAP package Origami (Veech groups of origamis), v2.0.1](https://ag-weitze-schmithusen.github.io/Origami/doc/manual.pdf)
