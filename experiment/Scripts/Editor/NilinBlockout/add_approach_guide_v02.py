import unreal,json,os,math
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v02'
def main():
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);spec=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'))
    for actor in sub.get_all_level_actors():
        if actor.actor_has_tag('NLBlockout.ApproachGuide'):sub.destroy_actor(actor)
    flight=next(s for s in spec['stairs'] if s['name']=='Node06_to_Upper');a,b=flight['a'],flight['b'];run=math.hypot(b[0]-a[0],b[1]-a[1]);u=((b[0]-a[0])/run,(b[1]-a[1])/run);n=(-u[1],u[0])
    approach=[a[0]-4*u[0],a[1]-4*u[1],a[2]];spec['route_approaches']={'6':approach}
    node=next(n['ground'] for n in spec['nodes'] if n['index']==6)
    tip=[a[0]-.7*u[0],a[1]-.7*u[1],a[2]]
    segments=[(node,approach),(approach,tip)]
    for side in (-1,1):segments.append((tip,[tip[0]-u[0]*.8+n[0]*side*.4,tip[1]-u[1]*.8+n[1]*side*.4,tip[2]]))
    vec=lambda p:unreal.Vector(*[v*100 for v in p]);cube=unreal.load_asset('/Engine/BasicShapes/Cube');mat=unreal.load_asset('/Game/ReversedScale/Blockout/V06/Materials/M_Accent')
    for i,(p,q) in enumerate(segments):
        p=[p[0],p[1],p[2]+.025];q=[q[0],q[1],q[2]+.025];mid=[(p[j]+q[j])/2 for j in range(3)]
        actor=sub.spawn_actor_from_class(unreal.StaticMeshActor,vec(mid),unreal.MathLibrary.find_look_at_rotation(vec(p),vec(q)))
        actor.set_actor_label('NB_ApproachGuide_06_%02d'%i);actor.set_folder_path('Nilin_V07/04_ContinuousAscent');actor.set_editor_property('tags',[unreal.Name('NLBlockout.ApproachGuide'),unreal.Name('NLBlockoutV06')])
        c=actor.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(cube);c.set_material(0,mat);c.set_collision_profile_name('NoCollision');c.set_mobility(unreal.ComponentMobility.STATIC)
        actor.set_actor_scale3d(unreal.Vector(math.dist(p,q),.08,.012))
    json.dump(spec,open(os.path.join(OUT,'LayoutSpec.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():raise RuntimeError('Approach guide save failed')
main()
