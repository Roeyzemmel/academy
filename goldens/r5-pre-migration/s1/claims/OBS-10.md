---
id: OBS-10
aliases: [N19, M4]
title: "Pillowcase criterion: illuminating δ^(2s)x via corner-monodromy pair sums"
summary: "If M/⟨δ⟩ (Dδ = −I) is the pillowcase and ⟨δ⟩ is free off Σ*, x illuminates δ^(2s)x only if 2s ∈ ⟨d_a+d_b⟩ for the pairing fixed by the direction's parity; converse off a finite set."
kind: prop
status: Proved
topics: [obstructions, pillowcase-covers]
depends_on: []
source: notes/03-q2/families-hunt.md:748-788
added: 2026-09-24
---

## Statement

### N19 (Proved) — pillowcase criterion, general form

**N19.** Let $M$ be a translation surface and $\delta\in\mathrm{Aff}(M)$ with $D\delta=-I$,
order $N$. Assume $Q_0=M/\langle\delta\rangle$ is the pillowcase $E_0/\langle-I\rangle$,
$E_0=\mathbb R^2/2\mathbb Z^2$, with corners $c_1,\dots,c_4$ the images of $\mathbb Z^2$, and
that $\langle\delta\rangle$ acts freely off $\Sigma^*:=q^{-1}\{c_a\}$. **This freeness
hypothesis is kept and is not redundant**: a translation $\delta^{2k}$ can fix a cone point
of $M$ lying over a regular point of $Q_0$. Let $d_a\in\mathbb Z/N$ be the corner
monodromies (a small anticlockwise loop around $c_a$ lifts from $x$ to $\delta^{d_a}x$).
Directions are primitive $(q,p)\in\mathbb Z^2$ relative to this pillowcase lattice; their
**parity classes** are the three nonzero classes of $(q,p)\bmod2$. Then, for
$x\in M\setminus\Sigma^*$, $s\in\mathbb Z/N$:
$$x\ \text{illuminates}\ \delta^{2s}x\ \Longrightarrow\ 2s\in\bigcup_{\{a,b\}\sqcup\{c,d\}}\langle d_a+d_b\rangle,$$
the union over the three pairings of the four corners. **Class-by-class form** (what the
proof actually gives): if the segment has direction of parity class $\epsilon$, then
$2s\in\langle d_a+d_b\rangle$ for the pairing $\pi(\epsilon)$ that $\epsilon$ induces (each
corner paired with its translate by $\epsilon$ mod 2); the displayed union is the union of
these three class-by-class statements.

**Converse.** Let $\pi$ be a pairing, $\epsilon$ its inducing class, $\{a,b\}\in\pi$ with
$2s\in\langle d_a+d_b\rangle$. Then every $x\in M\setminus\Sigma^*$ whose image in $E_0$ lies
outside the **finite** exceptional set
$$X_\epsilon=\{y\in(\tfrac12\mathbb Z^2\setminus\mathbb Z^2)/2\mathbb Z^2:\ \text{every direction of class }\epsilon\text{ through }y\text{ meets }\mathbb Z^2\}$$
illuminates $\delta^{2s}x$ — explicitly $X_{(1,0)}$ = horizontal-edge midpoints,
$X_{(0,1)}$ = vertical-edge midpoints, $X_{(1,1)}$ = square centres (mod $\mathbb Z^2$); the
corners are excluded by definition (they lie in $\Sigma^*$).

## Proof

*Proof sketch.* $\rho:\pi_1(Q_0\setminus\{c_a\})\to\mathbb Z/N$ factors through $H_1$; a
segment from $x$ to $\delta^{2s}x$ projects to a closed geodesic loop of $E_0=M/\langle
\delta^2\rangle$ through a lift $y$ (the case $-y$, reversed direction, is excluded since a
translate cannot produce it), which on the pillowcase is $k$ turns of a simple closed core
separating one corner-pair from the other, homologous to $\ell_a+\ell_b$, giving
$\rho(\text{core})=\pm(d_a+d_b)$ and $2s=k\rho$; the pairing is fixed by the direction's
parity class. The converse follows from the elementary fact that the line through
$y\in\mathbb R^2$ in direction $(q,p)$ meets $\mathbb Z^2$ iff $py_1-qy_2\in\mathbb Z$
($\gcd(q,p)=1$), checked on two directions of determinant $\pm2$ per class.

*Cleared by.* Two `claim-verifier` runs, both Proved, no inputs, sequential, both on
`claude-opus-5-5`; see `computation/verdicts.md`, entry "2026-09-24 — M2–M5
(writing/n8-quotient-mechanism.md), after repair → N17–N20". Source:
`writing/n8-quotient-mechanism.md` §4 (M4), in the repaired class-by-class form.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:748-788 (relabel map).
