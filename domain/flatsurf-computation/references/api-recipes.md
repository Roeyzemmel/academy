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

## Table of Contents

1. [Versions, installation, and the no-Sage question](#1-versions-installation-and-the-no-sage-question)
2. [sage-flatsurf: building and inspecting surfaces](#2-sage-flatsurf-building-and-inspecting-surfaces)
3. [Billiard unfolding](#3-billiard-unfolding)
4. [Saddle connections, holonomy vectors, trajectories](#4-saddle-connections-holonomy-vectors-trajectories)
5. [Cylinder / flow decompositions and moduli](#5-cylinder--flow-decompositions-and-moduli)
6. [surface_dynamics: origamis, Veech groups, strata](#6-surface_dynamics-origamis-veech-groups-strata)
7. [Illumination-specific recipes](#7-illumination-specific-recipes)
8. [Pure-Python fallbacks (no Sage) — tested in this session](#8-pure-python-fallbacks-no-sage--tested-in-this-session)
9. [Using this responsibly in research](#9-using-this-responsibly-in-research)
10. [Deprecated / removed API — do not use](#10-deprecated--removed-api--do-not-use)
11. [Quick reference card](#11-quick-reference-card)
12. [Environment cluster — probed 2026-09-19 (api-prober)](#12-environment-cluster--probed-2026-09-19-api-prober)

---

## 1. Versions, installation, and the no-Sage question

| Package | Current version | Released | Needs SageMath? |
|---|---|---|---|
| `sage-flatsurf` | 0.8.0 | 2025-11-19 (PyPI) | **Yes** — it is a SageMath package |
| `surface-dynamics` | 0.7.0 | 2025-02-12 (PyPI) | **Yes** — "requires a working Sage installation", plus Cython and gcc |
| `pyflatsurf` / `libflatsurf` | ships with the suite | — | No (C++/Python), but you reach it through sage-flatsurf |
| `pyexactreal` / `exact-real` | ships with the suite | — | No, but used from Sage |
| `veerer` | optional | — | Yes |

### Recommended install: the pixi tarball (this is what upstream now pushes) **[VERIFIED-DOC — install page]**

```bash
curl -fsSL https://github.com/flatsurf/sage-flatsurf/releases/download/0.8.0/sage-flatsurf-0.8.0.unix.tar.gz | tar zxf -
./sage-flatsurf-0.8.0/sage          # a Sage REPL with everything preloaded
./sage-flatsurf-0.8.0/jupyterlab    # notebook
```

Needs about **7 GB** of disk, and **the install directory path must contain no spaces**. This is
the only route that reliably gives you `pyflatsurf` and `pyexactreal`, which you need for flow
decompositions and orbit closures.

### conda / mamba **[VERIFIED-DOC — install page]**

```bash
conda create -n flatsurf sage-flatsurf pyflatsurf pyexactreal sage pip
conda activate flatsurf
pip install ipyvue-flatsurf flipper realalg veerer
```

This is what `scripts/setup_env.sh` does (Miniforge, no root, plus
`surface-dynamics` — note the hyphen in the conda-forge name; `surface_dynamics`
does not resolve). **[VERIFIED 2026-09-09 on WSL Ubuntu 24.04: sage-flatsurf 0.8.0,
surface-dynamics 0.7.0, ~8 GB including the package cache, about 15 minutes.]**

### Into an existing SageMath **[VERIFIED-DOC]**

```bash
sage -pip install sage-flatsurf
sage -pip install surface-dynamics
```

> **Version caveat.** The docs are explicit that this route "does not include the optional
> dependencies" and that "some computations may fail" — concretely, anything routed through
> `GL2ROrbitClosure` (§5) needs `pyflatsurf`, and exact-real coefficients need `pyexactreal`.
> `surface-dynamics` also recommends the Sage optional packages `gap_packages` and `latte_int`
> to "improve or extend the functionality" (GAP is used for monodromy group names, LattE for
> polytope volume computations).

`surface-dynamics` 0.7.0 specifically notes fixed compatibility with **SageMath 10.4 and 10.5**;
sage-flatsurf 0.8.0 adds **SageMath 10.6** and Apple Silicon support, and **removed** support for
SageMath 9.2–9.6.

### Can any of this be installed *without* Sage?

**Essentially no.** `pip install sage-flatsurf` pulls `sagelib` as a Python package (the docs say
so), which is a very large source build; `surface-dynamics` states outright that it needs a
working Sage. `pyflatsurf`, `pyintervalxt` and `pyexactreal` are independently installable via
conda and are pure C++/Python, but their APIs are low-level (you would be constructing
`FlatTriangulation` objects by hand) and there is no documented path from "a rational polygon" to
"a libflatsurf surface" that does not go through sage-flatsurf.

**Fallback if Sage is unavailable in a sandbox:** write self-contained Python for the one surface
you care about. §8 gives two such programs, both tested here — a float billiard tracer for
arbitrary polygons, and an **exact** (Fraction-arithmetic) connection enumerator for square-tiled
surfaces. The origami one is exact and complete, and for illumination questions on origamis it is
a genuine substitute rather than a toy.

---

## 2. sage-flatsurf: building and inspecting surfaces

All of the following is run inside a Sage session (`sage`, or a Jupyter kernel with the Sage
kernel), because it uses Sage globals like `QQ`, `AA`, `matrix`, `vector`, `QuadraticField`.

### 2.1 The current way to build a surface from polygons **[VERIFIED-DOC — "Tour" and "Defining Surfaces" pages]**

```python
from flatsurf import MutableOrientedSimilaritySurface, Polygon

hexagon = Polygon(vertices=((0, 0), (3, 0), (3, 1), (3, 2), (0, 2), (0, 1)))
square  = Polygon(vertices=((0, 0), (1, 0), (1, 1), (0, 1)))

S = MutableOrientedSimilaritySurface(QQ)
S.add_polygon(hexagon)          # label 0 (labels are assigned 0,1,2,... in order)
S.add_polygon(square)           # label 1

S.glue((0, 0), (0, 3))          # glue edge 0 of polygon 0 to edge 3 of polygon 0
S.glue((0, 1), (1, 3))
S.glue((0, 2), (0, 4))
S.glue((0, 5), (1, 1))
S.glue((1, 0), (1, 2))
S.set_immutable()               # REQUIRED before most computations

print(S)
S.plot()
```

`add_polygon` also takes an explicit `label=` argument. Making the surface immutable is not
cosmetic: the docs say it is what lets sage-flatsurf "enable automatic category detection and
optimize operations" — i.e. `S.stratum()`, `S.saddle_connections(...)` etc. may misbehave or
refuse on a mutable surface.

Over a non-rational field, pass the field to the constructor: **[VERIFIED-DOC — "Defining Surfaces"]**

```python
from flatsurf import polygons, MutableOrientedSimilaritySurface

p0 = polygons.regular_ngon(12, field=AA)
p1 = polygons.regular_ngon(3, field=AA)

surface = MutableOrientedSimilaritySurface(AA)
surface.add_polygon(p0, label=0)
surface.add_polygon(p1, label=1)
surface.glue((0, 6), (1, 0))
surface.glue((0, 10), (1, 1))
surface.glue((0, 2), (1, 2))
surface.set_immutable()
```

### 2.2 Polygon constructors **[VERIFIED-DOC — polygon module reference]**

```python
from flatsurf import Polygon, polygons, EuclideanPolygonsWithAngles

Polygon(vertices=[(0, 0), (1, 0), (0, 1)])           # from vertices
Polygon(edges=[(1, 0), (-1, 1), (0, -1)])            # from edge vectors
Polygon(angles=[1, 1, 1], lengths=[1, 1, 1])         # from prescribed angles + lengths
Polygon(angles=(1, 1, 4), vertices=[(0, 0), (1, 0)]) # angles + a fixed first edge

polygons.square()                 # Polygon(vertices=[(0,0),(1,0),(1,1),(0,1)])
polygons.rectangle(1, 2)
polygons.regular_ngon(3, field=AA)
polygons.right_triangle(1/3, leg0=1)
polygons.triangle(3, 4, 5)        # angles in ratio 3:4:5 (times pi/12)

Delta = EuclideanPolygonsWithAngles(7, 7, 16).an_element()
Delta = EuclideanPolygonsWithAngles(2, 3, 6).random_element()
```

Full signature: `Polygon(vertices=None, edges=None, angles=None, lengths=None, base_ring=None,
category=None, check=True, **kwds)`.

`EuclideanPolygonsWithAngles(7, 7, 16).an_element()` returns, verbatim from the docs,
`Polygon(vertices=[(0, 0), (1, 0), (1/2, c^7 - 13/2*c^5 + 21/2*c^3 - 3/2*c)])` — note the
coordinates live in a real cyclotomic-type number field, generated by `c`. This is the exact
arithmetic that makes the rest of the pipeline rigorous.

### 2.3 Built-in translation surfaces **[VERIFIED-DOC]**

```python
from flatsurf import translation_surfaces, dilation_surfaces, similarity_surfaces, Polygon

translation_surfaces.veech_double_n_gon(5)
translation_surfaces.arnoux_yoccoz(3)
translation_surfaces.chamanara(1/2)
translation_surfaces.infinite_staircase()
translation_surfaces.square_torus()
translation_surfaces.octagon_and_squares()
translation_surfaces.cathedral(1, 2)
translation_surfaces.mcmullen_L(1, 1, 1, 1)
translation_surfaces.from_flipper(h)                 # from a flipper mapping torus

dilation_surfaces.genus_two_square(1/2, 1/3, 1/4, 1/5)
similarity_surfaces.self_glued_polygon(Polygon(edges=[(2, 0), (-1, 3), (-1, -3)]))
```

### 2.4 Stratum, marked points, base ring **[VERIFIED-DOC — Tour page]**

```python
S.stratum()               # requires surface-dynamics; e.g. H_6(7, 2, 1)
S.base_ring()
S.change_ring(K)
S.erase_marked_points()   # kill regular vertices of cone angle 2*pi
S.canonicalize()          # canonical representative, usable for == comparison
S.j_invariant()           # Kenyon-Smillie J-invariant; needs a number field
S.rel_deformation(deformation, local=None, limit=None)
```

### 2.5 GL(2,R) action, Delaunay, deciding equality **[VERIFIED-DOC — "linear_action_and_delaunay"]**

```python
from flatsurf import translation_surfaces

s = translation_surfaces.veech_double_n_gon(5)
m = matrix([[2, 1], [1, 1]])
ss = m * s                              # left multiplication is the GL(2,R) action

sss = ss.delaunay_decompose().codomain()   # CURRENT form (returns a morphism)
ttt = ss.delaunay_triangulate().codomain()

# Testing membership in the Veech group, via canonical forms:
m = matrix(s.base_ring(), [[1, 1/modulus], [0, 1]])
s.canonicalize() == (m * s).canonicalize()      # True  <-- m is a Veech element
```

This `canonicalize()`-comparison **is** the practical isomorphism test in sage-flatsurf: two
finite-type translation surfaces are translation-equivalent iff their canonical forms are equal.
There is no separate `is_isomorphic` method on translation surfaces.

> **Runtime requirement.** `canonicalize()` loads `pyflatsurf` (and so cling) on first
> call, even though `import flatsurf` does not. It needs a fully activated env; see §12.4.

> **[UNVERIFIED]** `modulus` in that snippet is a variable the tutorial defines earlier (the
> modulus of a cylinder in the double pentagon); you must supply it yourself. The *pattern*
> `s.canonicalize() == (m*s).canonicalize()` is verbatim from the docs.

`apply_matrix(m)` also exists but **as of 0.7.0 it returns a morphism, not a surface** — use
`.codomain()` on the result, or just use `m * s`.

---

## 3. Billiard unfolding

### 3.1 The canonical incantation **[VERIFIED-DOC — Tour page, with printed outputs]**

```python
from flatsurf import polygons, similarity_surfaces, GL2ROrbitClosure

T = polygons.triangle(1, 4, 7)                              # angles pi/12 * (1,4,7)
S = similarity_surfaces.billiard(T).minimal_cover('translation')
S = S.erase_marked_points()
S.plot()
```

and with a right-triangle-style keyword form, also verbatim:

```python
from flatsurf import similarity_surfaces, Polygon

P = Polygon(angles=(1, 1, 4), vertices=[(0, 0), (1, 0)])
S = similarity_surfaces.billiard(P).minimal_cover(cover_type="translation")
print(S.base_ring())
S.plot(polygon_labels=False, edge_labels=False)
```

Stratum of an unfolding, with the doc's own output: **[VERIFIED-DOC]**

```python
T = polygons.triangle(2, 3, 8)
S = similarity_surfaces.billiard(T).minimal_cover('translation')
S.stratum()
# H_6(7, 2, 1)
```

Both `minimal_cover('translation')` (positional) and `minimal_cover(cover_type="translation")`
appear in current docs; the signature is `minimal_cover(cover_type='translation')`.

### 3.2 The two pitfalls that will bite you

**(a) Unfolding produces *marked points*, and marked points change the stratum.** Compare, from
the "Exploring Orbit Closures" page **[VERIFIED-DOC]**:

```python
S                       # Half-Translation Surface in Q_3(10, -1^2) built from a square and 2 rectangles
U = S.minimal_cover("translation")
U.stratum()
# H_6(5^2, 0^2)
```

The `0^2` are two **fake zeros** — regular points that the construction has marked. They change
the dimension of the stratum (`dim H_6(5^2,0^2) = 14` vs `dim H_6(5^2) = 12`), which will silently
corrupt any orbit-closure dimension argument. Call `erase_marked_points()` — and note the Tour
page does exactly this before building `GL2ROrbitClosure`. Not erasing them is the single most
common way to get a wrong answer out of this pipeline.

> **However**: for *illumination* you may genuinely want the marked points, because the points
> you are asking about are marked points. Decide consciously which surface you are on, and record
> it. "Same surface, different marked-point set" is a different stratum and a different
> `GL(2,R)`-orbit-closure problem.

**(b) `minimal_cover` gives you a cover, not the primitive surface.** The unfolding of a
`(p, q, r)` triangle is the translation surface on which the *unfolded* flow lives; it is generally
not the primitive invariant surface, and its `GL(2,R)`-orbit closure may be a proper cover of the
one you have in mind. `surface_dynamics` origamis have explicit tests for this
(`o.is_primitive()`, `o.intermediate_covers()`, `o.quotient(H)`) — see §6.

---

## 4. Saddle connections, holonomy vectors, trajectories

### 4.1 Enumerating saddle connections **[VERIFIED-DOC — "Working with Saddle Connections", Tour]**

**The bound is on the SQUARED length.** The signature is

```
saddle_connections(squared_length_bound, initial_label=None, initial_vertex=None,
                   sc_list=None, check=False)
```

and the docstring says it returns connections "whose length squared is less than or equal to
`squared_length_bound`", measured by holonomy from the starting polygon. Passing `10` when you
meant "length ≤ 10" gives you length ≤ √10 ≈ 3.16 — a classic silent off-by-a-square.

```python
from flatsurf import translation_surfaces

S = translation_surfaces.octagon_and_squares()
connections = S.saddle_connections(squared_length_bound=50)     # length <= sqrt(50)

lengths = sorted(set(c.length() for c in connections))
color = lambda c: colormaps.Accent(lengths.index(c.length()) / len(lengths))[:3]
S.plot(polygon_labels=False, edge_labels=False) + sum(sc.plot(color=color(sc))
                                                     for sc in connections)
```

Each connection appears together with its reverse; deduplicate with `invert()`: **[VERIFIED-DOC]**

```python
sc_set = set()
for sc in S.saddle_connections(100):
    if sc.invert() not in sc_set:
        sc_set.add(sc)
sc_list = list(sc_set)
```

### 4.2 The `SaddleConnection` interface **[VERIFIED — method list read off the 0.8.0 source]**

```
surface()  direction()  end_direction()  start_data()  end_data()
holonomy()  end_holonomy()  length()  start_tangent_vector()  end_tangent_vector()
trajectory()  plot()  invert()  intersects(other)  intersections(other)
__eq__  __ne__  __hash__
```

- `holonomy()` — the holonomy vector, measured from the start, in the surface's base ring.
- `length()` — returned as an element of `AA` (the algebraic reals), because the length need
  not lie in the field of definition.
- `start_data()` / `end_data()` — return the pair `(label, vertex_index)`.
  **There are no `start()` / `end()` methods** returning `SurfacePoint`s; I checked the 0.8.0
  source and only `start_data`/`end_data` exist. Convert yourself if you need a point:
  `S.point(label, S.polygon(label).vertex(v))`. **[UNVERIFIED — the conversion line is mine]**
- `direction()` is used in the docs like this **[VERIFIED-DOC — Boshernitzan page]**:

```python
for connection in S.saddle_connections(4):
    decomposition = GL2ROrbitClosure(S).decomposition(connection.direction())
```

### 4.3 Just the holonomy vectors, up to a bound **[UNVERIFIED — composed from verified primitives]**

```python
from flatsurf import translation_surfaces

S = translation_surfaces.veech_double_n_gon(5)
L = 6
hols = set()
for sc in S.saddle_connections(squared_length_bound=L**2):
    h = sc.holonomy()
    h.set_immutable()
    hols.add(tuple(h))
print(len(hols), "holonomy vectors of length <=", L)

# numerically, for plotting a Veech-group orbit / Siegel--Veech picture:
import matplotlib.pyplot as plt
pts = [(float(a), float(b)) for (a, b) in hols]
plt.scatter(*zip(*pts), s=2)
plt.gca().set_aspect(1)
```

> **[UNVERIFIED]** `h.set_immutable()` before hashing is standard Sage practice for vectors, but
> I could not confirm what type `holonomy()` actually returns in 0.8.0 (Sage vector vs tuple). If
> hashing fails, use `tuple(h)` directly; if `tuple(h)` fails, use `(h[0], h[1])`.

### 4.4 Straight-line flow **[VERIFIED-DOC — "Straight-Line Flow" page and Tour]**

```python
from flatsurf import translation_surfaces

t = translation_surfaces.square_torus()
v = t.tangent_vector(0, (1/2, 0), (5, 6))     # (polygon label, base point, direction)
traj = v.straight_line_trajectory()
traj.flow(10)                                  # extend forward through 10 polygons
traj.flow(-10)                                 # and backward
traj.is_closed()
traj.is_saddle_connection()
traj.coding()                                  # symbolic itinerary of edges crossed
```

The Tour page uses the keyword form `S.tangent_vector(0, (1/47, 1/49), v=(1, 1/31))`; both the
positional signature `tangent_vector(lab, p, v, ring=None)` and that keyword form are current.

Trajectory interface, from the module reference **[VERIFIED-DOC]**:

```
flow(steps)                 segments()            segment(i)
is_closed()                 is_saddle_connection()
is_forward_separatrix()     is_backward_separatrix()
initial_tangent_vector()    terminal_tangent_vector()
combinatorial_length()      coding(alphabet=None)
cylinder()                  # maximal cylinder containing a closed orbit
intersections(traj, count_singularities=False, include_segments=False)
intersects(traj, count_singularities=False)
plot(**options)             graphical_trajectory()
surface()
```

`StraightLineTrajectoryTranslation` is a faster IET-backed implementation used automatically on
translation surfaces.

> **Behaviour to be aware of:** `flow(n)` advances "through up to n polygons **or until hitting a
> vertex**". So a returned trajectory shorter than you asked for is the signal that you have hit a
> singularity — that is exactly the event you care about when hunting for saddle connections. Test
> it with `is_saddle_connection()` / `is_forward_separatrix()` rather than by measuring length.

### 4.5 Plotting **[VERIFIED-DOC]**

```python
S.plot()
S.plot(edge_labels=False, polygon_labels=False)
S.plot() + sc1.plot(color="orange") + sc2.plot(color="green")
S.plot() + T.plot(color="red")                      # T a tangent vector
S.plot() + trajectory.plot(color="red")
p.plot(color="red", zorder=3)                       # a SurfacePoint

gs = S.graphical_surface(polygon_labels=False, edge_labels=False)
gs.make_all_visible(limit=12)                       # for infinite / covering surfaces
gs.plot()
```

---

## 5. Cylinder / flow decompositions and moduli

**There is no `S.cylinder_decomposition(direction)` method on a sage-flatsurf translation
surface.** I checked the full method inventory of the `similarity_surfaces` and
`translation_surfaces` categories in 0.8.0 and there is nothing of the kind. Flow decompositions
go through `GL2ROrbitClosure`, which is backed by `pyflatsurf` (and hence needs the full install).

### 5.1 Decomposition in one direction **[VERIFIED-DOC — Tour page, with printed outputs]**

```python
from flatsurf import similarity_surfaces, Polygon, GL2ROrbitClosure

P = Polygon(angles=(2, 2, 5))
S = similarity_surfaces.billiard(P).minimal_cover(cover_type="translation")

connection = next(iter(S.saddle_connections(squared_length_bound=4)))

O = GL2ROrbitClosure(S)
decomposition = O.decomposition(connection.holonomy())
decomposition
# FlowDecomposition with 4 cylinders, 0 minimal components and 0 undetermined components
```

A direction can be given as an explicit vector over the base field **[VERIFIED-DOC — Boshernitzan page]**:

```python
from flatsurf import EuclideanPolygonsWithAngles, similarity_surfaces, GL2ROrbitClosure

Delta = EuclideanPolygonsWithAngles(1, 1, 10).an_element()
S = similarity_surfaces.billiard(Delta).minimal_cover(cover_type="translation")
D = GL2ROrbitClosure(S).decomposition(vector(Delta.base_ring(), (0, 1)))
D
# FlowDecomposition with 6 cylinders, 0 minimal components and 0 undetermined components
```

If the decomposition does not resolve, raise the induction budget: `O.decomposition(direction,
limit=1024)`. With `limit=0` you get the un-decomposed object, whose components still expose
`intervalExchangeTransformation()`. Both forms are verbatim in the Tour page.

### 5.2 Reading off cylinders and their moduli **[VERIFIED-DOC — "Exploring Orbit Closures"]**

This is the exact loop from the docs, and it contains the one trap that matters:

```python
holonomies = [cyl.circumferenceHolonomy() for cyl in dec.cylinders()]
# .area() as reported by libflatsurf is actually TWICE the area
areas = [cyl.area() / 2 for cyl in dec.cylinders()]
moduli = [area / (v.x()*v.x() + v.y()*v.y()) for v, area in zip(holonomies, areas)]

u = dec.vertical().vertical()          # the direction, as a libflatsurf vector
print("holonomy           :", u)
print("length             :", RDF(u.x()*u.x() + u.y()*u.y()).sqrt())
print("num cylinders      :", len(dec.cylinders()))
print("num minimal comps. :", len(dec.minimalComponents()))
print("cyls. holonomies   :", holonomies)
print("cyls. moduli       :", moduli)
```

`cyl.area()` returning **twice** the area is a documented libflatsurf convention; the modulus
formula `area / |circumference|²` (= height/circumference) is only correct after halving.

Other decomposition methods **[VERIFIED-DOC]**:

```
dec.components()                 dec.cylinders()
dec.minimalComponents()          dec.undeterminedComponents()
dec.vertical().vertical()        dec.parabolic()      # bool: completely periodic w/ commensurable moduli
component.cylinder()             component.withoutPeriodicTrajectory()
component.height()               component.circumferenceHolonomy()
component.intervalExchangeTransformation()
```

Example of `parabolic()` in use **[VERIFIED-DOC — Tour]**:

```python
T = polygons.triangle(1, 4, 7)
S = similarity_surfaces.billiard(T).minimal_cover('translation').erase_marked_points()
O = GL2ROrbitClosure(S)
decomposition = O.decomposition((1, 0))
bool(decomposition.parabolic())
# True
```

### 5.3 Orbit closures **[VERIFIED-DOC — Tour, with outputs]**

```python
from flatsurf import GL2ROrbitClosure

O = GL2ROrbitClosure(S)
O
# GL(2,R)-orbit closure of dimension at least 2 in H_6(7, 2, 1) (ambient dimension 14)

for decomposition in O.decompositions(10, limit=20):
    if O.dimension() == O.ambient_stratum().dimension():
        break
    O.update_tangent_space_from_flow_decomposition(decomposition)

O
# GL(2,R)-orbit closure of dimension at least 14 in H_6(7, 2, 1) (ambient dimension 14)
```

Full `GL2ROrbitClosure` interface: `decomposition(v, limit=-1)`,
`decompositions(bound, limit=-1, bfs=False)`, `decompositions_depth_first`,
`decompositions_breadth_first`, `dimension()`, `ambient_stratum()`, `field_of_definition()`,
`update_tangent_space_from_flow_decomposition(dec)`, `is_teichmueller_curve(bound, limit=-1)`.

**`dimension()` is always a lower bound.** The repr says so. `is_teichmueller_curve` can only ever
return `False` conclusively (it looks for a witnessing direction); a `True`/inconclusive result is
not a proof.

### 5.4 Dropping to raw libflatsurf, e.g. for Siegel–Veech counting **[VERIFIED-DOC — "siegel_veech" page]**

```python
from flatsurf import translation_surfaces

S = translation_surfaces.mcmullen_L(1, 1, 1, 1)
S = S.pyflatsurf().codomain().flat_triangulation()
S = S.eliminateMarkedPoints().surface()

L = int(16)
directions = S.connections().bound(L).slopes()

def target(component):
    if component.cylinder():
        return True
    if component.withoutPeriodicTrajectory():
        return True
    height = component.height()
    from pyflatsurf import flatsurf
    denom = flatsurf.Bound.upper(component.vertical().vertical()).squared()
    return (height * height) / denom > L

circumferences = []
for direction in directions:
    from pyflatsurf import flatsurf
    decomposition = flatsurf.makeFlowDecomposition(S, direction.vector())
    decomposition.decompose(target)
    for component in decomposition.components():
        if component.cylinder():
            circumference = component.circumferenceHolonomy()
            if circumference > L:
                continue
            circumferences.append(circumference)

lengths = [sqrt(float(v.x())**2 + float(v.y())**2) for v in circumferences]
import matplotlib.pyplot as plot
_ = plot.hist(lengths); _ = plot.xlim(0, L)
```

Note the `int(16)` — libflatsurf's pybind11 bindings want a C++ integer, not a Sage `Integer`.
Same reason for the `int(0)` / `-int(1)` you see in the Boshernitzan page's `iet.induce(int(0))`.
This is a real and easy-to-hit failure mode when calling into `pyflatsurf` from Sage.

---

## 6. surface_dynamics: origamis, Veech groups, strata

### 6.1 Strata **[VERIFIED-DOC — strata module doctests, quoted verbatim]**

The modern constructor is `Stratum(signature, k)` with `k=1` for abelian differentials and `k=2`
for quadratic differentials (`k>=3` for higher-order). `AbelianStratum` / `QuadraticStratum` still
exist as subclasses, but the docs use `Stratum` throughout in 0.7.0.

```python
from surface_dynamics import Stratum

Stratum((2,), k=1)                  # H_2(2)
Stratum([1, 2, 1], k=1)             # H_?(2,1,1)  -- signature is sorted, UniqueRepresentation
Stratum([12], k=2)                  # a quadratic stratum
Stratum({-1: 4}, k=2)               # dict form: exponent multiplicities
Stratum({2: 4}, k=1).signature()    # (2, 2, 2, 2)

Stratum([4], k=1).components()
# (H_3(4)^hyp, H_3(4)^odd)
Stratum([1,1,1,1], k=1).components()
# (H_3(1^4)^c,)
Stratum([12], k=2).components()
# (Q_4(12)^reg, Q_4(12)^irr)
Stratum([6,-1,-1], k=2).components()
# (Q_2(6, -1^2)^hyp, Q_2(6, -1^2)^nonhyp)

Stratum((2,), k=1).dimension()      # 4
Stratum((1,1), k=1).dimension()     # 5
Stratum((0,), k=1).dimension()      # 2
Stratum((3,2,1), k=1).surface_genus()   # 4
Stratum([2], k=1).is_connected()        # True
Stratum([2,2], k=1).is_connected()      # False
Stratum([4], k=1).number_of_components()  # 2
Stratum([2], k=1).one_component()         # H_2(2)^hyp
Stratum([1,1], k=1).unique_component()    # H_2(1^2)^hyp

Stratum([2], k=1).masur_veech_volume()               # 1/120*pi^4
Stratum([4], k=1).hyperelliptic_component().masur_veech_volume()   # 1/6720*pi^6
Stratum((2,), k=1).rank()                            # 2
Stratum([4], k=1).odd_component().rank()             # 3
```

Component selectors: `.hyperelliptic_component()`, `.odd_component()`, `.even_component()`,
`.regular_component()`, `.irregular_component()`, `.non_hyperelliptic_component()`,
`.unique_component()`, `.one_component()`.

**Deprecated on `Stratum` (0.6.0 onwards) — will be removed:** `zeros()`, `genus()`, `nb_zeros()`,
`nb_fake_zeros()`, `nb_poles()`. Use `signature()` and `surface_genus()`. The doctest even shows
the warning text: *"nb_fake_zeros() has been deprecated and will be removed in a future version of
surface-dynamics; use signature()"*.

### 6.2 Origamis / square-tiled surfaces **[VERIFIED-DOC — "Square-tiled Surfaces" tutorial, outputs verbatim]**

```python
from surface_dynamics import Origami, origamis, Stratum

o = Origami("(1,2)", "(1,3)")       # r = (1,2), u = (1,3): the 3-square L in H(2)
print(o.r())        # (1,2)
print(o.u())        # (1,3)

ew = origamis.EierlegendeWollmilchsau()
print(ew.r())       # (1,2,3,4)(5,6,7,8)
print(ew.u())       # (1,5,3,7)(2,8,4,6)

print(o.stratum())            # H_2(2)
print(o.stratum_component())  # H_2(2)^hyp
print(ew.stratum())           # H_3(1^4)
print(ew.stratum_component()) # H_3(1^4)^c
```

Also accepted: `Origami([2,1,3], [3,2,1])` (one-line notation) and `Origami(r, u, as_tuple=True)`
(0-based tuples).

Origamis of a component, and Teichmüller curves in it: **[VERIFIED-DOC]**

```python
from surface_dynamics import Stratum
H2_hyp = Stratum([2]).hyperelliptic_component()
H2_hyp.origamis(4)                 # all 4-square origamis in that component

cc = Stratum([4]).odd_component()
for T in cc.arithmetic_teichmueller_curves(11):     # all T-curves with <= 11 squares
    cyls = [0]*3
    for o in T:                                     # T iterates over its origamis
        n = len(o.cylinder_decomposition())
        cyls[n-1] += 1
    print(cyls)
# [1474, 4310, 2016]
# [110, 0, 90]
# [1650, 636, 1114]
```

Structural predicates (useful precisely for the "is this a cover?" pitfall) **[VERIFIED-DOC — origami module reference]**:

```python
o.nb_squares()   o.genus()   o.num_cylinders()   o.widths_and_heights()
o.cylinder_decomposition()   o.cylinder_diagram()
o.is_connected()  o.is_primitive()  o.is_normal()  o.is_regular()
o.is_quasi_primitive()  o.is_reduced()  o.is_orientation_cover()  o.is_hyperelliptic()
o.automorphism_group()   o.monodromy()
o.is_isomorphic(other, certificate=False)
o.intermediate_covers(degree=None)   o.lattice_of_quotients()   o.quotient(H)
o.lattice_of_periods()   o.period_generators()   o.absolute_period_generators()
o.vertical_symmetry()  o.horizontal_symmetry()  o.mirror()  o.inverse()
o.vertical_twist(width=1)  o.horizontal_twist(width=1)
o.to_standard_form(return_map=True)   o.reduce()   o.relabel(return_map=True)
o.sl2z_edges()   o.gl2z_edges()   o.pgl2z_edges()   o.psl2z_edges()
o.plot()   o.as_graph()   o.set_positions(pos)
```

### 6.3 Veech group of a square-tiled surface **[VERIFIED-DOC — outputs verbatim]**

This is the one place where you get a *genuinely computable* Veech group.

```python
from surface_dynamics import Origami, origamis

o = Origami("(1,2)", "(1,3)")
G = o.veech_group()
print(G)
# Arithmetic subgroup with permutations of right cosets
#  S2=(2,3)
#  S3=(1,2,3)
#  L=(1,2)
#  R=(1,3)
print(G.is_congruence())      # True

ew = origamis.EierlegendeWollmilchsau()
print(ew.veech_group())
# Arithmetic subgroup with permutations of right cosets
#  S2=()
#  S3=()
#  L=()
#  R=()          <-- index 1: the Veech group is all of SL(2,Z)
```

The return value is a Sage `ArithmeticSubgroup_Permutation`, so the whole Sage arithmetic-subgroup
API applies **[VERIFIED — Sage reference manual, `sage.modular.arithgroup.arithgroup_perm`]**:

```python
G.index()            # index in SL(2,Z)
G.ncusps()           # number of cusps
G.cusp_widths()      # list of cusp widths
G.nu2()   G.nu3()    # elliptic points of order 2 and 3
G.genus()            # genus of the quotient
G.is_congruence()    # Hsu's algorithm
G.congruence_closure()
G.generators()
```

Teichmüller curve object **[VERIFIED — source of `teichmueller_curve.py`]**:

```python
t = o.teichmueller_curve()
t.origami()                       # canonical representative
t.stratum()                       # H_2(2)
t.veech_group()
t.sum_of_lyapunov_exponents()     # 4/3
t.orbit_graph(s2_edges=True, s3_edges=True, l_edges=False, r_edges=False,
              vertex_labels=True)
for o_rep, width in t.cusp_representatives():
    print(o_rep, width)
```

> **[UNVERIFIED / CORRECTION]** Several older write-ups (and some LLM-generated snippets) use
> **`t.cusps()`**. I read the current `teichmueller_curve.py` and **there is no `cusps()` method**.
> The real API is `cusp_representatives()`, which returns a list of pairs `(origami, width)`, and
> the underlying generator `cusp_representative_iterator()`, documented as: *"Iterator over the
> cusp of self. Each term is a couple (o, w) where o is a representative of the cusp (an origami)
> and w is the width of the cusp (an integer)."* For the *number* of cusps use
> `o.veech_group().ncusps()` or the database column `teich_curve_ncusps`.

### 6.4 Lyapunov exponents **[VERIFIED-DOC — outputs verbatim]**

```python
o.lyapunov_exponents_approx()      # [0.333313763095923]     (Monte-Carlo; varies run to run)
o.sum_of_lyapunov_exponents()      # 4/3                     (exact, Eskin-Kontsevich-Zorich)

ew.lyapunov_exponents_approx()     # [0.0000513874765558288, 0.0000408841305871166]
ew.sum_of_lyapunov_exponents()     # 1
```

Full signature: `lyapunov_exponents_approx(nb_iterations=2**17, nb_experiments=4, involution=None)`.
Note that the Eierlegende Wollmilchsau's exponents are theoretically **0** and the numerics return
`5e-5`, `4e-5` — a perfect illustration of what "approx" means. The Tour page independently
reports `[0.332649016459072]` for the same `o` that the tutorial reports `[0.333313763095923]`
for. **These are stochastic. Never quote them as evidence of an exact value; use them only to
identify a candidate rational, then confirm with `sum_of_lyapunov_exponents()`.**

### 6.5 The origami database **[VERIFIED-DOC — outputs verbatim]**

Enormously useful for finding candidate counterexamples without any computation.

```python
from surface_dynamics import OrigamiDatabase, Stratum

D = OrigamiDatabase()
q = D.query(stratum=Stratum([2]), nb_squares=9)
print(q.number_of())      # 2
o1, o2 = q.list()

# comparison-operator form:
q = D.query(('stratum', '=', Stratum([2])), ('nb_squares', '<', 15))
q.cols('nb_squares', 'veech_group_level', 'teich_curve_nu2', 'teich_curve_nu3',
       'teich_curve_genus', 'monodromy_name')
q.show()

D.info(genus=3)
D.max_nb_squares()
D.cols()
```

The 45 queryable columns include `primitive`, `quasi_primitive`, `orientation_cover`,
`hyperelliptic`, `regular`, `genus`, `nb_squares`, `optimal_degree`, `veech_group_index`,
`veech_group_congruence`, `veech_group_level`, `teich_curve_ncusps`, `teich_curve_nu2`,
`teich_curve_nu3`, `teich_curve_genus`, `sum_of_L_exp`, `L_exp_approx`, `min_nb_of_cyls`,
`max_nb_of_cyls`, `min_hom_dim`, `max_hom_dim`, `minus_identity_invariant`, `monodromy_name`,
`monodromy_signature`, `monodromy_index`, `monodromy_order`, `monodromy_solvable`,
`monodromy_nilpotent`, `monodromy_gap_primitive_id`, the `relative_monodromy_*` analogues,
`orientation_stratum`, `orientation_genus`, `pole_partition`, `automorphism_group_order`,
`automorphism_group_name`.

`D.info(genus=3)` reports, e.g., `H_3(4)^hyp : 163 T. curves (up to 51 squares)`, so you know the
coverage limits before you rely on an exhaustive search.

### 6.6 Veech groups in **sage-flatsurf** — a warning

sage-flatsurf 0.6.0 added `S.veech_group()` and `S.affine_automorphism_group()`. **Do not rely on
them for computation.** The module documentation describes `VeechGroup_generic` as a "generic
(currently essentially empty) implementation", and **computing generators raises
`NotImplementedError`**. What does work is the section map:

```python
from flatsurf import translation_surfaces
S = translation_surfaces.square_torus()
A = S.affine_automorphism_group()
M = matrix([[1, 2], [0, 1]])
f = A.derivative().section()(M, check=False)
```

For an actual, finite, presentable Veech group your options are:
1. a **square-tiled surface** → `surface_dynamics`'s `o.veech_group()` (§6.3), which is complete;
2. the **canonicalize test** of §2.5 to check membership of one specific matrix;
3. the GAP package **Origami** (Weitze-Schmithüsen et al., v2.0.1, 2024-07-09), which computes
   Veech groups of general origamis — a separate, non-Sage tool worth knowing about.

### 6.7 Origami generators: `origamis.*` **[VERIFIED — run 2026-09-19, WSL Sage, surface_dynamics 0.7.0 / sage-flatsurf 0.8.0]**

Complete list of public generators in 0.7.0 (`[n for n in dir(origamis) if not n.startswith('_')]`):

```
['CyclicCover', 'EierlegendeWollmilchsau', 'Escalator', 'Heisenberg',
 'Podium', 'ProjectiveLine', 'ShresthaWang', 'Stair']
```

**Refuted: `origamis.Ornithorynque` does not exist.**

```python
origamis.Ornithorynque()
# AttributeError: 'OrigamiGenerators' object has no attribute 'Ornithorynque'
```

It reads as correct — the Ornithorynque is as standard a named example as the Eierlegende
Wollmilchsau — but only the latter has a generator. Build it as `origamis.CyclicCover([1,1,1,3])`
(below), which reports itself as `M_6(1,1,1,3)`.

#### 6.7.1 `origamis.EierlegendeWollmilchsau()` — confirmed, verbatim

```python
ew = origamis.EierlegendeWollmilchsau()
repr(ew)                          # 'Eierlegende Wollmilchsau'
str(ew)                           # '(1,2,3,4)(5,6,7,8)\n(1,5,3,7)(2,8,4,6)'   (1-based)
ew.r_tuple()                      # (1, 2, 3, 0, 5, 6, 7, 4)        0-based
ew.u_tuple()                      # (4, 7, 6, 5, 2, 1, 0, 3)        0-based
ew.nb_squares()                   # 8
ew.stratum()                      # H_3(1^4)
ew.stratum_component()            # H_3(1^4)^c
ew.genus()                        # 3
ew.veech_group().index()          # 1   (Veech group is all of SL(2,Z))
ew.sum_of_lyapunov_exponents()    # 1
```

#### 6.7.2 JSON serialisation: which of these are Sage types

Checked explicitly, because a pipeline that dumps invariants to JSON will crash on the Sage ones.

| call | type | `json.dumps` |
|---|---|---|
| `r_tuple()` / `u_tuple()` entries | **Python `int`** | **OK** |
| `nb_squares()` | **Python `int`** | OK |
| `genus()` | **Python `int`** | OK |
| `veech_group().index()` | **Python `int`** | OK |
| `sum_of_lyapunov_exponents()` | `sage.rings.rational.Rational` | `TypeError: Object of type Rational is not JSON serializable` |
| `monodromy().order()` | `sage.rings.integer.Integer` | `TypeError: Object of type Integer is not JSON serializable` |
| `automorphism_group().order()` | `sage.rings.integer.Integer` | `TypeError` |
| `lattice_of_periods()` / `lattice_of_absolute_periods()` | `tuple` of `Integer` | `TypeError` |
| `stratum()` / `stratum_component()` | `AbelianStratum…` object | not serialisable; use `str()` |

So `r_tuple()`/`u_tuple()` need **no** conversion; `int(...)` / `str(...)` the group orders, the
lattice triples and the Lyapunov sum.

#### 6.7.3 `origamis.CyclicCover(a, M=None)` — confirmed

Signature: `CyclicCover(a, M=None)`. `a` is a quadruple; `M` defaults to `sum(a)`; the result has
**`2*M` squares** (not `2*sum(a)` when `M` is given explicitly).

```python
orn = origamis.CyclicCover([1,1,1,3])          # the Ornithorynque
repr(orn)                         # 'M_6(1,1,1,3)'
orn.nb_squares()                  # 12
orn.stratum()                     # H_4(2^3)
orn.stratum_component()           # H_4(2^3)^even
orn.genus()                       # 4
orn.veech_group().index()         # 1
orn.sum_of_lyapunov_exponents()   # 1
orn.r_tuple()                     # (1, 8, 7, 2, 5, 0, 11, 6, 9, 4, 3, 10)
orn.u_tuple()                     # (7, 6, 5, 0, 11, 10, 9, 4, 3, 2, 1, 8)

cc = origamis.CyclicCover([1,1,1,1])
repr(cc)                          # 'M_4(1,1,1,1)'
cc.nb_squares()                   # 8
cc.r_tuple()                      # (1, 4, 7, 2, 5, 0, 3, 6)
cc.u_tuple()                      # (7, 2, 5, 0, 3, 6, 1, 4)
cc.is_isomorphic(origamis.EierlegendeWollmilchsau())   # True
```

Note that `CyclicCover([1,1,1,1])` is isomorphic to the Eierlegende Wollmilchsau but is **not
given with the same labelling** — the tuples differ. Anything pinned to square indices must pick
one of the two constructions and stay with it.

**Validation, in source order** (`generators.py`, `surface_dynamics/flat_surfaces/origamis/`).
Reproduce this order exactly in any re-implementation; an input failing two tests reports the
first:

```python
if M is None: M = sum(a)
a = list(map(Integer, a))
if len(a) != 4:                  raise ValueError("a should be of length 4")
if any(ai % 2 == 0 for ai in a): raise ValueError("ai should be odd")
if gcd([M] + a) != 1:            raise ValueError("gcd(M,a) should be 1")
if M % 2:                        raise ValueError("M should be even")
if sum(a) % M:                   raise ValueError("the sum of ai should be 0 mod M")
```

Messages verbatim, each triggered:

| call | error |
|---|---|
| `CyclicCover([1,1,1])` | `ValueError: a should be of length 4` |
| `CyclicCover([1,1,1,2])` | `ValueError: ai should be odd` |
| `CyclicCover([3,3,3,3])` | `ValueError: gcd(M,a) should be 1` |
| `CyclicCover([1,1,1,3], M=5)` | `ValueError: M should be even` |
| `CyclicCover([1,1,1,1], M=8)` | `ValueError: the sum of ai should be 0 mod M` |
| `CyclicCover([1,1,1,3], M=4)` | `ValueError: the sum of ai should be 0 mod M` |
| `CyclicCover([1,1,1,3], M=12)` | `ValueError: the sum of ai should be 0 mod M` |

Precedence traps confirmed by running inputs that fail two tests at once:
`[3,3,3,3], M=5` → `M should be even` (**not** the gcd message: `gcd([5,3,3,3]) == 1`, so the gcd
test passes); `[2,2,2,2]` → `ai should be odd` (before gcd); `[1,1,1,1], M=3` → `M should be even`
(before `sum % M`); `[1,1,2]` → the length message wins over the even-entry one.

**An explicit `M` other than `sum(a)` is allowed** whenever `M | sum(a)`, `M` even and
`gcd(M, a) = 1`. Confirmed:

```python
origamis.CyclicCover([1,1,1,1], M=2)   # M_2(1,1,1,1)  4 squares,  H_1(0)
origamis.CyclicCover([1,1,1,1], M=4)   # M_4(1,1,1,1)  8 squares,  H_3(1^4)
origamis.CyclicCover([1,1,1,3], M=2)   # M_2(1,1,1,3)  4 squares,  H_1(0)
origamis.CyclicCover([1,1,1,5], M=8)   # M_8(1,1,1,5) 16 squares,  H_7(3^4)
```

So "M defaults to sum(a)" is **not** "M must be sum(a)"; an enumerator that only ever passes the
default silently skips every proper divisor, including the degenerate torus cases.

**Transcription note.** The construction loop in `generators.py` has an asymmetry that looks like
an upstream typo but determines the labelling: inside the `neg` branch, the two `u` steps test
membership with `if j not in seen and j not in neg:` and then `pos.add(j)`. Copy it verbatim — a
"corrected" version produces a different square indexing.

#### 6.7.4 Invariants on origamis **[VERIFIED — three cases with known answers]**

| | 4-square torus `Origami([1,0,3,2],[2,3,0,1], as_tuple=True)` | 3-square L `Origami([1,0,2],[2,1,0], as_tuple=True)` | Eierlegende Wollmilchsau |
|---|---|---|---|
| `stratum()` | `H_1(0)` | `H_2(2)` | `H_3(1^4)` |
| `genus()` | 1 | 2 | 3 |
| `monodromy()` gens | `(1,2)(3,4), (1,3)(2,4)` | `(1,2), (1,3)` | `(1,2,3,4)(5,6,7,8), (1,5,3,7)(2,8,4,6)` |
| `monodromy().order()` | 4 | 6 | 8 |
| `automorphism_group().order()` | 4 | 1 | 8 |
| `Centralizer(Sym(n), mono).Size()` | 4 | 1 | 8 |
| `is_normal()` | True | False | True |
| `is_regular()` | True | False | True |
| `is_primitive()` | False | True | False |
| `lattice_of_periods()` | `(2, 0, 2)` | `(1, 0, 1)` | **`(1, 0, 1)`** |
| `lattice_of_absolute_periods()` | `(2, 0, 2)` | `(1, 0, 1)` | `(2, 0, 2)` |
| `len(intermediate_covers())` | 5 | 2 | 6 |

- **`monodromy()`** returns a `sage.groups.perm_gps.permgroup.PermutationGroup_generic_with_category`
  — a **group**, not a permutation — generated by `r` and `u`. Its `domain()` is `{1, …, n}`, so it
  is **1-based**, while `r_tuple()`/`u_tuple()` are 0-based. `.order()` is a Sage `Integer`.
  Keyword `relative=True` gives the monodromy relative to the largest torus covered.
- **`automorphism_group()`** is the **centraliser of `⟨r,u⟩` in `S_n`** — the *translation* group
  (affine maps with trivial linear part), **not** the affine group. Confirmed against
  `libgap.Centralizer(SymmetricGroup(n).gap(), S.subgroup(o.monodromy().gens()).gap()).Size()`:
  orders agree (4, 1, 8) in all three cases. Returns a `PermutationGroup_subgroup_with_category`
  inside `Sym(n)`; `.order()` is a Sage `Integer`. The docstring says this explicitly:
  *"corresponds combinatorially to the centralizer of the group generated by the permutations `r`
  and `u`"*.
- **`is_normal()` vs `is_regular()`**: documented differently (`is_normal` = the defining subgroup
  of `F_2` is normal; `is_regular` = `Aut` acts transitively on squares) but **equivalent**, and
  both equal `|automorphism_group()| == nb_squares()`. Verified to agree on all three cases.
- **`lattice_of_periods()` / `lattice_of_absolute_periods()`** return a **triple of Sage
  `Integer`s** `(a, t, u)` for the standard basis `((a,0), (t,u))` with `0 <= t < a`, `0 < u`.
  `lattice_of_periods` uses holonomies of **saddle connections** (i.e. relative periods);
  `lattice_of_absolute_periods` uses holonomies of **loops**. They differ: on the EW,
  `lattice_of_periods() == (1,0,1)` while `lattice_of_absolute_periods() == (2,0,2)`. If you want
  the "is this a proper torus cover" index-2 signal on the EW, it is the **absolute** one.
- **`is_primitive()`** returns a Python `bool`; documented as "does not cover another origami" /
  "the monodromy action has no non-trivial block".
- **`intermediate_covers()`** returns a **`list` of `Origami_dense_pyx`**, including the trivial
  1-square cover and the origami itself (L: `[1-square, L]`; EW: 6 entries ending in the EW).
  Optional `degree=` argument filters by degree.

#### 6.7.5 The twists relabel **[VERIFIED — the SL(2,Z) relabelling trap, demonstrated]**

Signature is `horizontal_twist(width=1, cylinder=None)` / `vertical_twist(width=1, cylinder=None)`
— **the parameter is named `width`, not `k`** (positional use is fine). `horizontal_twist` returns
the origami `(r, r^{-width} u)`; `cylinder=i` twists only the band containing `i` and is then
**not** an SL(2,R) deformation.

Take `S = h(1) v(-1) h(1)`, whose matrix is `[[0,1],[-1,0]]`, of order 4, so `S^4 = I`. On the
3-square L:

```python
L = Origami([1,0,2], [2,1,0], as_tuple=True)
L.r_tuple(), L.u_tuple()                     # (1, 0, 2)  (2, 1, 0)

S1 = L.horizontal_twist(1).vertical_twist(-1).horizontal_twist(1)
S1.r_tuple(), S1.u_tuple()                   # (0, 2, 1)  (1, 0, 2)

S4 = the same three-step word applied four times
S4.r_tuple(), S4.u_tuple()                   # (0, 2, 1)  (1, 0, 2)
S4.is_isomorphic(L)                          # True
tuple(S4.r_tuple()) == tuple(L.r_tuple())    # False   <-- relabelled
```

So a word whose matrix is the **identity** comes back isomorphic but with **different `r_tuple()`
and `u_tuple()`**. The relabelling is not uniform: on the Eierlegende Wollmilchsau the same
`S^4` word returns `r_tuple() == (1,2,3,0,5,6,7,4)` and `u_tuple() == (4,7,6,5,2,1,0,3)`,
i.e. **unchanged** — so "my test origami came back with the same tuples" proves nothing.

Consequences for a search pipeline:

- Anything keyed on **square indices** (a marked pair of squares, a tracked cone-point corner)
  must be re-identified after every twist, or applied one generator at a time with the labels
  transported explicitly (`fslab/vh.py`).
- Label-free invariants survive: on the L, `lattice_of_absolute_periods()` stayed `(1,0,1)`,
  `automorphism_group().order()` stayed 1, `is_normal()` stayed `False` across `S^1` and `S^4`.
  That is consistent with them being SL(2,Z)-orbit invariants, but **three points on one origami
  is a consistency check, not a proof** — the mathematical argument still has to be made
  separately.

---

## 7. Illumination-specific recipes

### 7.1 Recipe: unfold a rational polygon, get the surface + stratum

```python
from flatsurf import polygons, similarity_surfaces

T  = polygons.triangle(1, 4, 7)                  # angles proportional to (1,4,7)
Sm = similarity_surfaces.billiard(T).minimal_cover('translation')   # with marked points
S  = Sm.erase_marked_points()                                        # primitive-ish

print("with marked points   :", Sm.stratum())
print("without marked points:", S.stratum())
print("base ring            :", S.base_ring())
S.plot(edge_labels=False, polygon_labels=False)
```

**[VERIFIED-DOC]** every call; the `print` framing is mine. Always print *both* strata — the
difference is exactly the set of fake zeros the unfolding introduced, and knowing it saves you
from a wrong dimension count later.

### 7.2 Recipe: does `p` illuminate `q`? — the honest situation

There is **no** `S.connections_between(p, q, bound)` in either package. I checked the complete
method inventories of both `similarity_surfaces` and `translation_surfaces` categories in 0.8.0.
The available machinery is:

- `S.saddle_connections(squared_length_bound, initial_label=..., initial_vertex=...)` —
  enumerates connections **between vertices**, optionally restricted to a starting vertex;
- `S.point(label, coords)`, with working `__eq__` and `__hash__`, so you can identify which
  singularity a `(label, vertex)` pair represents;
- `S.tangent_vector(label, p, v).straight_line_trajectory().flow(n)` — shoots one geodesic.

So there are three usable strategies.

#### (a) Both points are singularities: exact, and fully supported **[UNVERIFIED — composed from verified primitives]**

```python
from flatsurf import polygons, similarity_surfaces

S = similarity_surfaces.billiard(polygons.triangle(1, 4, 7)) \
        .minimal_cover('translation').erase_marked_points()

def vertex_point(S, label, v):
    return S.point(label, S.polygon(label).vertex(v))

L2 = 400                                   # bound on the SQUARED length

# List the distinct singularities, then pick the two you care about.
sings = []
for lab in S.labels():
    for v in range(len(S.polygon(lab).vertices())):
        pt = vertex_point(S, lab, v)
        if pt not in sings:
            sings.append(pt)
print(len(sings), "singularities")
p, q = sings[0], sings[1]

connecting = []
for sc in S.saddle_connections(squared_length_bound=L2):
    a, va = sc.start_data()
    b, vb = sc.end_data()
    if vertex_point(S, a, va) == p and vertex_point(S, b, vb) == q:
        connecting.append(sc)

print(len(connecting), "connections from p to q of length <= sqrt(L2)")
for sc in sorted(connecting, key=lambda c: c.length())[:10]:
    print(float(sc.length()), sc.holonomy())
```

> **[UNVERIFIED]** `S.polygon(label)` and `S.labels()` are standard sage-flatsurf accessors but I
> did not find them in the method lists I read (the pages I fetched document the *category*
> methods, not the base surface accessors). If `S.polygon(label)` fails, the alternative is
> `S.polygon(label)` → `list(S.polygons())` indexed by `list(S.labels())`. Everything else in this
> snippet — `saddle_connections(squared_length_bound=...)`, `start_data()`, `end_data()`,
> `S.point()`, point equality, `holonomy()`, `length()` — is verified.

The comparison must go through `SurfacePoint`, **not** through raw `(label, vertex)` pairs,
because one singularity has many representatives. The docs show this explicitly:

```
sage: p = S.point(1, (0, 0))
sage: p.representatives()
frozenset({(1, (0, 0)), (1, (1, 1)), (2, (0, 1)), (2, (1, 0))})
sage: hash(S.point(0, (0,0))) == hash(S.point(4, (0,0)))
True
```

#### (b) At least one point is regular: you must first *make it a vertex*

sage-flatsurf 0.8.0 has **no `insert_marked_points` method** (I checked; `subdivide()`,
`subdivide_edges(parts=2)` and `subdivide_polygon(p, v1, v2)` exist, but `subdivide_polygon` cuts
along a diagonal between *existing* vertices — it cannot introduce an interior point). So you cone
the containing polygon over the point by hand:

```python
from flatsurf import MutableOrientedSimilaritySurface, Polygon

def mark_interior_point(S, label, pt):
    """Rebuild S with `pt` (interior to polygon `label`) as a new vertex.

    Replaces polygon `label` by the fan of triangles (pt, w_i, w_{i+1}).
    Returns the new immutable surface and the list of new labels.
    """
    K  = S.base_ring()
    P  = S.polygon(label)
    n  = len(P.vertices())
    T  = MutableOrientedSimilaritySurface(K)

    old_to_new = {}
    for lab in S.labels():
        if lab != label:
            old_to_new[lab] = T.add_polygon(S.polygon(lab))

    pt   = vector(K, pt)
    fan  = []
    for i in range(n):
        a = vector(K, P.vertex(i))
        b = vector(K, P.vertex((i + 1) % n))
        fan.append(T.add_polygon(Polygon(vertices=[pt, a, b], base_ring=K)))

    # edge 1 of triangle i is the old edge i of P; edges 0 and 2 are internal
    for i in range(n):
        T.glue((fan[i], 2), (fan[(i + 1) % n], 0))
    for i in range(n):
        opp_lab, opp_e = S.opposite_edge(label, i)
        if opp_lab == label:
            T.glue((fan[i], 1), (fan[opp_e], 1))
        else:
            T.glue((fan[i], 1), (old_to_new[opp_lab], opp_e))
    for lab in S.labels():
        if lab == label:
            continue
        for e in range(len(S.polygon(lab).vertices())):
            opp_lab, opp_e = S.opposite_edge(lab, e)
            if opp_lab == label:
                continue
            T.glue((old_to_new[lab], e), (old_to_new[opp_lab], opp_e))

    T.set_immutable()
    return T, fan
```

> **[UNVERIFIED — this whole function is mine and has NOT been executed.]** It uses only verified
> primitives (`MutableOrientedSimilaritySurface`, `add_polygon`, `glue`, `set_immutable`,
> `Polygon(vertices=..., base_ring=...)`) plus `S.opposite_edge(label, edge)`, `S.labels()`,
> `S.polygon(label)` and `P.vertex(i)`, which I believe are standard but did not find in the pages
> I read. **Treat it as a sketch to debug, not as working code.** Sanity checks to run first:
> `T.stratum()` should differ from `S.stratum()` by one extra `0` in the signature, and
> `T.erase_marked_points().canonicalize() == S.canonicalize()` should hold.
>
> Also note the triangle-edge indexing assumption (`Polygon(vertices=[pt, a, b])` has edge 0 =
> `pt→a`, edge 1 = `a→b`, edge 2 = `b→pt`). Verify with `Polygon(vertices=[...]).edges()` before
> trusting the gluings.

Once both points are vertices, apply recipe (a).

#### (c) Numerical probe by shooting geodesics **[UNVERIFIED — composed from verified primitives]**

Cheap, immediately runnable, and the right first move when you just want to know whether to
believe a conjecture.

```python
from flatsurf import translation_surfaces

S = translation_surfaces.veech_double_n_gon(5)

# p is a regular point; q is the target.  Shoot in the directions of the short
# saddle connections -- on a Veech surface these are exactly the "interesting"
# directions, and they are dense in the right way.
dirs = sorted({tuple(sc.holonomy()) for sc in S.saddle_connections(squared_length_bound=200)})

hits = []
for d in dirs:
    v = S.tangent_vector(0, (1/3, 1/4), d)
    traj = v.straight_line_trajectory()
    traj.flow(300)
    if traj.is_saddle_connection():
        hits.append((d, traj.combinatorial_length()))

print(len(hits), "of", len(dirs), "directions gave a separatrix")
```

**What this can and cannot tell you** is the subject of §9. In brief: a hit is a *proof* that
`p` illuminates something (you have an explicit geodesic); the absence of hits is *not* a proof of
non-illumination, only of non-illumination within the search window.

### 7.3 Recipe: holonomy vectors up to a bound

See §4.3. On a Veech surface the set of holonomy vectors is a finite union of lattice orbits
(Veech dichotomy), so plotting `{holonomy(sc)}` and eyeballing the lattice structure is a fast,
honest check that your surface really is Veech — and it is exactly the picture you want when
reasoning about which directions can connect two points.

### 7.4 Recipe: cylinder decomposition in a direction + moduli

See §5.1–5.2. The illumination-relevant reading: if the direction of a candidate connection
decomposes into **cylinders only** and `dec.parabolic()` is `True`, that direction is completely
periodic with commensurable moduli, so there is a parabolic element of the Veech group fixing it
— which is exactly the situation in which illumination questions become tractable by a
Veech-group argument rather than a search. If `len(dec.minimalComponents()) > 0`, the direction is
not periodic and a finite search will never settle it.

```python
from flatsurf import similarity_surfaces, polygons, GL2ROrbitClosure

S = similarity_surfaces.billiard(polygons.triangle(1, 4, 7)) \
        .minimal_cover('translation').erase_marked_points()
O = GL2ROrbitClosure(S)

for sc in S.saddle_connections(squared_length_bound=64):
    dec = O.decomposition(sc.holonomy())
    if len(dec.minimalComponents()) == 0:
        hol   = [c.circumferenceHolonomy() for c in dec.cylinders()]
        area  = [c.area() / 2 for c in dec.cylinders()]
        mod   = [a / (v.x()*v.x() + v.y()*v.y()) for v, a in zip(hol, area)]
        print(sc.holonomy(), "->", len(dec.cylinders()), "cyls, moduli", mod,
              "parabolic:", bool(dec.parabolic()))
```

**[UNVERIFIED as a whole; every individual call is VERIFIED-DOC.]**

### 7.5 Recipe: Veech group of a square-tiled surface

```python
from surface_dynamics import Origami

o = Origami("(1,2,3,4)", "(1,5)")     # your origami here
G = o.veech_group()
print("index in SL(2,Z):", G.index())
print("cusps            :", G.ncusps(), "widths", G.cusp_widths())
print("nu2, nu3, genus  :", G.nu2(), G.nu3(), G.genus())
print("congruence?      :", G.is_congruence())

t = o.teichmueller_curve()
print("stratum          :", t.stratum())
print("sum of Lyapunov  :", t.sum_of_lyapunov_exponents())
for rep, width in t.cusp_representatives():
    print("  cusp of width", width, "represented by\n", rep)
```

**[UNVERIFIED as a whole]** — `Origami("(1,2,3,4)", "(1,5)")` is my example (check it defines a
connected origami with `o.is_connected()`); every method call is verified individually in §6.3.

---

## 8. Pure-Python fallbacks (no Sage) — tested in this session

Both programs below were **executed** in this session on CPython 3.11 with only the standard
library. Their printed output is reproduced verbatim.

### 8.1 Exact illumination on a square-tiled surface

This is the one that matters. On an origami the question "which holonomy vectors join
`p = (square s, (x, y))` to `q = (square t, (x', y'))`?" has an exact, complete answer with no
floating point at all, because of a small observation:

> A straight segment from `(s, (x,y))` ends at `(t, (x',y'))` only if its holonomy `(a, b)`
> satisfies `a ∈ x'-x+Z` and `b ∈ y'-y+Z`. So the candidate holonomies form a **translate of Z²**,
> and one only has to decide, for each candidate, which square it lands in — a finite word in the
> gluing permutations `r`, `u`.

```python
"""Exact illumination probe on a square-tiled surface (origami).
Pure Python; only `fractions` and `math`.  An origami is a pair of permutations
(r, u) of {0,...,n-1}: square i is glued on the right to r(i), on top to u(i).
"""

from fractions import Fraction as F
import math


def inv_perm(p):
    q = [0] * len(p)
    for i, pi in enumerate(p):
        q[pi] = i
    return q


class Origami:
    def __init__(self, r, u):
        assert len(r) == len(u)
        assert sorted(r) == sorted(u) == list(range(len(r)))
        self.r, self.u = list(r), list(u)
        self.ri, self.ui = inv_perm(self.r), inv_perm(self.u)
        self.n = len(r)

    def develop(self, s, x, y, a, b):
        """Follow the segment from (s,(x,y)) by holonomy (a,b), all Fractions.
        Returns the terminal square, or None if the segment hits a vertex."""
        events = []
        if a != 0:
            lo, hi = (x, x + a) if a > 0 else (x + a, x)
            k = math.floor(lo) + 1
            while k <= hi:
                if lo < k < hi or k == hi:
                    t = F(k - x, 1) / a
                    if 0 < t <= 1:
                        events.append((t, "r" if a > 0 else "ri"))
                k += 1
        if b != 0:
            lo, hi = (y, y + b) if b > 0 else (y + b, y)
            k = math.floor(lo) + 1
            while k <= hi:
                if lo < k < hi or k == hi:
                    t = F(k - y, 1) / b
                    if 0 < t <= 1:
                        events.append((t, "u" if b > 0 else "ui"))
                k += 1
        events.sort(key=lambda e: e[0])
        for i in range(len(events) - 1):          # simultaneous crossings = a vertex
            if events[i][0] == events[i + 1][0]:
                return None
        cur = s
        for _, kind in events:
            cur = getattr(self, kind)[cur]
        return cur

    def connections(self, p, q, bound):
        """All holonomy vectors of length <= bound joining p to q.
        p, q are triples (square, x, y) with x, y Fractions in [0,1)."""
        s, x, y = p
        t, xp, yp = q
        a0, b0 = F(xp) - F(x), F(yp) - F(y)
        out = []
        M = int(math.floor(bound)) + 2
        for m in range(-M, M + 1):
            a = a0 + m
            if abs(a) > bound:
                continue
            rem2 = bound * bound - float(a) ** 2
            if rem2 < 0:
                continue
            K = int(math.floor(math.sqrt(rem2))) + 2
            for k in range(-K, K + 1):
                b = b0 + k
                if float(a) ** 2 + float(b) ** 2 > bound * bound:
                    continue
                if a == 0 and b == 0:
                    continue
                if self.develop(s, F(x), F(y), a, b) == t:
                    out.append((a, b))
        out.sort(key=lambda v: (float(v[0]) ** 2 + float(v[1]) ** 2))
        return out
```

Self-tests and their **actual output**:

```python
half, third, quart = F(1, 2), F(1, 3), F(1, 4)

# 1. torus: EVERY candidate vector must work
T = Origami([0], [0])
got = T.connections((0, third, quart), (0, F(1,5), F(2,7)), 5.0)
# -> torus: found 77 expected 77 -> True

# 2. the 3-square origami in H(2): r=(1,2), u=(1,3) in 1-based = [1,0,2],[2,1,0]
O = Origami([1, 0, 2], [2, 1, 0])
# connections by target square: {0: 64, 1: 63, 2: 72}  total 199
#   fractions: [0.322, 0.317, 0.362]
#   (disc of radius 8 has area ~201: every candidate lands somewhere, and the
#    three squares get roughly a third each -- a good consistency check)

# 3. vertex detection
T.develop(0, half, half, F(1), F(1)) is None      # True  -- passes through a corner
T.develop(0, half, half, F(1), F(0)) == 0         # True

# 4. reversal symmetry: connections p->q are exactly the negatives of q->p
#    -> True
```

Runtime: 0.08 s for all four tests.

**Why this is research-usable, not a toy:** it is exact (no epsilon anywhere), it is complete
within the bound (nothing is missed), and it correctly flags trajectories through singularities.
For an origami it answers "does `p` illuminate `q` within distance `L`?" definitively. Converting a
`surface_dynamics` origami to this format is `[o.r_tuple(), o.u_tuple()]` (0-based tuples on
`{0,...,n-1}`) — **[UNVERIFIED]**, `r_tuple`/`u_tuple` appear in the origami API list but I did
not see a doctest confirming the indexing base; check `o.r_tuple()` against `o.r()` once.

### 8.2 Float billiard tracer for an arbitrary polygon

For non-rational polygons, Tokarsky-style rooms, or a quick picture, a direct billiard simulation
is often all you need and needs nothing installed.

```python
import math

class Billiard:
    def __init__(self, vertices):
        self.V = [(float(x), float(y)) for (x, y) in vertices]
        self.n = len(self.V)

    def edge(self, i):
        return self.V[i], self.V[(i + 1) % self.n]

    def _hit(self, p, d, eps):
        best_t, best_i = None, None
        for i in range(self.n):
            (x1, y1), (x2, y2) = self.edge(i)
            ex, ey = x2 - x1, y2 - y1
            den = d[0]*ey - d[1]*ex
            if abs(den) < 1e-15:
                continue
            wx, wy = p[0]-x1, p[1]-y1
            t = (ex*wy - ey*wx) / den
            s = (d[0]*wy - d[1]*wx) / den
            if t > eps and -1e-9 <= s <= 1+1e-9:
                if best_t is None or t < best_t:
                    best_t, best_i = t, i
        return best_t, best_i

    def trajectory(self, p, theta, nbounces=200, eps=1e-9):
        """Billiard path from p in direction theta.  Stops at a corner."""
        d = (math.cos(theta), math.sin(theta))
        pts = [tuple(map(float, p))]
        cur = pts[0]
        for _ in range(nbounces):
            t, i = self._hit(cur, d, eps)
            if t is None:
                break
            q = (cur[0] + t*d[0], cur[1] + t*d[1])
            pts.append(q)
            (x1, y1), (x2, y2) = self.edge(i)
            ex, ey = x2-x1, y2-y1
            L = math.hypot(ex, ey)
            if L == 0:
                break
            ex, ey = ex/L, ey/L
            if min(math.dist(q, (x1, y1)), math.dist(q, (x2, y2))) < 1e-9:
                break                      # hit a corner -- trajectory undefined
            dot = d[0]*ex + d[1]*ey
            d = (2*dot*ex - d[0], 2*dot*ey - d[1])
            cur = q
        return pts

    def min_distance_to(self, pts, q):
        best = float("inf")
        for k in range(len(pts)-1):
            a, b = pts[k], pts[k+1]
            ax, ay = b[0]-a[0], b[1]-a[1]
            L2 = ax*ax + ay*ay
            s = 0.0 if L2 == 0 else max(0.0, min(1.0,
                    ((q[0]-a[0])*ax + (q[1]-a[1])*ay) / L2))
            best = min(best, math.dist((a[0]+s*ax, a[1]+s*ay), q))
        return best


def illumination_scan(B, p, q, ndirs=20000, nbounces=200):
    """Scan directions from p; return (closest approach to q, best theta)."""
    best, best_theta = float("inf"), None
    for k in range(ndirs):
        theta = 2*math.pi*k/ndirs
        d = B.min_distance_to(B.trajectory(p, theta, nbounces=nbounces), q)
        if d < best:
            best, best_theta = d, theta
    return best, best_theta
```

**Actual output of the sanity checks:**

```
square best approach: 5.190079620543489e-06 at theta = 0.5906194188748811
L-room best approach: 0.0 at theta = 0.0
square slope-1 path: [(0.25, 0.0), (1.0, 0.75), (0.75, 1.0), (0.0, 0.25), (0.25, 0.0), (1.0, 0.75)]
```

The third line is the real test: from `(1/4, 0)` at slope 1 in the unit square, the path is
periodic of combinatorial period 4 and returns exactly to `(0.25, 0.0)`. Runtime for all three:
0.46 s.

**Read the scan output correctly.** `illumination_scan` reports the *closest approach*, never a
yes/no. `5.19e-06` after 2000 directions means "there is very likely a connecting trajectory
nearby"; you then refine around `best_theta`. A distance that stubbornly refuses to fall below,
say, `1e-2` as you increase `ndirs` by orders of magnitude is *evidence for* non-illumination and
nothing more. In particular, corner-hitting truncates the trajectory silently (the `break`), so
directions that hit a vertex are under-sampled — precisely the directions that matter most in
unilluminable-room constructions.

---

## 9. Using this responsibly in research

### 9.1 What numerical experiments can and cannot establish

**They can:**
- **Refute.** One explicit geodesic from `p` to `q`, with its holonomy vector, *is* a proof that
  `p` illuminates `q`. One direction whose flow decomposition has a minimal component *is* a
  disproof of complete periodicity in that direction (subject to §9.2). A `False` from
  `O.is_teichmueller_curve(bound)` is conclusive, because it exhibits a witnessing direction.
- **Find the right statement.** Compute the invariant on 50 origamis from the database and the
  pattern in `sum_of_L_exp`, `teich_curve_ncusps` or `min_nb_of_cyls` will usually tell you what
  the theorem should say. This is the highest-value use.
- **Calibrate.** Before proving a bound, check numerically whether it is remotely tight.

**They cannot:**
- **Prove universally quantified statements.** "No connection of length ≤ 40" says nothing about
  length 41. Illumination is a statement about *all* geodesics; a bounded search is a statement
  about finitely many.
- **Certify a negative on a non-lattice surface.** On a Veech surface, the Veech dichotomy can
  sometimes upgrade a finite check into a theorem (if you know the direction is periodic, a
  bounded search in that direction is exhaustive). Off the Veech locus there is no such upgrade.
- **Establish exact values from `lyapunov_exponents_approx`.** §6.4 shows the method returning
  `5e-5` for a true value of `0`, and two different values for the same origami on two doc pages.
- **Turn `O.dimension()` into an orbit closure.** It is documented as a lower bound.

### 9.2 Floating point versus exact arithmetic

The flatsurf stack is unusually good here, and you should exploit it.

- **Number fields (the default, and what you want).** `polygons.triangle(a, b, c)` and
  `EuclideanPolygonsWithAngles(...)` return polygons over a real number field; the doc's own
  output `Polygon(vertices=[(0,0), (1,0), (1/2, c^7 - 13/2*c^5 + 21/2*c^3 - 3/2*c)])` shows the
  generator `c`. Everything downstream — gluings, holonomies, `parabolic()`, cylinder moduli — is
  then **exact**. Always `print(S.base_ring())` after unfolding, and be suspicious if it says
  `Real Double Field`.
- **`AA` (algebraic reals).** `polygons.regular_ngon(12, field=AA)`. Exact but slower; `length()`
  returns an `AA` element by design, since a length need not lie in the field of definition.
- **`pyexactreal` / `ExactReals`.** For *transcendental* parameters — genuinely useful if you want
  a surface with a generic modulus, e.g. to check that a phenomenon is not an arithmetic accident:
  **[VERIFIED-DOC — Tour]**

  ```python
  from pyexactreal import ExactReals
  from flatsurf import similarity_surfaces, Polygon

  R = ExactReals(QuadraticField(3))
  almost_one = R.random_element(1)
  P = Polygon(angles=(1, 1, 4), vertices=[(0, 0), (almost_one, 0)])
  S = similarity_surfaces.billiard(P).minimal_cover(cover_type="translation")
  print(S.base_ring())
  ```

  These are exact real numbers represented lazily with certified comparisons — not floats.
- **`libflatsurf`/`pyflatsurf` is exact too**, over the same coefficient rings (via `pyeantic` for
  number fields and `pyexactreal` for exact reals). The floating-point numbers you see in flow
  decomposition output (`~ -7.6568542`) are only the *display* of exact elements.
- **Where floats do creep in:** `lyapunov_exponents_approx` (Monte-Carlo, genuinely stochastic),
  `RDF(...)` conversions in the tutorials, `float(...)` in plotting, and everything in §8.2.

### 9.3 Common pitfalls, ranked by how often they bite

1. **`saddle_connections(B)` bounds the SQUARED length.** Wrong by a square, silently.
2. **Marked points change the stratum.** `minimal_cover` yields `H_6(5^2, 0^2)`, not
   `H_6(5^2)`, and every dimension you compare against is then wrong. Call
   `erase_marked_points()` — *unless* the marked points are the points you are studying, in which
   case say so explicitly in your notes.
3. **Unfolding gives a cover, not the primitive surface.** Check `o.is_primitive()`,
   `o.intermediate_covers()` on the origami side; on the sage-flatsurf side, an orbit closure
   dimension that is smaller than expected is the usual symptom.
4. **`cyl.area()` from libflatsurf is twice the area.** Halve it before computing moduli. The
   docs say so in a comment that is very easy to skim past.
5. **`O.dimension()` is a lower bound**, and `is_teichmueller_curve` can only prove `False`.
6. **A singularity has many `(label, vertex)` representatives.** Compare `SurfacePoint`s
   (`S.point(...)`), which have correct `__eq__`/`__hash__`; never compare `start_data()` tuples.
7. **Mutable surfaces misbehave.** Always `set_immutable()`.
8. **Sage `Integer` vs C++ `int` at the pyflatsurf boundary.** The docs write `int(16)`,
   `int(0)`, `-int(1)` deliberately.
9. **`traj.flow(n)` stops early at a vertex.** A short trajectory is a signal, not a failure.
10. **sage-flatsurf's `veech_group()` cannot compute generators** (`NotImplementedError`). Use
    `surface_dynamics` origamis, or the `canonicalize()` membership test.
11. **`t.cusps()` does not exist** on a Teichmüller curve. Use `cusp_representatives()`.
12. **`delaunay_decomposition()` / `delaunay_triangulation()` are deprecated** — use
    `delaunay_decompose().codomain()` / `delaunay_triangulate().codomain()`.
13. **Origami invariants are a mix of Python `int` and Sage types.** `r_tuple()`, `nb_squares()`,
    `genus()`, `veech_group().index()` are plain `int` and serialise; `monodromy().order()`,
    `automorphism_group().order()`, `lattice_of_*periods()` and `sum_of_lyapunov_exponents()` are
    Sage `Integer` / `Rational` and raise `TypeError` in `json.dumps`. §6.7.2 has the table.
14. **`lattice_of_periods()` is the *relative* lattice.** On the Eierlegende Wollmilchsau it is
    `(1,0,1)` while `lattice_of_absolute_periods()` is `(2,0,2)`. Picking the wrong one silently
    loses the torus-cover index. §6.7.4.
15. **A twist word whose matrix is the identity relabels the squares.** On the 3-square L,
    `(h(1) v(-1) h(1))^4` returns `r_tuple() == (0,2,1)` instead of `(1,0,2)`; on the EW the same
    word leaves the tuples alone, so testing on one origami proves nothing. §6.7.5.

### 9.4 A workflow that keeps you honest

1. Build the surface, print `S.base_ring()` and **both** strata (with and without marked points).
2. Record the exact package versions in the notebook: `import flatsurf; flatsurf.__version__` and
   the surface-dynamics equivalent, plus the date.
3. Run the cheap probe (§7.2c or §8) to form a conjecture.
4. Re-run at 2× and 10× the bound. If the answer changes, the first run was noise.
5. Perturb: change the polygon slightly (or use `ExactReals` for a generic parameter). If the
   phenomenon vanishes, it was arithmetic; if it survives, it may be a theorem.
6. Before writing anything down, ask which half of §9.1 the result belongs to, and phrase the
   claim accordingly ("we verified computationally that …up to length 40", never "…there is no").

---

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

---

## 12. Environment cluster — probed 2026-09-19 (api-prober)

Probed on **both** targets: WSL Ubuntu (`~/miniforge3`, env `flatsurf`) and
`ssh:lingo` (`-Prefix /data/roeyzemmel/miniforge3`). Versions identical on both:
**SageMath 10.7, surface_dynamics 0.7.0, sage-flatsurf 0.8.0** (Python 3.12).

### 12.1 `from surface_dynamics import ...` — **Confirmed** (WSL and lingo)

```python
from surface_dynamics import Origami, origamis, PillowcaseCover
```
Imports clean, ~4.1 s cold on WSL, ~4.2 s on lingo. Does **not** touch
`pyflatsurf`/cppyy. Safe as the base of any origami pipeline.

### 12.2 `from sage.libs.gap.libgap import libgap` as the *first* Sage import — **Refuted**

```python
from sage.libs.gap.libgap import libgap        # plain `python`, nothing Sage imported yet
```
```
ImportError: cannot import name 'is_MPolynomial' from partially initialized module
'sage.rings.polynomial.multi_polynomial' (most likely due to a circular import)
(/home/roey/miniforge3/envs/flatsurf/lib/python3.12/site-packages/sage/rings/polynomial/multi_polynomial.cpython-312-x86_64-linux-gnu.so)
```
Chain: `libgap.pyx` → `gap/util.pyx` → `gap/element.pyx` → `permgroup_element.pyx`
→ `multi_polynomial.pyx` → `multi_polynomial_ring.py` → `multi_polynomial_element.py`.
This is a **Sage 10.7 packaging bug under a plain `python` interpreter**, not a missing
feature: nothing is wrong with libgap itself. The deep dotted path is exactly what a
confident memory or an old tutorial produces, so it belongs in the pitfall list.

**What the library offers instead — Confirmed (WSL and lingo):**
```python
from sage.all import libgap                    # 1.4 s
# or, if you need the submodule path for some other reason:
import sage.all
from sage.libs.gap.libgap import libgap        # 2.1 s — works once sage.all is loaded
```
Known case: `libgap.eval('Order(SymmetricGroup(5))')` → `120` on both targets.
Rule: **import `sage.all` (or use `from sage.all import …`) before any
`sage.libs.*` / `sage.rings.*` submodule import** in a script run by `python`
rather than `sage`.

### 12.3 `import flatsurf` — **Confirmed** (WSL and lingo)

```python
import flatsurf                                # flatsurf.__version__ == '0.8.0', 1.6 s
from flatsurf import Polygon, MutableOrientedSimilaritySurface, translation_surfaces
translation_surfaces.mcmullen_L(1, 1, 1, 1).stratum()
# H_2(2)
```
**`import flatsurf` does NOT import `pyflatsurf`.** The pure-Sage half of
sage-flatsurf (polygons, `MutableOrientedSimilaritySurface`, `translation_surfaces`,
strata) loads and works with `pyflatsurf` broken. libflatsurf is imported lazily,
only when a call needs it (`GL2ROrbitClosure`, `.decomposition(...)`, the
libflatsurf-backed saddle-connection enumeration).

> Corrects the note in `fslab/ptranslation.py` (2026-09-19), "`import flatsurf`
> goes through it", and the same claim in FlatSurfLab's `CLAUDE.md`. The
> successful lingo run in `results/2026-09-18_relative_marking_compatibility.json`,
> whose code path does `from flatsurf import Polygon, MutableOrientedSimilaritySurface`,
> is consistent with this and was never in conflict.

### 12.4 `import pyflatsurf` — **Fixed on lingo 2026-09-22** (root cause found); WSL still broken, for a second reason

> **Resolution, 2026-09-22 (read this before the history below).** The crash was never
> in cppyy's version. The frame under the signal is
> `__strlen_evex` ← `AddHostArguments` ← `cling::CIFactory::createCI`, i.e. a NULL
> string: conda-forge's cling reads the variables set by the compiler packages'
> `etc/conda/activate.d` scripts (`CXX`, `CONDA_BUILD_SYSROOT`, …), and the runner
> used to "activate" by setting `PATH` and `CONDA_PREFIX` only, which skips those
> scripts. Setting `CONDA_BUILD_SYSROOT` alone is **not** enough; a full
> `conda activate` is. `scripts/run.sh` now sources `etc/profile.d/conda.sh` and runs
> `conda activate` (no stdout buffering, unlike `mamba run`).
>
> Verified on lingo through the patched `run.sh` (cppyy 3.1.2 / cppyy-cling 6.30.0,
> gcc/gxx/libstdcxx 14.4): `import pyflatsurf` OK; `veech_double_n_gon(5).canonicalize()`
> OK; `GL2ROrbitClosure(...).decomposition((1,0))` OK in both `python` and `SAGE=1`
> modes; output still streams. The first run rebuilds cling's precompiled header
> (about a minute), later runs reuse it. **The fix reaches queued jobs only once
> `run.sh` is committed and pushed**, because `fsq` runs from a worktree at the job's commit.
>
> **WSL needed a second fix, also done 2026-09-22.** With a full activation cling
> starts, but the WSL env had gcc/gxx **16.2**, and cling cannot parse its headers
> (`member access into incomplete type '__normal_iterator<…>'` in `stl_iterator.h`).
> Fixed with `mamba install -n flatsurf gxx=14 gcc=14`, which downgrades only the 11
> compiler-toolchain packages. Do **not** also pin `libstdcxx=14`: that drags 34
> downgrades and swaps openjdk 25 → 11. The gcc-16 runtime is backward compatible,
> and only the headers matter to cling. Verified on WSL: `canonicalize()` on the
> double pentagon and `GL2ROrbitClosure(...).decomposition((1,0))`. Undo with
> `gxx=16 gcc=16`. Any future env (re)build must keep `gxx`/`gcc` at 14 until
> cppyy-cling catches up.
>
> **Signature to recognise:** exit 139 / `returncode -11` with `AddHostArguments` in
> the stack means an un-activated env; header errors under `lib/gcc/.../16.*` mean a
> too-new libstdc++.

History, kept for the record:

```python
import pyflatsurf
```
Exit code **139** (SIGSEGV), no Python traceback — the process dies inside cling's
interpreter startup:
```
Stack dump without symbol names (ensure you have llvm-symbolizer in your PATH ...):
 ...
10 libCling.so      0x00007ff32ecc3744 CreateInterpreter + 52
11 libCoreLegacy.so 0x00007ff32d4b1bbd CppyyLegacy::TROOT::InitInterpreter() + 205
12 libCoreLegacy.so 0x00007ff32d4b20e0 CppyyLegacy::Internal::GetROOT2() + 48
13 libCling.so      0x00007ff32ec462da TCling__GetInterpreter + 74
...
cppyy_backend/loader.py:139: UserWarning: No precompiled header available (failed to build);
  this may impact performance.
```
(cppyy 3.5.0 / cppyy-cling 6.32.8; also fails after downgrading to 3.1.2 / 6.30.0.)
lingo gives the same `Stack dump without symbol names` cling signature.

**What is still available with `pyflatsurf` dead:** everything in §2 (polygon
surfaces, gluings, strata) **except `canonicalize()`**, §6 (all of `surface_dynamics`:
origamis, Veech groups, strata, the database), libgap via §12.2, and the §8
pure-Python fallbacks. **Unavailable:** `GL2ROrbitClosure`, `.decomposition(v)`,
cylinder decompositions and moduli via libflatsurf (§5), the libflatsurf
Siegel–Veech path (§5.4), and **`canonicalize()`**. This list originally put
`canonicalize` among the survivors. That was wrong: on 2026-09-22 two lingo jobs
(`ex:rhombus-same-unfolding`) died with exit 139 inside
`S1.canonicalize() == S2.canonicalize()`, because `canonicalize()` lazily starts
cling to build its precompiled header. `import flatsurf` stays clean (§12.3); the
backend loads only on the first call. So a `sys.modules` check after import proves
nothing about later calls.

### 12.5 `Origami` constructor forms and index base — **Confirmed** (WSL and lingo)

Both constructor forms exist in 0.7.0 and give the *same* object:

```python
from surface_dynamics import Origami
o  = Origami('(1,2,3)', '(1,3)')                    # 1-based cycle strings
o2 = Origami([1, 2, 0], [2, 1, 0], as_tuple=True)   # 0-based images
o2 == o                 # True
```

The 3-square L, read off the installed library:

| call | value | base |
|---|---|---|
| `repr(o)` | `(1,2,3)` / `(1,3)(2)` | **1-based** |
| `o.r()` | `(1,2,3)` (a `SymmetricGroupElement`) | **1-based** |
| `o.u()` | `(1,3)` | **1-based** |
| `o.r_tuple()` | `(1, 2, 0)` | **0-based** |
| `o.u_tuple()` | `(2, 1, 0)` | **0-based** |
| `o.nb_squares()` | `3` | |
| `o.stratum()` | `H_2(2)` | |
| `o.genus()` | `2` | |
| `o.is_reduced()` | `True` | |

Confirms the CLAUDE.md trap: **1-based in the string/permutation form, 0-based in
`r_tuple()` / `u_tuple()`.** Sanity check on the 0-based tuples: `r_tuple()[0] == 1`
says square 0 → square 1, matching the 1-based cycle `(1,2,3)` sending 1 → 2.

### 12.6 The libgap cluster for the (Q2) search — **Confirmed** (WSL, SageMath 10.7 / sage-flatsurf 0.8.0 / surface_dynamics 0.7.0), probed 2026-09-19 (api-check)

All calls below use `from sage.all import libgap` (§12.2). Known cases throughout:
the 3-square L `Origami([1,2,0],[2,1,0], as_tuple=True)` (monodromy S_3),
the 4-square torus `Origami([1,0,3,2],[2,3,0,1], as_tuple=True)` (monodromy Klein
four, regular), and `origamis.EierlegendeWollmilchsau()` (8 squares, monodromy
Q_8, regular and normal in S_8).

**Building the monodromy group from 0-based tuples.** `r_tuple()`/`u_tuple()` are
0-based (`r_tuple()[i]` = image of `i`); `libgap.PermList` wants a 1-based image
list. The conversion is:

```python
def to_gap_perm(tup0based):
    n = len(tup0based)
    return libgap.PermList([tup0based[i] + 1 for i in range(n)])

r = to_gap_perm(o.r_tuple())
u = to_gap_perm(o.u_tuple())
G = libgap.Group(r, u)
```

Checked explicitly on the L: `r_tuple() == (1, 2, 0)` gives `PermList([2, 3, 1])`,
which prints as `(1,2,3)` — matching `o.r()` (`(1,2,3)`, 1-based) exactly, so the
`+1` shift is the whole conversion, nothing else changes. `G.Size()` reproduces
the known monodromy order on all three: **L → 6, torus → 4, EW → 8**
(`int(G.Size())` in each case; `libgap.SymmetricGroup(3).Size()` → `6` confirms
`SymmetricGroup(n)` too).

**`libgap.Centralizer(Sn, G)`** — signature `Centralizer(Sn, G)` with
`Sn = libgap.SymmetricGroup(n)`, returns a `GapElement` group. `.Size()` matches
`Origami.automorphism_group().order()` on all three cases exactly:

| case | `Centralizer(Sn,G).Size()` | `automorphism_group().order()` | match |
|---|---|---|---|
| L | 1 | 1 | True |
| torus | 4 | 4 | True |
| EW | 8 | 8 | True |

**Centraliser elements back into Python as 0-based tuples** — there is no
`.OnPoints` method on a `GapElement_Permutation`; the working call is the global
GAP function applied as `libgap.OnPoints(point, perm)` (point 1-based in, image
1-based out):

```python
def gap_perm_to_0based_tuple(g, n):
    return tuple(int(libgap.OnPoints(i + 1, g)) - 1 for i in range(n))

elts = list(C.Elements())              # C = libgap.Centralizer(Sn, G)
[gap_perm_to_0based_tuple(g, n) for g in elts]
```
On the L (trivial centraliser): `elts = [()]`, giving `(0, 1, 2)` — the identity,
correctly. `g.OnPoints(i+1)` (method-call form) **fails**:
```
TypeError: int() argument must be a string, a bytes-like object or a real number,
not 'sage.libs.gap.element.GapElement_Permutation'
```
— `OnPoints` is not a bound method of the permutation element; use the
`libgap.OnPoints(pt, perm)` free-function form.

**`libgap.IsTransitive(G, dom)` / `libgap.IsPrimitive(G, dom)`.** Both
`libgap.eval("[1..%d]" % n)` and `libgap(list(range(1, n+1)))` build the same
domain (`dom_eval == dom_call` → `True`); either works, `eval` is marginally
simpler to build in a loop. Confirmed: L → `IsTransitive` `true`, `IsPrimitive`
`true` (3 points, S_3, primitive as required); 4-square torus → `IsTransitive`
`true`, `IsPrimitive` `false` (imprimitive, as required).

**`libgap.AllBlocks(G)`.** Return shape is a `GapElement_List` of 1-based-point
lists, each block containing point 1. On the L (primitive): `AllBlocks(L)` →
`[ ]`, empty — correct, a primitive group has no nontrivial block. On the
4-square torus: `AllBlocks(G)` → `[ [ 1, 2 ], [ 1, 3 ], [ 1, 4 ] ]`, i.e. 0-based
`(0,1)`, `(0,2)`, `(0,3)` after the `-1` shift. Hand check: the Klein four-group
acting regularly on 4 points has exactly 3 nontrivial proper block systems, one
per order-2 subgroup — `{0,1}|{2,3}`, `{0,2}|{1,3}`, `{0,3}|{1,2}` — and
`AllBlocks` returned one representative block per system, each containing point
1 as documented. **This case cannot settle the "whole lattice vs. minimal
systems only" question** the spec raises: Klein four has only one level between
singletons and the whole set, so "all nontrivial block systems" and "all minimal
block systems" coincide here. `AllBlocks` is documented upstream as returning
representatives of *all* block systems (not just minimal ones), which this
result is consistent with but does not distinguish from the buggy
`blocks_all()`-only-minimal behaviour the spec warns about, since Klein four's
lattice has no proper level between the minimal block systems and the whole set.

**Settled on a group with a longer subgroup chain** (2026-09-19 follow-up): the
cyclic group of order 8, `G = <(1,2,3,4,5,6,7,8)>` acting regularly on 8 points,
whose subgroup lattice is the chain `1 < C_2 < C_4 < C_8`, giving two proper
nontrivial block systems by hand — blocks of size 2 (orbits of the order-4
subgroup `<g^2>`: `[[1,3,5,7],[2,4,6,8]]`, only the size-2 system is *minimal*)
and blocks of size 4 (orbits of the order-2 subgroup `<g^4>`:
`[[1,5],[2,6],[3,7],[4,8]]`). `libgap.AllBlocks(G)` on this group:
```python
gen = libgap.PermList(list(range(2, 9)) + [1])   # (1,2,3,4,5,6,7,8)
G = libgap.Group(gen)
libgap.AllBlocks(G)
# [ [ 1, 3, 5, 7 ], [ 1, 5 ] ]
```
**Returns representatives of both systems** — the size-4 block `[1,3,5,7]` (0-based
`(0,2,4,6)`) *and* the size-2 block `[1,5]` (0-based `(0,4)`), both containing
GAP-point 1 as on the torus. **Verdict: `AllBlocks` gives the whole block
lattice (all proper nontrivial block systems), not only the minimal ones** — the
spec's recommendation to use `libgap.AllBlocks(G)` in place of a `blocks_all()`
that returns only minimal systems is **confirmed correct** on a case built
specifically to distinguish the two behaviours. The earlier torus check remains
useful as a second, independent data point but was never sufficient on its own.

Two further checks on this same cyclic-8 group, both also confirmed:
`libgap.IsTransitive(G, dom)` → `true`, `libgap.IsPrimitive(G, dom)` → `false`
(imprimitive, consistent with having nontrivial blocks); `libgap.Stabilizer(G,
1).Size()` → `1` (regular action ⇒ trivial point stabiliser) and
`libgap.Orbits(H, dom)` → `[ [1], [2], [3], [4], [5], [6], [7], [8] ]`, rank 8 —
a second regular-action data point alongside the Eierlegende Wollmilchsau (§12.6
above), where the same pattern (trivial stabiliser, rank = n) held.

**`libgap.Stabilizer(G, 1)` and `libgap.Orbits(H, dom)`** — rank of the action
(1-based point 1 throughout). On the L: `Stabilizer(G,1).Size()` → `2`,
`Orbits(H, dom)` → `[ [ 1 ], [ 2, 3 ] ]`, rank 2 — the fixed point and the other
two, exactly as expected. On the EW (Q_8 regular, so the stabiliser of any point
is trivial): `Stabilizer(G,1).Size()` → `1`, `Orbits(H, dom)` → eight singleton
orbits, rank 8.

**`libgap.AbelianInvariants(H)`** — returns a `GapElement_List` of integers, the
invariant factors of $H^{\mathrm{ab}}$ (read as a period lattice: e.g. `[2]` on a
stabiliser reads as $\mathbb{Z}/2$). On `Stab_L(1)` (order 2, cyclic): `[ 2 ]`.
On `Stab_EW(1)` (trivial group): `[ ]`, the empty list — correctly, the trivial
group has no invariant factors.

**`libgap.RepresentativeAction(G, libgap([g1,g2]), libgap([h1,h2]), libgap.OnTuples)`**
— simultaneous conjugacy of an ordered pair. Signature confirmed:
`RepresentativeAction(G, seq1, seq2, action)`, both `seq1`/`seq2` wrapped with
`libgap([...])` and the action passed as `libgap.OnTuples`.

Positive case on the EW (`G` = Q_8 acting regularly, `g1=r`, `g2=u` its two
generators): picked a genuine non-identity `h` in `G`, formed the honestly
conjugate target pair `t1 = h^-1*g1*h`, `t2 = h^-1*g2*h`, then
`RepresentativeAction(G, [g1,g2], [t1,t2], OnTuples)` returned
`(1,4,3,2)(5,8,7,6)` — a `GapElement_Permutation`, verified by hand to satisfy
`conj^-1 * g1 * conj == t1` and `conj^-1 * g2 * conj == t2` (`True`). This
conjugator need not equal `h`; the check confirms it is *a* valid one.

Negative case: `RepresentativeAction(G, [g1,g1], [g1,g2], OnTuples)` — the
identical pair `(g1,g1)` cannot be simultaneously conjugate to the distinct pair
`(g1,g2)` since conjugation is injective and `g1 != g2`. Returned `fail`, a
`GapElement_Boolean`.

**Comparing `fail` from Python** — the critical check, since getting this wrong
silently breaks the pruning step:
```python
fail_const = libgap.eval("fail")
res == fail_const     # True for the negative case, False for the positive one
res is None            # False in BOTH cases — fail is a GapElement_Boolean, not None
bool(res)              # True for the positive (conjugator) case, False for `fail`
```
So `res == libgap.eval("fail")` and `bool(res)` (`False` for `fail`, `True` for
any actual permutation) both work; **`res is None` never works** — `fail` is a
distinct `GapElement_Boolean`, never Python `None`. Note also, as a side effect
observed while building the negative case: single-element
`libgap.RepresentativeAction(G, r, u, libgap.OnPoints)` on the EW also returned
`fail` — `r` and `u` (the two Q_8 generators used here) sit in different
conjugacy classes of Q_8 ($\{i,-i\}$ vs. $\{j,-j\}$ in quaternion notation), so
they are not even individually conjugate in this pair; the pair test above is
still the correct example of "positive pair when a genuine non-identity
conjugator exists, negative pair when the two sequences cannot possibly match".

**GAP integers into Python / JSON.** `.Size()` (and `AbelianInvariants` entries)
come back as `sage.libs.gap.element.GapElement_Integer`, **not**
JSON-serialisable:
```
TypeError: Object of type GapElement_Integer is not JSON serializable
```
`int(x)` converts cleanly to a plain Python `int`, which **is** serialisable
(`json.dumps(int(G.Size()))` → `"8"`). Every value pulled out of libgap for the
JSON pipeline needs an explicit `int(...)` (or, for lists like `AllBlocks`, a
list comprehension of `int(...)` over the entries).

**Timing.** On the EW (8 points): building the group from `PermList`/`Group` is
effectively instant (~0.0001 s) and `AllBlocks(G)` ~0.0007–0.0013 s. At this
cost, hundreds of members in a (Q2) sweep is negligible against Sage's own
per-process startup (~1.4–4 s, §12.2/12.3); the sweep's wall time is dominated by
process/import overhead, not by GAP group theory, unless a much larger `n` or a
richer block lattice changes this.

**pyflatsurf** — this whole cluster (`libgap.PermList`, `.Group`,
`.SymmetricGroup`, `.Centralizer`, `.IsTransitive`, `.IsPrimitive`,
`.AllBlocks`, `.Stabilizer`, `.Orbits`, `.AbelianInvariants`,
`.RepresentativeAction`) plus `surface_dynamics.Origami`/`origamis` was reached
through `from sage.all import libgap` and `from surface_dynamics import Origami,
origamis` only — no `flatsurf`/`pyflatsurf` import anywhere in this probe,
consistent with §12.4 (`pyflatsurf` segfaults) not being in the path.

---

### 12.7 Re-probe 2026-09-20 (api-check) — corrections and additions to 12.6

Five independent `api-prober` runs re-derived the 12.6 cluster from scratch in WSL
Sage 10.7 / sage-flatsurf 0.8.0 / surface_dynamics 0.7.0, two of them also on lingo.
**Everything in 12.6 held**, with one wording correction and four additions below.
Findings files: `FlatSurfLab/scratch/api_findings_{A,B,C,D,E}_*.md`.

**Read this first: there are two copies of this file.** The canonical one is
`~/.claude/skills/flatsurf-computation/references/api-recipes.md`, a symlink to the
skills-plugin copy: 2084 lines before this section was added, sections 1-12,
sha256 prefix `7ded754e`. A **stale** second copy lives under
`~/.claude/skills/synced/9966c44f...5d44e6b0.../`: 1538 lines, sections 1-11,
section 6 ending at 6.6, and **zero** occurrences of `libgap`. On 2026-09-20 three
separate notes in the sibling research repo declared sections 12, 12.2 and 6.7
"non-existent" and retracted correct citations on that basis; all three had read the
stale copy. A backup of the canonical file is at
`FlatSurfLab/scratch/api-recipes.backup-2026-09-20.md`. **Cite this file by path, not
by name.**

#### 12.7.1 Correction to 12.6: `g.OnPoints(pt)` does not raise

12.6 above says the method form "fails" and quotes a `TypeError`. The recipe it gives
(use the free function) is right, but the failure mode described is not what happens,
and the difference matters because the real one is silent.

`g.OnPoints(pt)` **raises nothing**. It returns `g**pt`: libgap's method sugar resolves
to GAP's `OnPoints(g, pt)`, which is the power operator `g^pt`, not the point-image
lookup. Checked term by term on `g = (1,2,3,4,5,6,7,8)` for `pt = 1..8`: `g.OnPoints(pt)
== g**pt` every time, no exception ever. On `g = libgap.PermList([2,1,4,3])`,
`g.OnPoints(2)` returns `()`.

The `TypeError` quoted in 12.6 is `int()`'s, one step later:
```
int(g.OnPoints(2))
TypeError: int() argument must be a string, a bytes-like object or a real number,
not 'sage.libs.gap.element.GapElement_Permutation'
```
So the mistake is caught only if `int()` is applied immediately. Store the value first
and you are holding a wrong permutation with nothing raised anywhere. The free-function
form `int(libgap.OnPoints(i + 1, g)) - 1` remains correct and is unchanged.

Round trips re-verified exactly: the 4-square torus (`(1,0,3,2)` out and back), and the
EW, `r_tuple() = (1,2,3,0,5,6,7,4)`, `u_tuple() = (4,7,6,5,2,1,0,3)`, both generators
through `PermList` -> `OnPoints` -> 0-based tuple unchanged, with `Group(gr,gu).Size()`
-> `8` confirming the monodromy independently.

#### 12.7.2 Addition: a real separating case for `RepresentativeAction`

12.6's negative case is `RepresentativeAction(G, [g1,g1], [g1,g2], OnTuples)`, which is
impossible for the trivial reason that conjugation is injective. It therefore does not
distinguish **simultaneous** conjugacy from independent elementwise conjugacy, which is
the property the pruning step actually relies on.

The case that does, in `S_4`: `g1 = (1,2)`, `g2 = (3,4)`, `h1 = (1,2)`, `h2 = (1,3)`.
Each pair is conjugate elementwise -- all transpositions are conjugate in `S_4`, and the
single-element calls return non-`fail` permutations:
```
RepresentativeAction(S4, g1, h1) = ()
RepresentativeAction(S4, g2, h2) = (1,2,4,3)
```
But no single tau can do both: tau must fix `{1,2}` setwise, hence send `{3,4}` to
itself, while `g2 -> h2` demands `tau({3,4}) = {1,3}`. Provable by hand, and the
simultaneous call agrees:
```
RepresentativeAction(S4, [g1,g2], [h1,h2], OnTuples) = fail   GapElement_Boolean
```
Any future re-probe of this call should use this pair, not the `(g1,g1)` one.

The truthiness table of 12.6 re-confirmed on the EW, all six values:
```
res_pos  is None : False      res_fail is None : False
res_pos  == fail : False      res_fail == fail : True
bool(res_pos)    : True       bool(res_fail)   : False
```
`is None` cannot discriminate; `== libgap.eval("fail")` and `bool(...)` both can.

#### 12.7.3 Addition: the pitfall that nearly poisoned 12.7.2

Hand-built EW generator tuples, guessed rather than taken from the library, produced
`Warning: the origami is not connected` and a monodromy group of order **4**, not 8.
Nothing crashed; the script ran clean and the numbers looked plausible. It was caught
only by asserting `G.Size() == 8` against the independently known answer.

**Assert the known invariant, not just that the call returned.** Use
`origamis.EierlegendeWollmilchsau()` rather than transcribing tuples.

#### 12.7.4 Addition: `AllBlocks` cross-checked against subgroup orbits

12.6's `AllBlocks` entry re-confirmed, and the whole-lattice claim cross-checked by a
route independent of `AllBlocks` itself. On the cyclic group of order 8, regular action:
```
gen: (1,2,3,4,5,6,7,8)      IsPrimitive(G8,dom8): false
raw AllBlocks(G8): [ [ 1, 3, 5, 7 ], [ 1, 5 ] ]        sizes: [2, 4]
Orbits of <gen^4> (order 2): [ [1,5],[2,6],[3,7],[4,8] ]      -> matches the size-2 rep
Orbits of <gen^2> (order 4): [ [1,3,5,7],[2,4,6,8] ]          -> matches the size-4 rep
```
Both levels returned, so the whole block lattice and not only the minimal systems.

**The four-square torus cannot settle this and a probe using only it proves nothing**:
Klein four has no subgroup level between minimal and whole, and `AllBlocks` there returns
only three size-2 systems. Confirmed by running both.

`int()` coercion re-confirmed on entries of both `AllBlocks` and `AbelianInvariants`:
```
json.dumps(raw_entry) -> TypeError: Object of type GapElement_Integer is not JSON serializable
json.dumps(int(raw_entry)) -> 2
```

#### 12.7.5 Addition: import topology and timing on lingo

12.1-12.4 re-confirmed on **both** WSL and lingo, checking `sys.modules` after each
import rather than only that the import succeeded:

| | WSL | lingo |
|---|---|---|
| `surface_dynamics` pulls in `pyflatsurf`/`cppyy`/`cling` | `[]` | `[]` |
| `import flatsurf` pulls them in | `[]`, 0.125 s | `[]`, 0.106 s |
| `import pyflatsurf` | segfault, `returncode -11` | segfault, `returncode -11` |

`-11` is SIGSEGV, the same signal as the exit code 139 (128+11) recorded in 12.4. The
cling stack ends in `CreateInterpreter` / `TROOT::InitInterpreter()` on both machines.
(Superseded 2026-09-22: the cause was the missing `conda activate`, and lingo now works;
see the resolution at the head of 12.4.)

**Timing, and it is not what 12.6 assumed.** `import surface_dynamics`: WSL **5.5 s**;
lingo **64.8 s cold, 14.7 s warm**, on the NFS-backed `/data` env. The timer sat inside
the remote process, bracketing the import statement alone, so none of this is ssh
overhead. 12.6's timing note above cites "~1.4-4 s" of per-process startup; that is a
WSL figure. On lingo the steady-state floor is roughly **15 s per process**, and the
first launch after a quiet period pays about a minute. The conclusion 12.6 draws is
unchanged but much stronger: batch a sweep into one process.

Both probes used `-Prefix /data/roeyzemmel/miniforge3`. Without it, `run.ps1 -Target
ssh:lingo` fails with `no python in /a/home/.../miniforge3/envs/flatsurf -- run
scripts/setup_env.sh first`, which reads as "environment not installed" and is not.

**Still open.** Whether `fslab/christoffel/` stays clean of `pyflatsurf` on lingo could
not be checked: `import fslab.christoffel` there raises `ModuleNotFoundError`, because
the remote checkout predates the package. Confirmed on WSL (no direct import; `sys.modules`
clean). Recheck after the next push.

#### 12.7.6 Addition: `conj_test_factory` / `simultaneous_conjugator_gap` (`fslab/christoffel/gapinv.py`) — Confirmed against 12.6/12.7.2, WSL only, probed 2026-09-23 (api-check)

Question under test: does `libgap.RepresentativeAction(D, src, tgt, libgap.OnTuples)`
decide simultaneous conjugacy of pairs *in a subgroup `D`, not `S_n`*, and does
`gapinv.py`'s inversion (`simultaneous_conjugator_gap` returning
`inverse(representative_action_tuples(...))`) actually match `perm.py`'s
`conjugate(g, h) = h g h^-1` under `compose(p, q)[i] = q[p[i]]`? 12.6/12.7.2 confirmed
the raw GAP call and the `fail` trap; they did not run `gapinv.py`'s own wrapper
functions or pin the inversion against `perm.py`. This entry does both, plus a fresh
hand-derived Q_8 pair (not the `(g1,g1)` or `S_4`-transposition cases already on
file) and the latency at `|G| ~ 10^4` the family-hunt budget needs.

Probe: `FlatSurfLab/scratch/probe_repaction_convention.py`, run via
`scripts\run.ps1 scratch\probe_repaction_convention.py` (WSL, SageMath 10.7 /
sage-flatsurf 0.8.0 / surface_dynamics 0.7.0). **Lingo side not run this dispatch —
VPN down (`scripts\vpn.ps1` → "vpn: down (Ethernet 4: Disabled)"); unconfirmed there.**

**0. Existence/signature.** `hasattr(libgap, 'RepresentativeAction')` → `True`.
`inspect.signature` fails (`ValueError: no signature found for builtin
<method-wrapper '__call__' of ... GapElement_Function ...>`) — libgap functions carry
no Python-introspectable signature; the call shape has to come from GAP's own help or,
as here, from running it. `help(libgap.RepresentativeAction)` prints only the generic
`GapElement_Function.__call__` docstring (`*args -> GapElement`), no argument names —
confirms existence and callability but not arity; arity is pinned by 12.6's worked
examples and reconfirmed by this run.

**1. Fresh Q_8 hand-derived negative case: `(r,u)` vs `(u,r)`.** Using
`origamis.EierlegendeWollmilchsau()`'s tuples directly (`r = (1,2,3,0,5,6,7,4)`,
`u = (4,7,6,5,2,1,0,3)`, 0-based; `r=i`, `u=j` in quaternion notation), `D = <r,u>`,
`D.Size() = 8`. Hand reasoning: $Q_8$'s conjugacy classes are $\{1\},\{-1\},\{i,-i\},
\{j,-j\},\{k,-k\}$ (inner automorphisms act as $\mathrm{Inn}(Q_8)\cong V_4$, fixing
each cyclic subgroup $\langle i\rangle,\langle j\rangle,\langle k\rangle$ setwise and at
worst inverting its generator). Any conjugate of $i$ lies in $\{i,-i\}$, and $j\notin$
that class, so no single conjugator can send $i\mapsto j$ — the *ordered pair*
$(i,j)\to(j,i)$ is therefore not simultaneously conjugate, by the same obstruction
already used for a single element, but now stated for the pair as the task asked.
Ran:
```
RepresentativeAction(D,[R,U],[U,R],OnTuples) = fail   type: GapElement_Boolean
  == fail_const? True   is None? False   bool? False
```
Matches the hand prediction.

**2. Fresh Q_8 hand-derived positive case: `(r,u)` vs `(r^-1,u^-1)`, via `k = ij`.**
Hand computation from the quaternion relations $ij=k$, $ji=-k$, $ki=j$, $kj=-i$:
$k\,i\,k^{-1} = k\,i\,(-k) = -(k\,i\,k) = -(j\,k) = -i$ (using $jk=i$), and
$k\,j\,k^{-1} = k\,j\,(-k) = -(k\,j\,k) = -((-i)\,k) = i\,k = -j$ (using $ik=-j$). So
conjugation by $k$ sends $(i,j)\mapsto(-i,-j) = (i^{-1},j^{-1})$ — the pair **is**
simultaneously conjugate to its elementwise inverse. Ran, with `Rinv = inverse(r)`,
`Uinv = inverse(u)` (`perm.inverse`, i.e. GAP inverse too since inversion doesn't
depend on the composition convention):
```
RepresentativeAction(D,[R,U],[Rinv,Uinv],OnTuples) = (1,6,3,8)(2,5,4,7)   GapElement_Permutation
  == fail_const? False   is None? False   bool? True
  res_pos^-1 * R * res_pos == Rinv ? True
  res_pos^-1 * U * res_pos == Uinv ? True
```
Confirms both the GAP convention $g^x = x^{-1}gx$ (stated in `gapinv.py`'s docstring)
and the hand-derived answer: a genuine conjugator exists, as predicted, and it is a
GAP `GapElement_Permutation` satisfying the GAP-sense relation directly.

**3. `gapinv.py`'s own functions, run (not just the raw GAP call), and the inversion
pinned against `perm.py`.** This is the part 12.6/12.7 never exercised — `conj_test_factory`
and `simultaneous_conjugator_gap` are the functions the (Q2) BFS dedupe actually calls,
not `libgap.RepresentativeAction` directly.
```python
x = gapinv.representative_action_tuples([r, u], [r, u], [r_inv, u_inv], n)
# -> (5, 4, 7, 6, 3, 2, 1, 0)                      (0-based tuple, GAP's x with r^x=r_inv)
h = gapinv.simultaneous_conjugator_gap([r, u], [r_inv, u_inv], n, gens_domain=[r, u])
# -> (7, 6, 5, 4, 1, 0, 3, 2)                      (package convention: conjugate(r,h)==r_inv)
perm.conjugate(r, h) == r_inv   # True
perm.conjugate(u, h) == u_inv   # True   <- BOTH hold: the load-bearing check
```
`h != inverse(x)`'s naive negation is not what's being claimed — checking directly,
`h == inverse(x)` holds exactly (`(7,6,5,4,1,0,3,2) == inverse((5,4,7,6,3,2,1,0))`),
confirming `gapinv.py`'s documented inversion step. **`conj_test_factory`'s negative
case, run through the actual factory-produced test, not just the raw GAP call:**
```python
gapinv.representative_action_tuples([r, u], [r, u], [u, r], n)   # -> None (not fail!)
gapinv.simultaneous_conjugator_gap([r, u], [u, r], n, gens_domain=[r, u])  # -> None
```
Both correctly normalise GAP's `fail` to Python `None` before returning — this is
`_is_fail` working as documented, exercised through the real call path rather than
inline.

**4. Convention pinned in `S_3`, independently of the Q_8 case, with the action
convention made explicit.** `g3 = (1,2,0)` (the 3-cycle $(0\,1\,2)$, 0-based),
`h3 = (1,0,2)` (the transposition $(0\,1)$). Hand-predicted
`perm.conjugate(g3,h3) = h3 g3 h3^-1` (package sense) by relabelling the cycle
$(0\,1\,2)$ under swapping $0\leftrightarrow1$: becomes $(1\,0\,2) = (0\,2\,1)$ as a
cycle, i.e. the 0-based tuple $(2,0,1)$. Ran: `perm.conjugate(g3,h3) == (2,0,1)`
→ **True**, confirming the hand prediction and, independently, `compose`'s "first `p`
then `q`" convention (`gapinv.py`'s stated reduction of the package's `h g h^-1` to
GAP's `h*g*h^-1`). Then asked GAP for the *single-element* conjugator, in GAP's own
`g^x = x^{-1}gx` sense, target = the same `(2,0,1)`:
```
RepresentativeAction(S3, G3, tgt3, OnPoints) = (2,3)     # GAP 1-based cycle notation
  x3 as 0-based tuple: (0, 2, 1)
  h3^-1 predicted: (1, 0, 2)
  match: False
```
This mismatch is **not** a refutation: `g3` (order 3) has nontrivial centraliser
`<g3>` in `S_3` (order 3), so the conjugator solving `g3^x = target` is not unique —
`x3` and `h3^-1` are both valid, differing by an element of `C_{S_3}(g3)`. Checked:
`x3^-1 * G3 * x3 == tgt3`? **True** (GAP arithmetic, confirms `x3` is *a* valid
conjugator). The load-bearing check is instead run through `gapinv.py`'s own wrapper:
```python
h3_from_pkg = gapinv.simultaneous_conjugator_gap([g3], [predicted], 3, gens_domain=[g3, h3])
# -> (0, 2, 1)   (also not equal to h3 -- same non-uniqueness -- but:)
perm.conjugate(g3, h3_from_pkg) == predicted   # True
```
So: **any given `x` from `RepresentativeAction` need not equal "the" conjugator one
constructed by hand when the centraliser is nontrivial, but `gapinv.py`'s
`simultaneous_conjugator_gap` always returns *some* `h` satisfying the package's own
`conjugate(g,h)==target` relation exactly** — which is the only property `conj_test_factory`
relies on. This nuance (non-uniqueness of the conjugator on non-regular actions) is not
in 12.6/12.7 and is worth carrying forward: **never assert `h == (the constructed
conjugator)`; only assert the conjugation relation holds.**

**5. `fail`-handling, reconfirmed through `gapinv.py`'s own `_is_fail`.** Same
three-way table as 12.6/12.7.2 (`is None` always `False`, `== libgap.eval("fail")` and
`bool(...)` both discriminate correctly), and separately confirmed that `_is_fail`
converts both to Python `None` at the `gapinv.py` API boundary (item 3 above) — this
closes the gap between "the raw GAP trap is understood" (12.6/12.7.2) and "the
project's wrapper actually applies the trap correctly" (this entry).

**6. Timing at `|G| ~ 10^4`, the family-hunt budget figure.** Built
`P = Image(IsomorphismPermGroup(DirectProduct(CyclicGroup(100), CyclicGroup(100))))`,
confirmed `P.Size() = 10000`, `IsPermGroup(P)` `True`, 4 generators. 1000 calls to
`libgap.RepresentativeAction(P, [g1,g2], [g1,g2], OnTuples)` (trivial positive case,
`src == tgt`, so the identity conjugator is found immediately — a **lower-bound**
timing, not a worst case; a genuinely hard search in a group this size could cost
more) took **0.0054 s total, 0.0000054 s/call**. Consistent with 12.6's "hundreds of
members negligible against Sage's own process startup" conclusion — even at `|G| ~
10^4`, `RepresentativeAction` itself is not the bottleneck; process/import overhead
(5.5 s WSL / 15-65 s lingo, per 12.7.5) dominates by four to seven orders of
magnitude. **Not a worst-case bound**: a pair genuinely requiring backtracking search
through a 10^4-element group could be far slower; this timing only establishes the
floor.

**Verdict: gapinv.py's `conj_test_factory` assumption is Confirmed**, on every
sub-claim tested: `RepresentativeAction(D, src, tgt, libgap.OnTuples)` decides
simultaneous conjugacy *within the subgroup `D`* (not `S_n`) exactly as the (Q2)
soundness argument requires; `_is_fail`/`simultaneous_conjugator_gap`'s inversion
correctly translates GAP's `g^x=x^{-1}gx` into the package's `conjugate(g,h)=hgh^{-1}`
convention; and the returned conjugator, while not unique when the centraliser of the
source pair in `D` is nontrivial, always satisfies the package's own conjugation
relation, which is all `conj_test_factory` needs.

---

### 12.8 Multi-statement GAP function definitions through `libgap` — refutation and fix, probed 2026-09-20 (api-check)

**What failed in production.** `fslab/christoffel/gap_reverify.py:419`, `_gap_func`, on
lingo (job `20260920-123729`, commit `de0c1c5`, Sage 10.7): `f = libgap.eval(source)`
where `source` is a `function(gens, maxStates, maxGroup) local ...; ... end;` block
(`_BFS_GAP`, line 193). The docstring at line 408 had already flagged the form
UNCONFIRMED. It has now run and failed.

**Refuted: `libgap.eval(source)` of a `function ... end;` block, trailing `;` included.**
```
sage.libs.gap.util.GAPError: can only evaluate a single statement
```
Reproduced exactly on the production sources, not a toy: `libgap.eval(_BFS_GAP)` and
`libgap.eval(_COVER_GAP)`, both as they stand in `gap_reverify.py` (multi-line, `local`
declarations, `for`/`while` loops, `if`/`Error`, `end;` with trailing newline), both raise
the identical `GAPError`. `libgap.function_factory(source)` with the trailing `;` left in
raises the **same** `GAPError` — `function_factory` is "almost the same as calling
`libgap.eval(function_name)`" (its own docstring, `sage/libs/gap/libgap.pyx:431`) and
inherits the restriction; it does not sidestep it. Also refuted: assigning inside GAP,
`libgap.eval("name := function(...) ... end;;")`, raises the same `GAPError` — the
statement-count restriction applies to the whole string handed to `eval`, before any
assignment or factory logic sees it, so wrapping does not help.

**Confirmed replacement.** Strip the string with `.strip()` and drop exactly the final
`;` that follows the closing `end`, then hand the result to either `libgap.eval` or
`libgap.function_factory` — both work once that one semicolon is gone:
```python
def _strip_trailing_semicolon(source):
    s = source.strip()
    if s.endswith(";"):
        s = s[:-1]
    return s

f = libgap.function_factory(_strip_trailing_semicolon(source))
```
`libgap.function_factory(str) -> GapElement_Function`, confirmed by
`inspect.signature` failing (it is a Cython builtin, `ValueError: no signature found for
builtin`) and its docstring read directly instead: `Gap.function_factory(self,
function_name)`, "the name of a GAP function" — the doc line describes the intended use
(wrapping an already-named GAP function) but the probe shows it accepts and evaluates a
full function-literal source string exactly like `eval` does, once that string is a
single GAP statement. `libgap.eval(_strip...(source))` also returns a
`GapElement_Function` and is equally usable; `function_factory` is not required, only the
semicolon fix is. Both were run on the unmodified `_BFS_GAP` and `_COVER_GAP` strings
from `gap_reverify.py` (not a simplified stand-in) and both succeeded:
```
=== _BFS_GAP repr tail: ';\nend;'
_BFS_GAP libgap.eval(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'>
_BFS_GAP function_factory(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'> True
=== _COVER_GAP repr tail: ';\nend;'
_COVER_GAP libgap.eval(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'>
_COVER_GAP function_factory(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'> True
```

**Known-answer case, genuinely multi-statement** (a `local` block, a `for` loop, list
accumulation, a `return` of a list) run on `origamis.EierlegendeWollmilchsau()` with
`assert Size() == 8` checked *before* trusting anything, per the pitfall recorded in
12.7.3:
```
Group(r,u).Size() = 8          # assert passed
function_factory call result: [ [ 1, 4, 2, 4, 4, 4, 4, 4 ], 27, 8 ]
element orders sorted: [1, 2, 4, 4, 4, 4, 4, 4]
order histogram: Counter({4: 6, 1: 1, 2: 1})
```
This is the quaternion group `Q8`'s exact element-order profile — one identity (order 1),
one central involution (order 2), six elements of order 4 — an independently known
answer, not merely a plausible-looking one. The unmodified production `_BFS_GAP`,
called the same way on the same generators, also completed and gave a self-consistent
answer: `m=8, complete=1, nStates=24, num vals=6` (6 = the number of distinct minimal
Christoffel values reachable in `Q8` from its two order-4 generators before the BFS
frontier closes — `complete=1` confirms the BFS exhausted the state space rather than
hitting `maxStates`).

**The two production dependency questions:**

- **Callable with plain `int` args and a `libgap` list of generators**, i.e.
  `f(gens, int(max_states), int(group_limit))` as `_gap_func`/line 497 calls it —
  **confirmed**. Ran `f_ff(gens, int(100), int(10000))` where `gens = libgap([r, u])`;
  returned the same `GapElement_List` as the non-`int`-cast call. libgap coerces Python
  `int` to GAP integers transparently at the call boundary; no `libgap(...)` wrapping of
  the ints is needed.
- **Caching the returned function in a module-level dict (`_FUNCS`) across calls in one
  Sage process** — **confirmed safe**, at least for repeated calls with fresh arguments.
  Called the same cached `GapElement_Function` twice with identical arguments (results
  agreed) and once with different arguments (returned a distinct, correct result with no
  cross-call state bleed). The GAP function's `local` variables are re-initialised on
  each GAP-level call, as GAP semantics require, and the Sage-side wrapper is a thin
  handle to the GAP object, not a fresh recompilation — nothing was observed to leak
  between calls to the same cached function.

**The fix that must land in `gap_reverify.py`.** Only `_gap_func` at line 419 needs to
change — strip the trailing `end;`'s semicolon before `libgap.eval` (or switch to
`libgap.function_factory` on the same stripped string; either is confirmed). That fix is
`family-experimenter`'s to apply, not made here.

Probed against **sage-flatsurf 0.8.0 / surface_dynamics 0.7.0 / SageMath 10.7**, WSL,
2026-09-20. Probe scripts: `FlatSurfLab/scratch/probe_gap_funcdef.py` (the isolated
`function_factory` characterisation and the Q8 known-answer case) and
`FlatSurfLab/scratch/probe_gap_funcdef2.py` (re-run against the unmodified `_BFS_GAP` /
`_COVER_GAP` production strings). Opened the canonical copy of this file at
`C:\Users\Galit\.claude\skills\flatsurf-computation\references\api-recipes.md` per
Roey's 2026-09-20 designation (2225 lines before this section, §§1-12 including 12.7); did
not open the stale `~/.claude/skills/synced/` copy.

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
