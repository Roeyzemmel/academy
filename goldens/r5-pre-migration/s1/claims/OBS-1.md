---
id: OBS-1
aliases: [N12, G1]
title: "Parity–translation obstruction: a fibre-preserving centralising T can be unmet"
summary: "If G has a level-Λ′ fibration (Λ′ ⊆ pZ²) and a fibre-preserving centralising T ≠ 1 with Tx never in ⟨g^(d_g)⟩x for primitive-image g, then gr(T) misses R^pow and (Q2) fails."
kind: prop
status: Proved
topics: [obstructions, orbitals]
depends_on: []
source: notes/03-q2/families-hunt.md:419-468
added: 2026-09-24
---

## Statement

## [2026-09-24] N12 (Proved) — the parity–translation obstruction (generalises N8)

**Setting.** $\Omega$ is a finite set, $G=\langle\sigma,\tau\rangle$ transitive on $\Omega$,
and $p$ is a prime. $\Lambda'\subseteq p\mathbb Z^2$ is a full-rank lattice, and
$Q:=\mathbb Z^2/\Lambda'$. A map $\beta:\Omega\to Q$ is a **level-$\Lambda'$ fibration** if
$\beta(\sigma x)=\beta(x)+\bar e_1$ and $\beta(\tau x)=\beta(x)+\bar e_2$. Write
$\psi:G\to Q$ for the induced homomorphism, so $\psi(w(\sigma,\tau))=\overline{\mathrm{ab}(w)}$,
and for $g\in G$ let $d_g$ be the order of $\psi(g)$ in $Q$.

**N12 (Proved).** Let $T\in C_{S_\Omega}(G)$ with $T\ne1$ and $\beta\circ T=\beta$. Assume

**(NP$_T$)** for every $g\in G$ such that $\psi(g)$ is the image of a primitive vector of
$\mathbb Z^2$, and every $x\in\Omega$: $\ Tx\notin\langle g^{d_g}\rangle x$.

Then no $c\in C^{\mathrm{pow}}$ satisfies $cx=Tx$ for any $x$. So
$\mathrm{gr}(T)\cap R^{\mathrm{pow}}=\varnothing$. Since $\mathrm{gr}(T)$ is a single
$G$-orbital of off-diagonal pairs, **(Q2) fails**.

## Proof

*Proof.* Let $c=(huh^{-1})^k$ with $u$ a Christoffel value, $h\in G$ and $k\in\mathbb Z$, and
suppose $cx=Tx$. Put $x'=h^{-1}x$. Since $T$ commutes with $h$, $u^kx'=Tx'$. Apply $\beta$:
$k\,\overline{\mathrm{ab}(u)}=\beta(Tx')-\beta(x')=0$ in $Q$, so $d_u\mid k$. Hence
$Tx'=(u^{d_u})^{k/d_u}x'\in\langle u^{d_u}\rangle x'$. Here $\psi(u)$ is the image of the
primitive vector $\mathrm{ab}(u)$, so this contradicts (NP$_T$). $T\ne1$ commutes with a
transitive group, so it is fixed-point-free and the pairs $(x,Tx)$ are off-diagonal. The set
$\{(gx,Tgx)\}$ is all of $\mathrm{gr}(T)$ by transitivity. $\square$

**What is used.** The level-$\Lambda'$ fibration with $\Lambda'\subseteq p\mathbb Z^2$, and a
fibre-preserving centralising $T\ne1$ with (NP$_T$). Transitivity is used only to identify
$\mathrm{gr}(T)$ as one orbital; the fact that $\mathrm{gr}(T)\not\subset R^{\mathrm{pow}}$
does not need it.

**Remark (redundancy in the hypotheses).** $\Lambda'\subseteq p\mathbb Z^2$ and $T\ne1$ are
both implied by (NP$_T$) together with transitivity and $\beta\circ T=\beta$: if $\Lambda'$
contained a primitive vector, or $T=1$, (NP$_T$) would fail outright against that generator's
own translation. $T\in C(G)$ is needed only to identify $\mathrm{gr}(T)$ as a single
$G$-orbital, not for the non-membership argument itself.

**Special case ($p=2$, $\Lambda'=2\mathbb Z^2$).** Here $d_g=2$ for every $g\notin\ker\psi$,
and (NP$_T$) becomes "$Tx\notin\langle g^2\rangle x$ for every block-moving $g$". This
recovers N8's Prop. 1.3 as the conjunction **(NP$_T$) $\wedge$ (NP$_{T^{-1}}$)**. In the
normal case, in the right-regular model (squares = elements of $G$, $\sigma=\rho_a$,
$\tau=\rho_b$), the centraliser consists of the left multiplications $\lambda_E$ with
$E\in\ker\psi$, and (NP$_T$) for $T=\lambda_E$ reads: **$E\notin\langle g^{2}\rangle$ for
every $g\notin\ker\psi$** — "$E$ is not a power of the square of a block-moving element."

*Cleared by.* Two `claim-verifier` runs, both **Proved**, no inputs, sequential, both on
`claude-opus-5-5` (an equal primary with Fable 5.1 for clearing, Roey, 2026-09-24); see
`computation/verdicts.md`, entry "2026-09-24 — G1 → N12 (re-decided under the amended model
rule)". The label covers the boxed statement only. Source: `writing/n8-generalization.md`
§1 (G1).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:419-468 (relabel map).
