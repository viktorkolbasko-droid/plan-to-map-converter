"""Affine frames. One convention everywhere: pixel k covers [k, k+1) (map/rules/30 §1.3).

A plan lives in several frames: PDF page points, the main raster, a page render (zoom px per pt),
the canvas of the clean plan. Keep every mapping as an explicit 3x3 affine and compose them;
never re-derive a frame by eye."""
import numpy as np


class Affine:
    def __init__(self, M):
        M = np.asarray(M, float)
        self.M = np.vstack([M.reshape(2, 3), [0, 0, 1]]) if M.size == 6 else M.reshape(3, 3)

    @staticmethod
    def scale_shift(sx, sy, tx=0.0, ty=0.0):
        return Affine([[sx, 0, tx], [0, sy, ty], [0, 0, 1]])

    def __matmul__(self, other):
        return Affine(self.M @ other.M)

    def inv(self):
        return Affine(np.linalg.inv(self.M))

    def __call__(self, P):
        P = np.atleast_2d(np.asarray(P, float))
        return (self.M[:2, :2] @ P.T).T + self.M[:2, 2]

    def scale(self):
        """mean linear scale (sqrt of |det|)"""
        return float(np.sqrt(abs(np.linalg.det(self.M[:2, :2]))))

    def shapely(self):
        """coefficients for shapely.affinity.affine_transform"""
        a, b, c = self.M[0]; d, e, f = self.M[1]
        return [a, b, d, e, c, f]


def canvas_affine(src_bounds, px_per_src, margin):
    """source frame -> canvas: X = (x - x0) * s + margin. src_bounds = building bbox (x0, y0, x1, y1).
    Returns (Affine, (W, H))."""
    x0, y0, x1, y1 = src_bounds
    W = int(round((x1 - x0) * px_per_src + 2 * margin)); H = int(round((y1 - y0) * px_per_src + 2 * margin))
    return Affine.scale_shift(px_per_src, px_per_src, margin - x0 * px_per_src, margin - y0 * px_per_src), (W, H)
