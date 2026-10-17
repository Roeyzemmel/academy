# The hypothesis check

Written at the point of use, for every cited result a step rests on. The statement comes
from the card or the cached text (`library_lookup`), never from memory; whatever is
not quoted is marked `[CHECK]` (`SKILL.md`, "The `[CHECK]` marker").

## Form

```
Result:   bib:<key>#<pinpoint>, <version>, read_from: source | extraction
Statement, hypotheses, one per line:
  H1. ...
  H2. ...  [CHECK]
Conclusion: ...

For our objects (<what they are>):
  H1  holds        <why, one line>
  H2  needs an argument   <the argument, or the gap it leaves>
  H3  fails        <what this does to the step>
Parts still from memory: <the [CHECK] lines, or "none">
```

Rules:

- Every hypothesis the source states gets its own line and its own verdict, including
  standing assumptions inherited from the section or the paper's conventions.
- "Holds" carries its reason. A hypothesis that "holds" without a reason is `needs an
  argument`.
- If a hypothesis fails, say whether a different or weaker citation covers the case
  (often the real theorem is one you did not need), or whether the step becomes an input
  named in `modulo`.
- Compare the stated conclusion with what you use: using more than the source concludes
  is a misapplied citation.

## Resolving a `[CHECK]`

File a `cite` ticket to the Expert. The `clerk` returns the verbatim statement and
hypotheses from the card with its `version` and `read_from`, or says the card is
missing. Replace each marker by the quote and redo the verdicts the quote changes. A
part nobody can verify stays marked and keeps the step an unverified input.

## Example (shape only: its recalled details are exactly what `[CHECK]` is for)

Citing the orbit-closure theorem of Eskin-Mirzakhani-Mohammadi for a square-tiled
surface in H(2):

```
Result:   bib:EMM15#[CHECK pinpoint], [CHECK version]
  H1. X is a compact Riemann surface and omega a nonzero holomorphic 1-form.
  H2. (X, omega) lies in a stratum H(alpha), at unit area  [CHECK: GL+ vs SL(2,R),
      area normalisation as the paper states it]
  H3. No genericity, finite-type or Veech assumption.
Conclusion: the SL(2,R)-orbit closure is an affine invariant submanifold
  [CHECK: the paper's exact definition; immersed rather than embedded]

For a square-tiled surface in H(2):
  H1  holds   a branched cover of the square torus, compact, holomorphic form
  H2  holds   in H(2); rescale to unit area (say so)
  H3  holds   vacuous: the theorem assumes nothing more
Parts still from memory: the three [CHECK] items above.
```

The check also shows the citation is overpowered here: a square-tiled surface has a closed
orbit (its Veech group has finite index in SL(2,Z)), so the orbit closure is the orbit
and a lighter citation suffices.
