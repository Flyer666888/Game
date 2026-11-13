import json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parents[3]/'Docs/Gameplay/RigPolish_v04'
ROOT='/Game/ReversedScale/Characters/WuxiaMale/Animations/'
MESH='/Game/ReversedScale/Characters/WuxiaMale/'
variants=[('Before','Wuxia_Attack_Sword_Compact_v03')]
if len(sys.argv)<2 or sys.argv[1]!='before':variants.append(('After','Wuxia_Attack_Sword_Natural_v04'))
samples=[]
for label,clip in variants:
    for seconds in (.6,.9,1.03,1.3):
        for angle,offset in [('Front',[155,75,25]),('Side',[15,170,20])]:
            samples.append({'label':label+'_'+str(seconds)+'_'+angle,'clip':ROOT+clip,'time':seconds,
                'mesh':MESH+('SK_WuxiaMale_Shoulder_v02' if label=='Before' else 'SK_WuxiaMale_Hands_v04'),
                'grip_variant':'before' if label=='Before' else 'candidate',
                'focus_bones':['upperarm_r','hand_r'],'camera':offset,'fov':34})
(OUT/'HandDetailSpec.json').write_text(json.dumps({'samples':samples},indent=2),encoding='utf-8')
whole=[]
for seconds in (0,.6,.8,.9,1.03,1.3,1.8,2.333333):
    whole.append({'left':{'clip':ROOT+'Wuxia_Attack_Sword_Compact_v03','mesh':MESH+'SK_WuxiaMale_Shoulder_v02','grip_variant':'before','time':seconds,'label':'Before'},
        'right':{'clip':ROOT+'Wuxia_Attack_Sword_Natural_v04','mesh':MESH+'SK_WuxiaMale_Hands_v04','grip_variant':'candidate','time':seconds,'label':'After'},
        'target':[0,0,30],'camera':[600,-55,40],'fov':50})
(OUT/'PreviewSpec.json').write_text(json.dumps({'name':'NaturalAttackComparison','samples':whole},indent=2),encoding='utf-8')
