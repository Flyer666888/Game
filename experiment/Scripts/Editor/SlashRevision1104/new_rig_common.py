"""Canonical normalization for the supplied Mixamo rig. Source stays untouched."""
from pathlib import Path
import bpy, math, json
from mathutils import Matrix, Vector, Quaternion

P=Path(r'D:/game design/experiment')
SOURCE=Path(r'C:/Users/21475/Desktop/Game model/古代男青年走路动画.fbx')
OUT=P/'ArtSource/WuxiaMale/NativeRigV07';OUT.mkdir(parents=True,exist_ok=True)
DOC=P/'Docs/Gameplay/SlashRevision1104';DOC.mkdir(parents=True,exist_ok=True)

def load_rig():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(SOURCE),automatic_bone_orientation=False,use_anim=True,ignore_leaf_bones=False)
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    # Measure the undeformed mesh in source world space, not the animated bounds.
    points=[mesh.matrix_world@v.co for v in mesh.data.vertices]
    lo=min(p.z for p in points);hi=max(p.z for p in points)
    factor=1.8/(hi-lo)
    # Root centered laterally; +X forward,+Y left,+Z up.
    root=arm.matrix_world@arm.data.bones['mixamorig:Hips'].head_local
    T=Matrix.Scale(factor,4)@Matrix.Translation(Vector((-root.x,-root.y,-lo)))
    walk=[]
    for frame in range(1,33):
        bpy.context.scene.frame_set(frame)
        walk.append({'frame':frame,'world':{b.name:T@arm.matrix_world@b.matrix for b in arm.pose.bones}})
    arm.animation_data_clear()
    for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    # Detach mesh while retaining world transform, then apply the same global transform.
    mw=mesh.matrix_world.copy();mesh.parent=None;mesh.matrix_world=mw
    arm.matrix_world=T@arm.matrix_world;mesh.matrix_world=T@mesh.matrix_world
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);mesh.select_set(True)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
    scene.render.fps=60
    meta={'height_m':1.8,'source_z_bounds':[lo,hi],'source_to_meter_scale':factor,
      'forward':'+X','left':'+Y','up':'+Z','bones':list(arm.data.bones.keys()),
      'rest_world':{b.name:[list(r) for r in b.matrix_local] for b in arm.data.bones}}
    (DOC/'NativeRigCanonical.json').write_text(json.dumps(meta,indent=2))
    return arm,mesh,walk,meta

def apply_world(arm,world):
    # Resolve basis directly: assigning pb.matrix sequentially may read stale
    # parent evaluation in background Blender and corrupt the child pose.
    for b in arm.pose.bones:
        rest=b.bone.matrix_local
        desired=world[b.name]
        if b.parent:
            rest=b.parent.bone.matrix_local.inverted()@rest
            desired=world[b.parent.name].inverted()@desired
        b.matrix_basis=rest.inverted()@desired
    bpy.context.view_layer.update()

def capture_world(arm):return {b.name:b.matrix.copy() for b in arm.pose.bones}

def key_pose(arm,frame):
    for b in arm.pose.bones:
        b.rotation_mode='QUATERNION'
        b.keyframe_insert('location',frame=frame,group=b.name)
        b.keyframe_insert('rotation_quaternion',frame=frame,group=b.name)
        b.keyframe_insert('scale',frame=frame,group=b.name)

def export_clip(arm,mesh,path,start,end,fps=60,include_mesh=True):
    scene=bpy.context.scene;scene.frame_start=start;scene.frame_end=end;scene.render.fps=fps
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True)
    if include_mesh:mesh.select_set(True)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'ARMATURE','MESH'} if include_mesh else {'ARMATURE'},
      axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',
      add_leaf_bones=False,use_armature_deform_only=False,bake_anim=True,bake_anim_use_all_bones=True,
      bake_anim_use_nla_strips=False,bake_anim_use_all_actions=False,bake_anim_force_startend_keying=True,
      bake_anim_step=1.0,bake_anim_simplify_factor=0.0,path_mode='AUTO')

if __name__=='__main__':
    arm,mesh,walk,meta=load_rig()
    print('CANONICAL',json.dumps({k:v for k,v in meta.items() if k not in ('bones','rest_world')}))
