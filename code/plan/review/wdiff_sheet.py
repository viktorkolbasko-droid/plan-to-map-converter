# walls before (red) / after (blue) over the source at the biggest differences: wdiff_sheet.py prev_walls.pkl out.png [N]
import pickle, sys, math
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF, kx, ky
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.ops import unary_union
A=pickle.load(open(sys.argv[1],'rb'))['Wpt']; B=pickle.load(open('walls.pkl','rb'))['Wpt']
out=sys.argv[2]; N=int(sys.argv[3]) if len(sys.argv)>3 else 20
ua=unary_union([g for v in A.values() for g in v]); ub=unary_union([g for v in B.values() for g in v])
sd=ua.symmetric_difference(ub)
parts=sorted([g for g in getattr(sd,'geoms',[sd]) if g.area>0.5],key=lambda g:-g.area)[:N]
pg=fitz.open(PDF)[0]; f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
T=240; cols=5
sheet=Image.new('RGB',(cols*(T+6),max(1,(len(parts)+cols-1)//cols)*(T+16)),'white'); d_=ImageDraw.Draw(sheet)
for n,g in enumerate(parts):
    b=g.bounds; cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2; h=max(6,max(b[2]-b[0],b[3]-b[1])/2+5); Z=T/(2*h)
    pix=pg.get_pixmap(matrix=fitz.Matrix(Z,Z),clip=fitz.Rect(cx-h,cy-h,cx+h,cy+h))
    im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).resize((T,T))
    im=Image.blend(im,Image.new('RGB',im.size,'white'),0.5); dr=ImageDraw.Draw(im); s=T/(2*h)
    for W_,col,wd in ((A,(230,0,0),3),(B,(0,70,230),2)):
        for v in W_.values():
            for gg in v:
                for p in ([gg] if gg.geom_type=='Polygon' else list(gg.geoms)):
                    pb=p.bounds
                    if pb[2]<cx-h or pb[0]>cx+h or pb[3]<cy-h or pb[1]>cy+h: continue
                    dr.line([((x-cx+h)*s,(y-cy+h)*s) for x,y in p.exterior.coords],fill=col,width=wd)
    r_,c_=divmod(n,cols); sheet.paste(im,(c_*(T+6),r_*(T+16)+14))
    mmx=kx[0]*cx+kx[1]; mmy=ky[0]*cy+ky[1]
    d_.text((c_*(T+6),r_*(T+16)+1),f"#{n+1} {g.area*kx[0]**2/1e6:.2f}м² ({cx:.0f},{cy:.0f}) {'+' if ub.contains(g.representative_point()) else '-'}",fill='black',font=f)
sheet.save(out); print(sheet.size,len(parts))
