import os
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
for name in ('validate_v02.py','audit_edges_v02.py'):
    path=os.path.join(BASE,name)
    exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
