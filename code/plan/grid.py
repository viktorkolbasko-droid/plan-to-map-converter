import pymupdf as fitz, sys, math
from PIL import Image, ImageDraw, ImageFont
# coords in rotated (display) page space: 1191 x 842
fn,tag,x0,y0,x1,y1,S=sys.argv[1],sys.argv[2],*map(float,sys.argv[3:8])
step=int(sys.argv[8]) if len(sys.argv)>8 else 20
d=fitz.open(fn); p=d[0]
# display-space clip -> unrotated clip
IM=~p.rotation_matrix
r=fitz.Rect(x0,y0,x1,y1)
pix=p.get_pixmap(matrix=fitz.Matrix(S,S).prerotate(0), clip=r)
im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
im=Image.blend(im, Image.new('RGB',im.size,'white'),0.2)
dr=ImageDraw.Draw(im); f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
for x in range(int(math.ceil(x0/step)*step), int(x1), step):
    X=(x-x0)*S; dr.line([(X,0),(X,im.height)],fill=(255,0,0) if x%100==0 else (255,190,190),width=1); dr.text((X+2,2),str(x),fill=(200,0,0),font=f)
for y in range(int(math.ceil(y0/step)*step), int(y1), step):
    Y=(y-y0)*S; dr.line([(0,Y),(im.width,Y)],fill=(0,0,255) if y%100==0 else (190,190,255),width=1); dr.text((2,Y+2),str(y),fill=(0,0,200),font=f)
im.save(tag+'.png'); print(im.size)
