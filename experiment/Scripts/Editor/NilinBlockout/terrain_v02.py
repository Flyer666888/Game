"""Deterministic, standard-library-only V02 karst terrain source generator.

Reads actual mirrored UE-world LayoutSpec; never imports Unreal or writes umap.
All OBJ/mesh_source vertices are METRES in already-mirrored UE world space.
ue_mesh_v02.make_asset multiplies these by 100; spawn each mesh at world zero.

The five closed meshes replace the old repeated rock/backbone cylinders only.
Existing stairs, floor slabs, rails, eye positions, gate and furnace stay put.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LAYOUT = ROOT / "Docs/LevelDesign/Blockout_v01/LayoutSpec.json"
if (ROOT / "Docs/LevelDesign/Blockout_v02/LayoutSpec_working.json").exists():
    DEFAULT_LAYOUT = ROOT / "Docs/LevelDesign/Blockout_v02/LayoutSpec_working.json"
DEFAULT_OUT = ROOT / "ArtSource/BlockoutV02"
EPS = 1e-8


def add(a, b):
    return tuple(x+y for x,y in zip(a,b))


def sub(a, b):
    return tuple(x-y for x,y in zip(a,b))


def mul(a, k):
    return tuple(x*k for x in a)


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def area2(points):
    return sum(a[0]*b[1]-a[1]*b[0]
               for a,b in zip(points,points[1:]+points[:1]))


def ccw(points):
    return list(points) if area2(points)>0 else list(reversed(points))


def cross2(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def inside_triangle(p,a,b,c):
    return min(cross2(a,b,p),cross2(b,c,p),cross2(c,a,p)) >= -EPS


def ear_clip(points):
    """Triangulate simple CCW concave outlines without filling B's notch."""
    if area2(points)<0:
        raise ValueError("ear_clip requires a CCW outline")
    todo=list(range(len(points)))
    triangles=[]
    while len(todo)>3:
        found=False
        for j,k in enumerate(todo):
            p,n=todo[j-1],todo[(j+1)%len(todo)]
            if cross2(points[p],points[k],points[n])<=EPS:
                continue
            if any(inside_triangle(points[t],points[p],points[k],points[n])
                   for t in todo if t not in (p,k,n)):
                continue
            triangles.append((p,k,n));todo.pop(j);found=True;break
        if not found:
            raise ValueError("Non-simple outline or degenerate cap")
    triangles.append(tuple(todo))
    return triangles


def convex_hull(points):
    points=sorted(set((round(p[0],5),round(p[1],5)) for p in points))
    if len(points)<3:return points
    lower=[]
    for p in points:
        while len(lower)>=2 and cross2(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(points):
        while len(upper)>=2 and cross2(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def mesh_from_rings(name,rings,cap_coordinates):
    n=len(rings[0]);vertices=[p for ring in rings for p in ring]
    if any(len(r)!=n for r in rings):raise ValueError("Ring vertex count mismatch")
    triangles=[]
    for j in range(len(rings)-1):
        for i in range(n):
            k=(i+1)%n
            a,b,c,d=j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i
            # Alternate long planar diagonals; avoid a conspicuous spiral seam.
            if (i+j)%2:
                triangles.extend(((a,d,b),(b,d,c)))
            else:
                triangles.extend(((a,c,b),(a,d,c)))
    for ids,offset,reverse in ((cap_coordinates[0],0,False),
                               (cap_coordinates[1],(len(rings)-1)*n,True)):
        signed=area2(ids)
        cap=ear_clip(ids if signed>0 else list(reversed(ids)))
        mapping=list(range(n)) if signed>0 else list(reversed(range(n)))
        for t in cap:
            tri=tuple(offset+mapping[i] for i in t)
            # Preserve index-order boundary orientation even when the cap's
            # 2-D coordinates were clockwise (ridge cross sections are CW).
            triangles.append(tuple(reversed(tri)) if reverse != (signed<0) else tri)
    volume=sum(dot(vertices[a],cross(vertices[b],vertices[c]))
               for a,b,c in triangles)/6
    if volume<0:triangles=[(c,b,a) for a,b,c in triangles]
    return {"name":name,"vertices":vertices,"triangles":triangles}


def clip_b_cut(x,y,z):
    """The mirrored B southwest sight corridor is never refilled above 20m.

    Floor notch: x < -15, 116 <= y < 138. Upper support west limit is -14.
    Keep a wider two-metre shoulder margin around that original cut.
    """
    if z>20.0 and y<140 and x<-12:
        x=-12
    return x,y,z


def mountain(name,center,outline,top_z,bottom_z,seed,b_cut=False):
    outline=ccw(outline)
    cx,cy=center
    fractions=(0,.10,.28,.53,.77,1)
    scales=(1,1.0,1.13,1.21,1.13,.92)
    rings=[]
    for layer,(fraction,scale) in enumerate(zip(fractions,scales)):
        z=top_z+(bottom_z-top_z)*fraction
        ring=[]
        for i,(ox,oy) in enumerate(outline):
            angle=math.atan2(oy,ox)
            # Coherent broad buttresses; no per-vertex random/high-frequency noise.
            low=.09*math.sin(3*angle+seed+layer*.65)+.045*math.cos(2*angle-seed*.7)
            # Upper lip stays fixed; only mid/lower buttresses move. Distinct
            # broad ribs and tilted strata replace the previous barrel surface.
            drift_x=(0 if layer<=1 else 4.2*math.sin(layer*.9+seed))
            drift_y=(0 if layer<=1 else 3.4*math.cos(layer*.8+seed))
            radial=1 if layer<=1 else 1+low*math.sin(math.pi*fraction)
            x=cx+ox*scale*radial+drift_x
            y=cy+oy*scale*radial+drift_y
            zz=z+(0 if layer<=1 else .037*(top_z-bottom_z)*
                  math.sin(2*angle+seed+layer*.55)*math.sin(math.pi*fraction))
            # B keeps identical notched upper rings down to the old lower cap.
            if b_cut and z>20:
                x,y,zz=cx+ox,cy+oy,z
            if b_cut:x,y,zz=clip_b_cut(x,y,zz)
            ring.append((x,y,zz))
        rings.append(ring)
    coords=[[(p[0],p[1]) for p in rings[0]],
            [(p[0],p[1]) for p in rings[-1]]]
    mesh=mesh_from_rings(name,rings,coords)
    mesh["top_outline_m"]=[[p[0],p[1]] for p in rings[0]]
    mesh["footprint_m"]=convex_hull(mesh["vertices"])
    mesh["top_z_m"]=top_z
    return mesh


def sample_chain(points,spacing=9.0):
    out=[tuple(points[0])]
    for a,b in zip(points,points[1:]):
        run=math.hypot(b[0]-a[0],b[1]-a[1])
        if run<EPS:continue
        count=max(1,math.ceil(run/spacing))
        for i in range(1,count+1):
            t=i/count
            out.append(tuple(a[k]+(b[k]-a[k])*t for k in range(3)))
    return out


def support_caps(layout):
    """Exactly reproduce old Backbone cylinder XY/top envelopes from builder."""
    caps=[]
    for s in layout["stairs"]:
        a,b=s["a"],s["b"]
        run=math.hypot(b[0]-a[0],b[1]-a[1])
        n=max(1,int(run/15))
        for i in range(n):
            t=(i+.5)/n
            caps.append((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,
                         a[2]+(b[2]-a[2])*t-7,9))
    # Under landing/crag shoulders, top caps remain 2.5m below the walking plane.
    for r in layout.get("rests",[]):
        x,y,z=r["center"]
        caps.append((x,y,z-2.5,max(r["size"])*.6))
    for p in layout["platforms"]:
        x,y,z=p["center"]
        radius=p.get("radius",{ "A_Shanmen":28,"B_MartialCourt":29,
                               "C_AlchemyCourt":31}.get(p["name"],9))
        caps.append((x,y,z-(7.5 if p["name"].startswith("B_") else 3),radius))
    return caps


def ridge(layout):
    chain=[]
    for s in layout["stairs"]:
        a,b=tuple(s["a"]),tuple(s["b"])
        if not chain:chain.append(a)
        elif math.dist(chain[-1],a)>EPS:chain.append(a)
        chain.append(b)
    points=sample_chain(chain,9)
    caps=support_caps(layout)
    rings=[];local_profiles=[];outer_left=[];outer_right=[]
    distance=0
    for i,p in enumerate(points):
        before=points[max(0,i-1)];after=points[min(len(points)-1,i+1)]
        dx,dy=after[0]-before[0],after[1]-before[1]
        length=math.hypot(dx,dy)
        nx,ny=-dy/length,dx/length
        if i:distance+=math.dist(p,points[i-1])
        wave=1+.27*math.sin(distance/31+.6)+.13*math.sin(distance/57-.7)
        left_wave=1+.22*math.sin(distance/37+1.8)+.11*math.sin(distance/73)
        lower_drift=4.1*math.sin(distance/29+.4)+2.2*math.sin(distance/67)
        top=p[2]-7.25
        base=-70-5*math.sin(distance/180)
        height=top-base
        right_z0=top-height*(.25+.015*math.sin(distance/43))
        right_z1=top-height*(.44+.035*math.sin(distance/31+.9))
        right_z2=top-height*(.69+.04*math.sin(distance/39+1.4))
        left_z0=top-height*(.255+.015*math.sin(distance/47+1.2))
        left_z1=top-height*(.45+.035*math.sin(distance/35+2.1))
        left_z2=top-height*(.70+.04*math.sin(distance/41+.3))
        profile=[(-2.15,top-.5),(2.15,top-.5),
                 (6.5,top-min(8,height*.12)),
                 (8.0*wave+lower_drift*.18,right_z0),
                 (9.7*wave+lower_drift*.55,right_z1),
                 (13.5*wave+lower_drift,right_z2),
                 (15.2*wave+lower_drift,base+9),
                 (10.0*wave+lower_drift,base),
                 (-9.5*left_wave+lower_drift,base),
                 (-15.0*left_wave+lower_drift,base+11),
                 (-12.4*left_wave+lower_drift,left_z2),
                 (-9.2*left_wave+lower_drift*.45,left_z1),
                 (-8.0*left_wave+lower_drift*.16,left_z0),
                 (-6.4,top-min(8.5,height*.125))]
        ring=[];local=[]
        for j,(lateral,z) in enumerate(profile):
            x,y=p[0]+nx*lateral,p[1]+ny*lateral
            if j in (0,1):
                available=[cap_z for cx,cy,cap_z,r in caps
                           if (x-cx)**2+(y-cy)**2<=r*r]
                if available:z=min(z,max(available)-.35)
                # On long stair joins a gap gets a lower saddle, never a new hump.
                else:z-=3.0
            x,y,z=clip_b_cut(x,y,z)
            ring.append((x,y,z));local.append((lateral,z))
        rings.append(ring);local_profiles.append(local)
        left_i=min(range(len(profile)),key=lambda j:profile[j][0])
        right_i=max(range(len(profile)),key=lambda j:profile[j][0])
        outer_left.append([ring[left_i][0],ring[left_i][1]])
        outer_right.append([ring[right_i][0],ring[right_i][1]])
    mesh=mesh_from_rings("Ridge",rings,[local_profiles[0],local_profiles[-1]])
    mesh["top_outline_m"]=[[r[0][0],r[0][1]] for r in rings]+[
        [r[1][0],r[1][1]] for r in reversed(rings)]
    mesh["footprint_m"]=outer_left+list(reversed(outer_right))
    mesh["centreline_m"]=points
    mesh["top_clearance_m"]=7.25
    return mesh


def validate_mesh(mesh):
    vertices,triangles=mesh["vertices"],mesh["triangles"]
    edges=Counter();directions=Counter();bad=[]
    for i,t in enumerate(triangles):
        if len(set(t))!=3 or any(k<0 or k>=len(vertices) for k in t):
            bad.append(i);continue
        normal=cross(sub(vertices[t[1]],vertices[t[0]]),
                     sub(vertices[t[2]],vertices[t[0]]))
        if dot(normal,normal)<1e-12:bad.append(i)
        for a,b in zip(t,t[1:]+t[:1]):
            key=tuple(sorted((a,b)))
            edges[key]+=1;directions[key]+=1 if a<b else -1
    nonmanifold=[e for e,n in edges.items() if n!=2]
    inconsistent=[e for e,n in directions.items() if n!=0]
    volume=sum(dot(vertices[a],cross(vertices[b],vertices[c]))
               for a,b,c in triangles)/6
    result={"vertices":len(vertices),"triangles":len(triangles),
            "degenerate_triangles":len(bad),"nonmanifold_edges":len(nonmanifold),
            "inconsistent_winding_edges":len(inconsistent),
            "signed_volume_m3":round(volume,3)}
    if bad or nonmanifold or inconsistent or volume<=0:
        raise ValueError(f"Invalid terrain mesh {mesh['name']}: {result}")
    return result


def bounds(vertices):
    return [[min(p[i] for p in vertices) for i in range(3)],
            [max(p[i] for p in vertices) for i in range(3)]]


def clip_polygon_3d(poly,axis,limit,keep_less=True):
    if not poly:return []
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        va=(a[axis]-limit)*(1 if keep_less else -1)
        vb=(b[axis]-limit)*(1 if keep_less else -1)
        ia,ib=va<=-1e-7,vb<=-1e-7
        if ia:out.append(a)
        if ia!=ib:
            t=va/(va-vb)
            out.append(tuple(a[k]+(b[k]-a[k])*t for k in range(3)))
    return out


def ray_box(a,b,box):
    lo,hi=0.0,1.0
    for k in range(3):
        d=b[k]-a[k]
        if abs(d)<1e-12:
            if a[k]<box[0][k] or a[k]>box[1][k]:return False
        else:
            p,q=(box[0][k]-a[k])/d,(box[1][k]-a[k])/d
            if p>q:p,q=q,p
            lo,hi=max(lo,p),min(hi,q)
            if lo>hi:return False
    return True


def ray_triangle(a,b,tri):
    p0,p1,p2=tri
    direction=sub(b,a);e1=sub(p1,p0);e2=sub(p2,p0)
    h=cross(direction,e2);det=dot(e1,h)
    if abs(det)<1e-10:return None
    inv=1/det;s=sub(a,p0);u=inv*dot(s,h)
    if u<0 or u>1:return None
    q=cross(s,e1);v=inv*dot(direction,q)
    if v<0 or u+v>1:return None
    t=inv*dot(e2,q)
    return t if 1e-7<t<1-1e-7 else None


def make_bvh(items):
    box=bounds([p for _,tri in items for p in tri])
    if len(items)<=10:return {"box":box,"items":items}
    axis=max(range(3),key=lambda k:box[1][k]-box[0][k])
    items=sorted(items,key=lambda item:sum(p[axis] for p in item[1])/3)
    half=len(items)//2
    return {"box":box,"children":(make_bvh(items[:half]),make_bvh(items[half:]))}


def bvh_hit(tree,a,b):
    if not ray_box(a,b,tree["box"]):return None
    if "items" in tree:
        hits=[(t,name) for name,tri in tree["items"]
              if (t:=ray_triangle(a,b,tri)) is not None]
    else:
        hits=[hit for child in tree["children"]
              if (hit:=bvh_hit(child,a,b)) is not None]
    return min(hits) if hits else None


def source_audit(meshes,layout):
    """Terrain triangles only; never substitute for floor/rail/UE-world traces."""
    items=[(m["name"],tuple(m["vertices"][i] for i in tri))
           for m in meshes for tri in m["triangles"]]
    tree=make_bvh(items)
    d=next(p for p in layout["platforms"] if p["name"].startswith("D_"))
    dx,dy,dz=d["center"];radius=d.get("radius",30)
    rim=[(dx+x,dy-math.sqrt(radius*radius-x*x),dz+.25)
         for x in (-24,-18,-12,-6,0,6,12,18,24)]
    crown=(dx,dy+10,158)
    def check(points):
        states=rim_bad=crown_bad=0;examples=[]
        for p in points:
            if p[2]>=131.5:continue
            for height in (1.1,1.7):
                for ipd in (-.032,.032):
                    states+=1;eye=add(p,(ipd,0,height))
                    hits=[bvh_hit(tree,eye,target) for target in rim]
                    rim_ok=any(a is None and b is None for a,b in zip(hits,hits[1:]))
                    crown_hit=bvh_hit(tree,eye,crown)
                    rim_bad+=not rim_ok;crown_bad+=crown_hit is not None
                    if (not rim_ok or crown_hit) and len(examples)<8:
                        examples.append({"foot_m":p,"eye_height_m":height,
                                         "ipd_offset_m":ipd,"rim_segment_visible":rim_ok,
                                         "rim_blockers":[h[1] if h else None for h in hits],
                                         "crown_blocker":crown_hit[1] if crown_hit else None})
        return {"eye_states":states,"rim_blocked_states":rim_bad,
                "crown_blocked_states":crown_bad,"examples":examples}
    nodes={str(n["index"]):check([n["ground"]]) for n in layout["nodes"]
           if n["index"]<7}
    route=[]
    for stair in layout["stairs"]:
        # <=1m 3D spacing along the canonical nominal stair plane.
        a,b=stair["a"],stair["b"]
        steps=max(1,math.ceil(math.dist(a,b)))
        route.extend(tuple(a[k]+(b[k]-a[k])*i/steps for k in range(3))
                     for i in range(steps+1))
    clearances=[];near_walk=[]
    for p in route+[tuple(n["ground"]) for n in layout["nodes"]]:
        hit=bvh_hit(tree,add(p,(0,0,10)),add(p,(0,0,-40)))
        if hit:
            clearance=p[2]-(p[2]+10-50*hit[0])
            clearances.append(clearance)
            if clearance<.3 and len(near_walk)<12:
                near_walk.append({"foot_m":p,"mesh":hit[1],
                                  "terrain_below_foot_m":round(clearance,4)})
    corridor_intrusions=[]
    for name,tri in items:
        if name not in ("B","Ridge"):continue
        poly=clip_polygon_3d(list(tri),0,-14,True)
        poly=clip_polygon_3d(poly,1,138,True)
        poly=clip_polygon_3d(poly,2,20.5,False)
        if len(poly)>=3:
            area=sum(math.sqrt(dot(n:=cross(sub(poly[i],poly[0]),
                                            sub(poly[i+1],poly[0])),n))/2
                     for i in range(1,len(poly)-1))
            if area>1e-5:corridor_intrusions.append({"mesh":name,"area_m2":area})
    return {"scope":"Source terrain triangles only; floors, rails, buildings, vegetation and UE collision excluded",
            "rim_rule":"At least two adjacent points of 9 on true near rim are visible",
            "B_cut_prism":{"x_max":-14,"y_max":138,"z_min":20.5,
                            "intruding_triangles":len(corridor_intrusions)},
            "nodes":nodes,"stair_paths_1m":check(route),
            "walk_surface_clearance":{"samples_with_hit":len(clearances),
                                      "minimum_m":round(min(clearances),4) if clearances else None,
                                      "under_0_3m_examples":near_walk}}


def write_mesh(mesh,out):
    name="TerrainV02_"+mesh["name"]
    vertices=[[round(x,6) for x in p] for p in mesh["vertices"]]
    triangles=[list(t) for t in mesh["triangles"]]
    payload={"name":name,"units":"metres","coordinate_system":"UE world XYZ, Z up; already mirrored X",
             "actor_location_m":[0,0,0],"actor_scale":[1,1,1],
             "vertices":vertices,"triangles":triangles,
             "bounds_m":bounds(vertices),"validation":validate_mesh(mesh)}
    digest=hashlib.sha256(json.dumps([vertices,triangles],separators=(",",":"))
                          .encode()).hexdigest()
    payload["content_sha256"]=digest
    source_path=out/(name+".mesh_source.json")
    source_path.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    obj=["# units: metres; UE XYZ Z-up; X is already mirrored",
         "# Spawn at world origin; ue_mesh_v02.make_asset converts metres to cm.",
         "o "+name,"s 1"]
    obj.extend("v %.6f %.6f %.6f"%tuple(v) for v in vertices)
    obj.extend("f %d %d %d"%tuple(i+1 for i in t) for t in triangles)
    obj_path=out/(name+".obj")
    obj_path.write_text("\n".join(obj)+"\n",encoding="utf-8")
    folder={"A":"01_Shanmen","B":"02_MartialCourt","C":"03_AlchemyCourt",
            "Ridge":"04_ContinuousAscent","D":"05_SummitSeal"}[mesh["name"]]
    return {k:payload[k] for k in ("name","units","actor_location_m","actor_scale",
                                  "bounds_m","validation","content_sha256")} | {
        "mesh_source_json":str(source_path.resolve()),"json_path":str(source_path.resolve()),
        "folder":folder,"group":mesh["name"],"obj":str(obj_path.resolve())}


def generate(layout_path=DEFAULT_LAYOUT,out=DEFAULT_OUT):
    layout=json.loads(Path(layout_path).read_text(encoding="utf-8"))
    d=next(p for p in layout["platforms"] if p["name"].startswith("D_"))
    if d["center"][0]>=0:
        raise ValueError("Expected the current mirrored-X layout; refusing a second mirror")
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    outlines={
        "A":[(-22,-18),(-26,-7),(-23,11),(-16,22),(-2,27),(15,23),
             (24,12),(25,-3),(18,-21),(3,-26),(-10,-24)],
        "B":[(26,-21),(-8,-21),(-12,-18),(-12,-1),(-24,1),(-27,6),
             (-26,20),(-12,22),(10,21),(26,16),(27,-2),(26,-12)],
        "C":[(-22,-19),(-29,-7),(-26,10),(-15,24),(3,29),(21,20),
             (28,4),(25,-13),(9,-28),(-6,-29)],
        "D":[(-23,-14),(-28,-2),(-23,16),(-9,27),(8,28),(22,20),
             (28,3),(22,-15),(8,-27),(-8,-27)],
    }
    config=(("A",(0,1),-3,-72,.7),("B",(0,140),25.5,-76,1.9),
            ("C",(0,300),69,-80,3.1),("D",tuple(d["center"][:2]),129,-85,4.3))
    meshes=[mountain(name,center,outlines[name],top,bottom,seed,name=="B")
            for name,center,top,bottom,seed in config]
    meshes.append(ridge(layout))
    entries=[write_mesh(m,out) for m in meshes]
    footprints={"units":"metres","coordinates":"actual mirrored UE world XY",
                "note":"Rock projection only; not walkable ground. Ridge is a swept outer envelope.",
                "meshes":[{"name":"TerrainV02_"+m["name"],
                           "points":[[round(x,4),round(y,4)] for x,y in m["footprint_m"]],
                           "top_points":[[round(x,4),round(y,4)] for x,y in m["top_outline_m"]],
                           "height_range":[round(entries[i]["bounds_m"][0][2],3),
                                           round(entries[i]["bounds_m"][1][2],3)]}
                          for i,m in enumerate(meshes)]}
    (out/"terrain_footprints.json").write_text(json.dumps(footprints,ensure_ascii=False,indent=2),encoding="utf-8")
    spec={"source_layout":str(Path(layout_path).resolve()),"units":"metres",
          "world_mirrored_x":True,"meshes":entries,
          "footprints_json":str((out/"terrain_footprints.json").resolve()),
          "preserved_constraints":[
              "All stairs, platform slabs, rails, node transforms and combat space stay unchanged.",
              "B's mirrored southwest cut remains open above Z20m; no transparency/collision tricks.",
              "Main rock tops are 2.5-3m below platforms; ridge crest is at least 7.25m below stair line.",
              "Broader lower flanks below shoulders replace repeated cylinders, not new playable terrain."],
          "import_recommendations":[
              "Use mesh_source JSON vertices/triangles with ue_mesh_v02.make_asset; vertices are metres.",
              "Actor transform is location(0,0,0), rotation(0,0,0), scale(1,1,1); do not mirror again.",
              "Use a new asset name including content_sha256[:8] to avoid make_asset returning stale assets.",
              "Keep complex query collision and Visibility blocking; terrain must not use NoCollision to pass sight tests.",
              "Keep the existing platform/stair collision. These cliffs are visual/support mass, not navigation surfaces.",
              "Keep Nanite off for this whitebox; use one matte opaque cliff material per mesh.",
              "After import rerun Editor-world floor and line traces; these source checks do not certify UE collision."]}
    audit=source_audit(meshes,layout)
    validation_path=out/"TerrainV02_validation.json"
    validation_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    spec["source_validation_json"]=str(validation_path.resolve())
    spec["source_validation_summary"]={"B_cut_intrusions":audit["B_cut_prism"]["intruding_triangles"],
                                       "node_rim_blocked_states":sum(n["rim_blocked_states"] for n in audit["nodes"].values()),
                                       "node_crown_blocked_states":sum(n["crown_blocked_states"] for n in audit["nodes"].values())}
    (out/"TerrainV02_spec.json").write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding="utf-8")
    return spec


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout","--source",dest="layout",type=Path,default=DEFAULT_LAYOUT)
    parser.add_argument("--out",type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    spec=generate(args.layout,args.out)
    print(json.dumps({"meshes":[{"name":m["name"],**m["validation"]}
                                for m in spec["meshes"]],
                      "spec":str((args.out/"TerrainV02_spec.json").resolve())},indent=2))


if __name__=="__main__":main()
