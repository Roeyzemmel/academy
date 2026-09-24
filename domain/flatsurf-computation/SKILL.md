---
name: flatsurf-computation
description: Run computational experiments on translation surfaces and rational billiards using sage-flatsurf, surface_dynamics, or bundled pure-Python fallbacks that need no SageMath. Use this whenever a claim about flat surfaces should be tested numerically before it is proved — building a surface from polygons, unfolding a rational billiard, enumerating saddle connections and holonomy vectors, computing cylinder decompositions and moduli, computing a Veech group of a square-tiled surface, finding an orbit closure, tracing billiard trajectories, or probing whether one point illuminates another. Trigger on "let's test this numerically", "check this on an example", "compute the saddle connections", "unfold this polygon", "what's the stratum", "find a counterexample", "sage-flatsurf", "surface_dynamics", "origami", or any request to experiment with a flat-surface example rather than prove something about it.
---

# Computational experiments on flat surfaces

Numerics in this subject earn their keep by killing false conjectures cheaply and
by revealing what the correct statement should be. They never prove anything. Keep
that boundary visible in everything reported: an experiment produces "no
counterexample found up to length 40 on these 6 surfaces", never "true".

## First: which environment am I in?

Three places code can run. Pick the first that fits; the bundled scripts run in
all of them, the Sage recipes only in the last two.

| Where | What is there | How to run |
|---|---|---|
| **Windows** (Roey's laptop, Claude Code in the desktop app or VS Code) | Python 3.10 via the `py` launcher only. No Sage. | `py scripts\origami_illumination.py` |
| **WSL Ubuntu** on the same laptop | Miniforge at `~/miniforge3`, conda env `flatsurf` with sage-flatsurf + surface_dynamics (installed by `scripts/setup_env.sh`). | From Windows: `scripts\flatsurf-run.ps1 experiment.py`. From a WSL shell: `. ~/miniforge3/etc/profile.d/conda.sh && conda activate flatsurf`, then `python experiment.py` (FlatSurfLab: `bash scripts/run.sh`). |
| **Remote Linux server** | Same layout once `scripts/setup_env.sh` has been run there. | `scripts\flatsurf-run.ps1 experiment.py -Target ssh:<host>` pipes the script over ssh. |

`scripts/flatsurf-run.ps1` also takes `-Code "…"` for one-liners and `-Sage` to
use the Sage interpreter instead of Python. Windows paths are translated with
`wslpath`; files the script reads or writes should live under `/mnt/c/...` (the
repo) so both sides see them.

Two things that look like they should work and do not:

- **`mamba run` is not usable here.** It captures the child's stdout until exit, so
  nothing streams and interactive tools are dead, and this build rejects
  `--no-capture-output` ("exec: --: invalid option"). Use a sourced `conda activate`
  instead, which is what the runner scripts do. **Not PATH alone**: that skips the
  compiler packages' `activate.d` scripts, and cling (under pyflatsurf, so under
  `canonicalize()` and `GL2ROrbitClosure`) then segfaults.
- **A project may forbid running experiments locally at all.** In FlatSurfLab every
  experiment run, validation included, goes through a job queue to a remote server,
  and WSL Sage is kept for unit tests and one-line API checks. Read the project's
  `CLAUDE.md` before picking a row of that table; it wins over this skill.

**Setting up a new Linux machine** is one command, no root:

```bash
bash scripts/setup_env.sh        # ~10-30 min, downloads SageMath from conda-forge
```

It installs Miniforge, creates the `flatsurf` env, and prints the versions plus
the stratum of a McMullen L as a smoke test. Re-running it updates the env.

**In an unknown sandbox**, check before planning around Sage:

```bash
which sage && sage -c "import flatsurf; print(flatsurf.__version__)"
python3 -c "import surface_dynamics; print(surface_dynamics.version.version)"
```

**If Sage is present**, use the recipe files under `references/api/`, the verified
API guide below. **If it is not** and you cannot reach the WSL env, do not waste a long
installation attempt in a sandbox (it is a large conda install and often blocked).
Go straight to the bundled scripts, which are pure standard-library Python and
cover the two questions that come up most.

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
o.u_tuple())` — check the indexing base against `o.r()` once, as the reference
file flags this as unverified.

**`scripts/billiard_trace.py`** — floating-point billiard tracer for an arbitrary
polygon, including irrational ones where unfolding is unavailable. Use it for
Tokarsky-style room experiments. `illumination_scan` returns a *closest approach*,
not a yes/no; the script's docstring explains how to read that and names its own
sampling bias (corner-hitting directions are under-sampled, and those are exactly
the interesting ones).

Both files run their self-tests with `python3 <file>`; run them once after any
edit, since they check real invariants (lattice-point counts on the torus, orbit
closure of the slope-1 square trajectory, reversal symmetry of connections).

## With Sage: use the recipe files

`references/api/` has version-checked, runnable recipes with upstream's own printed
outputs, one file per topic. Read `references/api/INDEX.md` (2 KB), then the one
file you need, rather than writing from memory — **this API changed substantially in
recent versions and plausible-looking calls from older tutorials silently do not
exist.**

| File | § | Contents |
|---|---|---|
| `setup.md` | 1, 12.1–12.4 | Versions, installation, imports; the pyflatsurf / cling crash |
| `surfaces.md` | 2, 3 | Building surfaces: `MutableOrientedSimilaritySurface`, polygon constructors, strata, $\mathrm{GL}(2,\mathbb{R})$ action, Delaunay, deciding equality; billiard unfolding and its two pitfalls |
| `saddle-connections.md` | 4 | Saddle connections, the `SaddleConnection` interface, holonomy vectors, straight-line flow, plotting |
| `cylinders.md` | 5 | Cylinder / flow decompositions, moduli, orbit closures, raw libflatsurf for Siegel–Veech |
| `origamis.md` | 6, 12.5 | `surface_dynamics`: origamis, Veech groups, strata, Lyapunov exponents, the origami database, `origamis.*` |
| `libgap.md` | 12.2, 12.6–12.8 | `libgap` from Sage |
| `illumination.md` | 7 | End-to-end illumination recipes |
| `pure-python.md` | 8 | The pure-Python fallbacks (source of the bundled scripts) |
| `practice.md` | 9 | Using this responsibly; exact vs floating arithmetic; ranked pitfall list |
| `quick-reference.md` | 10, 11 | Removed API; the quick reference card |

The § numbers are those of the former single `api-recipes.md`, so older citations
("api-recipes §6.7.1") still resolve through the index.

Verified against sage-flatsurf 0.8.0 and surface-dynamics 0.7.0. Sections tagged
`[UNVERIFIED]` are composed rather than copied from docs — run them on a known
example before trusting a result.

## API traps worth carrying in memory

These are the ones that cost an afternoon each:

- `saddle_connections(B)` bounds the **squared** length — the keyword is literally
  `squared_length_bound`.
- `SaddleConnection` has `start_data()` / `end_data()` returning `(label, vertex)`.
  There is no `start()` / `end()`, despite what older snippets suggest.
- There is **no** `surface.cylinder_decomposition(direction)`; go through
  `GL2ROrbitClosure.decomposition(v, limit)`.
- libflatsurf's `cyl.area()` returns **twice** the area. Miss this and every
  modulus is wrong by a factor of 2 — and wrong by a consistent factor is the
  hardest kind of wrong to notice.
- sage-flatsurf's `veech_group()` raises `NotImplementedError` for generators. A
  real Veech group needs a square-tiled surface via `surface_dynamics`.
- `t.cusps()` does not exist on a Teichmüller curve; it is `cusp_representatives()`
  returning `(origami, width)` pairs.
- Deprecated and to be avoided: `delaunay_decomposition()`,
  `delaunay_triangulation()`, `Singularity()`, and `Stratum.zeros/genus/nb_zeros`.

## How to run an experiment worth trusting

1. **Say what would refute the claim** before computing anything. An experiment
   with no refuting outcome is not an experiment.
2. **Validate the setup on something you know.** The square torus, the 3-square L
   in $\mathcal{H}(2)$, the regular pentagon. If the pipeline gets the torus
   wrong, nothing downstream means anything. Every bundled script does this.
3. **Prefer exact arithmetic.** Number fields for Veech surfaces, `ExactReals` /
   pyflatsurf for the rest, `Fraction` in the fallbacks. Floating point turns
   "these two points coincide" — the whole question in illumination problems —
   into a threshold choice, and the answer then depends on the threshold.
4. **Watch the stratum.** Adding a marked point moves $\mathcal{H}(2)$ to
   $\mathcal{H}(2,0)$ and changes dimensions and orbit closures. Unfolding often
   produces a cover rather than the primitive surface, and `erase_marked_points()`
   changes the object. Print the stratum at every stage.
5. **Report the bound and the class searched.** "No connection with squared length
   below 1600, over these 6 surfaces, searching vertex pairs only" is a usable
   research statement; "it doesn't illuminate" is not. Naming the class is not
   pedantry — it is what lets a reader (and you) notice that the search space
   structurally could not have contained the counterexample, which is the most
   common way an exhaustive-looking computation means nothing.
6. **Don't let the computation replace the argument.** Before building
   validation layers around a numerical result, check whether a short proof
   settles it. Two points inside a single cylinder are joined by a segment that
   cannot meet the cone point — one observation, no computer. Reaching for
   exhaustive search where a clean argument exists is the characteristic waste
   here.
7. **Save the script.** Referees and coauthors ask how a computation was done, and
   a rerunnable file with its seed and versions is the answer. Keep experiment
   scripts next to the paper.

When an experiment produces something surprising, suspect the code first — a
stratum mismatch, a squared-vs-linear bound, the factor of 2 — before believing a
new theorem.
