from pathlib import Path
import json,hashlib,datetime
ROOT=Path(r'D:\game design\experiment')
BASE=ROOT/'Scripts/Editor/NilinBlockout'
OUT=ROOT/'Docs/LevelDesign/Blockout_v05'
OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'Content/ReversedScale/Maps/L_NilinBlockoutV09.umap'
baseline=OUT/'SourceBaseline.json'
if not baseline.exists():
    baseline.write_text(json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'created':datetime.datetime.now().isoformat()},indent=2),encoding='utf-8')
text=(BASE/'review_session_v04.py').read_text(encoding='utf-8').replace('Blockout_v04','Blockout_v05')
(BASE/'review_session_v05.py').write_text(text,encoding='utf-8')
(OUT/'ReviewCommand.json').write_text(json.dumps({'revision':1,'action':'exec_script','script':'copy_scene_v05.py'}),encoding='utf-8')
print(OUT)
