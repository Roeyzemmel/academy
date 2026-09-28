# The questions (Q1), (Q2) and the Christoffel formalism

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

The objects: an origami's monodromy pair $(\sigma,\tau)$, Christoffel values $W$, their conjugacy closure $C$ and power closure $C^{\mathrm{pow}}$. R states the questions; R2 fixes the notation used from then on ($R_W$, $R^{\mathrm{pow}}$, $K$).

---

## [R §0] Setting and standing hypotheses

$\Omega = \{1,\dots,n\}$; $\sigma,\tau \in S_n$ with $G = \langle\sigma,\tau\rangle$
transitive. Geometrically $\sigma$ is "go right", $\tau$ is "go up" on the $n$
squares of an origami $p : M \to \mathbb{T}^2$ branched over $0$, and $G$ is the
monodromy group. **The indices $i,j$ are square indices.**

$$W = \{\, w(\sigma^a,\tau^b) : w \text{ Christoffel},\ a,b \in \{\pm1\} \,\},\qquad
C = \bigcup_{u\in W} u^{G},\qquad C^{\mathrm{pow}} = \{c^k : c\in C,\ k\in\mathbb{Z}\}.$$

Single letters ($x$, $y$; slopes $0$ and $\infty$) are included in $W$; upper and
lower words are both allowed, so $W$ is inversion-closed (S1 §1.1).

**(Q2)** Is $C^{\mathrm{pow}}$ transitive off the diagonal? — **the live question.**
**(Q1)** Is $C$ transitive off the diagonal? — false in general (§3); of secondary
interest, a few examples suffice.

The case $i = j$ is excluded by decision.

---

## [R2 §0] Standing data (group-theoretic)


---

## [R2 §0.1] The pair and the Christoffel relations

$\Omega=\{1,\dots,n\}$; $\sigma,\tau\in S_n$; $G=\langle\sigma,\tau\rangle$ transitive.
$F_2=\langle x,y\rangle\xrightarrow{\pi}G$, $x\mapsto\sigma,y\mapsto\tau$;
$\mathrm{ab}:F_2\to\mathbb Z^2$ exponent sums. $G_i$ = stabiliser; $\mathrm{Stab}_F(i)=\pi^{-1}(G_i)$.
$C_{S_n}(G)$ = centraliser (semiregular).

Christoffel data: $w_{p,q}$ the lower Christoffel word with $q$ letters $x$, $p$ letters $y$,
$\gcd(q,p)=1$ (including $x,y$). A *Christoffel value of direction $(aq,bp)$*, $a,b=\pm1$, is
$u=w_{p,q}(\sigma^a,\tau^b)$; $W$ = the set of all; $W_{\mathrm{rot}}$ = values of all cyclic
rotations; $C=\bigcup_{u\in W}u^G$; $C^{\mathrm{pow}}=\{c^k\}$. On $\Omega^{(2)}=\{(i,j):i\ne j\}$:
$$R_W=\{(i,u^ki):u\in W_{\mathrm{rot}}\},\qquad R^{\mathrm{pow}}=\{(i,ci):c\in C^{\mathrm{pow}}\}=G\text{-saturation of }\{(i,u^ki):u\in W\}.$$
A set $X$ of permutations is *2‑transitive* if $\{(i,ci):c\in X\}\supseteq\Omega^{(2)}$.
**(Q2)**: $C^{\mathrm{pow}}$ is 2‑transitive, i.e. $R^{\mathrm{pow}}=\Omega^{(2)}$. **(Q1)**: $C$ is.
$K$ always denotes a bound $|p|+|q|\le K$ on the directions used.
