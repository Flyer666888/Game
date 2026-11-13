import json
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDSession28B'
L=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
E=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
A=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert E.get_game_world() is None
assert L.load_level('/Game/ReversedScale/Maps/L_NilinGameplayV01')
world=E.get_editor_world()
records=[]
for a in A.get_all_level_actors():
    label=a.get_actor_label();p=a.get_actor_location()
    if 'Friend' in label or ('Ritual' in label) or (abs(p.x)<3000 and 27000<p.y<32500 and 7000<p.z<9000):
        records.append({'label':label,'class':a.get_class().get_name(),'location':str(p),'folder':str(a.get_folder_path())})
stages=[]
for a in A.get_all_level_actors():
    if isinstance(a,unreal.NLLevelEncounterDirector):
        for s in a.get_editor_property('stages'):
            if str(s.stage_id).startswith('C'):
                stages.append({'id':str(s.stage_id),'entry':str(s.entry_transform),'points':[{'id':str(p.spawn_point_id),'transform':str(p.spawn_transform)} for p in s.spawn_points]})
checks=[]
for x,y in [(0,28300),(0,28600),(-1200,29800),(1200,29800),(-1200,30600),(1200,30600)]:
    hit=unreal.SystemLibrary.line_trace_single(world,unreal.Vector(x,y,7600),unreal.Vector(x,y,7000),unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
    t=hit.to_tuple() if hit else None
    checks.append({'xy':[x,y],'hit':str(t[5]) if t else None,'actor':t[9].get_actor_label() if t and t[9] else None})
(O/'CourtInspection.json').write_text(json.dumps({'actors':records,'stages':stages,'ground':checks},ensure_ascii=False,indent=2),encoding='utf-8')
camera=unreal.Vector(1600,26800,8400);target=unreal.Vector(0,29400,7350)
E.set_level_viewport_camera_info(camera,unreal.MathLibrary.find_look_at_rotation(camera,target))
unreal.AutomationLibrary.take_high_res_screenshot(1600,1000,str(O/'AlchemyBefore.png'))
