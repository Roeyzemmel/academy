---
id: GEO-8
aliases: [R Prop 1.5]
title: "Explicit monodromy of a garage unfolding on S(P)×K_4"
summary: "Under PA-4, σ and τ on S(P)×K_4 move to the neighbouring square in direction diag(a,b) across interior edges and flip the K_4 sign across boundary edges"
kind: prop
status: Proved
level: PA-4
topics: [unfoldings]
examples: [EX-2x1]
depends_on: [GEO-7]
source: notes/01-geometry/unfoldings.md:36-59
added: 2026-09-24
---

## Statement

> **Proposition 1.5 (Proved: explicit model).** With $\Omega = S(P)\times K_4$,
> write $g = \operatorname{diag}(a,b)$, $\rho_1 = \operatorname{diag}(-1,1)$,
> $\rho_2 = \operatorname{diag}(1,-1)$, and let $r,\ell = r^{-1}$ and $u,d = u^{-1}$
> be the partial right/left and up/down neighbour maps on $S(P)$, defined exactly
> when the corresponding edge is interior to $P$. Then
> $$\sigma(s,g) = \begin{cases}(r^{a}(s),\,g) & \text{edge interior to } P,\\ (s,\,\rho_1 g) & \text{edge on } \partial P,\end{cases}
> \qquad
> \tau(s,g) = \begin{cases}(u^{b}(s),\,g) & \text{edge interior to } P,\\ (s,\,\rho_2 g) & \text{edge on } \partial P.\end{cases}$$
>
## Proof

> *Proof.* Moving in $M$-direction $e_1$ inside the copy $g(P)$ is moving in
> $P$-direction $g^{-1}e_1 = a\,e_1$; crossing a vertical boundary edge passes to
> the copy $\rho_1 g$ at the same square. ($K_4$ abelian, so left/right
> multiplication is immaterial.) $\square$

*Check.* $P = 2\times1$: $\sigma$ is the 4-cycle
$(s_0,{+}{+}) \to (s_1,{+}{+}) \to (s_1,{-}{+}) \to (s_0,{-}{+}) \to$, and $\tau$
a product of 2-cycles — the regular action of $\mathbb{Z}/4\times\mathbb{Z}/2$ on
8 squares, i.e. the $4\times 2$ torus. ✓

**Consequence for search.** Under (A6) the class is parametrised by
**polyominoes**; under (A4)–(A5) by rectangle-tiled parking garages, best encoded
as a set of unit squares with an explicit edge gluing (orientable, non-empty
boundary) rather than as a planar region. In all cases $n = 4m$ and $\sigma,\tau$
are determined by $P$.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/unfoldings.md:36-59 (relabel map).
