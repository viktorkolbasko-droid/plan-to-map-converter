"""Measure positions of lines by averaged profiles instead of by eye.

On a small raster (the client C floor is 789 px wide, 16.8 px/m) a single pixel is 6 cm. Averaging a profile
over the length of a feature gives sub-pixel positions: this is how v2 placed corridor walls, the facade
and the stair flights. The same routine works on a page render (zoom x the page) and on the main raster."""
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.signal import find_peaks


def _sample(gray, P):
    return map_coordinates(gray, [P[:, 1], P[:, 0]], order=1, cval=255.0)


def across(gray, frame_to_img, c, theta_deg, offs, ts):
    """darkness (255 - gray) at each offset `offs` along the normal of the axis (angle theta through c),
    averaged over positions `ts` along the axis. All lengths in frame units."""
    th = np.radians(theta_deg); u = np.array([np.cos(th), np.sin(th)]); n = np.array([-u[1], u[0]])
    prof = np.zeros(len(offs))
    for t in ts:
        P = np.asarray(c, float) + t * u + np.asarray(offs)[:, None] * n
        prof += 255.0 - _sample(gray, frame_to_img(P))
    return prof / max(len(ts), 1)


def along(gray, frame_to_img, c, theta_deg, ts, off, band=(-1.5, -0.75, 0.0, 0.75, 1.5)):
    """darkness along the axis at normal offset `off`, averaged over a narrow band"""
    th = np.radians(theta_deg); u = np.array([np.cos(th), np.sin(th)]); n = np.array([-u[1], u[0]])
    v = np.zeros(len(ts))
    for b in band:
        P = np.asarray(c, float) + np.asarray(ts)[:, None] * u + (off + b) * n
        v += 255.0 - _sample(gray, frame_to_img(P))
    return v / len(band)


def lines_at(x, prof, height=25.0, min_sep=0.5):
    """peak positions (line centres) of a darkness profile"""
    step = float(x[1] - x[0])
    pk, _ = find_peaks(prof, height=height, distance=max(1, int(round(min_sep / step))))
    return [(float(x[i]), float(prof[i])) for i in pk]


def dominant_angle(segments, weight_pow=2.0, tol_deg=5.0):
    """dominant direction (deg, mod 180) of line segments [(a, b), ...] weighted by length^pow"""
    ang = np.array([np.arctan2(b[1] - a[1], b[0] - a[0]) % np.pi for a, b in segments])
    w = np.array([np.hypot(*(np.asarray(b) - np.asarray(a))) for a, b in segments]) ** weight_pow
    H, e = np.histogram(ang, bins=90, range=(0, np.pi), weights=w)
    th = (e[np.argmax(H)] + e[np.argmax(H) + 1]) / 2
    m = np.abs(((ang - th + np.pi / 2) % np.pi) - np.pi / 2) < np.radians(tol_deg)
    return float(np.degrees(np.average(ang[m], weights=w[m])))
