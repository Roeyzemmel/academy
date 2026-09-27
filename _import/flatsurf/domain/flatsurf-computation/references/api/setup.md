# Versions, environment, imports (§1, §12 intro, §12.1, §12.3, §12.4)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

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
