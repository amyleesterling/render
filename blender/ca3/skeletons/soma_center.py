import numpy as np, json
from scipy import ndimage
d=np.load(r'D:\Meshes\skeletons\648518346438632877.npz',allow_pickle=True)
sv=d['vertices']
mv=[]
with open(r"D:\Meshes\hero\hero_648518346438632877.obj") as f:
    for line in f:
        if line[0]=='v' and line[1]==' ': mv.append(line[2:])
mv=np.fromstring(" ".join(mv),sep=' ').reshape(-1,3)
c=(sv[234]+sv[215])/2.0
VOX=300.0; HALF=16000.0
lo,hi=c-HALF,c+HALF
p=mv[((mv>=lo).all(1)&(mv<=hi).all(1))]
n=int(2*HALF/VOX)
g=np.clip(((p-lo)/VOX).astype(int),0,n-1)
occ=np.zeros((n,n,n),bool); occ[g[:,0],g[:,1],g[:,2]]=True
occ=ndimage.binary_closing(occ,np.ones((3,3,3)))
interior=ndimage.binary_fill_holes(occ)&~occ
lab,nl=ndimage.label(interior)
sizes=ndimage.sum(interior,lab,range(1,nl+1))
k=int(np.argmax(sizes))+1
vol=sizes.max()*(VOX/1000.)**3
com=np.array(ndimage.center_of_mass(lab==k))*VOX+lo
R=(3*vol/(4*np.pi))**(1/3.)
print(f"soma volume {vol:.0f} um^3, equiv radius {R:.2f} um")
print("soma centre (nm, OBJ file space):", com.round(0).tolist())
dd=np.linalg.norm(sv-com,axis=1)
order=np.argsort(dd)[:6]
print("\nnearest skeleton nodes to soma centre:")
for i in order:
    print(f"  idx {i:4d}  dist {dd[i]/1000:6.2f} um  pos {sv[i].round(0)}")
json.dump({"soma_centre_nm":com.round(1).tolist(),"soma_volume_um3":round(float(vol),1),
           "soma_equiv_radius_um":round(float(R),2),"nearest_node":int(order[0]),
           "nearest_node_dist_um":round(float(dd[order[0]]/1000),2)},
          open(r'D:\Meshes\skeletons\_soma.json','w'),indent=1)
