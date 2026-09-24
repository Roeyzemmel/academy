#!/usr/bin/env python3
"""Floating-point billiard tracer for an arbitrary polygon.

Pure Python, standard library only. Use this when the polygon is irrational (so
unfolding is unavailable), for Tokarsky-style unilluminable-room experiments, or
for a quick picture before reaching for SageMath.

READ THE OUTPUT CORRECTLY. `illumination_scan` reports a *closest approach*, never
a yes/no:

  - a distance that drops toward 0 as you increase `ndirs` means "there is very
    likely a connecting trajectory near this direction" -- then refine around
    `best_theta` and, if you need certainty, find the trajectory combinatorially;
  - a distance that stubbornly stays above (say) 1e-2 as `ndirs` grows by orders
    of magnitude is *evidence for* non-illumination and nothing more.

The known bias: trajectories that hit a corner are truncated (the trajectory is
undefined there, which is mathematically correct), so directions through vertices
are under-sampled -- and those are exactly the directions that matter in
unilluminable-room constructions. Treat a scan as a conjecture generator.

Usage
-----
    from billiard_trace import Billiard, illumination_scan
    B = Billiard([(0,0), (1,0), (1,1), (0,1)])
    pts = B.trajectory((0.25, 0.0), math.pi/4)
    d, theta = illumination_scan(B, (0.25, 0.25), (0.75, 0.75), ndirs=5000)

    python3 billiard_trace.py     # runs the self-tests
"""

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
            den = d[0] * ey - d[1] * ex
            if abs(den) < 1e-15:
                continue
            wx, wy = p[0] - x1, p[1] - y1
            t = (ex * wy - ey * wx) / den
            s = (d[0] * wy - d[1] * wx) / den
            if t > eps and -1e-9 <= s <= 1 + 1e-9:
                if best_t is None or t < best_t:
                    best_t, best_i = t, i
        return best_t, best_i

    def trajectory(self, p, theta, nbounces=200, eps=1e-9):
        """Billiard path from p in direction theta. Stops at a corner."""
        d = (math.cos(theta), math.sin(theta))
        pts = [tuple(map(float, p))]
        cur = pts[0]
        for _ in range(nbounces):
            t, i = self._hit(cur, d, eps)
            if t is None:
                break
            q = (cur[0] + t * d[0], cur[1] + t * d[1])
            pts.append(q)
            (x1, y1), (x2, y2) = self.edge(i)
            ex, ey = x2 - x1, y2 - y1
            L = math.hypot(ex, ey)
            if L == 0:
                break
            ex, ey = ex / L, ey / L
            if min(math.dist(q, (x1, y1)), math.dist(q, (x2, y2))) < 1e-9:
                break                      # hit a corner: trajectory undefined
            dot = d[0] * ex + d[1] * ey
            d = (2 * dot * ex - d[0], 2 * dot * ey - d[1])
            cur = q
        return pts

    def min_distance_to(self, pts, q):
        best = float("inf")
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            ax, ay = b[0] - a[0], b[1] - a[1]
            L2 = ax * ax + ay * ay
            s = 0.0 if L2 == 0 else max(
                0.0, min(1.0, ((q[0] - a[0]) * ax + (q[1] - a[1]) * ay) / L2)
            )
            best = min(best, math.dist((a[0] + s * ax, a[1] + s * ay), q))
        return best


def illumination_scan(B, p, q, ndirs=20000, nbounces=200):
    """Scan directions from p; return (closest approach to q, best theta)."""
    best, best_theta = float("inf"), None
    for k in range(ndirs):
        theta = 2 * math.pi * k / ndirs
        d = B.min_distance_to(B.trajectory(p, theta, nbounces=nbounces), q)
        if d < best:
            best, best_theta = d, theta
    return best, best_theta


def _self_test():
    ok = True
    sq = Billiard([(0, 0), (1, 0), (1, 1), (0, 1)])

    # The real test: from (1/4, 0) at slope 1 the path is periodic of period 4
    # and returns exactly to the start.
    path = sq.trajectory((0.25, 0.0), math.pi / 4, nbounces=5)
    closes = math.dist(path[4], (0.25, 0.0)) < 1e-12
    print(f"  square slope-1 orbit closes after 4 bounces: {closes}")
    print(f"    {[tuple(round(c, 4) for c in P) for P in path]}")
    ok &= closes

    d, th = illumination_scan(sq, (0.25, 0.25), (0.75, 0.75), ndirs=2000)
    print(f"  square scan closest approach: {d:.3e} at theta={th:.4f}")
    ok &= d < 1e-3

    Lroom = Billiard([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
    d2, th2 = illumination_scan(Lroom, (0.5, 0.5), (0.5, 1.5), ndirs=2000)
    print(f"  L-room scan closest approach: {d2:.3e} at theta={th2:.4f}")
    ok &= d2 < 1e-3

    print("ALL PASS" if ok else "FAILURE")
    return ok


if __name__ == "__main__":
    print("billiard_trace self-tests:")
    raise SystemExit(0 if _self_test() else 1)
