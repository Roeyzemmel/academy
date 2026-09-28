---
id: CEX-4
aliases: [N23, G9]
title: "O_16^b: second 16-square counterexample, not in O_16^a's SL(2,Z)-orbit"
summary: "Column form over (Z/2)² with σ an involution: (Q2) fails on gr(T_e) by OBS-4; OA-3 via explicit μ,ν; G ≅ (Z/4×Z/2)⋊Z/2 has an involution outside its Frattini subgroup, so G ≇ Z/4⋊Z/4."
kind: prop
status: Proved
level: OA-3
topics: [counterexamples, pillowcase-covers]
examples: [EX-O16b, EX-O16a]
depends_on: [OBS-4, OBS-2, OBS-1, CEX-3]
source: notes/03-q2/families-hunt.md:947-996
added: 2026-09-24
---

## Statement

### N23 (Proved) — $O_{16}^{b}$: column form over $A=(\mathbb Z/2)^2$ with $\sigma$ an involution

**N23.** Write $A=\{0,e,f,e+f\}$, encoded (the only one of the six encodings reproducing both
tuples below) as $m\in\{0,1,2,3\}$ with XOR ($e\mapsto1$, $f\mapsto2$), and label squares
$4m+j$. Take
$$\sigma=[(0,0,e,e),\ \pi_r],\qquad \tau=[(0,0,f,f),\ \pi_u],$$
tuples `r = (1,0,7,6,5,4,3,2,9,8,15,14,13,12,11,10)`,
`u = (3,2,9,8,7,6,13,12,11,10,1,0,15,14,5,4)`.

**(Q2) fails for $O_{16}^{b}$**, on the orbital $\mathrm{gr}(T_e)$, e.g. the pair $(0,4)$ — an
unmet orbital, not claimed to be the only one here. Here $c_{\sigma^2}=0$, $c_{\tau^2}=(f,f,f,f)$
and $c_{(\sigma\tau)^2}=(e+f,e+f,e+f,e+f)$ are constant, so $L_K$ is the constants, $|G|=16$, $G$
is regular, $\sigma^2=1$, and $S=\{0,f,e+f\}$; by N15 (G4) with $t=e$, $t\notin\langle
S\rangle$. **Level (A3)**, with $\mu=T_f$ (i.e. $s\mapsto s\oplus8$) and
$\nu=[(e,e,e+f,e+f),\mathrm{id}]$: constant maps commute with column-form maps and
$\sigma=\sigma^{-1}$, so $\mu$ works; $\nu\sigma\nu=\sigma$ since $d=d\circ\pi_r$ for
$d=(e,e,e+f,e+f)$, and $\nu\tau\nu=[(f,f,0,0),\pi_u]=\tau^{-1}$. $\mu$, $\nu$ lie in the
elementary abelian 2-group $\{[c,\mathrm{id}]\}$, so $\mu^2=\nu^2=1$ and $\mu\nu=\nu\mu$, and
$1,\mu,\nu,\mu\nu$ are distinct; all three of $\mu,\nu,\mu\nu$ have only nonzero entries, so
they are free.

**Group structure.** With $G_0:=K=\{T_0,T_e,T_f,T_{e+f}\}=\ker\psi=\Phi(G)$ (Frattini
subgroup, renamed to avoid the (A3) $\Phi$), and $\sigma=\sigma^{-1}$ with constants central,
$$z:=[\sigma,\tau]=(\sigma\tau)^2\tau^{-2}=T_{e+f}T_f=T_e.$$
$G=\langle\sigma,\tau\mid\sigma^2,\tau^4,\ z=[\sigma,\tau]\text{ central of order }2\rangle
\cong(\mathbb Z/4\times\mathbb Z/2)\rtimes\mathbb Z/2$ (order count: the quotient by
$\langle z\rangle$ already has order $\le8$ and $\cong\mathbb Z/2\times\mathbb Z/4$, and the
presented relations hold in $G$, giving an isomorphism with the order-16 group $G$; the
semidirect form comes from $N=\langle\tau,z\rangle\cong\mathbb Z/4\times\mathbb Z/2$ normal of
index 2, $\sigma\notin N$, $\sigma^2=1$, $\sigma\tau\sigma^{-1}=z\tau$). **$G\not\cong
\mathbb Z/4\rtimes\mathbb Z/4$**: $G$ has an involution outside $G_0$ ($\sigma$), while every
involution of $\mathbb Z/4\rtimes\mathbb Z/4$ lies in its Frattini subgroup (by N22's square
formula, $a^ib^j$ outside $\langle a^2,b^2\rangle$ squares to $b^2$ or $a^2$, never to 1). The
monodromy group is an $\mathrm{SL}(2,\mathbb Z)$-invariant up to isomorphism (the action
replaces $(\sigma,\tau)$ by a new basis of $F_2$, generating the same group), so **$O_{16}^{b}$
is not in the $\mathrm{SL}(2,\mathbb Z)$-orbit of $O_{16}^{a}$**. Here $X(G)=\{z\}$: by N13(b)
the squares of elements outside $G_0=\Phi(G)$ are the $T_s$, $s\in S=\{0,f,e+f\}$, so
$X(G)=G_0\setminus\{1,T_f,T_{e+f}\}=\{T_e\}=\{z\}$; by N22's argument ($\ker\psi=\Phi(G)$ for
every generating pair of a 2-generated 2-group), **every normal origami with this group fails
(Q2)**.

*Cleared by.* Two `claim-verifier` runs, both Proved, CONFIRMED, sequential, both on
`claude-opus-5-5`: run A with inputs "none (N13, N12 Proved)"; run B with inputs "none (N12,
N13 Proved; N10 Proved only for the preamble's 'not (A4)')". See `computation/verdicts.md`,
entry "2026-09-24 — G9 (writing/n8-generalization.md) → N23". Source:
`writing/n8-generalization.md` §4.2 (G9 box, the encoding line, the (A3) proof with
$\mu^2=\nu^2=1$, $\mu\nu=\nu\mu$, and the "Group structure" paragraph).

*Not claimed here.* Uniqueness of $\mathrm{gr}(T_e)$ as the unmet orbital, and Remark (U) on
the classification of groups of order 16, both stay outside this item (per the verdict).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:947-996 (relabel map).
