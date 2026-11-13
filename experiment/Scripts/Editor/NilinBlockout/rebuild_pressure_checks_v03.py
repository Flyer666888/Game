import os
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
for name in ('build_pressure_v03.py','final_pressure_checks_v03.py','runtime_walk_v03.py'):
    path=os.path.join(BASE,name)
    exec(compile(open(path,encoding='utf-8-sig').read(),path,'exec'),{'__name__':'__main__'})
