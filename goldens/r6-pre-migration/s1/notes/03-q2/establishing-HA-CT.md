# How to establish (HA) and (CT)

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

---

## [R2 §5] Establishing (HA)


---

## [R2 §5.1] Tools from the literature

* **Jordan** (Jones 2014, Thm 1.1/Cor. 1.3): a primitive group of degree $m$ containing a
  cycle fixing $\ge3$ points contains $A_m$; so primitive + a $3$-cycle ($m\ge6$; $m=4,5$
  by inspection) ⇒ $\supseteq A_m$; primitive + a transposition ⇒ $S_m$.
* **Jones's classification** (ibid., Thm 1.2) of primitive groups $\not\supseteq A_m$ containing a
  cycle fixing $\le2$ points: affine, $PGL_d(q)\le G\le P\Gamma L_d(q)$, $L_2(11)$, $M_{11},M_{12},M_{23},M_{24}$,
  $L_2(p)$, $PGL_2(p)$, $PGL_2(q)\le G\le P\Gamma L_2(q)$. Relevant under (RD5) with long odd
  corners ($5\pi/2,\dots$).
* **Liebeck–Saxl 1991** (via Maróti's survey, Thm 3.2): a primitive group either lies in the
  product-action family $(A_{m'})^r\le G\le S_{m'}\wr S_r$ on $k$-subsets, or all its nontrivial
  elements move $\ge m/3$ points. A small-support element therefore forces the product-action
  family, which contains $A_m,S_m$ but also e.g. $S_{m'}$ on 2‑subsets — insufficient alone.

---

## [R2 §5.2] Corner rotations (Proved)

Under (RD6): $\rho_{XY}$ acts on a path-orbit of length $\ell$ as an $\ell$-cycle and on a
$4$-cycle-orbit as a double transposition, so $\rho_{XY}^6=1$ and
$$c_{XY}:=\rho_{XY}^{2}=\prod_{\text{reflex vertices of type }XY}(3\text{-cycle}),\qquad
\rho_{XY}^{3}=\prod_{\pi\text{-vertices of type }XY}(\text{transposition})\cdot\prod_{\text{interior vertices of type }XY}(\text{double transposition}).$$
Under (RD5) with path-orbits of odd prime length $\ell$ of type $XY$, $\rho_{XY}^{N}$ with
$N$ the lcm of the other orbit lengths of $\rho_{XY}$ (prime to $\ell$ when $\ell$ does not
divide them) is a product of $\ell$-cycles — the input for Jones's list.

> **→ [CRIT-19](../../claims/CRIT-19.md)** (R2 Prop 5.1) — moved to its own file, 2026-09-24.

---

## [R2 §5.3] Primitivity (Partial)

> **→ [OPEN-4](../../claims/OPEN-4.md)** (R2 Open 5.B, R2 §5.3) — moved to its own file, 2026-09-24.

> **→ [OPEN-3](../../claims/OPEN-3.md)** (R2 Open 5.A) — moved to its own file, 2026-09-24.

---

## [R2 §6] Establishing (CT)

> **→ [CRIT-20](../../claims/CRIT-20.md)** (R2 Prop 6.1) — moved to its own file, 2026-09-24.

> **→ [OPEN-5](../../claims/OPEN-5.md)** (R2 Open 6.A) — moved to its own file, 2026-09-24.
