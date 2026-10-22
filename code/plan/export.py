from common import *
import ezdxf, hashlib, json, re, collections, importlib, pymupdf as fitz
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import Polygon
from shapely.ops import unary_union
P=load()
inst,free=pickle.load(open('assign2.pkl','rb'))
# (code 007, 04.10.2026, строка 172) glass doors: the glass line a door's opening runs through is cut between the
#   jambs - the plan shows the passage; the door itself is drawn in the glass style (fix7.py, F14)
from own7 import glass_gaps as _glass_gaps, cut_line as _cut_line
CUT=_glass_gaps(inst)
HOLES=pickle.load(open('holes.pkl','rb'))
WALLS=pickle.load(open('walls.pkl','rb'))['W']
# explication / specification tables: rows "number / name / area m2" anywhere on the sheet
_pg=fitz.open(PDF)[0]; txt=_pg.get_text()
EXPL={}
for m in re.finditer(r'(?m)^(\d{1,3})\n([^\n]+)\n(\d+(?:[.,]\d+)?\s*м²)$',txt):
    EXPL.setdefault(m.group(1),(m.group(2).strip(),m.group(3).strip()))
from layers8 import table as _lay_table, DESC as _LDESC   # code 008: the layer table - layers8.py (Т4-13, Т4-14)
LAY=_lay_table()
doc=ezdxf.new('R2018',setup=True); doc.units=ezdxf.units.MM
doc.header['$INSUNITS']=4; doc.header['$MEASUREMENT']=1
for n,d,c,lw in LAY:
    l=doc.layers.add(n,color=c,lineweight=lw); l.description=d
if 'ANSI31' not in doc.linetypes: pass
msp=doc.modelspace()
def Hl(layer): return layer[:-2]+'H-'
# ---- room / zone fills (cfg.ZONE_FILLS): plain hatches under everything, as in the source
for q in inst:
    if q['key']!='zone': continue
    for i_ in q['prims']:
        k_,w_,sc_,fc_,g_,di_=P[i_]
        if k_ in ('l','c'):
            # (01.10.2026, test of floor 5, T16) a line that rule H carried into a room fill was not drawn at all: export
            #   drew only the fills and their outlines (floor 5, iteration 3: 8 pieces of the wardrobe hangers - 5 ink misses).
            #   Now it goes on the contour layer of the fills
            pl_=[tuple(round(c,1) for c in MM(v)) for v in (g_ if k_=='l' else bez(g_,8))]
            if len(pl_)>=2 and math.dist(pl_[0],pl_[-1])+sum(math.dist(a,b) for a,b in zip(pl_,pl_[1:]))>=0.5:
                if len(pl_)==2: msp.add_line(pl_[0],pl_[1],dxfattribs={'layer':'A-92----E-'})
                else: msp.add_lwpolyline(pl_,dxfattribs={'layer':'A-92----E-'})
            continue
        if k_!='qu': continue
        ring_=[tuple(round(c,1) for c in MM(v)) for v in g_]
        if fc_ is not None and fc_!=(1.0,1.0,1.0):
            h_=msp.add_hatch(dxfattribs={'layer':'A-92----H-'}); h_.set_solid_fill(); h_.rgb=tuple(int(c*255) for c in fc_)
            h_.paths.add_polyline_path(ring_,is_closed=True,flags=1)
            for hh in HOLES.get(di_,[]): h_.paths.add_polyline_path([tuple(round(c,1) for c in MM(v)) for v in hh],is_closed=True,flags=0)
        if sc_ is not None: msp.add_lwpolyline(ring_,close=True,dxfattribs={'layer':'A-92----E-'})
# ---- walls (wallsdxf.write_walls: outline, grey poche, material pattern)
from wallsdxf import write_walls
wall_stats=write_walls(msp,WALLS)
# ---- blocks for instances
def ent_list(ids,ox,oy):
    out=[]
    for i in ids:
        k,w,sc,fc,g,di=P[i]
        if k=='l':
            for seg_ in (_cut_line(g,CUT[i]) if i in CUT else [g]):
                a=MM(seg_[0]); b=MM(seg_[-1])
                if math.dist(a,b)<0.5: continue
                out.append(('L',(round(a[0]-ox,1),round(a[1]-oy,1)),(round(b[0]-ox,1),round(b[1]-oy,1))))
        elif k=='c':
            q=[MM(v) for v in bez(g,8)]; out.append(('P',tuple((round(x-ox,1),round(y-oy,1)) for x,y in q)))
        elif k=='qu':
            q=[MM(v) for v in g]
            if fc is not None and fc!=(1.0,1.0,1.0):
                hs_=tuple(tuple((round(MM(v)[0]-ox,1),round(MM(v)[1]-oy,1)) for v in h_) for h_ in HOLES.get(di,[]))
                out.append(('F',tuple((round(x-ox,1),round(y-oy,1)) for x,y in q),fc,hs_))
            if sc is not None: out.append(('Q',tuple((round(x-ox,1),round(y-oy,1)) for x,y in q)))
    return sorted(set(out),key=str)
def clean(s): return re.sub(r'[^0-9A-Za-zА-Яа-яЁё]+','_',s).strip('_')[:60]
bdefs={}; names=collections.Counter(); inserts=[]; stats=collections.Counter()
F=np.diag([1,-1])
def decomp(Dmm):
    det=round(np.linalg.det(Dmm))
    if det>0: return math.degrees(math.atan2(Dmm[1,0],Dmm[0,0])),1
    R=Dmm@np.diag([-1,1]); return math.degrees(math.atan2(R[1,0],R[0,0])),-1
GLASS_ACI,GLASS_RGB=4,(28,127,214)   # the glass style: the colour of A-22G (ACI 4) and of glass in the SVG (#1c7fd6)
def mkblock(bn,desc,E,hlayer,glass=False):
    blk=doc.blocks.new(name=bn); blk.block.dxf.description=desc
    da_={'layer':'0','color':GLASS_ACI} if glass else {'layer':'0'}
    def _st(e_):
        if glass: e_.rgb=GLASS_RGB
        return e_
    for e in E:
        if e[0]=='L': _st(blk.add_line(e[1],e[2],dxfattribs=dict(da_)))
        elif e[0]=='P': _st(blk.add_lwpolyline(e[1],dxfattribs=dict(da_)))
        elif e[0]=='Q': _st(blk.add_lwpolyline(e[1],close=True,dxfattribs=dict(da_)))
        elif e[0]=='F':
            h=blk.add_hatch(dxfattribs={'layer':hlayer}); h.set_solid_fill()
            h.rgb=tuple(int(c*255) for c in e[2]); h.paths.add_polyline_path(e[1],is_closed=True,flags=1)
            for hh in (e[3] if len(e)>3 else ()): h.paths.add_polyline_path(hh,is_closed=True,flags=0)
    return blk
BLOCKGEOM={}
def place(q,bn,ins,rot=0,xs=1,ys=1):
    e_=msp.add_blockref(bn,ins,dxfattribs={'layer':q['layer'],'rotation':rot,'xscale':xs,'yscale':ys})
    q['block']=bn; q['ins']=ins; q['rot']=rot; q['xs']=xs; q['ys']=ys; q['ins_handle']=e_.dxf.handle
    inserts.append((q['layer'],bn,q['name'])); stats[q['name']]+=1
# ---- doors: frame from the source leaf line (hinge = its end at the arc centre), snapped to 90 deg multiples
def _unit(v): n=math.hypot(*v); return (v[0]/n,v[1]/n)
DOORFRAME={}; DOORBLOCK={}; DOORNAME={}
_dg=collections.defaultdict(list)
for q in inst:
    if q['key']!='door': continue
    dd=q['door']; c=dd['c']; lf=dd['open']; cl=dd['closed']; best=None
    for i in q['prims']:
        if P[i][0]!='l': continue
        a,b=P[i][4]
        for u_,v_ in ((a,b),(b,a)):
            if math.dist(u_,c)<0.8 and math.dist(v_,lf)<1.3 and (best is None or math.dist(u_,v_)>best[0]): best=(math.dist(u_,v_),u_,v_)
    Hp,Lp=(best[1],best[2]) if best else (c,lf)
    H_=MM(Hp); Lm=MM(Lp); Cm_=MM(cl)
    u=_unit((Lm[0]-H_[0],Lm[1]-H_[1])); Rl=math.dist(H_,Lm); v=_unit((Cm_[0]-H_[0],Cm_[1]-H_[1]))
    sg=1 if (v[0]*u[1]-v[1]*u[0])>0 else -1
    th_u=math.degrees(math.atan2(u[1],u[0])); k90=round(th_u/90)*90
    if abs(th_u-k90)<=4: th_u=k90
    th_v=th_u-90*sg
    vv=(math.cos(math.radians(th_v)),math.sin(math.radians(th_v))); vp=(-vv[1],vv[0])
    def loc(p,H_=H_,vv=vv,vp=vp,sg=sg):
        m=MM(p); d=(m[0]-H_[0],m[1]-H_[1]); return (round(d[0]*vv[0]+d[1]*vv[1],1),round(sg*(d[0]*vp[0]+d[1]*vp[1]),1))
    E=[]
    for i in q.get('core',q['prims']):
        k=P[i][0]
        if k=='l': E.append(('L',loc(P[i][4][0]),loc(P[i][4][1])))
        elif k=='c': E.append(('P',tuple(loc(x) for x in bez(P[i][4],8))))
    DOORFRAME[id(q)]=dict(H=H_,R=Rl,s=sg,th_v=th_v,C=(H_[0]+Rl*vv[0],H_[1]+Rl*vv[1]),L=(H_[0]+Rl*math.cos(math.radians(th_u)),H_[1]+Rl*math.sin(math.radians(th_u))),E=E)
    _dg[(bool(q.get('glass')),sum(e[0]=='L' for e in E),sum(e[0]=='P' for e in E))].append(q)
def _geom_match(E1,E2,tol=20):
    """same door type: Hausdorff distance of the drawn curves (densified) <= tol mm"""
    from shapely.geometry import MultiLineString as _MLS
    def g(E): return _MLS([list(e[1:]) if e[0]=='L' else list(e[1]) for e in E])
    import shapely as _sh
    return _sh.hausdorff_distance(g(E1),g(E2),densify=0.05)<=tol
DOORTYPES=[]   # (block name, E, glass)
for typ,qs in _dg.items():
    for q in sorted(qs,key=lambda q:DOORFRAME[id(q)]['R']):
        fr=DOORFRAME[id(q)]; E=sorted(set(fr['E']),key=str)
        gl_=typ[0]
        hit=next((bn for bn,E0,g0 in DOORTYPES if g0==gl_ and _geom_match(E,E0)),None)
        if hit is None:
            Rn=round(fr['R']/10)*10; kind_='стеклянная_однопольная' if gl_ else 'однопольная'; bn=f"Дверь_{kind_}_{Rn}"; k_=2
            while bn in BLOCKGEOM: bn=f"Дверь_{kind_}_{Rn}_{k_}"; k_+=1
            desc_=(f'Дверь стеклянная однопольная, полотно {Rn} мм (геометрия по исходнику; в стеклянной перегородке — проём с разрывом линии стекла, решение владельца 04.10.2026)'
                   if gl_ else f'Дверь однопольная, полотно {Rn} мм (геометрия по исходнику)')
            mkblock(bn,desc_,E,'A-32----H-',glass=gl_); BLOCKGEOM[bn]=E
            DOORTYPES.append((bn,E,gl_)); DOORNAME[bn]=f'Дверь {"стеклянная " if gl_ else ""}однопольная {round(Rn/50)*50}'; hit=bn
        DOORBLOCK[id(q)]=hit
print('door types',len(DOORTYPES),collections.Counter(DOORBLOCK.values()))
# ---- convectors: length clusters (gap > 25 mm), common width, loop geometry from the first instance that has one
# kinds: 'dark' = black solid with outline micro-strokes (floor 3) -> outline + dark fill, as before;
#        'grey' = grey stroke-fill without outline (floor 4, Ecom zone) -> fill of the source colour only.
# Width, length clusters and the loop are taken per kind (a floor may have both).
CONV_L={}; CONV_LOOP={}; CONV_W={}; CONV_KIND={}; CONV_COL={}
_cq=[q for q in inst if q['key']=='convector' and q.get('rect')]
for q in _cq:
    c_=P[q['solid']][3] if q.get('solid') is not None else (0,0,0)
    CONV_KIND[id(q)]='dark' if max(c_)<0.5 else 'grey'
for kind in ('dark','grey'):
    kq=[q for q in _cq if CONV_KIND[id(q)]==kind]
    if not kq: continue
    _ls=sorted(kq,key=lambda q:q['Lpt'])
    _cl=[]
    for q in _ls:
        if _cl and q['Lpt']*MM_PER_PT-_cl[-1][-1]['Lpt']*MM_PER_PT<=25: _cl[-1].append(q)
        else: _cl.append([q])
    for g in _cl:
        Lc=round(sum(q['Lpt'] for q in g)/len(g)*MM_PER_PT/10)*10
        for q in g: CONV_L[id(q)]=Lc
    # widths cluster with a spread of at most 15 mm (floor 5: 175-209 mm and 254 mm convectors; a chain of small gaps
    #   must not merge 175 and 209 into one 200 mm block - the strict ink diff sees the 12 mm per side)
    _ws=sorted(kq,key=lambda q:q['Wpt']); _wc=[]
    for q in _ws:
        if _wc and (q['Wpt']-_wc[-1][0]['Wpt'])*MM_PER_PT<=15: _wc[-1].append(q)
        else: _wc.append([q])
    for g in _wc:
        Wc_=round(sum(q['Wpt'] for q in g)/len(g)*MM_PER_PT/10)*10
        for q in g: CONV_W[id(q)]=Wc_
    CONV_COL[kind]=collections.Counter(P[q['solid']][3] for q in kq).most_common(1)[0][0] if kind=='grey' else (0.2,0.2,0.2)
    CONV_LOOP[kind]=[]
    for q in kq:
        if not q['loop']: continue
        Cm=MM(q['cpt']); t_=MM((q['cpt'][0]+q['u'][0],q['cpt'][1]+q['u'][1]))
        D=_unit((t_[0]-Cm[0],t_[1]-Cm[1])); N=(-D[1],D[0]); Lh=q['Lpt']*MM_PER_PT/2
        def lc(p):
            m=MM(p); d=(m[0]-Cm[0],m[1]-Cm[1]); return (d[0]*D[0]+d[1]*D[1]-Lh,d[0]*N[0]+d[1]*N[1])
        for i in q['loop']:
            if P[i][0]=='l': CONV_LOOP[kind].append(('L',lc(P[i][4][0]),lc(P[i][4][1])))
            elif P[i][0]=='c': CONV_LOOP[kind].append(('P',)+tuple(lc(x) for x in bez(P[i][4],8)))
        break
    print('convector',kind,'lengths',collections.Counter(CONV_L[id(q)] for q in kq),'widths',collections.Counter(CONV_W[id(q)] for q in kq),'loop entities',len(CONV_LOOP[kind]))
def desk_measure(ids):
    tans=[i for i in ids if P[i][0]=='qu' and is_tan(P[i][3])]
    tb=[(min(v[0] for v in P[i][4]),min(v[1] for v in P[i][4]),max(v[0] for v in P[i][4]),max(v[1] for v in P[i][4])) for i in tans]
    tb=max(tb,key=lambda b:(b[2]-b[0])*(b[3]-b[1]))
    # each side = the outermost stroke parallel to it, covering >= 80 % of it, within 0.35 pt outside the fill edge
    side=[tb[0],tb[1],tb[2],tb[3]]
    for i in ids:
        if P[i][0]!='l': continue
        (ax,ay),(bx,by)=P[i][4]
        if abs(ax-bx)<0.02 and abs(ay-by)>=0.8*(tb[3]-tb[1]):
            if tb[0]-0.35<=ax<=tb[0]+0.05: side[0]=min(side[0],ax)
            if tb[2]-0.05<=ax<=tb[2]+0.35: side[2]=max(side[2],ax)
        if abs(ay-by)<0.02 and abs(ax-bx)>=0.8*(tb[2]-tb[0]):
            if tb[1]-0.35<=ay<=tb[1]+0.05: side[1]=min(side[1],ay)
            if tb[3]-0.05<=ay<=tb[3]+0.35: side[3]=max(side[3],ay)
    xs_p=[side[0],side[2]]; ys_p=[side[1],side[3]]
    (x0,y0),(x1,y1)=MM((min(xs_p),max(ys_p))),MM((max(xs_p),min(ys_p)))
    w=abs(x1-x0); h=abs(y1-y0)
    return x0,y0,x1,y1,w,h
def cluster_values(vals,gap=15):
    """values within `gap` mm of each other are one print-quantised size: map each to the cluster mode (10 mm)"""
    vs=sorted(set(vals)); out={}; cur=[]
    def fl(cur):
        c=collections.Counter(v for v in vals if v in cur); m=max(c.items(),key=lambda t:(t[1],-abs(t[0]-sorted(cur)[len(cur)//2])))[0]
        for v in cur: out[v]=m
    for v in vs:
        if cur and v-cur[-1]>gap: fl(cur); cur=[]
        cur.append(v)
    if cur: fl(cur)
    return out
def desk_measure_turned(q):
    """(cfg.ROT_DESKS) a turned desk: centre, length, depth (mm) of its own turned box"""
    r=q['rrect']; c=MM(r['c']); return c,r['L']*MM_PER_PT,r['S']*MM_PER_PT
_dfc=collections.Counter(P[i][3] for q in inst if q['key']=='desk' and 'rrect' not in q for i in q['prims'] if P[i][0]=='qu' and is_tan(P[i][3]))
DESKFILL=_dfc.most_common(1)[0][0] if _dfc else (0.84,0.78,0.64)   # the source's own desk colour
DESKM={}; _dl=[]; _ds=[]
for q in inst:
    if q['key']!='desk' or not q['prims']: continue
    if 'rrect' in q:
        c_,Lm_,Sm_=desk_measure_turned(q); DESKM[id(q)]=(c_[0],c_[1],c_[0],c_[1],Lm_,Sm_); w,h=Lm_,Sm_
    else:
        m=desk_measure(q['prims']); DESKM[id(q)]=m; w,h=m[4],m[5]
    _dl.append(round(max(w,h)/10)*10); _ds.append(round(min(w,h)/10)*10)
_cL=cluster_values(_dl); _cS=cluster_values(_ds)
DESKDIM={}
for q in inst:
    if id(q) in DESKM:
        w,h=DESKM[id(q)][4],DESKM[id(q)][5]
        DESKDIM[id(q)]=(_cL[round(max(w,h)/10)*10],_cS[round(min(w,h)/10)*10])
tplblocks={}
for q in inst:
    # (code 007, 03.10.2026, owner's decision) openings A-23: the outline of a stair cage or of the atrium, no fill -
    #   a closed polyline from fix7.py (F10), not a block
    if q['key']=='opening' and q.get('poly'):
        pl_=[tuple(round(c,1) for c in MM(v)) for v in q['poly']]
        msp.add_lwpolyline(pl_[:-1] if pl_[0]==pl_[-1] else pl_,close=True,dxfattribs={'layer':q['layer']})
        xs_=[p[0] for p in pl_]; ys_=[p[1] for p in pl_]; q['bbmm']=(min(xs_),min(ys_),max(xs_),max(ys_)); stats[q['name']]+=1
        continue
    ids=q['prims']
    # (code 007) a boundary line shared by several objects (п. 240) is drawn in the block of each of them
    shared_=[i for i in q.get('shared',[]) if i not in set(ids)]
    if not ids and shared_: ids=shared_; shared_=[]
    if not ids: continue
    ps=[MM(p) for i in ids for p in pts(P[i])]
    xs_=[p[0] for p in ps]; ys_=[p[1] for p in ps]
    q['bbmm']=(min(xs_),min(ys_),max(xs_),max(ys_))
    if q['key']=='zone': continue                    # drawn above, under the walls
    if q['key']=='loose':
        for e_ in ent_list(ids,0,0):
            if e_[0]=='L': msp.add_line(e_[1],e_[2],dxfattribs={'layer':q['layer']})
            elif e_[0]=='P': msp.add_lwpolyline(e_[1],dxfattribs={'layer':q['layer']})
            elif e_[0]=='Q': msp.add_lwpolyline(e_[1],close=True,dxfattribs={'layer':q['layer']})
            elif e_[0]=='F':
                h_=msp.add_hatch(dxfattribs={'layer':Hl(q['layer'])}); h_.set_solid_fill(); h_.rgb=tuple(int(c*255) for c in e_[2]); h_.paths.add_polyline_path(e_[1],is_closed=True,flags=1)
                for hh in (e_[3] if len(e_)>3 else ()): h_.paths.add_polyline_path(hh,is_closed=True,flags=0)
        continue
    if q['key']=='axmark':
        for e in ent_list(ids,0,0):
            if e[0]=='L': msp.add_line(e[1],e[2],dxfattribs={'layer':'A-AX----E-'})
        continue
    if 'tpl' in q:   # canonical family block from exemplar (one block per exemplar: a floor may have two chair families)
        tk=(q['key'],tuple(q['tpl']))
        tb=q['tplbb']; ct=((tb[0]+tb[2])/2,(tb[1]+tb[3])/2)
        if tk not in tplblocks:
            cm=MM(ct); E=ent_list(list(q['tpl'])+list(q.get('tplF',[])),cm[0],cm[1])
            bn=clean(q['name']); k_=2
            while bn in doc.blocks: bn=clean(q['name'])+f'_{k_}'; k_+=1
            mkblock(bn,q['name'],E,Hl(q['layer'])); tplblocks[tk]=bn; BLOCKGEOM[bn]=E
        D=np.array([[q['D'][0],q['D'][1]],[q['D'][2],q['D'][3]]],float)
        an=q['anchor']; rel=(ct[0]-an[0],ct[1]-an[1]); d=D@np.array(rel)
        cpt=(q['t'][0]+d[0],q['t'][1]+d[1])
        rot,mir=decomp(F@D@F)
        place(q,tplblocks[tk],MM(cpt),rot,mir,1); continue
    if q['key']=='desk':
        x0,y0,x1,y1,w,h=DESKM[id(q)]; L_,S_=DESKDIM[id(q)]
        n_=max(1,round(L_/1400))
        # worktop colour = this desk's own fill (floor 4 has four tans and a light green); the floor's main colour keeps
        #   the plain block name
        _dc=collections.Counter(P[i][3] for i in q['prims'] if P[i][0]=='qu' and is_tan(P[i][3]))
        dcol=q['rrect']['fill'] if 'rrect' in q else (_dc.most_common(1)[0][0] if _dc else DESKFILL)
        bn=f"Стол_бенч_{L_}x{S_}"+('' if dcol==DESKFILL else '_'+''.join(f'{int(round(v*255)):02X}' for v in dcol))
        if bn not in BLOCKGEOM:
            r_=((-L_/2,-S_/2),(L_/2,-S_/2),(L_/2,S_/2),(-L_/2,S_/2))
            E=[('Q',r_),('F',r_,dcol)]   # outline + the source's own worktop fill; the source has no place divisions
            mkblock(bn,f'Стол рабочий (бенч) {L_}×{S_}, {n_} раб. места',E,'A-82----H-'); BLOCKGEOM[bn]=E
        q['name']=f'Стол рабочий (бенч) {L_}×{S_}'
        if 'rrect' in q:   # the same desk block, inserted turned (PDF y down -> DXF y up: the angle changes sign)
            place(q,bn,(x0,y0),(-q['rrect']['a'])%360); continue
        place(q,bn,((x0+x1)/2,(y0+y1)/2),0 if w>=h else 90); continue
    if q['key']=='convector' and q.get('rect'):
        Cm=MM(q['cpt']); t_=MM((q['cpt'][0]+q['u'][0],q['cpt'][1]+q['u'][1]))
        D=(t_[0]-Cm[0],t_[1]-Cm[1]); nD=math.hypot(*D); D=(D[0]/nD,D[1]/nD); N=(-D[1],D[0])
        kind=CONV_KIND[id(q)]; Lc=CONV_L[id(q)]; Wc=CONV_W[id(q)]
        bn=f'Конвектор_{Lc}x{Wc}'+('' if kind=='dark' else '_тонированный')+('' if q['loop'] else '_без_подводки')
        if bn not in BLOCKGEOM:
            r=((-Lc/2,-Wc/2),(Lc/2,-Wc/2),(Lc/2,Wc/2),(-Lc/2,Wc/2))
            E=[('Q',r),('F',r,(0.2,0.2,0.2))] if kind=='dark' else [('F',r,CONV_COL[kind])]
            if q['loop']:
                for e in CONV_LOOP[kind]:
                    pp_=[(round(x_+Lc/2,1),round(y_,1)) for x_,y_ in e[1:]]
                    E.append(('L',pp_[0],pp_[1]) if e[0]=='L' else ('P',tuple(pp_)))
            mkblock(bn,f'Конвектор внутрипольный {Lc}×{Wc}',E,'A-56----H-'); BLOCKGEOM[bn]=E
        q['name']=f'Конвектор внутрипольный {Lc}×{Wc}'
        place(q,bn,Cm,math.degrees(math.atan2(D[1],D[0]))); continue
    if q['key']=='door':
        fr=DOORFRAME[id(q)]; bn=DOORBLOCK[id(q)]
        q['name']=DOORNAME[bn]; q['hinge_mm']=fr['H']; q['closed_mm']=fr['C']; q['leaf_mm']=fr['L']; q['R_mm']=fr['R']
        place(q,bn,fr['H'],fr['th_v'],1,fr['s']); continue
    ox,oy=round((q['bbmm'][0]+q['bbmm'][2])/2),round((q['bbmm'][1]+q['bbmm'][3])/2)
    E=ent_list(list(ids)+shared_,ox,oy)
    hsh=hashlib.md5((q['name']+repr(E)).encode()).hexdigest()
    if hsh not in bdefs:
        base=clean(q['name']); names[base]+=1; bn=f"{base}_{names[base]:02d}"
        mkblock(bn,q['name'],E,Hl(q['layer'])); bdefs[hsh]=bn; BLOCKGEOM[bn]=E
    place(q,bdefs[hsh],(ox,oy))
# ---- no ink loss: prims of canonical instances not covered (0.4 pt) by the placed block are drawn as they are
from shapely.geometry import LineString as _LS, Polygon as _PG
from shapely.ops import unary_union as _UU
from shapely.prepared import prep as _prep
def _mm2pt(p): return ((p[0]-kx[1])/kx[0],(p[1]-ky[1])/ky[0])
def _block_pt(q,fills=False):
    """block geometry in pt. fills=False: the block's INK (lines and dark fills) - what covers a source line;
    fills=True: every block fill - what reproduces a source fill. A light fill is not ink: a line lying on it
    (floor 4: plant leaves over a desk top) is covered only by a block line, else it is drawn raw."""
    E=BLOCKGEOM[q['block']]; ins=q['ins']; c,s_=math.cos(math.radians(q['rot'])),math.sin(math.radians(q['rot']))
    def tf(p): x,y=p[0]*q['xs'],p[1]*q['ys']; return _mm2pt((ins[0]+c*x-s_*y,ins[1]+s_*x+c*y))
    out=[]
    for e in E:
        if fills:
            if e[0]=='F': out.append(_PG([tf(p) for p in e[1]]))
            continue
        if e[0]=='L': out.append(_LS([tf(e[1]),tf(e[2])]))
        elif e[0]=='P': out.append(_LS([tf(p) for p in e[1]]))
        elif e[0]=='Q': out.append(_LS([tf(p) for p in e[1]]+[tf(e[1][0])]))
        elif e[0]=='F' and max(e[2])<0.6: out.append(_PG([tf(p) for p in e[1]]))
    return _UU(out)
def _prim_geom(i):
    k=P[i][0]
    if k=='l': return _LS(P[i][4])
    if k=='c': return _LS(bez(P[i][4],8))
    g=_PG(P[i][4]); return g if g.is_valid else g.buffer(0)
# ---- no invented ink: a family instance partly hidden in the source (floor 4: a chair pushed under the desk, whose
#      fill covers its back) keeps its family name but is drawn from its own source geometry instead of the full block.
#      Test = the strict ink diff on the instance: block ink with no source ink within 0.4 pt (plan/rules/60 §2).
import cv2
_cls=pickle.load(open('cls.pkl','rb'))
_SZ=6.0; _X0,_Y0,_X1,_Y1=cfg.WIN; _SW,_SH=int((_X1-_X0)*_SZ)+1,int((_Y1-_Y0)*_SZ)+1
def _spx(p): return (int(round((p[0]-_X0)*_SZ)),int(round((p[1]-_Y0)*_SZ)))
_src=np.zeros((_SH,_SW),np.uint8)
for i,p in enumerate(P):
    if _cls[i] in ('sheet','dim','axis'): continue
    if p[0]=='qu':
        if p[2] is not None and len(p[4])>=2: cv2.polylines(_src,[np.array([_spx(v) for v in p[4]],np.int32)],True,255,1)
        if p[3] is None or max(p[3])>=0.6: continue
        cv2.fillPoly(_src,[np.array([_spx(v) for v in p[4]],np.int32)],255); continue
    cv2.polylines(_src,[np.array([_spx(v) for v in pts(p)],np.int32)],False,255,1)
_r=max(1,int(round(0.4*_SZ)))
_sup=cv2.dilate(_src,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*_r+1,2*_r+1)))
def _unsupported_px(q):
    E=BLOCKGEOM[q['block']]; ins=q['ins']; c,s_=math.cos(math.radians(q['rot'])),math.sin(math.radians(q['rot']))
    def tf(p): x,y=p[0]*q['xs'],p[1]*q['ys']; return _spx(_mm2pt((ins[0]+c*x-s_*y,ins[1]+s_*x+c*y)))
    G=[]
    for e in E:
        if e[0]=='L': G.append(('l',np.array([tf(e[1]),tf(e[2])],np.int32)))
        elif e[0]=='P': G.append(('l',np.array([tf(p) for p in e[1]],np.int32)))
        elif e[0]=='Q': G.append(('q',np.array([tf(p) for p in e[1]],np.int32)))
        elif e[0]=='F' and max(e[2])<0.6: G.append(('f',np.array([tf(p) for p in e[1]],np.int32)))
    if not G: return 0
    A_=np.concatenate([g for _,g in G]); x0_,y0_=A_.min(0)-2; x1_,y1_=A_.max(0)+3
    x0_,y0_=max(0,x0_),max(0,y0_); x1_,y1_=min(_SW,x1_),min(_SH,y1_)
    if x1_<=x0_ or y1_<=y0_: return 0
    m=np.zeros((y1_-y0_,x1_-x0_),np.uint8); o_=np.array([x0_,y0_],np.int32)
    for k_,g in G:
        if k_=='f': cv2.fillPoly(m,[g-o_],255)
        else: cv2.polylines(m,[g-o_],k_=='q',255,1)
    return int(((m>0)&(_sup[y0_:y1_,x0_:x1_]==0)).sum())
PARTIAL=[]
for q in inst:
    # family instances, and desks drawn by the floor's canonical desk block (floor 2: a cable stroke of the exemplar
    #   desk appeared on desks that do not have it)
    if not q.get('block') or not ('tpl' in q or q['key']=='desk'): continue
    n_=_unsupported_px(q)
    if n_<0.4*_SZ*_SZ: continue                          # below the strict ink-diff threshold (0.4 pt2, plan/rules/60 §2)
    msp.delete_entity(doc.entitydb[q['ins_handle']])
    inserts.remove((q['layer'],q['block'],q['name'])); stats[q['name']]-=1
    q['partial']=n_; PARTIAL.append((q['key'],n_))
    ox,oy=round((q['bbmm'][0]+q['bbmm'][2])/2),round((q['bbmm'][1]+q['bbmm'][3])/2)
    E=ent_list(q['prims'],ox,oy)
    hsh=hashlib.md5((q['name']+repr(E)).encode()).hexdigest()
    if hsh not in bdefs:
        base=clean(q['name']); names[base]+=1; bn=f"{base}_{names[base]:02d}"
        mkblock(bn,q['name'],E,Hl(q['layer'])); bdefs[hsh]=bn; BLOCKGEOM[bn]=E
    place(q,bdefs[hsh],(ox,oy))
print('family instances partly hidden in the source -> own geometry',collections.Counter(k for k,_ in PARTIAL))
del _src,_sup
CANON=('chair','wc','sink','stool','desk','convector','door')
ORPH=collections.Counter()
for q in inst:
    # (29.09.2026) any family block, not only the canonical ones: a piece attached to it by reclass.py that the block
    #   does not cover is drawn raw on its layer
    if not ((q['key'] in CANON or 'tpl' in q) and q.get('block')): continue
    zone=_prep(_block_pt(q).buffer(0.4)); fz_=_block_pt(q,True); fzone=_prep(fz_.buffer(0.4)) if not fz_.is_empty else None
    def _cov(i):
        p=P[i]
        if p[0]=='qu' and p[3] is not None and max(p[3])>=0.6:            # light fill: reproduced by a block fill
            return (fzone is not None and fzone.contains(_prim_geom(i))) or zone.contains(_prim_geom(i))
        return zone.contains(_prim_geom(i))
    orph=[i for i in q['prims'] if not (P[i][0]=='qu' and P[i][3]==(1.0,1.0,1.0)) and not _cov(i)]
    if not orph: continue
    q['orphans']=orph; ORPH[q['key']]+=len(orph)
    for e in ent_list(orph,0,0):
        if e[0]=='L': msp.add_line(e[1],e[2],dxfattribs={'layer':q['layer']})
        elif e[0] in ('P',): msp.add_lwpolyline(e[1],dxfattribs={'layer':q['layer']})
        elif e[0]=='Q': msp.add_lwpolyline(e[1],close=True,dxfattribs={'layer':q['layer']})
        elif e[0]=='F':
            h=msp.add_hatch(dxfattribs={'layer':Hl(q['layer'])}); h.set_solid_fill(); h.rgb=tuple(int(c*255) for c in e[2]); h.paths.add_polyline_path(e[1],is_closed=True,flags=1)
            for hh in (e[3] if len(e)>3 else ()): h.paths.add_polyline_path(hh,is_closed=True,flags=0)   # its holes (floor 2: the frame under a desk top)
print('orphan prims drawn raw',dict(ORPH))
# ---- double doors: leaves whose closed ends meet
dl=[q for q in inst if q['key']=='door' and 'closed_mm' in q]
for a in dl:
    for b in dl:
        if a is b: continue
        if math.dist(a['closed_mm'],b['closed_mm'])<200:
            a['pair']=True
            w=round((math.dist(a['hinge_mm'],a['closed_mm'])+math.dist(b['hinge_mm'],b['closed_mm']))/10)*10
            a['name']=f'Дверь {"стеклянная " if a.get("glass") else ""}двупольная {w} (створка)'
stats=collections.Counter(q['name'] for q in inst if q.get('block'))
# ---- room tags text
_WU=unary_union([g for v in WALLS.values() for g in v])
for q in inst:
    if q['key']!='tag': continue
    x,y=MM(q['c']); nm,ar=EXPL.get(q['text'],('',''))
    msp.add_text(q['text'],height=450,dxfattribs={'layer':'A-90----T-'}).set_placement((x,y),align=TextEntityAlignment.MIDDLE_CENTER)
    # name + area next to the tag: first free spot (no wall under the text) of below / above / right / left
    lab=f"{nm}  {ar}"; hw=len(lab)*0.55*250/2
    from shapely.geometry import box as _box
    spots=[((x,y-450),_box(x-hw,y-750,x+hw,y-450),TextEntityAlignment.TOP_CENTER),
           ((x,y+450),_box(x-hw,y+450,x+hw,y+750),TextEntityAlignment.BOTTOM_CENTER),
           ((x+500+hw,y),_box(x+500,y-150,x+500+2*hw,y+150),TextEntityAlignment.MIDDLE_CENTER),
           ((x-500-hw,y),_box(x-500-2*hw,y-150,x-500,y+150),TextEntityAlignment.MIDDLE_CENTER),
           ((x,y-1000),_box(x-hw,y-1300,x+hw,y-1000),TextEntityAlignment.TOP_CENTER),
           ((x,y+1000),_box(x-hw,y+1000,x+hw,y+1300),TextEntityAlignment.BOTTOM_CENTER)]
    pos,_,al=next((sp for sp in spots if not _WU.intersects(sp[1])),spots[0])
    msp.add_text(lab,height=250,dxfattribs={'layer':'A-90----T-'}).set_placement(pos,align=al)
# ---- source texts inside the drawing (room names, level marks, labels, local dimensions) at their place and size;
#      axis bubbles/chains are regenerated, room tag numbers are drawn with their circles above, tables are sheet
_M=_pg.rotation_matrix; _tags={q.get('text') for q in inst if q['key']=='tag'}
_tagpos=[q['c'] for q in inst if q['key']=='tag']
ntext=collections.Counter()
for blk in _pg.get_text('dict')['blocks']:
    for ln in blk.get('lines',[]):
        s_=''.join(sp['text'] for sp in ln['spans']).strip()
        if not s_: continue
        r=fitz.Rect(ln['bbox'])*_M; b=(r.x0,r.y0,r.x1,r.y1); c=((r.x0+r.x1)/2,(r.y0+r.y1)/2)
        if not inboxes(b,[cfg.SHEET_IN]) or inboxes(b,getattr(cfg,'SHEET_BOXES',[])) or inboxes(b,getattr(cfg,'AXIS_BOXES',[])): continue
        if s_ in AX_XN+AX_YN and inboxes(b,getattr(cfg,'OUTSIDE_BOXES',[])): continue          # axis bubble names
        if re.fullmatch(r'\d{1,3}',s_) and any(math.dist(c,t)<3 for t in _tagpos): continue   # room tag numbers
        if re.fullmatch(r'\d{3,5}',s_) and inboxes(b,getattr(cfg,'OUTSIDE_BOXES',[])): continue  # grid dimension chains
        size=max(sp['size'] for sp in ln['spans'])
        d=ln.get('dir',(1,0)); dv=fitz.Point(d)*_M-fitz.Point(0,0)*_M; ang=-math.degrees(math.atan2(dv.y,dv.x))
        lay='A-91----T-' if re.fullmatch(r'[+-]?\d+[.,]\d{3}',s_) else ('A-68----T-' if s_.startswith('ПК') else 'A-90----T-')   # code 008, Т4-14: «ПК…» on A-68----T-
        msp.add_text(s_,height=size*0.72*MM_PER_PT,rotation=ang,dxfattribs={'layer':lay}).set_placement(MM(c),align=TextEntityAlignment.MIDDLE_CENTER)
        ntext[lay]+=1
print('source texts',dict(ntext))
# ---- axes, bubbles, dims (only when the source has a grid)
xmm=[float(v) for v in AX_XMM]; ymm=[float(v) for v in AX_YMM]
if not (xmm and ymm): xmm=[]; ymm=[]
_wb=unary_union([g for v in WALLS.values() for g in v]).bounds
X0m,X1m=min(xmm+[_wb[0]])-3600,max(xmm+[_wb[2]])+2600; Y0m,Y1m=min(ymm+[_wb[1]])-2600,max(ymm+[_wb[3]])+1500
for x,nme in zip(xmm,AX_XN):
    msp.add_line((x,Y0m+800),(x,Y1m),dxfattribs={'layer':'A-AX----E-','linetype':'DASHDOT2'})
    msp.add_circle((x,Y0m+400),400,dxfattribs={'layer':'A-AX----T-'})
    msp.add_text(nme,height=350,dxfattribs={'layer':'A-AX----T-'}).set_placement((x,Y0m+400),align=TextEntityAlignment.MIDDLE_CENTER)
for y,nme in zip(ymm,AX_YN):
    msp.add_line((X0m+800,y),(X1m,y),dxfattribs={'layer':'A-AX----E-','linetype':'DASHDOT2'})
    msp.add_circle((X0m+400,y),400,dxfattribs={'layer':'A-AX----T-'})
    msp.add_text(nme,height=300,dxfattribs={'layer':'A-AX----T-'}).set_placement((X0m+400,y),align=TextEntityAlignment.MIDDLE_CENTER)
ds=doc.dimstyles.get('EZDXF') if 'EZDXF' in doc.dimstyles else None
for a,b in zip(xmm[:-1],xmm[1:]):
    msp.add_linear_dim(base=(0,Y0m+1500),p1=(a,Y0m+2000),p2=(b,Y0m+2000),dimstyle='EZDXF',override={'dimtxt':250,'dimasz':150,'dimexe':100,'dimexo':100,'dimlfac':1,'dimdec':0},dxfattribs={'layer':'A-AX----D-'}).render()
for a,b in zip(sorted(ymm)[:-1],sorted(ymm)[1:]):
    msp.add_linear_dim(base=(X0m+1500,0),p1=(X0m+2000,a),p2=(X0m+2000,b),angle=90,dimstyle='EZDXF',override={'dimtxt':250,'dimasz':150,'dimexe':100,'dimexo':100,'dimlfac':1,'dimdec':0},dxfattribs={'layer':'A-AX----D-'}).render()
if xmm: msp.add_linear_dim(base=(0,Y0m+800),p1=(xmm[0],Y0m+2000),p2=(xmm[-1],Y0m+2000),dimstyle='EZDXF',override={'dimtxt':300,'dimasz':150,'dimlfac':1,'dimdec':0},dxfattribs={'layer':'A-AX----D-'}).render()
# (code 008, Т4-13) every layer a primitive uses is in the table: a '...H-' fill of a known '...E-' gets its pair; any
#   other unknown layer is added with a description that says so - verify.py and the gate (S14*) stop on it
from layers8 import dxf_layers as _dxf_layers
_lu=_dxf_layers(doc); _added=[]
for L_ in _lu['unrecorded']:
    # the fill of an object on a '...T-' / '...D-' layer (floor 5: the local dimension of MANUAL on A-90----T-) goes to
    #   '...H-' too: its description is that of the sibling layer
    E_=next((L_[:-2]+x for x in ('E-','T-','D-') if L_[:-2]+x in _LDESC),None)
    d_=(_LDESC[E_]+' — заливка') if L_.endswith('H-') and E_ else 'НЕТ В ТАБЛИЦЕ СЛОЁВ КОДА (layers8.py) — остановка шлюза S14*'
    l_=doc.layers.add(L_,color=8,lineweight=13); l_.description=d_ if 'НЕТ' not in d_ else ''; _added.append((L_,d_))
if _added: print('layers added to the table at export',_added)
doc.saveas(DXF)
pickle.dump(BLOCKGEOM,open('blockgeom.pkl','wb'))
json.dump(dict(stats=stats,walls=wall_stats,blocks=len(BLOCKGEOM),expl=EXPL),open('export_stats.json','w'),ensure_ascii=False,indent=1)
pickle.dump(inst,open('inst_final.pkl','wb'))
print('blocks',len(BLOCKGEOM),'inserts',len(inserts)); print(wall_stats)
for k,v in sorted(stats.items(),key=lambda t:-t[1]): print(v,k)
