import sys,bpy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from new_rig_common import load_rig,OUT
arm,mesh,walk,meta=load_rig()
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.fbx(filepath=str(OUT/'NativeMesh.fbx'),use_selection=True,
 object_types={'ARMATURE','MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,
 apply_scale_options='FBX_SCALE_NONE',add_leaf_bones=False,use_armature_deform_only=False,
 bake_anim=False,path_mode='AUTO')
print('NATIVE_MESH_EXPORTED',str(OUT/'NativeMesh.fbx'))
