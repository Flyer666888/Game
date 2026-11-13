"""Read back real collision across stair widths and newly designed bridgeheads."""
import os,json,math,datetime,unreal
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v03'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV08'

def main():
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Open V07 for edge audit')
    world=editor.get_editor_world();data=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'))
    failures=[];counts={};examples=[]
    # This query verifies supporting floor coverage, underneath guardrails.
    # Guardrails retain BlockAll in the map; real CharacterMovement is audited separately.
    ignore=[]
    for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
        label=a.get_actor_label()
        if label.startswith(('NB_RailPost_','NB_PostCap_','NB_Balustrade_','NB_Handrail_')):ignore.append(a)
        elif a.actor_has_tag('NLBlockout.ClusterV02'):
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            if c and all(c.get_material(i) and c.get_material(i).get_name()=='M_Stone' for i in range(c.get_num_materials())):ignore.append(a)
    def sample(p,kind):
        counts[kind]=counts.get(kind,0)+1
        vec=lambda q:unreal.Vector(*[v*100 for v in q])
        hit=unreal.SystemLibrary.line_trace_single(world,vec((p[0],p[1],p[2]+.8)),vec((p[0],p[1],p[2]-1.5)),unreal.TraceTypeQuery.ECC_VISIBILITY,False,ignore,unreal.DrawDebugTrace.NONE)
        values=hit.to_tuple() if hit else None
        z=values[5].z/100 if values else None
        if z is None or abs(z-p[2])>.205:
            failures.append({'kind':kind,'p':p,'hit_z':z,'actor':values[9].get_actor_label() if values and values[9] else None})
    cursor=0
    for s in data['stairs']:
        dx,dy=s['b'][0]-s['a'][0],s['b'][1]-s['a'][1];length=math.hypot(dx,dy);n=(-dy/length,dx/length)
        count=s['steps']+s['landings'];points=data['route'][cursor:cursor+count];cursor+=count
        for p in points:
            for f in (-.46,-.23,0,.23,.46):sample((p[0]+n[0]*s['width']*f,p[1]+n[1]*s['width']*f,p[2]),'stair_width')
        if s['name'] in ('Threshold_to_C','C_to_Ridge','Ridge_to_Node06','Node06_to_Upper','Upper_to_Summit'):
            for p in (s['a'],s['b']):
                for f in (-.46,-.23,0,.23,.46):sample((p[0]+n[0]*s['width']*f,p[1]+n[1]*s['width']*f,p[2]),'upper_end_caps')
    for r in data.get('bridgeheads',[]):
        a=r['start'];u=r['inward'];n=(-u[1],u[0]);length,width=r['size']
        for i in range(9):
            for j in range(7):
                run=length*(.02+.96*i/8);lateral=width*(-.45+.9*j/6)
                sample((a[0]+u[0]*run+n[0]*lateral,a[1]+u[1]*run+n[1]*lateral,a[2]),'bridgeheads')
    report={'map':MAP,'checked_at':datetime.datetime.now().isoformat(),'source':'Actual UE visibility collision traces','counts':counts,'samples':sum(counts.values()),'failure_count':len(failures),'failures':failures,'success':not failures,'ignored_guardrail_actors_for_floor_query':len(ignore),'scope':'Supporting floors sampled at five lateral positions, endpoint caps and bridgehead grids, with guardrails ignored only by this floor query. Guardrails keep real BlockAll collision; usable walking clearance is verified separately by PIE. Does not certify every possible player position.'}
    json.dump(report,open(os.path.join(OUT,'EdgeAudit.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.log('NILIN_EDGE_AUDIT '+str(report['success'])+' '+str(report['samples']))
main()

