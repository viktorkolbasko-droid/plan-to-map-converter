# source + prims coloured by owner/class in a box: primview.py cx cy half zoom out
import pickle, sys, math
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import load, pts, PDF
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
cx,cy,h,Z=map(float,sys.argv[1:5]); out=sys.argv[5]
P=load(); cls=pickle.load(open('cls.pkl','rb')); I=pickle.load(open('inst_final.pkl','rb'))
own={}
for q in I:
    for i in q['prims']: own[i]=q['key']
WP=pickle.load(open('wallprims.pkl','rb'))
pg=fitz.open(PDF)[0]
pix=pg.get_pixmap(matrix=fitz.Matrix(Z,Z),clip=fitz.Rect(cx-h,cy-h,cx+h,cy+h))
im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
im=Image.blend(im,Image.new('RGB',im.size,'white'),0.7); dr=ImageDraw.Draw(im)
col={'misc':(220,0,0),'lpartc':(240,140,0),'lpart':(240,200,0),'facade':(0,170,170),'loose':(150,0,150)}
for i,p in enumerate(P):
    q=pts(p); xs=[x for x,y in q]; ys=[y for x,y in q]
    if max(xs)<cx-h or min(xs)>cx+h or max(ys)<cy-h or min(ys)>cy+h: continue
    if i in WP: c=(0,0,230)
    elif cls[i]=='axis': c=(230,0,230)
    else: c=col.get(own.get(i),(90,90,90))
    xy=[((x-cx+h)*Z,(y-cy+h)*Z) for x,y in q]
    if p[0]=='l' or p[0]=='c': dr.line(xy,fill=c,width=2)
    else: dr.line(xy,fill=c,width=1)
im.save(out); print(im.size)
