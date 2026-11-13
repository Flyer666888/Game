import unreal,json
from pathlib import Path
out=Path(unreal.Paths.project_dir())/'Docs/Gameplay/VRWeaponPolish_v03'
names=['TextureCompressionSettings','MaterialSamplerType','MaterialExpressionTextureSample','MaterialExpressionTextureCoordinate','MaterialExpressionNormalize','MaterialExpressionLinearInterpolate']
r={n:str(getattr(unreal,n).__doc__) for n in names}
tex=unreal.Texture2D()
r['texture_properties']={}
for p in ['srgb','compression_settings','flip_green_channel','max_texture_size','lod_group','mip_gen_settings','filter','address_x','address_y']:
    try:r['texture_properties'][p]=str(tex.get_editor_property(p))
    except Exception as e:r['texture_properties'][p]=str(e)
(out/'MaterialAPIReadback.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
