# Saddle connections, holonomy, trajectories (§4)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

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

