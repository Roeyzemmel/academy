> Living copy of `archive/2026-09-project-docs/periodic-points-origami-orbits.md`. Related to, but not part of, the
> Christoffel-transitivity line: it concerns *periodic* (torsion) points, which R2 Thm 2.2
> explicitly excludes (non-torsion base points only).

# Periodic points of origamis: orbit structure and the cylinder question

Written 2026-09-11. Question (Roey): for an origami $O$ and a point $x$ with finite
$\mathrm{Aff}(O)$-orbit, what does the orbit look like, and does it enter a cylinder?
Context: the twist mechanism of Hubert–Schmoll–Troubetzkoy, *Modular fibers and
illumination problems* (arXiv math/0602394; IMRN 2008), Theorem 28 in the arXiv
numbering = "rectangle theorem" (Roey cites it as Theorem 29 of the published version).

## Setup

$O$ reduced origami (relative period lattice $=\mathbb Z^2$), genus $\ge 2$,
$\pi\colon O\to\mathbb T^2=\mathbb R^2/\mathbb Z^2$, singularities $\Sigma\subset\pi^{-1}(0)$
(regular corners allowed). $\Gamma=\mathrm{SL}(O)\subset\mathrm{SL}_2(\mathbb Z)$, finite index.
For a primitive $v\in\mathbb Z^2$, $\ell_v=\mathbb Rv/\mathbb Z^2\subset\mathbb T^2$ is the closed
geodesic through $0$ in direction $v$.

**Descent (Proved).** $\pi\circ\varphi = D\varphi\circ\pi$ for every $\varphi\in\mathrm{Aff}(O)$.
(Develop from a singularity $x_0$: $\mathrm{dev}(\varphi x)=\mathrm{dev}(\varphi x_0)+D\varphi\,\mathrm{dev}(x)$,
and $\mathrm{dev}(\varphi x_0)\in\Lambda_{\rm rel}=\mathbb Z^2$.) So $\mathrm{Aff}(O)$ acts on $\mathbb T^2$
through the *linear* action of $\Gamma$.

## Results

1. **(GHS 2003, reproved.)** $x$ is periodic iff $\pi(x)$ is a torsion point, i.e. $x$ has
   rational coordinates in its square. ($\Leftarrow$: $\Gamma$ preserves the finite set
   $\mathbb T^2[N]$. $\Rightarrow$: the derivative group of $\mathrm{Stab}(x)$ has finite index in
   $\Gamma$, hence contains a hyperbolic $h$; $(h-I)\tilde\pi(x)\in\mathbb Z^2$ with $h-I$
   invertible over $\mathbb Q$.) Source: Gutkin–Hubert–Schmidt, Ann. Sci. ENS 36 (2003);
   exact theorem number not checked against the paper.

2. **Orbit shape (Proved).** With $y=\pi(x)$ of order $N$:
   $\mathrm{Aff}(O)\cdot x\subset\pi^{-1}(\Gamma y)\subset\pi^{-1}(\mathbb T^2[N])$, all points of
   order exactly $N$; $|\mathrm{Aff}\cdot x|\le d\,|\Gamma y|$, $d$ = number of squares. The orbit is
   in general **not** the full preimage of $\Gamma y$: in $\mathcal H(2)$ Weierstrass and
   non-Weierstrass points over the same 2-torsion point are in different orbits.

3. **Cylinder criterion (Proved).** Fix a primitive direction $v$.
   (i) If $\Gamma y\not\subset\ell_v$, the orbit contains points $z$ with $\pi(z)\notin\ell_v$, and
   every such $z$ is in the interior of a $v$-cylinder (boundaries of $v$-cylinders are
   $v$-saddle connections, which project into $\ell_v$).
   (ii) If $\Gamma y\subset\ell_v$ — equivalently $y=\tfrac kN v$ with $\gcd(k,N)=1$ and
   $\Gamma\subset g\,\Gamma_0(N)\,g^{-1}$ for $g\in\mathrm{SL}_2(\mathbb Z)$ with $ge_1=v$ — then every
   point of the orbit lies on a closed $v$-geodesic through $\pi^{-1}(0)$. If moreover
   $\pi^{-1}(0)=\Sigma$ (no regular corners), the orbit never meets the interior of any
   $v$-cylinder.
   Consequence: for a *fixed* direction the answer can be no; but for every nonsingular
   periodic $x$ and all directions $v$ outside one residue class mod $N$ ($y\notin\ell_v$),
   $x$ itself is interior to a $v$-cylinder, and choosing two such directions puts $x$ in an
   open "rectangle" for that pair.

4. **Counterexample (hand-checked + script, 2026-09-11).** $O'=(r,u)=((1\,2\,3),(1\,2))$:
   3 squares, $\mathcal H(2)$, one horizontal cylinder (height 1, circumference 3), single
   corner point. $\iota$ = rotation by $\pi$ about the centre of square 3 is the hyperelliptic
   involution; its fixed points are the singularity, the centre of square 3, the midpoint of
   the edge right(1)=left(2), and **all three horizontal edge midpoints**. Weierstrass counts
   over $\mathbb T^2[2]$: $(0{:}1,\ (\tfrac12,0){:}3,\ (0,\tfrac12){:}1,\ (\tfrac12,\tfrac12){:}1)$,
   so $\Gamma$ fixes $(\tfrac12,0)$, i.e. $\Gamma\subset\Gamma_0(2)$ (in fact $=\Gamma_0(2)$, index 3,
   $T\in\Gamma$ via the relabelling $\sigma=(1\,2\,3)$). Hence the orbit of a horizontal edge
   midpoint is exactly the three horizontal edge midpoints, all on horizontal saddle
   connections: **it never enters the horizontal cylinder**, nor any $v$-cylinder for
   $v=(p,q)$ with $p$ odd, $q$ even. It does meet the interiors of both vertical cylinders.
   For $L(2,2)$ ($\Gamma=\Gamma_\theta$) the non-Weierstrass edge midpoints have orbits inside
   $\ell_h\cup\ell_v$: they never enter an open horizontal–vertical rectangle $\mathscr R(p)$.

## Relation to HST's twist argument

HST move points with the horizontal/vertical multitwists, which act on each closed leaf of
a cylinder as a rotation by an angle proportional to the normalised height; their Lemma 29
(quantitative Kronecker) excludes finitely many rotation numbers — the rational ones. A
periodic point has rational height in every cylinder of every periodic direction it ever
visits, so every twist orbit it generates is a finite rational rotation orbit and Lemma 29
never applies to it. The replacement for periodic points is the congruence description in
item 3: what the twists cannot do, only the finite group $\Gamma$ acting on $\mathbb T^2[N]$ can.
