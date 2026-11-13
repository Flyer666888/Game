import unreal,sys,importlib,os,json
sys.path.insert(0,r'D:\game design\experiment\Scripts\Editor\NilinBlockout')
import optimize_v02 as opt
importlib.reload(opt)
m=opt.cloud_material()
count=0
for a in opt.actors.get_all_level_actors():
    if a.get_actor_label().startswith('NB2_LowCloudBank_'):
        a.get_component_by_class(unreal.StaticMeshComponent).set_material(0,m);count+=1
if not opt.levels.save_current_level():raise RuntimeError('Cloud correction save failed')
json.dump({'material':m.get_path_name(),'clouds':count,'source_fix':'OneMinus default input connected and checked'},open(os.path.join(opt.OUT,'CloudCorrection.json'),'w'),indent=2)
