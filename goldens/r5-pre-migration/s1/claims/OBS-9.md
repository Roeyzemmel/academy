---
id: OBS-9
aliases: [N18, M3]
title: "Monodromy form of the M_12 certificate over the torus M/⟨T⟩"
summary: "M∖Σ* → E∖V, E = M/⟨T⟩ = R²/2Z², is a Z/6 cover; a segment from x to T^s x projects to k turns of a closed geodesic c with s = kφ(c), so x lights T^{±1}x only if some core has φ(c) a unit."
kind: prop
status: Proved
topics: [obstructions, quotients]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [CEX-2]
source: notes/03-q2/families-hunt.md:720-746
added: 2026-09-24
---

## Statement

### N18 (Proved) — monodromy form of [N8p]'s Prop. 1.3

**N18.** Let $E=M/\langle T\rangle$ and $V=q(\Sigma^*)$. Then $E$ is the torus
$\mathbb R^2/2\mathbb Z^2$, $V=\mathbb Z^2/2\mathbb Z^2$, and $M\setminus\Sigma^*\to
E\setminus V$ is a regular unbranched cover with deck group $\langle T\rangle\cong\mathbb Z/6$.
Let $\varphi:\pi_1(E\setminus V)\to\mathbb Z/6$ be its monodromy, so a loop $\gamma$ lifts
from $x$ to $T^{\varphi(\gamma)}x$. Then:

1. For $x\in M\setminus\Sigma^*$ and $s\in\mathbb Z/6$, every straight segment of $M$ from $x$
   to $T^sx$ with interior off $\Sigma^*$ projects to $k\cdot c$, $c$ the closed geodesic of
   $E$ through $q(x)$ in some rational direction, $k\ne0$; its endpoint gives $s=k\varphi(c)$.
2. Let $c$ be the closed geodesic of $E$ in direction $(q,p)$ through $q(x)$, $x$ in column
   $j$, $c$ avoiding $V$. Let $u\in G$ be the traversal-order-lift word (a rotation of the
   Christoffel word fixed by the intercept) of the closed geodesic of the unit torus through
   the image of $x$ in that direction. Then $\varphi(c)=h_u(j)$, $h_u=c_{u^2}$ (N9/N12's
   column shift). $\varphi(c)$ is **not** a function of direction and column alone — the two
   cylinders of $E$ in one direction can give different values (e.g. direction $(1,1)$
   through column 0 gives $\varphi=2$ in one cylinder and $4$ in the other) — but the set of
   values over all cores is still constrained by [N8p] Lemma 3.2 / §2.3, since every such $u$
   lies outside $\ker\psi$.
3. **Hence** $x$ illuminates $T^{\pm1}x$ only if some core has $\varphi(c)$ a unit of
   $\mathbb Z/6$.

*Cleared by.* Two `claim-verifier` runs, both Proved, no inputs beyond [N8p] Lemmas 1.1, 1.2,
3.2 = N9 (Proved), sequential, both on `claude-opus-5-5`; see `computation/verdicts.md`,
entry "2026-09-24 — M2–M5 (writing/n8-quotient-mechanism.md), after repair → N17–N20".
Source: `writing/n8-quotient-mechanism.md` §4 (M3).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:720-746 (relabel map).
