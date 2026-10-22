"""Badge placement (map/rules/70 §1 'Точка бейджа'; map/rules/70 §2.6).

The point of a badge is the room-number circle of the source; with no circle - the pole of inaccessibility.
Before placing, move it off the room labels and the other badges; furniture is a soft cost (stairs and
lifts: the badge lies on top of the flights / the shaft by the canon, no furniture cost).
v2 placed 15.04(2)'s storage badge on its own label before this function existed."""
import math
import numpy as np
from shapely.geometry import Point, box as sbox
from shapely.ops import polylabel


def label_box(text, x, y, font, pad=3):
    """bbox of a label drawn with text-anchor middle and baseline y+8 (24 px font); font = PIL ImageFont"""
    w = font.getlength(text)
    return (x - w / 2 - pad, y - 11, x + w / 2 + pad, y + 11)


def place(room_canvas, label_boxes, badges, furniture=None, r=15.0, wall_half=3.0, step=4.0, pref=None):
    """room_canvas: room polygon in canvas px; label_boxes: [(x0, y0, x1, y1)]; badges: [(x, y)] already placed;
    furniture: shapely geometry of furniture lines in canvas px or None. Returns (x, y)."""
    if pref is None:
        c = polylabel(room_canvas, tolerance=1.0); pref = (c.x, c.y)
    inner = room_canvas.buffer(-(r + wall_half + 2.0))
    if inner.is_empty:
        inner = room_canvas.buffer(-(r * 0.5))
    if inner.is_empty:
        return pref
    boxes = [sbox(*b).buffer(3) for b in label_boxes]
    x0, y0, x1, y1 = inner.bounds
    cands = [pref] + [(x, y) for x in np.arange(x0, x1 + 0.1, step) for y in np.arange(y0, y1 + 0.1, step)]
    best = None
    for c in cands:
        p = Point(c)
        if not inner.contains(p):
            continue
        disc = p.buffer(r)
        if any(disc.intersects(b) for b in boxes):
            continue
        if any(math.hypot(c[0] - a, c[1] - b) < 2 * r + 6 for a, b in badges):
            continue
        cost = math.hypot(c[0] - pref[0], c[1] - pref[1])
        if furniture is not None and disc.intersects(furniture):
            cost += 60 + disc.intersection(furniture).length * 3
        if best is None or cost < best[0]:
            best = (cost, c)
    return best[1] if best else pref
