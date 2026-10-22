# Doors drawn as 'leaf in the opening + open leaf and chord', without an arc (01.10.2026, test of floor 5, item T4;
#   client A floors 1, 2, 4, 5). The Revit family draws the open leaf H-E as one axis-parallel line 650-1150 mm long
#   from the hinge H, and a straight chord E-J at 45 deg to it that ends at the other jamb J: |HJ| = |HE| +-12 %,
#   angle EHJ = 90 +-6 deg. The leaf drawn closed in the opening lies in the wall band along H-J, on the side away
#   from E, with its own 45-deg hatch: without a rule that hatch became a false wall across the opening (floor 5 -
#   6 doors, floor 2 - 1). The arc detector (doors2.py) does not see these doors.
# Output doors45.json, one record per door:
#   H, E, J (pt), L_mm, leaf / chord prim ids, red (the leaf in the opening drawn red - a fire door, owner 01.10.2026),
#   nohatch - the band of the leaf in the opening: walls_vec5 takes no hatch and no wall face there,
#   box - the door object: assign.py (step 4b) gives it the free primitives inside, as an operator box would.
# cfg.DOOR45_AUTO = False switches the rule off for a floor; cfg.DOOR45_SKIP = [boxes] drops detections whose hinge
#   lies in a box. A door the operator already boxed (MANUAL 'door45') keeps the operator's object: assign skips the
#   detection when the box is taken; the no-hatch band still applies.
#   python3 doors45.py [out.json]       (run.sh prep, after doors2.py; reads seq.pkl and cls.pkl)
import sys, json, math, pickle
import numpy as np
from scipy.spatial import cKDTree
from common import cfg, load, MM_PER_PT
OUT = sys.argv[1] if len(sys.argv) > 1 else 'doors45.json'
P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
LEAF_MM = getattr(cfg, 'DOOR45_LEAF_MM', (650, 1150))   # 600 took the 45-deg end of a cabinet (floor 5, (991, 445))
AWAY, TOWARD, ALONG = 2.8, 1.2, 0.6      # the band of the leaf in the opening, pt: away from E, toward E, past H and J
SKIP = [tuple(b) for b in getattr(cfg, 'DOOR45_SKIP', [])]
res = []
if getattr(cfg, 'DOOR45_AUTO', True):
    lo, hi = LEAF_MM[0] / MM_PER_PT, LEAF_MM[1] / MM_PER_PT
    S = []                                           # dark straight segments that can be a leaf or a chord
    for i, p in enumerate(P):
        if p[0] != 'l' or p[2] is None or max(p[2]) > 0.3 or cls[i] in ('sheet', 'axis', 'dim'): continue
        g = p[4]
        for k in range(len(g) - 1):
            a, b = tuple(g[k]), tuple(g[k + 1]); l = math.dist(a, b)
            if 0.5 * lo <= l <= 1.5 * hi: S.append((i, a, b, l))
    ends = np.array([e for s in S for e in (s[1], s[2])]) if S else np.zeros((0, 2))
    T = cKDTree(ends) if len(ends) else None
    seen = set()
    for n, (i, a, b, l) in enumerate(S):
        if not (lo <= l <= hi): continue
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
        if not (min(ang, 180 - ang) < 1.5 or abs(ang - 90) < 1.5): continue          # the open leaf is axis-parallel
        for H, E in ((a, b), (b, a)):
            for m in T.query_ball_point(E, 0.25):
                j = m // 2
                if S[j][0] == i and j == n: continue
                i2, a2, b2, l2 = S[j]
                J = b2 if math.dist(a2, E) < math.dist(b2, E) else a2
                hj = math.dist(H, J)
                if not (0.88 * l <= hj <= 1.12 * l): continue
                v1 = (E[0] - H[0], E[1] - H[1]); v2 = (J[0] - H[0], J[1] - H[1])
                c = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))
                if abs(math.degrees(math.acos(max(-1.0, min(1.0, c)))) - 90) > 6: continue
                key = (round(H[0]), round(H[1]))
                if key in seen or any(z[0] <= H[0] <= z[2] and z[1] <= H[1] <= z[3] for z in SKIP): continue
                seen.add(key)
                u = (v2[0] / hj, v2[1] / hj); nv = (v1[0] / l, v1[1] / l)               # along the opening, toward E
                q = [(H[0] + s * u[0] + t * nv[0], H[1] + s * u[1] + t * nv[1]) for s in (-ALONG, hj + ALONG) for t in (-AWAY, TOWARD)]
                nh = (min(x for x, y in q), min(y for x, y in q), max(x for x, y in q), max(y for x, y in q))
                xs = [H[0], E[0], J[0], nh[0], nh[2]]; ys = [H[1], E[1], J[1], nh[1], nh[3]]
                box = (min(xs) - 0.3, min(ys) - 0.3, max(xs) + 0.3, max(ys) + 0.3)
                red = any(P[k][0] in ('l', 'qu') and (P[k][2] or P[k][3]) is not None
                          and (lambda c_: c_[0] >= 0.8 and c_[1] <= 0.25 and c_[2] <= 0.25)(P[k][2] if P[k][2] is not None else P[k][3])
                          and all(nh[0] - 0.5 <= x <= nh[2] + 0.5 and nh[1] - 0.5 <= y <= nh[3] + 0.5 for x, y in P[k][4])
                          for k in range(len(P)))
                res.append(dict(H=[round(H[0], 2), round(H[1], 2)], E=[round(E[0], 2), round(E[1], 2)], J=[round(J[0], 2), round(J[1], 2)],
                                L_mm=round(l * MM_PER_PT), leaf=i, chord=i2, red=bool(red),
                                nohatch=[round(v, 2) for v in nh], box=[round(v, 2) for v in box]))
json.dump(res, open(OUT, 'w'), indent=1, ensure_ascii=False)
print('doors leaf + chord', len(res), [(d['H'], d['L_mm'], 'red' if d['red'] else '') for d in res])
