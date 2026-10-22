from common import *
import json, cv2, collections, importlib
import vmatch
from shapely.geometry import LineString, Point, box as sbox
P=load(); cls=pickle.load(open('cls.pkl','rb'))
def pb(i):
    ps=pts(P[i]); xs=[q[0] for q in ps]; ys=[q[1] for q in ps]; return (min(xs),min(ys),max(xs),max(ys))
PB=[pb(i) for i in range(len(P))]
import os
WALLP=pickle.load(open('wallprims.pkl','rb')) if os.path.exists('wallprims.pkl') else set()
# first round (no vector walls yet): only raster 'obj'; later rounds: everything that is not inside the final vector walls
POOL=('obj','wall') if WALLP else ('obj',)
OBJ=set(i for i,c in enumerate(cls) if c in POOL and i not in WALLP and not (P[i][0]=='qu' and P[i][3]==(1.0,1.0,1.0)))
WHITE=[i for i,c in enumerate(cls) if c=='obj' and P[i][0]=='qu' and P[i][3]==(1.0,1.0,1.0)]
free=set(OBJ); inst=[]
def take(ids): 
    s=set(ids)&free; free.difference_update(s); return s
def inbox(i,b,pad=0.3): 
    q=PB[i]; return q[0]>=b[0]-pad and q[2]<=b[2]+pad and q[1]>=b[1]-pad and q[3]<=b[3]+pad
def add(key,name,layer,ids,**kw):
    d=dict(key=key,name=name,layer=layer,prims=sorted(ids)); d.update(kw); inst.append(d); return d
from shapely.geometry import LineString as _LS, Polygon as _PG
from shapely.ops import unary_union as _UU
from shapely.prepared import prep
def prim_geom(i):
    k=P[i][0]
    if k=='l': return _LS(P[i][4])
    if k=='c': return _LS(bez(P[i][4],8))
    g=_PG(P[i][4]); return g if g.is_valid else g.buffer(0)
def tpl_geom(t,x):
    D=x['D']; pa=x['t']; ta=x['anchor']
    def tf(p):
        r=(p[0]-ta[0],p[1]-ta[1]); return (pa[0]+D[0]*r[0]+D[1]*r[1],pa[1]+D[2]*r[0]+D[3]*r[1])
    return _UU([_LS([tf(v) for v in pts(P[i])]) for i in t])
CANON=('chair','wc','sink','stool','desk','convector','door')   # drawn by canonical blocks: nothing may be attached to them
# 1 room tags: circles around digit words
words=json.load(open('words.json'))
_IN=cfg.SHEET_IN
tagw=[w for w in words if w[2].isdigit() and len(w[2])<=2 and inboxes(w[3],[_IN]) and not inboxes(w[3],getattr(cfg,'SHEET_BOXES',[])+getattr(cfg,'AXIS_BOXES',[])+getattr(cfg,'OUTSIDE_BOXES',[]))]
def _circle_pts(Q,c):
    """least-squares circle through Q with outliers dropped; returns (#points on it, R) if centred near c"""
    R=0; cx_=cy_=0
    for it in range(4):
        if len(Q)<8: return 0,0
        A=np.array([[x,y,1.0] for x,y in Q]); bb_=np.array([-(x*x+y*y) for x,y in Q])
        D_,E_,F_=np.linalg.lstsq(A,bb_,rcond=None)[0]
        cx_,cy_=-D_/2,-E_/2; R=math.sqrt(max(cx_*cx_+cy_*cy_-F_,0))
        Q=[v for v in Q if abs(math.dist((cx_,cy_),v)-R)<0.35]
    if not (3<=R<=9) or math.dist((cx_,cy_),c)>2.5: return 0,0
    return len(Q),R
def _ring(c,ids):
    """stroke ends on the mark circle around the digit. Floor 3: ~15 equal chords -> chords of the modal length
    (1-3.5 pt, +-0.15) are fitted; floor 1: the circle is ~70 micro-strokes -> all short dark strokes are fitted.
    A mark circle gives 16+ ends"""
    S_=[]; Cv=[]
    for i in ids:
        p=P[i]
        if p[2] is None or max(p[2])>=0.5: continue
        if p[0]=='c':                                   # floor 1: the circle is 4 Bezier quarters
            bp=bez(p[4],8)
            if all(2.0<=math.dist(c,v)<=9.5 for v in bp): Cv+=bp
            continue
        if p[0]!='l': continue
        L_=math.dist(*p[4])
        if 0.1<=L_<=3.5 and all(2.0<=math.dist(c,v)<=9.5 for v in p[4]): S_.append((L_,p[4]))
    best=0
    ch=[(L_,g) for L_,g in S_ if 1.0<=L_<=3.5]
    if len(ch)>=6:
        m_=collections.Counter(round(L_,1) for L_,_ in ch).most_common(1)[0][0]
        best=_circle_pts([v for L_,g in ch if abs(L_-m_)<=0.15 for v in g],c)[0]
    if best<16 and len(S_)+len(Cv)>=8:
        best=max(best,_circle_pts([v for L_,g in S_ for v in g]+Cv,c)[0])
    if best<16 and len(Cv)>=16:                         # the Bezier circle alone (floor 1: a round stool overlaps it)
        best=max(best,_circle_pts(Cv,c)[0])
    return best
for w in tagw:
    b=(w[0]-8,w[1]-8,w[0]+8,w[1]+8)
    ids=[i for i in free if inbox(i,b,0)]
    # a room mark is the number inside its circle; a bare digit ("ПК 4" on floor 4) is not
    if ids and _ring((w[0],w[1]),ids)<16: print('digit without mark circle, not a room tag',w[2],[round(w[0],1),round(w[1],1)]); continue
    if ids: add('tag','Марка помещения '+w[2],'A-90----T-',take(ids),text=w[2],c=(w[0],w[1]))
# 3 doors (before families: a family bbox must not swallow a door swing); a door owns only its arc and leaf
def leafzone(h,e,tol=0.9):
    """leaf outline: long strokes parallel to the leaf within tol, and short caps at the leaf's free end"""
    from shapely.geometry import LineString as _LS2
    z=_LS2([h,e]).buffer(tol); L2=math.dist(h,e); d2=((e[0]-h[0])/L2,(e[1]-h[1])/L2)
    out=[]
    for i in free:
        if P[i][0]!='l' or PB[i][0]>max(h[0],e[0])+tol or PB[i][2]<min(h[0],e[0])-tol or PB[i][1]>max(h[1],e[1])+tol or PB[i][3]<min(h[1],e[1])-tol: continue
        a_,b_=P[i][4]
        if not (z.contains(Point(a_)) and z.contains(Point(b_))): continue
        L_=math.dist(a_,b_)
        if L_<=1.2:
            if math.dist(a_,e)<=1.2 and math.dist(b_,e)<=1.2: out.append(i)
            continue
        d1=((b_[0]-a_[0])/L_,(b_[1]-a_[1])/L_)
        if abs(d1[0]*d2[1]-d1[1]*d2[0])<0.09 and L_>=0.5*L2: out.append(i)
    return out
_PLCD=getattr(cfg,'PLANT_COLOR',None)
def _plant_leaf(i):
    """(cfg.PLANT_COLOR, floor 2) the 'leaf' is a radial line of a plant drawn in the plant colour, the 'arc' is a piece
    of the plant's black leaf outline: two false door leaves inside one plant"""
    if _PLCD is None: return False
    c=P[i][2]; return c is not None and max(abs(c[j]-_PLCD[j]) for j in range(3))<=0.06
_DJ=json.load(open('doors.json'))
_DOK=[d for d in _DJ if d['sweep']>=getattr(cfg,'DOOR_MIN_SWEEP',70) and 550<=d['R']*MM_PER_PT<=1300 and not _plant_leaf(d['leaf'])]
for d in _DJ:
    # cabinet doors (ПК) and small arcs are not room doors; a room door may be drawn opened 70-80 deg (floor 1: 18 doors
    #   at 74-78 deg). Floor 3's two small arcs at 67-68 deg stay out.
    # A small leaf (300-550 mm) is a door leaf only as the narrow leaf of an unequal double door: its closed end meets
    #   the closed end of an accepted room door within 1.5 pt (floor 2: 900 + 500 mm; on floors 1, 3-6 no such leaf).
    _small=d['sweep']>=getattr(cfg,'DOOR_MIN_SWEEP',70) and 300<=d['R']*MM_PER_PT<550 and \
           any(math.dist(d['closed'],o['closed'])<=1.5 for o in _DOK)
    if _plant_leaf(d['leaf']): print('door leaf in the plant colour, not a door',[round(v,1) for v in d['c']]); continue
    if not _small and (d['sweep']<getattr(cfg,'DOOR_MIN_SWEEP',70) or not (550<=d['R']*MM_PER_PT<=1300)): continue
    ids=set(d['arc'])|{d['leaf']}|set(leafzone(d['c'],d['leaf_end']))
    s_=take(ids)
    if s_: add('door',f"Дверь однопольная {round(d['R']*MM_PER_PT/100)*100:.0f}",'A-32----E-',s_,R=d['R']*MM_PER_PT,c=d['c'],door=dict(c=d['c'],open=d['leaf_end'],closed=d['closed'],sweep=d['sweep']),core=sorted(s_))
# 1a colour-defined elements (cfg.COLOR_ELEMENTS): what the sheet draws in its own colour is one kind of element -
#   room separation lines (purple dashes in openings and along glass partitions, plan/rules/40 §...), the green signs
#   at the doors, washbasins in the WC cabins, carpets. Entry: dict(key, name, layer, colors=[rgb], near_colors=[rgb], near=pt,
#   inside=pt (all prims inside the shape), kinds=('l','c','qu'), min_area=pt2, boxes=[...] or None, gap=pt). A prim belongs when its stroke or fill is within 0.03 of a colour; near_colors are
#   taken only within `near` pt of an element found by `colors` (the green rectangle on the wall under a sign's
#   triangle). One element per cluster (bboxes closer than `gap`; dashes of one line are one element).
def _col_match(c,cols): return c is not None and any(max(abs(c[j]-z[j]) for j in range(3))<=0.03 for z in cols)
for _ce in getattr(cfg,'COLOR_ELEMENTS',[]):
    _bx=_ce.get('boxes') or [cfg.SHEET_IN]; _kinds=_ce.get('kinds',('l','c','qu')); _amin=_ce.get('min_area',0)
    _ids=[i for i in free if P[i][0] in _kinds and any(inbox(i,b,0.3) for b in _bx) and (_col_match(P[i][2],_ce['colors']) or (P[i][0]=='qu' and _col_match(P[i][3],_ce['colors'])))
          and (not _amin or P[i][0]!='qu' or prim_geom(i).area>=_amin)]
    _g=_ce.get('gap',0.6); _par={i:i for i in _ids}
    def _cf(x):
        while _par[x]!=x: _par[x]=_par[_par[x]]; x=_par[x]
        return x
    if _ids:
        _A=np.array([PB[i] for i in _ids])
        from scipy.spatial import cKDTree as _Kc
        _ct=_Kc(np.c_[(_A[:,0]+_A[:,2])/2,(_A[:,1]+_A[:,3])/2]); _rad=float(np.max(np.hypot(_A[:,2]-_A[:,0],_A[:,3]-_A[:,1])))/2+_g
        for a_,b_ in _ct.query_pairs(_rad):
            A_,B_=PB[_ids[a_]],PB[_ids[b_]]
            if A_[0]<=B_[2]+_g and B_[0]<=A_[2]+_g and A_[1]<=B_[3]+_g and B_[1]<=A_[3]+_g: _par[_cf(_ids[a_])]=_cf(_ids[b_])
    _cl=collections.defaultdict(list)
    for i in _ids: _cl[_cf(i)].append(i)
    _n=0
    for g_ in _cl.values():
        bb=(min(PB[i][0] for i in g_),min(PB[i][1] for i in g_),max(PB[i][2] for i in g_),max(PB[i][3] for i in g_))
        if _ce.get('near_colors'):
            nr=_ce.get('near',1.5)
            g_=g_+[i for i in free if i not in g_ and inbox(i,(bb[0]-nr,bb[1]-nr,bb[2]+nr,bb[3]+nr),0) and _col_match(P[i][2] if P[i][0]!='qu' else (P[i][3] if P[i][3] is not None else P[i][2]),_ce['near_colors'])]
        if _ce.get('inside') is not None:   # everything drawn inside the coloured shape belongs to it (washbasin: bowl, mixer)
            pd=_ce['inside']; g_=g_+[i for i in free if i not in g_ and inbox(i,bb,pd)]
        s_=take(g_)
        if s_: add(_ce['key'],_ce['name'],_ce['layer'],s_,colour=True); _n+=1
    print('colour elements',_ce['key'],_n)
# 3b door hardware drawn in the opening (floor 4; cfg.DOOR_HARDWARE=True where the source draws it): handle / stop
#    capsules and the coloured threshold line between the jambs belong to the door, not to "unclassified".
#    Zone = the opening (hinge -> closed leaf end) +-1.6 pt, flat ends. Taken: connected clusters of free prims fully
#    inside the zone whose whole extent is <= 3.5 pt, and coloured (not black / grey) lines along the opening.
#    Off by default: on floor 3 the zone would take cubicle fronts and glass-partition bits (checked, compare_runs).
from shapely.geometry import LineString as _LSd
_DHW=0
if getattr(cfg,'DOOR_HARDWARE',False):
    for dq in [q for q in inst if q['key']=='door']:
        h_=dq['door']['c']; cl_=dq['door']['closed']; Lo=math.dist(h_,cl_)
        if Lo<1: continue
        ln_=_LSd([h_,cl_]); z_=ln_.buffer(1.6,cap_style=2); zb=z_.bounds; zp=prep(z_)
        u_=((cl_[0]-h_[0])/Lo,(cl_[1]-h_[1])/Lo)
        cz=[i for i in free if PB[i][0]>=zb[0] and PB[i][2]<=zb[2] and PB[i][1]>=zb[1] and PB[i][3]<=zb[3] and zp.contains(sbox(*PB[i]).buffer(0.001))]
        par_={i:i for i in cz}
        def _f(x):
            while par_[x]!=x: par_[x]=par_[par_[x]]; x=par_[x]
            return x
        for a_i in cz:
            A=PB[a_i]
            for b_i in cz:
                if b_i<=a_i: continue
                B=PB[b_i]
                if A[0]<=B[2]+0.2 and B[0]<=A[2]+0.2 and A[1]<=B[3]+0.2 and B[1]<=A[3]+0.2: par_[_f(a_i)]=_f(b_i)
        cl__=collections.defaultdict(list)
        for i in cz: cl__[_f(i)].append(i)
        hw=[]
        for g_ in cl__.values():
            gb=(min(PB[i][0] for i in g_),min(PB[i][1] for i in g_),max(PB[i][2] for i in g_),max(PB[i][3] for i in g_))
            if max(gb[2]-gb[0],gb[3]-gb[1])<=3.5: hw+=g_; continue
            for i in g_:
                p=P[i]
                if p[0]!='l' or p[2] is None or (p[2][0]==p[2][1]==p[2][2]): continue      # coloured lines only
                a_,e_=p[4]; L_=math.dist(a_,e_)
                if L_>0 and abs(((e_[0]-a_[0])*u_[1]-(e_[1]-a_[1])*u_[0])/L_)<0.05 and ln_.distance(Point(a_))<=0.5 and ln_.distance(Point(e_))<=0.5: hw.append(i)
        if hw: add('doorhw','Фурнитура двери (ручка, упор, порог)','A-32----E-',take(hw)); _DHW+=1
print('door hardware groups',_DHW)
# 2 families via vector matching. Exemplar = a bbox on this floor, or 'LIB' = template from the family library
#   (the same Revit family on another floor); with 'LIB' the fullest match on this floor becomes the exemplar,
#   so the canonical block is always this floor's own source geometry.
def _dmul(A,B): return (A[0]*B[0]+A[1]*B[2],A[0]*B[1]+A[1]*B[3],A[2]*B[0]+A[3]*B[2],A[2]*B[1]+A[3]*B[3])
def _dT(A): return (A[0],A[2],A[1],A[3])
_lib_save=[]
for key,name,layer,bb,mf in cfg.FAMILIES:
    if bb=='LIB':
        e_,segs_=vmatch.lib_segs(key); name=name or e_['name']; layer=layer or e_['layer']; mf=mf or e_['minfrac']
        size_=2*max(max(abs(a[0]),abs(a[1]),abs(b[0]),abs(b[1])) for a,b in segs_)
        f=vmatch.match_segs(segs_,mf,anchor='long',DEDUP=0.35*size_)
        if not f: print(key,0); continue
        ex_=max(f,key=lambda x:len(x['prims']))
        t=ex_['prims']
        for x in f: x['D']=_dmul(x['D'],_dT(ex_['D'])); x['anchor']=ex_['t']
        tb=(min(PB[i][0] for i in t),min(PB[i][1] for i in t),max(PB[i][2] for i in t),max(PB[i][3] for i in t))
        bb=(tb[0]-0.2,tb[1]-0.2,tb[2]+0.2,tb[3]+0.2)
    else:
        t=vmatch.template(bb); f=vmatch.match(t,mf,anchor='long',DEDUP=0.35*max(bb[2]-bb[0],bb[3]-bb[1]))
        tb=(min(PB[i][0] for i in t),min(PB[i][1] for i in t),max(PB[i][2] for i in t),max(PB[i][3] for i in t))
        _lib_save.append((key,name,layer,t,mf))
    # any rotation angle, after the D4 poses (rotated armchairs, floor 4); only centres not found above
    if getattr(cfg,'FAMILY_ANY_ANGLE',True):
        _segs=[vmatch.seg(P[i]) for i in t]
        _fa=vmatch.match_segs_any(_segs,mf,DEDUP=0.35*max(bb[2]-bb[0],bb[3]-bb[1]),seen=[x['c'] for x in f])
        if _fa: print(key,'any-angle',len(_fa),sorted(collections.Counter(round(x['anyangle']) for x in _fa).items())[:12])
        f=f+_fa
    # exemplar fills (seat, basin...): part of the canonical block; an instance fill matching a transformed one is absorbed
    tF=[i for i in range(len(P)) if P[i][0]=='qu' and P[i][3] is not None and P[i][3]!=(1.0,1.0,1.0) and cls[i] in ('obj','wall') and inbox(i,bb,0)]
    for x in f:
        ids=set(x['prims'])
        xs=[PB[i][0] for i in ids]+[PB[i][2] for i in ids]; ys=[PB[i][1] for i in ids]+[PB[i][3] for i in ids]
        b=(min(xs),min(ys),max(xs),max(ys))
        # absorb only what the canonical block reproduces: prims lying on the transformed template (0.3 pt)
        Gt=prep(tpl_geom(t,x).buffer(0.3))
        ids|=set(i for i in free if inbox(i,b,0.2) and Gt.contains(prim_geom(i)))
        if tF:
            D_=x['D']; pa=x['t']; ta=x['anchor']
            def tf_(p): r=(p[0]-ta[0],p[1]-ta[1]); return (pa[0]+D_[0]*r[0]+D_[1]*r[1],pa[1]+D_[2]*r[0]+D_[3]*r[1])
            TFp=[_PG([tf_(v) for v in P[j][4]]).buffer(0) for j in tF]
            for i in free:
                if P[i][0]!='qu' or not inbox(i,b,0.3) or P[i][3]==(1.0,1.0,1.0): continue
                g_=prim_geom(i)
                if g_.area>0 and any(g_.intersection(h_).area>=0.8*max(g_.area,h_.area) for h_ in TFp): ids.add(i)
        if getattr(cfg,'FAMILY_WALLCLS',False):   # the matched family owns its prims even where the raster mask said 'wall'
            free.update(i for i in ids if cls[i]=='wall' and i not in WALLP)
        s=take(ids)
        if s: add(key,name,layer,s,tpl=t,tplF=tF,tplbb=tb,D=x['D'],t=x['t'],anchor=x['anchor'])
    print(key,len(f))
if getattr(cfg,'SAVE_FAMILIES_LIB',False) and _lib_save: vmatch.save_lib(_lib_save); print('families saved to library',[e[0] for e in _lib_save])
# 4 manual objects (before desks so tables are not eaten)
_PLC0=getattr(cfg,'PLANT_COLOR',None)
import detect8
for key,name,layer,boxes in cfg.MANUAL:
    # (code 008, Т4-7) an element of a record is a box or a polygon (dict(poly=[(x,y),...]) or a list of >= 3 points):
    #   a polygon takes the free primitives whose geometry lies inside it + 0.6 pt (a turned block of desks)
    if any(detect8.is_poly(b) for b in boxes):
        ids=set(i for i in free for b in boxes if detect8.element_takes(b,PB[i],lambda i=i:prim_geom(i),0.6))
    else: ids=set(i for i in free for b in boxes if inbox(i,b,0.6))
    if _PLC0 and key!='plant':   # (cfg.PLANT_COLOR) leaves of a plant over the box stay with the plant
        ids={i for i in ids if not ((lambda c:c is not None and max(abs(c[j]-_PLC0[j]) for j in range(3))<=0.06)(P[i][2] if P[i][0]!='qu' else (P[i][3] if P[i][3] is not None else P[i][2])))}
    s=take(ids)
    if s: add(key,name,layer,s)
    else: print('EMPTY manual',name)
# 4b doors 'leaf in the opening + open leaf and chord' found by doors45.py (01.10.2026, test of floor 5, T4): the door
#   takes the free primitives of its box, as an operator box 'door45' does. A detection whose hinge lies in an operator
#   box (cfg.MANUAL, any key - a door boxed by hand, a stair) is left to that box. The leaf in the opening drawn red -
#   a fire door (owner 01.10.2026, question 2)
_MB=[detect8.bbox_of(b) for key,name,layer,boxes in cfg.MANUAL for b in boxes]
_n45=[]
for d in (json.load(open('doors45.json')) if os.path.exists('doors45.json') else []):
    H_=d['H']
    if any(b[0]<=H_[0]<=b[2] and b[1]<=H_[1]<=b[3] for b in _MB): _n45.append('operator'); continue
    s=take(set(i for i in free if inbox(i,d['box'],0.6)))
    if not s: _n45.append('empty'); continue
    add('door45',f"Дверь однопольная {int(round(d['L_mm']/100.0))*100}{' противопожарная' if d.get('red') else ''} (полотно и хорда, без дуги)",'A-32----E-',s)
    _n45.append('door')
print('doors leaf + chord (doors45.json)',collections.Counter(_n45))
# (code 008, Т4-4) the front of WC cabins: the leaf drawn closed between two posts of a door in a sanitary zone - the
#   door's leaf in the opening ('door45'), the posts - partition ends ('lpartc', carriers of the jambs)
if detect8.on('wcfront'):
    if getattr(cfg,'SANZONES',None) is not None: _wz8=[tuple(z) for z in cfg.SANZONES]
    else:
        _g8=_UU([sbox(*(min(PB[i][0] for i in q['prims']),min(PB[i][1] for i in q['prims']),max(PB[i][2] for i in q['prims']),max(PB[i][3] for i in q['prims']))).buffer(10)
                 for q in inst if q['key'] in ('wc','sink') and q['prims']])
        _wz8=[]
        for g8 in (getattr(_g8,'geoms',None) or ([_g8] if not _g8.is_empty else [])):
            b8=g8.buffer(-10).bounds if not g8.buffer(-10).is_empty else g8.bounds; _wz8.append((b8[0]-2,b8[1]-2,b8[2]+2,b8[3]+2))
    _dr8=[(tuple(q['door']['c']),tuple(q['door']['closed'])) for q in inst if q['key']=='door' and q.get('door')]
    for k8,nm8,ids8 in detect8.wc_fronts(P,PB,free,_dr8,_wz8):
        s8=take(ids8)
        if s8: add(k8,nm8,'A-32----E-' if k8=='door45' else 'A-22G---E-',s8,d8='wcfront')
# 5 desks
# (cfg.DESK_MM = (min length, min depth, max depth), default 1300/550/900; floor 6: 1200 x 600 desks)
_DMM=getattr(cfg,'DESK_MM',(1300,550,900))
desks=[d for d in json.load(open('desks.json')) if d['wmm']>=_DMM[0] and _DMM[1]<=d['hmm']<=_DMM[2] and d['fill']>=0.6]
for d in desks:
    b=(d['x0'],d['y0'],d['x1'],d['y1'])
    ids_=[i for i in free if inbox(i,b,0.6)]
    # a desk owns its own tan worktop fill; a raster blob without one (plants on a long counter, floor 4) is not a desk
    if not any(P[i][0]=='qu' and is_tan(P[i][3]) for i in ids_): print('desk without worktop fill skipped',[round(v,1) for v in b]); continue
    s=take(ids_)
    if s:
        places=max(1,round(d['wmm']/1400))
        add('desk',f"Стол рабочий {d['wmm']//100*100}×{d['hmm']//100*100} ({places} раб. места)",'A-82----E-',s,places=places,bb=b)
# 5b turned desks (cfg.ROT_DESKS = dict(fills=[rgb], L=(mm,mm), S=(mm,mm)); floor 6: benches turned along the east
#    semicircle and the curved facade). A free fill of a listed worktop colour that is a rectangle (>= 0.95 of its turned
#    box) of desk size, off the axes by more than 1 deg, is a desk: the same desk element as the straight ones, inserted
#    turned (export). It owns the prims inside its box + 0.6 pt.
_RD=getattr(cfg,'ROT_DESKS',None)
if _RD:
    _nrd=0
    for i in sorted(free):
        p=P[i]
        if i not in free or p[0]!='qu' or p[3] is None or not any(max(abs(p[3][j]-z[j]) for j in range(3))<=0.02 for z in _RD['fills']): continue
        g_=prim_geom(i); r_=g_.minimum_rotated_rectangle
        if r_.area<=0 or g_.area/r_.area<0.95: continue
        xy_=list(r_.exterior.coords); e1=math.dist(xy_[0],xy_[1]); e2=math.dist(xy_[1],xy_[2])
        Lp,Sp=max(e1,e2),min(e1,e2)
        Lr,Sr=_RD.get('L',(1000,3200)),_RD.get('S',(450,1000))
        if not (Lr[0]<=Lp*MM_PER_PT<=Lr[1] and Sr[0]<=Sp*MM_PER_PT<=Sr[1]): continue
        a_=math.degrees(math.atan2(xy_[1][1]-xy_[0][1],xy_[1][0]-xy_[0][0])) if e1>=e2 else math.degrees(math.atan2(xy_[2][1]-xy_[1][1],xy_[2][0]-xy_[1][0]))
        a_%=180
        if min(a_%90,90-a_%90)<=1: continue
        z_=r_.buffer(0.6); zb_=z_.bounds; zp_=prep(z_)
        ids_=[j for j in free if PB[j][0]>=zb_[0] and PB[j][2]<=zb_[2] and PB[j][1]>=zb_[1] and PB[j][3]<=zb_[3] and zp_.contains(prim_geom(j))]
        s_=take(ids_)
        if s_:
            Lmm,Smm=Lp*MM_PER_PT,Sp*MM_PER_PT; places=max(1,round(Lmm/1400))
            add('desk',f"Стол рабочий {int(Lmm)//100*100}×{int(Smm)//100*100} ({places} раб. места)",'A-82----E-',s_,places=places,bb=r_.bounds,
                rrect=dict(c=(r_.centroid.x,r_.centroid.y),L=Lp,S=Sp,a=a_,fill=p[3]))
            _nrd+=1
    print('turned desks',_nrd)
# 6 columns: only the prims inside the section extent (flange lines +- thickness); risers, wall lines etc. stay free
_D8C=detect8.on('columns')
_MBK=[(key,detect8.bbox_of(b)) for key,name,layer,boxes in cfg.MANUAL for b in boxes]
_ncs=collections.Counter()
for c in json.load(open('columns.json')):
    x,y=c['c']
    b=c['bb']
    if _D8C:
        # (code 008, Т4-3) the column step takes only free primitives: a section inside an operator box of another class
        #   (floor 4: the frame of a cabinet at the lifts, a false column in all four tests) makes no column, and the
        #   primitives another object took stay with it (duplicates of primitives)
        _ab=max((b[2]-b[0])*(b[3]-b[1]),1e-6)
        _in=[(k_,bx) for k_,bx in _MBK if k_!='column' and bx[0]<=x<=bx[2] and bx[1]<=y<=bx[3]]
        # a box about the size of the section (< 10 times its area: the frame of a cabinet) is the object - no column;
        #   a room-size box (a stair, 10+ times) holds the I-beam at its edge: the column takes its section back from it
        if any((bx[2]-bx[0])*(bx[3]-bx[1])<10*_ab for k_,bx in _in): _ncs['in operator box']+=1; continue
        _back=set()
        if _in:
            for q in inst:
                if q['key']!='column' and any(q['key']==k_ for k_,bx in _in):
                    _sec=[i for i in q['prims'] if inbox(i,b,0.05) and cls[i] in ('obj','wall')]
                    if _sec: q['prims']=[i for i in q['prims'] if i not in set(_sec)]; _back|=set(_sec)
            if _back: free.update(_back); _ncs['taken back from a room-size box']+=1
        s=take(i for i in list(free) if inbox(i,b,0.05))
        if not s: _ncs['nothing free']+=1; continue
        _ncs['column']+=1
        add('column','Колонна стальная (двутавр)','A-28----E-',s,c=c['c'],**({'back8':sorted(_back)} if _in and _back else {})); continue
    allp=[i for i in range(len(P)) if cls[i] in ('obj','wall') and inbox(i,b,0.05)]
    s=set(allp)
    for i in s: free.discard(i)
    add('column','Колонна стальная (двутавр)','A-28----E-',s,c=c['c'])
if _D8C: print('detect8 columns',dict(_ncs))
# (code 008, Т4-1, Т4-6) desks drawn by lines - before the facade band (step 8), so the band does not take the outer side
#   of a desk at the facade, and before the light partitions (step 12), so a desk's outline does not become a partition
if detect8.on('desks'):
    _SEATK=('chair','armchair','stool')
    _seats=[sbox(*(min(PB[i][0] for i in q['prims']),min(PB[i][1] for i in q['prims']),max(PB[i][2] for i in q['prims']),max(PB[i][3] for i in q['prims'])))
            for q in inst if q['key'] in _SEATK and q['prims']]
    from shapely.strtree import STRtree as _STs
    _sst=_STs(_seats) if _seats else None
    def _seats_near(f,d): return _sst is not None and any(_seats[j].distance(f)<=d for j in _sst.query(f.buffer(d)))
    _dcol=tuple(getattr(cfg,'DESK_OUTLINE_COLOR',(0.67,0.67,0.67)))
    _nd8=collections.Counter()
    _tk8=[i for q in inst if q['key'] not in _SEATK for i in q['prims'] if P[i][0]=='l']   # lines other objects took: they close cells only
    _kd8=[q['bb'] for q in inst if q['key']=='desk' and q.get('bb')]   # filled desks of step 5
    for k_,nm_,f_,ids_ in detect8.outline_desks(P,free,_dcol,_seats_near,taken=_tk8,known=_kd8):
        s_=take(ids_)
        if s_: add(k_,nm_,'A-82----E-',s_,bb=f_.bounds,d8='desks'); _nd8[k_]+=1
    for k_,nm_,f_,ids_ in detect8.line_desks(P,PB,free,_seats,taken=_tk8,known=_kd8):
        s_=take(ids_)
        if s_: add(k_,nm_,'A-82----E-',s_,bb=f_.bounds,d8='desks'); _nd8[k_]+=1
    print('detect8 desks',dict(_nd8))
pickle.dump((inst,free),open('assign1.pkl','wb'))
print('instances',collections.Counter(q['key'] for q in inst)); print('free',len(free))
# 7 bench screens: free prims inside union of touching desk bboxes
# (28.09.2026) turned desks (ROT_DESKS) stay out: the axis box of a turned desk is far larger than the desk, and the
#   touching boxes of the floor 6 semicircle made one 'screen' of 6765 prims - convectors, fins, chairs
dbs=[q['bb'] for q in inst if q['key']=='desk' and not q.get('rrect')]
import itertools
parent=list(range(len(dbs)))
def fnd(a):
    while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
    return a
for a,b in itertools.combinations(range(len(dbs)),2):
    A,B=dbs[a],dbs[b]
    if A[0]<=B[2]+2.5 and B[0]<=A[2]+2.5 and A[1]<=B[3]+2.5 and B[1]<=A[3]+2.5: parent[fnd(a)]=fnd(b)
grp=collections.defaultdict(list)
for k in range(len(dbs)): grp[fnd(k)].append(dbs[k])
for g in grp.values():
    b=(min(x[0] for x in g),min(x[1] for x in g),max(x[2] for x in g),max(x[3] for x in g))
    s=take(i for i in free if inbox(i,b,0.8))
    if s: add('screen','Экран настольный / кабель-канал бенча','A-82----E-',s,bb=b)
# 9 plants via Hough circles on free raster
fl0=facade_multi() or LineString([(-1e6,-1e6),(-1e6+1,-1e6)])
mfree=np.zeros((H,W),np.uint8)
for i in free:
    q=np.array([T(v) for v in pts(P[i])],np.int32); cv2.polylines(mfree,[q],False,255,1)
cir=cv2.HoughCircles(cv2.GaussianBlur(mfree,(5,5),1.2),cv2.HOUGH_GRADIENT,dp=1,minDist=int(5*S),param1=100,param2=17,minRadius=int(2.6*S),maxRadius=int(6*S))
cir=[] if cir is None else [(x/S+X0,y/S+Y0,r/S) for x,y,r in cir[0]]
print('hough circles',len(cir))
# a plant circle must have radial lines: count free segments crossing centre neighbourhood
# (speed only: a bbox prefilter in numpy, then the same exact test on the few candidates)
_RL=[i for i in free if P[i][0]=='l' and math.dist(*P[i][4])>=3]
_RB=np.array([PB[i] for i in _RL],float).reshape(-1,4)
def radial(c):
    k_=np.nonzero((_RB[:,0]-0.6<=c[0])&(_RB[:,2]+0.6>=c[0])&(_RB[:,1]-0.6<=c[1])&(_RB[:,3]+0.6>=c[1]))[0]
    n=0
    for j in k_:
        a,b=P[_RL[j]][4]
        if LineString([a,b]).distance(Point(c[0],c[1]))<0.6: n+=1
    return n
cand=[c for c in cir if radial(c)>=1 and fl0.distance(Point(c[0],c[1]))>9]
print('plant centres',len(cand))
# black plants (no cfg.PLANT_COLOR): the pot must be drawn. Pot cover = share of the Hough circle's circumference along
#   which free pieces run (within 0.35 pt, within 25 deg of the tangent). A Hough circle on a rack, the treads of a stair,
#   a wooden shelf or a wall hatch has next to no drawn ring: floor 1 had 90+ such 'plants', one ate a wall piece.
#   Leaves hide much of a real pot: on floor 3 the cover of real plants is 0.11-0.78. So a candidate needs cover >= 0.10,
#   and a plant whose lines are >= 50 % axis-parallel (0/90 +-3 deg: shelves, stairs, walls) needs cover >= 0.5
#   (floor 3: axis-parallel share of real plants <= 0.45). Floor 3 does not change.
def pot_cover(c):
    cx,cy,r=c; spans=[]
    for i in free:
        b=PB[i]
        if b[2]<cx-r-0.5 or b[0]>cx+r+0.5 or b[3]<cy-r-0.5 or b[1]>cy+r+0.5 or P[i][0] not in ('l','c'): continue
        ps=pts(P[i])
        for (x1,y1),(x2,y2) in zip(ps,ps[1:]):
            L=math.hypot(x2-x1,y2-y1)
            if L<1e-6: continue
            mx,my=(x1+x2)/2,(y1+y2)/2; rr=math.hypot(mx-cx,my-cy)
            if abs(rr-r)>0.35 or rr<1e-6: continue
            if abs(((x2-x1)*(mx-cx)+(y2-y1)*(my-cy))/(L*rr))>0.42: continue
            a1=math.atan2(y1-cy,x1-cx); a2=math.atan2(y2-cy,x2-cx)
            d=(a2-a1+math.pi)%(2*math.pi)-math.pi
            lo=a1 if d>=0 else a2; spans.append((lo%(2*math.pi),abs(d)))
    if not spans: return 0.0
    cov=np.zeros(360,bool)
    for lo,w in spans:
        k0=int(math.degrees(lo)); k1=int(math.degrees(lo+w))+1
        cov[[k%360 for k in range(k0,k1)]]=True
    return cov.mean()
_POTC={}
if not getattr(cfg,'PLANT_COLOR',None):
    _pc=[(c,pot_cover(c)) for c in cand]
    if os.environ.get('DBG_POT'): print('pot cover',sorted(round(float(v),2) for _,v in _pc))
    _rej=[c for c,v in _pc if v<0.10]
    cand=[c for c,v in _pc if v>=0.10]; _POTC={k:v for k,(c,v) in enumerate([t for t in _pc if t[1]>=0.10])}
    print('plant centres without a drawn pot, dropped',len(_rej))
def _axis_share(ids):
    ax=0
    for i in ids:
        if P[i][0]!='l': continue
        a,b=P[i][4]
        if math.dist(a,b)<0.3: continue
        ang=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%90
        if min(ang,90-ang)<=3: ax+=1
    return ax/max(1,len(ids))
owner=collections.defaultdict(set)
_CC=np.array([(p[0],p[1]) for p in cand],float).reshape(-1,2)
_RMAX=max([p[2] for p in cand],default=0)
for i in list(free):
    b=PB[i]; cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
    if max(b[2]-b[0],b[3]-b[1])>14: continue
    if P[i][0]=='qu' and P[i][3] and P[i][3][0]<0.45: continue
    if not cand: break
    # (speed only) the winner has dist-r<4.5, so it is within 4.5+rmax; farther pots can neither win nor tie
    near_=np.nonzero(np.hypot(_CC[:,0]-cx,_CC[:,1]-cy)<4.5+_RMAX+0.01)[0]
    if not len(near_): continue
    if fl0.distance(Point(cx,cy))<6: continue
    d=[(math.dist((cx,cy),(cand[k][0],cand[k][1]))-cand[k][2],int(k)) for k in near_]
    dm,k=min(d)
    if dm<4.5: owner[k].add(i)
# (cfg.PLANT_COLOR, floor 5) plants are drawn in their own colour (green leaves, brown/tan pot): a plant takes the
#   coloured prims around its pot and neutral ones only inside the pot circle, and needs 5+ prims of the plant colour.
#   Without it a Hough circle on a WC front or a table took the partition, the desk ends, the table hatch.
_PLC=getattr(cfg,'PLANT_COLOR',None)
def _pcol(i):
    p=P[i]; return (p[3] if p[3] is not None else p[2]) if p[0]=='qu' else p[2]
def _neutral(c): return c is None or (abs(c[0]-c[1])<0.03 and abs(c[1]-c[2])<0.03)
def _spokes(c,ids):
    """directions (>= 15 deg apart) of the lines >= 3 pt through the plant centre (+-0.6 pt)"""
    ds=sorted(math.degrees(math.atan2(P[i][4][1][1]-P[i][4][0][1],P[i][4][1][0]-P[i][4][0][0]))%180 for i in ids
              if P[i][0]=='l' and math.dist(*P[i][4])>=3 and LineString(P[i][4]).distance(Point(c[0],c[1]))<0.6)
    n=0; last=-99
    for d in ds:
        if d-last>=15: n+=1; last=d
    return n
# (cfg.PLANT_STRICT=True, floor 1) black plants among shelves, stairs and slatted walls: a plant whose lines are >= 30 %
#   axis-parallel needs 3+ spoke directions. Off by default: on floor 3 a real plant by a partition has 0.45 and 1 spoke.
_PST=getattr(cfg,'PLANT_STRICT',False)
for k,ids in owner.items():
    if not _PLC and _POTC.get(k,1.0)<0.5 and _axis_share(ids)>=0.5:
        if os.environ.get('DBG_POT'): print('axis-parallel plant dropped',[round(v,1) for v in cand[k][:2]],round(_POTC[k],2))
        continue
    if _PST and _axis_share(ids)>=0.3 and _spokes(cand[k],ids)<=2:
        if os.environ.get('DBG_POT'): print('strict: axis-parallel plant without spokes dropped',[round(v,1) for v in cand[k][:2]])
        continue
    if _PST:
        # leaves are many short pieces in all directions: 12+ pieces of 0.3-2.5 pt in 3+ direction bins of 30 deg
        #   (a dot grid, a slatted screen, the grooves of an entrance mat are not); long axis-parallel lines that do not
        #   pass through the centre are the neighbour's (the mat, a partition), not the plant's
        _b=collections.Counter(int((math.degrees(math.atan2(P[i][4][1][1]-P[i][4][0][1],P[i][4][1][0]-P[i][4][0][0]))%180)//30)
                               for i in ids if P[i][0]=='l' and 0.3<=math.dist(*P[i][4])<=2.5)
        if sum(_b.values())<12 or sum(1 for v in _b.values() if v>=2)<3:
            if os.environ.get('DBG_POT'): print('strict: no leaves, dropped',[round(v,1) for v in cand[k][:2]])
            continue
        def _longax(i):
            if P[i][0]!='l' or math.dist(*P[i][4])<3: return False
            (x1,y1),(x2,y2)=P[i][4]; ang=math.degrees(math.atan2(y2-y1,x2-x1))%90
            return min(ang,90-ang)<=3 and LineString(P[i][4]).distance(Point(cand[k][0],cand[k][1]))>=0.6
        ids={i for i in ids if not _longax(i)}
    if _PLC:
        cx_,cy_,r_=cand[k]
        ids={i for i in ids if not _neutral(_pcol(i)) or all(math.dist((cx_,cy_),v)<=r_+0.3 for v in pts(P[i]))}
        if sum(1 for i in ids if _pcol(i) is not None and max(abs(_pcol(i)[j]-_PLC[j]) for j in range(3))<=0.06)<5: continue
    s_=take(ids)
    if len(s_)>15: add('plant','Растение в кашпо','A-89----E-',s_,c=cand[k][:2])
    else: free.update(s_)
# (cfg.PLANT_COLOR) leaves of the plant colour without a detected pot (a pot wider than the 6 pt Hough range: courtyard
#   trees on floor 2): each cluster of 8+ coloured prims is a plant; its pot = rings (_ring_pot) among the short
#   neutral pieces / curves within the cluster radius + 6 pt of its centre
def _ring_pot(c_,r_,cands,leaves):
    """the pot of a leaf-colour plant is a ring the leaves grow around: circles through pieces of the candidates
    (RANSAC, fixed seed), R 2.5 pt .. min(14 pt, cluster radius + 5 pt), inliers = pieces lying within 0.4 pt of the circle
    (lines: >= 0.6 pt and across the radius),
    4+ of them covering >= 180 deg and filling >= 60 % of that arc, and leaves in at least 3 of the 4 quadrants around the
    circle within R + 6 pt.
    Several rings per cluster (neighbouring courtyard trees merge into one leaf cluster, floor 2). Without it the sweep
    'short neutral pieces within the cluster radius + 3 pt' took a convector and facade mullions (floor 5), a partition
    node, a cabinet and a round stool (floor 6)."""
    import random
    if len(cands)<4: return []
    rnd=random.Random(12345)
    ids=list(cands); n=len(ids)
    A=np.zeros((n,12,2))
    for k,i in enumerate(ids):
        v=np.array(pts(P[i]),float); A[k,:len(v)]=v[:12]; A[k,len(v):]=v[-1]
    MID=A.mean(axis=1)
    # lines: unit direction and length (curves: length 0 = no tangency test); micro-strokes (< 0.6 pt) never form a pot
    ISL=np.array([P[i][0]=='l' for i in ids]); DV=A[:,1]-A[:,0]; LN=np.hypot(DV[:,0],DV[:,1])
    DU=DV/np.maximum(LN,1e-9)[:,None]
    OKP=~ISL|(LN>=0.6)
    LV=np.array([v for i in leaves for v in pts(P[i])]) if leaves else np.zeros((0,2))
    alive=np.ones(n,bool); out=[]
    for _ring in range(8):
        idx=np.nonzero(alive)[0]
        if len(idx)<4: break
        best=None
        for _ in range(300):
            a_,b_,c3=rnd.sample(list(idx),3)
            (x1,y1),(x2,y2),(x3,y3)=MID[a_],MID[b_],MID[c3]
            d=2*(x1*(y2-y3)+x2*(y3-y1)+x3*(y1-y2))
            if abs(d)<1e-6: continue
            ux=((x1*x1+y1*y1)*(y2-y3)+(x2*x2+y2*y2)*(y3-y1)+(x3*x3+y3*y3)*(y1-y2))/d
            uy=((x1*x1+y1*y1)*(x3-x2)+(x2*x2+y2*y2)*(x1-x3)+(x3*x3+y3*y3)*(x2-x1))/d
            R=math.hypot(x1-ux,y1-uy)
            if not (2.5<=R<=min(14,r_+5)): continue          # a tree's pot ring is wider than its canopy (floor 2)
            dev=np.abs(np.hypot(A[idx,:,0]-ux,A[idx,:,1]-uy)-R).max(axis=1)
            rx=MID[idx,0]-ux; ry=MID[idx,1]-uy; rn=np.maximum(np.hypot(rx,ry),1e-9)
            tang=np.abs(DU[idx,0]*rx/rn+DU[idx,1]*ry/rn)<=0.3          # a chord runs across the radius
            inl=idx[(dev<=0.4)&OKP[idx]&(~ISL[idx]|tang)]
            if len(inl)>=4 and (best is None or len(inl)>len(best[3])): best=(ux,uy,R,inl)
        if best is None: break
        ux,uy,R,inl=best
        alive[inl]=False
        an=np.sort((np.degrees(np.arctan2(A[inl,:,1]-uy,A[inl,:,0]-ux))%360).ravel())
        gaps=np.append(np.diff(an),an[0]+360-an[-1])
        quad=set()
        if len(LV):
            sel=LV[np.hypot(LV[:,0]-ux,LV[:,1]-uy)<=R+6]
            quad={(bool(x_>=ux),bool(y_>=uy)) for x_,y_ in sel}
        # a drawn ring is dense: its pieces fill >= 60 % of the covered arc (accidental circles through a convector's
        #   loop strokes or mullion bits are sparse)
        _cov=math.radians(360-gaps.max())*R; _len=float(np.hypot(np.diff(A[inl,:,0],axis=1),np.diff(A[inl,:,1],axis=1)).sum())
        ok=360-gaps.max()>=180 and len(quad)>=3 and _len>=0.6*_cov
        if os.environ.get('DBG_LEAF'): print('   ring',[round(ux,1),round(uy,1)],round(R,1),len(inl),'cover',round(360-gaps.max()),'dens',round(_len/max(_cov,1e-6),2),'quadrants',len(quad),'ok' if ok else 'no')
        if ok: out.extend(ids[k] for k in inl)
    return out
if _PLC:
    _gl=[i for i in free if _pcol(i) is not None and max(abs(_pcol(i)[j]-_PLC[j]) for j in range(3))<=0.06]
    if _gl:
        _m=np.zeros((H,W),np.uint8)
        for i in _gl: cv2.polylines(_m,[np.array([T(v) for v in pts(P[i])],np.int32)],False,255,1)
        _n,_lab=cv2.connectedComponents(cv2.dilate(_m,np.ones((5,5),np.uint8)))
        _cl=collections.defaultdict(list)
        for i in _gl:
            q_=T(pts(P[i])[0]); _cl[int(_lab[min(max(q_[1],0),H-1),min(max(q_[0],0),W-1)])].append(i)
        _np=0
        for k_,ids_ in _cl.items():
            if k_==0 or len(ids_)<8: continue
            xs_=[v[0] for i in ids_ for v in pts(P[i])]; ys_=[v[1] for i in ids_ for v in pts(P[i])]
            c_=((min(xs_)+max(xs_))/2,(min(ys_)+max(ys_))/2); r_=max(max(xs_)-min(xs_),max(ys_)-min(ys_))/2
            pot=[i for i in free if _neutral(_pcol(i)) and (P[i][0]=='c' or (P[i][0]=='l' and math.dist(*P[i][4])<=4)) and PB[i][0]>=c_[0]-r_-6 and PB[i][2]<=c_[0]+r_+6 and PB[i][1]>=c_[1]-r_-6 and PB[i][3]<=c_[1]+r_+6 and all(math.dist(c_,v)<=r_+6 for v in pts(P[i]))]
            _p0=len(pot); pot=_ring_pot(c_,r_,pot,ids_)
            if os.environ.get('DBG_LEAF'): print('leaf plant',[round(v,1) for v in c_],round(r_,1),len(ids_),'pot',_p0,'->',len(pot))
            add('plant','Растение в кашпо','A-89----E-',take(ids_+pot),c=c_); _np+=1
        print('plants by leaf colour',_np)
# 8 facade band. Convectors = dark solid rectangles along the facade (stroke-fills restored by strokefill.py,
#   or native dark fills), parallel to the local facade direction, with the connection loop at one short end.
#   A convector owns its solid, the outline micro-strokes inside it and the loop; the rest of the band is glazing.
# (cfg.FACADE_BAND, pt; floors 3-5: 14) the band that is 'glazing': on floor 1 radiators, pilasters and furniture stand
#   within 14 pt of the thin glazing line, so the band there is only the glazing itself
fl=facade_multi() or LineString([(-1e6,-1e6),(-1e6+1,-1e6)]); band=facade_band(getattr(cfg,'FACADE_BAND',ptb(14))) if FACADES else fl.buffer(1); _FL=facade_lines()   # code 008: 14 pt at 63.5 mm/pt = 0.9 m of the building
from shapely.prepared import prep
from shapely.geometry import Polygon as SPoly
pband=prep(band)
dark=lambda c: c is not None and (max(c)<0.5 or (c[0]==c[1]==c[2] and c[0]<=0.8))   # black, or neutral grey (floor 4)
def solid_rect(i):
    g=SPoly(P[i][4])
    if not g.is_valid: g=g.buffer(0)
    r=g.minimum_rotated_rectangle; xy=list(r.exterior.coords)[:4]
    e1=math.dist(xy[0],xy[1]); e2=math.dist(xy[1],xy[2])
    if e1>=e2: u=((xy[1][0]-xy[0][0])/e1,(xy[1][1]-xy[0][1])/e1); L,Wd=e1,e2
    else: u=((xy[2][0]-xy[1][0])/e2,(xy[2][1]-xy[1][1])/e2); L,Wd=e2,e1
    return g,(r.centroid.x,r.centroid.y),u,L,Wd,g.area/r.area
def fac_dir(c,h=3.0):
    ln=min(_FL,key=lambda g:g.distance(Point(c)))
    t=ln.project(Point(c)); p1=ln.interpolate(max(0,t-h)); p2=ln.interpolate(min(ln.length,t+h))
    d=(p2.x-p1.x,p2.y-p1.y); n=math.hypot(*d); return (d[0]/n,d[1]/n)
_PBA=np.array(PB,float)
def _within(bnd):
    """(speed only) indices of prims whose bbox lies inside bnd: a necessary condition of every containment test below"""
    x0,y0,x1,y1=bnd
    return [int(j) for j in np.nonzero((_PBA[:,0]>=x0)&(_PBA[:,2]<=x1)&(_PBA[:,1]>=y0)&(_PBA[:,3]<=y1))[0]]
nconv=0; rejected=[]
for i in sorted(free):
    p=P[i]
    if p[0]!='qu' or not dark(p[3]) or len(p[4])<3 or i not in free: continue
    g,c,u,L,Wd,rf=solid_rect(i)
    Lmm,Wmm=L*MM_PER_PT,Wd*MM_PER_PT
    if Lmm<600 or fl.distance(Point(c))>ptb(14): continue
    fd=fac_dir(c)
    # 180-330 mm wide as on floor 3; a narrower one (100-180 mm, floor 4 grey convectors) only with its connection loop:
    # the false 1200x130 'convector' of floor 3 (mullions + tint) has no loop
    ok=1100<=Lmm<=2700 and 100<=Wmm<=330 and rf>=0.9 and abs(u[0]*fd[1]-u[1]*fd[0])<=0.26
    if not ok: rejected.append((round(c[0],1),round(c[1],1),round(Lmm),round(Wmm),round(rf,2))); continue
    zg_=g.buffer(0.25); zone=prep(zg_)
    mem={i}|{j for j in _within(zg_.bounds) if j in free and j!=i and zone.contains(sbox(*PB[j])) and ((P[j][0]=='qu' and dark(P[j][3])) or (P[j][0]!='qu' and max(PB[j][2]-PB[j][0],PB[j][3]-PB[j][1])<=1.2))}
    loop=None
    for k,sg in ((0,1),(1,-1)):
        ex,ey=c[0]+sg*u[0]*L/2,c[1]+sg*u[1]*L/2
        wc=(ex+sg*u[0]*1.0,ey+sg*u[1]*1.0)
        Wq=SPoly([(wc[0]+a_*u[0]*1.15-b_*u[1]*1.15,wc[1]+a_*u[1]*1.15+b_*u[0]*1.15) for a_,b_ in ((-1,-1),(1,-1),(1,1),(-1,1))]); pw=prep(Wq)
        ids=[j for j in _within(Wq.bounds) if j in free and j not in mem and P[j][0] in ('l','c') and pw.contains(sbox(*PB[j]))]
        if ids and (loop is None or len(ids)>len(loop[1])): loop=(k,ids)
    # a real loop is a dense knot of micro-strokes (floor 3: 23-35, floor 4: 54-69); 1-4 strokes are a mullion detail
    #   next to a glazing panel (floor 4 grey panels 1150x150 would pass the size test)
    #   a grey restored stroke-fill of the right size needs no loop: floor 4 has one whose connection is not drawn
    _gsf=isinstance(p[5],tuple) and p[5][0]=='sf' and not max(p[3])<0.5
    if Wmm<180 and (not loop or len(loop[1])<12) and not _gsf: rejected.append((round(c[0],1),round(c[1],1),round(Lmm),round(Wmm),round(rf,2),'no loop')); continue
    if loop: mem|=set(loop[1])
    s_=take(mem)
    if s_:
        nconv+=1
        dv=u if (loop is None or loop[0]==0) else (-u[0],-u[1])
        nv=(-dv[1],dv[0])
        rect=[(c[0]+a_*dv[0]*L/2+b_*nv[0]*Wd/2,c[1]+a_*dv[1]*L/2+b_*nv[1]*Wd/2) for a_,b_ in ((-1,-1),(1,-1),(1,1),(-1,1))]
        add('convector','Конвектор внутрипольный','A-56----E-',s_,rect=rect,cpt=c,u=dv,Lpt=L,Wpt=Wd,loop=sorted(loop[1]) if loop else [],solid=i)
print('convectors',nconv,'rejected solids near facade',len(rejected),'by size/shape:',[r for r in rejected if r[-1]!='no loop'][:25],'without loop:',sum(1 for r in rejected if r[-1]=='no loop'))
if detect8.on('band'):
    # (code 008, Т4-2) glazing - a primitive whose length lies >= 90 % in the band (a fill: its bbox as before, or >= 90 %
    #   of its area): a chord of an arc or of a slanted run is wider than the band by its bbox and stayed a partition;
    #   lines of the furniture pen (cfg.DESK_OUTLINE_COLOR and cfg.FURN_PENS - the outline colour of desks and chairs)
    #   are never glazing: the band took the outer sides of desks and of a counter at the facade (floor 4)
    _fp8=[tuple(getattr(cfg,'DESK_OUTLINE_COLOR',(0.67,0.67,0.67)))]+[tuple(c) for c in getattr(cfg,'FURN_PENS',[])]
    _bb8=band.bounds; _nb8=collections.Counter(); fac=[]
    for i in _within((_bb8[0]-50,_bb8[1]-50,_bb8[2]+50,_bb8[3]+50)):
        if i not in free: continue
        if detect8.furn_pen(P[i],_fp8): continue
        if pband.contains(sbox(*PB[i]).buffer(0.01)): fac.append(i); _nb8['bbox']+=1; continue
        if not pband.intersects(sbox(*PB[i])): continue
        if detect8.band_share(prim_geom(i),band)>=0.9: fac.append(i); _nb8['share']+=1
    print('detect8 band',dict(_nb8))
else: fac=[i for i in free if pband.contains(sbox(*PB[i]).buffer(0.01))]
# (cfg.FACADE_FILL_GEOM, 30.09.2026, floor 5) a fill along a CURVED glazing: its bbox leaves the band although the
#   fill itself lies in it (the grey glass of the SW and SE curves, 5.6 x 5.5 m and 4.1 x 1.9 m, stayed 'misc').
#   The fill's own polygon is tested instead. Default off: other floors do not change.
if getattr(cfg,'FACADE_FILL_GEOM',False):
    #   Only a neutral grey fill (glass tint, max channel <= 0.6): light room fills (step 11d) stay rooms.
    _fs=set(fac); fac+=[i for i in free if i not in _fs and P[i][0]=='qu' and len(P[i][4])>=3 and P[i][3] is not None and max(P[i][3])<=0.6
                       and max(P[i][3])-min(P[i][3])<=0.05 and pband.contains(prim_geom(i).buffer(-0.02))]
add('facade','Витраж фасадный (стойки, остекление)','A-31----E-',take(fac))
# 10 attach small leftovers to containing instance
def ibb(q):
    return (min(PB[i][0] for i in q['prims']),min(PB[i][1] for i in q['prims']),max(PB[i][2] for i in q['prims']),max(PB[i][3] for i in q['prims']))
for q in inst: q['bbx']=ibb(q) if q['prims'] else None
# (speed only) candidate hosts by a numpy containment prefilter at the largest tolerance, then the same exact test in inst order
_HQ=[k for k,q in enumerate(inst) if not (q['key'] in ('facade','atrium','doorhw')+CANON or not q['bbx'] or q.get('colour'))]   # door hardware spans the opening: it must not collect the wall lines there
# (28.09.2026) nor does a colour element (cfg.COLOR_ELEMENTS): it is its colour only - a room separation line at the
#   end of the floor 4 stair enclosure collected the black outline of the wall there, and the wall lost its end
_HB=np.array([inst[k]['bbx'] for k in _HQ],float).reshape(-1,4)
for i in list(free):
    b=PB[i]; best=None
    tol=2.6 if max(b[2]-b[0],b[3]-b[1])<2.6 else 1.2
    _h=np.nonzero((_HB[:,0]-2.61<=b[0])&(_HB[:,2]+2.61>=b[2])&(_HB[:,1]-2.61<=b[1])&(_HB[:,3]+2.61>=b[3]))[0]
    for q in (inst[_HQ[k]] for k in _h):
        if _PLC and q['key']=='plant' and _neutral(_pcol(i)): continue   # a plant takes no neutral leftovers (floor 5)
        x=q['bbx']
        if b[0]>=x[0]-tol and b[2]<=x[2]+tol and b[1]>=x[1]-tol and b[3]<=x[3]+tol:
            a=(x[2]-x[0])*(x[3]-x[1])
            if best is None or a<best[0]: best=(a,q)
    if best: best[1]['prims'].append(i); free.discard(i)
print('after attach free',len(free))
# 11 axis markers outside building (never next to wall hatch: the curved wall of ЛК-1 lies at x<186)
from shapely.strtree import STRtree as _STR
_HL=[LineString([h[0],h[1]]) for h in pickle.load(open('hatch.pkl','rb'))]
_ht=_STR(_HL)
def near_wall(b,d=3.0):
    bx=sbox(*b)
    return any(_HL[j].distance(bx)<=d for j in _ht.query(bx.buffer(d)))
OUTSIDE=getattr(cfg,'OUTSIDE_BOXES',[])   # outside the building: small free prims there are axis/grid markers
for i in list(free):
    b=PB[i]
    if not inboxes(b,OUTSIDE): continue
    if near_wall(b): continue
    free.discard(i); inst.append(dict(key='axmark',name='Маркер оси',layer='A-AX----E-',prims=[i]))
# 11b wall face lines: strokes hugging a final wall body (finish/outer face lines, within 0.6 pt and parallel
#     to its boundary) belong to that wall's layer, not to "unclassified"
if os.path.exists('walls.pkl') and WALLP:
    _W=pickle.load(open('walls.pkl','rb'))['Wpt']
    _WL={'ext':'A-21----E-','cap':'A-221---E-','gkl':'A-222---E-','blk':'A-223---E-'}
    from shapely.strtree import STRtree as _STR2
    _bd=[]; _bc=[]
    for k_,ps_ in _W.items():
        for g_ in ps_:
            for gg in ([g_] if g_.geom_type=='Polygon' else list(g_.geoms)):
                for ring in [gg.exterior]+list(gg.interiors):
                    c_=list(ring.coords)
                    for a_,b_ in zip(c_[:-1],c_[1:]):
                        if math.dist(a_,b_)>0.3: _bd.append(LineString([a_,b_])); _bc.append(k_)
    _bt=_STR2(_bd); wl=collections.defaultdict(list)
    for i in list(free):
        if P[i][0]!='l': continue
        a_,b_=P[i][4]; L_=math.dist(a_,b_)
        if L_<0.1: continue
        ln=LineString([a_,b_]); best=None
        for j in _bt.query(ln.buffer(0.6)):
            e=_bd[j]; (u0,u1)=list(e.coords)
            d1=((b_[0]-a_[0])/L_,(b_[1]-a_[1])/L_); Le=e.length; d2=((u1[0]-u0[0])/Le,(u1[1]-u0[1])/Le)
            if abs(d1[0]*d2[1]-d1[1]*d2[0])>0.05: continue
            if e.buffer(0.6,cap_style=2).contains(ln): best=_bc[j]; break
        if best: wl[best].append(i)
    if detect8.on('strips'):
        # (code 008, Т4-5) finish strips along a wall face: a free thin fill <= 60 mm wide (brown and beige strips of
        #   floor 4, 0.24-0.72 pt) whose centre line lies >= 80 % within 0.6 pt of the face of one wall body is a line of
        #   that wall - not a partition, a bench end, a wardrobe or 'misc'. The sign is the geometry against the wall
        #   body, not the colour. <один пример: клиент А, 4 этаж>
        _ns8=0
        for i in list(free):
            p_=P[i]
            if p_[0]!='qu' or p_[3] is None or p_[3]==(1.0,1.0,1.0) or len(p_[4])<3: continue
            if max(PB[i][2]-PB[i][0],PB[i][3]-PB[i][1])<detect8.pt(100): continue   # a strip may be a chain of short pieces (4.7 pt)
            g_=prim_geom(i)
            if g_.is_empty or g_.area<=0: continue
            ts_=detect8.thin_strip(g_)
            if ts_ is None: continue
            L_,W_,cl_=ts_
            if W_*MM_PER_PT>60 or L_<3*W_: continue
            near_=collections.defaultdict(list)
            for j in _bt.query(cl_.buffer(0.6+W_/2)): near_[_bc[j]].append(_bd[j])
            best=None
            for k_,es_ in near_.items():
                z_=_UU([e.buffer(0.6+W_/2,cap_style=2) for e in es_])
                if cl_.intersection(z_).length>=0.8*cl_.length: best=k_; break
            if best:
                wl[best].append(i); _ns8+=1
                # the strip's own outline (a thin pen round the fill, floor 4: each beige piece has a black 0.24 outline)
                _zo=g_.buffer(0.1)
                wl[best]+=[j for j in _within(_zo.bounds) if j in free and j!=i and P[j][0]=='l' and _zo.contains(_LS(P[j][4]))]
        print('detect8 finish strips',_ns8)
    for k_,ids in wl.items():
        add('wallline','Линии стен (контур/отделка по исходнику)',_WL[k_],take(ids))
    print('wall face lines',{k_:len(v) for k_,v in wl.items()})
# 11c desks drawn as outlines only (floor 4, Ecom zone: grey rectangles without a worktop fill). Opt-in:
#     cfg.DESK_OUTLINES=True (+ DESK_OUTLINE_COLOR, default grey 0.67). A cell of the free axis-parallel lines of that
#     colour is a desk if it is a rectangle 1000-2000 x 500-1000 mm; it owns the lines on its boundary.
if getattr(cfg,'DESK_OUTLINES',False) and not detect8.on('desks'):   # code 008: with DETECT8 the desks are found before step 8
    from shapely.ops import polygonize as _polyg
    col_=tuple(getattr(cfg,'DESK_OUTLINE_COLOR',(0.67,0.67,0.67)))
    cand_=[i for i in free if P[i][0]=='l' and P[i][2]==col_ and math.dist(*P[i][4])>=3 and (abs(P[i][4][0][0]-P[i][4][1][0])<0.02 or abs(P[i][4][0][1]-P[i][4][1][1])<0.02)]
    cells_=[]
    for f_ in _polyg(_UU([_LS(P[i][4]) for i in cand_])):
        r_=f_.minimum_rotated_rectangle; xy_=list(r_.exterior.coords)
        e_=sorted([math.dist(xy_[0],xy_[1]),math.dist(xy_[1],xy_[2])])
        if f_.area/r_.area>0.98 and 1000<=e_[1]*MM_PER_PT<=2000 and 500<=e_[0]*MM_PER_PT<=1000: cells_.append(f_)
    _nd=0
    for f_ in cells_:
        bd_=f_.exterior.buffer(0.05)
        ids_=[i for i in cand_ if i in free and bd_.contains(_LS(P[i][4]))]
        if ids_:
            b_=f_.bounds
            add('desk_o','Стол рабочий (контур без заливки)','A-82----E-',take(ids_),bb=b_); _nd+=1
    print('outline desks',_nd,'of',len(cells_),'cells')
# 11d room / zone fills (cfg.ZONE_FILLS=True, floor 5): the source fills every room with a light tint (0.98 grey,
#   light cyan corridor bands). A free light fill (min channel >= 0.85, not white) of >= 400 pt2 (1.6 m2) is the room's
#   fill, not an object: layer A-92, drawn under everything, and it no longer glues all the leftovers inside a room
#   into one 'misc' component. After step 10, so a zone never collects leftovers. Off by default (floor 3: none free).
if getattr(cfg,'ZONE_FILLS',False):
    _zn=0
    for i in list(free):
        p=P[i]
        if p[0]!='qu' or p[3] is None or p[3]==(1.0,1.0,1.0) or min(p[3])<0.85: continue
        g_=_PG(p[4]); g_=g_ if g_.is_valid else g_.buffer(0)
        if g_.area<400: continue
        add('zone','Заливка помещения / зоны (по исходнику)','A-92----E-',take([i])); _zn+=1
    print('zone fills',_zn)
# 12 light partitions: long free straight lines
lp=[i for i in free if P[i][0]=='l' and math.dist(*P[i][4])>=6]
if detect8.on('pen'):
    # (code 008, Т4-6) lines of the furniture pen (cfg.DESK_OUTLINE_COLOR, cfg.FURN_PENS: the grey outline of desks and
    #   chairs) are not partitions: what the desk detectors did not take stays a piece for the gate (S1, S12*), not a
    #   silent partition across the furniture
    _fp12=[tuple(getattr(cfg,'DESK_OUTLINE_COLOR',(0.67,0.67,0.67)))]+[tuple(c) for c in getattr(cfg,'FURN_PENS',[])]
    _n12=len(lp); lp=[i for i in lp if not detect8.furn_pen(P[i],_fp12)]
    print('detect8 pen: furniture-pen lines kept out of the light partitions',_n12-len(lp))
add('lpart','Перегородка без штриховки в исходнике (стеклянная/лёгкая)','A-22G---E-',take(lp))
# 12b (cfg.LPART_CHAINS=True, floor 5) a partition drawn as a chain of short thick pieces (>= 0.45 pt: a curved glass
#   wall, a straight run broken at every mullion): pieces joined end to end with a turn < 25 deg into a run of >= 6 pt
if getattr(cfg,'LPART_CHAINS',False):
    _cc=[i for i in free if P[i][0]=='l' and P[i][1] is not None and P[i][1]>=0.45 and math.dist(*P[i][4])>=0.3]
    _ek=lambda p:(round(p[0]/0.06),round(p[1]/0.06))
    _em=collections.defaultdict(list)
    for i in _cc:
        for e_ in P[i][4]: _em[_ek(e_)].append(i)
    def _dir(i,frm):
        a_,b_=P[i][4]
        v_=(b_[0]-a_[0],b_[1]-a_[1]) if _ek(a_)==_ek(frm) else (a_[0]-b_[0],a_[1]-b_[1])
        n_=math.hypot(*v_) or 1; return (v_[0]/n_,v_[1]/n_)
    _seen=set(); _runs=[]
    for i0 in _cc:
        if i0 in _seen: continue
        run=[i0]; _seen.add(i0)
        for end in P[i0][4]:
            cur=i0; p_=end
            while True:
                din=_dir(cur,p_); din=(-din[0],-din[1])
                best=None
                for j in _em[_ek(p_)]:
                    if j in _seen: continue
                    dj=_dir(j,p_); c_=din[0]*dj[0]+din[1]*dj[1]
                    if c_>math.cos(math.radians(25)) and (best is None or c_>best[0]): best=(c_,j)
                if best is None: break
                j=best[1]; _seen.add(j); run.append(j)
                a_,b_=P[j][4]; p_=b_ if _ek(a_)==_ek(p_) else a_; cur=j
        if sum(math.dist(*P[k][4]) for k in run)>=6: _runs.append(run)
    _lc=[k for r in _runs for k in r]
    if _lc: add('lpartc','Перегородка без штриховки (криволинейная или из коротких отрезков)','A-22G---E-',take(_lc))   # own key: never hatch (walls_vec5 NOHATCH)
    print('partition chains',len(_runs),len(_lc))
# 13 remainder -> components
# (cfg.LPART_BITS=True, floor 5) the glass partitions of meeting rooms are long lines (step 12) plus mullion nodes,
#   door frames and joints in short pieces; a leftover component lying >= 85 % within 1 pt of those lines is the
#   partition's own detail, not 'misc'
_LPB=None
if getattr(cfg,'LPART_BITS',False):
    _lpg=[_LS(P[i][4]) for q in inst if q['key'] in ('lpart','lpartc') for i in q['prims'] if P[i][0]=='l']
    if _lpg: _LPB=prep(_UU([g.buffer(1.0) for g in _lpg]))
m=np.zeros((H,W),np.uint8)
for i in free:
    q=np.array([T(v) for v in pts(P[i])],np.int32)
    if P[i][0]=='qu': cv2.fillPoly(m,[q],255)
    cv2.polylines(m,[q],False,255,1)
n,lab,st,_=cv2.connectedComponentsWithStats(cv2.dilate(m,np.ones((3,3),np.uint8)))
cg=collections.defaultdict(list)
for i in free:
    q=T(pts(P[i])[0]); cg[int(lab[min(max(q[1],0),H-1),min(max(q[0],0),W-1)])].append(i)
LOOSE=collections.defaultdict(list)
# sanitary rooms: cfg.SANZONES (bboxes) or, by default, groups of WC / sink instances: each grown by 10 pt,
# touching ones merged, zone = bbox of the group + 2 pt (a cubicle block becomes one zone)
if getattr(cfg,'SANZONES',None) is not None: WCZ=cfg.SANZONES
else:
    _g=_UU([sbox(*ibb(q)).buffer(10) for q in inst if q["key"] in ("wc","sink") and q["prims"]])
    WCZ=[]
    for g in (getattr(_g,'geoms',None) or ([_g] if not _g.is_empty else [])):
        b=g.buffer(-10).bounds if not g.buffer(-10).is_empty else g.bounds
        WCZ.append((b[0]-2,b[1]-2,b[2]+2,b[3]+2))
print('sanitary zones',[tuple(round(v) for v in z) for z in WCZ])
plants=[q for q in inst if q['key']=='plant']
# (cfg.SANZONE_SPLIT=True, floor 5) a component that runs out of a sanitary room is split at the zone border: its
#   part inside is sanitary accessories, the rest is judged on its own. Off by default (floor 3 keeps whole components)
if getattr(cfg,'SANZONE_SPLIT',False) and WCZ:
    _cg2={}; _n=0
    for k,ids in cg.items():
        ins=[i for i in ids if any(z[0]<=(PB[i][0]+PB[i][2])/2<=z[2] and z[1]<=(PB[i][1]+PB[i][3])/2<=z[3] for z in WCZ)]
        if ins and len(ins)<len(ids):
            _si=set(ins); _cg2[('in',k)]=ins; _cg2[('out',k)]=[i for i in ids if i not in _si]; _n+=1
        else: _cg2[k]=ids
    cg=_cg2; print('components split at sanitary zones',_n)
for k,ids in cg.items():
    ids=list(ids)
    b=(min(PB[i][0] for i in ids),min(PB[i][1] for i in ids),max(PB[i][2] for i in ids),max(PB[i][3] for i in ids))
    w,h=b[2]-b[0],b[3]-b[1]; c=((b[0]+b[2])/2,(b[1]+b[3])/2)
    tan=any(P[i][0]=='qu' and is_tan(P[i][3]) for i in ids)
    near=[(math.dist(c,q['c']),q) for q in plants]
    if _PLC and sum(1 for i in ids if not _neutral(_pcol(i)))<0.5*len(ids): near=[]   # neutral bits are not leaves
    if near and min(near,key=lambda t:t[0])[0]<13 and max(w,h)<16:
        min(near,key=lambda t:t[0])[1]['prims'].extend(take(ids)); continue
    _ba=max(1e-6,(b[2]-b[0])*(b[3]-b[1]))
    _insan=any(max(0,min(b[2],z[2])-max(b[0],z[0]))*max(0,min(b[3],z[3])-max(b[1],z[1]))>=0.5*_ba for z in WCZ)
    if len(ids)<5 and max(w,h)<3:                      # tiny bits: drawn as loose linework, not a block each
        LOOSE['A-74----E-' if _insan else 'A-00----E-']+=take(ids); continue
    if _insan:
        add('wcacc','Аксессуар санузла (сушилка, урна, поручень, смыв)','A-74----E-',take(ids)); continue
    if tan and 20<max(w,h)<30 and min(w,h)<9:
        add('benchend','Приставной элемент бенча (тумба)','A-82----E-',take(ids)); continue
    if 25<max(w,h)<35 and min(w,h)<3:
        add('fscreen','Экран-перегородка напольная','A-82----E-',take(ids)); continue
    if max(w,h)<7 and inboxes(b,OUTSIDE) and not near_wall(b):
        for i in take(ids): inst.append(dict(key='axmark',name='Маркер оси',layer='A-AX----E-',prims=[i]))
        continue
    # plant missed by the pot detector: radial lines meeting at one point inside a roundish cluster
    if 10<=w<=26 and 10<=h<=26 and len(ids)>=25:
        segs_=[P[i][4] for i in ids if P[i][0]=='l' and math.dist(*P[i][4])>3]
        cx_,cy_=(b[0]+b[2])/2,(b[1]+b[3])/2
        hub=collections.Counter()
        for a_,b_ in segs_:
            for e_ in (a_,b_):
                hub[(round(e_[0]),round(e_[1]))]+=1
        if hub and hub.most_common(1)[0][1]>=4 and not (_PLC and sum(1 for i in ids if _pcol(i) is not None and max(abs(_pcol(i)[j]-_PLC[j]) for j in range(3))<=0.06)<5) \
           and not (not _PLC and _axis_share(ids)>=(0.3 if _PST else 0.5)):          # a stair or a shelf, not a plant (floor 1)
            add('plant','Растение в кашпо','A-89----E-',take(ids),c=(cx_,cy_)); continue
    # (cfg.GLAZING_COLORS, floor 1) a glass partition drawn in thousands of micro-strokes: its glazing lines have their
    #   own colour; 5 % of such lines make the component a glass partition
    _GC=getattr(cfg,'GLAZING_COLORS',None)
    if _GC and len(ids)>=20 and sum(1 for i in ids if P[i][2] is not None and any(max(abs(P[i][2][j]-g[j]) for j in range(3))<=0.02 for g in _GC))>=0.05*len(ids):
        add('glass','Перегородка стеклянная (витраж, по исходнику)','A-22G---E-',take(ids)); continue
    # (cfg.RADIATORS=True, floor 1) a sectional radiator: a band (<= 6 pt wide, >= 8 pt long) of 200+ micro-strokes
    #   (< 0.6 pt: the fins), >= 95 % of the component
    if getattr(cfg,'RADIATORS',False) and len(ids)>=200 and min(w,h)<=6 and max(w,h)>=8 and \
       sum(1 for i in ids if P[i][0]=='l' and math.dist(*P[i][4])<0.6)>=0.95*len(ids):
        add('radiator','Радиатор отопления секционный (по исходнику)','A-56----E-',take(ids)); continue
    if _LPB is not None and sum(1 for i in ids if _LPB.contains(prim_geom(i)))>=0.85*len(ids):
        add('lpartc','Перегородка без штриховки — узлы, стойки, примыкания (по исходнику)','A-22G---E-',take(ids)); continue
    add('misc','Прочий элемент (не классифицирован)','A-00----E-',take(ids))
for lay_,ids_ in LOOSE.items():
    if ids_: add('loose','Мелкие элементы исходника (россыпью, не блоком)',lay_,ids_)
pickle.dump((inst,free),open('assign2.pkl','wb'))
pickle.dump((inst,free),open('assign2_pre.pkl','wb'))   # the input of reclass.py: the export stage can run again (29.09.2026)
print(collections.Counter(q['key'] for q in inst))
