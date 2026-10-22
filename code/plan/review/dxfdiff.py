# raster diff of two DXFs of one floor (pt space, Z px/pt): contact sheet of the biggest changed spots
# usage (in floor folder): dxfdiff.py before.dxf after.dxf out.png [N]
import sys, os, numpy as np, cv2, ezdxf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ezdxf import disassemble, path as ezpath
from common import kx, ky, cfg
from PIL import Image, ImageDraw, ImageFont
A,B,out=sys.argv[1:4]; N=int(sys.argv[4]) if len(sys.argv)>4 else 24
Z=6; X0,Y0,X1,Y1=cfg.WIN; W,H=int((X1-X0)*Z),int((Y1-Y0)*Z)
def mm2pt(x,y): return ((x-kx[1])/kx[0],(y-ky[1])/ky[0])
def px(v): p=mm2pt(v.x,v.y); return (int(round((p[0]-X0)*Z)),int(round((p[1]-Y0)*Z)))
def rast(fn):
    doc=ezdxf.readfile(fn); m=np.zeros((H,W),np.uint8)
    def draw(e):
        if e.dxftype() in ('TEXT','MTEXT','DIMENSION'): return
        if e.dxftype()=='HATCH':
            if not e.dxf.solid_fill: return
            for p in ezpath.from_hatch(e):
                vs=list(p.flattening(5))
                if len(vs)>=3: cv2.fillPoly(m,[np.array([px(v) for v in vs],np.int32)],128)
            return
        for pr in disassemble.to_primitives([e]):
            try: vs=list(pr.vertices())
            except Exception: continue
            if len(vs)>=2: cv2.polylines(m,[np.array([px(v) for v in vs],np.int32)],False,255,1)
    for e in doc.modelspace():
        if e.dxftype()=='INSERT':
            for v in e.virtual_entities(): draw(v)
        else: draw(e)
    return m
a=rast(A); b=rast(B)
d=((a>0)!=(b>0)).astype(np.uint8)
n,lab,st,_=cv2.connectedComponentsWithStats(cv2.dilate(d,np.ones((7,7),np.uint8)))
comps=sorted([(int((d[st[k,1]:st[k,1]+st[k,3],st[k,0]:st[k,0]+st[k,2]]>0).sum()),k) for k in range(1,n)],reverse=True)
print('changed px',int(d.sum()),'spots',n-1)
f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',10)
T=180; cols=6; sel=comps[:N]
sheet=Image.new('RGB',(cols*(T+6),max(1,(len(sel)+cols-1)//cols)*(T+16)),'white'); dd=ImageDraw.Draw(sheet)
for i,(cnt,k) in enumerate(sel):
    x,y,w,h=st[k,:4]; cx,cy=x+w//2,y+h//2; r=max(20,max(w,h)//2+10)
    x0,y0=max(0,cx-r),max(0,cy-r); x1,y1=min(W,cx+r),min(H,cy+r)
    im=np.full((y1-y0,x1-x0,3),255,np.uint8)
    ca=a[y0:y1,x0:x1]>0; cb=b[y0:y1,x0:x1]>0
    im[ca&cb]=(150,150,150); im[ca&~cb]=(220,40,40); im[cb&~ca]=(40,90,230)
    pim=Image.fromarray(im).resize((T,T),Image.NEAREST)
    rr,cc=divmod(i,cols); sheet.paste(pim,(cc*(T+6),rr*(T+16)+14))
    dd.text((cc*(T+6),rr*(T+16)+1),f"{cnt}px ({x/Z+X0:.0f},{y/Z+Y0:.0f})",fill='black',font=f)
sheet.save(out); print(sheet.size)
for cnt,k in comps[:10]: x,y,w,h=st[k,:4]; print(cnt,round(x/Z+X0,1),round(y/Z+Y0,1),round(w/Z,1),round(h/Z,1))
