from pathlib import Path
P=Path(r'D:/game design/experiment')
src=(P/'Scripts/Editor/HandGripPolish1104/FitRenderCandidates.py').read_text()
src=src.replace("exec(compile(src,__file__,'exec'))", "pass")
exec(compile(src,__file__,'exec'))
src=src.replace("for label,kind,index in [('FitB','idle',0),('FitC','idle',0)]:", "for label,kind,index in [('FitB','idle',0)]:")
src=src.replace("scene.render.filepath=str(O/f'Geometry_{label}_{view}.png');bpy.ops.render.render(write_still=True)","pass")
src=src.replace("out['frames'].append(row)","out['frames'].append(row)\n clearance(coords,faces,mapping,weapon,g,label)")
def clearance(coords,faces,mapping,weapon,g,label):
 from mathutils.bvhtree import BVHTree
 import math
 tree=BVHTree.FromPolygons(coords,[[mapping[i] for i in f] for f in faces],all_triangles=False)
 def distance(v):
  co,n,i,d=tree.find_nearest(v);return float(d)*(1 if (v-co).dot(n)>=0 else -1)
 evaluated=[]
 for v in weapon.data.vertices:
  p=v.co
  if abs(p.z)<5.0 and math.hypot(p.x,p.y)<1.5:
   pos=weapon.matrix_world@p;evaluated.append({'source':list(p),'hand':list(pos),'clearance_m':distance(pos)})
 inside=[e for e in evaluated if e['clearance_m']<-.0005]
 def inside_votes(p):
  votes=[]
  for d in [(0,1,0),(.13,1,.17),(-.19,1,.12),(.11,1,-.23),(-.21,1,-.18)]:
   direction=Vector(d).normalized();origin=Vector(p);count=0
   for repeat in range(40):
    co,n,i,dist=tree.ray_cast(origin,direction,.5)
    if co is None:break
    count+=1;origin=co+direction*.000001
   votes.append(count%2)
  return sum(votes)
 for e in inside:e['inside_votes']=inside_votes(e['hand'])
 confirmed=[e for e in inside if e['inside_votes']>=4]
 axes=[]
 for s in range(-40,41,5):
  p=weapon.matrix_world@Vector((0,0,s/10));axes.append({'local_z_cm':s/10,'hand':list(p),'clearance_m':distance(p)})
 report={'candidate':label,'handle_vertices_checked':len(evaluated),'vertices_below_minus_0_5mm':len(inside),'confirmed_inside_4of5_ray_parity':len(confirmed),'confirmed_max_depth_m':max([-e['clearance_m'] for e in confirmed],default=0),'min_surface_clearance_m':min(e['clearance_m'] for e in evaluated),'worst':sorted(confirmed,key=lambda e:e['clearance_m'])[:12],'axis':axes,'method':'Actual weighted hand mesh and sword vertices. Closest-triangle normal signed distances can disagree near folded surfaces; 5 ray-parity samples check suspected points. Use rendered multi-angle UE review as acceptance.'}
 (O/('FitClearance'+label+'Report.json')).write_text(json.dumps(report,indent=2))
exec(compile(src,__file__,'exec'))
axis=Vector((1,.2,-.25)).normalized()
weapon.matrix_world.translation+=axis*.012
clearance(coords,faces,mapping,weapon,g,'B2')
candidate=json.loads((O/'FitCandidateB.json').read_text());candidate['grip']['p']=[axis.x*.012,-.048-axis.y*.012,.046+axis.z*.012];candidate['fit_parameters']['axial_slide_m']=.012
(O/'FitCandidateB2.json').write_text(json.dumps(candidate,indent=2))
me=bpy.data.meshes.new('B2HandMesh');me.from_pydata(coords,[],[[mapping[i] for i in f] for f in faces]);me.update();hand=bpy.data.objects.new('B2Hand',me);bpy.context.collection.objects.link(hand);hand.data.materials.append(skin)
for p in me.polygons:p.use_smooth=True
for view,location in [('Side',(0,.07,.35)),('Oblique',(.3,.3,.25))]:
 cam.location=location;cam.rotation_euler=(Vector((0,.07,.025))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(O/f'Geometry_FitB2_{view}.png');bpy.ops.render.render(write_still=True)
