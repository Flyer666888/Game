import os
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
for name in ('validate_v03.py','audit_edges_v03.py','audit_pressure_v03.py','readback_v03.py'):
    path=os.path.join(BASE,name)
    exec(compile(open(path,encoding='utf-8-sig').read(),path,'exec'),{'__name__':'__main__'})
