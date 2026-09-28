# Illumination recipes (§7)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

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

