import os,sys,unreal,importlib,json
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
for name in ('validate_v02.py','audit_edges_v02.py'):
    path=os.path.join(BASE,name)
    exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
sys.path.insert(0,BASE)
import cluster_v02
importlib.reload(cluster_v02)
unreal.log('NILIN_CLUSTER_PREFLIGHT '+json.dumps(cluster_v02.main(audit_only=True)))
