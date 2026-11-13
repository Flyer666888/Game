"""Write camera/pose specs; executed by the local Python runtime."""
import json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parents[3]/'Docs/Gameplay/RigPolish_v02'
ROOT='/Game/ReversedScale/Characters/WuxiaMale'
kind=sys.argv[1]
samples=[]
if kind=='Shoulder':
    for name,seconds in [('Idle_Planted',0),('Attack_Sword',.6),('Attack_Sword',1.1),('Attack_Sword',1.5),('Cast_Talisman',1.1),('Hit_Sword',.3)]:
        clip=ROOT+'/Animations/Wuxia_'+name+'_Upright_v01'
        samples.append({'left':{'clip':clip,'time':seconds,'mesh':ROOT+'/SK_WuxiaMale_Combat','label':'Before'},'right':{'clip':clip,'time':seconds,'mesh':ROOT+'/SK_WuxiaMale_Shoulder_v02','label':'After'},'target':[0,0,40],'camera':[500,-35,30],'fov':42})
elif kind=='Death':
    for seconds in [0,.45,.7,1.2,1.8,2.1,2.6]:
        samples.append({'left':{'clip':ROOT+'/Animations/Wuxia_Death_Grounded','time':seconds,'mesh':ROOT+'/SK_WuxiaMale_Combat','label':'Before'},'right':{'clip':ROOT+'/Animations/Wuxia_Death_Restrained_v02','time':seconds,'mesh':ROOT+'/SK_WuxiaMale_Shoulder_v02','label':'After'},'target':[30,0,-20],'camera':[620,-220,290],'fov':50})
else:raise ValueError(kind)
(OUT/'PreviewSpec.json').write_text(json.dumps({'name':kind+'Comparison','samples':samples},indent=2),encoding='utf-8')
