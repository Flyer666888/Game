"""Persist V09 scene enrichment in a separate level, using real collision."""
import unreal,sys,os,json,math,hashlib,importlib,datetime
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v04')
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV09'
ASSET='/Game/ReversedScale/Blockout/V09'
TAG='NLEnrichV04'
sys.path.insert(0,BASE)
import ue_mesh_v02,terrain_enrichment_v04,architecture_enrichment_v04
importlib.reload(terrain_enrichment_v04);importlib.reload(architecture_enrichment_v04)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.EditorAssetLibrary

def vec(p):return unreal.Vector(*[float(x)*100 for x in p])
class Scene:
    def __init__(self):self.materials={};self.clusters={};self.records=[];self.group='Architecture'
    def tag(self,a,name):
        a.set_actor_label('NB4_'+name)
        a.set_folder_path('Nilin_V09/'+self.group)
        a.set_editor_property('tags',[unreal.Name(TAG)])
        return a
    def mat(self,key):
        if key not in self.materials:
            path=ASSET+'/Materials/M_'+key
            m=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Game/ReversedScale/Blockout/V06/Materials/M_'+key,path)
            if not m:raise RuntimeError('Unknown material '+key)
            unreal.MaterialEditingLibrary.set_base_material_usage(m,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES,True)
            unreal.MaterialEditingLibrary.recompile_material(m)
            if not assets.save_loaded_asset(m,False):raise RuntimeError('Material not saved')
            self.materials[key]=m
        return self.materials[key]
    def instance(self,name,p,size,mat,collision,rotation):
        key=(mat,collision,self.group)
        if key not in self.clusters:
            a=self.tag(actors.spawn_actor_from_class(unreal.load_class(None,'/Script/experiment.NLBlockoutMeshCluster'),unreal.Vector()),'Cluster_'+self.group+'_'+mat+('_Solid' if collision else '_Trim'))
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
            c.set_material(0,self.mat(mat));c.set_mobility(unreal.ComponentMobility.STATIC)
            c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
            c.set_editor_property('can_ever_affect_navigation',collision)
            self.clusters[key]=(a,c)
        c=self.clusters[key][1]
        idx=c.add_instance(unreal.Transform(location=vec(p),rotation=rotation,scale=unreal.Vector(*size)),world_space=True)
        self.records.append({'name':name,'type':'box','center':p,'size':size,'rotation':[rotation.pitch,rotation.yaw,rotation.roll],'material':mat,'collision':collision,'cluster':self.clusters[key][0].get_actor_label(),'index':idx})
        return idx
    def box(self,name,p,size,mat='Stone',collision=True,yaw=0):
        return self.instance(name,p,size,mat,collision,unreal.Rotator(yaw=yaw))
    def beam(self,name,a,b,width=.3,depth=None,mat='Wood',collision=True):
        return self.instance(name,tuple((x+y)*.5 for x,y in zip(a,b)),(math.dist(a,b),width,depth or width),mat,collision,unreal.MathLibrary.find_look_at_rotation(vec(a),vec(b)))
    def part(self,name,vertices,triangles,mat='Roof',collision=True):
        digest=hashlib.sha1(json.dumps([vertices,triangles,collision]).encode()).hexdigest()[:9]
        # Separate rock render vertices retain the intended plane changes.
        if mat.startswith('Cliff'):
            vertices=[vertices[i] for t in triangles for i in t]
            triangles=[(i,i+1,i+2) for i in range(0,len(vertices),3)]
        mesh=ue_mesh_v02.make_asset(ASSET+'/Meshes/SM_'+name+'_'+digest,vertices,triangles,collision)
        a=self.tag(actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector()),name)
        c=a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(mesh);c.set_material(0,self.mat(mat))
        c.set_mobility(unreal.ComponentMobility.STATIC)
        c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
        self.records.append({'name':name,'type':'mesh','asset':mesh.get_path_name(),'triangles':len(triangles),'material':mat,'collision':collision,'bounds':[[min(p[k] for p in vertices) for k in range(3)],[max(p[k] for p in vertices) for k in range(3)]]})
        return a

def main():
    if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Open independent V09 before editing')
    for a in list(actors.get_all_level_actors()):
        if a.actor_has_tag(TAG):actors.destroy_actor(a)
    scene=Scene();scene.group='Terrain'
    terrain=terrain_enrichment_v04.build(scene)
    scene.group='Architecture'
    architecture=architecture_enrichment_v04.build(scene)
    spec=json.load(open(os.path.join(ROOT,'Docs','LevelDesign','Blockout_v03','LayoutSpec.json'),encoding='utf-8'))
    spec['map']=MAP;spec['version']='V09 mountain and Chinese architecture enrichment'
    scene.group='Cameras'
    camera={'name':'CAM_14_AlchemyElevated','position':[45,255,96],'target':[0,313,84],'fov':67}
    cam=scene.tag(actors.spawn_actor_from_class(unreal.CameraActor,vec(camera['position']),unreal.MathLibrary.find_look_at_rotation(vec(camera['position']),vec(camera['target']))),camera['name'])
    cam.set_actor_label('NB_'+camera['name']+'_V09')
    comp=cam.get_component_by_class(unreal.CameraComponent)
    comp.set_editor_property('field_of_view',camera['fov']);comp.set_editor_property('constrain_aspect_ratio',False)
    template=next(a for a in actors.get_all_level_actors() if isinstance(a,unreal.CameraActor) and 'CAM_03_Alchemy' in a.get_actor_label())
    comp.set_editor_property('post_process_settings',template.get_component_by_class(unreal.CameraComponent).get_editor_property('post_process_settings'))
    comp.set_editor_property('post_process_blend_weight',1.0)
    spec['cameras'].append(dict(camera,label=cam.get_actor_label()))
    spec['enrichment']={'terrain':terrain,'architecture':architecture}
    if not level.save_current_level():raise RuntimeError('V09 save failed')
    json.dump(spec,open(os.path.join(OUT,'LayoutSpec.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    report={'map':MAP,'saved':True,'time':datetime.datetime.now().isoformat(),'actor_count':len(actors.get_all_level_actors()),'new_clusters':len(scene.clusters),'new_instances':sum(c.get_instance_count() for _,c in scene.clusters.values()),'records':scene.records,'terrain':terrain,'architecture':architecture}
    json.dump(report,open(os.path.join(OUT,'SceneBuild.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.log('NILIN_V09_BUILD_SAVED')
main()
