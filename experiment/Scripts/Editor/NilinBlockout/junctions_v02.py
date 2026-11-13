"""Planar rail clipping for continuous guarded landings. All units are metres."""
import math

def rectangle(center,size):
    x,y=center[:2];w,d=size
    return [(x-w/2,y-d/2),(x+w/2,y-d/2),(x+w/2,y+d/2),(x-w/2,y+d/2)]

def strip(a,b,width,extra=.25):
    dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);u=(dx/length,dy/length);n=(-u[1],u[0]);w=width/2
    a=(a[0]-u[0]*extra,a[1]-u[1]*extra);b=(b[0]+u[0]*extra,b[1]+u[1]*extra)
    return [(a[0]+n[0]*w,a[1]+n[1]*w),(a[0]-n[0]*w,a[1]-n[1]*w),(b[0]-n[0]*w,b[1]-n[1]*w),(b[0]+n[0]*w,b[1]+n[1]*w)]

def clip_interval(a,b,poly):
    lo,hi=0.,1.;dx,dy=b[0]-a[0],b[1]-a[1]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        ex,ey=q[0]-p[0],q[1]-p[1]
        c=ex*(a[1]-p[1])-ey*(a[0]-p[0]);v=ex*dy-ey*dx
        if abs(v)<1e-9:
            if c<-.00001:return None
        elif v>0:lo=max(lo,-c/v)
        else:hi=min(hi,-c/v)
        if lo>hi:return None
    return (max(0,lo),min(1,hi))

def open_segments(a,b,exclusions):
    cuts=sorted(x for p in exclusions if (x:=clip_interval(a,b,p)) is not None)
    cursor=0.;ranges=[]
    for lo,hi in cuts:
        if lo>cursor:ranges.append((cursor,lo))
        cursor=max(cursor,hi)
    if cursor<1:ranges.append((cursor,1.))
    def lerp(t):return tuple(a[i]+(b[i]-a[i])*t for i in range(2))
    return [(lerp(lo),lerp(hi)) for lo,hi in ranges if math.dist(lerp(lo),lerp(hi))>.35]

def guarded_landings(spec,names):
    rests=[dict(r,points=rectangle(r['center'],r['size'])) for r in spec['rests'] if r['name'] in names]
    rests += [dict(r,points=r.get('points',rectangle(r['center'],r['size']))) for r in spec['platforms'] if r['name'] in names and r.get('shape')!='circle']
    rests += [r for r in spec.get('bridgeheads',[]) if r.get('associated_rest') in names]
    result=[]
    for r in rests:
        outline=r['points'];z=r['center'][2]
        stair_exclusions=[strip(s['a'],s['b'],s['width']+.5) for s in spec['stairs'] if min(s['a'][2],s['b'][2])-.1<=z<=max(s['a'][2],s['b'][2])+.1]
        exclusions=stair_exclusions+[o['points'] for o in rests if o is not r and abs(o['center'][2]-z)<.05]
        for a,b in zip(outline,outline[1:]+outline[:1]):
            for c,d in open_segments(a,b,exclusions):result.append(((*c,z),(*d,z)))
    return result
