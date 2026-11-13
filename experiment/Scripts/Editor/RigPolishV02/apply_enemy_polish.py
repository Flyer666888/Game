"""Assign the visually reviewed mesh/death derivatives to current enemy defaults."""
import hashlib,json,shutil
from pathlib import Path
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
OUT=PROJECT/'Docs/Gameplay/RigPolish_v02'
A=unreal.EditorAssetLibrary
ROOT='/Game/ReversedScale/Characters/WuxiaMale'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
for name in ('ShoulderImport.json','ShoulderComparison.json','DeathComparison.json'):
    evidence=json.loads((OUT/name).read_text(encoding='utf-8'))
    assert evidence['state']=='passed',name
contacts=json.loads((PROJECT/'ArtSource/WuxiaMale/RigPolishV02/Death/RestrainedDeathRuntimeContacts.json').read_text(encoding='utf-8'))
assert contacts['state']=='passed','Compressed death skin did not pass contact validation'
mesh=A.load_asset(ROOT+'/SK_WuxiaMale_Shoulder_v02')
death=A.load_asset(ROOT+'/Animations/Wuxia_Death_Restrained_v02')
assert mesh and death
assert mesh.get_editor_property('skeleton')==death.get_editor_property('skeleton')
records=[]
for key in ('sword','talisman','rock_talisman','GM01','GM02','GM03','GM04','boss'):
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    source=PROJECT/'Content'/(path.removeprefix('/Game/')+'.uasset')
    backup=OUT/'Backups/Assets'/source.relative_to(PROJECT/'Content')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(source,backup)
    bp=A.load_asset(path);default=unreal.get_default_object(A.load_blueprint_class(path))
    row={'enemy':key,'blueprint':path,'backup':str(backup),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()}
    row['before']={p:default.get_editor_property(p).get_path_name() for p in ('enemy_skeletal_mesh','death_animation')}
    preserved={p:default.get_editor_property(p) for p in ('idle_animation','walk_animation','attack_animation','cast_animation','hit_reaction_animation','sword_grip_transform','grip_morph_name','grip_morph_weight')}
    default.set_editor_property('enemy_skeletal_mesh',mesh)
    default.set_editor_property('death_animation',death)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert A.save_loaded_asset(bp,False),path
    check=unreal.get_default_object(A.load_blueprint_class(path))
    assert check.get_editor_property('enemy_skeletal_mesh')==mesh
    assert check.get_editor_property('death_animation')==death
    for prop,value in preserved.items():assert check.get_editor_property(prop)==value,prop
    row['after']={p:check.get_editor_property(p).get_path_name() for p in ('enemy_skeletal_mesh','death_animation')}
    records.append(row)
(OUT/'EnemyAssignments.json').write_text(json.dumps({'state':'passed','enemies':records,'scope':'Current eight Gameplay/V01 enemies only. Existing combat clips, character gameplay settings, player assets and maps preserved.'},ensure_ascii=False,indent=2),encoding='utf-8')
