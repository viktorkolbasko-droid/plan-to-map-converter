from common import *
import json
P=load(); cls=pickle.load(open('cls.pkl','rb'))
import detect8
# (code 008, Т4-3) flange of an I-beam by the building: 150-320 mm (cfg.DETECT8; floor 4: six I-beams behind the north
#   wall have 4.68-4.8 pt = 300 mm flanges, eight others 3.28 pt = 208 mm - the range 3.6-4.6 pt missed them and 14
#   operator boxes took them); without DETECT8 - 3.6-4.6 pt as code 007, converted by the scale of the sheet (№98)
FL=(detect8.pt(150),detect8.pt(320)) if detect8.on('columns') else (ptb(3.6),ptb(4.6))
DEP=(ptb(6.0),ptb(8.5))   # flange to flange, 381-540 mm at 63.5 mm/pt
fl=[]
for i,p in enumerate(P):
    if p[0]!='l' or cls[i] in ('sheet','axis','dim'): continue
    a,b=p[4]; L=math.dist(a,b)
    if FL[0]<=L<=FL[1]:
        if abs(a[1]-b[1])<0.05: fl.append(('h',(a[0]+b[0])/2,a[1],i,min(a[0],b[0]),max(a[0],b[0])))
        if abs(a[0]-b[0])<0.05: fl.append(('v',(a[1]+b[1])/2,a[0],i,min(a[1],b[1]),max(a[1],b[1])))
cols=[]
for o in ('h','v'):
    F=sorted([f for f in fl if f[0]==o],key=lambda f:f[1])
    for j,f in enumerate(F):
        for g in F:
            if g is f: continue
            if abs(g[1]-f[1])<0.3 and DEP[0]<=g[2]-f[2]<=DEP[1]:
                c=(f[1],(f[2]+g[2])/2) if o=='h' else ((f[2]+g[2])/2,f[1])
                lo,hi=min(f[4],g[4]),max(f[5],g[5])
                # extent of the section: flange lines along, flanges +-0.6 pt (thickness) across
                bb=(lo-0.2,f[2]-0.6,hi+0.2,g[2]+0.6) if o=='h' else (f[2]-0.6,lo-0.2,g[2]+0.6,hi+0.2)
                if not any(math.dist(c,q['c'])<2 for q in cols): cols.append(dict(c=c,o=o,d=g[2]-f[2],bb=bb))
# web: a line along the section axis between the flanges (>= 60 % of the flange distance, within 0.35 pt of the axis)
LN=[(i,P[i][4]) for i,p in enumerate(P) if p[0]=='l' and cls[i] not in ('sheet','axis','dim')]
def has_web(c):
    x,y=c['c']; d=c['d']
    for i,(a,b) in LN:
        if c['o']=='h':
            if abs(a[0]-b[0])<0.05 and abs(a[0]-x)<=0.35 and abs(a[1]-b[1])>=0.6*d and min(a[1],b[1])>=y-d/2-0.3 and max(a[1],b[1])<=y+d/2+0.3: return True
        else:
            if abs(a[1]-b[1])<0.05 and abs(a[1]-y)<=0.35 and abs(a[0]-b[0])>=0.6*d and min(a[0],b[0])>=x-d/2-0.3 and max(a[0],b[0])<=x+d/2+0.3: return True
    return False
n0=len(cols); cols=[c for c in cols if has_web(c)]
print('flange pairs',n0,'with web',len(cols))
for c in sorted(cols,key=lambda c:(c['c'][1],c['c'][0])): print([round(v,1) for v in c['c']],c['o'],round(c['d'],2))
json.dump(cols,open('columns.json','w'))
