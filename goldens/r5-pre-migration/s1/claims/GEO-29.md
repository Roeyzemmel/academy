---
id: GEO-29
aliases: [R2 Lemma 2.1]
title: "Illumination ⊆ R_W ⊆ R^pow; non-torsion one-point orbit closures are full"
summary: "I_z ⊆ R_W ⊆ R^pow with R_W the union of the I_z; affine maps cover z ↦ Dz; for non-torsion z the orbit closure of (M, x_i(z)) is the whole one-point locus (EMM, Smillie–Weiss)"
kind: lemma
status: Proved
topics: [dictionary, base-point]
depends_on: [GEO-26]
cites: [EMM15, SW08]
source: notes/01-geometry/dictionary.md:90-105
added: 2026-09-24
---

## Statement

**Lemma 2.1 (Proved).** (a) $I_z\subseteq R_W\subseteq R^{\mathrm{pow}}$ for all $z\in(0,1)^2$ and
$R_W=\bigcup_zI_z$ (R Prop. 4.1: an illuminating segment has holonomy $m(q,p)$ and is the
$m$-th power of the cutting sequence at $z$, a rotation of $w_{p,q}$; each rotation occurs on
an open set of $z$). (b) The stabiliser $V^*$ of $(M,\Sigma^*)$ has finite index in
$\mathrm{SL}(2,\mathbb Z)$ and every affine automorphism $f$ of $(M,\Sigma^*)$ covers
$z\mapsto Df\cdot z$ on $\mathbb T^2$. (c) For $z$ non-torsion, the orbit closure of
$(M,x_i(z))$ in $\mathcal H^*_1$ is the full one-point locus $L_1$ over the Teichmüller curve.

## Proof

*Proof of (c).* $L_1$ is closed, invariant, connected, locally linear of complex dimension 3;
the orbit closure $N\subseteq L_1$ has dimension 2 or 3 (A). If 2, orbits are open in $N$
(immersion of equal dimension) so $N$ is one closed orbit and by (B) the stabiliser of
$(M,x)$ is a lattice inside the lattice $V^*$, hence of finite index; via the derivative map
(finite kernel, trivial on the stabiliser of $x$) the $\mathrm{Aff}^*$-orbit of $x$ is finite,
but by (b) it projects onto a $V^*$-orbit of $z$, infinite for non-torsion $z$ (use
$\begin{pmatrix}1&0\\N&1\end{pmatrix}^k$ or $\begin{pmatrix}1&N\\0&1\end{pmatrix}^k$). So
$\dim N=3$ and $N$ is open and closed in $L_1$. $\square$

## Notes

The inputs **(A)**, **(B)**, **(C)** are stated in the R2 §2.1 "Inputs" paragraph, which stays on the topic page
[notes/01-geometry/dictionary.md](../notes/01-geometry/dictionary.md): (A) EMM15 Thm 2.1, (B) SW08 (x),
(C) illumination is open and invariant. **Open point (2026-09-24):** (A) is quoted there with "marked points
allowed", but the `../papers/EMM15.meta` scope note says EMM as written covers strata with no marked points.
Neither this item nor its source justifies the extension (e.g. via AW21). Tracked as OPEN-13, parked by Roey on 2026-09-24:
many papers assume the extension, and it will be checked later. No status change until then.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/dictionary.md:90-105 (relabel map).
- 2026-09-24: Notes added: pointer to inputs (A)–(C) and the EMM marked-points open point (no status change).
