# Cylinder and flow decompositions, moduli (§5)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

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

