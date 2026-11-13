import unreal,json
from pathlib import Path
out=Path(unreal.Paths.project_dir())/'Docs/Gameplay/VRWeaponPolish_v02'
m=unreal.load_asset('/Game/ReversedScale/Weapons/SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01')
d=m.get_editor_property('asset_import_data')
before={'normal_import_method':str(d.get_editor_property('normal_import_method')),'normal_generation_method':str(d.get_editor_property('normal_generation_method'))}
d.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
d.set_editor_property('normal_generation_method',unreal.FBXNormalGenerationMethod.MIKK_T_SPACE)
assert unreal.EditorAssetLibrary.save_loaded_asset(m,False)
(out/'ReimportSettingsRepair.json').write_text(json.dumps({'before':before,'after':{'normal_import_method':str(d.get_editor_property('normal_import_method')),'normal_generation_method':str(d.get_editor_property('normal_generation_method'))}},indent=2),encoding='utf-8')
