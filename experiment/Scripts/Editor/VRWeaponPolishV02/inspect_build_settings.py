import unreal,json
from pathlib import Path
out=Path(unreal.Paths.project_dir())/'Docs/Gameplay/VRWeaponPolish_v02'
m=unreal.load_asset('/Game/ReversedScale/Weapons/SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01')
s=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).get_lod_build_settings(m,0)
r={'settings':str(s),'import_data':str(m.get_editor_property('asset_import_data'))}
for n in ['recompute_normals','recompute_tangents','use_mikk_t_space','use_full_precision_u_vs','remove_degenerates']:
    try:r[n]=s.get_editor_property(n)
    except Exception as e:r[n]=str(e)
(out/'BuildSettings.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
