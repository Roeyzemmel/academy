# Strata, period coordinates, background (§4)

Split from `theorems.md` on 2026-09-24, section numbers kept. Read `INDEX.md` first: it holds how to read an entry (quoted vs paraphrased) and the standing notation.

## 4. Strata, period coordinates & background

### 4.1 Strata, dimension, and period coordinates

**Definitions.**
- $\mathcal{H}(k_1,\dots,k_n)$ = moduli space of pairs $(X,\omega)$, $X$ a compact genus-$g$
  Riemann surface and $\omega$ a holomorphic 1-form with zeros of orders $k_1,\dots,k_n$, where
  $\sum_{i=1}^n k_i = 2g-2$.
- **Period coordinates.** Locally, $\Phi(X,\omega) = \left(\int_{\xi_1}\omega,\dots,\int_{\xi_N}\omega\right)$
  where $\{\xi_i\}$ is a basis of relative homology $H_1(X,\Sigma;\mathbb{Z})$; equivalently the
  local chart is the relative cohomology class $[\omega] \in H^1(X,\Sigma;\mathbb{C})$.
- **Dimension.** $\dim_{\mathbb{C}} \mathcal{H}(k_1,\dots,k_n) = 2g + n - 1$.

**Common misuse.** The dimension count uses **relative** cohomology: $\dim_{\mathbb{C}} H^1(X,\Sigma;\mathbb{C}) = 2g + n - 1$
with $n = |\Sigma|$. **Marked points count toward $n$.** Adding a marked point raises the dimension
by 1 — which is precisely the definition of a "generic" vs "periodic" point (§1.9, §1.11). Any
argument that compares dimensions of orbit closures must fix a marked-point convention first.

**Source.** M. Kontsevich, A. Zorich, arXiv:math/0201292, https://arxiv.org/html/math/0201292v2 ;
A. Wright, https://websites.umich.edu/~alexmw/numfield.pdf

---

### 4.2 Kontsevich–Zorich classification of connected components (2003)

**Statement.** *Theorem 1 (genus $g \ge 4$).* The connected components of the strata are:
- $\mathcal{H}(2g-2)$ has **three** components: $\mathcal{H}^{\mathrm{hyp}}(2g-2)$,
  $\mathcal{H}^{\mathrm{even}}(2g-2)$, $\mathcal{H}^{\mathrm{odd}}(2g-2)$;
- $\mathcal{H}(2l,2l)$ for $l \ge 2$ has **three** components: $\mathcal{H}^{\mathrm{hyp}}$,
  $\mathcal{H}^{\mathrm{even}}$, $\mathcal{H}^{\mathrm{odd}}$;
- every other stratum $\mathcal{H}(2l_1,\dots,2l_n)$ with all $l_i \ge 1$ has **two** components,
  $\mathcal{H}^{\mathrm{even}}$ and $\mathcal{H}^{\mathrm{odd}}$;
- $\mathcal{H}(2l-1,2l-1)$ for $l \ge 2$ has **two** components: hyperelliptic and
  non-hyperelliptic;
- all remaining strata are connected.

*Theorem 2 (small genus).* $g=2$: $\mathcal{H}(2)$ and $\mathcal{H}(1,1)$ are connected and
coincide with their hyperelliptic components. $g=3$: $\mathcal{H}(4)$ and $\mathcal{H}(2,2)$ each
have **two** components — hyperelliptic and odd spin; all other genus-3 strata are connected.

**Notation used.**
- *Hyperelliptic components*: arise from meromorphic quadratic differentials on
  $\mathbb{P}^1$ via the canonical double cover. Specifically $\mathcal{H}^{\mathrm{hyp}}(2g-2)$
  (a single zero of order $2g-2$ on a hyperelliptic curve, $\omega$ invariant under the
  hyperelliptic involution) and $\mathcal{H}^{\mathrm{hyp}}(g-1,g-1)$ (two zeros of order $g-1$
  exchanged by the involution).
- *Parity of spin structure*: a spin structure is "a choice of a half of the canonical class",
  $\alpha \in \mathrm{Pic}(C)$ with $2\alpha = K_C$; parity is $\dim H^0(C,L) \bmod 2$ for
  $c_1(L)=\alpha$. Defined only when **all $k_i$ are even**.

**Common misuse.** The even/odd spin invariant is defined **only for strata with all zero orders
even**; quoting "two components, even and odd spin" for a stratum with an odd $k_i$ is wrong.
The hyperelliptic component exists only for $\mathcal{H}(2g-2)$ and $\mathcal{H}(g-1,g-1)$.
Genus 2 is the degenerate case where the whole stratum *is* hyperelliptic — relevant because so
many blocking/illumination results are stated in genus 2.

**Source.** M. Kontsevich, A. Zorich, *Connected components of the moduli spaces of Abelian
differentials with prescribed singularities*, Invent. Math. **153** (2003), no. 3, 631–678,
DOI 10.1007/s00222-003-0303-x; arXiv:math/0201292, https://arxiv.org/html/math/0201292v2

---

### 4.3 Masur–Veech ergodicity (1982)

**Statement.** The Teichmüller geodesic flow is ergodic (indeed mixing) with respect to the
Masur–Veech measure on each connected component of each stratum of unit-area Abelian differentials.
As quoted from a source consulted: "Masur [17] and Veech [25] independently showed the Teichmüller
geodesic flow is ergodic with respect to $\mu_Q$ and even mixing."

**Common misuse.** Ergodicity is on each **connected component** of each stratum, not on the whole
stratum (which by §4.2 can be disconnected). This mattered historically — the KZ classification
came after.

**Source.** H. Masur, *Interval exchange transformations and measured foliations*, Ann. of Math.
**115** (1982), 169–200; W. Veech, *Gauss measures for transformations on the space of interval
exchange maps*, Ann. of Math. **115** (1982), 201–242. Quoted phrasing from
https://arxiv.org/html/math/0506158v4

---

### 4.4 Kerckhoff–Masur–Smillie (1986)

**Statement.** For any translation surface (equivalently, any holomorphic quadratic differential),
the directional flow is uniquely ergodic in almost every direction $\theta$ (with respect to
Lebesgue measure on $S^1$). Consequently the billiard flow in a rational polygon is uniquely
ergodic in almost every direction.

**Verification caveat.** The Annals page for this paper carries no abstract, and the theorem
statement above is the standard formulation as universally cited; the printed statement was **not**
read directly. Bibliographic data is confirmed.

**Source.** S. Kerckhoff, H. Masur, J. Smillie, *Ergodicity of billiard flows and quadratic
differentials*, Ann. of Math. (2) **124** (1986), no. 2, 293–311, DOI 10.2307/1971280,
https://annals.math.princeton.edu/1986/124-2/p04

---

### 4.5 Masur's criterion (1992)

**Statement (as quoted in a source consulted).** Masur's criterion for unique ergodicity "asserts
that $\mathcal{F}_v$ is uniquely ergodic as soon as $X_t$ has an accumulation point in the moduli
space of compact Riemann surfaces." I.e.: if the Teichmüller geodesic $g_t(X,\omega)$ is recurrent
to a compact subset of the moduli space (does not diverge to infinity), then the vertical
foliation of $(X,\omega)$ is uniquely ergodic.

**Common misuse — verified pitfall.** **The converse is false.** There exist divergent Teichmüller
geodesics whose vertical foliation is uniquely ergodic (Cheung–Eskin, *A divergent Teichmüller
geodesic with uniquely ergodic vertical foliation*, arXiv:math/0501296). So Masur's criterion is a
sufficient condition only; "uniquely ergodic $\Rightarrow$ recurrent" is wrong.

**Source.** H. Masur, *Hausdorff dimension of the set of nonergodic foliations of a quadratic
differential*, Duke Math. J. **66** (1992), 387–442. Phrasing quoted from
https://arxiv.org/html/math/0608004v1 . Converse failure: https://arxiv.org/html/math/0501296

