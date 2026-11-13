"""Read exported support FBX back, check original bones and inspect actual skinned poses."""
import sys,json,bpy,math
from pathlib import Path
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import new_rig_common as common
report=json.loads((common.DOC/'NativeSupportClips.json').read_text())
out=common.DOC/'SupportReview';out.mkdir(exist_ok=True)
arm,mesh,_,meta=common.load_rig()
expected_names=set(meta['bones'])
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12
scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('SupportReviewWorld');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.09,.11,.14,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25
mat=bpy.data.materials.new('ReviewClay');mat.use_nodes=True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.08,.18,.27,1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.65
mesh.data.materials.clear();mesh.data.materials.append(mat)
for poly in mesh.data.polygons:poly.material_index=0
bpy.ops.mesh.primitive_plane_add(size=10,location=(0,0,-.005));floor=bpy.context.object
fm=bpy.data.materials.new('Ground');fm.use_nodes=True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.08,.095,.11,1)
fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8
floor.data.materials.append(fm)
bpy.ops.object.camera_add(location=(3,-3,2.2));cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=2.5
focus=Vector((0,0,.85));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler()
for loc,power in [((3,-3,4),180),((-2,3,4),200)]:
    bpy.ops.object.light_add(type='AREA',location=loc);lamp=bpy.context.object;lamp.data.energy=power;lamp.data.size=4
    lamp.rotation_euler=(focus-lamp.location).to_track_quat('-Z','Y').to_euler()
results=[]
for clip in report['clips']:
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=clip['file'],automatic_bone_orientation=False,use_anim=True,ignore_leaf_bones=False)
    imported=next(o for o in bpy.data.objects if o not in before and o.type=='ARMATURE')
    assert set(imported.data.bones.keys())==expected_names,(clip['action'],'bone mismatch')
    action=imported.animation_data.action;first,last=action.frame_range
    errors=[]
    # Blender importer scene rate follows exported FBX; compare proportional frame
    # positions because scene frame rate may retain a previous imported file rate.
    for i,sample in enumerate(clip['samples']):
        f=first+(last-first)*i/(len(clip['samples'])-1)
        scene.frame_set(int(f),subframe=f-int(f))
        for b,key in [('mixamorig:Head','head'),('mixamorig:Hips','hip'),('mixamorig:RightHand','right_hand')]:
            actual=(imported.matrix_world@imported.pose.bones[b].matrix).translation
            errors.append((actual-Vector(sample[key])).length)
    assert max(errors)<.001,(clip['action'],'FBX roundtrip error',max(errors))
    result={'clip':clip['action'],'maximum_roundtrip_position_error_m':max(errors),'bone_count':len(imported.data.bones),'frames':list(action.frame_range),'images':[]}
    indices=[0] if '_Idle_' in clip['action'] else [len(clip['samples'])//2]
    if '_Death_' in clip['action']:indices=[30,60,99]
    for index in indices:
        f=first+(last-first)*index/(len(clip['samples'])-1);scene.frame_set(int(f),subframe=f-int(f))
        world={b.name:imported.matrix_world@b.matrix for b in imported.pose.bones}
        world={b:Matrix.LocRotScale(m.translation,m.to_quaternion(),Vector((1,1,1))) for b,m in world.items()}
        common.apply_world(arm,world)
        scene.render.filepath=str(out/(clip['action']+f'_{index:03d}.png'));bpy.ops.render.render(write_still=True)
        result['images'].append(scene.render.filepath)
    results.append(result)
    bpy.data.objects.remove(imported,do_unlink=True)
(common.DOC/'NativeSupportValidation.json').write_text(json.dumps({'state':'passed','clips':results},indent=2))
print('NATIVE_SUPPORT_VALIDATED',json.dumps(results))
