import json
from pathlib import Path
OUT=Path(__file__).resolve().parents[3]/'Docs/Gameplay/RigPolish_v04'
samples=[]
for label,weight,view,tangent in [('Basis_Lit',0,'lit',0),('Grip_Lit',1,'lit',0),('Grip_Unlit',1,'unlit',0),('Grip_RecomputedTangents',1,'lit',1)]:
    samples.append({'label':label,'clip':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Natural_v04',
        'mesh':'/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Hands_v04','time':1.03,
        'focus_bones':['hand_r'],'camera':[70,-95,-12],'fov':30,
        'grip_weight':weight,'view_mode':view,'recompute_tangents':tangent})
(OUT/'HandDetailSpec.json').write_text(json.dumps({'name':'GripDiagnostic','folder':'GripDiagnostic','samples':samples},indent=2),encoding='utf-8')
