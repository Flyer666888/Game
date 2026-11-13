"""Refresh only the two alchemy images after the hanging-trim adjustment."""
from pathlib import Path
path=Path(r'D:\game design\experiment\Scripts\Editor\NilinBlockout\capture_v04.py')
source=path.read_text(encoding='utf-8')
source=source.replace("('01_Gate','03_Alchemy','05_Boss','09_AlternateOverview','10_PressureEntry','14_AlchemyElevated')","('03_Alchemy','14_AlchemyElevated')")
source=source.replace('results=[]',"results=[r for r in json.load(open(os.path.join(OUT,'CaptureReport.json'),encoding='utf-8'))['captures'] if not any(t in r['file'] for t in ('03_Alchemy','14_AlchemyElevated'))]")
exec(compile(source,str(path),'exec'),{'__name__':'__main__'})
