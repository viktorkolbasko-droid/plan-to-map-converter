import ezdxf, numpy as np, cv2, pymupdf as fitz, sys
from ezdxf import disassemble
from common import kx,ky,DXF,PDF,cfg
doc=ezdxf.readfile(DXF); msp=doc.modelspace()
import os; Z=int(os.environ.get("Z","4"))
pg=fitz.open(PDF)[0]
x0,y0,x1,y1=[float(v) for v in sys.argv[1:5]] if len(sys.argv)>4 else cfg.WIN
pix=pg.get_pixmap(matrix=fitz.Matrix(Z,Z),clip=fitz.Rect(x0,y0,x1,y1))
im=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()
gray=cv2.cvtColor(im,cv2.COLOR_RGB2GRAY); base=np.full_like(im,255); base[gray<200]=(185,185,185)
def topx(x,y):
    px=(x-kx[1])/kx[0]; py=(y-ky[1])/ky[0]; return (int(round((px-x0)*Z)),int(round((py-y0)*Z)))
COL={'A-2':(0,0,220),'A-3':(0,150,0),'A-82':(200,120,0),'A-7':(200,0,200),'A-89':(0,140,0),'A-28':(0,0,0),'A-56':(150,0,150),'A-00':(0,160,255),'A-AX':(170,170,255)}
def c(layer):
    for k in sorted(COL,key=len,reverse=True):
        if layer.startswith(k): return COL[k]
    return (60,60,60)
def walk():
    for e in msp:
        if e.dxftype()=='INSERT':
            for v in e.virtual_entities(): yield e.dxf.layer,v
        elif e.dxftype()=='DIMENSION': continue
        else: yield e.dxf.layer,e
n=0
for L,ent in walk():
  if L.endswith('H-'): continue
  for p in disassemble.to_primitives([ent]):
    if L.endswith('H-'): continue
    try: vs=list(p.vertices())
    except: continue
    if len(vs)<2: continue
    pts=np.array([topx(v.x,v.y) for v in vs],np.int32)
    cv2.polylines(base,[pts],False,c(L)[::-1],1 if Z<8 else 2); n+=1
cv2.imwrite(sys.argv[5] if len(sys.argv)>5 else 'overlay.png',base)
print(n)
