# Hypotheses: the chain (A0)–(A7), (SC), and the tags

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

R's geometric chain, R2's restatement with (A7), the dictionary of two-letter tags, and the full implication chart. Reflection data (RD*) are defined in `notes/02-structure/reflection-data.md`; (EP), (D0), (2T) in `invariants.md`.

---

## [R §0.2] The hypothesis chain, enumerated by implication

> **(A0)** No assumption beyond $G = \langle\sigma,\tau\rangle$ transitive.
>
> **(A1)** There is $\iota \in S_n$ with $\iota\sigma\iota^{-1} = \sigma^{-1}$ and
> $\iota\tau\iota^{-1} = \tau^{-1}$. *(Equivalently: $M$ carries an affine
> automorphism with derivative $-I$.)*
>
> **(A2)** (A1) holds with some such $\iota$ satisfying $\iota^2 = 1$.
> *(Equivalently: $M$ carries an affine **involution** with derivative $-I$. This
> involution is **not** assumed hyperelliptic — see Remark 1.3.)*
>
> **(A3)** There is an **injective** homomorphism $\phi : K_4 \hookrightarrow S_n$,
> $K_4=\{\pm1\}^2$, with $\phi(a,b)\,\sigma\,\phi(a,b)^{-1} = \sigma^{a}$,
> $\phi(a,b)\,\tau\,\phi(a,b)^{-1} = \tau^{b}$, acting **freely** on $\Omega$.
> Write $\mu = \phi(-1,1)$, $\nu = \phi(1,-1)$, $\Phi = \phi(K_4)$, $G^+ = G\Phi$.
>
> **(A4)** $M$ is the unfolding of a **rectangle-tiled parking garage** $P$ whose
> boundary segments are horizontal or vertical. $P$ need not be simply connected
> and $h$ need not be injective.
>
> **(A5)** (A4), and **no corner of $P$ has angle a multiple of $2\pi$** — i.e. no
> corner of angle $2\pi, 4\pi, 6\pi, \dots$; slit tips are excluded as well.
> Writing angles as $m\pi/2$ this forbids exactly $4 \mid m$; every other angle is
> permitted, including $3\pi/2$, $5\pi/2$ and $3\pi$. $P$ may still be
> non-simply-connected and $h$ non-injective.
>
> **(A6)** $M$ is the unfolding of a **simple** rectangle-tiled polygon embedded in
> the plane — i.e. of a polyomino.

$$\boxed{\ \text{(A6)} \implies \text{(A5)} \implies \text{(A4)} \implies \text{(A3)} \implies \text{(A2)} \implies \text{(A1)} \implies \text{(A0)}\ }$$

**Transverse condition.** **(SC)**: $P$ is simply connected. (A6) $\Rightarrow$ (SC),
but **(SC) and (A5) are incomparable** — Gauss–Bonnet on a disc permits a single
$4\pi$ corner against ten right angles ($-3\pi + 10\cdot\tfrac\pi2 = 2\pi$), so a
simply connected garage may violate (A5). Impose (SC) alongside (A4) or (A5) when
wanted; see Remark 1.3 for why it is interesting.

> **→ [GEO-1](../../claims/GEO-1.md)** (R Prop 0.1) — moved to its own file, 2026-09-24.

---

## [R2, preamble] Naming scheme and deductive order

# Christoffel transitivity — consolidated results (sessions of 2026-09-10/11)

Supersedes `christoffeltransitivityresults3.md` and `…results4.md`; continues R
(`christoffeltransitivityresults.md`) and S1. Status labels: Proved / Proved modulo stated
inputs / Reduced / Partial / Disproved / Not settled. Only hand-checkable examples were
computed (toolkit `christoffel_lib.py`, `examples.py`).

**Naming scheme.** (A0)–(A6), (SC) are R's hypotheses, kept verbatim; (A7) — $P$ a
rectangle, the trivial level — is added for completeness. Two-letter tags in parentheses are
the new *group-theoretic* conditions, all on $(\Omega,\sigma,\tau)$:

| tag | reads | defined in |
|---|---|---|
| (EP) | even periods, $\Lambda\subseteq2\mathbb Z^2$ | §0.3 |
| (RD), (RD4), (RD5), (RD6), (RD7) | $(\sigma,\tau)$ is the twisted diagonal of a reflection datum, with local conditions; (RD7) is the flat (torus) case | §1.2 |
| (D0) | $R^{\mathrm{pow}}$ meets the zero difference class | §0.3 |
| (2T) | relative 2‑transitivity: each nonempty $D_\delta$ is one $G$-orbital | §0.3 |
| (HA) | the block group $H$ contains $A_m$ | §3.2 |
| (CT) | every nontrivial centralising $T$ has a $T$-invariant Christoffel orbit of the right parity | §4.4 |
| (2T′), (CT′) | relative 2‑transitivity with respect to $A$ *and* the centraliser, and the matching necessary condition | §4.5 |

Deductive order: §0 data → §1 hypotheses and the datum → §2 the geometric bridge (the only
place geometry is used) → §3 structure of $G$ under (RD) → §4 orbitals and (Q2) → §5, §6
how to establish (HA) and (CT) → §7 bounds on $K$ → §8 examples → §9 literature → §10 status.

---

## [R2 §1] Hypotheses


---

## [R2 §1.1] R's chain

> **(A0)** $G$ transitive. **(A1)** $\exists\iota_0$: $\iota_0\sigma\iota_0^{-1}=\sigma^{-1}$, $\iota_0\tau\iota_0^{-1}=\tau^{-1}$. **(A2)** (A1) with $\iota_0^2=1$. **(A3)** an injective $\phi:K_4\hookrightarrow S_n$ with $\phi(a,b)\sigma\phi(a,b)^{-1}=\sigma^a$, $\phi(a,b)\tau\phi(a,b)^{-1}=\tau^b$, $\Phi=\phi(K_4)$ free on $\Omega$; $G^+=G\Phi$; $\mu=\phi(-1,1)$, $\nu=\phi(1,-1)$.
>
> **(A4)** $(\sigma,\tau)$ is the monodromy of the unfolding $M$ of a rectangle-tiled parking garage $P$ (immersed in the plane, no interior cone points). **(A5)** (A4), no corner of angle $\in2\pi\mathbb Z$. **(A6)** $P$ a polyomino. **(A7)** $P$ a $p\times q$ rectangle — the trivial case, isolated for completeness: $M=\mathbb R^2/(2p\mathbb Z\oplus2q\mathbb Z)$, $G=\mathbb Z/2p\times\mathbb Z/2q$ regular (R Prop. 3.1). **(SC)** $P$ simply connected.

---

## [R2 §1.3] The implication chart

$$\text{(A7)}\Rightarrow\text{(A6)}\Rightarrow\text{(A5)}\Rightarrow\text{(A4)}\Rightarrow\text{(A3)}\Rightarrow\text{(A2)}\Rightarrow\text{(A1)}\Rightarrow\text{(A0)}\qquad\text{(R Prop. 0.1)}$$
$$\text{(A7)}\Rightarrow\text{(RD7)}\Rightarrow\text{(RD6)}\Rightarrow\text{(RD5)}\Rightarrow\text{(RD4)}\Rightarrow\text{(RD)}\Rightarrow\text{(A3)}\wedge\text{(EP)}\qquad(\S2.2,\ \S3.1)$$
$$\text{(A6)}\Rightarrow\text{(RD6)},\quad\text{(A5)}\Rightarrow\text{(RD5)},\quad\text{(A4)}\Rightarrow\text{(RD4)}\qquad(\S2.2)$$
$$\text{(RD7)}\iff\text{(RD4)}\wedge[\sigma,\tau]=1\iff\text{(RD4)}\wedge G\text{ abelian};\qquad \text{under (A6): (A7)}\iff G\text{ abelian}\iff G\text{ regular}\qquad(\S3.1,\ \S3.4)$$
$$\text{(2T)}\wedge\text{(D0)}\Rightarrow\text{(Q2)}\quad(\S4.2);\qquad \text{(HA)}\Rightarrow\big[\text{(Q2)}\Leftrightarrow\text{(CT)}\big]\quad(\S4.4);\qquad \text{abelian},\ \text{(2T)},\ \text{(EP)}\wedge\text{(HA)}\ \Rightarrow\ \text{(2T′)}\Rightarrow\big[\text{(Q2)}\Leftrightarrow\text{(CT′)}\big]\quad(\S4.5)$$
$$\text{(A6)}\wedge\neg\text{(A7)}\Rightarrow\text{(D0)}\quad(\S2.3);\qquad \text{(2T)}\wedge C_{S_n}(G)\ne1\Rightarrow G\text{ abelian regular}\quad(\S4.3)$$
$$\text{(RD)}\iff\text{(EP)}\wedge\text{(A3}^{\rm std}\text{)}\quad(\text{Prop. 3.1′});\qquad\text{(A3)}\wedge\text{(EP)}\not\Rightarrow\text{(RD)}\ \ (\text{Eierlegende Wollmilchsau}).$$
