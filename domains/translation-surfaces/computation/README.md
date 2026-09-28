# Computation in this domain

What the translation-surfaces pack knows about computing: the verified API recipes for
sage-flatsurf / surface_dynamics / libgap, and two pure-Python scripts that need no
Sage. How to design, run, validate and report an experiment is **not** here: that is the
Scientist role's `experiment-method` skill, and where code runs (WSL, a local Linux box,
an ssh workstation) is the Scientist instance's environment profiles (`/scientist:env`).
This folder is domain mathematics, not plugin logic.

Numerics in this subject earn their keep by killing false conjectures cheaply and by
revealing what the correct statement should be. They never prove anything.

## Which tool

| Situation | Use |
|---|---|
| Sage with sage-flatsurf + surface_dynamics is reachable | the recipe files in `api/` — read `api/INDEX.md`, then the one topic file you need |
| No Sage, and the question is about a square-tiled surface | `scripts/origami_illumination.py` (exact) |
| No Sage, or an irrational polygon | `scripts/billiard_trace.py` (floating point) |

In an unknown sandbox, check before planning around Sage:

```bash
which sage && sage -c "import flatsurf; print(flatsurf.__version__)"
python3 -c "import surface_dynamics; print(surface_dynamics.version.version)"
```

If it is not there and the Scientist's environments cannot be reached, do not attempt
a long installation in a sandbox (it is a large conda install and often blocked). Go
straight to the bundled scripts.

## Bundled scripts (no Sage needed, both tested)

**`scripts/origami_illumination.py`** — *exact* illumination probe on a
square-tiled surface. This is the one that matters. On an origami, the holonomies
joining two given points form a translate of $\mathbb{Z}^2$, so they can be
enumerated exactly in `Fraction` arithmetic with nothing missed below a length
bound, and trajectories passing through a vertex are correctly reported as
undefined rather than silently continued. No floating point anywhere.

```python
from origami_illumination import Origami
from fractions import Fraction as F
O = Origami([1, 0, 2], [2, 1, 0])                  # 3-square L in H(2)
O.connections((0, F(1,3), F(1,4)), (2, F(1,5), F(2,7)), bound=8.0)
O.illuminates((0, F(1,3), F(1,4)), (2, F(1,5), F(2,7)), bound=8.0)
```

Converting a `surface_dynamics` origami to this format is `Origami(o.r_tuple(),
o.u_tuple())`: both are 0-based (`api/origamis.md` §12.5).

**`scripts/billiard_trace.py`** — floating-point billiard tracer for an arbitrary
polygon, including irrational ones where unfolding is unavailable. Use it for
Tokarsky-style room experiments. `illumination_scan` returns a *closest approach*,
not a yes/no; the script's docstring explains how to read that and names its own
sampling bias (corner-hitting directions are under-sampled, and those are exactly
the interesting ones).

Both files run their self-tests with `python3 <file>` (on Windows `py <file>`); run
them once after any edit, since they check real invariants (lattice-point counts on the
torus, orbit closure of the slope-1 square trajectory, reversal symmetry of
connections). The standard examples they and the recipes use are listed with ids in
`../examples.md`.

## With Sage: the recipe files

`api/` has version-checked, runnable recipes with upstream's own printed outputs, one
file per topic. Read `api/INDEX.md`, then the one file you need, rather than writing
from memory — **this API changed substantially in recent versions and plausible-looking
calls from older tutorials silently do not exist.**

| File | § | Contents |
|---|---|---|
| `api/setup.md` | 1, 12.1–12.4 | Versions, installation, imports; the pyflatsurf / cling crash |
| `api/surfaces.md` | 2, 3 | Building surfaces: `MutableOrientedSimilaritySurface`, polygon constructors, strata, $\mathrm{GL}(2,\mathbb{R})$ action, Delaunay, deciding equality; billiard unfolding and its two pitfalls |
| `api/saddle-connections.md` | 4 | Saddle connections, the `SaddleConnection` interface, holonomy vectors, straight-line flow, plotting |
| `api/cylinders.md` | 5 | Cylinder / flow decompositions, moduli, orbit closures, raw libflatsurf for Siegel–Veech |
| `api/origamis.md` | 6, 12.5 | `surface_dynamics`: origamis, Veech groups, strata, Lyapunov exponents, the origami database, `origamis.*` |
| `api/libgap.md` | 12.2, 12.6–12.8 | `libgap` from Sage |
| `api/illumination.md` | 7 | End-to-end illumination recipes |
| `api/pure-python.md` | 8 | The pure-Python fallbacks (source of the bundled scripts) |
| `api/practice.md` | 9 | Using this responsibly; exact vs floating arithmetic; ranked pitfall list |
| `api/quick-reference.md` | 10, 11 | Removed API; the quick reference card |
| `api/sources.md` | — | Upstream doc links; the tag definitions |

The § numbers are those of the former single `api-recipes.md`, so older citations
("api-recipes §6.7.1") still resolve through the index.

Verified against sage-flatsurf 0.8.0 and surface-dynamics 0.7.0 (SageMath 10.7).
Sections tagged `[UNVERIFIED]` are composed rather than copied from docs — run them on
a known example before trusting a result. The API traps worth carrying in memory are
collected in `../traps.md` §C.

## Writing here

A confirmed signature or a refutation goes in its topic file under `api/` (rules in
`api/INDEX.md`), with a line in `../CHANGELOG.md`. Records about particular machines,
job ids or one project's code do not belong in this pack: they go to the Scientist
home's environment notes or to the project's own notes.
