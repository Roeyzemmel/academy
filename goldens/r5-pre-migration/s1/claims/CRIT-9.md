---
id: CRIT-9
aliases: [R Prop 5.7]
title: "Normal case: (Q2) ⇔ G is covered by conjugates of Christoffel cyclic subgroups"
summary: "For a normal origami, (Q2) ⇔ every g≠1 is conjugate to a power of a Christoffel value. Worked with x, y, xy for the EW, D4 and 2×1 rectangle (that row is wrong: BOUND-3)."
kind: prop
status: Proved
topics: [normal-case, q2-criteria]
examples: [EX-EW, EX-D4, EX-2x1]
depends_on: []
source: notes/03-q2/normal-case.md:17-36
added: 2026-09-24
---

## Statement

> **Proposition 5.7 (Proved).** For a normal origami,
> $$\text{(Q2)} \iff \text{every } g \in G\setminus\{1\} \text{ is conjugate to a power of a Christoffel value}
> \iff G = \bigcup_{u \in W}\bigcup_{\gamma\in G}\langle u\rangle^{\gamma}.$$

So (Q2) becomes: **cover $G$ by conjugates of cyclic subgroups whose generators
are Christoffel values.** The relevant literature is on *normal covering numbers*
of finite groups (Bubboloni–Praeger–Spiga). A sufficient condition: $W$ contains,
up to conjugacy, a generator of every maximal cyclic subgroup of $G$.

**Worked examples**, using only the three shortest Christoffel words $x$, $y$,
$xy$, i.e. the directions $(1,0)$, $(0,1)$, $(1,1)$:

| origami | $G$ | values of $x,y,xy$ | covering |
|---|---|---|---|
| Eierlegende Wollmilchsau | $Q_8$, $n=8$, $\mathcal{H}(1,1,1,1)$ | $i,\ j,\ ij=k$ | $\langle i\rangle\cup\langle j\rangle\cup\langle k\rangle = Q_8$ ✓ |
| $D_4$ regular | $\langle s,t\rangle$, $s,t$ reflections, $n=8$ | $s,\ t,\ st=r$ | $\langle r\rangle \cup s^{G}\cup t^{G} = D_4$ ✓ |
| $2\times1$ rectangle | $\mathbb{Z}/4\times\mathbb{Z}/2$, $n=8$ | $(1,0),(0,1),(1,1)$ | union is all of $G$ ✓ |

Two directions do **not** suffice for the EW: $\langle i\rangle\cup\langle j\rangle$
misses $\pm k$, so horizontal-plus-vertical fails and the diagonal is needed.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/normal-case.md:17-36 (relabel map).
