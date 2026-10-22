import pickle, math, numpy as np, cv2
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
P,_=pickle.load(open('seq.pkl','rb'))
from common import S,X0,Y0,X1,Y1,W,H,cfg,inboxes
def T(p): return (int(round((p[0]-X0)*S)),int(round((p[1]-Y0)*S)))
_NHC=getattr(cfg,'NOHATCH_COLORS',[])
def isgray(c): return c is not None and abs(c[0]-c[1])<0.02 and abs(c[1]-c[2])<0.02 and c[0]<0.85 and not any(max(abs(c[j]-z[j]) for j in range(3))<=0.015 for z in _NHC)
st=[p for p in P if p[0]=='l' and isgray(p[2])]
longs=[LineString(p[4]) for p in st if math.dist(*p[4])>=1.5]
longs+= [LineString(p[4][:1]+p[4][3:]) for p in P if p[0]=='c']
tree=STRtree(longs)
def touches(q,self_ls):
    pt=Point(q); idx=tree.query(pt.buffer(0.2))
    return any(longs[i].distance(pt)<0.15 and not longs[i].equals(self_ls) for i in idx)
cand=[]
for p in st:
    a,b=p[4]; L=math.dist(a,b)
    if not (0.4<L<9): continue
    ang=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
    if min(abs(ang-0),abs(ang-90),abs(ang-180))<4: continue
    cand.append((a,b,ang,L,p[2]))
mid=np.array([((a[0]+b[0])/2,(a[1]+b[1])/2) for a,b,*_ in cand]); angs=np.array([c[2] for c in cand])
tr=cKDTree(mid); keep=[]
for i,(a,b,ang,L,col) in enumerate(cand):
    nb=tr.query_ball_point(mid[i],14)
    same=sum(1 for j in nb if j!=i and min(abs(angs[j]-ang),180-abs(angs[j]-ang))<2.5)
    if same<2: continue
    ls=LineString([a,b])
    if not (touches(a,ls) or touches(b,ls)): continue
    keep.append(i)
print('cand',len(cand),'hatch',len(keep))
hat=[cand[i] for i in keep]; pickle.dump(hat,open('hatch.pkl','wb'))
hm=np.zeros((H,W),np.uint8)
for a,b,*_ in hat: cv2.line(hm,T(a),T(b),255,2)
lm=np.zeros((H,W),np.uint8)
for p in P:
    if p[0]=='l' and isgray(p[2]): cv2.line(lm,T(p[4][0]),T(p[4][1]),255,1)
    if p[0]=='c' and isgray(p[2]):
        g=p[4]; pts=[]
        for t in np.linspace(0,1,12):
            x=(1-t)**3*g[0][0]+3*(1-t)**2*t*g[1][0]+3*(1-t)*t*t*g[2][0]+t**3*g[3][0]
            y=(1-t)**3*g[0][1]+3*(1-t)**2*t*g[1][1]+3*(1-t)*t*t*g[2][1]+t**3*g[3][1]
            pts.append(T((x,y)))
        cv2.polylines(lm,[np.array(pts,np.int32)],False,255,1)
np.save('hm.npy',hm); np.save('lm.npy',lm)
k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7*S,7*S))
hc=cv2.morphologyEx(hm,cv2.MORPH_CLOSE,k)
free=(lm==0).astype(np.uint8)
n,lab,stt,cen=cv2.connectedComponentsWithStats(free,connectivity=4)
cov=np.bincount(lab.ravel(),weights=(hc>0).ravel(),minlength=n)
area=stt[:,4]
wallc=(cov/np.maximum(area,1)>0.5)&(area<400*S*S); wallc[0]=False
wm=wallc[lab].astype(np.uint8)*255
wm=cv2.morphologyEx(wm,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
wm=np.maximum(wm,cv2.bitwise_and(lm,cv2.dilate(wm,np.ones((3,3),np.uint8))))
np.save('wm.npy',wm); np.save('lab.npy',lab)
viz=np.full((H,W,3),255,np.uint8); viz[lm>0]=(160,160,160); viz[wm>0]=(0,0,200)
cv2.imwrite('walls2.png',cv2.resize(viz,(W//3,H//3),interpolation=cv2.INTER_AREA))
cv2.imwrite('walls2_full.png',viz)
