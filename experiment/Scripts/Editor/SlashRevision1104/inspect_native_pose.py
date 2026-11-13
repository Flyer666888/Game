import unreal,json
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/SlashRevision1104'
A=unreal.EditorAssetLibrary
mesh=A.load_asset('/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/SK_WuxiaMale_Native_v07')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
probe=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(0,0,0))
c=probe.skeletal_mesh_component;c.set_skeletal_mesh_asset(mesh)
def vec(v):return [v.x,v.y,v.z]
def tr(t):return {'p':vec(t.translation),'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],'s':vec(t.scale3d)}
data={'rest':{str(c.get_bone_name(i)):tr(c.get_socket_transform(c.get_bone_name(i),unreal.RelativeTransformSpace.RTS_COMPONENT)) for i in range(c.get_num_bones())},
 'attach_doc':c.attach_to_component.__doc__}
actors.destroy_actor(probe)
(O/'NativeUEReference.json').write_text(json.dumps(data,indent=2))
