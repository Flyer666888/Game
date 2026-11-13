import os
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
for name in ('check_scene_v04.py','runtime_walk_v04.py'):
    path=os.path.join(BASE,name)
    exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
