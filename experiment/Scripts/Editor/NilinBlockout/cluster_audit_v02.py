import sys,importlib,unreal,json
sys.path.insert(0,r'D:\game design\experiment\Scripts\Editor\NilinBlockout')
import cluster_v02
importlib.reload(cluster_v02)
unreal.log('NILIN_CLUSTER_PREFLIGHT '+json.dumps(cluster_v02.main(audit_only=True)))
