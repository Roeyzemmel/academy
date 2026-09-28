#!/usr/bin/env python3
"""Exact illumination probe on a square-tiled surface (origami).

Pure Python, standard library only. No SageMath required.

An origami is a pair of permutations (r, u) of {0,...,n-1}: square i is glued on
its right edge to square r(i), and on its top edge to square u(i).

Why this is exact and complete rather than a numerical approximation
--------------------------------------------------------------------
A straight segment from p = (square s, (x, y)) to q = (square t, (x', y')) has
holonomy (a, b) with a in x'-x+Z and b in y'-y+Z. So the candidate holonomies
form a *translate of Z^2*: they can be enumerated exactly, with no floating
point, and nothing within a given length bound is missed. Developing a candidate
means reading off which unit-square boundaries it crosses, in order, and applying
the corresponding permutation -- again exactly, in Fractions.

The routine also detects segments that pass through a vertex (two boundary
crossings at the same time), where the trajectory is *undefined* rather than
continuing. That distinction is the whole subject, so it is reported rather than
silently resolved.

Usage
-----
    from origami_illumination import Origami
    from fractions import Fraction as F

    O = Origami([1, 0, 2], [2, 1, 0])        # 3-square L in H(2)
    v = O.connections((0, F(1,3), F(1,4)), (2, F(1,5), F(2,7)), bound=8.0)
    # -> list of exact holonomy vectors (Fraction, Fraction), shortest first

    python3 origami_illumination.py          # runs the self-tests
"""

from fractions import Fraction as F
import math


def inv_perm(p):
    q = [0] * len(p)
    for i, pi in enumerate(p):
        q[pi] = i
    return q


class Origami:
    """A square-tiled surface given by right/up gluing permutations."""

    def __init__(self, r, u):
        assert len(r) == len(u), "r and u must have the same length"
        assert sorted(r) == sorted(u) == list(range(len(r))), \
            "r and u must be permutations of {0,...,n-1}"
        self.r, self.u = list(r), list(u)
        self.ri, self.ui = inv_perm(self.r), inv_perm(self.u)
        self.n = len(r)

    def develop(self, s, x, y, a, b):
        """Follow the segment from (s, (x, y)) with holonomy (a, b).

        All arguments after `s` are Fractions. Returns the terminal square
        index, or None if the segment passes through a vertex (in which case the
        trajectory is undefined, not blocked).
        """
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
        for i in range(len(events) - 1):        # simultaneous crossing = a vertex
            if events[i][0] == events[i + 1][0]:
                return None
        cur = s
        for _, kind in events:
            cur = getattr(self, kind)[cur]
        return cur

    def connections(self, p, q, bound):
        """All holonomy vectors of length <= bound joining p to q.

        p, q are triples (square, x, y) with x, y Fractions in [0, 1).
        Returns exact (Fraction, Fraction) pairs sorted by length.
        """
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

    def illuminates(self, p, q, bound):
        """True if p illuminates q via some trajectory of length <= bound.

        A False result is NOT a proof of non-illumination -- it means no
        connection exists below this bound. Raise the bound; a stable False
        across large bounds is evidence, not proof.
        """
        return len(self.connections(p, q, bound)) > 0


def _self_test():
    half = F(1, 2)
    ok = True

    # 1. Torus: every candidate vector must connect, so the count equals the
    #    number of lattice points of the translated Z^2 inside the disc.
    T = Origami([0], [0])
    p, q = (0, F(1, 3), F(1, 4)), (0, F(1, 5), F(2, 7))
    got = len(T.connections(p, q, 5.0))
    a0, b0 = F(1, 5) - F(1, 3), F(2, 7) - F(1, 4)
    expected = sum(
        1
        for m in range(-8, 9)
        for k in range(-8, 9)
        if not (a0 + m == 0 and b0 + k == 0)
        and float(a0 + m) ** 2 + float(b0 + k) ** 2 <= 25.0
    )
    print(f"  torus: found {got}, expected {expected} -> {got == expected}")
    ok &= got == expected

    # 2. 3-square origami in H(2): candidates should split roughly evenly among
    #    the three squares, and the total should be near the disc area.
    O = Origami([1, 0, 2], [2, 1, 0])
    src = (0, F(1, 3), F(1, 4))
    counts = {
        t: len(O.connections(src, (t, F(1, 5), F(2, 7)), 8.0)) for t in range(3)
    }
    total = sum(counts.values())
    frac = [round(c / total, 3) for c in counts.values()]
    print(f"  H(2) 3-square: by target square {counts}, total {total}")
    print(f"    fractions {frac} (disc area ~{round(math.pi*64, 0)})")
    ok &= total > 150 and all(0.25 < f < 0.42 for f in frac)

    # 3. Vertex detection: the diagonal from the center of the torus hits a corner.
    v1 = T.develop(0, half, half, F(1), F(1)) is None
    v2 = T.develop(0, half, half, F(1), F(0)) == 0
    print(f"  vertex detected: {v1}; non-vertex ok: {v2}")
    ok &= v1 and v2

    # 4. Reversal symmetry: p->q connections are the negatives of q->p.
    A = O.connections(src, (2, F(1, 5), F(2, 7)), 4.0)
    B = O.connections((2, F(1, 5), F(2, 7)), src, 4.0)
    sym = sorted(A) == sorted((-b[0], -b[1]) for b in B)
    print(f"  reversal symmetry: {sym}")
    ok &= sym

    print("ALL PASS" if ok else "FAILURE")
    return ok


if __name__ == "__main__":
    print("origami_illumination self-tests:")
    raise SystemExit(0 if _self_test() else 1)
