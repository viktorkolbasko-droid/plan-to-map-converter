"""Stair flights drawn, not traced (owner 26.09: flights drawn, badge on top; map/rules/61 §2.3: treads 1 px
every 0.30 m).

The CAD stair symbol of a furniture plan is often schematic: on client C floor 15 the treads were 0.20 m
apart and on floor 14 not drawn at all. Tracing LSD fragments gives noise (v1: 215-232 broken lines per floor).
Measure the flight box once (profiles.across / profiles.along on the page render), then generate:
  * one rectangle per flight, the gap between them = the wall between the flights;
  * treads evenly spaced, as close to 0.30 m as the flight length allows;
  * the stairwell (flights + landings) is ONE room (map/rules/40 §3.3): a line along the flight edge is not a wall.
The tread spacing of a symbol is never a scale source (map/rules/30 §2.1 p.5)."""
import math
import numpy as np
from shapely.geometry import LineString, Polygon


def flights(spec, px_per_m, tread_m=0.30):
    """spec: dict(c=(x, y), th=deg along the flights, fl=[(o0, o1), ...] offsets across, t=(t0, t1) along).
    Returns [(outline Polygon, [tread LineStrings])] in the same frame as spec."""
    c = np.array(spec['c'], float); th = math.radians(spec['th'])
    u = np.array([math.cos(th), math.sin(th)]); n = np.array([-u[1], u[0]])
    t0, t1 = spec['t']; out = []
    for o0, o1 in spec['fl']:
        P = lambda t, o: tuple(c + t * u + o * n)
        box = Polygon([P(t0, o0), P(t1, o0), P(t1, o1), P(t0, o1)])
        k = max(1, int(round((t1 - t0) / (tread_m * px_per_m)))); st = (t1 - t0) / k
        out.append((box, [LineString([P(t0 + i * st, o0), P(t0 + i * st, o1)]) for i in range(1, k)]))
    return out


def measure_spec_hint():
    """How the spec was measured on client C (keep the procedure, not the numbers):
    1. dominant direction of LSD segments inside the stair room -> th (profiles.dominant_angle);
    2. profiles.across over the middle of the flights -> line offsets: outer edges, the double line of the wall
       between flights, the lines of travel in the middle of each flight;
    3. profiles.along at 3-4 offsets inside the flights -> t of the box ends and of the landing edge;
    4. check: each flight 1.0-1.4 m wide, the line of travel in its middle, both floors of one core agree +-2 px."""
    return None
