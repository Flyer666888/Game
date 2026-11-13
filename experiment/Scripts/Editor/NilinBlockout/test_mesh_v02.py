import sys,json,os,unreal
sys.path.insert(0,r'D:\game design\experiment\Scripts\Editor\NilinBlockout')
import mesh_shapes_v02,ue_mesh_v02
v,t=mesh_shapes_v02.roof(34,12,3.2)
asset=ue_mesh_v02.make_asset('/Game/ReversedScale/Blockout/V07/Meshes/SM_ShanmenRoof',v,t)
json.dump({'path':asset.get_path_name(),'vertices':len(v),'triangles':len(t)},open(r'D:\game design\experiment\Docs\LevelDesign\Blockout_v02\MeshTrial.json','w'),indent=2)
unreal.log('NILIN_V02_MESH_TRIAL_OK')
