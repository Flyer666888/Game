"""Small deterministic, metre-scale mesh builders; no UE dependency."""
import math

def roof(width,depth,height=3.0,thickness=.28):
    xs=[-1,-.94,-.82,-.68,-.45,0,.45,.68,.82,.94,1]
    ys=[-1,-.9,-.72,-.45,0,.45,.72,.9,1]
    vertices=[];triangles=[]
    def elevation(x,y):
        hip=max(abs(y),max(0,(abs(x)-.7)/.3))
        return height*max(0,1-hip)**.78+.28*abs(y)**7+.85*abs(x)**9*abs(y)**7
    for bottom in (False,True):
        for y in ys:
            for x in xs:vertices.append((x*width/2,y*depth/2,elevation(x,y)-(thickness if bottom else 0)))
    nx=len(xs);ny=len(ys);n=nx*ny
    for j in range(ny-1):
        for i in range(nx-1):
            a=j*nx+i;b=a+1;c=a+nx;d=c+1
            triangles.extend([(a,b,d),(a,d,c),(a+n,d+n,b+n),(a+n,c+n,d+n)])
    boundary=list(range(nx))+[j*nx+nx-1 for j in range(1,ny)]+list(range((ny-1)*nx+nx-2,(ny-1)*nx-1,-1))+[j*nx for j in range(ny-2,0,-1)]
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):triangles.extend([(a,b+n,b),(a,a+n,b+n)])
    return vertices,triangles

def lathe(profile,segments=48):
    vertices=[];triangles=[]
    for z,r in profile:
        for i in range(segments):
            t=i*2*math.pi/segments;vertices.append((r*math.cos(t),r*math.sin(t),z))
    for j in range(len(profile)-1):
        for i in range(segments):
            a=j*segments+i;b=j*segments+(i+1)%segments;c=a+segments;d=b+segments
            triangles.extend([(a,b,d),(a,d,c)])
    for j,flip in ((0,True),(len(profile)-1,False)):
        centre=len(vertices);vertices.append((0,0,profile[j][0]))
        for i in range(segments):
            a=j*segments+i;b=j*segments+(i+1)%segments
            triangles.append((centre,b,a) if flip else (centre,a,b))
    return vertices,triangles

def torus(radius,tube,segments=48,sides=8):
    v=[];t=[]
    for i in range(segments):
        a=i*2*math.pi/segments
        for j in range(sides):
            b=j*2*math.pi/sides;r=radius+tube*math.cos(b)
            v.append((r*math.cos(a),r*math.sin(a),tube*math.sin(b)))
    for i in range(segments):
        for j in range(sides):
            a=i*sides+j;b=((i+1)%segments)*sides+j;c=i*sides+(j+1)%sides;d=((i+1)%segments)*sides+(j+1)%sides
            t.extend([(a,b,d),(a,d,c)])
    return v,t

def arch_side(length=50,rise=8,thickness=1.0,width=.7,steps=32):
    """Solid shallow stone arch strip oriented along local X, base at Z=0."""
    v=[];t=[]
    for i in range(steps+1):
        x=length*i/steps;z=rise*math.sin(math.pi*i/steps)
        for y,dz in ((-width/2,0),(width/2,0),(-width/2,-thickness),(width/2,-thickness)):v.append((x,y,z+dz))
    for i in range(steps):
        a=i*4;b=a+4
        for q in ((a,b,b+1,a+1),(a+2,a+3,b+3,b+2),(a,a+2,b+2,b),(a+1,b+1,b+3,a+3)):
            t.extend([(q[0],q[1],q[2]),(q[0],q[2],q[3])])
    t.extend([(0,1,3),(0,3,2)])
    a=steps*4;t.extend([(a,a+2,a+3),(a,a+3,a+1)])
    return v,t

def trunk(points,radii,sides=12):
    v=[];t=[]
    for p,r in zip(points,radii):
        for i in range(sides):
            a=2*math.pi*i/sides;v.append((p[0]+r*math.cos(a),p[1]+r*math.sin(a),p[2]))
    for j in range(len(points)-1):
        for i in range(sides):
            a=j*sides+i;b=j*sides+(i+1)%sides;c=a+sides;d=b+sides
            t.extend([(a,b,d),(a,d,c)])
    for j,rev in ((0,True),(len(points)-1,False)):
        c=len(v);v.append(points[j])
        for i in range(sides):
            a=j*sides+i;b=j*sides+(i+1)%sides;t.append((c,b,a) if rev else (c,a,b))
    return v,t

def canopy(seed=0,segments=20,rings=8):
    v=[(0,0,-.5)];t=[]
    for j in range(1,rings):
        a=-math.pi/2+j*math.pi/rings
        for i in range(segments):
            b=2*math.pi*i/segments;variation=1+.13*math.sin(b*5+seed)+.06*math.sin(b*9-seed)
            r=math.cos(a)*variation
            v.append((r*math.cos(b)*.5,r*math.sin(b)*.5,math.sin(a)*.5+.025*math.cos(b*4+seed)))
    top=len(v);v.append((0,0,.5))
    for i in range(segments):
        t.append((0,1+(i+1)%segments,1+i))
        a=1+(rings-2)*segments+i;b=1+(rings-2)*segments+(i+1)%segments;t.append((top,a,b))
    for j in range(rings-2):
        for i in range(segments):
            a=1+j*segments+i;b=1+j*segments+(i+1)%segments;c=a+segments;d=b+segments
            t.extend([(a,b,d),(a,d,c)])
    return v,t
