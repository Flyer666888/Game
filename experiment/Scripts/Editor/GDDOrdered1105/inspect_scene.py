import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDOrdered1105'
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
assert level.load_level('/Game/ReversedScale/Maps/L_NilinGameplayV01')
rows=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    center,extent=a.get_actor_bounds(False)
    row={'name':a.get_name(),'label':a.get_actor_label(),'class':a.get_class().get_name(),
        'p':[a.get_actor_location().x,a.get_actor_location().y,a.get_actor_location().z],
        'extent':[extent.x,extent.y,extent.z],'tags':list(map(str,a.tags))}
    if isinstance(a,unreal.StaticMeshActor):
        m=a.static_mesh_component.static_mesh
        row['mesh']=m.get_path_name() if m else None
    rows.append(row)
file=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
(O/'SceneBaseline.json').write_text(json.dumps({'map_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'actors':rows},ensure_ascii=False,indent=2),encoding='utf-8')
