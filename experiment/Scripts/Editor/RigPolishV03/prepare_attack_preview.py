"""Prepare matched camera comparisons of the two attack clips."""
import json
from pathlib import Path
OUT=Path(__file__).resolve().parents[3]/'Docs/Gameplay/RigPolish_v03'
ROOT='/Game/ReversedScale/Characters/WuxiaMale'
samples=[]
for seconds in [0,.55,.7,.8,.9,1.03,1.2,1.5,2.333333]:
    samples.append({'left':{'clip':ROOT+'/Animations/Wuxia_Attack_Sword_Upright_v01','time':seconds,'mesh':ROOT+'/SK_WuxiaMale_Shoulder_v02','label':'Before'},
        'right':{'clip':ROOT+'/Animations/Wuxia_Attack_Sword_Compact_v03','time':seconds,'mesh':ROOT+'/SK_WuxiaMale_Shoulder_v02','label':'After'},
        'target':[0,0,30],'camera':[600,-55,40],'fov':50})
(OUT/'PreviewSpec.json').write_text(json.dumps({'name':'AttackComparison','samples':samples},indent=2),encoding='utf-8')
