# Theorem reference sheet: index

A precise-hypotheses reference for research on illumination, finite blocking, and the
Teichmüller-dynamics machinery routinely invoked in that literature.

**How to read this file.**
- Every statement below was checked against a primary source (arXiv HTML/ar5iv, publisher
  page, or author's posted PDF) during compilation. Sources are given per entry.
- Text in quotation marks is verbatim from the cited source. Text not in quotation marks is
  a faithful restatement; treat quoted text as citable and unquoted text as a paraphrase to
  re-check against the source before it goes into a paper.
- **Common misuse** fields are filled in *only* where the pitfall was verifiable from a
  source (e.g. a paper explicitly saying "this fails if you drop X"). Where no such note
  appears, none was verified — that does not mean the theorem has no pitfalls.
- A final section flags everything that could not be verified.

**Standing notational conventions used throughout.**
- $M$ or $(X,\omega)$: a translation surface (a nonzero Abelian differential $\omega$ on a
  compact Riemann surface $X$). $\Sigma$ denotes its set of singularities (zeros of $\omega$,
  plus marked points where relevant).
- $G = \mathrm{SL}(2,\mathbb{R})$; $P \subset G$ the upper-triangular subgroup;
  $a_t = \mathrm{diag}(e^t, e^{-t})$, $r_\theta$ rotation, $u_t = \begin{pmatrix}1&t\\0&1\end{pmatrix}$.
- $\mathcal{H}(k_1,\dots,k_n)$: stratum of Abelian differentials with zeros of orders $k_i$,
  $\sum k_i = 2g-2$; $\mathcal{H}_1(\alpha)$ its unit-area locus.
- $\mathrm{Aff}^+(X,\omega)$: group of orientation-preserving affine diffeomorphisms;
  $\mathrm{SL}(X,\omega)$: its derivative image, the **Veech group**.
- $\mathcal{M}$ (script M): an affine invariant submanifold / invariant subvariety.


## Where each entry is

Read the one file holding the entry you need. Section numbers are those of the former single `theorems.md`. Files are relative to this `theorems/` folder of the translation-surfaces domain pack; role plugins reach them through `domain_get` (file `theorems/<topic>.md`).

**`illumination.md`** (26 KB), §1. Illumination & blocking
- 1.0 Basic definitions (as fixed by Lelièvre–Monteil–Weiss)
- 1.1 Blocking dichotomy (Lelièvre–Monteil–Weiss, 2016)
- 1.2 Everything is illuminated (Lelièvre–Monteil–Weiss, 2016)
- 1.3 Illumination in rational polygons (Lelièvre–Monteil–Weiss, 2016)
- 1.4 Finiteness of unilluminated *pairs* in rational polygons (Wolecki, 2019)
- 1.5 Small unilluminable polygons (Tokarsky 1995; Castro 1997; Wolecki 2019)
- 1.6 Illumination on Veech / prelattice surfaces (Hubert–Schmoll–Troubetzkoy, 2008)
- 1.7 Finite blocking and pure periodicity (Monteil)
- 1.8 Finite blocking in rational polygons — the trichotomy (Apisa–Wright, 2021)
- 1.9 Periodic points and torus covers (attributed to Eskin–Filip–Wright)
- 1.10 Classification of markings; blocking on non-torus-cover orbit closures (Apisa–Wright)
- 1.11 Illumination / blocking on *generic* translation surfaces (Apisa, 2020)
- 1.12 Illumination/blocking on specific Veech surfaces: regular and double $n$-gons
- 1.13 Periodic points and blocking in genus two (Apisa)
- 1.14 Periodic points on Veech surfaces (Möller, 2006)

**`orbit-closures.md`** (16 KB), §2. Orbit closures & measure classification
- 2.1 Eskin–Mirzakhani measure classification (2018)
- 2.2 Eskin–Mirzakhani–Mohammadi orbit closure theorem (2015)
- 2.3 Cylinder Deformation Theorem (Wright, 2015)
- 2.4 Field of definition of an affine invariant submanifold (Wright, 2014)
- 2.5 Rank of an affine invariant submanifold
- 2.6 Boundary of an affine invariant submanifold (Mirzakhani–Wright, 2017)
- 2.7 Full rank affine invariant submanifolds (Mirzakhani–Wright, 2018)
- 2.8 High rank invariant subvarieties (Apisa–Wright, 2023)
- 2.9 Algebraic hull and finiteness (Eskin–Filip–Wright, 2018)

**`veech.md`** (9 KB), §3. Veech surfaces & the dichotomy
- 3.1 The Veech dichotomy (Veech, 1989)
- 3.2 Characterizations of lattice surfaces (Smillie–Weiss, 2010)
- 3.3 Translation coverings, balanced coverings, and Veech groups
- 3.4 Arithmetic Veech groups = square-tiled surfaces (Gutkin–Judge)

**`strata.md`** (6 KB), §4. Strata, period coordinates & background
- 4.1 Strata, dimension, and period coordinates
- 4.2 Kontsevich–Zorich classification of connected components (2003)
- 4.3 Masur–Veech ergodicity (1982)
- 4.4 Kerckhoff–Masur–Smillie (1986)
- 4.5 Masur's criterion (1992)

**`../open-problems.md`** (4 KB, at the pack root), §5. Open problems / active directions in illumination

**`unverified.md`** (5 KB), §6. UNVERIFIED — check before citing

A new entry goes in its topic file as the next number of its section, with its source; an unverified one goes in `unverified.md`.
