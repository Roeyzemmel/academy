---
id: CEX-3
aliases: [N22, G8]
title: "O_16^a: a 16-square (Q2) counterexample at OA-3"
summary: "The Cayley origami of Z/4⋊Z/4 (normal, 16 squares) fails (Q2) exactly on gr(T_E), E = a²b² central, as squares of elements outside the Frattini subgroup lie in {1,a²,b²}. OA-3, not PA-4."
kind: prop
status: Proved
level: OA-3
topics: [counterexamples, normal-case]
examples: [EX-O16a, EX-EW]
depends_on: [OBS-1, CRIT-9, GEO-12]
source: notes/03-q2/families-hunt.md:840-882
added: 2026-09-24
---

## Statement

### N22 (Proved) — $O_{16}^{a}$: the Cayley origami of $\mathbb Z/4\rtimes\mathbb Z/4$

**N22.** Let $G_{\mathrm{abs}}=\langle a,b\mid a^4=b^4=1,\ bab^{-1}=a^{-1}\rangle$ (order 16),
squares $(i,j)\in(\mathbb Z/4)^2$ labelled $i+4j$, $\sigma(i,j)=(i+(-1)^j,j)$,
$\tau(i,j)=(i,j+1)$ (a $4\times4$ grid whose odd rows run backwards); tuples
$r=(1,2,3,0,7,4,5,6,9,10,11,8,15,12,13,14)$, $u=(4,5,6,7,8,9,10,11,12,13,14,15,0,1,2,3)$.

**(Q2) fails for $O_{16}^{a}$**, on the orbital $\mathrm{gr}(T_E)$, $T_E(i,j)=(i+2,j+2)$ (left
multiplication by the central $E=a^2b^2$), e.g. the pair $(0,10)$. **Level (A3)**, with
$\mu(i,j)=(1-i,j+2)$, $\nu(i,j)=(i+2,-j)$, $\mu\nu(i,j)=(3-i,2-j)$; all three are
fixed-point-free ($2i\ne1,2,3$ in $\mathbb Z/4$), and every (A3) identity —
$\mu^2=\nu^2=\mathrm{id}$, $\mu\nu=\nu\mu$, $\mu\sigma\mu=\sigma^{-1}$, $\mu\tau\mu=\tau$,
$\nu\sigma\nu=\sigma$, $\nu\tau\nu=\tau^{-1}$ — is checked directly.

## Proof

*Proof of the failure.* With $\psi:G\to Q=\mathbb Z^2/2\mathbb Z^2$ as in N12/N15 and
$G_0:=\ker\psi=\langle a^2,b^2\rangle=\Phi(G_{\mathrm{abs}})$ (the Frattini subgroup — renamed
from the letter $\Phi$ to avoid the clash with the (A3) group), the squares of elements
outside $G_0$ lie in $\{1,a^2,b^2\}$, so $E=a^2b^2\notin\langle c\,w'^2c^{-1}\rangle$ for any
Christoffel value $w'$ (which has $\psi(w')\ne0$, forcing an even power, whose square lands
in $\{1,a^2,b^2\}$). This is N12 with $T=\lambda_E$, or equally R Prop. 5.7 (Proved).
**Uniqueness of the unmet orbital**: by regularity the orbitals are indexed by
$g\in G_{\mathrm{abs}}$; the conjugacy classes of $G_{\mathrm{abs}}$ are the four central
singletons $\{1\},\{a^2\},\{b^2\},\{E\}$ and six reflection-type pairs; the values $x,y,xy,xyy$
(i.e. $a,b,ab,ab^2$ up to conjugacy) and their powers meet all eight non-identity classes
other than $\{E\}$, so $\mathrm{gr}(T_E)$ is the **only** unmet orbital, with $K_{\min}=3$ on
the met part.

**Not (A4).** By N10, an (A4) unfolding needs at least four fixed points of $[\sigma,\tau]$;
here the commutator has none (every square corner is a genuine zero — commutator type
$2^8$, no fixed point), so $O_{16}^{a}$ is not (A4), and not an origami-quotient of any (A4)
unfolding.

**Structure.** $G_{\mathrm{abs}}/\langle E\rangle\cong Q_8$, so **$O_{16}^{a}\to
O_{16}^{a}/\langle T_E\rangle$ is a translation double cover of the Eierlegende
Wollmilchsau, unramified** (commutator types $2^8$ over $2^4$, Euler characteristic matches).
(Q2) holds on the EW and fails on this cover; the failure is created by the cover, not lifted
from it (contrast W5). Every normal origami with group $\cong\mathbb Z/4\rtimes\mathbb Z/4$
fails (Q2), by the same argument (the squares generate the Frattini subgroup for any
2-generated 2-group, Burnside's basis theorem).

*Cleared by.* Two `claim-verifier` runs, both Proved, no inputs, sequential, both on
`claude-opus-5-5`; see `computation/verdicts.md`, entry "2026-09-24 — G8
(writing/n8-generalization.md) → N22". Source: `writing/n8-generalization.md` §4.1 (G8).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:840-882 (relabel map).
