# Walls from source linework (v3): ink = lines buffered by EPS; faces = holes of ink;
# wall faces = faces running along hatch lines; walls = selected faces grown back by EPS (mitre).
from common import *
import cv2, json, importlib, time, collections
import shapely
from shapely.geometry import LineString, Polygon, Point, box as sbox
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.affinity import affine_transform
from shapely.prepared import prep
t0=time.time()
EPS=0.3
CURVED=getattr(cfg,'CURVED_ZONES',[])   # bands of curved walls: hatch there may run at any angle
# bands of 45-degree partitions: single 45/135 strokes there are not hatch. An entry is a box (x0,y0,x1,y1) or a band
#   (centre polyline [(x,y),...], half width) - a box around a diagonal also catches straight walls next to it
def _diag_geom(z):
    from shapely.geometry import LineString as _L, box as _b
    return _b(*z) if len(z)==4 and all(isinstance(v,(int,float)) for v in z) else _L(z[0]).buffer(z[1],cap_style=2)
_DZ=[_diag_geom(z) for z in getattr(cfg,'DIAG_ZONES',[])]
_DZP=[prep(g) for g in _DZ]
def in_diag(p): return any(g.contains(Point(p)) for g in _DZP)
# (29.09.2026) cfg.WALL_ZONES: bands / boxes where the operator has said "this is a wall of class X" - the source draws
#   it with a hatch the recogniser does not read (floor 2: the round wall between axes Д and Г/2, a fixed 37/127-degree
#   X pattern cut by the curve) or with no hatch at all (a through element that a partial sheet shows as an outline,
#   owner 29.09). Every thin face of the source linework (2A/P <= maxw, default 6 pt) inside the zone is a wall face of
#   that class; the zone's own lines enter the linework. Entry: dict(zone=box (x0,y0,x1,y1) or band ([(x,y),...], half
#   width), cls='cap'|'gkl'|'blk'|'ext', maxw=6.0, why='...')
_WZ=[dict(g=_diag_geom(z['zone']),cls=z['cls'],maxw=z.get('maxw',6.0)) for z in getattr(cfg,'WALL_ZONES',[])]
for _z in _WZ: _z['p']=prep(_z['g'])
def in_wzone(ps):
    if not _WZ: return False
    m_=Point(ps[len(ps)//2]) if len(ps)>2 else Point((ps[0][0]+ps[-1][0])/2,(ps[0][1]+ps[-1][1])/2)
    return any(z['p'].contains(m_) for z in _WZ)
# inside a declared 45-degree wall band the operator has said "this is a wall": object detectors that grabbed its
#   pattern (plant hubs, door hardware, misc) do not take its lines away from the walls; door leaves still do
_DOORK=('door','door45')
# band strokes: a straight neutral stroke at 45/135 deg (+-2) whose BOTH ends sit on thick outline lines (>=0.45 pt)
#   is the pattern of a partition band, whoever grabbed it in the previous round (floors 4-5: plants over a planter
#   along the partition, a rack box, a 'floor screen' made of the partition's own leftovers). Canonical blocks,
#   doors and the facade keep their strokes. Floor 3 has no such stroke under an object (checked): no change there.
_BANDSTROKE=set()
# automatic detectors only (+ the operator's 45-degree door, whose box cannot avoid the partition next to it):
#   an operator box (rack, kitchen, cabinet...) keeps what it holds - a box that covers a partition is fixed in cfg
_BS_OWN=('plant','fscreen','column','wcacc','benchend','screen','desk_o','misc','lpart','door45')
def _band_strokes():
    from shapely.geometry import LineString as _L, Point as _Pt
    from shapely.strtree import STRtree as _T
    TH=[i for i,p in enumerate(P) if p[0]=='l' and p[1] is not None and p[1]>=0.45]
    if not TH: return set()
    G_=[_L(P[i][4]) for i in TH]; tr_=_T(G_); out=set()
    for i,p in enumerate(P):
        if p[0]!='l' or own.get(i) not in _BS_OWN: continue
        c=p[2]
        if c is None or not (abs(c[0]-c[1])<0.02 and abs(c[1]-c[2])<0.02 and c[0]<=0.85): continue
        a,b=p[4]; L=math.dist(a,b)
        if not (0.4<=L<=11): continue
        t=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
        # inside a 45-degree band (cfg.DIAG_ZONES) the pattern is turned: its strokes run at 0/90 there
        if _DZ and in_diag(((a[0]+b[0])/2,(a[1]+b[1])/2)):
            if min(t,180-t,abs(t-90))>6 or L>3.0: continue      # the turned pattern: a sawtooth of short steps, quantised +-6 deg as the DIAG hatch
        elif min(abs(t-45),abs(t-135))>2: continue
        # the lines it ends on must CROSS its direction (>= 20 deg): a piece of a 45-degree outline ends on the next
        #   collinear piece - that is linework, not a pattern (floor 5, the octagonal glass room 12)
        def _xing(e):
            for j in tr_.query(_Pt(e).buffer(0.1)):
                if TH[j]==i or G_[j].distance(_Pt(e))>0.06: continue
                u_,v_=P[TH[j]][4]; tj=math.degrees(math.atan2(v_[1]-u_[1],v_[0]-u_[0]))%180
                if abs(((t-tj)+90)%180-90)>=20: return True
            return False
        if _xing(a) and _xing(b): out.add(i)
    return out
def owned_out(i,keys):
    k=own.get(i)
    if k not in keys: return False
    if i in _BANDSTROKE or i in _CONT: return False
    if _DZ and k not in _DOORK:
        a_,b_=P[i][4][0],P[i][4][-1]
        if in_diag(((a_[0]+b_[0])/2,(a_[1]+b_[1])/2)): return False
    return True
P=load(); cls=pickle.load(open('cls.pkl','rb'))
inst_,_=pickle.load(open('assign2.pkl','rb'))
# 'door': a door's own leaf and arc (doors2 finds them before the walls) are neither hatch nor wall linework: a leaf
#   in a 45-degree wall looks exactly like a hatch stroke, and its swing became a 'wall' face (floor 4). The jambs are
#   not door prims, so the wall ends keep their outline.
# (28.09.2026) colour elements - room separation lines, signs, carpets, washbasins - are neither hatch nor wall
#   linework: floor 1's purple line along the SE glazing closed a 1 m2 'wall' face with the facade line
FURN={'plant','chair','desk','screen','stool','sofa','tag','wc','sink','wcacc','benchend','fscreen','mtable','dtable','convector','axmark','door','doorhw','desk_o','roomsep','sign','carpet','wcsink'}
NOHATCH={'plant','chair','desk','screen','stool','sofa','tag','wc','sink','wcacc','benchend','fscreen','mtable','dtable','convector','column','axmark','facade','rack','kitchen','fire','door','doorhw','desk_o','lpartc','radiator','rdoor','cafe','roomsep','sign','carpet','wcsink'}   # lpartc: chains of thick outline pieces (LPART_CHAINS)
own={}
for q in inst_:
    for i in q['prims']: own[i]=q['key']
_BANDSTROKE=_band_strokes()
print('band strokes freed from objects',len(_BANDSTROKE),collections.Counter(own[i] for i in _BANDSTROKE).most_common(8))
# (cfg.WALL_CONTINUATION, round 2 on) a wall that ends before the source wall does: strokes that carry the hatch of a
#   round-1 body on along its band (wallcont.py; floor 4 - the lower stub of the stair enclosure was taken by the
#   glazing band, floor 1 - partition strips taken by plants, the niche at axis 8) are hatch, whoever took them.
#   cfg.WALL_CONT_SKIP: boxes where a reviewed cluster is not a wall (radiator fins, door frames).
_CONT=set()
if getattr(cfg,'WALL_CONTINUATION',False) and os.path.exists('wallprims.pkl') and os.path.exists('walls.pkl'):
    from wallcont import continuation as _continuation
    _skip=getattr(cfg,'WALL_CONT_SKIP',[])
    # cfg.WALL_CONT_STEPS (default 4): how far the search goes from a round-1 body; a long straight wall with a turned
    #   hatch (floor 1, the wall at 60 deg) needs more than a curved stub
    for _c in _continuation(P,cls,own,pickle.load(open('walls.pkl','rb'))['Wpt'],pts,max_steps=getattr(cfg,'WALL_CONT_STEPS',4),axis_ok=lambda m_: bool(_DZ) and in_diag(m_)):
        _b=_c['bbox_pt']
        if any(z[0]<=_b[0] and _b[2]<=z[2] and z[1]<=_b[1] and _b[3]<=z[3] for z in _skip): continue
        _CONT|=set(_c['ids'])
    print('wall continuation strokes',len(_CONT),collections.Counter(own.get(i,'free') for i in _CONT).most_common(6))
import detect8 as _d8
FREE_BOXES=[_d8.bbox_of(b) for key,name,layer,boxes in cfg.MANUAL if key=='fire' and 'ПК' in name for b in boxes]
# (cfg.NOHATCH_BOXES, 30.09.2026, floor 5) operator boxes where a 45-deg stroke is never wall hatch: a door leaf drawn
#   closed in the opening with its own hatch (technical doors 'leaf + chord' along the north corridor - 7 false
#   slivers of wall across the openings), the 45-deg side of a cabinet. Default []: other floors do not change.
FREE_BOXES=FREE_BOXES+[tuple(b) for b in getattr(cfg,'NOHATCH_BOXES',[])]
# (doors45.py, 01.10.2026, test of floor 5, T4) the band of the leaf drawn closed in the opening of a door 'leaf + chord'
#   is found by the detector, not boxed by the operator: no wall hatch there (floor 2 - 3 false walls across openings,
#   floor 4 - 1, floor 5 - 6). The same band drops wall faces below (_NHB)
_D45=[tuple(d['nohatch']) for d in (json.load(open('doors45.json')) if os.path.exists('doors45.json') else [])]
FREE_BOXES=FREE_BOXES+_D45
from shapely.ops import unary_union as _uu
_FB=min(8,getattr(cfg,'FACADE_BAND',14))   # the glazing band where 45-deg strokes are mullion details, not hatch
fac_zone=prep(_uu([ln.buffer(min(_FB,w_)).difference(Point(ln.coords[0]).buffer(12)).difference(Point(ln.coords[-1]).buffer(12)) for ln,w_ in zip(facade_lines(),facade_band_widths(_FB))]) if FACADES else Point(-1e6,-1e6).buffer(1))
# the 12 pt at each end of a facade line stay open for the hatch of the walls the glazing meets, except strokes
#   parallel (+-6 deg) to the glazing there: those are glass lines (floor 4: the SE curve reaches the shaft at 45 deg,
#   its glass lines passed as hatch and made false walls). Floor 3 ends run at 0/90/20 deg: no change there.
_FEND=[(ln,Point(ln.coords[0]).buffer(12).union(Point(ln.coords[-1]).buffer(12)).intersection(ln.buffer(8))) for ln in facade_lines()] if FACADES else []
def fac_end_glass(a,b):
    m=Point((a[0]+b[0])/2,(a[1]+b[1])/2); L=math.dist(a,b)
    for ln,z in _FEND:
        if L==0 or not z.contains(m): continue
        t=ln.project(m); p1=ln.interpolate(max(0,t-3)); p2=ln.interpolate(min(ln.length,t+3))
        d=(p2.x-p1.x,p2.y-p1.y); n=math.hypot(*d)
        if n>0 and abs(d[0]*(b[1]-a[1])-d[1]*(b[0]-a[0]))/(n*L)<=math.sin(math.radians(6)): return True
    return False
def ibb(q):
    ps=[v for i in q['prims'] for v in (list(P[i][4]) if P[i][0]!='c' else bez(P[i][4],6))]
    return (min(p[0] for p in ps),min(p[1] for p in ps),max(p[0] for p in ps),max(p[1] for p in ps))
def plant_disc(q):
    b=ibb(q); c=q.get('c') or ((b[0]+b[2])/2,(b[1]+b[3])/2)
    r=min(10.0,max(b[2]-b[0],b[3]-b[1])/2+1.5)
    return Point(c).buffer(r)
def geo(i):
    p=P[i]; return list(p[4]) if p[0]=='l' else bez(p[4],10)
LN=[i for i,p in enumerate(P) if p[0] in ('l','c') and cls[i] not in ('axis','sheet','dim') and p[2] not in ((1.0,0.67,0.67),(0.67,0.67,0.67))]
G={i:LineString(geo(i)) for i in LN}
tree=STRtree([G[i] for i in LN])
# plant hubs: >=6 lines radiating from one point in >=4 directions (plant symbol), also for plants the detector missed
hubc=collections.defaultdict(list)
for i in LN:
    if P[i][0]!='l': continue
    a,b=P[i][4]; L=math.dist(a,b)
    if not (2<=L<=12): continue
    for e,f_ in ((a,b),(b,a)): hubc[(round(e[0]/0.25),round(e[1]/0.25))].append(math.degrees(math.atan2(f_[1]-e[1],f_[0]-e[0]))%360)
hubs=[]
for k_,angs in hubc.items():
    # a plant's spokes run at any angle: 3+ direction bins must come from lines off the sheet axes (+-3 deg). A crossing
    #   of wall edges and glass lines has 4 bins at 0/90/180/270 only - as a 'hub' it cut a capital wall (floor 1).
    #   All 37 hubs of floor 3 pass.
    _na=[a_ for a_ in angs if min(a_%90,90-a_%90)>3]
    if len(angs)>=6 and len(set(int(a_//30) for a_ in angs))>=4 and len(set(int(a_//30) for a_ in _na))>=3:
        hubs.append(Point(k_[0]*0.25,k_[1]*0.25))
print('plant hubs',len(hubs))
# (cfg.PLANT_COLOR set, floor 5: plants are drawn in their own colour) a hatch candidate is neutral grey, so it can
#   never be a leaf: the plant zone is not needed there - it only cut the partitions that planters stand along
_PLANTC=getattr(cfg,'PLANT_COLOR',None)
plant_zone=prep(Point(-1e6,-1e6).buffer(1)) if _PLANTC else prep(unary_union([plant_disc(q) for q in inst_ if q['key']=='plant' and q['prims']]+[h.buffer(10) for h in hubs]))
# ---- hatch candidates (geometric): 45/135 deg, 0.4..14 pt, both ends on other lines
_DBG=[int(v) for v in os.environ.get('DBG','').split(',') if v.strip()]
def _dbg(stage,coll):
    if _DBG: _c=set(coll); print('DBG',stage,{i:(i in _c) for i in _DBG})
def ang(a,b): return math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
HAT=[]
_HMAX=float(getattr(cfg,'HATCH_MAXLEN',11.5))
for i in LN:
    p=P[i]
    if i in _DBG: print('DBG pre',i,p[0],'owned_out',owned_out(i,NOHATCH),'own',own.get(i),p[2])
    if p[0]!='l' or owned_out(i,NOHATCH): continue
    c=p[2]
    if c is None or not (abs(c[0]-c[1])<0.02 and abs(c[1]-c[2])<0.02 and c[0]<=0.85): continue
    # (cfg.NOHATCH_COLORS, floor 6) a grey of the sheet that is never hatch: the 45-deg casings around the columns
    if any(max(abs(c[j]-z[j]) for j in range(3))<=0.015 for z in getattr(cfg,'NOHATCH_COLORS',[])): continue
    a,b=p[4]; L=math.dist(a,b)
    t=ang(a,b); curved=in_curved(a)
    # in a curved band the 45/135 pattern lines become long where the band runs parallel to them
    longok=curved and L<=30 and min(abs(t-45),abs(t-135))<=1.0
    # the grey hatch of existing (capital) walls, 0.40-0.55: a wall 500-700 mm thick has strokes up to 14 pt (floor 1:
    #   the long capital wall along the axis of the lifts, 11.4 pt strokes, was left as 'light partition' lines).
    #   Floor 3 has no such stroke longer than 11 pt.
    capok=0.40<=c[0]<=0.55 and L<=14
    # (28.09.2026) a continuation stroke (wallcont.py) is parallel to the hatch of its own wall body: the pattern turns
    #   with a turned wall (floor 1: the wall at 60 deg at (1001,236), strokes at 165 deg), so no 45/135 test for it -
    #   unless it runs along an axis (+-6 deg): door frames and column flanges are drawn so (floor 2, (542,129): the
    #   vertical lines of a door frame became a 'wall'); 45-deg bands with a 0/90 pattern are DIAG_ZONES
    if i in _CONT and 0.4<=L<=15 and min(t%90,90-t%90)>6: HAT.append(i); continue
    # the longest hatch stroke (cfg.HATCH_MAXLEN, default 11.5 pt since 01.10.2026 - proposal 61: floor 6 has a wall
    #   piece at the stairs whose light-grey strokes are 11.1-11.2 pt; it was drawn as lines, the floor's only unexplained
    #   wall gap. Checked by the real pipeline on all client A floors: 1, 2, 4, 5 - the same drawing, 3 - no such stroke)
    if not (0.4<=L<=_HMAX or longok or capok): continue
    m=((a[0]+b[0])/2,(a[1]+b[1])/2)
    # operator bands along 45-degree partitions (cfg.DIAG_ZONES, floor 4 at the WC): the band is turned by 45 degrees,
    #   so is its pattern - strokes at 0/90 are the hatch there (a sawtooth of short steps), while 45/135 strokes are
    #   pieces of the band's own outline
    if _DZ and in_diag(m):
        if min(t,180-t,abs(t-90))>6: continue
    else:
        if not curved and min(abs(t-45),abs(t-135))>6: continue
        if curved and min(t,180-t,abs(t-90))<4: continue
    if i in _DBG: print('DBG why',i,'fac',fac_zone.contains(Point(m)),'endglass',fac_end_glass(a,b),'plant',plant_zone.contains(Point(m)),'freebox',any(bx[0]<=m[0]<=bx[2] and bx[1]<=m[1]<=bx[3] for bx in FREE_BOXES))
    if i in _CONT: HAT.append(i); continue
    if fac_zone.contains(Point(m)) or fac_end_glass(a,b) or plant_zone.contains(Point(m)): continue
    if any(bx[0]<=m[0]<=bx[2] and bx[1]<=m[1]<=bx[3] for bx in FREE_BOXES): continue
    HAT.append(i)
_dbg('HAT0',HAT)
# (cfg.ROT_OUTLINE, default on) a 45-deg stroke whose both ends meet ONLY lines of the 45/135 family is a side of a
#   turned square / rectangle (floor 1: chairs and a bench turned by 45 deg), not hatch: hatch ends on the band edges,
#   which run another way. Not in curved zones (the edges turn there) nor in 45-degree bands (the pattern turns).
if getattr(cfg,'ROT_OUTLINE',True):
    _nr=0; _H3=[]
    for i in HAT:
        a,b=P[i][4]; t=ang(a,b)
        if in_curved(a) or (_DZ and in_diag(((a[0]+b[0])/2,(a[1]+b[1])/2))): _H3.append(i); continue
        def _only45(e):
            seen=False
            for j in tree.query(Point(e).buffer(0.08)):
                jj=LN[j]
                if jj==i or G[jj].distance(Point(e))>0.06: continue
                g_=geo(jj); u_,v_=g_[0],g_[-1]
                if math.dist(u_,v_)<0.05: continue
                tj=ang(u_,v_); seen=True
                if min(abs(tj-45),abs(tj-135))>10: return False
            return seen
        if _only45(a) and _only45(b): _nr+=1; continue
        _H3.append(i)
    HAT=_H3; print('turned outlines rejected from hatch',_nr)
from scipy.spatial import cKDTree
HATc=set(HAT)
EP=[];EPo=[]
for i in LN:
    if i in HATc: continue          # endpoints of other hatch candidates do not make a corner
    g=geo(i); EP+= [g[0],g[-1]]; EPo+=[i,i]
ktree=cKDTree(np.array(EP)); EPo=np.array(EPo)
def at_corner(p,i):
    ids=ktree.query_ball_point(p,0.06)
    return any(EPo[j]!=i for j in ids)
nd=0
H2=[]
for i in HAT:
    a,b=P[i][4]
    if at_corner(a,i) and at_corner(b,i) and own.get(i) in ('lift','door','door45','equip','grey','misc','stair') and i not in _BANDSTROKE: nd+=1; continue
    H2.append(i)
print('cell diagonals rejected',nd)
HAT=H2
_dbg('H2',HAT)
# polyline pieces of curves (arcs of the ЛК-1 wall etc.) are boundaries, not hatch:
# follow smooth continuations (turn < 25 deg) through shared endpoints; chain longer than 14 pt -> not hatch
SEGS={i:P[i][4] for i in LN if P[i][0]=='l'}
ekey=lambda p:(round(p[0]*20),round(p[1]*20))
emap=collections.defaultdict(list)
for i,(a,b) in SEGS.items(): emap[ekey(a)].append(i); emap[ekey(b)].append(i)
def dirv(i,frm):
    a,b=SEGS[i]; 
    if ekey(a)==ekey(frm): v=(b[0]-a[0],b[1]-a[1])
    else: v=(a[0]-b[0],a[1]-b[1])
    L=math.hypot(*v) or 1; return (v[0]/L,v[1]/L)
# a circle drawn as a 24-gon turns ~10-15 deg per vertex (floor 1: round table tops) - 10 deg missed it and two of its
#   sides at exactly 45/135 deg made the table top a 'wall'; (cfg.CURVE_TURN, deg; default 10 as on floors 3-5)
COSC=math.cos(math.radians(getattr(cfg,'CURVE_TURN',10)))
def has_cont(i,p):
    din=dirv(i,p); din=(-din[0],-din[1])
    return any(j!=i and (din[0]*dirv(j,p)[0]+din[1]*dirv(j,p)[1])>COSC for j in emap[ekey(p)])
def chain_len(i,maxlen=14.0):
    tot=math.dist(*SEGS[i]); seen={i}
    a0,b0=SEGS[i]
    if not (has_cont(i,a0) and has_cont(i,b0)): return 0.0     # a curve piece continues smoothly at both ends
    for end in SEGS[i]:
        cur=i; p=end
        while tot<=maxlen:
            din=dirv(cur,p); din=(-din[0],-din[1])       # direction arriving at p
            nxt=None
            for j in emap[ekey(p)]:
                if j in seen: continue
                dj=dirv(j,p)
                if din[0]*dj[0]+din[1]*dj[1]>COSC: nxt=j; break
            if nxt is None: break
            seen.add(nxt); tot+=math.dist(*SEGS[nxt])
            a,b=SEGS[nxt]; p=b if ekey(a)==ekey(p) else a; cur=nxt
    return tot
before=len(HAT)
HAT=[i for i in HAT if chain_len(i)<=14.0]
print('curve pieces removed from hatch',before-len(HAT)); _dbg('chain',HAT)
# X-pattern pairs at any angle (insulation / plasterboard symbol in thin bands)
XC=[]
_HATs=set(HAT)
for i in LN:
    p=P[i]
    if p[0]!='l' or owned_out(i,NOHATCH) or i in _HATs: continue
    c=p[2]
    if c is None or not (abs(c[0]-c[1])<0.02 and abs(c[1]-c[2])<0.02 and c[0]<=0.85): continue
    a,b=p[4]; L=math.dist(a,b)
    if not (0.8<=L<=8): continue
    t=ang(a,b)
    # axis-parallel crosses are furniture grids - except inside a 45-degree band (cfg.DIAG_ZONES), where the
    #   plasterboard X-pattern itself turns to 0/90 degrees (floor 4, partitions at the WC)
    _m=((a[0]+b[0])/2,(a[1]+b[1])/2)
    if min(t,180-t,abs(t-90))<8 and not in_diag(_m): continue
    XC.append(i)
xm=np.array([((P[i][4][0][0]+P[i][4][1][0])/2,(P[i][4][0][1]+P[i][4][1][1])/2) for i in XC]) if XC else np.zeros((0,2))
xtree=cKDTree(xm) if len(XC) else None
xadd=set()
if xtree is not None:
    for k,i in enumerate(XC):
        for j in xtree.query_ball_point(xm[k],0.3):
            if j==k: continue
            i2=XC[j]
            if LineString(P[i][4]).crosses(LineString(P[i2][4])): xadd.add(i); xadd.add(i2)
print('X-pattern lines added',len(xadd))
HAT=HAT+[i for i in xadd if i not in set(HAT)]
_dbg('X',HAT)
ends=[];eown=[]
for i in HAT:
    a,b=P[i][4]; ends+=[Point(a),Point(b)]; eown+=[i,i]
qa,qb=tree.query(ends,predicate='dwithin',distance=0.15)
touch=collections.defaultdict(set); BOUND=set()
for e,t in zip(qa,qb):
    j=LN[t]
    if j==eown[e]: continue
    touch[e].add(j)
ok=set()
for i in HAT: pass
hat=[]
for k in range(0,len(ends),2):
    i=eown[k]
    if touch.get(k) and touch.get(k+1) or (i in _CONT and (touch.get(k) or touch.get(k+1))):
        hat.append(i); BOUND|=touch.get(k,set()); BOUND|=touch.get(k+1,set())
# second pass: pattern continuation - one end on a line, parallel accepted neighbour nearby (end of a hatch run)
hs=set(hat)
acc_idx=[i for i in hat]
acc_mid=np.array([((P[i][4][0][0]+P[i][4][1][0])/2,(P[i][4][0][1]+P[i][4][1][1])/2) for i in acc_idx])
acc_tree=cKDTree(acc_mid)
nadd=0
for k in range(0,len(ends),2):
    i=eown[k]
    if i in hs: continue
    if not (touch.get(k) or touch.get(k+1)): continue
    a,b=P[i][4]; m=((a[0]+b[0])/2,(a[1]+b[1])/2); L=math.dist(a,b); t=ang(a,b)
    ok_=False
    for j in acc_tree.query_ball_point(m,4.0):
        jj=acc_idx[j]; a2,b2=P[jj][4]
        if abs(((ang(a2,b2)-t)+90)%180-90)<1.5 and abs(math.dist(a2,b2)-L)<0.3*L: ok_=True; break
    if ok_:
        hat.append(i); hs.add(i); nadd+=1
        for kk in (k,k+1): BOUND|=touch.get(kk,set())
print('hatch lines',len(hat),'(pattern ends added',nadd,') boundary lines',len(BOUND),round(time.time()-t0,1)); _dbg('hat',hat)
# ---- zone around hatch: 12 pt
# sparse concrete strokes (cfg.SPARSE_HATCH): collected here so that the band they float in enters the linework
SPARSE=[]
if getattr(cfg,'SPARSE_HATCH',False):
    _hs=set(hat)
    for i in LN:
        p=P[i]
        if p[0]!='l' or owned_out(i,NOHATCH) or i in _hs: continue
        c=p[2]
        if c is None or not (abs(c[0]-c[1])<0.02 and abs(c[1]-c[2])<0.02 and c[0]<=0.85): continue
        a,b=p[4]; L=math.dist(a,b)
        if not (0.8<=L<=11): continue
        t=ang(a,b)
        if min(abs(t-45),abs(t-135))>6: continue
        _m=((a[0]+b[0])/2,(a[1]+b[1])/2)
        if fac_zone.contains(Point(_m)) or plant_zone.contains(Point(_m)): continue
        SPARSE.append(i)
    print('sparse pattern strokes',len(SPARSE))
    # concrete pattern: dots and small triangles scattered in the band (floor 5, corridor walls)
    MARKS=[]
    for i in LN:
        p=P[i]
        if p[0]!='l' or owned_out(i,NOHATCH) or i in _hs: continue
        c=p[2]
        if c is None or not (abs(c[0]-c[1])<0.02 and abs(c[1]-c[2])<0.02 and c[0]<=0.85): continue
        if 0.1<=math.dist(*p[4])<=1.5: MARKS.append(i)
    # a mark floats: its ends touch no line other than marks (a dot, a small triangle); a short piece of an outline
    #   is connected to longer lines and stays linework
    _ms=set(MARKS); _keep=[]
    for i in MARKS:
        a,b=P[i][4]; ok=True
        for e in (a,b):
            for j in tree.query(Point(e).buffer(0.05)):
                jj=LN[j]
                if jj!=i and jj not in _ms and G[jj].distance(Point(e))<=0.05: ok=False; break
            if not ok: break
        if ok: _keep.append(i)
    MARKS=_keep
    print('concrete pattern marks',len(MARKS))
else: MARKS=[]
MARKSs=set(MARKS)
SPARSEs=set(SPARSE)
hr=np.zeros((H,W),np.uint8)
for i in list(hat)+SPARSE+MARKS: a,b=P[i][4]; cv2.line(hr,T(a),T(b),1,1)
Z=cv2.dilate(hr,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(int(24*S),int(24*S))))
def inZline(ps):
    for a,b in zip(ps[:-1],ps[1:]):
        n=max(1,int(math.dist(a,b)/4))
        for t in np.linspace(0,1,n+1):
            x,y=T((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t))
            if 0<=x<W and 0<=y<H and Z[y,x]: return True
    return False
lines=[]
HATS=set(hat)
for i in LN:
    if own.get(i) in ('roomsep','sign','carpet','wcsink'): continue      # never wall linework (28.09.2026)
    if owned_out(i,FURN) and i not in BOUND and i not in HATS: continue
    if (i in SPARSEs or i in MARKSs) and i not in BOUND: continue   # floating pattern strokes / marks are not boundaries
    ps=geo(i)
    if i in BOUND or i in HATS or inZline(ps) or in_wzone(ps): lines.append(G[i])
print('linework',len(lines),round(time.time()-t0,1))
# ---- exact faces: node the linework, connect dangling ends (gaps < 0.7 pt), polygonize
from shapely.ops import polygonize, nearest_points
noded=shapely.union_all(np.array(lines,dtype=object))
edges=list(noded.geoms) if noded.geom_type=='MultiLineString' else [noded]
def key(p): return (round(p[0],5),round(p[1],5))
deg=collections.Counter(); eown={}
for j,e in enumerate(edges):
    c=list(e.coords)
    for p in (c[0],c[-1]): deg[key(p)]+=1; eown.setdefault(key(p),[]).append(j)
dang=[k for k,v in deg.items() if v==1]
etree=STRtree(edges)
conn=[]
for k in dang:
    p=Point(k); mine=set(eown[k])
    best=None
    for j in etree.query(p.buffer(0.7)):
        if j in mine: continue
        d=edges[j].distance(p)
        if d<=0.7 and (best is None or d<best[0]): best=(d,j)
    if best and best[0]>1e-6:
        q=edges[best[1]].interpolate(edges[best[1]].project(p))
        conn.append(LineString([p,q]))
print('dangling ends',len(dang),'connectors',len(conn),round(time.time()-t0,1))
noded=shapely.union_all(np.array(edges+conn,dtype=object))
faces=[f for f in polygonize(noded) if f.area>1e-4]
print('faces',len(faces),round(time.time()-t0,1))
HL=[G[i] for i in hat]; HD=[]
for i in hat:
    a_,b_=P[i][4]; L=math.dist(a_,b_); HD.append(((b_[0]-a_[0])/L,(b_[1]-a_[1])/L))
HC=[P[i][2] for i in hat]
htree=STRtree(HL)
mids=[];dirs=[];fown=[];lens=[]
for k,f in enumerate(faces):
    if f.area>6000: continue
    c=list(f.exterior.coords)
    for a_,b_ in zip(c[:-1],c[1:]):
        L=math.dist(a_,b_)
        if L<0.05: continue
        mids.append(Point((a_[0]+b_[0])/2,(a_[1]+b_[1])/2)); dirs.append(((b_[0]-a_[0])/L,(b_[1]-a_[1])/L)); fown.append(k); lens.append(L)
qi,qt=htree.query(mids,predicate='dwithin',distance=0.02)
fcol=collections.defaultdict(collections.Counter); fcont=collections.Counter()
HCONT=[i in _CONT for i in hat]
for mi,hi in zip(qi,qt):
    d=dirs[mi]; h=HD[hi]
    if abs(d[0]*h[1]-d[1]*h[0])<0.05:
        fcol[fown[mi]][HC[hi]]+=lens[mi]
        if HCONT[hi]: fcont[fown[mi]]+=lens[mi]
sel=np.zeros(len(faces),bool); why=collections.Counter()
for k,cc in fcol.items():
    f=faces[k]; m=sum(cc.values()); per=f.exterior.length; th=2*f.area/per
    # a face held only by continuation strokes (cfg.WALL_CONTINUATION) is a cell of the band that goes on: small and
    #   thin (floor 1: the whole area inside the SE curved glazing touched two such strokes and became a 'wall')
    #   continuation strokes count only for small thin cells; a bigger face must be held by the other hatch alone
    if fcont[k]>0 and not (f.area<=120 and th<=4):
        m-=fcont[k]; why['cont_not_counted']+=1
    if (f.area<=120 and m>=0.3) or (th<=8 and m>=1.5 and m/per>=0.04):
        sel[k]=True; why['hatch']+=1
# (cfg.WALL_ZONES) thin faces inside an operator wall zone are wall faces of the zone's class
ZCL={}
for _z in _WZ:
    for k,f in enumerate(faces):
        if f.area>600: continue
        rp=f.representative_point()
        if not _z['p'].contains(rp) or 2*f.area/f.exterior.length>_z['maxw']: continue
        sel[k]=True; ZCL[k]=_z['cls']
# (29.09.2026, late) a zone band whose lines do not close it on the source leaks into the room next to it: its cells
#   are one face with the room (floor 2, the ramp's core at 26-43 deg - one face of 28 939 pt2). The part of such a big
#   face that lies in the zone is the zone's wall: the operator has said the band is a wall. So the zone ends where the
#   band ends and stops at every opening in it (plan/rules/30 §10)
_nleak=0
for _z in _WZ:
    for k in range(len(faces)):
        f=faces[k]
        if sel[k] or f.area<=600 or not f.intersects(_z['g']): continue
        # the zone is drawn 0.2-0.3 pt wider than its band to hold the band's lines: the cut stays 0.15 pt inside it,
        #   and the zone's margin along a big face outside the band (a strip 0.2-0.3 pt wide) is not cut at all - the
        #   first cut put the whole outer margin of the ramp's lining into the walls (edges 16 mm off the lines, floor 2)
        pc=f.intersection(_z['g'].buffer(-0.15))
        for g in getattr(pc,'geoms',[pc]):
            if g.geom_type!='Polygon' or g.area<0.5 or 2*g.area/g.exterior.length<1.0: continue
            faces.append(g); sel=np.append(sel,True); ZCL[len(faces)-1]=_z['cls']; _nleak+=1
if _WZ: why['wall_zone']=len(ZCL); print('wall zone faces',len(ZCL),round(sum(faces[k].area for k in ZCL)*MM_PER_PT**2/1e6,2),'m2','| cut from big faces',_nleak)
# (cfg.WALL_FINISH_ZONES) the finish of a wall drawn outside its body - floor 2: the teeth along the round wall - is not
#   the body: faces there that are not in a wall zone are not walls (the teeth are single thick strokes, some of them at
#   45 degrees, and read as hatch); their lines become the wall's finish in reclass.py
_WFZ=[prep(_diag_geom(z['zone'])) for z in getattr(cfg,'WALL_FINISH_ZONES',[])]
if _WFZ:
    _nf=0
    for k,f in enumerate(faces):
        if not sel[k] or k in ZCL: continue
        rp=f.representative_point()
        if any(z.contains(rp) for z in _WFZ): sel[k]=False; _nf+=1
    print('finish-zone faces left out of the walls',_nf)
# thin slivers / small cells mostly surrounded by wall faces
ftree=STRtree(faces)
for it in range(5):
    add=0
    selset=set(np.where(sel)[0])
    for k,f in enumerate(faces):
        if sel[k] or f.area>30: continue
        per=f.exterior.length; th=2*f.area/per
        shared=0.0
        for j in ftree.query(f):
            if j==k or j not in selset: continue
            shared+=f.exterior.intersection(faces[j].exterior).length
        r=shared/per
        if (th<1.0 and r>=0.6) or r>=0.8: sel[k]=True; add+=1
    why['surrounded']+=add
    if add==0: break
# a tiny cell (<= 3 pt2, i.e. < 110 mm) between wall faces on two opposite sides is part of the wall (floor 5: stud
#   squares every 25 pt in a plasterboard partition left 70-80 mm holes). No opening is that small.
if getattr(cfg,'TINY_CELLS',False):
    selset=set(np.where(sel)[0]); _nt=0
    for k,f in enumerate(faces):
        if sel[k] or f.area>3: continue
        per=f.exterior.length; nb=[]
        for j in ftree.query(f):
            if j==k or j not in selset: continue
            L_=f.exterior.intersection(faces[j].exterior).length
            if L_>0.1: nb.append((j,L_))
        if len(nb)>=2 and sum(L_ for _,L_ in nb)>=0.4*per: sel[k]=True; _nt+=1
    # a stud drawn as a square frame (two nested squares of thick lines, floor 5) splits into a ring and a core:
    #   neither piece touches the wall on two sides, their union does - judge groups of adjacent small faces as one
    _sm=[k for k,f in enumerate(faces) if not sel[k] and f.area<=3]
    _sms=set(_sm); _par={k:k for k in _sm}
    def _fd(x):
        while _par[x]!=x: _par[x]=_par[_par[x]]; x=_par[x]
        return x
    for k in _sm:
        for j in ftree.query(faces[k]):
            if j!=k and j in _sms and faces[k].exterior.intersection(faces[j].exterior).length>0.05: _par[_fd(k)]=_fd(j)
    _grp=collections.defaultdict(list)
    for k in _sm: _grp[_fd(k)].append(k)
    selset=set(np.where(sel)[0])
    for g_ in _grp.values():
        if len(g_)<2: continue
        U_=unary_union([faces[k] for k in g_])
        if U_.geom_type!='Polygon' or U_.area>3.5: continue
        per=U_.exterior.length; nb=[]
        for j in ftree.query(U_):
            if j in selset:
                L_=U_.exterior.intersection(faces[j].exterior).length
                if L_>0.1: nb.append((j,L_))
        if len(nb)>=2 and sum(L_ for _,L_ in nb)>=0.4*per:
            for k in g_: sel[k]=True
            _nt+=len(g_)
    why['tiny_between']=_nt
# sparse concrete pattern (floor 5, cfg.SPARSE_HATCH=True): 45/135 strokes that float inside a band without
#   reaching its edges (reinforced concrete). A thin face (2A/P <= 12 pt) holding at least 3 such strokes, one per
#   12 pt of its length, is a wall. Off by default: on floor 3 no wall is drawn like that.
if getattr(cfg,'SPARSE_HATCH',False):
    _sp=[LineString(P[i][4]) for i in SPARSE]
    _spt=STRtree(_sp) if _sp else None
    _nsp=0
    for k,f in enumerate(faces):
        if sel[k] or f.area<2 or f.area>2500 or _spt is None: continue
        per=f.exterior.length; th=2*f.area/per
        if th>12: continue
        fz=prep(f.buffer(0.2))
        n_=sum(1 for j in _spt.query(f) if fz.contains(_sp[j]))
        if n_>=3 and n_>=(per/2)/12: sel[k]=True; _nsp+=1
    why['sparse_hatch']=_nsp
    # concrete marks: an elongated band (length >= 4 x width, width 1-8 pt) with a mark strictly inside every 4 pt
    _mk=[LineString(P[i][4]) for i in MARKS]; _mkt=STRtree(_mk) if _mk else None; _nmk=0
    for k,f in enumerate(faces):
        if sel[k] or _mkt is None or f.area<2 or f.area>2500: continue
        r_=f.minimum_rotated_rectangle; xy_=list(r_.exterior.coords); e_=sorted([math.dist(xy_[0],xy_[1]),math.dist(xy_[1],xy_[2])])
        if not (1.0<=e_[0]<=8 and e_[1]>=4*e_[0] and f.area/r_.area>=0.6): continue
        fin=prep(f.buffer(-0.1)) if not f.buffer(-0.1).is_empty else None
        if fin is None: continue
        n_=sum(1 for j in _mkt.query(f) if fin.contains(_mk[j]))
        if n_>=3 and n_>=e_[1]/4: sel[k]=True; _nmk+=1
    why['concrete_marks']=_nmk
# walls are elongated bands: a small round face (bin, dryer, pipe) next to a wall is never a wall
for k in np.where(sel)[0]:
    f=faces[k]
    if f.area<40 and 4*math.pi*f.area/f.exterior.length**2>0.88: sel[k]=False; why['round_dropped']+=1
# (cfg.NOHATCH_BOXES, 30.09.2026, floor 5) an operator box of 'no wall here' (a door leaf drawn closed in the opening
#   with its own hatch): without hatch its small cells still joined the walls by the 'surrounded' and TINY_CELLS rules
#   (floor 5, the door at (942, 234-249)). A face whose representative point lies in such a box is not a wall; the
#   same for the ink faces below. Default []: other floors do not change.
_NHB=[tuple(b) for b in getattr(cfg,'NOHATCH_BOXES',[])]+_D45   # + the bands of the doors 'leaf + chord' (doors45.json)
def _in_nhb(g):
    rp=g.representative_point(); return any(b[0]<=rp.x<=b[2] and b[1]<=rp.y<=b[3] for b in _NHB)
if _NHB:
    for k in np.where(sel)[0]:
        if _in_nhb(faces[k]): sel[k]=False; why['nohatch_box']+=1
print('selected',int(sel.sum()),dict(why),round(time.time()-t0,1))
# ---- unhatched strip candidates (report only)
Ubnd=unary_union([faces[k].buffer(0.05) for k in np.where(sel)[0]])
cands=[]
for k,f in enumerate(faces):
    if sel[k] or f.area<1 or f.area>600: continue
    r=f.minimum_rotated_rectangle; xs=list(r.exterior.coords)
    e1=math.dist(xs[0],xs[1]); e2=math.dist(xs[1],xs[2]); w=min(e1,e2); L=max(e1,e2)
    if not (1.2<=w<=12 and L>=3*w and f.area/r.area>=0.85): continue
    sh=f.exterior.intersection(Ubnd).length/f.exterior.length
    if sh>=0.2: cands.append((k,round(w*MM_PER_PT),round(L*MM_PER_PT),round(sh,2),[round(v,1) for v in f.bounds]))
print('unhatched strip candidates',[c[1:] for c in cands])
# ---- classes: by the hatch colour/pattern adjacent to each face; propagate to faces without own hatch
def fclass(k):
    cc=fcol.get(k)
    if not cc: return None
    g=sum(v for c,v in cc.items() if c[0]>0.3); b=sum(v for c,v in cc.items() if c[0]<=0.3)
    return 'cap' if g>=b else 'blk'
# X pattern (black, both diagonals near) -> gkl
b45=np.zeros((H,W),np.uint8); b135=np.zeros((H,W),np.uint8)
for i in hat:
    if P[i][2][0]>0.3: continue
    a,b=P[i][4]; t=ang(a,b)
    if _DZ and in_diag(((a[0]+b[0])/2,(a[1]+b[1])/2)): t=(t+45)%180      # the pattern of a 45-degree band is turned too
    cv2.line(b45 if abs(t-45)<20 else b135,T(a),T(b),1,1)
r_=int(3*S); X2=(cv2.dilate(b45,np.ones((r_,r_),np.uint8))>0)&(cv2.dilate(b135,np.ones((r_,r_),np.uint8))>0)
def inext(p): return zone_contains('EXT_ZONES',p)   # boxes or bands (floor 1: the curved east wall)
lab={}
for k in np.where(sel)[0]:
    f=faces[k]; rp=f.representative_point()
    if inext((rp.x,rp.y)): lab[k]='ext'; continue
    c=fclass(k)
    if c=='blk':
        x,y=T((rp.x,rp.y)); c='gkl' if X2[min(max(y,0),H-1),min(max(x,0),W-1)] else 'blk'
    lab[k]=c
# faces without class take the class of the neighbour sharing most boundary
selk=[k for k in np.where(sel)[0]]
st=STRtree([faces[k].buffer(0.05) for k in selk])
for it in range(6):
    miss=[k for k in selk if lab.get(k) is None]
    if not miss: break
    for k in miss:
        best=collections.Counter()
        for j in st.query(faces[k]):
            kk=selk[j]
            if kk==k or lab.get(kk) is None: continue
            best[lab[kk]]+=faces[kk].buffer(0.05).intersection(faces[k].exterior).length
        if best: lab[k]=best.most_common(1)[0][0]
for k in selk:
    if lab.get(k) is None: lab[k]='cap'
# ---- smooth classes within one hatched band layer: faces separated only by hatch lines form one group
par={k:k for k in selk}
def fnd(a):
    while par[a]!=a: par[a]=par[par[a]]; a=par[a]
    return a
stt=STRtree([faces[k] for k in selk])
for ii,k in enumerate(selk):
    fa=faces[k]
    for jj in stt.query(fa):
        if jj<=ii: continue
        kb=selk[jj]; fb=faces[kb]
        sh=fa.boundary.intersection(fb.boundary)
        if sh.is_empty: continue
        parts=[sh] if sh.geom_type=='LineString' else [g for g in getattr(sh,'geoms',[]) if g.geom_type=='LineString']
        for g in parts:
            if g.length<0.2: continue
            m=g.interpolate(0.5,normalized=True)
            if any(HL[j].distance(m)<0.03 for j in htree.query(m.buffer(0.05))):
                par[fnd(k)]=fnd(kb); break
grp=collections.defaultdict(list)
for k in selk: grp[fnd(k)].append(k)
nchg=0
for g,ks in grp.items():
    votes=collections.Counter()
    for k in ks: votes[lab[k]]+=faces[k].area
    best=votes.most_common(1)[0][0]
    for k in ks:
        if lab[k]!=best: lab[k]=best; nchg+=1
print('band groups',len(grp),'faces relabelled',nchg)
for k,c_ in ZCL.items(): lab[k]=c_                                  # the operator's class for zone faces
byc=collections.defaultdict(list)
for k in selk: byc[lab[k]].append(k)
def grow(ks):
    return shapely.union_all([faces[k] for k in ks]).buffer(0)
Gr={k:grow(v) for k,v in byc.items()}
ALL=grow(selk)
# ---- robust complement: ink faces (lines buffered by EPS) close drawing gaps/channels < 0.6 pt;
#      selected ink faces grown back to the line centres are added to the exact faces
inkU=shapely.union_all(shapely.buffer(np.array(lines,dtype=object),EPS,quad_segs=2))
ifaces=[Polygon(r) for g in ([inkU] if inkU.geom_type=='Polygon' else list(inkU.geoms)) for r in g.interiors]
ifaces=[f for f in ifaces if f.area>0.02]
mids=[];dirs=[];iown=[];lens=[]
for k,f in enumerate(ifaces):
    if f.area>6000: continue
    c=list(f.exterior.coords)
    for a_,b_ in zip(c[:-1],c[1:]):
        L=math.dist(a_,b_)
        if L<0.3: continue
        mids.append(Point((a_[0]+b_[0])/2,(a_[1]+b_[1])/2)); dirs.append(((b_[0]-a_[0])/L,(b_[1]-a_[1])/L)); iown.append(k); lens.append(L)
qi,qt=htree.query(mids,predicate='dwithin',distance=EPS+0.08)
icol=collections.Counter(); icont=collections.Counter()
for mi,hi in zip(qi,qt):
    d=dirs[mi]; h=HD[hi]
    if abs(d[0]*h[1]-d[1]*h[0])<0.08 and HL[hi].distance(mids[mi])>=EPS-0.08:
        icol[iown[mi]]+=lens[mi]
        if HCONT[hi]: icont[iown[mi]]+=lens[mi]
def _im(k,m):   # the same guard as for the exact faces: continuation strokes count only for small thin cells
    f=ifaces[k]; return m if (f.area<=120 and 2*f.area/f.exterior.length<=4) else m-icont[k]
# (29.09.2026) 'thin' by 2A/P <= 8 is also a big face with a long ragged outline: floor 2, the lobby between the curved
#   glazing and the panoramic lift (920 pt2, 2A/P 5.8) touched the car's diagonals - grey strokes 11.7 pt long, taken
#   for a capital wall's hatch - along 6 % of its outline and became plasterboard with a quarter of the car. A face
#   > 120 pt2 held so is a wall only when it is thin indeed - its inscribed circle <= 6 pt (a wall <= 760 mm) - or the
#   hatch runs along >= 20 % of its outline (check 3.12 found the place)
import shapely as _shp
def _thin_ok(f,m):
    return f.area<=120 or m/f.exterior.length>=0.2 or _shp.maximum_inscribed_circle(f,0.2).length<=6
isel=[k for k,m0 in icol.items() for m in [_im(k,m0)] if (ifaces[k].area<=120 and m>=0.5) or (2*ifaces[k].area/ifaces[k].exterior.length<=8 and m>=1.5 and m/ifaces[k].exterior.length>=0.04 and _thin_ok(ifaces[k],m))]
isel=[k for k in isel if not (ifaces[k].area<40 and 4*math.pi*ifaces[k].area/ifaces[k].exterior.length**2>0.88)]
if _NHB: isel=[k for k in isel if not _in_nhb(ifaces[k])]   # (cfg.NOHATCH_BOXES) see above
if _WFZ:   # (cfg.WALL_FINISH_ZONES) nor through the ink faces
    _wzp=[z['p'] for z in _WZ]
    isel=[k for k in isel if not (any(z.contains(ifaces[k].representative_point()) for z in _WFZ) and not any(z.contains(ifaces[k].representative_point()) for z in _wzp))]
# (01.10.2026, code 005) a negative buffer of a multi-part geometry is taken part by part. GEOS lost whole parts of a
#   multi-part negative buffer: floor 4, round 2 - the ink faces (35 parts) shrunk by 0.06 pt lost 189 pt2, among them
#   an X-hatched wall piece 0.04 m2 at (816, 179) that round 1 of the same floor kept. Whether a part is lost depends on
#   the whole floor, so a change anywhere moved walls far from it. The parts of a valid multipolygon are disjoint, so the
#   result is the same set - only without the losses
def _nbuf(g, d, **kw):
    if d >= 0 or g.is_empty: return g.buffer(d, **kw)
    parts = list(g.geoms) if hasattr(g, 'geoms') else [g]
    return unary_union([p.buffer(d, **kw) for p in parts if not p.is_empty])
INK=_nbuf(shapely.union_all([ifaces[k].buffer(EPS+0.06,join_style=2,mitre_limit=6) for k in isel]),-0.06,join_style=2,mitre_limit=6)
# ---- complete cells cut off by a hatch line at a wall end (the band continues past the last hatch line)
def complete_ends(G):
    polys=list(G.geoms) if G.geom_type=='MultiPolygon' else [G]
    ltree=STRtree(lines)
    adds=[]
    for pg in polys:
        for ring in [pg.exterior]+list(pg.interiors):
            c=list(ring.coords)
            for p,q in zip(c[:-1],c[1:]):
                L=math.dist(p,q)
                if L<0.4: continue
                mid=Point((p[0]+q[0])/2,(p[1]+q[1])/2); d=((q[0]-p[0])/L,(q[1]-p[1])/L)
                hit=False
                for j in htree.query(mid.buffer(0.03)):
                    h=HD[j]
                    if HL[j].distance(mid)<0.03 and abs(d[0]*h[1]-d[1]*h[0])<0.05: hit=True; break
                if not hit: continue
                n=(-d[1],d[0])
                if pg.contains(Point(mid.x+n[0]*0.1,mid.y+n[1]*0.1)): n=(-n[0],-n[1])   # outward
                ext=[]
                for e in (p,q):
                    best=None
                    for j in ltree.query(Point(e).buffer(0.05)):
                        ln=lines[j]
                        if ln.distance(Point(e))>0.03 or ln.length<0.5: continue
                        cc=list(ln.coords)
                        for a_,b_ in zip(cc[:-1],cc[1:]):
                            seg=LineString([a_,b_])
                            if seg.distance(Point(e))>0.03: continue
                            for far in (a_,b_):
                                v=(far[0]-e[0],far[1]-e[1]); dl=math.hypot(*v)
                                if dl<0.2 or dl>4.0: continue
                                if (v[0]*n[0]+v[1]*n[1])/dl<0.3: continue
                                if best is None or dl<best[0]: best=(dl,far,(v[0]/dl,v[1]/dl))
                    ext.append(best)
                if not ext[0] and not ext[1]: continue
                if ext[0] and ext[1]:
                    if abs(ext[0][2][0]*ext[1][2][1]-ext[0][2][1]*ext[1][2][0])>0.09: continue
                    far0,far1=ext[0][1],ext[1][1]
                else:
                    # hatch line reaches the band end at one corner: triangle, closing side must lie on a source line
                    far0=ext[0][1] if ext[0] else p; far1=ext[1][1] if ext[1] else q
                    cm=Point((far0[0]+far1[0])/2,(far0[1]+far1[1])/2)
                    if not any(lines[j].distance(cm)<0.12 for j in ltree.query(cm.buffer(0.15))): continue
                cell=Polygon([p,far0,far1,q]).buffer(0)
                if cell.is_empty or cell.area>20 or cell.area<0.05: continue
                if cell.difference(G).area<0.05: continue
                adds.append(cell)
    return adds
adds=complete_ends(ALL)
print('end cells completed',len(adds),round(sum(a.area for a in adds),2))
if adds: ALL=unary_union([ALL]+[a.buffer(0.01,join_style=2) for a in adds]).buffer(0)
extra=INK.difference(ALL.buffer(0.02))
print('ink faces',len(ifaces),'selected',len(isel),'extra area from ink',round(extra.area,1))
ALL=unary_union([ALL,INK]).buffer(0)
CLR=0.35   # close hairline gaps between wall layers / drawing gaps < 0.7 pt (46 mm)
ALL=_nbuf(ALL.buffer(CLR,join_style=2,mitre_limit=4),-CLR,join_style=2,mitre_limit=4)
order=['ext','cap','gkl','blk']; acc=None; Wpt={}
def tidy(g):
    out=[]
    for p in ([g] if g.geom_type=='Polygon' else list(getattr(g,'geoms',[]))):
        if p.geom_type!='Polygon' or p.area<0.3: continue
        holes=[h for h in p.interiors if Polygon(h).area>=0.6]
        q=Polygon(p.exterior,holes).simplify(0.02,preserve_topology=True)
        if not q.is_valid: q=shapely.make_valid(q)
        for r in ([q] if q.geom_type=='Polygon' else [x for x in getattr(q,'geoms',[]) if x.geom_type=='Polygon']):
            if r.area>=0.3: out.append(r)
    return out
# drop small isolated non-rectangular specks (plant leaves etc.)
allg=ALL
comps=list(allg.geoms) if allg.geom_type=='MultiPolygon' else [allg]
pz=Point(-1e6,-1e6).buffer(1) if _PLANTC else unary_union([plant_disc(q).buffer(4) for q in inst_ if q['key']=='plant' and q['prims']]+[h.buffer(12) for h in hubs])
rz=unary_union([sbox(*ibb(q)).buffer(0.5) for q in inst_ if q['key'] in ('rack','kitchen','desk','mtable','dtable','sofa') and q['prims']])
drop=[]
for c in comps:
    others=[o for o in comps if o is not c and o.distance(c)<0.05]
    if c.area<150 and c.intersects(pz) and not others:
        # a piece with a regular pattern (2+ pairs of parallel hatch strokes inside) is a partition next to the
        #   plants, not leaves (floor 1: the plasterboard partition at axis 9 stood among planters)
        _in=[i for i in hat if c.buffer(0.05).contains(G[i])]
        _dd=[ang(*P[i][4]) for i in _in]
        _pp=sum(1 for x in range(len(_dd)) for y in range(x+1,len(_dd)) if abs(((_dd[x]-_dd[y])+90)%180-90)<2)
        if not (getattr(cfg,'SPECK_PATTERN_KEEP',True) and _pp>=4 and len(_in)>=6): drop.append(c); continue
    if c.area<3 and rz.contains(c): drop.append(c); continue
    if c.area<2.0 and not others: drop.append(c); continue
    if c.area<60 and not others:
        inside=[i for i in hat if c.buffer(0.05).contains(G[i])]
        dirs_=[ang(*P[i][4]) for i in inside]
        # the turned sawtooth of a 45-degree band (cfg.DIAG_ZONES) is quantised a few degrees off 0/90
        _tol=4 if (_DZ and in_diag((c.centroid.x,c.centroid.y))) else 2
        par_=sum(1 for x in range(len(dirs_)) for y in range(x+1,len(dirs_)) if abs(((dirs_[x]-dirs_[y])+90)%180-90)<_tol)
        if os.environ.get('DBG_SPECK'): print('DBG speck',[round(v) for v in c.bounds],round(c.area,1),'inside',len(inside),[round(d_) for d_ in dirs_],'par',par_,'tol',_tol)
        if par_<2 and not (_tol==4 and len(inside)>=2): drop.append(c); continue   # in a declared 45-degree band two strokes suffice
    # a compact isolated body (thickness 2A/P >= 3 pt, < 600 pt2) without two DISTINCT parallel hatch strokes >= 1.5 pt
    #   (offset >= 0.5 pt: an outline drawn twice is not a pattern) is furniture read as hatch: turned poufs, sofas and
    #   armchairs, rack tops, a stair stringer (floor 6: 7 such 'walls'; floor 1: 2). Thin strips keep their short strokes.
    #   Floors 2-5: none. Opt-in (cfg.COMPACT_FURNITURE_DROP=True, floor 6): on floor 1 dropping a false body at the north
    #   wall let the next round close the gate opening beside it with a false 'ext' wall.
    if getattr(cfg,'COMPACT_FURNITURE_DROP',False) and c.area<600 and not others and 2*c.area/max(c.length,1e-9)>=3:
        _ins=[i for i in hat if c.buffer(0.05).contains(G[i]) and math.dist(*P[i][4])>=1.5]
        _reg=False
        for x in range(len(_ins)):
            for y in range(x+1,len(_ins)):
                if abs(((ang(*P[_ins[x]][4])-ang(*P[_ins[y]][4]))+90)%180-90)>=2: continue
                (x1,y1),(x2,y2)=P[_ins[x]][4]; L_=math.dist((x1,y1),(x2,y2)); nx,ny=-(y2-y1)/L_,(x2-x1)/L_
                mx,my=[(u+v)/2 for u,v in zip(*P[_ins[y]][4])]
                if abs((mx-x1)*nx+(my-y1)*ny)>=0.5: _reg=True; break
            if _reg: break
        if not _reg: drop.append(c); continue
print('dropped specks',len(drop),[(round(c.area,1),[round(v) for v in c.bounds]) for c in drop][:12])
if os.environ.get('DBG_SPECK'): print('DBG all drops',[(round(c.area,1),[round(v) for v in c.bounds],bool(c.intersects(pz))) for c in drop])
if drop:
    D_=unary_union([c.buffer(0.01) for c in drop])
    Gr={k:v.difference(D_) for k,v in Gr.items()}
    ALL=ALL.difference(D_)
for k in order:
    g=Gr.get(k)
    if g is None: Wpt[k]=[]; continue
    g=g.intersection(ALL)
    if acc is not None: g=g.difference(acc)
    acc=g if acc is None else unary_union([acc,g])
    Wpt[k]=tidy(g)
# anything of ALL not covered by a class (hairlines between classes) goes to the neighbouring class
rest=ALL.difference(acc)
if not rest.is_empty:
    for r in (rest.geoms if hasattr(rest,'geoms') else [rest]):
        if r.geom_type!='Polygon' or r.area<1e-4: continue
        best=max(order,key=lambda k:sum(p.buffer(0.05).intersection(r).area for p in Wpt[k]))
        Wpt[best]=tidy(unary_union(Wpt[best]+[r]))
# thin slivers (finish layers < 0.5 pt = 33 mm thick) take the class of the wall body they line
# (01.10.2026, floor 3, code 005) the thickness is measured on the piece opened by 0.02 pt: a zero-width tail that the
#   class cut (difference with the classes above) leaves along a neighbour's edge adds its length to the perimeter but
#   no area - floor 3, the plasterboard wall at (863, 286), 1.5 pt thick, grew a hairline tail 113 pt long along the
#   capital wall, measured 0.43 pt and went to 'cap' whole (0.30 m2). A real sliver (>= 0.04 pt) keeps its measure
def _th_open(p):
    q=p.buffer(-0.02,join_style=2,mitre_limit=6).buffer(0.02,join_style=2,mitre_limit=6)
    if q.is_empty: return 0.0
    per=sum(g.exterior.length for g in getattr(q,'geoms',[q]) if g.geom_type=='Polygon')
    return 2*q.area/per if per>0 else 0.0
moved=0
for k in order:
    keep=[]
    for p in Wpt.get(k,[]):
        per=p.exterior.length; th=2*p.area/per
        if th<0.5 and _th_open(p)>=0.5: th=_th_open(p)
        if th>=0.5: keep.append(p); continue
        pb=p.buffer(0.05)
        sc={k2:sum(q.buffer(0.05).intersection(pb).area for q in Wpt.get(k2,[]))/0.1 for k2 in order if k2!=k}
        k2=max(sc,key=sc.get) if sc else None
        if k2 and sc[k2]>=0.3*per/2:
            Wpt[k2]=tidy(unary_union(Wpt[k2]+[p])); moved+=1
        else: keep.append(p)
    Wpt[k]=keep
print('thin slivers reassigned',moved)
# (29.09.2026) cfg.WALL_ADD: explicit wall bodies (pt polygons) the operator adds where a partial sheet has lost a
#   through element's walls (floor 5: the lift core, drawn by outlines only - owner 29.09: the floors shown whole are
#   the more reliable, draw the core as the walls there). Made by checks/wall_transfer.py from the reference floor's
#   walls (pair registration), edges snapped to this sheet's own lines; each entry dict(cls, poly=[(x,y),...], why)
_WA=getattr(cfg,'WALL_ADD',[])
def _clip_local(polys,cut):
    # only the pieces the operator's geometry touches are re-made: a union and tidy of a whole class changes how the
    #   later steps see its other pieces (floor 2: a thin 'blk' strip 0.11 m2 at the east diagonal was lost, 29.09.2026)
    hit=[g for g in polys if g.intersects(cut)]
    if not hit: return polys
    return [g for g in polys if not g.intersects(cut)]+tidy(unary_union(hit).difference(cut))
if _WA:
    for e in _WA:
        pg_=Polygon(e['poly']).buffer(0)
        for k in order:
            if k==e['cls']: continue
            Wpt[k]=_clip_local(Wpt.get(k) or [],pg_)
        _own=Wpt.get(e['cls']) or []; _h=[g for g in _own if g.intersects(pg_.buffer(0.01))]
        Wpt[e['cls']]=[g for g in _own if not g.intersects(pg_.buffer(0.01))]+tidy(unary_union(_h+[pg_]))
        ALL=unary_union([ALL,pg_]).buffer(0)
    print('operator wall bodies added',len(_WA),round(sum(Polygon(e['poly']).area for e in _WA)*MM_PER_PT**2/1e6,2),'m2')
if _WFZ:   # (cfg.WALL_FINISH_ZONES) whatever of the walls still reaches into a finish zone past the wall zone is cut off
    _cut=unary_union([_diag_geom(z['zone']) for z in getattr(cfg,'WALL_FINISH_ZONES',[])])
    if _WZ: _cut=_cut.difference(unary_union([z['g'] for z in _WZ]))
    for k in order:
        if Wpt.get(k): Wpt[k]=_clip_local(Wpt[k],_cut)
    ALL=ALL.difference(_cut)
aff=[kx[0],0,0,ky[0],kx[1],ky[1]]
# merge pieces of one class that touch along an edge and close drawing notches < 0.7 pt (46 mm);
# classes stay disjoint (priority ext > cap > gkl > blk)
acc2=None
for k in order:
    if not Wpt.get(k): continue
    m_=_nbuf(unary_union([p.buffer(0.35,join_style=2,mitre_limit=6) for p in Wpt[k]]),-0.35,join_style=2,mitre_limit=6)
    m_=m_.intersection(ALL.buffer(0.35,join_style=2,mitre_limit=6))
    if acc2 is not None: m_=m_.difference(acc2)
    acc2=m_ if acc2 is None else unary_union([acc2,m_])
    Wpt[k]=tidy(m_)
# ---- cut small notches and spikes: a run of ring vertices whose ends are <= 0.8 pt apart,
#      that deviates <= 1.2 pt from the chord and encloses <= 0.6 pt2, is replaced by the chord
def cut_ring(c):
    c=list(c[:-1]); changed=True; n_cut=0
    while changed and len(c)>4:
        changed=False; n=len(c)
        for i in range(n):
            for L in range(2,7):
                j=(i+L)%n
                if L>=n-2: break
                a,b=c[i],c[j]
                if math.dist(a,b)>0.8: continue
                run=[c[(i+k)%n] for k in range(L+1)]
                area=abs(Polygon(run).area) if len(run)>=3 else 0
                if area>0.6: continue
                seg=LineString([a,b]) if math.dist(a,b)>1e-9 else Point(a)
                if max(seg.distance(Point(q)) for q in run[1:-1])>1.2: continue
                idx=[(i+k)%n for k in range(1,L)]
                c=[q for t,q in enumerate(c) if t not in set(idx)]
                changed=True; n_cut+=1; break
            if changed: break
    return c+[c[0]], n_cut
def cut_poly(p):
    ext,n1=cut_ring(list(p.exterior.coords)); holes=[]; n=n1
    for h in p.interiors:
        hc,n2=cut_ring(list(h.coords)); n+=n2
        if len(hc)>=4 and Polygon(hc).area>0.6: holes.append(hc)
    q=Polygon(ext,holes)
    if not q.is_valid or abs(q.area-p.area)>2.0: return p,0
    return q,n
ncut=0
for k in order:
    out_=[]
    for p in Wpt.get(k,[]):
        q,n=cut_poly(p); ncut+=n; out_.append(q)
    Wpt[k]=out_
acc3=None
for k in order:
    if not Wpt.get(k): continue
    g=unary_union(Wpt[k])
    if acc3 is not None: g=g.difference(acc3)
    acc3=g if acc3 is None else unary_union([acc3,g])
    Wpt[k]=tidy(g)
print('notches/spikes cut',ncut)
# ---- hairline gaps between wall bodies of different classes (< 0.7 pt): fill and give to the neighbour
Uall=unary_union([p for k in order for p in Wpt.get(k,[])])
Cl=_nbuf(Uall.buffer(0.35,join_style=2,mitre_limit=6),-0.35,join_style=2,mitre_limit=6)
gaps_=Cl.difference(Uall)
nfill=0
for r in (gaps_.geoms if hasattr(gaps_,'geoms') else [gaps_]):
    if r.geom_type!='Polygon' or r.area<1e-4 or r.area>3.0: continue
    best=max(order,key=lambda k:sum(p.buffer(0.02).intersection(r.boundary).length for p in Wpt.get(k,[])))
    Wpt[best]=tidy(unary_union(Wpt[best]+[r.buffer(0.005,join_style=2)]).buffer(0))
    nfill+=1
acc4=None
for k in order:
    if not Wpt.get(k): continue
    g=unary_union(Wpt[k])
    if acc4 is not None: g=g.difference(acc4)
    acc4=g if acc4 is None else unary_union([acc4,g])
    Wpt[k]=tidy(g)
print('hairline gaps filled',nfill)
# ---- micro-gaps (< 0.5 pt = 33 mm) between separate wall bodies: bridge with the local convex hull
from shapely.ops import nearest_points as _np
nbr=0
for it in range(3):
    Uall=unary_union([p for k in order for p in Wpt.get(k,[])])
    parts_=list(Uall.geoms) if Uall.geom_type=='MultiPolygon' else [Uall]
    tr_=STRtree(parts_); done=False
    for i_,A in enumerate(parts_):
        for j_ in tr_.query(A.buffer(0.5)):
            if j_<=i_: continue
            B=parts_[j_]; d_=A.distance(B)
            if not (0<d_<0.5): continue
            a_,b_=_np(A,B); m_=Point((a_.x+b_.x)/2,(a_.y+b_.y)/2)
            disc=m_.buffer(d_+0.6)
            br=unary_union([A.intersection(disc),B.intersection(disc)]).convex_hull.difference(Uall)
            if br.is_empty or br.area>2.0: continue
            best=min(order,key=lambda k:min((p.distance(m_) for p in Wpt.get(k,[])),default=1e9))
            Wpt[best]=tidy(unary_union(Wpt[best]+[br.buffer(0.003,join_style=2)]).buffer(0)); nbr+=1; done=True
    if not done: break
acc5=None
for k in order:
    if not Wpt.get(k): continue
    g=unary_union(Wpt[k])
    if acc5 is not None: g=g.difference(acc5)
    acc5=g if acc5 is None else unary_union([acc5,g])
    Wpt[k]=tidy(g)
print('micro-gaps bridged',nbr)
def fixmm(p):
    p=affine_transform(p,aff)
    if p.is_valid: return [p]
    q=shapely.make_valid(p)
    return [x for x in ([q] if q.geom_type=='Polygon' else getattr(q,'geoms',[])) if x.geom_type=='Polygon' and x.area>100]
WALLS={k:[r for p in v for r in fixmm(p)] for k,v in Wpt.items()}
for k,v in WALLS.items(): print(k,len(v),'area m2',round(sum(p.area for p in v)/1e6,1))
pickle.dump(dict(W=WALLS,Wpt=Wpt,bridges=[],cands=cands),open('walls.pkl','wb'))
pickle.dump(dict(faces=faces,sel=sel,COV=np.zeros(len(faces))),open('faces.pkl','wb'))
pickle.dump(dict(hat=hat,BOUND=BOUND),open('hat3.pkl','wb'))
print('done',round(time.time()-t0,1))
