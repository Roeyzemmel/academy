# Extracted environment records (destined for `FlatSurfLab/docs/environment.md`)

(The imported copy under `_import/` was removed once distributed; the original is unchanged in `C:\Work\Math\claude-flatsurf\domain\`.)

Verbatim passages cut from the old `flatsurf-computation` API recipe files when they
became the domain pack's `domains/translation-surfaces/computation/api/` (Group B,
2026-09-28). They are records about specific machines (the laptop's WSL env, the
remote server lingo), job runs and file locations, not facts about the API, so they
belong in the Scientist home's environment notes. The pack keeps the API findings in
a machine-neutral wording. Line numbers are those of the imported files
(`_import/flatsurf/domain/flatsurf-computation/references/api/`, claude-flatsurf as
imported by Group A). Passages are quoted whole, so a few API sentences appear here
as well as in the pack.

Group B did not write into FlatSurfLab (read-only in this run); moving this file to
`FlatSurfLab/docs/environment.md` is left to the Group C (FlatSurfLab) builder.

## From `setup.md`

### `setup.md` lines 75-175 — §12 intro, 12.1, 12.3, 12.4 (the whole environment cluster: lingo prefix, timings on both targets, the lingo fix and fsq note, the rhombus jobs)

````markdown
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
````

## From `libgap.md`

### `libgap.md` lines 5-31 — §12.2 (the `/home/roey/miniforge3` path; 'WSL and lingo')

````markdown
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
````

### `libgap.md` lines 225-242 — §12.7 intro (lingo re-probe; findings files in FlatSurfLab/scratch; the two-copies record and backup path)

````markdown
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
````

### `libgap.md` lines 333-364 — §12.7.5 (import topology and timing on lingo; `-Prefix /data/roeyzemmel/miniforge3`; fslab.christoffel on lingo)

````markdown
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
````

### `libgap.md` lines 378-381 — §12.7.6 probe location and VPN-down note

````markdown
Probe: `FlatSurfLab/scratch/probe_repaction_convention.py`, run via
`scripts\run.ps1 scratch\probe_repaction_convention.py` (WSL, SageMath 10.7 /
sage-flatsurf 0.8.0 / surface_dynamics 0.7.0). **Lingo side not run this dispatch —
VPN down (`scripts\vpn.ps1` → "vpn: down (Ethernet 4: Disabled)"); unconfirmed there.**
````

### `libgap.md` lines 612-619 — §12.8 provenance (probe scripts, the canonical-copy path under C:\Users\Galit)

````markdown
Probed against **sage-flatsurf 0.8.0 / surface_dynamics 0.7.0 / SageMath 10.7**, WSL,
2026-09-20. Probe scripts: `FlatSurfLab/scratch/probe_gap_funcdef.py` (the isolated
`function_factory` characterisation and the Q8 known-answer case) and
`FlatSurfLab/scratch/probe_gap_funcdef2.py` (re-run against the unmodified `_BFS_GAP` /
`_COVER_GAP` production strings). Opened the canonical copy of this file at
`C:\Users\Galit\.claude\skills\flatsurf-computation\references\api-recipes.md` per
Roey's 2026-09-20 designation (2225 lines before this section, §§1-12 including 12.7); did
not open the stale `~/.claude/skills/synced/` copy.
````

## From `INDEX.md`

### `INDEX.md` lines 24-32 — 'One copy' and 'Writing' (skills paths, synced copy, writer agents)

````markdown
**One copy.** This directory is in git (`claude-flatsurf/domain/flatsurf-computation`),
reached through `~/.claude/skills/flatsurf-computation`. The claude.ai-synced copy under
`~/.claude/skills/synced/` is obsolete (a strict subset; its §6 ends at 6.6 and it has
no §12); the "two copies" warning in §12.7 is historical.

**Writing.** A new finding goes in the topic file it belongs to, as the next number in
that file's section (e.g. `### 6.8`, `#### 12.7.7`), never a new top-level file without
a row here. A refutation goes beside the entry it refutes. Writers: `flatsurf:api-prober`,
`/flatsurf:api-check`.
````

## From `quick-reference.md`

### `quick-reference.md` lines 28-28 — the pyflatsurf row (`scripts/run.sh`, 'Fixed on lingo and WSL')

````markdown
| `import pyflatsurf`, `canonicalize()`, `GL2ROrbitClosure` in an env reached by `PATH` only | a full `conda activate` (what `scripts/run.sh` does since 2026-09-22) | segfault in cling's `AddHostArguments` otherwise; also keep `gxx`/`gcc` at 14 (cling cannot parse gcc-16 headers). Fixed on lingo and WSL 2026-09-22; see 12.4 |
````

## From `origamis.md`

### `origamis.md` lines 468-468 — §12.5 heading ('WSL and lingo')

````markdown
### 12.5 `Origami` constructor forms and index base — **Confirmed** (WSL and lingo)
````

### `origamis.md` lines 457-459 — the `fslab/vh.py` pointer

````markdown
- Anything keyed on **square indices** (a marked pair of squares, a tracked cone-point corner)
  must be re-identified after every twist, or applied one generator at a time with the labels
  transported explicitly (`fslab/vh.py`).
````
