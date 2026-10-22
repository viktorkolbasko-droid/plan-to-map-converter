# side-by-side: source PDF crop | SVG crop, window in pt
import sys, pymupdf as fitz, numpy as np
from PIL import Image
from svgcrop_lib import crop
from common import SVG, PDF
x0,y0,x1,y1=map(float,sys.argv[1:5]); Wd=int(sys.argv[5]); out=sys.argv[6]; src=sys.argv[7] if len(sys.argv)>7 else SVG
pdf=sys.argv[8] if len(sys.argv)>8 else PDF
pg=fitz.open(pdf)[0]; z=Wd/(x1-x0)
pix=pg.get_pixmap(matrix=fitz.Matrix(z,z),clip=fitz.Rect(x0,y0,x1,y1))
a=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
crop(x0,y0,x1,y1,Wd,'_side_b.png',src); b=Image.open('_side_b.png').convert('RGB')
bg=Image.new('RGB',b.size,'white'); 
im=Image.new('RGB',(a.width+b.width+10,max(a.height,b.height)),'white'); im.paste(a,(0,0)); im.paste(b,(a.width+10,0)); im.save(out); print(im.size)
