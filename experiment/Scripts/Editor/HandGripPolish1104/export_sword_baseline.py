import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104';A=unreal.EditorAssetLibrary
mesh=A.load_asset('/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player')
b=mesh.get_bounds()
data={'mesh':mesh.get_path_name(),'materials':[{'slot':str(s.material_slot_name),'imported_slot':str(s.get_editor_property('imported_material_slot_name')),'material':s.material_interface.get_path_name()} for s in mesh.static_materials],
      'bounds':{'origin':list(b.origin.to_tuple()),'extent':list(b.box_extent.to_tuple())},'triangles':mesh.get_num_triangles(0),'uv_channels':mesh.get_num_tex_coords(0)}
data['sha256']=hashlib.sha256((P/'Content/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player.uasset').read_bytes()).hexdigest()
(O/'SwordBaseline.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
