"""Additive Chinese architectural blockout details for V09 (metres, no UE).

The existing gate, open alchemy court and roofless summit retain their distinct
silhouettes.  All additions have real collision.  ``build(api)`` emits only
through the supplied box/beam/part adapter, after checking the new geometry
against the six established approach views.
"""
import json
import math
from pathlib import Path

import mesh_shapes_v02 as shapes


ROOT = Path(__file__).resolve().parents[3]
LAYOUT = ROOT / 'Docs' / 'LevelDesign' / 'Blockout_v03' / 'LayoutSpec.json'


def _box_mesh(p, size):
    x, y, z = p
    a, b, c = (v / 2 for v in size)
    vertices = [(x + i*a, y + j*b, z + k*c)
                for i, j, k in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                                (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    triangles = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
                 (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    return vertices, triangles


def _combine(parts):
    vertices, triangles = [], []
    for vv, tt in parts:
        offset = len(vertices)
        vertices.extend(vv)
        triangles.extend(tuple(i + offset for i in tri) for tri in tt)
    return vertices, triangles


def _rect_lattice(p, width, height, plane='xz', pitch=1.0, bar=.13):
    """Solid joined bars: an open screen rather than an opaque wall plane."""
    x, y, z = p
    parts = []
    def add(u, v, w, h):
        center = (x+u,y,z+v) if plane == 'xz' else (x,y+u,z+v)
        size = (w,.18,h) if plane == 'xz' else (.18,w,h)
        parts.append(_box_mesh(center,size))
    for edge in (-1,1):
        add(edge*width/2,0,.22,height+.22)
        add(0,edge*height/2,width,.22)
    n = max(2,round(width/pitch))
    for i in range(1,n):
        add(-width/2+width*i/n,0,bar,height)
    for v in (-height*.23,height*.23):
        add(0,v,width,bar)
    return _combine(parts)


def _frustum(p, lower, upper, height):
    x,y,z=p
    v=[]
    for width,depth,dz in ((*lower,0),(*upper,height)):
        v.extend((x+sx*width/2,y+sy*depth/2,z+dz)
                 for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1)))
    t=[(0,2,1),(0,3,2),(4,5,6),(4,6,7)]
    for a,b in ((0,1),(1,2),(2,3),(3,0)):
        t.extend(((a,b,b+4),(a,b+4,a+4)))
    return v,t


def _sub(a,b): return tuple(x-y for x,y in zip(a,b))
def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def _segment_box(a,b,center,axes,half):
    lo,hi=0.,1.
    aa=_sub(a,center);d=_sub(b,a)
    for axis,h in zip(axes,half):
        start=_dot(aa,axis);delta=_dot(d,axis)
        if abs(delta)<1.e-9:
            if abs(start)>h:return False
        else:
            t0,t1=(-h-start)/delta,(h-start)/delta
            lo=max(lo,min(t0,t1));hi=min(hi,max(t0,t1))
            if lo>hi:return False
    return hi>1.e-6 and lo<1.-1.e-6


def _segment_triangle(a,b,v0,v1,v2):
    d=_sub(b,a);e1=_sub(v1,v0);e2=_sub(v2,v0)
    h=_cross(d,e2);det=_dot(e1,h)
    if abs(det)<1.e-9:return False
    inv=1./det;s=_sub(a,v0);u=_dot(s,h)*inv
    if u<0 or u>1:return False
    q=_cross(s,e1);v=_dot(d,q)*inv
    if v<0 or u+v>1:return False
    t=_dot(e2,q)*inv
    return 1.e-6<t<1.-1.e-6


def _hits(record,a,b):
    if record['kind']=='part':
        vv=record['vertices']
        return any(_segment_triangle(a,b,*(vv[i] for i in tri))
                   for tri in record['triangles'])
    if record['kind']=='box':
        angle=math.radians(record.get('yaw',0))
        axes=((math.cos(angle),math.sin(angle),0),
              (-math.sin(angle),math.cos(angle),0),(0,0,1))
        return _segment_box(a,b,record['p'],axes,[v/2 for v in record['size']])
    p,q=record['a'],record['b'];length=math.dist(p,q)
    axis=tuple(v/length for v in _sub(q,p))
    horizontal=math.hypot(axis[0],axis[1])
    side=(-axis[1]/horizontal,axis[0]/horizontal,0) if horizontal>1.e-9 else (0,1,0)
    up=_cross(axis,side)
    return _segment_box(a,b,tuple((x+y)/2 for x,y in zip(p,q)),
                        (axis,side,up),(length/2,record['width']/2,record['depth']/2))


def _check_sightlines(records):
    with LAYOUT.open(encoding='utf-8') as stream:
        layout=json.load(stream)
    peak=next(p for p in layout['platforms'] if p['name'].startswith('D_'))
    px,py,pz=peak['center'];radius=peak.get('radius',30)
    seal=next(p for p in layout['footprints'] if p['name']=='SealWall')
    targets=[(px+radius*t,py-math.sqrt(radius**2-(radius*t)**2),pz+.2)
             for t in (-.8,-.6,-.4,-.2,0,.2,.4,.6,.8)]
    crown=(px,seal['center'][1],pz+26)
    checks=[]
    for node in layout['nodes']:
        if node['index']>=7:continue
        for eye in (1.1,1.7):
            x,y,z=node['ground'];start=(x,y,z+eye)
            blockers=[[r['name'] for r in records if _hits(r,start,target)]
                      for target in targets+[crown]]
            checks.append({'node':node['index'],'eye_m':eye,
                           'new_rim_blockers':blockers[:-1],
                           'new_crown_blockers':blockers[-1]})
    # Existing physics is verified by the importing editor.  This is only an
    # additive preflight: no new architectural piece may cut any of these rays.
    if any(any(c['new_rim_blockers']) or c['new_crown_blockers'] for c in checks):
        raise RuntimeError('V09 architecture intersects a protected approach ray: '+json.dumps(checks))
    return checks


def build(api):
    records=[]
    section='A_Shanmen'
    def box(name,p,size,mat='Stone',collision=True,yaw=0):
        records.append(dict(kind='box',section=section,name=name,p=p,size=size,
                            mat=mat,collision=collision,yaw=yaw))
    def beam(name,a,b,width=.3,depth=None,mat='Wood',collision=True):
        records.append(dict(kind='beam',section=section,name=name,a=a,b=b,
                            width=width,depth=depth or width,mat=mat,collision=collision))
    def part(name,vertices,triangles,mat='Roof',collision=True):
        records.append(dict(kind='part',section=section,name=name,vertices=vertices,
                            triangles=triangles,mat=mat,collision=collision))

    # A: ceremonial gate.  Extra cross-beams articulate the broad dark fascia;
    # the main 20 m opening and the established column feet stay untouched.
    for y in (-6,1):
        box('Gate_Efang',(0,y,9.9),(24.2,.62,.65),'Wood')
        box('Gate_EfangUpperFillet',(0,y-.06,10.35),(24.7,.72,.16),'Trim')
        for side in (-1,1):
            beam('Gate_CornerBrace',(side*11.6,y,8.15),
                 (side*8.7,y,9.67),.34,.38,'Wood')
            box('Gate_BraceSeat',(side*11.6,y,8.15),(.85,.78,.28),'Trim')
    for x in (-12,12):
        box('Gate_LongitudinalEfang',(x,-2.5,9.9),(.62,7.0,.65),'Wood')
        for y,sgn in ((-6,1),(1,-1)):
            beam('Gate_SideBrace',(x,y,8.35),(x,y+sgn*1.9,9.65),.27,.33,'Wood')
    # Raised side screens recall the reference gate's timber enclosure.  Their
    # footprint is outside both main circulation and the combat disk.
    panels=[]
    for x in (-12.8,12.8):
        box('Gate_ScreenStoneSill',(x,-2.5,.7),(.65,5.5,1.4),'Stone')
        panels.append(_rect_lattice((x,-2.5,4.46),5.4,5.9,'yz',.85,.13))
    part('Gate_OpenSideLattice',*_combine(panels),'Wood')
    # Hanging trim occupies only the upper 1.1 m and has a broad empty middle.
    part('Gate_FrontGualuo',*_combine([
        _rect_lattice((x,-6.12,9.02),5.2,1.03,'xz',.86,.12)
        for x in (-7.85,7.85)]),'Trim')
    box('Gate_TabletBorderTop',(0,-3.6,11.68),(8.35,.20,.17),'Stone')
    box('Gate_TabletBorderBottom',(0,-3.6,10.32),(8.35,.20,.17),'Stone')
    for x in (-4.1,4.1):box('Gate_TabletBorderSide',(x,-3.6,11.0),(.17,.20,1.37),'Stone')

    section='B_MartialCourt'
    # Two quiet stone lamps outside the pressure terraces help frame the court
    # without competing with thirty elevated enemy silhouettes.
    for x in (-22.2,22.2):
        y=156.2
        box('Martial_StoneLampFoot',(x,y,28.16),(1.0,1.0,.32),'Stone')
        box('Martial_StoneLampStem',(x,y,28.85),(.36,.36,1.1),'Stone')
        box('Martial_StoneLampTray',(x,y,29.45),(.9,.9,.16),'Stone')
        box('Martial_StoneLampBody',(x,y,29.85),(.52,.52,.64),'Warm')
        box('Martial_StoneLampCrown',(x,y,30.23),(1.0,1.0,.20),'Stone')

    section='C_AlchemyCourt'
    # C: an open court with a lifted rear roof, not a second gate.  The upper
    # roof is wholly within the existing roof footprint and sits behind the
    # furnace axis, leaving the skyline/exit on negative X open.
    box('Alchemy_UpperRoofDrum',(0,318,87.55),(22,7,3.0),'Wood')
    box('Alchemy_UpperRoofBelt',(0,318,88.65),(22.6,7.6,.24),'Trim')
    vv,tt=shapes.roof(26,12,2.2,.24)
    vv=[(x,y+318,z+89.05) for x,y,z in vv]
    part('Alchemy_RearUpperHipRoof',vv,tt,'Roof')
    beam('Alchemy_UpperRidge',(-8.71,318,91.37),(8.71,318,91.37),.32,.32,'Trim')
    for side in (-1,1):
        box('Alchemy_UpperRidgeEnd',(side*8.75,318,91.68),(.38,.46,.6),'Trim')
        # Segment-like chiwen massing rather than tall identical spires.
        beam('Alchemy_UpperRidgeHook',(side*8.75,318,91.6),
             (side*9.2,318,91.97),.24,.25,'Stone')
    for y in (309.56,320.44):
        box('Alchemy_Efang',(0,y,83.45),(34.6,.72,.57),'Wood')
        box('Alchemy_EfangFineBand',(0,y-.05,83.84),(35,.8,.15),'Trim')
        for side in (-1,1):
            beam('Alchemy_ColumnBrace',(side*16.95,y,81.65),
                 (side*13.4,y,83.16),.30,.38,'Wood')
            box('Alchemy_BraceShoulder',(side*16.95,y,81.65),(.8,.8,.26),'Trim')
    for x in (-17.22,17.22):
        box('Alchemy_SideEfang',(x,315,83.45),(.62,11.1,.57),'Wood')
        for y,sgn in ((309.56,1),(320.44,-1)):
            beam('Alchemy_SideBrace',(x,y,81.8),(x,y+sgn*2.1,83.17),.28,.33,'Wood')
    # Short elevated panels: no ground-level wall, no lattice behind the
    # complete furnace silhouette, and no decorative screen across the exit.
    panels=[_rect_lattice((x,320.55,82.2),6.2,1.8,'xz',1.0,.13)
            for x in (-11.9,11.9)]
    panels.extend(_rect_lattice((x,315,82.45),6.1,1.22,'yz',1.0,.12)
                  for x in (-17.33,17.33))
    part('Alchemy_HighOpenGualuo',*_combine(panels),'Wood')
    # A narrow front strip gives a recognizable bay rhythm above the player.
    part('Alchemy_FrontGualuo',*_combine([
        _rect_lattice((x,309.45,82.65),5.5,.84,'xz',.9,.11)
        for x in (-11.9,11.9)]),'Trim')

    section='D_SummitSeal'
    # D stays roofless: shallow stone relief and tapered capitals reinforce
    # the two existing que towers without adding a temple at the summit.
    capitals=[]
    for x in (-155,-193):
        y=530.5
        capitals.append(_frustum((x,y,145.15),(3.9,3.9),(5.75,4.75),.78))
        capitals.append(_frustum((x,y,150.05),(4.5,3.8),(3.6,3.0),.54))
        box('Summit_QueTopAbacus',(x,y,150.72),(3.85,3.25,.26),'Stone')
        box('Summit_QueNeckBand',(x,y,144.93),(4.05,4.05,.22),'Stone')
        # Low-relief panel remains on the front face of the existing shaft.
        for z in (135.35,143.9):
            box('Summit_QueReliefRail',(x,y-1.94,z),(2.65,.16,.20),'Stone')
        for dx in (-1.23,1.23):
            box('Summit_QueReliefStile',(x+dx,y-1.94,139.63),(.16,.16,8.35),'Stone')
        for dz in (-.65,.65):
            beam('Summit_QueLozenge',(x-1.05,y-1.96,139.9),
                 (x,y-1.96,139.9+dz),.13,.15,'Trim')
            beam('Summit_QueLozenge',(x,y-1.96,139.9+dz),
                 (x+1.05,y-1.96,139.9),.13,.15,'Trim')
    part('Summit_StoneCapitalBevels',*_combine(capitals),'Stone')

    instance_count=len(records)
    meshes=sum(r['kind']=='part' for r in records)
    if instance_count>180 or meshes>12:
        raise RuntimeError('Architectural enrichment exceeds the agreed budget')
    sightlines=_check_sightlines(records)
    for record in records:
        payload={k:v for k,v in record.items() if k not in ('kind','section')}
        getattr(api,record['kind'])(**payload)
    counts={name:sum(r['section']==name for r in records)
            for name in ('A_Shanmen','B_MartialCourt','C_AlchemyCourt','D_SummitSeal')}
    return {
        'version':'V09 additive architecture',
        'instance_count':instance_count,'custom_meshes':meshes,
        'all_new_geometry_has_collision':all(r['collision'] for r in records),
        'section_counts':counts,
        'source_layout':str(LAYOUT),
        'protected_approach_preflight':sightlines,
        'notes':[
            'A: layered efang, corner braces, raised side lattice; central opening retained.',
            'B: two stone lamps outside pressure terraces; enemy ranks retained.',
            'C: rear-set 26 x 12 m upper hip roof and open hanging lattice; furnace and combat disk unchanged.',
            'D: tapered stone que capitals and shallow relief; summit remains roofless.',
            'Geometry preflight only; integration must still run actual UE collision and route checks.'
        ],
        'parts':[{'name':r['name'],'section':r['section'],'kind':r['kind']}
                 for r in records]
    }
