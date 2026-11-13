import unreal,json
from pathlib import Path
m=unreal.load_asset('/Game/ReversedScale/Weapons/SelectedSwordA_DetailV01/Materials/V03/M_BladeSteel')
names=['MaterialExpressionTextureSample','MaterialExpressionNormalize','MaterialExpressionClamp','MaterialExpressionLinearInterpolate','MaterialExpressionMultiply','MaterialExpressionAdd']
r={}
for name in names:
    n=unreal.MaterialEditingLibrary.create_material_expression(m,getattr(unreal,name))
    r[name]=list(unreal.MaterialEditingLibrary.get_material_expression_input_names(n))
(Path(unreal.Paths.project_dir())/'Docs/Gameplay/VRWeaponPolish_v03/MaterialPins.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
