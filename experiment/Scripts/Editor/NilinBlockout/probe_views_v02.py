import unreal,json,os,math
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v02'
def main():
    w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    d=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'));p=next(p for p in d['platforms'] if p['name'].startswith('D_'));x,y,z=p['center'];r=30
    targets=[(x+t,y-math.sqrt(r*r-t*t),z+.2) for t in (-24,-18,-12,-6,0,6,12,18,24)];crown=(x,y+20,158)
    vec=lambda p:unreal.Vector(*[v*100 for v in p])
    def visible(a,b):
        h=unreal.SystemLibrary.line_trace_single(w,vec(a),vec(b),unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
        return not h or (h.to_tuple()[9] and '05_SummitSeal' in str(h.to_tuple()[9].get_folder_path()))
    result={}
    for index,xs,ys,z in ((4,[-8.4,-8,-7.6,-7.2,-6.8,-6.4],[199,199.4,199.8,200.2,200.6],44),(6,[-114.8,-114.4,-114,-113.6,-113.2,-112.8,-112.4,-112,-111.6,-111.2,-110.8],[404.5,405,405.5,406,406.5,407,407.5,408,408.5,409],104)):
        rows=[]
        for px in xs:
            for py in ys:
                h=unreal.SystemLibrary.capsule_trace_single(w,vec((px,py,z+.93)),vec((px,py,z+.94)),30,90,unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
                if h:continue
                checks=[]
                for eye in (1.1,1.7):
                    a=(px,py,z+eye);v=[bool(visible(a,t)) for t in targets]
                    checks.append({'eye':eye,'peak':sum(v),'crown':bool(visible(a,crown)),'rim_segment':any(a and b for a,b in zip(v,v[1:]))})
                if all(c['peak'] and c['crown'] for c in checks):rows.append({'ground':[px,py,z],'checks':checks,'score':sum(c['peak'] for c in checks)})
        result[str(index)]=sorted(rows,key=lambda r:-r['score'])
    json.dump(result,open(os.path.join(OUT,'ViewpointCandidates.json'),'w'),indent=2)
main()
