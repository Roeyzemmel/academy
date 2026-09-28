# Orbit closures and measure classification (§2)

Split from `theorems.md` on 2026-09-24, section numbers kept. Read `INDEX.md` first: it holds how to read an entry (quoted vs paraphrased) and the standing notation.

## 2. Orbit closures & measure classification

### 2.1 Eskin–Mirzakhani measure classification (2018)

**Statement.** *Theorem 1.4.* "Let $\nu$ be any ergodic $P$-invariant probability measure on
$\mathcal{H}_1(\alpha)$. Then $\nu$ is $\mathrm{SL}(2,\mathbb{R})$-invariant and affine."

**Notation used.**
- $P = AN$: "the set of upper triangular matrices of determinant 1 in
  $\mathrm{SL}(2,\mathbb{R})$", where $A = \{\mathrm{diag}(e^t,e^{-t})\}$ and $N$ is the upper
  unipotent subgroup.
- *Definition 1.1 (affine measure).* An ergodic $\mathrm{SL}(2,\mathbb{R})$-invariant probability
  measure $\nu_1$ on $\mathcal{H}_1(\alpha)$ is **affine** if (i) its support $\mathcal{M}_1$ is
  an immersed submanifold whose self-intersection locus has $\nu_1$-measure zero, and locally its
  image is "a complex linear subspace defined over $\mathbb{R}$ in the period coordinates";
  (ii) with $\mathcal{M} = \mathbb{R}\mathcal{M}_1$ and $d\nu = d\nu_1\,da$, the local restriction
  of $\nu$ is "an affine linear measure in the period coordinates", i.e. the restriction of
  Lebesgue measure to that subspace.
- *Definition 1.2 (affine invariant submanifold).* "Any suborbifold $\mathcal{M}_1$ for which
  there exists a measure $\nu_1$ such that the pair $(\mathcal{M}_1,\nu_1)$ satisfies (i) and (ii)."

**Common misuse.** (a) The theorem is about **$P$-invariant** measures; the conclusion (not the
hypothesis) is $\mathrm{SL}(2,\mathbb{R})$-invariance — this is the whole point and citing it as
"classification of $\mathrm{SL}(2,\mathbb{R})$-invariant measures" understates it. (b) The
hypothesis is a *probability* measure; there is no classification of infinite invariant measures.
(c) The linear equations defining an AIS are **real** linear in complex period coordinates, i.e.
the tangent space is $\mathbb{C}$-linear and defined over $\mathbb{R}$; "linear subvariety" in
this sense is not the same as an algebraic subvariety statement (that is Filip's theorem).

**Source.** A. Eskin, M. Mirzakhani, *Invariant and stationary measures for the
$\mathrm{SL}(2,\mathbb{R})$ action on Moduli space*, Publ. Math. IHÉS **127** (2018), 95–324,
DOI 10.1007/s10240-018-0099-2, https://www.numdam.org/item/PMIHES_2018__127__95_0/ ;
arXiv:1302.3320.

---

### 2.2 Eskin–Mirzakhani–Mohammadi orbit closure theorem (2015)

**Statement.** *Theorem 2.1.* "Suppose $x \in \mathcal{H}_1(\alpha)$. Then, the orbit closure
$\overline{Px} = \overline{\mathrm{SL}(2,\mathbb{R})x}$ is an affine invariant submanifold of
$\mathcal{H}_1(\alpha)$."

*Theorem 2.2.* "Any closed $P$-invariant subset of $\mathcal{H}_1(\alpha)$ is a finite union of
affine invariant submanifolds."

*Theorem 2.3.* "Let $\mathcal{N}_n$ be a sequence of affine manifolds, and suppose
$\nu_{\mathcal{N}_n} \to \nu$. Then $\nu$ is a probability measure. Furthermore, $\nu$ is the
affine measure $\nu_{\bar{\mathcal{N}}}$, where $\bar{\mathcal{N}}$ is the smallest submanifold
with the following property: there exists some $n_0 \in \mathbb{N}$ such that
$\mathcal{N}_n \subset \bar{\mathcal{N}}$ for all $n > n_0$." (This is the *isolation* statement.)

*Theorem 2.6 (equidistribution of circle averages).* "Suppose $x \in \mathcal{H}_1(\alpha)$ and
let $\mathcal{M}$ be an affine invariant submanifold of minimum dimension which contains $x$. Then
for any $\varphi \in C_c(\mathcal{H}_1(\alpha))$, and any interval $I \subset [0,2\pi)$,
$$\lim_{T\to\infty}\frac{1}{T}\int_0^T \frac{1}{|I|}\int_I \varphi(a_t r_\theta x)\,d\theta\,dt = \int_{\mathcal{M}} \varphi\, d\nu_{\mathcal{M}}.$$"

*Theorem 2.7.* Uniform version of 2.6: "Let $\mathcal{M}$ be an affine invariant submanifold. Then
for any $\varphi \in C_c(\mathcal{H}_1(\alpha))$ and any $\epsilon > 0$ there are affine invariant
submanifolds $\mathcal{N}_1,\dots,\mathcal{N}_\ell$ properly contained in $\mathcal{M}$ such that
for any compact subset $F \subset \mathcal{M}\setminus(\cup_{j}\mathcal{N}_j)$ there exists $T_0$ so
that for all $T > T_0$ and any $x \in F$,
$\left|\frac{1}{T}\int_0^T\frac{1}{|I|}\int_I \varphi(a_t r_\theta x)d\theta\,dt - \int_{\mathcal{M}}\varphi\,d\nu_{\mathcal{M}}\right| < \epsilon.$"

*Theorem 2.8 (random walk averages).* For $\mu$ a compactly supported, Haar-absolutely-continuous
probability measure on $\mathrm{SL}(2,\mathbb{R})$, and $\mathcal{M}$ the minimal-dimension AIS
containing $x$: $\lim_{n\to\infty}\frac1n\sum_{k=1}^n\int_{\mathrm{SL}(2,\mathbb{R})}\varphi(gx)\,d\mu^{(k)}(g) = \int_{\mathcal{M}}\varphi\,d\nu_{\mathcal{M}}$.
*Theorem 2.9* is its uniform version.

*Abstract (verbatim).* "We prove results about orbit closures and equidistribution for the
$\mathrm{SL}(2,\mathbb{R})$ action on the moduli space of compact Riemann surfaces, which are
analogous to the theory of unipotent flows. The proofs of the main theorems rely on the measure
classification theorem of the first two authors and a certain isolation property of closed
$\mathrm{SL}(2,\mathbb{R})$ invariant manifolds developed in this paper."

**Common misuse.** (a) **Theorem 2.6 is a Cesàro (time-)averaged circle-average statement**, not
the un-averaged $\lim_{t\to\infty}\frac{1}{2\pi}\int_0^{2\pi}\varphi(a_t r_\theta x)\,d\theta$.
Papers that need the un-averaged version must cite the later strengthening (Chaika–Eskin or the
relevant follow-up), not EMM Theorem 2.6. (b) Everything is **ineffective**: no bound on any
constant, no bound on the "how long until equidistribution" time, no bound on the number/degree
of the exceptional $\mathcal{N}_j$. Every illumination finiteness result downstream of EMM
inherits this ineffectivity (see §5). (c) Theorem 2.2 is about closed $P$-invariant *subsets* —
a stronger statement than about single orbit closures.

**Source.** A. Eskin, M. Mirzakhani, A. Mohammadi, *Isolation, equidistribution, and orbit closures
for the $\mathrm{SL}(2,\mathbb{R})$ action on moduli space*, Ann. of Math. (2) **182** (2015),
no. 2, 673–721, DOI 10.4007/annals.2015.182.2.7,
https://annals.math.princeton.edu/wp-content/uploads/annals-v182-n2-p07-p.pdf ; arXiv:1305.3015.

---

### 2.3 Cylinder Deformation Theorem (Wright, 2015)

**Statement (introduction form, Theorem 1.1).** "Let $M$ be a translation surface, and let
$\mathcal{C}$ be the collection of all horizontal cylinders on $M$. Then for all
$s,t \in \mathbb{R}$, the surface $a_s^{\mathcal{C}}(u_t^{\mathcal{C}}(M))$ remains in the
$\mathrm{GL}^+(2,\mathbb{R})$-orbit closure of $M$."

**Statement (refined form, in the body of the paper — numbered Theorem 5.1 per the source fetch).**
"Let $\mathcal{M}$ be an affine invariant submanifold. Suppose that $\mathcal{C}$ is an
equivalence class of $\mathcal{M}$-parallel horizontal cylinders on $M \in \mathcal{M}$. Then for
all $s,t \in \mathbb{R}$, the surface $a_s^{\mathcal{C}}(u_t^{\mathcal{C}}(M)) \in \mathcal{M}$."

**Notation used.**
- *Definition 4.6.* "Two cylinders on $M \in \mathcal{M}$ are $\mathcal{M}$-*parallel* if they are
  parallel at $M$ and at every nearby $M' \in \mathcal{M}$."
- *Theorem 4.7.* "Two cylinders are $\mathcal{M}$-parallel if and only if their core curves are
  $\mathcal{M}$-collinear."
- Equivalent formulation used by Mirzakhani–Wright: two cylinders are $\mathcal{M}$-parallel if
  there is a linear relation $\int_\alpha \omega = c \int_\beta \omega$ ($c \in \mathbb{R}$)
  holding locally on $\mathcal{M}$ between their core curves.
- *Cylinder shear* $u_t^{\mathcal{C}}(M)$: apply $u_t$ linearly to the rectangles giving the
  cylinders in $\mathcal{C}$, not to the rest, then reglue. *Cylinder stretch*
  $a_t^{\mathcal{C}}(M)$: apply $a_t$ only to the cylinders in $\mathcal{C}$.
- *Theorem 1.5.* "If $\dim_{\mathbb{C}} p(T(\mathcal{M})) = 2$, then every translation surface in
  $\mathcal{M}$ is completely periodic." *Corollary 1.6.* "All translation surfaces in all the
  Prym eigenform loci are completely periodic."

**Common misuse.** The **refined** version is the one almost always needed and the one that has
the $\mathcal{M}$-parallel hypothesis. The class $\mathcal{C}$ must be a **full equivalence class**
of $\mathcal{M}$-parallel cylinders — deforming an arbitrary sub-collection of parallel cylinders
does *not* stay in $\mathcal{M}$. Note also that "parallel on $M$" is not enough: parallelism must
persist on all nearby surfaces in $\mathcal{M}$.

**Numbering caveat.** The intro statement is Theorem 1.1 in both arXiv and published versions; the
refined statement's number (reported as Theorem 5.1) was obtained by machine extraction from the
author's posted PDF and **should be re-checked** against the printed Geom. Topol. version before
citing a number. Citing it as "Wright's Cylinder Deformation Theorem [Wri15]" is safe.

**Source.** A. Wright, *Cylinder deformations in orbit closures of translation surfaces*,
Geom. Topol. **19** (2015), no. 1, 413–438, DOI 10.2140/gt.2015.19.413; arXiv:1302.4108,
https://ar5iv.arxiv.org/html/1302.4108 ; https://public.websites.umich.edu/~alexmw/Cylinder.pdf

---

### 2.4 Field of definition of an affine invariant submanifold (Wright, 2014)

**Statement.** *Theorem 1.1.* "The field of definition $k(\mathcal{M})$ of an affine invariant
submanifold $\mathcal{M}$ is a real number field of degree at most the genus. It is equal to the
intersection of the holonomy fields of all translation surfaces in $\mathcal{M}$."

*Theorem 1.5 (semisimple decomposition).* For an affine invariant submanifold $\mathcal{M}$,
"there is a semisimple flat bundle $W$, and for each field embedding
$\rho : k(\mathcal{M}) \to \mathbb{C}$ there is a flat simple bundle $V_\rho$ which is Galois
conjugate to $V_{\mathrm{Id}}$, so that $H^1 = (\oplus_\rho V_\rho) \oplus W$."

*Corollary 1.3.* Translation surfaces with $\mathcal{M}$-typical periods form a full-measure
subset of $\mathcal{M}$, and each such surface is $\mathcal{M}$-generic (its orbit closure is
$\mathcal{M}$).

**Notation used.** "*Field of definition* $k(\mathcal{M})$: the smallest subfield of $\mathbb{R}$
such that $\mathcal{M}$ can be defined in local period coordinates by linear equations with
coefficients in this field." "*Affine invariant submanifold*: an immersed manifold
$\mathcal{M} \hookrightarrow \mathcal{H}$ such that each point of $\mathcal{M}$ has a neighborhood
whose image is locally defined by real linear equations in period coordinates."

**Common misuse.** The degree bound is **at most the genus $g$**, not $2g$, and it is a bound on
$[k(\mathcal{M}):\mathbb{Q}]$, not on the trace field of any particular Veech group inside.

**Source.** A. Wright, *The field of definition of affine invariant submanifolds of the moduli
space of abelian differentials*, Geom. Topol. **18** (2014), no. 3, 1323–1341,
DOI 10.2140/gt.2014.18.1323; arXiv:1210.4806; https://websites.umich.edu/~alexmw/numfield.pdf

---

### 2.5 Rank of an affine invariant submanifold

**Definition.** The **rank** of an affine invariant submanifold $\mathcal{M}$ is
$\tfrac12 \dim_{\mathbb{C}} p\big(T(\mathcal{M})\big)$, where
$p : H^1(X,\Sigma;\mathbb{C}) \to H^1(X;\mathbb{C})$ is the natural projection from relative to
absolute cohomology.

**Notes.** $p(T(\mathcal{M}))$ is symplectic, so the dimension is even and the rank is a positive
integer. Rank $1$ = Teichmüller curves and their relatives; rank $g$ = "full rank." Rank is
insensitive to relative (marked-point) directions — two invariant subvarieties differing only by
marked points have the same rank. This is exactly why the marked-point papers (§1.10, §1.11)
are needed to translate rank statements into illumination statements.

**Source.** Mirzakhani–Wright, *The boundary of an affine invariant submanifold*,
https://public.websites.umich.edu/~alexmw/Boundary.pdf ; Apisa–Wright,
https://arxiv.org/html/2409.07603 ("The rank of $\mathcal{M}$ is defined to be half of the
dimension of the image").

---

### 2.6 Boundary of an affine invariant submanifold (Mirzakhani–Wright, 2017)

**Statement.** *Abstract (verbatim).* "We study the boundary of an affine invariant submanifold of
a stratum of translation surfaces in a partial compactification consisting of all finite area
Abelian differentials over nodal Riemann surfaces, modulo zero area components. The main result is
a formula for the tangent space to the boundary. We also prove finiteness results concerning
cylinders, a partial converse to the Cylinder Deformation Theorem, and a result generalizing part
of the Veech dichotomy."

*Main theorem (informal form as extracted).* The tangent space of a boundary component
$\mathcal{M}_i$ is the intersection of the tangent space to $\mathcal{M}$ with the tangent space
to the boundary stratum.

*Corollary.* Each boundary component $\mathcal{M}_i$ has strictly smaller dimension than
$\mathcal{M}$, rank at most that of $\mathcal{M}$, and the same field of definition.

**Notation used.** The partial compactification ("WYSIWYG"): a *multicomponent translation
surface* is $(X,\omega,\Sigma)$ with $X$ compact with finitely many components, $\omega$ a nonzero
Abelian differential on each, $\Sigma$ marking zeros. Convergence is defined by diffeomorphisms
$g_n : X\setminus U_n \to X_n$ with $g_n^*\omega_n \to \omega$ compactly on $X\setminus\Sigma$ and
injectivity radii off the image tending uniformly to $0$.

**Numbering caveat.** The theorem/corollary numbers in the intro were extracted mechanically and
should be re-checked. The abstract is verbatim from the publisher page.

**Source.** M. Mirzakhani, A. Wright, *The boundary of an affine invariant submanifold*,
Invent. Math. **209** (2017), no. 3, 927–984, DOI 10.1007/s00222-017-0722-8,
https://link.springer.com/article/10.1007/s00222-017-0722-8

---

### 2.7 Full rank affine invariant submanifolds (Mirzakhani–Wright, 2018)

**Statement.** *Abstract (verbatim).* "We show that every $\mathrm{GL}(2,\mathbb{R})$ orbit
closure of translation surfaces is either a connected component of a stratum, the hyperelliptic
locus, or consists entirely of surfaces whose Jacobians have extra endomorphisms." The paper also
notes an application to polygonal billiards: infinitely many rational triangles unfold to surfaces
with dense $\mathrm{GL}(2,\mathbb{R})$ orbit.

**Common misuse.** The trichotomy is about orbit closures, and the third alternative ("extra
endomorphisms") is a genuinely open-ended class, not a classification. Also note this is *not* the
statement "full rank ⟹ stratum component or hyperelliptic locus" without qualification: the
rank condition and the marked-point convention matter; consult the paper.

**Source.** M. Mirzakhani, A. Wright, *Full rank affine invariant submanifolds*,
Duke Math. J. **167** (2018), no. 1, 1–40, DOI 10.1215/00127094-2017-0036; arXiv:1608.02147.

---

### 2.8 High rank invariant subvarieties (Apisa–Wright, 2023)

**Statement.** *Abstract (verbatim).* "We classify $\mathrm{GL}(2,\mathbb{R})$ orbit closures of
translation surfaces of rank at least half the genus plus 1." I.e. rank $\ge g/2 + 1$.

**Source.** P. Apisa, A. Wright, *High rank invariant subvarieties*, Ann. of Math. (2) **198**
(2023), no. 2, 657–726, https://annals.math.princeton.edu/2023/198-2/p04 ; arXiv:2102.06567;
https://websites.umich.edu/~alexmw/highrank.pdf

---

### 2.9 Algebraic hull and finiteness (Eskin–Filip–Wright, 2018)

**Statement.** *Abstract (verbatim).* "We compute the algebraic hull of the Kontsevich–Zorich
cocycle over any $\mathrm{GL}^+_2(\mathbb{R})$ invariant subvariety of the Hodge bundle, and
derive from this finiteness results on such subvarieties."

*Theorem 1.5 (finiteness, as extracted).* In each stratum of Abelian differentials, all but
finitely many affine invariant submanifolds have rank 1 and degree at most 2; and in each genus
there is a finite collection of rank-2, degree-1 affine invariant submanifolds $\mathcal{M}$ such
that all but finitely many rank-1, degree-2 affine invariant submanifolds are codimension-2
subvarieties of one of these $\mathcal{M}$.

**Numbering / statement caveat.** The Theorem 1.5 wording above is a machine extraction and the
terms "degree" and the exact quantifiers should be re-read in the source before citing.

**Source.** A. Eskin, S. Filip, A. Wright, *The algebraic hull of the Kontsevich–Zorich cocycle*,
Ann. of Math. (2) **188** (2018), no. 1, 281–313,
https://annals.math.princeton.edu/wp-content/uploads/annals-v188-n1-p05-p.pdf ; arXiv:1702.02074.

