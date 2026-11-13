"""Read-only geometry audit: execute geometry-only AST with in-memory primitive stubs.

Does not import unreal, open UE, execute the builder main, or write map/assets.
Only this directory's MathCheck.json is written. Not a substitute for collision playtests.
"""
from pathlib import Path
import ast, math, json, types, hashlib

ROOT=Path(r'D:/game design/experiment')
SOURCE=ROOT/'Scripts/Editor/NilinBlockout/build_blockout.py'
OUT=Path(__file__).resolve().parent
source_text=SOURCE.read_text(encoding='utf-8-sig')
tree=ast.parse(source_text)
records=[]
spec={'nodes':[],'route':[],'platforms':[],'stairs':[]}
def shape(name,p,size,mat='Stone',kind='Cube',rot=None,collision=True):
    records.append({'name':name,'p':tuple(p),'size':tuple(size),'mat':mat,'kind':kind,
                    'rot':rot or {},'collision':collision})
def cube(name,p,size,mat='Stone',yaw=0,collision=True,rot=None):
    shape(name,p,size,mat,rot=rot or {'yaw':yaw},collision=collision)
def cyl(name,p,r,h,mat='Stone',collision=True,rot=None):
    shape(name,p,(r*2,r*2,h),mat,'Cylinder',rot,collision)
def sphere(name,p,size,mat='Stone',collision=True):
    shape(name,p,size,mat,'Sphere',collision=collision)
def beam(name,a,b,width,depth=None,mat='Wood',collision=True):
    d=tuple(b[i]-a[i] for i in range(3)); length=math.sqrt(sum(t*t for t in d))
    shape(name,tuple((a[i]+b[i])/2 for i in range(3)),(length,width,depth or width),mat,
          rot={'yaw':math.degrees(math.atan2(d[1],d[0])),
               'pitch':math.degrees(math.atan2(d[2],math.hypot(d[0],d[1])))},collision=collision)
def node(n,p,yaw=90): spec['nodes'].append({'index':n,'ground':tuple(p),'yaw':yaw})
ns=dict(math=math,spec=spec,cube=cube,cyl=cyl,sphere=sphere,shape=shape,beam=beam,node=node,rail_posts=set(),
        unreal=types.SimpleNamespace(Rotator=lambda **kwargs:kwargs))
names={'add','mul','ring','rail','platform','crag','stairs','rest','roof','pavilion','flag','lantern','dummy'}
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),ns)
main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
geometry=[]; active=False
for statement in main.body:
    if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='group' for t in statement.targets):
        value=ast.literal_eval(statement.value)
        if value=='01_Shanmen': active=True
        elif value=='07_ReviewCameras': break
    if active:
        if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ps' for t in statement.targets):
            continue
        geometry.append(statement)
for statement in main.body:
    if isinstance(statement,ast.For) and any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
        and n.func.id=='sphere' and n.args and isinstance(n.args[0],ast.Constant)
        and n.args[0].value=='CloudSea' for n in ast.walk(statement)):
        geometry.insert(0,statement)
exec(compile(ast.Module(body=geometry,type_ignores=[]),str(SOURCE),'exec'),ns)

def footprint_contains(record,p):
    if abs(record['rot'].get('pitch',0))>1e-6 or abs(record['rot'].get('roll',0))>1e-6:
        return False
    dx,dy=p[0]-record['p'][0],p[1]-record['p'][1]
    theta=math.radians(-record['rot'].get('yaw',0))
    xx=dx*math.cos(theta)-dy*math.sin(theta)
    yy=dx*math.sin(theta)+dy*math.cos(theta)
    if record['kind']=='Cylinder':
        return (xx/(record['size'][0]/2))**2+(yy/(record['size'][1]/2))**2<=1.00001
    return abs(xx)<=record['size'][0]/2+.001 and abs(yy)<=record['size'][1]/2+.001
supports=[]
for item in spec['nodes']:
    p=item['ground']
    matches=[r['name'] for r in records if r['collision'] and r['mat'] in ('Floor','Landing')
             and r['kind'] in ('Cube','Cylinder') and footprint_contains(r,p)
             and abs(r['p'][2]+r['size'][2]/2-p[2])<.02]
    supports.append({'node':item['index'],'ground_m':p,'support_primitives':matches,'supported':bool(matches)})

stairs_report=[]
stairs_ast=next(n for n in functions if n.name=='stairs')
spine_call=next(n for n in ast.walk(stairs_ast) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                and n.func.id=='beam' and any(isinstance(v,ast.Constant) and v.value=='_Spine' for v in ast.walk(n.args[0])))
spine_lowering=ast.literal_eval(spine_call.args[1].args[1])[2]
spine_depth=ast.literal_eval(spine_call.args[4])
landing_length=next(ast.literal_eval(n.value) for n in ast.walk(stairs_ast) if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='landing' for t in n.targets))
for row in spec['stairs']:
    a,b=row['a'],row['b']; run=math.hypot(b[0]-a[0],b[1]-a[1]); rise=b[2]-a[2]
    count=row['steps']; tread=row['tread']; landing=landing_length
    landing_every=ns['stairs'].__defaults__[-1]
    angle=math.atan2(rise,run)
    # Check the spine upper plane against tread centres, including rest platforms.
    spine_offset=spine_lowering+(spine_depth/2)/math.cos(angle)
    pos=0; clearances=[]; full_clearances=[]
    for i in range(count):
        z=a[2]+(i+1)*row['riser']; centre=pos+tread/2
        clearances.append(z-(a[2]+rise*centre/run+spine_offset))
        full_clearances += [z-(a[2]+rise*t/run+spine_offset) for t in (pos,pos+tread)]
        pos+=tread
        if (i+1)%landing_every==0 and i<count-1:
            centre=pos+landing/2
            clearances.append(z-(a[2]+rise*centre/run+spine_offset)); pos+=landing
            full_clearances += [z-(a[2]+rise*t/run+spine_offset) for t in (pos-landing,pos)]
    stairs_report.append(dict(name=row['name'],steps=count,landings=row['landings'],riser_m=row['riser'],
        tread_m=tread,run_m=run,slope_degrees=math.degrees(angle),run_error_m=pos-run,
        spine_below_tread_centres_min_m=min(clearances),
        spine_below_tread_edges_min_m=min(full_clearances),
        pass_riser=row['riser']<=.35,pass_tread=tread>=.30,
        pass_slope=math.degrees(angle)<=45))

clouds=[r for r in records if r['name']=='CloudSea']
furnace=next(r for r in records if r['name']=='GiantFurnaceBody')
floor_count=sum(r['collision'] and r['mat'] in ('Floor','Landing') for r in records)
report={'source':str(SOURCE),'source_sha256':hashlib.sha256(source_text.encode('utf-8')).hexdigest(),
    'method':'Pure Python AST geometry stubs; no UE, map IO, or playtests',
    'primitive_count_geometry_and_clouds':len(records),'blocking_primitives':sum(bool(r['collision']) for r in records),
    'floor_primitives':floor_count,'stairs':stairs_report,'node_supports':supports,
    'all_nodes_have_planar_support':all(x['supported'] for x in supports),
    'all_stair_dimensions_pass':all(x['pass_riser'] and x['pass_tread'] and x['pass_slope'] for x in stairs_report),
    'furnace':{'body_centre_m':furnace['p'],'front_extent_y_m':furnace['p'][1]-furnace['size'][1]/2,
               'back_extent_y_m':furnace['p'][1]+furnace['size'][1]/2,
               'friend_y_m':283,'node05_y_m':279,'combat_disk_y_extent_m':[277,305],
               'outside_combat_disk':furnace['p'][1]-furnace['size'][1]/2>305,
               'matches_v06':'Furnace after friend and clear defense gap, under high open pavilion'},
    'cloud_sheet_top_range_m':[min(r['p'][2]+r['size'][2]/2 for r in clouds),max(r['p'][2]+r['size'][2]/2 for r in clouds)],
    'limitations':['Point support check does not prove capsule reachability or floor collision in UE.',
                  'No ray tracing, camera exposure, cloud appearance, FPS, input or VR playtest performed.',
                  'Static mesh actor counts imply draw/physics overhead; measure in the actual map.']}
(OUT/'MathCheck.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'primitives':report['primitive_count_geometry_and_clouds'],
 'blocking':report['blocking_primitives'],'nodes_supported':report['all_nodes_have_planar_support'],
 'stairs_dimensions_pass':report['all_stair_dimensions_pass'],'stairs':stairs_report,
 'furnace':report['furnace'],'cloud_sheet_top_range_m':report['cloud_sheet_top_range_m']},ensure_ascii=False,indent=2))
