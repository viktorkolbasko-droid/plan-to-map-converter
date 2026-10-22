from common import *
import cv2
P=load(); cls=pickle.load(open('cls.pkl','rb'))
def render(idx, box=None, th=1):
    if box is None: x0,y0,x1,y1=X0,Y0,X1,Y1
    else: x0,y0,x1,y1=box
    w,h=int(round((x1-x0)*S))+1,int(round((y1-y0)*S))+1
    m=np.zeros((h,w),np.uint8)
    for i in idx:
        p=P[i]
        if p[0]=='qu': continue
        q=np.array([(int(round((v[0]-x0)*S)),int(round((v[1]-y0)*S))) for v in pts(p)],np.int32)
        cv2.polylines(m,[q],False,255,th)
    return m
OBJ=[i for i,c in enumerate(cls) if c=='obj']
def full(): 
    try: return np.load('objr.npy')
    except: 
        m=render(OBJ); np.save('objr.npy',m); return m
def tmpl_from_box(box):
    x0,y0,x1,y1=box
    idx=[i for i in OBJ if P[i][0]!='qu' and all(x0<=q[0]<=x1 and y0<=q[1]<=y1 for q in pts(P[i]))]
    return idx, render(idx,box)
def variants(t):
    out=[]
    for k in range(4):
        r=np.rot90(t,k); out.append((k,False,r)); out.append((k,True,np.fliplr(r)))
    return out
def find(box, thr=0.75, sym_dedupe=True, region=None):
    idx,t=tmpl_from_box(box)
    R=full().astype(np.float32)
    Rb=cv2.GaussianBlur(R,(0,0),1.0)
    hits=[]
    seenshape=[]
    for k,fl,v in variants(t):
        key=v.tobytes()+bytes(v.shape)
        if sym_dedupe and key in seenshape: continue
        seenshape.append(key)
        vb=cv2.GaussianBlur(v.astype(np.float32),(0,0),1.0)
        res=cv2.matchTemplate(Rb,vb,cv2.TM_CCOEFF_NORMED)
        ink=cv2.boxFilter((R>0).astype(np.float32),-1,(v.shape[1],v.shape[0]),normalize=False,anchor=(0,0))[:res.shape[0],:res.shape[1]]
        tink=(v>0).sum()
        res=np.where((ink>0.7*tink)&(ink<1.4*tink),res,0)
        ys,xs=np.where(res>=thr)
        for y,x in zip(ys,xs): hits.append((float(res[y,x]),x,y,v.shape[1],v.shape[0],k,fl))
    hits.sort(reverse=True); keep=[]
    for h in hits:
        cx,cy=h[1]+h[3]/2,h[2]+h[4]/2
        if any(abs(cx-(g[1]+g[3]/2))<min(h[3],h[4])*0.5 and abs(cy-(g[2]+g[4]/2))<min(h[3],h[4])*0.5 for g in keep): continue
        keep.append(h)
    return idx,t,keep
