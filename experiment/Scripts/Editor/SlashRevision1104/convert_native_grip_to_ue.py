"""Use the measured UE reference bone, including FBX scale and orientation."""
import json
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
P=Path(r'D:/game design/experiment');D=P/'Docs/Gameplay/SlashRevision1104'
native=json.loads((D/'NativeRigCanonical.json').read_text());ue=json.loads((D/'NativeUEReference.json').read_text())
candidate=json.loads((D/'Grip/Candidate.json').read_text())
hand=Matrix(native['rest_world']['mixamorig:RightHand']);r=ue['rest']['RightHand']
U=Matrix.LocRotScale(Vector(r['p']),Quaternion((r['q'][3],*r['q'][:3])),Vector(r['s']))
g=candidate['quaternion_xyzw'];G=Matrix.LocRotScale(Vector(candidate['socket_cm'])*.01,Quaternion((g[3],*g[:3])),Vector((1,1,1)))
H=Matrix.Diagonal((1,-1,1,1));desired=Matrix.Scale(100,4)@H@hand@G@Matrix.Scale(.01,4)@H
attach=U.inverted()@desired;p,q,s=attach.decompose();readback=U@attach
report={'blade_local_axes':{'tip':[0,0,1],'cutting_edge':[-1,0,0],'face_normal':[0,1,0]},
 'blender':{'bone':'mixamorig:RightHand','translation_m':list(G.translation),'quaternion_wxyz':list(G.to_quaternion()),'finger_basis_local_x_degrees':candidate['angles']},
 'unreal':{'bone':'RightHand','translation':list(p),'quaternion_xyzw':[q.x,q.y,q.z,q.w],'scale':list(s)},
 'expected_reference_sword_transform_cm':{'p':list(desired.translation),'q_xyzw':[desired.to_quaternion().x,desired.to_quaternion().y,desired.to_quaternion().z,desired.to_quaternion().w],'s':list(desired.to_scale())},
 'maximum_roundtrip_matrix_error':max(abs(readback[i][j]-desired[i][j]) for i in range(4) for j in range(4)),
 'note':'UE local translation is small because the native imported reference bones carry scale 100; 0.01 grip scale cancels it for the existing centimetre weapon mesh. Finger pose assessed in three offline views; runtime socket and active cutting polarity still require imported animation validation.'}
(D/'NativeSwordGrip.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
