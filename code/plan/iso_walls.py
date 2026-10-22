# Contact sheet of isolated wall bodies without a regular hatch pattern (plan/rules/60: 'отдельные тела без узора').
# Usage (in a floor folder): python3 iso_walls.py [out.png]. Bodies not touching other walls, 20-600 pt2, without two
# distinct parallel hatch strokes >= 1.5 pt: thin strips with short strokes are real walls, compact blobs are furniture.
import sys, os, pickle, math
sys.path.insert(0,'/home/claude/eng/code')
from common import load, PDF
from shapely.geometry import LineString
from shapely.ops import unary_union
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
out=sys.argv[1] if len(sys.argv)>1 else "iso_walls.png"
P=load()
W=pickle.load(open('walls.pkl','rb'))['Wpt']; H=pickle.load(open('hat3.pkl','rb'))['hat']
cls_of={}
for k,v in W.items():
    for g in v:
        for gg in ([g] if g.geom_type=='Polygon' else list(g.geoms)): cls_of[id(gg)]=k
allg=unary_union([g for v in W.values() for g in v])
comps=list(allg.geoms) if allg.geom_type=='MultiPolygon' else [allg]
G={i:LineString(P[i][4]) for i in H}
def ang(a,b): return math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
res=[]
for c in comps:
    if not (20<=c.area<600): continue
    if any(o is not c and o.distance(c)<0.05 for o in comps): continue
    cb=c.buffer(0.05)
    ins=[i for i in H if cb.contains(G[i]) and math.dist(*P[i][4])>=1.5]
    ok=False
    for x in range(len(ins)):
        for y in range(x+1,len(ins)):
            a1=ang(*P[ins[x]][4]); a2=ang(*P[ins[y]][4])
            if abs(((a1-a2)+90)%180-90)>=2: continue
            (x1,y1),(x2,y2)=P[ins[x]][4]; L=math.dist((x1,y1),(x2,y2)); nx,ny=-(y2-y1)/L,(x2-x1)/L
            mx,my=[(u+v)/2 for u,v in zip(*P[ins[y]][4])]
            if abs((mx-x1)*nx+(my-y1)*ny)>=0.5: ok=True; break
        if ok: break
    if not ok: res.append(c)
print(len(res))
pg=fitz.open(PDF)[0]; f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
T=200; cols=6
sheet=Image.new('RGB',(cols*(T+6),max(1,(len(res)+cols-1)//cols)*(T+18)),'white'); d=ImageDraw.Draw(sheet)
for k,g in enumerate(res):
    x0,y0,x1,y1=g.bounds; cx,cy=(x0+x1)/2,(y0+y1)/2; h=max(x1-x0,y1-y0)/2+5; Z=T/(2*h)
    pix=pg.get_pixmap(matrix=fitz.Matrix(Z,Z),clip=fitz.Rect(cx-h,cy-h,cx+h,cy+h))
    im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    im=Image.blend(im,Image.new('RGB',im.size,'white'),0.3).convert('RGBA')
    ov=Image.new('RGBA',im.size,(0,0,0,0)); dr=ImageDraw.Draw(ov)
    dr.polygon([((u-(cx-h))*Z,(v-(cy-h))*Z) for u,v in g.exterior.coords],fill=(0,0,220,90))
    im=Image.alpha_composite(im,ov).convert('RGB').resize((T,T))
    r_,c_=divmod(k,cols); sheet.paste(im,(c_*(T+6),r_*(T+18)+16)); d.text((c_*(T+6),r_*(T+18)+2),f"#{k} {g.area:.0f} ({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})",fill='black',font=f)
sheet.save(out); print(sheet.size)
