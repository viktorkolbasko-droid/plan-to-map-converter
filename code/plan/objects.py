from common import *
import cv2, pymupdf as fitz, json
from collections import Counter, defaultdict
P=load()
wm=np.load('wm.npy')
wmd=cv2.dilate(wm,np.ones((5,5),np.uint8))
pg=fitz.open(PDF)[0]; M=pg.rotation_matrix
IN=cfg.SHEET_IN                                   # prims not fully inside: frame, title block, sheet texts
SHEET_BOXES=getattr(cfg,'SHEET_BOXES',[])         # tables (explication, specification) inside IN
AXIS_COLORS=[tuple(c) for c in getattr(cfg,'AXIS_COLORS',[(0.67,0.67,0.67),(1.0,0.67,0.67)])]
AXIS_BOXES=getattr(cfg,'AXIS_BOXES',[])           # axis bubbles and labels outside the building
DIM_X=getattr(cfg,'DIM_X',[]); DIM_Y=getattr(cfg,'DIM_Y',[])   # dimension chains: x of vertical, y of horizontal lines
SHEET_MAXLEN=getattr(cfg,'SHEET_MAXLEN',600)
words=[]
for x in pg.get_text('words'):
    r=fitz.Rect(x[:4])*M; words.append(((r.x0+r.x1)/2,(r.y0+r.y1)/2,x[4],(r.x0,r.y0,r.x1,r.y1)))
tags=[w for w in words if w[2].isdigit() and len(w[2])<=2 and IN[1]<w[1]<IN[3] and IN[0]<w[0]<IN[2] and not inboxes(w[3],SHEET_BOXES)]
json.dump(words,open('words.json','w'),ensure_ascii=False)
cls=[None]*len(P)
def bb(ps):
    xs=[q[0] for q in ps]; ys=[q[1] for q in ps]; return min(xs),min(ys),max(xs),max(ys)
def near_axis_y(y): return min(AX_Y,key=lambda v:abs(v-y)) if AX_Y else y
def near_axis_x(x): return min(AX_X,key=lambda v:abs(v-x)) if AX_X else x
for i,p in enumerate(P):
    ps=pts(p); b=bb(ps); k,w,sc,fc,g,di=p
    L=max(b[2]-b[0],b[3]-b[1])
    # (29.09.2026) length alone is not the sheet: the south glazing band of floors 2, 3, 5 is one line / one grey fill
    #   of 670-760 pt and was dropped with the frame. Long inside SHEET_IN = the frame (>= 1 pt) or a pale mask only
    _long=L>SHEET_MAXLEN and ((k=='l' and (w or 0)>=1.0) or (k!='l' and sc is None and fc is not None and min(fc)>=0.97))
    if not inboxes(b,[IN]) or _long or inboxes(b,SHEET_BOXES): cls[i]='sheet'; continue
    if k=='l' and sc in AXIS_COLORS and (any(abs(g[0][0]-x)<0.3 and abs(g[1][0]-x)<0.3 for x in AX_X) or any(abs(g[0][1]-y)<0.3 and abs(g[1][1]-y)<0.3 for y in AX_Y)):
        cls[i]='axis'; continue
    if k=='l':
        a_,b_=g; m_=((a_[0]+b_[0])/2,(a_[1]+b_[1])/2); diag=abs(abs(a_[0]-b_[0])-abs(a_[1]-b_[1]))<0.3
        isdim=False
        for c in DIM_X:
            if abs(a_[0]-c)<0.05 and abs(b_[0]-c)<0.05: isdim=True                                  # the chain line
            if w>=0.3 and diag and math.dist(m_,(c,near_axis_y(m_[1])))<3.2: isdim=True           # 45 deg tick at an axis
            if abs(a_[1]-b_[1])<0.02 and any(abs(a_[1]-y)<0.05 for y in AX_Y) and min(a_[0],b_[0])>=c-1.2 and max(a_[0],b_[0])<=c+1.2: isdim=True
        for c in DIM_Y:
            if abs(a_[1]-c)<0.05 and abs(b_[1]-c)<0.05: isdim=True
            if w>=0.3 and diag and math.dist(m_,(near_axis_x(m_[0]),c))<3.2: isdim=True
            if abs(a_[0]-b_[0])<0.02 and any(abs(a_[0]-x)<0.05 for x in AX_X) and min(a_[1],b_[1])>=c-1.2 and max(a_[1],b_[1])<=c+1.2: isdim=True
        if isdim: cls[i]='dim'; continue
    if inboxes(b,AXIS_BOXES): cls[i]='axis'; continue
    cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
    # a mark circle drawn as ONE outline around the digit; never a line or a bare fill (floor 1: the X of a rack cell and
    #   its white fill under mark 6 were taken for the mark and lost from the drawing)
    if k!='l' and not (k=='qu' and sc is None) and any(math.hypot(cx-t[0],cy-t[1])<3 and 9<L<18 for t in tags): cls[i]='tag'; continue
    # wall-owned
    inw=all(0<=T(q)[1]<H and 0<=T(q)[0]<W and wmd[T(q)[1],T(q)[0]]>0 for q in ps[::max(1,len(ps)//6)]+[ps[-1]])
    if inw: cls[i]='wall'; continue
    cls[i]='obj'
print(Counter(cls))
pickle.dump(cls,open('cls.pkl','wb'))
# raster for objects
om=np.zeros((H,W),np.int32)
idx=[i for i,c in enumerate(cls) if c=='obj']
m=np.zeros((H,W),np.uint8)
for i in idx:
    p=P[i]; q=np.array([T(v) for v in pts(p)],np.int32)
    if p[0]=='qu' and p[3] is not None and p[3]!=(1.0,1.0,1.0): cv2.fillPoly(m,[q],255)
    if p[0]=='qu' and p[3]==(1.0,1.0,1.0): continue
    cv2.polylines(m,[q],False,255,1)
n,lab,st,cen=cv2.connectedComponentsWithStats(m,connectivity=8)
print('components',n)
# assign prims to components
comp=defaultdict(list)
for i in idx:
    q=T(pts(P[i])[0]); x,y=min(max(q[0],0),W-1),min(max(q[1],0),H-1)
    c=lab[y,x]
    if c==0:
        # search neighborhood
        win=lab[max(0,y-2):y+3,max(0,x-2):x+3]; c=win.max()
    comp[int(c)].append(i)
np.save('olab.npy',lab)
pickle.dump(dict(comp),open('comp.pkl','wb'))
sz=Counter()
for c,l in comp.items():
    x,y,w,h,a=st[c]; sz[(round(max(w,h)/S/2)*2,round(min(w,h)/S/2)*2)]+=1
print(sorted(sz.items(),key=lambda t:-t[1])[:40])
