import unreal,json
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve()
m=unreal.load_asset('/Game/ReversedScale/Weapons/TalismanJade1104/SM_Nilin_JadeTalisman')
s=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
b=m.get_bounds()
result={'triangles':m.get_num_triangles(0),'bounds':str(b),'build_settings':str(s.get_lod_build_settings(m,0)),
        'description_methods':[x for x in dir(m) if 'description' in x]}
(P/'Docs/Gameplay/JadeTalismanCast1104/GeometryAudit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
