"""Read back saved staging, static architecture sightlines and actual floor queries."""
import unreal,json,os,math,datetime
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v04'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV09'
def main():
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Expected V08')
    world=editor.get_editor_world();spec=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'));p=spec['pressure']
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    def v(q):return unreal.Vector(*[t*100 for t in q])
    def trace(a,b):
        hit=unreal.SystemLibrary.line_trace_single(world,v(a),v(b),unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
        if not hit:return None
        t=hit.to_tuple();z=t[5];actor=t[9]
        return {'actor':actor.get_actor_label() if actor else None,'point':[z.x/100,z.y/100,z.z/100]}
    floor_fail=[];samples=0;enemy_tags=[];capsules=[]
    for e in p['enemies']:
        matches=[a for a in actors if a.actor_has_tag('NLPressure.Enemy.'+e['id'])]
        pos=matches[0].get_actor_location() if len(matches)==1 else None
        ok=pos is not None and math.dist([pos.x/100,pos.y/100,pos.z/100],e['foot'])<.001
        enemy_tags.append({'id':e['id'],'unique_actual_position_matches':ok})
        x,y,z=e['foot'];hit=trace((x,y,z+.4),(x,y,z-.4));samples+=1
        if not hit or abs(hit['point'][2]-z)>.03:floor_fail.append({'enemy':e['id'],'hit':hit})
    for s in p['stairs']:
        for q in s['steps']:
            for f in (-.4,0,.4):
                x,y,z=q;x+=s['width']*f;hit=trace((x,y,z+.4),(x,y,z-.4));samples+=1
                if not hit or abs(hit['point'][2]-z)>.03:floor_fail.append({'stair':s['name'],'p':[x,y,z],'hit':hit})
        q=(s['x'],(s['end_y']+s['landing_end_y'])/2,s['top'])
        # Landing capsule is 30 cm radius, 90 cm half-height, exactly the real
        # desktop Character dimensions. Floor is 3 cm below the capsule base.
        c=(q[0],q[1],q[2]+.93)
        hit=unreal.SystemLibrary.capsule_trace_single(world,v(c),v((c[0],c[1],c[2]+.01)),30,90,unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
        capsules.append({'stair':s['name'],'landing_m':q,'clear':hit is None,'blocker':hit.to_tuple()[9].get_actor_label() if hit and hit.to_tuple()[9] else None})
    views=[]
    for eye in (1.1,1.62):
        origin=(0,126,28+eye);enemies=[]
        for e in p['enemies']:
            x,y,z=e['foot'];head=(x,y,z+1.64);chest=(x,y,z+1.18)
            hh=trace(origin,head);ch=trace(origin,chest)
            enemies.append({'id':e['id'],'rank':e['rank'],'head_architecture_clear':hh is None,'chest_architecture_clear':ch is None,'head_blocker':hh,'chest_blocker':ch})
        views.append({'eye_height_m':eye,'count':len(enemies),'heads_clear':sum(e['head_architecture_clear'] for e in enemies),'chests_clear':sum(e['chest_architecture_clear'] for e in enemies),'enemies':enemies})
    # The entire R14 combat disk, including seated capsule height, remains flat.
    disk_fail=[];disk_samples=0
    for radius in (0,3,6,9,12,13.7):
        for i in range(1 if not radius else 36):
            a=i*2*math.pi/36;x=radius*math.cos(a);y=140+radius*math.sin(a);z=28
            hit=trace((x,y,z+.3),(x,y,z-.3));disk_samples+=1
            if not hit or abs(hit['point'][2]-z)>.06:disk_fail.append({'p':[x,y,z],'hit':hit})
    report={'map':MAP,'checked_at':datetime.datetime.now().isoformat(),'source':'Actual UE editor collision/read-back. Enemy HISM are deliberately NoCollision. This head/chest test measures architecture occlusion only; rendered images assess silhouette overlap.','display_enemy_count':len(enemy_tags),'enemy_markers':enemy_tags,'floor_samples':samples,'floor_failures':floor_fail,'landing_capsules':capsules,'entry_sightlines':views,'combat_disk_floor_samples':disk_samples,'combat_disk_failures':disk_fail}
    report['success']=all(e['unique_actual_position_matches'] for e in enemy_tags) and not floor_fail and not disk_fail and all(c['clear'] for c in capsules) and all(v['heads_clear']==len(enemy_tags) for v in views)
    json.dump(report,open(os.path.join(OUT,'PressureAudit.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.log('NILIN_PRESSURE_AUDIT '+str(report['success']))
main()
