---
id: GEO-30
aliases: [R2 Thm 2.2, R §7 open item 6]
title: "Illumination on a non-torsion fibre equals R^pow (via EMM)"
summary: "For non-torsion z_0, illumination on the fibre equals R^pow, so (Q2) ⇔ the n points of one generic fibre illuminate each other; needs only OA-0; fails at torsion points"
kind: thm
status: Proved modulo stated inputs
status_note: modulo EMM Thm 2.1, Smillie–Weiss
level: OA-0
topics: [dictionary, base-point, questions]
examples: [EX-D4]
depends_on: [GEO-29]
cites: [EMM15, SW08]
source: notes/01-geometry/dictionary.md:107-127; OPEN.md:88-91
added: 2026-09-24
---

## Statement

<!-- verbatim from notes/01-geometry/dictionary.md:107-127 (HEAD 2026-09-24) -->
**Theorem 2.2 (base-point independence; Proved modulo (A),(B)).** Let $z_0\in(0,1)^2$ be
non-torsion and $i\ne j$. The following are equivalent: (1) $(i,j)\in I_{z_0}$; (2) $(i,j)\in R_W$;
(3) $(i,j)\in R^{\mathrm{pow}}$; (4) $x_{hi}(z)$ illuminates $x_{hj}(z)$ for some $h\in G$,
$z\in(0,1)^2$. Hence $I_{z_0}=R_W=R^{\mathrm{pow}}$ for every non-torsion $z_0$, the illumination
relation on a generic fibre is base-point independent and $G^+$-saturated, and **(Q2) is
equivalent to the mutual illumination of the $n$ points of one non-torsion fibre.**

## Proof

*Proof.* (1)⇒(2)⇒(3): Lemma 2.1(a). (3)⇒(4): $j=hu^mh^{-1}i$; the word of $u$ is the cutting
sequence on an open set of $z$, where the trajectory of holonomy $m(\pm q,\pm p)$ from
$x_{h^{-1}i}(z)$ ends at $x_{h^{-1}j}(z)$. (4)⇒(1): the slope‑1 locus
$S=\{(gM,gx,gy):x\ne y,\ p(x)=p(y)\}\subset\mathcal H^*_2$ is closed, invariant, locally linear
(the condition is $\int_x^y\omega\in\mathbb Q\text{-span of two periods}$), of complex
dimension 3, and its forgetful map to $L_1$ is a covering of degree $n-1$; its component
through $(M,x_i(z),x_j(z))$ contains all $(M,x_{hi}(z'),x_{hj}(z'))$. If (1) fails, by (C) the
orbit closure $N$ of $(M,x_i(z_0),x_j(z_0))$ consists of non-illuminating triples; $N\subseteq S$,
its forgetful image is closed and contains $L_1$ (Lemma 2.1(c)), so $\dim N=3$ and $N$
contains the whole component, contradicting (4). $\square$

*Remarks.* Torsion base points are different ($D_4$ origami at $z=(1/50,1/2)$ misses eight
pairs for all $|p|+|q|\le24$); any $K$-statement is about $R^{\mathrm{pow}}$. No hypothesis
beyond (A0). **From here on (Q2) means $R^{\mathrm{pow}}=\Omega^{(2)}$.**

<!-- verbatim from OPEN.md:88-91 (HEAD 2026-09-24) -->
6. The orbit-closure / "slope 1" argument justifying the passage from the
   transport class back to a fixed $z_0$. Needs the orbit closure of $(M,x,y)$
   identified and non-illumination shown to be preserved along it; the possible
   slopes are listed as open in LMW §6.4.

## Notes

The inputs **(A)**, **(B)**, **(C)** are stated in the R2 §2.1 "Inputs" paragraph, which stays on the topic page
[notes/01-geometry/dictionary.md](../notes/01-geometry/dictionary.md): (A) EMM15 Thm 2.1, (B) SW08 (x),
(C) illumination is open and invariant. **Open point (2026-09-24):** (A) is quoted there with "marked points
allowed", but the `../papers/EMM15.meta` scope note says EMM as written covers strata with no marked points.
Neither this item nor its source justifies the extension (e.g. via AW21). Tracked as OPEN-13, parked by Roey on 2026-09-24:
many papers assume the extension, and it will be checked later. No status change until then.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/dictionary.md:107-127; OPEN.md:88-91 (relabel map).
- 2026-09-24: Notes added: pointer to inputs (A)–(C) and the EMM marked-points open point (no status change).
