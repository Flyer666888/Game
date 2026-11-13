from pathlib import Path
base=Path(r'D:\game design\experiment\Scripts\Editor\NilinBlockout')
for name in ('build_blockout.py','refine_final.py','present_blockout.py','validate_blockout.py'):
    exec(compile((base/name).read_text(encoding='utf-8'),str(base/name),'exec'),{'__name__':'__main__'})
