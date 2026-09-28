---
id: DEF-1
aliases: [R2 Def/Lemma 0.1]
title: "The period lattice Λ and the difference class d(i,j) ∈ Z²/Λ"
summary: "Λ = ab(Stab_F(i)) is independent of i, of index ≤ n; defines d(i,j) in A = Z²/Λ and the classes D_δ, with sizes, additivity, G-invariance and Φ-equivariance under OA-3"
kind: lemma
status: Proved
topics: [definitions, structure, orbitals]
depends_on: []
source: notes/00-setting/invariants.md:17-28
added: 2026-09-24
---

## Statement

**Definition/Lemma 0.1 (Proved).** $\Lambda:=\mathrm{ab}(\mathrm{Stab}_F(i))$ is independent of
$i$, of finite index $\le n$ in $\mathbb Z^2$, and contains $\mathrm{ab}(\ker\pi)$. Hence
$\mathrm{ab}_\Lambda:G\to A:=\mathbb Z^2/\Lambda$ ($\sigma\mapsto(1,0)$, $\tau\mapsto(0,1)$) is a
well-defined surjection with $G_i\le\ker\mathrm{ab}_\Lambda$. Define
$$d(i,j):=\mathrm{ab}(w)+\Lambda\ \text{ for any }w\text{ with }\pi(w)i=j,\qquad
D_\delta:=\{(i,j)\in\Omega^{(2)}:d(i,j)=\delta\}.$$
Then $d$ is well defined, $d(i,j)+d(j,k)=d(i,k)$, $d(hi,hj)=d(i,j)$ for $h\in G$, $j\mapsto d(i,j)$
is onto $A$, $|D_\delta|=n^2/|A|$ ($\delta\ne0$), $|D_0|=n(n/|A|-1)$; and if $u\in W$ has
direction $(q,p)$ then $u^mi=j\Rightarrow d(i,j)=m(q,p)+\Lambda$. Under (A3),
$d(\phi i,\phi j)=\phi\cdot d(i,j)$ with $\Phi$ acting on $A$ by sign changes.
*(Geometric meaning, §2: $\Lambda=\Lambda(M)$ the absolute periods; $A$-cosets are the
fibres of the maximal torus quotient $M\to E_\Lambda=\mathbb R^2/\Lambda$.)*

## History

- 2026-09-24: migrated verbatim from notes/00-setting/invariants.md:17-28 (relabel map).
