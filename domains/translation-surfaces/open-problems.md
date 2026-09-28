# Open problems and active directions in illumination (§5)

Split from `theorems.md` on 2026-09-24, section numbers kept. Read `theorems/INDEX.md` first: it holds how to read an entry (quoted vs paraphrased) and the standing notation. This file sits at the pack root; the §1-§4 and §6 files are in `theorems/`.

## 5. Open problems / active directions in illumination

Marked by how firmly each is established as open.

**(a) Is 22 the minimal number of sides of a polygon with a non-illuminating pair?** *Open.*
Wolecki proves only the upper bound $\le 22$ (Theorem 1.3) and establishes no lower bound; Monteil
independently found a (unpublished) 22-gon. No source consulted claims optimality.
*Source:* Wolecki, arXiv:1905.09358, §3 and Theorem 1.3.

**(b) Illumination in irrational polygons.** *Wide open.* Every finiteness result above (LMW
Cor. 3, Wolecki Thm 1.2, Apisa–Wright Thm 1.1) depends on the unfolding construction and therefore
on rationality. Nothing is known, by these methods, for a polygon with an irrational angle. This
is the single largest gap in the theory.
*Source:* inferred from the hypotheses of every theorem in §1 — no source consulted states a
result for irrational polygons.

**(c) Effective bounds.** *Open.* Every finiteness statement downstream of Eskin–Mirzakhani /
Eskin–Mirzakhani–Mohammadi is **ineffective**: there is no known bound on how many points can fail
to be illuminated from a given $x$ on a genus-$g$ surface, nor on the number of unilluminated
pairs in an $N$-gon, in terms of $g$ or $N$. LMW/Wolecki explicitly state their reliance on
[EM]/[EMM], which supply no effective constants.
*Source:* LMW abstract ("Our results crucially rely on the recent breakthrough results of
Eskin–Mirzakhani [EM] and Eskin–Mirzakhani–Mohammadi [EMM]"); Wolecki abstract (same). The
ineffectivity of EMM is standard but is my inference from the structure of those proofs, not a
quoted claim — flagged in §6.

**(d) Classification of unilluminable rational polygons.** *Open; no classification exists.* The
theory gives finiteness of the bad set, plus the Apisa–Wright trichotomy for *finite blocking*
(§1.8), plus complete answers on specific families (regular/double $n$-gon surfaces §1.12; genus
two §1.13). But there is no classification of which rational polygons possess a non-illuminating
pair, and no source consulted claims one.
*Source:* absence across LMW, Wolecki, Apisa–Wright, HST; Wolecki's own framing is a finiteness
theorem plus one construction, not a classification.

**(e) Determining periodic points on a given invariant subvariety.** *Active.* This is the
computational bottleneck for turning §1.9–§1.10 into concrete illumination statements. Solved for:
regular/double $n$-gons ($n\ge5$, $n\ne6$) [Apisa–Saavedra–Zhang]; primitive genus two
[Apisa, Möller]; strata components [Apisa]; higher-rank quadratic-differential loci
[Apisa–Wright Thm 1.4]. Open in general.
*Source:* §1.9–§1.14 above.

**(f) Structure of the unilluminated set on non-torus-cover translation surfaces.** *Partially
open.* LMW Theorem 2 says the unilluminated-pair set is a finite set plus finitely many embedded
translation surfaces $M'$ with both projections finite covers. LMW's own listed open questions
(their §6.4) are about the possible "slopes" $\lambda$ of these pieces:
- "It would be interesting to know whether other slopes are possible. In particular, do the cases
  $\lambda = 0$, $\lambda = \infty$ actually arise in connection with blocking configurations? Do
  positive rational slopes arise, except for $\lambda = 1$?"
- "Is it possible that $\lambda$ is irrational?"
- "In the last assertion of Lemma 7, can we take $\ell = n$?"
*Source:* arXiv:1407.2975, §6.4.

**(g) Does Veech's dichotomy characterize any natural class?** Smillie–Weiss (2008) showed it does
*not* characterize lattice surfaces. Characterizing the surfaces satisfying the dichotomy remains
open as far as the sources consulted indicate (cf. M. Cohen's thesis title, "Looking for a Billiard
Table which is not a Lattice Polygon but Satisfies Veech's Dichotomy," arXiv:1011.3217).

**(h) Curved / non-polygonal illumination.** Adjacent active direction: Castle (formerly Wright),
*Unilluminable rooms, billiards with hidden sets, and Bunimovich mushrooms*, arXiv:1703.02268 —
constructs convex, everywhere-differentiable billiard tables with dark regions, generalizing
beyond the ellipse-based Penrose examples. Not a translation-surface result.

