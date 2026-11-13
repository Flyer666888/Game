"""Prepare an independent V09 scene iteration and its repeatable review tools."""
from pathlib import Path
import json, hashlib, datetime

ROOT=Path(r'D:\game design\experiment')
BASE=ROOT/'Scripts/Editor/NilinBlockout'
OUT=ROOT/'Docs/LevelDesign/Blockout_v04'
OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'Content/ReversedScale/Maps/L_NilinBlockoutV08.umap'
baseline=OUT/'SourceBaseline.json'
if not baseline.exists():
    baseline.write_text(json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'created':datetime.datetime.now().isoformat()},indent=2),encoding='utf-8')
for name in ['review_session','validate','audit_edges','audit_pressure','runtime_walk','capture','readback']:
    text=(BASE/(name+'_v03.py')).read_text(encoding='utf-8')
    text=text.replace('Blockout_v03','Blockout_v04').replace('L_NilinBlockoutV08','L_NilinBlockoutV09')
    if name=='capture':
        text=text.replace("and ('Pressure' in a.get_actor_label() or 'AlternateOverview' in a.get_actor_label())", "and any(token in a.get_actor_label() for token in ('01_Gate','03_Alchemy','05_Boss','09_AlternateOverview','10_PressureEntry','14_AlchemyElevated'))")
    if name=='readback':
        text=text.replace("if a.actor_has_tag('NLBlockout.ClusterV02'):","if a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent):")
    (BASE/(name+'_v04.py')).write_text(text,encoding='utf-8')
(OUT/'ReviewCommand.json').write_text(json.dumps({'revision':1,'action':'exec_script','script':'copy_scene_v04.py'}),encoding='utf-8')
print(str(OUT))
