import json
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
p=Path(r'D:/game design/experiment/Docs/Gameplay/SlashRevision1104')
ue=json.loads((p/'NativeUEReference.json').read_text())['rest']['Head']
ref=Matrix(json.loads((p/'NativeRigCanonical.json').read_text())['rest_world']['mixamorig:Head'])
guard=Matrix(json.loads((p/'SlashPoses.json').read_text())['attack']['samples'][0]['world']['mixamorig:Head'])
c=Matrix.Diagonal((1,-1,1))
ueq=Quaternion((ue['q'][3],*ue['q'][:3]))
q=(c @ (guard.to_quaternion().to_matrix()@ref.to_quaternion().inverted().to_matrix()) @ c @ ueq.to_matrix()).to_quaternion()
offset=q@Vector((0,-8.5,8));height=guard.translation.z*100+offset.z
result={'source':'SlashPoses attack time 0 matches NativeGuard and idle start','bone_head_height_cm':guard.translation.z*100,'head_rotation_xyzw':[q.x,q.y,q.z,q.w],'eye_offset_local_cm':[0,-8.5,8],'rotated_eye_offset_cm':list(offset),'neutral_eye_height_cm':height,'imported_bone_unit_scale':ue['s'],'uses_bone_scale_for_cm_offset':False,'selected_default_cm':round(height,3)}
(p/'NativeEyeHeight.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
