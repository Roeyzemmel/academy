# The geometric dictionary and base-point independence

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

Why (Q2) is an illumination question: cutting sequences, conjugation as free homotopy, the marked-point convention (R §4), and the slope‑1 orbit-closure argument that makes the illumination relation on a non-torsion fibre equal to $R^{\mathrm{pow}}$ (R2 §2.1).

---

## [R §4] The dictionary: what (Q2) means geometrically

Fix $z_0$ in the interior of the unit square of $\mathbb{T}^2$. The fibre
$F_{z_0} \subset M$ has $n$ points, one per square, so $F_{z_0} \leftrightarrow \Omega$,
and $\pi_1(\mathbb{T}^2\setminus\{0\},z_0) = F_2$ acts by monodromy with
$\pi(x) = \sigma$, $\pi(y) = \tau$ (the horizontal and vertical closed geodesics
through $z_0$).

> **→ [GEO-26](../../claims/GEO-26.md)** (R Prop 4.1) — moved to its own file, 2026-09-24.

> **→ [GEO-27](../../claims/GEO-27.md)** (R Prop 4.2) — moved to its own file, 2026-09-24.

> **→ [GEO-28](../../claims/GEO-28.md)** (R Prop 4.3) — moved to its own file, 2026-09-24.

**Marked-point convention (recorded deliberately).** The word formalism lives in
$\pi_1(\mathbb{T}^2\setminus\{0\})$, so trajectories avoid **all** of
$\pi^{-1}(0)$, including preimages of cone angle $2\pi$. The algebra therefore
computes illumination on $M$ regarded in $\mathcal{H}(k_1,\dots,k_r,0^s)$ with
every square corner marked. Since marking more points removes trajectories, a
**positive** answer here implies the corresponding statement after forgetting
marked points; a counterexample does not transfer downward. This is the
conservative direction, and it is the correct convention for billiard and
half-translation unfoldings, where corner-derived marked points are genuinely
present.

---

## [R2 §2] The geometric bridge


---

## [R2 §2.1] The geometric question is $R^{\mathrm{pow}}$ (level (A0))

$M$ = the origami of $(\sigma,\tau)$ with **all** corners marked ($\Sigma^*=p^{-1}(0)$),
strata $\mathcal H^*,\mathcal H^*_1,\mathcal H^*_2$ (0, 1, 2 extra marked points). Fibres are
trivialised over the open unit square: $x_i(z)$, $z\in(0,1)^2$. "$x$ illuminates $y$": a
straight segment whose interior avoids $\Sigma^*$. $I_z=\{(i,j):x_i(z)\text{ illuminates }x_j(z)\}$.

**Inputs.** (A) Eskin–Mirzakhani–Mohammadi Thm 2.1: orbit closures in strata (marked points
allowed) are affine invariant submanifolds — closed, invariant, locally finite unions of
complex linear subspaces, of complex dimension $\ge2$. (B) Smillie–Weiss (x): closed
$\mathrm{GL}(2,\mathbb R)$-orbit iff lattice stabiliser. (C) Elementary: illumination is an
open invariant condition in $\mathcal H^*_2$ (a segment avoiding the finite marked set by a
positive margin persists under small changes of period coordinates).

> **→ [GEO-29](../../claims/GEO-29.md)** (R2 Lemma 2.1) — moved to its own file, 2026-09-24.

> **→ [GEO-30](../../claims/GEO-30.md)** (R2 Thm 2.2, R §7 open item 6) — moved to its own file, 2026-09-24.
