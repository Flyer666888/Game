"""Opaque PBR surface authoring for the V03 player sword; only new V03 assets."""
import hashlib, json
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
SRC = P/'ArtSource/WeaponReview/SelectedA_DetailV03'
DEST = '/Game/ReversedScale/Weapons/SelectedSwordA_DetailV01'
MAT_DEST = DEST+'/Materials/V03'
TEX_DEST = DEST+'/Textures/V03'
EL=unreal.EditorAssetLibrary
AT=unreal.AssetToolsHelpers.get_asset_tools()
ML=unreal.MaterialEditingLibrary

def link(a,output,b,input):
    assert ML.connect_material_expressions(a,output,b,input),(str(a),output,str(b),input)
def node(mat,cls,x=0,y=0): return ML.create_material_expression(mat,cls,x,y)
def scalar(mat,value):
    n=node(mat,unreal.MaterialExpressionConstant);n.set_editor_property('r',value);return n
def color(mat,value):
    n=node(mat,unreal.MaterialExpressionConstant3Vector)
    n.set_editor_property('constant',unreal.LinearColor(*value,1));return n
def binary(mat,cls,a,b,ao='',bo=''):
    n=node(mat,cls);link(a,ao,n,'A');link(b,bo,n,'B');return n

def import_texture(spec):
    source=Path(spec['file'])
    if not source.is_absolute():source=SRC/'Textures'/source
    assert source.is_file(),source
    name='T_'+source.stem
    task=unreal.AssetImportTask();task.filename=str(source);task.destination_path=TEX_DEST
    task.destination_name=name;task.automated=True;task.replace_existing=True;task.save=False
    AT.import_asset_tasks([task])
    tex=unreal.load_asset(TEX_DEST+'/'+name)
    assert isinstance(tex,unreal.Texture2D),(name,task.imported_object_paths)
    normal='normal' in source.stem.lower()
    tex.set_editor_property('srgb',bool(spec.get('srgb',False)))
    tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP if normal else
        unreal.TextureCompressionSettings.TC_DEFAULT if spec.get('srgb',False) else unreal.TextureCompressionSettings.TC_MASKS)
    tex.set_editor_property('flip_green_channel',False)
    tex.set_editor_property('max_texture_size',512)
    tex.set_editor_property('address_x',unreal.TextureAddress.TA_WRAP)
    tex.set_editor_property('address_y',unreal.TextureAddress.TA_WRAP)
    assert EL.save_loaded_asset(tex,False)
    return tex,{'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'asset':tex.get_path_name(),'srgb':tex.get_editor_property('srgb'),
        'compression':str(tex.get_editor_property('compression_settings')),'directx_normal':normal}

def author_materials(geometry):
    contract=json.loads((SRC/'Textures/material_texture_contract.json').read_text(encoding='utf-8'))
    textures={};texture_report={}
    for group,spec in contract['sets'].items():
        textures[group]={}
        for role,tspec in spec['textures'].items():
            textures[group][role],texture_report[group+'/'+role]=import_texture(tspec)
    profiles={
        'BladeSteel':('SteelSurface',.0,.07,(1.,1.)),
        'BladeEdge':('SteelSurface',-.08,.04,(1.,1.)),
        'BladeFuller':('SteelSurface',.0,.07,(1.,1.)),
        'Guard03':('AgedSilver',.0,.10,(1.,1.)),
        'GoldDetail':('AgedSilver',-.055,.08,(1.,1.)),
        'Grip04':('DarkLeather',.0,.35,(4.,4.)),
        'Pommel03':('IceJade',.0,.20,(2.,2.)),
    }
    mats={};report={}
    use_vertex_masks=bool(geometry.get('vertex_color_masks',False))
    for key,(group,offset,normal_strength,tiling) in profiles.items():
        spec=geometry['material_contract'][key]
        normal_strength=spec.get('normal_strength',normal_strength)
        offset=spec.get('roughness_offset',offset)
        variation=spec.get('roughness_variation_scale',{'SteelSurface':.35,'AgedSilver':.4,'DarkLeather':.8,'IceJade':1.}[group])
        name='M_'+key
        path=MAT_DEST+'/'+name
        mat=unreal.load_asset(path) if EL.does_asset_exist(path) else AT.create_asset(name,MAT_DEST,unreal.Material,unreal.MaterialFactoryNew())
        assert mat
        # Detach old outputs before deleting their graphs, avoiding transient compilation
        # of dangling Normalize inputs when a previously saved material is rebuilt.
        for prop in (unreal.MaterialProperty.MP_BASE_COLOR,unreal.MaterialProperty.MP_METALLIC,
                     unreal.MaterialProperty.MP_ROUGHNESS,unreal.MaterialProperty.MP_NORMAL):
            ML.disconnect_material_property(mat,prop)
        ML.delete_all_material_expressions(mat)
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
        mat.set_editor_property('two_sided',False)
        uv=node(mat,unreal.MaterialExpressionTextureCoordinate,-900,0)
        uv.set_editor_property('u_tiling',tiling[0]);uv.set_editor_property('v_tiling',tiling[1])
        samples={}
        for role,tex in textures[group].items():
            n=node(mat,unreal.MaterialExpressionTextureSample,-650,len(samples)*200)
            n.set_editor_property('texture',tex)
            st=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if role=='normal' else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if role=='base_color' else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
            n.set_editor_property('sampler_type',st);link(uv,'',n,'UVs');samples[role]=n
        if 'base_color' in samples:base=samples['base_color'];base_out='RGB'
        else:base=color(mat,spec['base_color_linear']);base_out=''
        rough_mean=contract['sets'][group]['roughness_mean']
        centered=binary(mat,unreal.MaterialExpressionAdd,samples['roughness'],scalar(mat,-rough_mean),'R')
        varied=binary(mat,unreal.MaterialExpressionMultiply,centered,scalar(mat,variation))
        rough=binary(mat,unreal.MaterialExpressionAdd,varied,scalar(mat,rough_mean+offset))
        vc=None
        if use_vertex_masks and key not in ('Grip04','Pommel03'):
            vc=node(mat,unreal.MaterialExpressionVertexColor)
            polish=binary(mat,unreal.MaterialExpressionMultiply,vc,scalar(mat,-.10),'R')
            cavity=binary(mat,unreal.MaterialExpressionMultiply,vc,scalar(mat,.10),'G')
            rough=binary(mat,unreal.MaterialExpressionAdd,binary(mat,unreal.MaterialExpressionAdd,rough,polish),cavity)
            cavity_tint=binary(mat,unreal.MaterialExpressionAdd,
                binary(mat,unreal.MaterialExpressionMultiply,vc,scalar(mat,-.12),'G'),scalar(mat,1.))
            base=binary(mat,unreal.MaterialExpressionMultiply,base,cavity_tint,base_out);base_out=''
        clamp=node(mat,unreal.MaterialExpressionClamp);clamp.set_editor_property('min_default',.12);clamp.set_editor_property('max_default',.85)
        link(rough,'',clamp,'None')
        flat=color(mat,(0.,0.,1.));normal=node(mat,unreal.MaterialExpressionLinearInterpolate)
        link(flat,'',normal,'A');link(samples['normal'],'RGB',normal,'B');normal.set_editor_property('const_alpha',normal_strength)
        normalized=node(mat,unreal.MaterialExpressionNormalize);link(normal,'',normalized,'VectorInput')
        assert ML.connect_material_property(base,base_out,unreal.MaterialProperty.MP_BASE_COLOR)
        assert ML.connect_material_property(scalar(mat,spec['metallic']),'',unreal.MaterialProperty.MP_METALLIC)
        assert ML.connect_material_property(clamp,'',unreal.MaterialProperty.MP_ROUGHNESS)
        assert ML.connect_material_property(normalized,'',unreal.MaterialProperty.MP_NORMAL)
        ML.layout_material_expressions(mat);ML.recompile_material(mat)
        assert EL.save_loaded_asset(mat,False)
        mats[key]=mat
        report[key]={'path':path,'surface_group':group,'texture_samples':len(samples),'uv_tiling':tiling,
            'normal_strength':normal_strength,'roughness_offset':offset,'roughness_variation_scale':variation,'base_color_linear':spec.get('base_color_linear'),
            'base_color_from_texture':'base_color' in samples,'metallic':spec['metallic'],
            'vertex_masks_used':vc is not None,'statistics':str(ML.get_statistics(mat))}
    return mats,{'textures':texture_report,'materials':report,'vertex_masks_enabled':use_vertex_masks}
