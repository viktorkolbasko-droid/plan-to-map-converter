# zoom sheet of doors: source + wall outlines + door hinge (red) / closed end (blue) + owners of prims near the jambs
import pickle, sys, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF, kx, ky, walls_file
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
out=sys.argv[1]; N=int(sys.argv[2]) if len(sys.argv)>2 else 12
def mm2pt(p): return ((p[0]-kx[1])/kx[0],(p[1]-ky[1])/ky[0])
P=pickle.load(open('seq.pkl','rb'))[0]
inst=pickle.load(open('inst_final.pkl','rb'))
W=pickle.load(open(walls_file(),'rb'))['Wpt']
own={}
for q in inst:
    for i in q['prims']: own[i]=q['key']
COL={'door':(0,150,0),'wcacc':(200,0,200),'misc':(255,120,0),'wallline':(120,60,0),'lpart':(0,170,200),'lpartc':(0,120,160),'loose':(160,160,0),'doorhw':(0,0,0)}
import os
_sel=os.environ.get('AT')
doors=[q for q in inst if q['key']=='door' and q.get('hinge_mm')]
if _sel:
    pts_=[tuple(map(float,x.split(':'))) for x in _sel.split(',')]
    doors=[q for q in doors if any(math.dist(q['hinge_mm'],p)<50 for p in pts_)]
doors=doors[:N]
pg=fitz.open(PDF)[0]; f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
T=300; cols=4
sheet=Image.new('RGB',(cols*(T+6),((len(doors)+cols-1)//cols)*(T+16)),'white'); d_=ImageDraw.Draw(sheet)
for n,q in enumerate(doors):
    H=mm2pt(q['hinge_mm']); C=mm2pt(q['closed_mm']); cx,cy=(H[0]+C[0])/2,(H[1]+C[1])/2; h=max(8,math.dist(H,C)/2+4); Z=T/(2*h)
    pix=pg.get_pixmap(matrix=fitz.Matrix(Z,Z),clip=fitz.Rect(cx-h,cy-h,cx+h,cy+h))
    im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).resize((T,T))
    im=Image.blend(im,Image.new('RGB',im.size,'white'),0.55); dr=ImageDraw.Draw(im); s=T/(2*h)
    tf=lambda p:((p[0]-cx+h)*s,(p[1]-cy+h)*s)
    for k,v in W.items():
        for g in v:
            for p in ([g] if g.geom_type=='Polygon' else list(g.geoms)):
                dr.line([tf(c) for c in p.exterior.coords],fill=(255,140,0),width=2)
    for i,p in enumerate(P):
        if p[0]!='l': continue
        a,b=p[4]
        if max(a[0],b[0])<cx-h or min(a[0],b[0])>cx+h or max(a[1],b[1])<cy-h or min(a[1],b[1])>cy+h: continue
        k=own.get(i)
        if k in COL: dr.line([tf(a),tf(b)],fill=COL[k],width=2)
    for pnt,c in ((H,(255,0,0)),(C,(0,0,255))):
        x,y=tf(pnt); dr.ellipse([x-5,y-5,x+5,y+5],outline=c,width=2)
    r_,c_=divmod(n,cols); sheet.paste(im,(c_*(T+6),r_*(T+16)+14)); d_.text((c_*(T+6),r_*(T+16)+1),f"{q['name']} ({cx:.0f},{cy:.0f})",fill='black',font=f)
sheet.save(out); print(sheet.size)
