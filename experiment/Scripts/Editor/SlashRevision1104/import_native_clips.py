"""Import supplied-skeleton clips, retaining a distinct v07 package per clip."""
import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/SlashRevision1104'
A=unreal.EditorAssetLibrary;L=unreal.AnimationLibrary
R='/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07'
mesh=A.load_asset(R+'/SK_WuxiaMale_Native_v07');assert mesh
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
spec=json.loads((O/'ClipImportSpec.json').read_text(encoding='utf-8-sig'))
rows={}
for kind,sourcefile in spec['clips'].items():
    source=Path(sourcefile);assert source.is_file()
    name='A_Wuxia_'+kind.title()+'_Native_v07'
    task=unreal.AssetImportTask();task.filename=str(source)
    task.destination_path=R;task.destination_name=name;task.automated=True;task.replace_existing=True;task.save=True
    opts=unreal.FbxImportUI();opts.automated_import_should_detect_type=False
    opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_ANIMATION
    opts.import_as_skeletal=True;opts.import_mesh=False;opts.import_animations=True
    opts.import_materials=False;opts.import_textures=False;opts.create_physics_asset=False
    opts.skeleton=mesh.skeleton
    opts.anim_sequence_import_data.convert_scene=True;opts.anim_sequence_import_data.convert_scene_unit=True
    opts.anim_sequence_import_data.set_editor_property('use_default_sample_rate',False)
    opts.anim_sequence_import_data.set_editor_property('custom_sample_rate',60)
    opts.anim_sequence_import_data.set_editor_property('add_curve_metadata_to_skeleton',False)
    task.options=opts
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    candidates=[A.load_asset(p) for p in task.imported_object_paths]
    anims=[c for c in candidates if isinstance(c,unreal.AnimSequence)]
    assert len(anims)==1,(kind,task.imported_object_paths)
    anim=anims[0]
    assert anim.get_editor_property('skeleton')==mesh.skeleton
    assert .05<anim.get_play_length()<6
    # FBX animation-only import strips Blender's armature unit scale. The mesh
    # reference root retains it, so restore that unit conversion on Hips once.
    evaluation=unreal.AnimPoseEvaluationOptions()
    evaluation.evaluation_type=unreal.AnimDataEvalType.COMPRESSED
    evaluation.optional_skeletal_mesh=mesh;evaluation.should_retarget=False;evaluation.extract_root_motion=False
    frames=round(anim.get_play_length()*60)
    root_keys=[]
    for i in range(frames+1):
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,i/60.,evaluation)
        root_keys.append(unreal.AnimPoseExtensions.get_bone_pose(pose,'Hips',unreal.AnimPoseSpaces.LOCAL))
    reference=json.loads((O/'NativeUEReference.json').read_text())['rest']['Hips']
    unit_factor=reference['s'][0]/root_keys[0].scale3d.x
    assert abs(unit_factor-100)<.01 or abs(unit_factor-1)<.001,('Unexpected FBX root unit',unit_factor)
    controller=anim.controller
    controller.open_bracket('Preserve native FBX centimetre root scale',False)
    try:
        controller.set_frame_rate(unreal.FrameRate(numerator=60,denominator=1),False)
        controller.set_number_of_frames(unreal.FrameNumber(value=frames),False)
        assert controller.set_bone_track_keys('Hips',[k.translation*unit_factor for k in root_keys],
          [k.rotation for k in root_keys],[k.scale3d*unit_factor for k in root_keys],False)
    finally:controller.close_bracket(False)
    anim.set_preview_skeletal_mesh(mesh)
    if kind=='attack':
        metadata=json.loads((O/'NativeSlashManifest.json').read_text())
        tracks=L.get_animation_notify_track_names(anim)
        if not tracks:
            L.add_animation_notify_track(anim,'AttackWindow',unreal.LinearColor(1,0.2,0,1))
            tracks=L.get_animation_notify_track_names(anim)
        for track in tracks:L.remove_animation_notify_events_by_track(anim,track)
        start,end=metadata['notify']
        assert L.add_animation_notify_state_event(anim,tracks[0],start,end-start,unreal.NLEnemyAttackWindowNotifyState)
        assert abs(anim.get_play_length()-metadata['duration'])<.002
    assert A.save_loaded_asset(anim,False)
    rows[kind]={'asset':anim.get_path_name(),'duration':anim.get_play_length(),'source':str(source),
      'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'restored_root_unit_scale':unit_factor}
previous=json.loads((O/'NativeClipsImport.json').read_text()) if (O/'NativeClipsImport.json').exists() else {'clips':{}}
previous['clips'].update(rows);previous['state']='passed';previous['mesh']=mesh.get_path_name()
(O/'NativeClipsImport.json').write_text(json.dumps(previous,indent=2),encoding='utf-8')
unreal.log('NATIVE_V07_CLIPS_IMPORTED '+','.join(rows))
