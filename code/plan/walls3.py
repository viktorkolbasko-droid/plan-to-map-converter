import pickle, math, numpy as np, cv2
from common import S,X0,Y0,X1,Y1,W,H,cfg,inboxes,in_curved
P,_=pickle.load(open('seq.pkl','rb'))
hat=[h for h in pickle.load(open('hatch.pkl','rb')) if min(abs(h[2]-45),abs(h[2]-135))<=4.5 or in_curved(h[0])]
print('hatch used',len(hat))
def T(p): return (int(round((p[0]-X0)*S)),int(round((p[1]-Y0)*S)))
def isgray(c): return c is not None and abs(c[0]-c[1])<0.02 and abs(c[1]-c[2])<0.02 and c[0]<0.85
def bez(g,n=12):
    out=[]
    for t in np.linspace(0,1,n):
        out.append(((1-t)**3*g[0][0]+3*(1-t)**2*t*g[1][0]+3*(1-t)*t*t*g[2][0]+t**3*g[3][0],(1-t)**3*g[0][1]+3*(1-t)**2*t*g[1][1]+3*(1-t)*t*t*g[2][1]+t**3*g[3][1]))
    return out
lm=np.zeros((H,W),np.uint8)
for p in P:
    if not isgray(p[2]): continue
    if p[0]=='l': cv2.line(lm,T(p[4][0]),T(p[4][1]),255,1)
    elif p[0]=='c': cv2.polylines(lm,[np.array([T(q) for q in bez(p[4])],np.int32)],False,255,1)
    elif p[0]=='qu': cv2.polylines(lm,[np.array([T(q) for q in p[4]],np.int32)],True,255,1)
hm=np.zeros((H,W),np.uint8)
for a,b,*_ in hat: cv2.line(hm,T(a),T(b),255,1)
lm=np.maximum(lm,hm)
free=(lm==0).astype(np.uint8)
n,lab,st,cen=cv2.connectedComponentsWithStats(free,connectivity=4)
hadj=np.zeros(n); padj=np.zeros(n)
for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
    sl=np.roll(lab,(dy,dx),axis=(0,1))
    isl=(lm>0)
    np.add.at(padj,sl[isl],1)
    np.add.at(hadj,sl[hm>0],1)
area=st[:,4]
ratio=hadj/np.maximum(padj,1)
cell=(area<45*S*S)&(ratio>0.1); cell[0]=False
wm=cell[lab].astype(np.uint8)*255
# line pixels bordered by wall cells on both sides -> wall
d=cv2.dilate(wm,np.ones((3,3),np.uint8))
wm=np.maximum(wm, ((lm>0)&(d>0)).astype(np.uint8)*255)
wm=cv2.morphologyEx(wm,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
np.save('wm.npy',wm); np.save('lm.npy',lm); np.save('hm.npy',hm)
viz=np.full((H,W,3),255,np.uint8); viz[lm>0]=(170,170,170); viz[wm>0]=(0,0,200)
cv2.imwrite('walls3.png',cv2.resize(viz,(W//3,H//3),interpolation=cv2.INTER_AREA)); cv2.imwrite('walls3_full.png',viz)
# drop plant-like blobs
n2,l2,s2,c2=cv2.connectedComponentsWithStats((wm>0).astype(np.uint8),connectivity=8)
keep=np.ones(n2,bool); keep[0]=False
for i in range(1,n2):
    a=s2[i,4]
    if a<80*S*S:
        cs,_=cv2.findContours((l2[s2[i,1]:s2[i,1]+s2[i,3],s2[i,0]:s2[i,0]+s2[i,2]]==i).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        (cx,cy),(rw,rh),ang=cv2.minAreaRect(max(cs,key=cv2.contourArea))
        if a/(rw*rh+1e-9)<0.75 or a<3*S*S: keep[i]=False
wm=(keep[l2]).astype(np.uint8)*255
np.save('wm.npy',wm)
viz=np.full((H,W,3),255,np.uint8); viz[lm>0]=(170,170,170); viz[wm>0]=(0,0,200)
cv2.imwrite('walls3.png',cv2.resize(viz,(W//3,H//3),interpolation=cv2.INTER_AREA)); cv2.imwrite('walls3_full.png',viz)
# iterative stripe filling
for it in range(3):
    wmd=cv2.dilate(wm,np.ones((5,5),np.uint8))>0
    ring=np.zeros(n); rw=np.zeros(n)
    isl=lm>0
    for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
        sl=np.roll(lab,(dy,dx),axis=(0,1))
        np.add.at(ring,sl[isl],1); np.add.at(rw,sl[isl&wmd],1)
    inwall=np.bincount(lab.ravel(),weights=(wm>0).ravel(),minlength=n)
    add=(area<45*S*S)&(rw/np.maximum(ring,1)>0.55)&(inwall<0.5*area); add[0]=False
    print('add',add.sum())
    if add.sum()==0: break
    wm=np.maximum(wm,add[lab].astype(np.uint8)*255)
    d=cv2.dilate(wm,np.ones((3,3),np.uint8)); wm=np.maximum(wm,((lm>0)&(d>0)&(cv2.erode(d,np.ones((3,3),np.uint8))>0)).astype(np.uint8)*255)
    wm=cv2.morphologyEx(wm,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
np.save('wm.npy',wm)
viz=np.full((H,W,3),255,np.uint8); viz[lm>0]=(170,170,170); viz[wm>0]=(0,0,200)
cv2.imwrite('walls3.png',cv2.resize(viz,(W//3,H//3),interpolation=cv2.INTER_AREA)); cv2.imwrite('walls3_full.png',viz)
