import ezdxf, math, html, sys
from common import DXF, SVG, cfg
from shapely.geometry import Polygon as SPoly, LineString as SLine
HSPEC={'A-21----H-':[(45,230)],'A-221---H-':[(45,230)],'A-222---H-':[(45,160),(135,160)],'A-223---H-':[(135,180)]}
HCOL={'A-21----H-':('#1f1f1f',16),'A-221---H-':('#3a3a3a',14),'A-222---H-':('#4a4a4a',9),'A-223---H-':('#5e4a26',12)}
from ezdxf import bbox
doc=ezdxf.readfile(DXF); msp=doc.modelspace()
ext=bbox.extents(msp)
X0,Y0=ext.extmin.x-500,ext.extmin.y-500; X1,Y1=ext.extmax.x+500,ext.extmax.y+500
Wd,Hd=X1-X0,Y1-Y0
STY={'A-21----E-':('#1a1a1a',45),'A-221---E-':('#1a1a1a',40),'A-222---E-':('#1a1a1a',28),'A-223---E-':('#1a1a1a',28),
     'A-22G---E-':('#1c7fd6',22),'A-23----E-':('#6a00aa',22),'A-31----E-':('#1c7fd6',18),'A-32----E-':('#1d8a3a',18),'A-28----E-':('#000',18),
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
def geo(e,layer_override=None):
    t=e.dxftype(); out=[]
    L=layer_override or e.dxf.layer
    s,w=STY.get(L,('#333',SRCW))
    # (code 007, 04.10.2026, строка 172) an entity with its own colour keeps it: a glass door is drawn in the glass style
    if t in ('LINE','LWPOLYLINE','CIRCLE') and col(e): s=col(e)
    base=f'stroke="{s}" stroke-width="{w}" fill="none"'
    if t=='LINE':
        out.append(f'<line x1="{e.dxf.start.x:.1f}" y1="{e.dxf.start.y:.1f}" x2="{e.dxf.end.x:.1f}" y2="{e.dxf.end.y:.1f}" {base}/>')
    elif t=='LWPOLYLINE':
        pts=' '.join(fp(p[0],p[1]) for p in e.get_points('xy'))
        tag='polygon' if e.closed else 'polyline'
        out.append(f'<{tag} points="{pts}" {base}/>')
    elif t=='CIRCLE':
        out.append(f'<circle cx="{e.dxf.center.x:.1f}" cy="{e.dxf.center.y:.1f}" r="{e.dxf.radius:.1f}" {base}/>')
    elif t=='HATCH':
        d=''
        for p in e.paths:
            vs=[(v[0],v[1]) for v in p.vertices] if hasattr(p,'vertices') else []
            if vs: d+='M'+' L'.join(fp(*v) for v in vs)+' Z '
        if not d: return out
        if e.dxf.solid_fill:
            c=col(e) or '#888'
            out.append(f'<path d="{d}" fill="{c}" fill-rule="evenodd" stroke="none"/>')
        else:
            # explicit hatch lines clipped to the wall body (SVG patterns render unreliably in Figma/cairo)
            rings=[[(v[0],v[1]) for v in p.vertices] for p in e.paths if hasattr(p,'vertices') and len(p.vertices)>=3]
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
        p=e.get_placement()[1] if e.dxf.halign or e.dxf.valign else e.dxf.insert
        hgt=e.dxf.height; anchor='middle'
        out.append(('TEXT',p.x,p.y,hgt,e.dxf.text,L,e.dxf.valign,e.dxf.rotation))
    elif t=='MTEXT':
        out.append(('TEXT',e.dxf.insert.x,e.dxf.insert.y,e.dxf.char_height,e.plain_text(),L,2,0))
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
        put('FILLS',f'<use href="#b{abs(hash(bn))}f" transform="{tr}"/>')
        put(L,f'<use href="#b{abs(hash(bn))}" transform="{tr}"><title>{html.escape(doc.blocks[bn].block.dxf.get("description",bn))}</title></use>')
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
for bn in used:
    blk=doc.blocks[bn]; parts=[]; hparts=[]
    for e in blk:
        for g in geo(e,None):
            if isinstance(g,tuple): continue
            (hparts if e.dxftype()=='HATCH' else parts).append(g)
    syms.append(f'<g id="b{abs(hash(bn))}f">{"".join(hparts)}</g>')
    syms.append(f'<g id="b{abs(hash(bn))}" data-block="{html.escape(bn)}">{"".join(parts)}</g>')
ORDER=['A-92----H-','A-92----E-','A-AX----E-','A-AX----D-','A-21----H-','A-221---H-','A-222---H-','A-223---H-','FILLS','A-23----E-','A-82----H-','A-89----H-','A-00----H-','A-56----H-','A-73----H-','A-74----H-','A-76----H-',
       'A-21----E-','A-221---E-','A-222---E-','A-223---E-','A-22G---E-','A-31----E-','A-28----E-','A-32----E-']
lays=sorted(groups,key=lambda l:(ORDER.index(l) if l in ORDER else 50,l))
desc={l.dxf.name:l.description for l in doc.layers}; desc['FILLS']='Заливки объектов (под линиями, как в исходнике)'
defs='''<pattern id="h45" patternUnits="userSpaceOnUse" width="220" height="220" patternTransform="rotate(45)"><line x1="110" y1="0" x2="110" y2="220" stroke="#4a4a4a" stroke-width="16"/></pattern>
<pattern id="h45d" patternUnits="userSpaceOnUse" width="220" height="220" patternTransform="rotate(45)"><line x1="110" y1="0" x2="110" y2="220" stroke="#1f1f1f" stroke-width="18"/></pattern>
<pattern id="h45w" patternUnits="userSpaceOnUse" width="180" height="180" patternTransform="rotate(-45)"><line x1="90" y1="0" x2="90" y2="180" stroke="#5e4a26" stroke-width="14"/></pattern>
<pattern id="hx" patternUnits="userSpaceOnUse" width="150" height="150"><path d="M0,0 L150,150 M150,0 L0,150" stroke="#4a4a4a" stroke-width="10"/></pattern>'''
out=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" viewBox="0 0 {Wd:.0f} {Hd:.0f}" width="{Wd/10:.0f}mm" height="{Hd/10:.0f}mm">',
     f'<title>{html.escape(cfg.TITLE)} — восстановленный план (единица файла = 1 мм)</title>',f'<defs>{defs}<g id="blocks">{"".join(syms)}</g></defs>',
     f'<rect x="0" y="0" width="{Wd:.0f}" height="{Hd:.0f}" fill="#ffffff"/>',
     f'<g id="drawing" transform="translate({-X0:.1f},{Y1:.1f}) scale(1,-1)">']
for l in lays:
    out.append(f'<g id="{l}" inkscape:groupmode="layer" inkscape:label="{l} {html.escape(desc.get(l,""))}">'+''.join(groups[l])+'</g>')
out.append('</g>')
# texts (unflipped)
tg={}
for (_,x,y,h,s,L,va,rot) in texts:
    X=x-X0; Y=Y1-y
    dy=h*0.35 if va==2 else (h if va==3 else 0)
    tr=f' transform="rotate({-rot:.2f} {X:.0f} {Y:.0f})"' if abs(rot)>0.01 else ''
    tg.setdefault(L,[]).append(f'<text x="{X:.0f}" y="{Y+dy:.0f}" font-size="{h:.0f}" text-anchor="middle" font-family="Arial, sans-serif" fill="#222"{tr}>{html.escape(s)}</text>')
for L,v in tg.items(): out.append(f'<g id="{L}-text" inkscape:groupmode="layer" inkscape:label="{L} текст">'+''.join(v)+'</g>')
out.append('</svg>')
open(SVG,'w').write('\n'.join(out))
print('svg layers',len(lays),'symbols',len(syms),'texts',len(texts), 'size',round(Wd),round(Hd))
