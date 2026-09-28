---
id: CEX-2
aliases: [N9, "[N8p] Thm A", "[N8p] Thm B", "[N8p] Cor 5.1", "[N8p] Prop 1.3"]
title: "Enumeration-free certificate for the two M_12 counterexamples"
summary: "Christoffel values never lie in ker ψ, so a C^pow element realising T^{±1} is an even power g², g ∉ ker ψ; their column shifts are non-units of Z/6, so gr(T^{±1}) misses R^pow, at every base point."
kind: prop
status: Proved
topics: [counterexamples, obstructions, base-point]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [GEO-29, GEO-26]
cites: [EMM15, SW08]
source: notes/03-q2/families-hunt.md:316-352
added: 2026-09-24
---

## Statement

## [2026-09-23] N9 (Proved) — an enumeration-free certificate for N8

**N9.** Strengthens N8's certificate for both cyclic-cover members at $N=12$, without
appealing to any enumeration of $W$. Writing each square as $i=4m+j$ ($m\in\mathbb Z/6$,
$j\in V=\{0,1,2,3\}$), let $T:i\mapsto i+4$ be the central translation (the square of the FMZ
deck generator $\delta$) and let $\psi:G\to V_4=\{\mathrm{id},\pi_r,\pi_u,\pi_r\pi_u\}$ be the
column-parity homomorphism ($\psi(\sigma)=\pi_r$, $\psi(\tau)=\pi_u$). Every Christoffel
value, in every sign quadrant and every rotation, has $\psi(u)\ne\mathrm{id}$, so an odd power
of a $G$-conjugate of $u$ never has trivial $\psi$-image, while $T^{\pm1}$ does. Hence any
element of $C^{\mathrm{pow}}$ realising $T^{\pm1}$ must be an **even** power $g^2$ of some
$g\notin\ker\psi$. Condition **(NU)** — for every such $g$, the column-shift $h_g$ takes only
non-unit values in $\mathbb Z/6$ — checked by hand for both members, then forces
$\mathrm{gr}(T)\cup\mathrm{gr}(T^{-1})$ disjoint from $R^{\mathrm{pow}}$.

- For $M_{12}(1,5,7,11)$: $C^{\mathrm{pow}} = G\setminus\{E_1^{\pm1}\}$ exactly, reached
  already at direction size $|p|+|q|\le2$; $E_1$ is not a square because $G$'s maximal
  element order is 6.
- For $M_{12}(1,3,3,5)$: $\mathrm{gr}(T^{\pm1})\cap R^{\mathrm{pow}}=\varnothing$ **without
  enumerating $W$** — this replaces N8's member-1 certificate, which relied on the computed
  cycle types ($4^6$ or $6^4$) of the complete 36-element value set.
- **Corollary 5.1.** For **every** base point $z\in(0,1)^2$, torsion or not, and every $i$:
  $x_i(z)$ never illuminates $x_{i\pm4}(z)$. This follows from $I_z\subseteq R_W\subseteq
  R^{\mathrm{pow}}$ (R2 Lemma 2.1(a) / R Prop. 4.1, Proved) and the two facts above.
- The reading of "(Q2) fails" as failure of mutual illumination on a generic fibre, and the
  positive half of illumination for member 2 (at non-torsion $z_0$, $x_i(z_0)$ illuminates
  $x_j(z_0)$ iff $j\notin\{i\pm4\}$), stay **Proved modulo** EMM Thm 2.1 and Smillie–Weiss,
  via R2 Thm 2.2 — unchanged from that item's own recorded status.

*Cleared by.* Two `claim-verifier` runs on the primary model (Fable 5.1), sequential, both
returning Proved/CONFIRMED on 2026-09-23 (Theorems A and B, and for run B also Cor. 5.1); see
`computation/verdicts.md`, entry "N8 conceptual certificate (writing/n8-counterexample-proof.md)".
Source: `writing/n8-counterexample-proof.md`.

*Relation to N8.* N8 stands, unchanged — it is not superseded. N9 strengthens N8's
certificate: member 2's argument was already conceptual (via the $G/C_3\cong D_4$ route);
N9 replaces member 1's enumeration-dependent cycle-type argument with an enumeration-free
one, and adds Corollary 5.1 as an unconditional (every-base-point) consequence.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:316-352 (relabel map).
