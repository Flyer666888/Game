"""Export current imported candidate for a round-trip geometry diagnostic."""
import json
from pathlib import Path
import unreal
OUT=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v04\Audit')
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
mesh=unreal.load_asset('/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Hands_v04')
task=unreal.AssetExportTask();task.object=mesh
task.filename=str(OUT/'UE_HandsA.fbx');task.automated=True;task.prompt=False;task.replace_identical=True
task.exporter=unreal.SkeletalMeshExporterFBX()
options=unreal.FbxExportOption();options.ascii=False;options.level_of_detail=False;options.export_morph_targets=True
options.bake_material_inputs=unreal.FbxMaterialBakeMode.DISABLED;task.options=options
assert unreal.Exporter.run_asset_export_task(task)
(OUT/'UE_HandsA_Export.json').write_text(json.dumps({'asset':mesh.get_path_name(),'file':task.filename}),encoding='utf-8')
