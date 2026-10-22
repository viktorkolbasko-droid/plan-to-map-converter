# test 2 copy of code 006 svgexport.py: + fill-opacity from the hatch transparency (source fills are 50 % meshes)
# code 009 (ocg/): python3 e8s_svg.py <dxf> <svg> <title> - the names come as arguments, not from a cfg.py in the folder
import ezdxf, math, html, sys, hashlib
DXF, SVG, TITLE = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else '')
from shapely.geometry import Polygon as SPoly, LineString as SLine
HSPEC={'A-21----H-':[(45,230)],'A-221---H-':[(45,230)],'A-222---H-':[(45,160),(135,160)],'A-223---H-':[(135,180)]}
HCOL={'A-21----H-':('#1f1f1f',16),'A-221---H-':('#3a3a3a',14),'A-222---H-':('#4a4a4a',9),'A-223---H-':('#5e4a26',12)}
from ezdxf import bbox
doc=ezdxf.readfile(DXF); msp=doc.modelspace()
ext=bbox.extents(msp)
X0,Y0=ext.extmin.x-500,ext.extmin.y-500; X1,Y1=ext.extmax.x+500,ext.extmax.y+500
Wd,Hd=X1-X0,Y1-Y0
STY={'A-21----E-':('#1a1a1a',45),'A-221---E-':('#1a1a1a',40),'A-222---E-':('#1a1a1a',28),'A-223---E-':('#1a1a1a',28),
     'A-22G---E-':('#1c7fd6',22),'A-31----E-':('#1c7fd6',18),'A-32----E-':('#1d8a3a',18),'A-28----E-':('#000',18),
     'A-AX----E-':('#b0b0b0',10),'A-AX----T-':('#444',14),'A-AX----D-':('#444',10),'A-90----T-':('#222',14),'A-68----E-':('#d11',16),
     'A-56----E-':('#8a4b9c',14),'A-00----E-':('#999',10),'A-82----E-':('#6b4f2c',11),'A-89----E-':('#3b7d3b',9),'A-74----E-':('#1f4fa8',12),'A-76----E-':('#a0522d',14),'A-24----E-':('#333',14),'A-66----E-':('#333',14),'A-69----E-':('#2e9e3e',14),'A-43----E-':('#7a7a7a',10),'A-93----E-':('#a0199e',12),
     'A-52----E-':('#2f6f9f',14),'A-53----E-':('#2f6f9f',14),'A-61----E-':('#9a6a00',14),'A-AXM---E-':('#8c8c8c',10)}
FILLPAT={'A-21----H-':'h45d','A-221---H-':'h45','A-222---H-':'hx','A-223---H-':'h45w'}
SRCW=16   # source stroke width 0.24 pt = 16 mm: dense line bands must render solid as in the PDF
for _k,(_c,_w) in list(STY.items()):
    if not _k.startswith('A-AX') and _w<SRCW: STY[_k]=(_c,SRCW)
def col(e):
    try:
        if e.dxf.hasattr('true_color') and e.rgb: return '#%02x%02x%02x'%tuple(e.rgb)
    except: pass
    return None
def fp(x,y): return f'{x:.1f},{y:.1f}'
# owner 09.10.2026 (З-6, З-7): arcs of the DXF (polyline bulges, ARC, CIRCLE in hatches) are SVG arcs; the door swing arc is dashed
DASH={'DOOR-SWING':'50 30'}
def bulge_d(vs,closed):
    """SVG path data of a polyline with bulges: vs = [(x, y, bulge)]"""
    if not vs: return ''
    d='M'+fp(vs[0][0],vs[0][1]); n=len(vs)
    for i in range(n if closed else n-1):
        x1,y1,b=vs[i][0],vs[i][1],(vs[i][2] if len(vs[i])>2 else 0.0); x2,y2=vs[(i+1)%n][0],vs[(i+1)%n][1]
        if abs(b)<1e-9: d+=' L'+fp(x2,y2); continue
        th=4*math.atan(abs(b)); c=math.hypot(x2-x1,y2-y1); r=c/(2*math.sin(th/2)) if th>1e-9 else 0
        d+=f' A{r:.1f},{r:.1f} 0 {1 if th>math.pi else 0},{1 if b>0 else 0} '+fp(x2,y2)
    return d+(' Z' if closed else '')
def bulge_pts(vs,closed,step=5.0):
    """flattened points of a polyline with bulges (for the clipping polygon of a pattern)"""
    out=[]; n=len(vs)
    for i in range(n if closed else n-1):
        x1,y1,b=vs[i][0],vs[i][1],(vs[i][2] if len(vs[i])>2 else 0.0); x2,y2=vs[(i+1)%n][0],vs[(i+1)%n][1]
        out.append((x1,y1))
        if abs(b)<1e-9: continue
        th=4*math.atan(b); c=math.hypot(x2-x1,y2-y1)
        if c<1e-9: continue
        r=c/(2*math.sin(abs(th)/2)); mx,my=(x1+x2)/2,(y1+y2)/2; h=math.sqrt(max(r*r-c*c/4,0))
        ux,uy=(x2-x1)/c,(y2-y1)/c; sgn=1 if (b>0)==(abs(th)<math.pi) else -1
        cx,cy=mx-uy*h*sgn,my+ux*h*sgn
        a1=math.atan2(y1-cy,x1-cx); m=max(2,int(abs(th)/math.radians(step)))
        for k in range(1,m): a=a1+th*k/m; out.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    if not closed and vs: out.append((vs[-1][0],vs[-1][1]))
    return out
def dash(e):
    lt=e.dxf.get('linetype','BYLAYER') if e.dxf.hasattr('linetype') else 'BYLAYER'
    return f' stroke-dasharray="{DASH[lt]}"' if lt in DASH else ''
def bid(bn): return 'b'+hashlib.sha1(bn.encode('utf-8')).hexdigest()[:12]   # test 8: stable symbol id (hash() of str changes per process)
CAP=0.72   # DXF TEXT height of e8_export = 0.72 x the PDF font size (cap height of Arial); SVG font-size is the em
def geo(e,layer_override=None):
    t=e.dxftype(); out=[]
    L=layer_override or e.dxf.layer
    s,w=STY.get(L,('#333',SRCW))
    base=f'stroke="{s}" stroke-width="{w}" fill="none"'
    if t=='LINE':
        out.append(f'<line x1="{e.dxf.start.x:.1f}" y1="{e.dxf.start.y:.1f}" x2="{e.dxf.end.x:.1f}" y2="{e.dxf.end.y:.1f}" {base}/>')
    elif t=='LWPOLYLINE':
        vs=list(e.get_points('xyb'))
        if any(abs(v[2])>1e-9 for v in vs):
            out.append(f'<path d="{bulge_d(vs,e.closed)}" {base}{dash(e)}/>')
        else:
            pts=' '.join(fp(p[0],p[1]) for p in vs)
            tag='polygon' if e.closed else 'polyline'
            out.append(f'<{tag} points="{pts}" {base}{dash(e)}/>')
    elif t=='CIRCLE':
        out.append(f'<circle cx="{e.dxf.center.x:.1f}" cy="{e.dxf.center.y:.1f}" r="{e.dxf.radius:.1f}" {base}{dash(e)}/>')
    elif t=='ARC':
        c=e.dxf.center; r=e.dxf.radius; a0=math.radians(e.dxf.start_angle); a1=math.radians(e.dxf.end_angle)
        sw=(e.dxf.end_angle-e.dxf.start_angle)%360
        p0=(c.x+r*math.cos(a0),c.y+r*math.sin(a0)); p1=(c.x+r*math.cos(a1),c.y+r*math.sin(a1))
        out.append(f'<path d="M{fp(*p0)} A{r:.1f},{r:.1f} 0 {1 if sw>180 else 0},1 {fp(*p1)}" {base}{dash(e)}/>')
    elif t=='HATCH':
        d=''
        for p in e.paths:
            vs=[tuple(v) for v in p.vertices] if hasattr(p,'vertices') else []
            if vs: d+=bulge_d(vs,True)+' '
        if not d: return out
        if e.dxf.solid_fill:
            c=col(e) or '#888'
            try: op=1-float(e.transparency or 0)
            except Exception: op=1
            oa=f' fill-opacity="{op:.2f}"' if op<0.99 else ''
            out.append(f'<path d="{d}" fill="{c}"{oa} fill-rule="evenodd" stroke="none"/>')
        else:
            # explicit hatch lines clipped to the wall body (SVG patterns render unreliably in Figma/cairo)
            rings=[bulge_pts([tuple(v) for v in p.vertices],True) for p in e.paths if hasattr(p,'vertices') and len(p.vertices)>=2]
            rings=[r for r in rings if len(r)>=3]
            if not rings: return out
            poly=SPoly(rings[0],[r for r in rings[1:]]).buffer(0)
            spec=HSPEC.get(e.dxf.layer,[(45,220)])
            segs=[]
            for angle,sp in spec:
                th=math.radians(angle); dx,dy=math.cos(th),math.sin(th); nx,ny=-dy,dx
                x0,y0,x1,y1=poly.bounds; cx,cy=(x0+x1)/2,(y0+y1)/2; R=math.hypot(x1-x0,y1-y0)
                ts=[(x-cx)*nx+(y-cy)*ny for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
                t=math.floor(min(ts)/sp)*sp
                while t<=max(ts):
                    ln=SLine([(cx+nx*t-dx*R,cy+ny*t-dy*R),(cx+nx*t+dx*R,cy+ny*t+dy*R)])
                    g=poly.intersection(ln)
                    for gg in ([g] if g.geom_type=='LineString' else [x for x in getattr(g,'geoms',[]) if x.geom_type=='LineString']):
                        c=list(gg.coords)
                        if len(c)>=2: segs.append('M'+fp(*c[0])+' L'+fp(*c[-1]))
                    t+=sp
            col_,wid=HCOL.get(e.dxf.layer,('#333',12))
            if segs: out.append(f'<path d="{" ".join(segs)}" fill="none" stroke="{col_}" stroke-width="{wid}"/>')
    elif t in ('TEXT',):
        # test 8: the alignment and the size of the DXF text (DXF TEXT height = cap height = CAP em of Arial): a left-aligned
        # text (halign 0, the PDF origin) is drawn from its start, not centred on it, at font-size = height / CAP
        p=e.get_placement()[1] if e.dxf.halign or e.dxf.valign else e.dxf.insert
        out.append(('TEXT',p.x,p.y,e.dxf.height/CAP,e.dxf.text,L,e.dxf.valign,e.dxf.rotation,e.dxf.halign,e.dxf.height,col(e) or '#222'))   # + its colour
    elif t=='MTEXT':
        out.append(('TEXT',e.dxf.insert.x,e.dxf.insert.y,e.dxf.char_height,e.plain_text(),L,2,0,1,e.dxf.char_height,'#222'))
    elif t=='SOLID':
        vs=[e.dxf.vtx0,e.dxf.vtx1,e.dxf.vtx3,e.dxf.vtx2]
        out.append(f'<polygon points="{" ".join(fp(v.x,v.y) for v in vs)}" fill="{s}" stroke="none"/>')
    return out
used=set(); inserts={}
groups={}
texts=[]
def put(layer,s):
    groups.setdefault(layer,[]).append(s)
for e in msp:
    t=e.dxftype(); L=e.dxf.layer
    if t=='INSERT':
        bn=e.dxf.name; used.add(bn)
        tr=f'translate({e.dxf.insert.x:.1f},{e.dxf.insert.y:.1f}) rotate({e.dxf.rotation:.3f}) scale({e.dxf.xscale:g},{e.dxf.yscale:g})'
        # fills of every block go to one group under all linework (source paint order: fills first, lines over them)
        put('FILLS',f'<use href="#{bid(bn)}f" transform="{tr}"/>')
        put(L,f'<use href="#{bid(bn)}" transform="{tr}"><title>{html.escape(doc.blocks[bn].block.dxf.get("description",bn))}</title></use>')
    elif t=='DIMENSION':
        for v in e.virtual_entities():
            for g in geo(v,L):
                if isinstance(g,tuple): texts.append(g)
                else: put(L,g)
    else:
        for g in geo(e):
            if isinstance(g,tuple): texts.append(g)
            else: put(L,g)
syms=[]
for bn in sorted(used):   # test 8: a stable order of the symbols
    blk=doc.blocks[bn]; parts=[]; hparts=[]
    for e in blk:
        for g in geo(e,None):
            if isinstance(g,tuple): continue
            (hparts if e.dxftype()=='HATCH' else parts).append(g)
    syms.append(f'<g id="{bid(bn)}f">{"".join(hparts)}</g>')
    syms.append(f'<g id="{bid(bn)}" data-block="{html.escape(bn)}">{"".join(parts)}</g>')
ORDER=['A-92----H-','A-92----E-','A-AX----E-','A-AX----D-','A-21----H-','A-221---H-','A-222---H-','A-223---H-','FILLS','A-23----E-','A-82----H-','A-89----H-','A-00----H-','A-56----H-','A-73----H-','A-74----H-','A-76----H-',
       'A-21----E-','A-221---E-','A-222---E-','A-223---E-','A-22G---E-','A-31----E-','A-28----E-','A-32----E-']
lays=sorted(groups,key=lambda l:(ORDER.index(l) if l in ORDER else 50,l))
desc={l.dxf.name:l.description for l in doc.layers}; desc['FILLS']='Заливки объектов (под линиями, как в исходнике)'
defs='''<pattern id="h45" patternUnits="userSpaceOnUse" width="220" height="220" patternTransform="rotate(45)"><line x1="110" y1="0" x2="110" y2="220" stroke="#4a4a4a" stroke-width="16"/></pattern>
<pattern id="h45d" patternUnits="userSpaceOnUse" width="220" height="220" patternTransform="rotate(45)"><line x1="110" y1="0" x2="110" y2="220" stroke="#1f1f1f" stroke-width="18"/></pattern>
<pattern id="h45w" patternUnits="userSpaceOnUse" width="180" height="180" patternTransform="rotate(-45)"><line x1="90" y1="0" x2="90" y2="180" stroke="#5e4a26" stroke-width="14"/></pattern>
<pattern id="hx" patternUnits="userSpaceOnUse" width="150" height="150"><path d="M0,0 L150,150 M150,0 L0,150" stroke="#4a4a4a" stroke-width="10"/></pattern>'''
out=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" viewBox="0 0 {Wd:.0f} {Hd:.0f}" width="{Wd/10:.0f}mm" height="{Hd/10:.0f}mm">',
     f'<title>{html.escape(TITLE)} — восстановленный план (единица файла = 1 мм)</title>',f'<defs>{defs}<g id="blocks">{"".join(syms)}</g></defs>',
     f'<rect x="0" y="0" width="{Wd:.0f}" height="{Hd:.0f}" fill="#ffffff"/>',
     f'<g id="drawing" transform="translate({-X0:.1f},{Y1:.1f}) scale(1,-1)">']
for l in lays:
    out.append(f'<g id="{l}" inkscape:groupmode="layer" inkscape:label="{l} {html.escape(desc.get(l,""))}">'+''.join(groups[l])+'</g>')
out.append('</g>')
# texts (unflipped)
tg={}
ANCHOR={0:'start',1:'middle',2:'end',4:'middle'}   # DXF halign: left, center, right, middle
for (_,x,y,fs,s,L,va,rot,ha,cap,tc) in texts:
    X=x-X0; Y=Y1-y
    dy=cap*0.5 if va==2 else (cap if va==3 else 0)   # baseline from the cap height: middle — half of it, top — all of it
    tr=f' transform="rotate({-rot:.2f} {X:.0f} {Y:.0f})"' if abs(rot)>0.01 else ''
    tg.setdefault(L,[]).append(f'<text x="{X:.0f}" y="{Y+dy:.0f}" font-size="{fs:.0f}" text-anchor="{ANCHOR.get(ha,"middle")}" font-family="Arial, sans-serif" fill="{tc}"{tr}>{html.escape(s)}</text>')
for L,v in tg.items(): out.append(f'<g id="{L}-text" inkscape:groupmode="layer" inkscape:label="{L} текст">'+''.join(v)+'</g>')
out.append('</svg>')
open(SVG,'w').write('\n'.join(out))
print('svg layers',len(lays),'symbols',len(syms),'texts',len(texts), 'size',round(Wd),round(Hd))
