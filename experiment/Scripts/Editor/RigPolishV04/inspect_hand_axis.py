from pathlib import Path
p=Path(r'D:\game design\experiment\Scripts\Editor\RigPolishV04\bake_natural_attack.py')
exec(compile(p.read_text(encoding='utf-8').split('samples=[];rows=[]')[0],str(p),'exec'),globals())
palm=(reference['hand_r'].to_quaternion()@Vector((-.2040,-.8414,-.50046))).normalized()
axis=neutral_blade.cross(ref_forearm).normalized()
for deg in (-20,-15,0,15,20,25):
    rot=Quaternion(axis,math.radians(deg));pp=rot@palm;bb=rot@neutral_blade
    print('HAND_ROT',deg,'palm_axis',list(pp),'palm_forearm',math.degrees(pp.angle(ref_forearm)),'sword_forearm',math.degrees(bb.angle(ref_forearm)),flush=True)
print('WRIST_SWING_AXIS_LOCAL',list(reference['hand_r'].to_quaternion().inverted()@axis),flush=True)
