# Helpers for cfg.py files (no dependency on cfg itself).
import math
def arc_points(cx, cy, r, a0, a1, step=3.0):
    """polyline along a circle (angles in degrees, y down as on the sheet) - for cfg bands (CURVED_ZONES, DIAG_ZONES)"""
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * t / (n - 1))), cy + r * math.sin(math.radians(a0 + (a1 - a0) * t / (n - 1)))) for t in range(n)]
