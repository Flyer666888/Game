"""Import user-approved A, keeping the previous Yueyao asset as a fallback."""
import hashlib, json, time, traceback
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
art=root/'ArtSource/WeaponReview/Over9000/SelectedA'
dest='/Game/ReversedScale/Weapons/SelectedSwordA'
started=time.monotonic()
done=None
running=False
handle=None
report={'date':'2026-10-16','success':False,'user_selection':'A','tests_added_or_run':False}

def author():
    fbx=art/'SM_PlayerSword_A.fbx'
    if not fbx.is_file():
        raise RuntimeError('Approved A FBX has not been prepared')
    unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
    task=unreal.AssetImportTask()
    task.filename=str(fbx)
    task.destination_path=dest
    task.destination_name='SM_PlayerSword_A'
    task.automated=True
    task.replace_existing=True
    task.save=False
    opts=unreal.FbxImportUI()
    opts.automated_import_should_detect_type=False
    opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    opts.import_as_skeletal=False
    opts.import_mesh=True
    opts.import_animations=False
    opts.import_materials=False
    opts.import_textures=False
    data=opts.static_mesh_import_data
    data.combine_meshes=True
    data.convert_scene=True
    data.convert_scene_unit=True
    data.auto_generate_collision=False
    data.generate_lightmap_u_vs=False
    data.build_nanite=False
    data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    task.options=opts
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh=unreal.load_asset(dest+'/SM_PlayerSword_A')
    if not isinstance(mesh,unreal.StaticMesh):
        raise RuntimeError('A mesh import failed')
    b=mesh.get_bounds()
    report['bounds']={'origin':[b.origin.x,b.origin.y,b.origin.z],
                      'extent':[b.box_extent.x,b.box_extent.y,b.box_extent.z]}
    # Offline import dimensions: tip +Z, width X, thickness Y, grip midpoint at zero.
    for actual,expected in zip(report['bounds']['extent'],[7.5275,1.80098,39.15715]):
        if abs(actual-expected)>0.08:
            raise RuntimeError('Imported geometry axes/scale differ from the approved A source: '+str(report['bounds']))
    if abs(b.origin.z+b.box_extent.z-64.9391)>0.08:
        raise RuntimeError('A blade tip does not match the authored hand/motion samples')
    material_paths={
        'Blade03':'MI_Sword_Blade_03',
        'Guard03':'MI_Sword_Crossguard_03',
        'Grip04':'MI_Sword_Hilt_01',
        'Pommel03':'MI_Sword_Pommel_03',
    }
    report['materials']=[]
    for i,slot in enumerate(mesh.get_editor_property('static_materials')):
        name=str(slot.get_editor_property('imported_material_slot_name'))
        if name not in material_paths:
            name=str(slot.get_editor_property('material_slot_name'))
        if name not in material_paths:
            raise RuntimeError('Unexpected A material slot: '+name)
        mat=unreal.load_asset('/Game/ModularWeapons/Materials/'+material_paths[name])
        if not mat:
            raise RuntimeError('Original A material missing: '+name)
        mesh.set_material(i,mat)
        report['materials'].append({'slot':name,'asset':mat.get_path_name()})
    if len(report['materials'])!=4:
        raise RuntimeError('The four approved source parts must retain their material slots')
    mesh.set_editor_property('bHasNavigationData',False)
    unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).remove_collisions(mesh)
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh,False):
        raise RuntimeError('A mesh save failed')
    report.update({'success':True,'mesh':mesh.get_path_name(),'fbx_sha256':hashlib.sha256(fbx.read_bytes()).hexdigest(),
                   'original_weapon_preserved':'/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player',
                   'blade_samples_cm':[[0,0,8.42],[0,0,36.68],[0,0,64.94]],
                   'melee_damage':10,'scope':'Static mesh import, original material binding and save only.'})

def tick(delta):
    global done,running
    if running or time.monotonic()-started<6:
        return
    if done is not None:
        if time.monotonic()-done>2:
            unreal.unregister_slate_post_tick_callback(handle)
            unreal.SystemLibrary.quit_editor()
        return
    running=True
    try:
        author()
    except Exception:
        report['error']=traceback.format_exc()
        unreal.log_error(report['error'])
    finally:
        (root/'Docs/AI/SelectedSwordAImported-2026-10-16.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        done=time.monotonic()
        running=False

handle=unreal.register_slate_post_tick_callback(tick)
