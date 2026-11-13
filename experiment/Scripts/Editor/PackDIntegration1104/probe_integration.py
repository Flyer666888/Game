import unreal,json
from pathlib import Path
O=Path(unreal.Paths.project_dir()).resolve()/'Docs/Gameplay/PackDIntegration1104'
out={'api':{},'enemies':[]}
for n in ['CurveVector','CurveVectorFactory','CurveBase','RichCurve','AnimationLibrary']:
    cls=getattr(unreal,n,None)
    out['api'][n]={k:str(getattr(cls,k).__doc__) for k in dir(cls) if any(w in k for w in ['curve','csv','key','notify']) and not k.startswith('_')} if cls else None
for key in ['sword','GM01','GM04','boss']:
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    obj=unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(path))
    brain=obj.get_enemy_brain()
    out['enemies'].append({'asset':path,'role':str(brain.role),'attack':str(obj.attack_animation),
        'range':brain.attack_range,'timing':[brain.telegraph_seconds,brain.attack_seconds,brain.recover_seconds],
        'show_sword':obj.b_show_sword if hasattr(obj,'b_show_sword') else obj.get_editor_property('show_sword')})
(O/'Probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
