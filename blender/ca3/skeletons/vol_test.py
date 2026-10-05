import numpy as np, time
from scipy import ndimage
t0=time.time()
d=np.load(r'D:\Meshes\skeletons\648518346438632877.npz',allow_pickle=True)
sv=d['vertices']
mv=[]
with open(r"D:\Meshes\hero\hero_648518346438632877.obj") as f:
    for line in f:
        if line[0]=='v' and line[1]==' ': mv.append(line[2:])
mv=np.fromstring(" ".join(mv),sep=' ').reshape(-1,3)
print("mesh",mv.shape,f"{time.time()-t0:.0f}s",flush=True)

VOX=400.0; HALF=12000.0
def local_vol(c):
    lo,hi=c-HALF,c+HALF
    m=((mv>=lo).all(1)&(mv<=hi).all(1))
    p=mv[m]
    if len(p)<50: return 0.0,0.0,0
    g=((p-lo)/VOX).astype(int)
    n=int(2*HALF/VOX)
    g=np.clip(g,0,n-1)
    occ=np.zeros((n,n,n),bool); occ[g[:,0],g[:,1],g[:,2]]=True
    occ=ndimage.binary_closing(occ,np.ones((3,3,3)))
    fill=ndimage.binary_fill_holes(occ)
    interior=fill&~occ
    # biggest interior connected blob -> equivalent-sphere radius
    lab,nl=ndimage.label(interior)
    if nl==0: return len(p),0.0,0
    sizes=ndimage.sum(interior,lab,range(1,nl+1))
    big=sizes.max()*(VOX/1000.)**3          # um^3
    R=(3*big/(4*np.pi))**(1/3.)
    return len(p), big, R

cands=[133,204,199,234,226,215,216,225,110,162,164,0]
print("\nnode   nverts_in_24um_box   biggest_interior_blob_um3   equiv_radius_um   pos")
for i in cands:
    n,vol,R=local_vol(sv[i])
    print(f"{i:5d}  {n:9d}   {vol:12.1f}   {R:8.2f}   {sv[i].round(0)}",flush=True)
