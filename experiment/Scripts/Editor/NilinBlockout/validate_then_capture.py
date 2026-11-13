import os
base=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
for name in ('validate_blockout.py','capture_blockout.py'):
    path=os.path.join(base,name)
    exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
