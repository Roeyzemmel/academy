---
id: BOUND-4
aliases: [N21, G7]
title: "The centraliser–fibration mechanism needs n≥16; sharp at OA-3"
summary: "If a fibration with Λ′⊆pZ² has a fibre-preserving centralising T≠1 with gr(T)⊄R^pow, then n≥16 at every level OA-0..OA-3; attained at OA-3 by O16^a (CEX-3)."
kind: prop
status: Proved
level: OA-0
topics: [bounds, obstructions, counterexamples]
examples: [EX-O16a]
depends_on: [OBS-1, OBS-2, CRIT-14, CEX-3]
source: notes/03-q2/families-hunt.md:884-941
added: 2026-09-24
---

## Statement

### N21 (Proved) — lower bound: the mechanism needs $n\ge16$, sharp

**N21.** Suppose $(\sigma,\tau)$ admits a level-$\Lambda'$ fibration with $\Lambda'\subseteq
p\mathbb Z^2$ (N12's setting) and a fibre-preserving $T\in C_{S_n}(G)\setminus\{1\}$ with
$\mathrm{gr}(T)\not\subseteq R^{\mathrm{pow}}$. Then:

**(i)** $n\ge16$, at **every** hypothesis level (A0)–(A3): no symmetry hypothesis is used in
the proof.

**(ii) Sharpness.** The bound is attained at level (A3), by $O_{16}^{a}$ = N22 (Proved).

## Proof

*Proof of (i).* $\psi:G\to Q$ is well defined and onto, and $G$ permutes the $|Q|$ fibres
transitively, so all fibres have a common size $f$ and $n=|Q|f$. $T\ne1$ centralises a
transitive group, so it is semiregular, and preserving fibres gives $\mathrm{ord}(T)\mid f$,
$f\ge2$. Since $|Q|$ is a multiple of $p^2$: if $|Q|\ge8$ then $n\ge16$ already; otherwise
$|Q|=4$ ($p=2$, $\Lambda'=2\mathbb Z^2$), and it remains to exclude $f\in\{2,3\}$. There $f$
is prime and $T$ acts on each fibre as an $f$-cycle; putting $G$ in column form over
$A=\mathbb Z/f$ (base points per fibre, $V\cong\mathbb Z^2/2\mathbb Z^2$ via N13(a)),
transitivity forces some entry $s=c_{u^2}(j)$ ($u\in\{\sigma,\tau,\sigma\tau\}$) to generate
$\mathbb Z/f$ (N13(a)), and then N13(d) gives $\mathrm{gr}(T)\subseteq R^{\mathrm{pow}}$, a
contradiction. (A short second proof: if $\sigma^2,\tau^2,(\sigma\tau)^2$ were all trivial
their normal closure $K$ would be trivial, forcing $|G|\le4<n$ against transitivity; so some
$u^2\ne1$ acts on some fibre as $T^k$, $k\not\equiv0\pmod f$, and inverting $k$ mod $f$ gives
$\mathrm{gr}(T)\subseteq R^{\mathrm{pow}}$ directly.)

**Remark (not separately verified as an item; argument given by both runs).** The prime-$f$
step never uses $f\le3$, so the mechanism is impossible whenever $n=4q$, $q$ prime
($n=8,12,20,28,44,\dots$): $|Q|$ is a multiple of $p^2$ dividing $4q$, forcing $|Q|=4$,
$f=q$ prime, which the step above excludes. Below 24 this leaves only $n=16$ (attained, N22)
and $n=18$ ($p=3$, $|Q|=9$, $f=2$; open, spec S5).

*Cleared by.* Two `claim-verifier` runs — part (i) Proved on both runs with no input; the
full item (with the attainment clause) Proved modulo G8/N22 on both runs; N22 has itself
cleared as **Proved** in the companion entry above, discharging N21's only stated input, so
**N21 → Proved**, in full including the attainment sentence; sequential, both on
`claude-opus-5-5`; see `computation/verdicts.md`, entry "2026-09-24 — G7
(writing/n8-generalization.md) → N21". Source: `writing/n8-generalization.md` §3 (G7).

**Consequence.** **(Q2) is refuted at level (A3) by a 16-square origami** ($O_{16}^{a}$,
N22), smaller than N8's 24-square members. It is **not (A4)** (N22, via N10), so nothing
changes at hypothesis levels (A4)–(A7): the parking-garage realisation problem (N3) stays
exactly as open as it was after N11.

**Not settled, explicitly.** $O_{16}^{b}$ and $O_{16}^{c}$ (`writing/n8-generalization.md`'s
G9, G10 — a second 16-square example realising the $|Q|=8,f=2$ branch, and a third lying in
the abelian pillowcase family) are **Not settled** and are not covered by N21 or N22. Whether
$p=3$, $n=18$ is realised (spec S5), and whether 16 is the minimum over **all** (Q2)
counterexamples rather than only this mechanism (spec S2), both stay open.

> Superseded by N23, N24 (Proved), 2026-09-24 — see the entries below. $O_{16}^{b}$ (G9) and
> $O_{16}^{c}$ (G10) have each cleared `/verify-claim` with two agreeing `claim-verifier` runs
> on `claude-opus-5-5`. **N23 (Proved):** $O_{16}^{b}$ is a genuine second 16-square
> counterexample at level (A3), and is **not** in the $\mathrm{SL}(2,\mathbb Z)$-orbit of
> $O_{16}^{a}$. **N24 (Proved):** $O_{16}^{c}$ also fails (Q2) at level (A3), but it is **in**
> the $\mathrm{SL}(2,\mathbb Z)$-orbit of $O_{16}^{a}$ (its transpose, via an explicit
> relabelling $\varphi$), so up to $\mathrm{SL}(2,\mathbb Z)$ the 16-square examples found so
> far are **two**, $O_{16}^{a}$ and $O_{16}^{b}$, not three. Spec S5 ($p=3$, $n=18$) and spec
> S2 (16 as the global minimum) remain open, untouched by this pass.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:884-941 (relabel map).
