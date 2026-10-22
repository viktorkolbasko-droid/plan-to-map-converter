# zoom crop: source raster + wall outlines (pt). usage: zoomwall.py cx cy half zoom out [walls.pkl]
import pickle, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF
import pymupdf as fitz
from PIL import Image, ImageDraw
cx,cy,h,Z=map(float,sys.argv[1:5]); out=sys.argv[5]; wp=sys.argv[6] if len(sys.argv)>6 else 'walls.pkl'
W=pickle.load(open(wp,'rb'))['Wpt']
pg=fitz.open(PDF)[0]
pix=pg.get_pixmap(matrix=fitz.Matrix(Z,Z),clip=fitz.Rect(cx-h,cy-h,cx+h,cy+h))
im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
im=Image.blend(im,Image.new('RGB',im.size,'white'),0.5); dr=ImageDraw.Draw(im)
col={'ext':(200,0,0),'cap':(0,0,220),'gkl':(0,150,0),'blk':(230,120,0)}
for k,v in W.items():
    for g in v:
        for p in ([g] if g.geom_type=='Polygon' else list(g.geoms)):
            for r in [p.exterior]+list(p.interiors):
                c=[((x-cx+h)*Z,(y-cy+h)*Z) for x,y in r.coords]
                dr.line(c,fill=col[k],width=2)
                for x,y in c: dr.ellipse([x-3,y-3,x+3,y+3],outline=col[k])
im.save(out)
