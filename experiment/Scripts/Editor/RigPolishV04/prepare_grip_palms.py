import json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parents[3]/'Docs/Gameplay/RigPolish_v04'
label=sys.argv[1] if len(sys.argv)>1 else 'After'
samples=[]
for seconds in (.6,.9,1.03,1.3):
    samples.append({'label':label+'_'+str(seconds)+'_Palm',
        'clip':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Natural_v04',
        'mesh':'/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Hands_v04',
        'grip_variant':'candidate',
        'time':seconds,'focus_bones':['hand_r'], 'camera':[70,-95,-12], 'fov':30})
(OUT/'HandDetailSpec.json').write_text(json.dumps({'name':'GripPalmPreview','folder':'GripPalm','samples':samples},indent=2),encoding='utf-8')
