"""Apply the visually reviewed hand mesh and attack to four sword archetypes."""
import hashlib,json,shutil
from pathlib import Path
import unreal
PROJECT=Path(unreal.Paths.project_dir()).resolve()
OUT=PROJECT/'Docs/Gameplay/RigPolish_v04'
ART=PROJECT/'ArtSource/WuxiaMale/RigPolishV04'
A=unreal.EditorAssetLibrary
ROOT='/Game/ReversedScale/Characters/WuxiaMale/'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
review=json.loads((OUT/'VisualSignoff.json').read_text(encoding='utf-8'))
assert review['accepted'] is True
mesh_import=json.loads((OUT/'HandsImport.json').read_text(encoding='utf-8'))
for name,path in {'poses':ART/'Attack/NaturalAttackPoses.json', 'mesh_fbx':Path(mesh_import['source_fbx']),
                  'grip':OUT/'CandidateGrip.json'}.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest()==review['sha256'][name],name+' changed after review'
for path in (OUT/'HandsImport.json',ART/'Attack/NaturalAttackImported.json',OUT/'NaturalAttackValidation.json',
             OUT/'NaturalAttackComparison.json',OUT/'HandDetailPreview.json'):
    report=json.loads(path.read_text(encoding='utf-8'))
    assert report['state']=='passed' and not report.get('failures'),str(path)
candidate=A.load_asset(ROOT+'Animations/Wuxia_Attack_Sword_Natural_v04')
previous=A.load_asset(ROOT+'Animations/Wuxia_Attack_Sword_Compact_v03')
mesh=A.load_asset(ROOT+'SK_WuxiaMale_Hands_v04')
old_mesh=A.load_asset(ROOT+'SK_WuxiaMale_Shoulder_v02')
grip_data=json.loads((OUT/'CandidateGrip.json').read_text(encoding='utf-8'))
grip=unreal.Transform(location=unreal.Vector(*grip_data['translation']),scale=unreal.Vector(*grip_data['scale']))
grip.rotation=unreal.Quat(*grip_data['quaternion'])
assert candidate and previous and mesh and old_mesh
assert candidate.get_editor_property('skeleton')==mesh.get_editor_property('skeleton')==old_mesh.get_editor_property('skeleton')
assert abs(candidate.get_play_length()-previous.get_play_length())<.0001
records=[]
for key in ('sword','GM01','GM04','boss'):
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    file=PROJECT/'Content'/(path.removeprefix('/Game/')+'.uasset')
    backup=OUT/'Backups/Assets'/file.relative_to(PROJECT/'Content')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(file,backup)
    bp=A.load_asset(path);default=unreal.get_default_object(A.load_blueprint_class(path))
    original_clip=default.get_editor_property('attack_animation')
    original_mesh=default.get_editor_property('enemy_skeletal_mesh')
    assert original_clip in (previous,candidate),'Unexpected user attack change: '+path
    assert original_mesh in (old_mesh,mesh),'Unexpected user mesh change: '+path
    preserved={p:default.get_editor_property(p) for p in ('idle_animation','walk_animation','cast_animation',
        'hit_reaction_animation','death_animation','grip_morph_name','grip_morph_weight')}
    brain=default.get_enemy_brain()
    timing={p:brain.get_editor_property(p) for p in ('telegraph_seconds','attack_seconds','recover_seconds','attack_range')}
    default.set_editor_property('attack_animation',candidate)
    default.set_editor_property('enemy_skeletal_mesh',mesh)
    default.set_editor_property('sword_grip_transform',grip)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert A.save_loaded_asset(bp,False),path
    check=unreal.get_default_object(A.load_blueprint_class(path))
    assert check.get_editor_property('attack_animation')==candidate
    assert check.get_editor_property('enemy_skeletal_mesh')==mesh
    assert check.get_editor_property('sword_grip_transform')==grip
    for prop,value in preserved.items():assert check.get_editor_property(prop)==value,prop
    for prop,value in timing.items():assert check.get_enemy_brain().get_editor_property(prop)==value,prop
    records.append({'enemy':key,'blueprint':path,'from_animation':original_clip.get_path_name(),
        'to_animation':candidate.get_path_name(),'from_mesh':original_mesh.get_path_name(),'to_mesh':mesh.get_path_name(),
        'grip':grip_data,'backup':str(backup),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()})
(OUT/'AttackAssignments.json').write_text(json.dumps({'state':'passed','enemies':records,
    'scope':'Four sword archetypes only: local right-hand replacement, natural attack and grip attachment fitted to the real closed hand. Caster assets, timing, range, damage, other animation clips and maps preserved.'},ensure_ascii=False,indent=2),encoding='utf-8')
