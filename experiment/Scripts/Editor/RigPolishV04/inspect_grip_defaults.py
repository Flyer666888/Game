"""Read configured enemy grip transforms without modifying assets."""
import json
from pathlib import Path
import unreal
out=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v04')
rows=[]
for key in ('sword','talisman','rock_talisman','GM01','GM02','GM03','GM04','boss'):
    cls=unreal.EditorAssetLibrary.load_blueprint_class('/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key)
    default=unreal.get_default_object(cls)
    t=default.get_editor_property('sword_grip_transform')
    p,q,s=t.translation,t.rotation,t.scale3d
    rows.append({'enemy':key,'translation':[p.x,p.y,p.z], 'quaternion':[q.x,q.y,q.z,q.w],
        'scale':[s.x,s.y,s.z], 'morph_name':str(default.get_editor_property('grip_morph_name')),
        'morph_weight':default.get_editor_property('grip_morph_weight')})
(out/'GripDefaults.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
