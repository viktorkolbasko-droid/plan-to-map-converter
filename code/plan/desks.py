from common import *
import cv2, json
P=load(); cls=pickle.load(open('cls.pkl','rb'))
def istan(c): return is_tan(c)
tm=np.zeros((H,W),np.uint8)
for p in P:
    if p[0]=='qu' and istan(p[3]):
        cv2.fillPoly(tm,[np.array([T(q) for q in p[4]],np.int32)],255)
R=np.load('objr.npy')[:H,:W]
sep=cv2.dilate(R,np.ones((3,3),np.uint8))
m=((tm>0)&(sep==0)).astype(np.uint8)
n,lab,st,cen=cv2.connectedComponentsWithStats(m,connectivity=4)
desks=[]
for i in range(1,n):
    x,y,w,h,a=st[i]
    if a<(4*S)**2: continue
    cs,_=cv2.findContours((lab[y:y+h,x:x+w]==i).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    c=max(cs,key=cv2.contourArea)
    (cx,cy),(rw,rh),ang=cv2.minAreaRect(c)
    fill=a/(rw*rh+1e-9)
    desks.append(dict(x0=x/S+X0,y0=y/S+Y0,x1=(x+w)/S+X0,y1=(y+h)/S+Y0,wmm=round(max(w,h)/S*MM_PER_PT),hmm=round(min(w,h)/S*MM_PER_PT),fill=round(fill,2)))
print(len(desks))
from collections import Counter
print(Counter((round(d['wmm'],-2),round(d['hmm'],-2)) for d in desks).most_common(20))
json.dump(desks,open('desks.json','w'))
viz=np.full((H,W,3),255,np.uint8); viz[R>0]=(170,170,170)
for d in desks: cv2.rectangle(viz,T((d['x0'],d['y0'])),T((d['x1'],d['y1'])),(0,0,255),4)
cv2.imwrite('desks.png',cv2.resize(viz,(W//3,H//3),interpolation=cv2.INTER_AREA))
