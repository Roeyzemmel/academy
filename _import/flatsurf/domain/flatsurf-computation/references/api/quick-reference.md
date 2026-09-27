# Removed API and the quick reference card (§10, §11)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

## 10. Deprecated / removed API — do not use

| Old / wrong | Current | Since |
|---|---|---|
| `s.delaunay_decomposition()` | `s.delaunay_decompose().codomain()` | deprecated 0.7.0 |
| `s.delaunay_triangulation()` | `s.delaunay_triangulate().codomain()` | deprecated 0.7.0 |
| `s.apply_matrix(m)` returning a surface | returns a **morphism**; use `m * s` or `.codomain()` | changed 0.7.0 |
| `s.subdivide_edges(...)` returning a surface | returns a morphism | changed 0.7.0 |
| `Singularity(...)` | `surface.point(label, coords)` | deprecated |
| `flatsurf.geometry.delaunay` module | `flatsurf.geometry.lazy` | renamed 0.7.0 |
| `flatsurf.geometry.relative_homology` | removed | 0.7.0 |
| `relabel(relabeling_map=...)` | `relabel(relabeling=...)`, integer labels by default | 0.7.0 |
| `circumscribing_circle()` | deprecated | 0.7.0 |
| SageMath 9.2–9.6 | unsupported | 0.7.0 |
| `stratum.zeros()`, `.genus()`, `.nb_zeros()`, `.nb_fake_zeros()`, `.nb_poles()` | `.signature()`, `.surface_genus()` | deprecated 0.6.0 (surface-dynamics) |
| `teichmueller_curve.cusps()` | `cusp_representatives()` | **never existed** in current source |
| `SaddleConnection.start()` / `.end()` | `start_data()` / `end_data()` | **do not exist** |
| `surface.cylinder_decomposition(direction)` | `GL2ROrbitClosure(S).decomposition(direction)` | **does not exist** in sage-flatsurf |
| `surface.insert_marked_points(...)` | no such method; see §7.2(b) | **does not exist** in 0.8.0 |
| sage-flatsurf `veech_group().gens()` | `NotImplementedError`; use surface_dynamics | as of 0.8.0 |
| `origamis.Ornithorynque()` | `origamis.CyclicCover([1,1,1,3])` (12 squares, `H_4(2^3)^even`) | **never existed**; see §6.7 |
| `o.horizontal_twist(k=...)` / `vertical_twist(k=...)` | the keyword is **`width`**, not `k` | signature `(width=1, cylinder=None)` |
| `from sage.libs.gap.libgap import libgap` as first Sage import under plain `python` | `from sage.all import libgap` | circular ImportError, Sage 10.7; see 12.2 |
| `import pyflatsurf`, `canonicalize()`, `GL2ROrbitClosure` in an env reached by `PATH` only | a full `conda activate` (what `scripts/run.sh` does since 2026-09-22) | segfault in cling's `AddHostArguments` otherwise; also keep `gxx`/`gcc` at 14 (cling cannot parse gcc-16 headers). Fixed on lingo and WSL 2026-09-22; see 12.4 |

Older tutorials (the "Warwick 2017" page, anything referencing `flatsurf` ≤ 0.5) use
`Surface_list`, `TranslationSurface(...)` wrappers, and `.underlying_surface()`. Those wrappers
are gone or vestigial; the current object model is: a surface **is** its own parent, categories
carry the methods, and mutability is explicit.

---

## 11. Quick reference card

```python
# ---- setup -------------------------------------------------------------
from flatsurf import (Polygon, polygons, EuclideanPolygonsWithAngles,
                      MutableOrientedSimilaritySurface,
                      translation_surfaces, similarity_surfaces, dilation_surfaces,
                      GL2ROrbitClosure, HyperbolicPlane)
from surface_dynamics import Origami, origamis, Stratum, OrigamiDatabase

# ---- unfold ------------------------------------------------------------
T = polygons.triangle(1, 4, 7)
S = similarity_surfaces.billiard(T).minimal_cover('translation')
S = S.erase_marked_points()
S.stratum(); S.base_ring(); S.plot()

# ---- saddle connections (bound is SQUARED length) ----------------------
for sc in S.saddle_connections(squared_length_bound=100):
    sc.holonomy(); sc.length(); sc.direction()
    sc.start_data(); sc.end_data(); sc.invert(); sc.plot()

# ---- trajectories ------------------------------------------------------
v = S.tangent_vector(label, (x, y), (dx, dy))
tr = v.straight_line_trajectory(); tr.flow(200)
tr.is_closed(); tr.is_saddle_connection(); tr.cylinder(); tr.coding(); tr.plot()

# ---- flow / cylinder decomposition ------------------------------------
O   = GL2ROrbitClosure(S)
dec = O.decomposition(direction, limit=1024)
dec.cylinders(); dec.minimalComponents(); dec.parabolic()
[c.area()/2 for c in dec.cylinders()]        # NB: area() is twice the area

# ---- GL(2,R), Delaunay, equality --------------------------------------
(matrix([[2,1],[1,1]]) * S).canonicalize() == S.canonicalize()
S.delaunay_decompose().codomain()

# ---- origamis ----------------------------------------------------------
o = Origami("(1,2)", "(1,3)")
o.stratum(); o.stratum_component(); o.is_primitive(); o.cylinder_decomposition()
G = o.veech_group(); G.index(); G.ncusps(); G.cusp_widths(); G.is_congruence()
t = o.teichmueller_curve(); t.sum_of_lyapunov_exponents(); t.cusp_representatives()
o.lyapunov_exponents_approx()

# ---- strata ------------------------------------------------------------
Stratum([2], k=1).components(); Stratum([2], k=1).dimension()
Stratum([2], k=1).masur_veech_volume(); Stratum([4], k=1).odd_component().rank()

# ---- database ----------------------------------------------------------
D = OrigamiDatabase(); D.query(stratum=Stratum([2]), nb_squares=9).list(); D.info()
```

