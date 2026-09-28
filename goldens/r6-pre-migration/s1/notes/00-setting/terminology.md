# Terminology that must not drift

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

Parking garage $P$ versus unfolding $M$, rectangle-tiled, normal origami, translation automorphisms, and the three senses of "primitive".

---

## [R §0.1] Terminology that must not drift

**Two different objects.** Throughout, $P$ is a **parking garage** and $M$ is its
**unfolding**. They are not the same kind of object and their definitions differ:

- $P$ is a compact connected surface *with boundary* carrying an immersion
  $h:P\to\mathbb{R}^2$. Because $h$ is an immersion it is a local diffeomorphism,
  so the pullback flat structure on $P$ has **no interior cone points**. Its
  *boundary corners*, however, may have any angle in $\tfrac\pi2\mathbb{Z}$,
  including angles $\ge 2\pi$: $h$ is not required to be injective, so the surface
  may wrap over itself (a ramp). $P$ is not a closed translation surface.
- $M$ is a **closed** translation surface, obtained from $P$ by the unfolding
  construction, and it **does** have cone points. It is $M$ that is the origami,
  and $M$ whose monodromy is $(\sigma,\tau)$.

Proposition 1.6 is the dictionary between the corners of $P$ and the cone points
of $M$. Never transfer a statement about one to the other without it.

**Parking garage (Cohen–Weiss, arXiv:1101.3772, verbatim).** "an immersion
$h:N\to\mathbb{R}^2$, where $N$ is a two dimensional compact connected manifold
with boundary, and $h(\partial N)$ is a finite union of linear segments." A
polygon is the case where $h$ is an **embedding**; rational polygons are a subset
of rational parking garages. The immersion hypothesis is what forbids interior
cone points while still permitting non-injectivity, hence ramp corners of angle
$2\pi$, $4\pi$, … on the boundary.

**Rectangle-tiled.** $P$ is tiled by rectangles with vertices on a common lattice;
after normalisation this is a tiling by unit squares (subdividing adds only
corners that are already marked), which is what makes $M$ an origami.

**Normal origami.** $M$ is *normal* (= regular = Galois) if the covering
$M\setminus p^{-1}(0) \to \mathbb{T}^2\setminus\{0\}$ is normal; equivalently $G$
acts regularly on $\Omega$ (transitively and freely); equivalently $|G| = n$. Then
$\Omega \cong G$ with $\sigma,\tau$ acting by left multiplication and the deck
group ($\cong G$, acting by translations of $M$) by right multiplication.

**Translation automorphisms.** The translation (deck) group of the origami is
$C_{S_n}(G)$ acting on the fibre; it is semiregular since $G$ is transitive.

**"Primitive" — three inequivalent senses, all in circulation.** Say which one is
meant every time.

1. *Primitive permutation group*: $G$ has no nontrivial block system on $\Omega$.
   By the Galois correspondence this says exactly that **$M$ admits no nontrivial
   intermediate origami** $M \to M' \to \mathbb{T}^2$ (the sense used in S1 §3.5–3.6).
2. *Primitive translation surface*: admits no translation map to a surface of
   lower genus (Hubert–Schmoll–Troubetzkoy; reference sheet §1.6).
3. *Primitive square-tiled surface*: $\Lambda(\omega) = \mathbb{Z}^2$
   (Hubert–Lelièvre; their Lemma 2.2: $n$ prime implies it).

These differ: the $2\times1$ rectangle unfolding has $\Lambda(\omega)=\mathbb{Z}^2$
(sense 3) but imprimitive monodromy (not sense 1). ⚠ Which sense Zmiaikou's
dichotomy uses is **not verified here**; nothing below depends on it (Remark 5.2).
