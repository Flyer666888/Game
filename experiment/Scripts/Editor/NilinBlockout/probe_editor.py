import unreal, json
from pathlib import Path
out=Path(unreal.Paths.project_dir())/'Docs/LevelDesign/Blockout_v01'
out.mkdir(parents=True,exist_ok=True)
report={'engine':unreal.SystemLibrary.get_engine_version(),'classes':{}}
for name in ('EditorActorSubsystem','LevelEditorSubsystem','UnrealEditorSubsystem','StaticMeshActor','DefaultPawn','SpectatorPawn','Character','GeometryScriptLibrary_MeshPrimitiveFunctions','DynamicMesh','DynamicMeshComponent','PostProcessVolume','CameraActor','AutomationLibrary','NavMeshBoundsVolume'):
    obj=getattr(unreal,name,None)
    report['classes'][name]=bool(obj)
for cls,func in [('Actor','add_component_by_class'),('SystemLibrary','line_trace_single'),('SystemLibrary','capsule_trace_single'),('AutomationLibrary','take_high_res_screenshot'),('EditorStaticMeshLibrary','set_lod_group'),('SystemLibrary','quit_editor')]:
    o=getattr(unreal,cls,None); f=getattr(o,func,None) if o else None
    report[cls+'.'+func]=str(f.__doc__) if f else None
for asset in ('/Engine/BasicShapes/Cube','/Engine/BasicShapes/Cylinder','/Engine/BasicShapes/Sphere','/Engine/BasicShapes/Cone','/Engine/MapTemplates/Sky/DaylightAmbientCubemap'):
    report[asset]=bool(unreal.load_asset(asset))
report['actor_add']= [n for n in dir(unreal.Actor) if 'component' in n.lower() or 'folder' in n.lower()]
(out/'EditorProbe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('NILIN_BLOCKOUT_PROBE_OK')
