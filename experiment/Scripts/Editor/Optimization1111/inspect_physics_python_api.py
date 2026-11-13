import unreal,json
from pathlib import Path
out=Path(unreal.Paths.project_dir())/'Docs/Gameplay/Optimization1111/PhysicsPythonAPI.json'
items=unreal.EditorAssetLibrary.list_assets('/Game/ReversedScale/Characters/Physics1111',recursive=True,include_folder=False)
report={'assets':list(map(str,items)),'properties':{}}
for path in items:
    asset=unreal.load_asset(path)
    if not asset:continue
    for name in ['skeletal_body_setups','SkeletalBodySetups','constraint_setup','ConstraintSetup','preview_skeletal_mesh','PreviewSkeletalMesh']:
        try:
            value=asset.get_editor_property(name)
            report['properties'][name]=str(value)
        except Exception as e:report['properties'][name]={'error':str(e)}
    report['methods']=[m for m in dir(asset) if any(k in m.lower() for k in ['body','constraint','preview'])]
    break
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
