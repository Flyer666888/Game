"""Compile the new surface library independently of the geometry export."""
import json,traceback
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve()
OUT=P/'Docs/Gameplay/VRWeaponPolish_v03'
r={'state':'starting'}
try:
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
    source=P/'Scripts/Editor/VRWeaponPolishV03/author_materials.py'
    exec(compile(source.read_text(encoding='utf-8'),str(source),'exec'),globals())
    specs={
        'BladeSteel':([.52,.55,.58],.98), 'BladeEdge':([.64,.67,.70],.98),
        'BladeFuller':([.43,.47,.50],.98), 'Guard03':([.48,.50,.52],.98),
        'GoldDetail':([.30,.22,.12],.94), 'Grip04':([.012,.019,.024],0.),
        'Pommel03':([.37,.60,.67],0.)}
    g={'material_contract':{k:{'base_color_linear':c,'metallic':m} for k,(c,m) in specs.items()}}
    mats,details=author_materials(g)
    r.update(state='passed',surface_authoring=details,scope='Surface library only; runtime mesh has not been rebound.')
except Exception:r.update(state='failed',error=traceback.format_exc());unreal.log_error(r['error'])
(OUT/'SurfaceLibraryReport.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
