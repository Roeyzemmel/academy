# Pure-Python fallbacks, no Sage (§8)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

## 8. Pure-Python fallbacks (no Sage) — tested in this session

Both programs below were **executed** in this session on CPython 3.11 with only the standard
library. Their printed output is reproduced verbatim.

### 8.1 Exact illumination on a square-tiled surface

This is the one that matters. On an origami the question "which holonomy vectors join
`p = (square s, (x, y))` to `q = (square t, (x', y'))`?" has an exact, complete answer with no
floating point at all, because of a small observation:

> A straight segment from `(s, (x,y))` ends at `(t, (x',y'))` only if its holonomy `(a, b)`
> satisfies `a ∈ x'-x+Z` and `b ∈ y'-y+Z`. So the candidate holonomies form a **translate of Z²**,
> and one only has to decide, for each candidate, which square it lands in — a finite word in the
> gluing permutations `r`, `u`.

```python
"""Exact illumination probe on a square-tiled surface (origami).
Pure Python; only `fractions` and `math`.  An origami is a pair of permutations
(r, u) of {0,...,n-1}: square i is glued on the right to r(i), on top to u(i).
"""

from fractions import Fraction as F
import math


def inv_perm(p):
    q = [0] * len(p)
    for i, pi in enumerate(p):
        q[pi] = i
    return q


class Origami:
    def __init__(self, r, u):
        assert len(r) == len(u)
        assert sorted(r) == sorted(u) == list(range(len(r)))
        self.r, self.u = list(r), list(u)
        self.ri, self.ui = inv_perm(self.r), inv_perm(self.u)
        self.n = len(r)

    def develop(self, s, x, y, a, b):
        """Follow the segment from (s,(x,y)) by holonomy (a,b), all Fractions.
        Returns the terminal square, or None if the segment hits a vertex."""
        events = []
        if a != 0:
            lo, hi = (x, x + a) if a > 0 else (x + a, x)
            k = math.floor(lo) + 1
            while k <= hi:
                if lo < k < hi or k == hi:
                    t = F(k - x, 1) / a
                    if 0 < t <= 1:
                        events.append((t, "r" if a > 0 else "ri"))
                k += 1
        if b != 0:
            lo, hi = (y, y + b) if b > 0 else (y + b, y)
            k = math.floor(lo) + 1
            while k <= hi:
                if lo < k < hi or k == hi:
                    t = F(k - y, 1) / b
                    if 0 < t <= 1:
                        events.append((t, "u" if b > 0 else "ui"))
                k += 1
        events.sort(key=lambda e: e[0])
        for i in range(len(events) - 1):          # simultaneous crossings = a vertex
            if events[i][0] == events[i + 1][0]:
                return None
        cur = s
        for _, kind in events:
            cur = getattr(self, kind)[cur]
        return cur

    def connections(self, p, q, bound):
        """All holonomy vectors of length <= bound joining p to q.
        p, q are triples (square, x, y) with x, y Fractions in [0,1)."""
        s, x, y = p
        t, xp, yp = q
        a0, b0 = F(xp) - F(x), F(yp) - F(y)
        out = []
        M = int(math.floor(bound)) + 2
        for m in range(-M, M + 1):
            a = a0 + m
            if abs(a) > bound:
                continue
            rem2 = bound * bound - float(a) ** 2
            if rem2 < 0:
                continue
            K = int(math.floor(math.sqrt(rem2))) + 2
            for k in range(-K, K + 1):
                b = b0 + k
                if float(a) ** 2 + float(b) ** 2 > bound * bound:
                    continue
                if a == 0 and b == 0:
                    continue
                if self.develop(s, F(x), F(y), a, b) == t:
                    out.append((a, b))
        out.sort(key=lambda v: (float(v[0]) ** 2 + float(v[1]) ** 2))
        return out
```

Self-tests and their **actual output**:

```python
half, third, quart = F(1, 2), F(1, 3), F(1, 4)

# 1. torus: EVERY candidate vector must work
T = Origami([0], [0])
got = T.connections((0, third, quart), (0, F(1,5), F(2,7)), 5.0)
# -> torus: found 77 expected 77 -> True

# 2. the 3-square origami in H(2): r=(1,2), u=(1,3) in 1-based = [1,0,2],[2,1,0]
O = Origami([1, 0, 2], [2, 1, 0])
# connections by target square: {0: 64, 1: 63, 2: 72}  total 199
#   fractions: [0.322, 0.317, 0.362]
#   (disc of radius 8 has area ~201: every candidate lands somewhere, and the
#    three squares get roughly a third each -- a good consistency check)

# 3. vertex detection
T.develop(0, half, half, F(1), F(1)) is None      # True  -- passes through a corner
T.develop(0, half, half, F(1), F(0)) == 0         # True

# 4. reversal symmetry: connections p->q are exactly the negatives of q->p
#    -> True
```

Runtime: 0.08 s for all four tests.

**Why this is research-usable, not a toy:** it is exact (no epsilon anywhere), it is complete
within the bound (nothing is missed), and it correctly flags trajectories through singularities.
For an origami it answers "does `p` illuminate `q` within distance `L`?" definitively. Converting a
`surface_dynamics` origami to this format is `[o.r_tuple(), o.u_tuple()]` (0-based tuples on
`{0,...,n-1}`) — **[UNVERIFIED]**, `r_tuple`/`u_tuple` appear in the origami API list but I did
not see a doctest confirming the indexing base; check `o.r_tuple()` against `o.r()` once.

### 8.2 Float billiard tracer for an arbitrary polygon

For non-rational polygons, Tokarsky-style rooms, or a quick picture, a direct billiard simulation
is often all you need and needs nothing installed.

```python
import math

class Billiard:
    def __init__(self, vertices):
        self.V = [(float(x), float(y)) for (x, y) in vertices]
        self.n = len(self.V)

    def edge(self, i):
        return self.V[i], self.V[(i + 1) % self.n]

    def _hit(self, p, d, eps):
        best_t, best_i = None, None
        for i in range(self.n):
            (x1, y1), (x2, y2) = self.edge(i)
            ex, ey = x2 - x1, y2 - y1
            den = d[0]*ey - d[1]*ex
            if abs(den) < 1e-15:
                continue
            wx, wy = p[0]-x1, p[1]-y1
            t = (ex*wy - ey*wx) / den
            s = (d[0]*wy - d[1]*wx) / den
            if t > eps and -1e-9 <= s <= 1+1e-9:
                if best_t is None or t < best_t:
                    best_t, best_i = t, i
        return best_t, best_i

    def trajectory(self, p, theta, nbounces=200, eps=1e-9):
        """Billiard path from p in direction theta.  Stops at a corner."""
        d = (math.cos(theta), math.sin(theta))
        pts = [tuple(map(float, p))]
        cur = pts[0]
        for _ in range(nbounces):
            t, i = self._hit(cur, d, eps)
            if t is None:
                break
            q = (cur[0] + t*d[0], cur[1] + t*d[1])
            pts.append(q)
            (x1, y1), (x2, y2) = self.edge(i)
            ex, ey = x2-x1, y2-y1
            L = math.hypot(ex, ey)
            if L == 0:
                break
            ex, ey = ex/L, ey/L
            if min(math.dist(q, (x1, y1)), math.dist(q, (x2, y2))) < 1e-9:
                break                      # hit a corner -- trajectory undefined
            dot = d[0]*ex + d[1]*ey
            d = (2*dot*ex - d[0], 2*dot*ey - d[1])
            cur = q
        return pts

    def min_distance_to(self, pts, q):
        best = float("inf")
        for k in range(len(pts)-1):
            a, b = pts[k], pts[k+1]
            ax, ay = b[0]-a[0], b[1]-a[1]
            L2 = ax*ax + ay*ay
            s = 0.0 if L2 == 0 else max(0.0, min(1.0,
                    ((q[0]-a[0])*ax + (q[1]-a[1])*ay) / L2))
            best = min(best, math.dist((a[0]+s*ax, a[1]+s*ay), q))
        return best


def illumination_scan(B, p, q, ndirs=20000, nbounces=200):
    """Scan directions from p; return (closest approach to q, best theta)."""
    best, best_theta = float("inf"), None
    for k in range(ndirs):
        theta = 2*math.pi*k/ndirs
        d = B.min_distance_to(B.trajectory(p, theta, nbounces=nbounces), q)
        if d < best:
            best, best_theta = d, theta
    return best, best_theta
```

**Actual output of the sanity checks:**

```
square best approach: 5.190079620543489e-06 at theta = 0.5906194188748811
L-room best approach: 0.0 at theta = 0.0
square slope-1 path: [(0.25, 0.0), (1.0, 0.75), (0.75, 1.0), (0.0, 0.25), (0.25, 0.0), (1.0, 0.75)]
```

The third line is the real test: from `(1/4, 0)` at slope 1 in the unit square, the path is
periodic of combinatorial period 4 and returns exactly to `(0.25, 0.0)`. Runtime for all three:
0.46 s.

**Read the scan output correctly.** `illumination_scan` reports the *closest approach*, never a
yes/no. `5.19e-06` after 2000 directions means "there is very likely a connecting trajectory
nearby"; you then refine around `best_theta`. A distance that stubbornly refuses to fall below,
say, `1e-2` as you increase `ndirs` by orders of magnitude is *evidence for* non-illumination and
nothing more. In particular, corner-hitting truncates the trajectory silently (the `break`), so
directions that hit a vertex are under-sampled — precisely the directions that matter most in
unilluminable-room constructions.

