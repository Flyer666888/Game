import os
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
for name in ('fix_instance_materials_v02.py','adjust_final_cameras_v02.py','add_approach_guide_v02.py','readback_v02.py'):
    path=os.path.join(BASE,name)
    exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
