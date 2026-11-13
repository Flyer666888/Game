import unreal,json
from pathlib import Path
Path(unreal.Paths.project_dir(),'Docs/Gameplay/CombatFeel1104/MaterialAPI.json').write_text(json.dumps({'usage':dir(unreal.MaterialUsage),'methods':[n for n in dir(unreal.MaterialEditingLibrary) if 'usage' in n]},indent=2))
