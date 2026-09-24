# Veech surfaces and the dichotomy (§3)

Split from `theorems.md` on 2026-09-24, section numbers kept. Read `INDEX.md` first: it holds how to read an entry (quoted vs paraphrased) and the standing notation.

## 3. Veech surfaces & the dichotomy

### 3.1 The Veech dichotomy (Veech, 1989)

**Statement (Hubert–Schmidt survey, Theorem 1).** "Let $(X,\omega)$ be a translation surface.
Suppose $\mathrm{SL}(X,\omega)$ is a lattice in $\mathrm{SL}(2,\mathbb{R})$. Then for each
direction $\theta$, the flow $F_\theta$ is either periodic or uniquely ergodic."

**Statement (Cheung–Hubert–Masur phrasing).** For a Veech surface, "for every direction $\theta$,
either the flow lines of $\varphi_\theta$ are all closed and the surface decomposes into a union
of cylinders, or the flow is minimal and uniquely ergodic."

**Supplementary facts usually bundled with it.**
- On a Veech surface, "a periodic direction … is fixed by a parabolic affine diffeomorphism."
- Generally (no lattice hypothesis): "If there are no saddle connections in direction $\theta$,
  then direction $\theta$ is minimal."

**Notation used.** $\mathrm{SL}(X,\omega)$ = "the stabilizer of $(X,\omega)$ under the action of
$\mathrm{SL}(2,\mathbb{R})$"; the *Veech group* $\mathrm{PSL}(X,\omega)$ is its image in
$\mathrm{PSL}(2,\mathbb{R})$. $\mathrm{Aff}(X,\omega)$ = affine diffeomorphisms (derivative
constant off singularities). "Veech surface"/"lattice surface": $\mathrm{SL}(X,\omega)$ is a
lattice, i.e. the quotient has finite hyperbolic area.

**Common misuse — verified pitfall.** *The converse is false.* Smillie–Weiss: "Veech showed that
if a translation surface has a stabilizer which is a lattice in $\mathrm{SL}(2,\mathbb{R})$, then
any direction for the corresponding constant slope flow is either completely periodic or uniquely
ergodic. **We show that the converse does not hold: there are translation surfaces that satisfy
Veech's dichotomy but for which the corresponding stabilizer subgroup is not a lattice.**" So
"satisfies Veech's dichotomy" is strictly weaker than "is a lattice surface." (The correct
equivalent condition is the *uniform* one — see §3.2 (ii)/(iii).)

A second pitfall: the periodic alternative is *complete periodicity* (the surface decomposes into
cylinders in that direction), not merely "there exists a periodic trajectory." And the minimal
alternative on a general (non-lattice) surface need not be uniquely ergodic.

**Source.** W. A. Veech, *Teichmüller curves in moduli space, Eisenstein series and an application
to triangular billiards*, Invent. Math. **97** (1989), no. 3, 553–583, DOI 10.1007/BF01388890.
Statements as quoted from: P. Hubert, T. Schmidt, *An introduction to Veech surfaces*,
https://math.uchicago.edu/~masur/hs.pdf ; Y. Cheung, P. Hubert, H. Masur, *Topological dichotomy
and strict ergodicity for translation surfaces*, arXiv:math/0607179,
https://arxiv.org/html/math/0607179v1 ; M. Cohen, arXiv:1011.3217.
Converse failure: J. Smillie, B. Weiss, *Veech's dichotomy and the lattice property*, Ergodic
Theory Dynam. Systems **28** (2008), no. 6, 1959–1972, DOI 10.1017/S0143385708000114.

---

### 3.2 Characterizations of lattice surfaces (Smillie–Weiss, 2010)

**Statement.** *Theorem 1.1.* "A flat surface has the lattice property if and only if it has no
small triangles."

*Theorem 1.2.* "For any $\alpha > 0$, $\mathrm{NST}(\alpha)$ contains a finite number of affine
equivalence classes."

*Theorem 1.3 (eleven equivalent conditions, verbatim).* The following are equivalent for a flat
surface $M$: "(i) $M$ is a lattice surface. (ii) $M$ is uniformly completely periodic.
(iii) $M$ is uniformly completely parabolic. (iv) $|T(M)| < \infty$. (v) The set of triangles for
$M$ consists of finitely many $\mathrm{Aff}(M)$-orbits. (vi) $M$ has no small triangles.
(vii) $\{u \wedge v : u,v \in \mathrm{hol}(M)\}$ is a discrete set of numbers. (viii) For any
$T > 0$, the set $\{(\xi,\eta) \in L_M \times L_M : |\mathrm{hol}(\xi)\wedge \mathrm{hol}(\eta)| < T\}$
contains finitely many $\mathrm{Aff}(M)$-orbits. (ix) $M$ has no small virtual triangles.
(x) The $G$-orbit of $M$ is closed. (xi) There is a compact subset $K$ of the stratum containing
$M$ such that for any $g \in G$, the geodesic orbit of $gM$ intersects $K$."

*Abstract (verbatim).* "We answer a question of Vorobets by showing that the lattice property for
flat surfaces is equivalent to the existence of a positive lower bound for the areas of affine
triangles. We show that the set of affine equivalence classes of lattice surfaces with a fixed
positive lower bound for the areas of triangles is finite and we obtain explicit bounds on its
cardinality. We deduce several other characterizations of the lattice property."

**Notation used.** "$M$ is a lattice surface if $\Gamma_M$ is a lattice, i.e. has finite covolume
in $G$." "$M$ has no small triangles if $\inf T(M) > 0$"; $\mathrm{NST}(\alpha)$ = surfaces with
that infimum $\ge \alpha$; $\mathrm{NSVT}(\beta)$ = "no small virtual triangles",
$\inf\{|v_1\wedge v_2| : v_i \in \mathrm{hol}(M),\, v_1 \wedge v_2 \ne 0\} \ge \beta$;
$L_M$ = set of saddle connections; $\mathrm{hol}$ = holonomy vector.

**Common misuse.** (x) — "the $G$-orbit of $M$ is closed" — is the condition that gets used
together with EMM; note it is *closed orbit*, and (xi) is the "no divergence" characterization
that pairs with Masur's criterion. Condition (ii) is *uniformly* completely periodic; plain
"completely periodic" is strictly weaker (cf. §3.1's failure of the converse to Veech dichotomy).

**Source.** J. Smillie, B. Weiss, *Characterizations of lattice surfaces*, Invent. Math. **180**
(2010), no. 3, 535–557; arXiv:0809.3729; http://www.math.tau.ac.il/~barakw/papers/nst.pdf

---

### 3.3 Translation coverings, balanced coverings, and Veech groups

**Definitions.**
- *Translation covering.* "A continuous map $p : Y \to X$ is called a translation covering, if
  $p(\Sigma(Y)) = \Sigma(X)$ and $p : Y\setminus\Sigma(Y) \to X\setminus\Sigma(X)$ is locally a
  translation."
- *Balanced.* A translation covering is *balanced* when $p^{-1}(\Sigma(X)) = \Sigma(Y)$ — i.e. no
  extra marked points in $Y$ beyond the full preimage of the singular set. (Verified statement of
  the condition from a secondary source; see §6 for the caveat about attribution.)

**Statement (Veech groups of covers).** *Lemma 2.1 (as stated in the source consulted).* "Let
$p : (Y,\nu) \to (X,\omega)$ be a (finite, balanced) translation covering with primitive base
surface $(X,\omega)$ and genus $g(X) > 1$, then $\Gamma(Y)$ is a subgroup of $\Gamma(X)$." The
source attributes the ambient framework to Möller (2006): "every translation surface is the
(balanced) covering surface of a primitive base surface."

**Relevance to blocking.** Blocking and illumination behave well under translation coverings
because straight-line trajectories lift and project; this is the mechanism behind LMW Theorem 1
(torus covers inherit the torus's blocking property) and behind Apisa–Wright Theorem 1.3
(markings arise from covering constructions).

**Common misuse.** "Balanced" is exactly the hypothesis that fails when you add marked points —
and marked points are the entire subject of the Apisa/Apisa–Wright program. Adding a marked point
to $Y$ generally shrinks the Veech group and can destroy the subgroup relation. Also note the
hypotheses *primitive base* and *$g(X)>1$* in the lemma above.

**Source.** Statements quoted from https://ar5iv.arxiv.org/html/1005.4588 (*A series of coverings
of the regular $n$-gon*). Original sources: E. Gutkin, C. Judge, *Affine mappings of translation
surfaces: geometry and arithmetic*, Duke Math. J. **103** (2000); P. Hubert, T. Schmidt,
*Invariants of translation surfaces*, Ann. Inst. Fourier **51** (2001), no. 2, 461–495,
https://www.numdam.org/item/AIF_2001__51_2_461_0/ (abstract verbatim: "We definite invariants of
translation surfaces which refine Veech groups. These aid in exact determination of Veech groups.
We give examples where two surfaces of isomorphic Veech group cannot even share a common tree of
balanced affine coverings."); M. Finster, *Veech Groups and Translation Coverings* (2013).

---

### 3.4 Arithmetic Veech groups = square-tiled surfaces (Gutkin–Judge)

**Statement (as quoted in the Hubert–Schmidt survey).** "The surface $(X,\omega)$ is tiled by
parallelograms if and only if $\mathrm{SL}(X,\omega)$ is arithmetic." And: "any surface of
arithmetic Veech group is a branched cover of the torus, with branching above one sole point."

**Common misuse.** This is *the* place where the torus-cover terminology collides. "Arithmetic /
square-tiled" $\Leftrightarrow$ torus cover branched over a **single** point $\Leftrightarrow$ all
periods (absolute *and* relative) lie in a lattice. The LMW "torus cover" (§1.0) only requires the
**absolute** period group to be discrete and permits branching over several points; such a surface
need not be arithmetic, need not be square-tiled, and need not even be a lattice surface. LMW
Theorem 1 covers all of them. Getting this wrong inverts the content of LMW's main theorem.

**Source.** E. Gutkin, C. Judge, *Affine mappings of translation surfaces: geometry and
arithmetic*, Duke Math. J. **103** (2000), 191–213. Statement as quoted from Hubert–Schmidt,
*An introduction to Veech surfaces*, https://math.uchicago.edu/~masur/hs.pdf

