"""Apply the supplied rig and a coherent animation set to saved sword archetypes."""
import unreal,json,hashlib,shutil
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/SlashRevision1104'
A=unreal.EditorAssetLibrary
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
imports=json.loads((O/'NativeClipsImport.json').read_text())
meta=json.loads((O/'NativeSlashManifest.json').read_text())
grip=json.loads((O/'NativeSwordGrip.json').read_text())['unreal']
mesh=A.load_asset(imports['mesh']);assert mesh
clips={kind:A.load_asset(row['asset']) for kind,row in imports['clips'].items()}
assert all(k in clips for k in ('attack','idle','walk','hit','death','cast'))
assert all(a.get_editor_property('skeleton')==mesh.skeleton for a in clips.values())
transform=unreal.Transform(location=unreal.Vector(*grip['translation']),scale=unreal.Vector(*grip['scale']))
transform.rotation=unreal.Quat(*grip['quaternion_xyzw'])
rows=[]
for key,factor in (('sword',1.),('GM01',1.2),('GM04',1.2),('boss',1.2)):
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    file=P/'Content'/(path.removeprefix('/Game/')+'.uasset')
    backup=O/'Backups'/'Content'/file.relative_to(P/'Content')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(file,backup)
    bp=A.load_asset(path);default=unreal.get_default_object(A.load_blueprint_class(path))
    component=default.get_component_by_class(unreal.SkeletalMeshComponent)
    before={'mesh':str(default.enemy_skeletal_mesh),'attack':str(default.attack_animation),
     'mesh_rotation':str(component.get_editor_property('relative_rotation')),'grip':str(default.sword_grip_transform)}
    default.set_editor_property('enemy_skeletal_mesh',mesh)
    component.set_skeletal_mesh_asset(mesh)
    component.set_editor_property('relative_rotation',unreal.Rotator())
    component.set_editor_property('relative_scale3d',unreal.Vector(1,1,1))
    component.set_editor_property('override_materials',[])
    default.set_editor_property('sword_attach_bone',grip['bone'])
    default.set_editor_property('sword_grip_transform',transform)
    default.set_editor_property('grip_morph_name','None')
    default.set_editor_property('grip_morph_weight',0.)
    for prop,kind in (('attack_animation','attack'),('idle_animation','idle'),('walk_animation','walk'),
                      ('hit_reaction_animation','hit'),('death_animation','death'),('cast_animation','cast')):
        default.set_editor_property(prop,clips[kind])
    # Measured from the original walk's grounded toe velocity (median of both feet).
    # At the existing 310 cm/s pursuit speed this plays the cycle at about 1.53x.
    default.set_editor_property('walk_animation_speed',202.38429)
    start,end=meta['notify'];brain=default.get_enemy_brain()
    for prop,value in zip(('telegraph_seconds','attack_seconds','recover_seconds'),
                          (start*factor,(end-start)*factor,(meta['duration']-end)*factor)):
        brain.set_editor_property(prop,value)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    check=unreal.get_default_object(A.load_blueprint_class(path))
    assert check.enemy_skeletal_mesh==mesh and check.attack_animation==clips['attack']
    assert str(check.sword_attach_bone)==grip['bone']
    assert A.save_loaded_asset(bp,False)
    rows.append({'enemy':key,'before':before,'mesh':mesh.get_path_name(),
      'attack':clips['attack'].get_path_name(),'socket':str(check.sword_attach_bone),
      'full_attack_seconds':meta['duration']*factor,'saved_sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
(O/'NativeEnemiesApplied.json').write_text(json.dumps({'state':'passed','mesh':mesh.get_path_name(),
 'skeleton':mesh.skeleton.get_path_name(),'clips':imports['clips'],'grip':grip,'enemies':rows},indent=2),encoding='utf-8')
unreal.log('NATIVE_ENEMIES_V07_APPLIED')
