"""Compare V06/V07 layout parameters without importing UE or changing source specs."""
from pathlib import Path
import json, hashlib, argparse, datetime, math

HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser()
ap.add_argument('--before',type=Path,default=HERE.parent/'Blockout_v01'/'LayoutSpec.json')
ap.add_argument('--after',type=Path,default=HERE/'LayoutSpec.json')
ap.add_argument('--output',type=Path,default=HERE)
args=ap.parse_args()
old_raw=args.before.read_bytes();new_raw=args.after.read_bytes()
old=json.loads(old_raw);new=json.loads(new_raw)

def describe(rows,key,fields):
    result={};counts={}
    for row in rows:
        name=str(row[key]);counts[name]=counts.get(name,0)+1
        unique=name if counts[name]==1 else name+'#'+str(counts[name])
        result[unique]={f:row[f] for f in fields if f in row}
    return result

collections={
    'nodes':('index',('ground','yaw')),
    'platforms':('name',('center','size','shape','radius','points')),
    'rests':('name',('center','size','shape','radius','points')),
    'bridgeheads':('name',('center','size','points','rotation_yaw','associated_rest','start','inward')),
    'stairs':('name',('a','b','width','riser','tread','steps','landings')),
    'footprints':('name',('center','size','shape','radius','points','height','yaw','kind','label','facing')),
}
report={'checked_at':datetime.datetime.now().isoformat(timespec='seconds'),
        'before':{'path':str(args.before),'map':old.get('map'),'sha256':hashlib.sha256(old_raw).hexdigest()},
        'after':{'path':str(args.after),'map':new.get('map'),'sha256':hashlib.sha256(new_raw).hexdigest()},
        'scope':'Parameter comparison only. No collision, visibility, playability or performance result is inferred.',
        'collections':{},'named_points':{}}
for category,(key,fields) in collections.items():
    before=describe(old.get(category,[]),key,fields);after=describe(new.get(category,[]),key,fields)
    report['collections'][category]={'before_count':len(before),'after_count':len(after),
        'added':{k:after[k] for k in sorted(after.keys()-before.keys())},
        'removed':{k:before[k] for k in sorted(before.keys()-after.keys())},
        'changed':{k:{'before':before[k],'after':after[k]} for k in sorted(before.keys()&after.keys()) if before[k]!=after[k]}}
for field in ('friend','furnace','boss','world_mirrored_x','summit','gameplay_notes'):
    if old.get(field)!=new.get(field):report['named_points'][field]={'before':old.get(field),'after':new.get(field)}
report['node_positions_unchanged']=bool(old.get('nodes')) and bool(new.get('nodes')) and \
    describe(old['nodes'],'index',('ground',))==describe(new['nodes'],'index',('ground',))
report['stair_geometry_unchanged']=not any(report['collections']['stairs'][k] for k in ('added','removed','changed'))
report['node_heights_unchanged']={n['index']:n['ground'][2] for n in old.get('nodes',[])}=={n['index']:n['ground'][2] for n in new.get('nodes',[])}
report['rest_sizes_unchanged']=describe(old.get('rests',[]),'name',('size','radius','shape'))==describe(new.get('rests',[]),'name',('size','radius','shape'))
def platform_shapes(spec):
    result={}
    for row in spec.get('platforms',[]):
        p=row.get('center',[0,0,0]);r={f:row[f] for f in ('size','radius','shape') if f in row}
        if row.get('points'):r['local_points']=[[round(q[0]-p[0],6),round(q[1]-p[1],6)] for q in row['points']]
        result[row['name']]=r
    return result
report['combat_platform_shapes_unchanged']=platform_shapes(old)==platform_shapes(new)
def route_metrics(spec):
    stairs=spec.get('stairs',[])
    c_height=next((n['ground'][2] for n in spec.get('nodes',[]) if n['index']==5),None)
    upper=[s for s in stairs if c_height is not None and min(s['a'][2],s['b'][2])>=c_height]
    def metrics(rows):
        plateau_length=0
        for a,b in zip(rows,rows[1:]):
            candidates=[r for r in spec.get('rests',[]) if abs(r['center'][2]-a['b'][2])<.001 and abs(r['center'][2]-b['a'][2])<.001]
            plateau_length+=min((math.dist(a['b'],r['center'])+math.dist(r['center'],b['a']) for r in candidates),default=math.dist(a['b'],b['a']))
        terminal_heads=[h for h in spec.get('bridgeheads',[]) if rows and not h.get('associated_rest') and math.dist(h['start'],rows[-1]['b'])<.001]
        terminal_length=sum(h['size'][0] for h in terminal_heads)
        sloped=sum(math.dist(s['a'],s['b']) for s in rows)
        return {'runs':len(rows),'horizontal_endpoint_length_m':sum(math.dist(s['a'][:2],s['b'][:2]) for s in rows),
                'sloped_endpoint_length_m':sloped,
                'landing_connection_length_m':sum(math.dist(a['b'],b['a']) for a,b in zip(rows,rows[1:])),
                'via_rest_centres_length_m':plateau_length,'terminal_bridgehead_length_m':terminal_length,
                'ascent_via_rest_centres_and_terminal_head_m':sloped+plateau_length+terminal_length,
                'minimum_width_m':min((s['width'] for s in rows),default=None),
                'minimum_tread_m':min((s['tread'] for s in rows),default=None),
                'maximum_riser_m':max((s['riser'] for s in rows),default=None)}
    return {'all_stairs':metrics(stairs),'C_to_D_stairs':metrics(upper)}
report['route_metrics']={'before':route_metrics(old),'after':route_metrics(new),
    'definition':'Endpoint centreline lengths from exported stair runs. Landing connections are either direct endpoint distances, or explicitly via same-height rest centres plus the terminal bridgehead. Not an actual measured player trajectory.'}
for key in ('all_stairs','C_to_D_stairs'):
    before=report['route_metrics']['before'][key];after=report['route_metrics']['after'][key]
    report['route_metrics'].setdefault('change',{})[key]={
        'horizontal_length_reduction_m':before['horizontal_endpoint_length_m']-after['horizontal_endpoint_length_m'],
        'sloped_length_reduction_m':before['sloped_endpoint_length_m']-after['sloped_endpoint_length_m'],
        'centreline_with_connections_reduction_m':before['sloped_endpoint_length_m']+before['landing_connection_length_m']-after['sloped_endpoint_length_m']-after['landing_connection_length_m'],
        'ascent_via_rest_centres_and_terminal_head_reduction_m':before['ascent_via_rest_centres_and_terminal_head_m']-after['ascent_via_rest_centres_and_terminal_head_m']}
args.output.mkdir(parents=True,exist_ok=True)
(args.output/'LayoutComparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
ss=['《逆鳞》V06 / V07 实际布局参数对照',
    '旧图：'+str(old.get('map')),'新图：'+str(new.get('map')),
    '节点地面位置：'+('相同' if report['node_positions_unchanged'] else '存在差异，见JSON'),
    '阶梯路线参数：'+('相同' if report['stair_geometry_unchanged'] else '存在差异，见JSON'),
    '八节点高程：'+('相同' if report['node_heights_unchanged'] else '存在差异，见JSON'),
    '四院坪形状尺寸：'+('相同（平移不视为缩小）' if report['combat_platform_shapes_unchanged'] else '存在差异，见JSON'),
    '落台/翼台尺寸：'+('相同' if report['rest_sizes_unchanged'] else '存在差异，见JSON'),'']
upper_before=report['route_metrics']['before']['C_to_D_stairs'];upper_after=report['route_metrics']['after']['C_to_D_stairs']
upper_change=report['route_metrics']['change']['C_to_D_stairs']
ss+=[f'C→D四段阶梯端点中心线：{upper_before["sloped_endpoint_length_m"]:.2f}m → {upper_after["sloped_endpoint_length_m"]:.2f}m，缩短{upper_change["sloped_length_reduction_m"]:.2f}m。',
     f'按经同高休息面中心、并计入最终接圆桥头板的中心线口径：{upper_before["ascent_via_rest_centres_and_terminal_head_m"]:.2f}m → {upper_after["ascent_via_rest_centres_and_terminal_head_m"]:.2f}m，缩短{upper_change["ascent_via_rest_centres_and_terminal_head_reduction_m"]:.2f}m。',
     '以上来自导出阶梯端点的空间中心线计算，不等于实际玩家移动轨迹或试玩计时。','']
labels={'nodes':'节点','platforms':'院坪','rests':'落台/翼台','bridgeheads':'附加桥头过渡板','stairs':'阶梯','footprints':'主构筑物占地'}
for cat,result in report['collections'].items():
    ss.append(f'{labels[cat]}：{result["before_count"]} → {result["after_count"]}条；新增{len(result["added"])}，移除{len(result["removed"])}，变更{len(result["changed"])}。')
    for label,key in (('新增','added'),('移除','removed'),('变更','changed')):
        if result[key]:ss.append('  '+label+'：'+'、'.join(result[key]))
ss+=['','源数据SHA256：',hashlib.sha256(old_raw).hexdigest(),hashlib.sha256(new_raw).hexdigest(),
     '本报告只比较源参数，不证明新地图碰撞、视线、实际行走或性能。实际新资产和地图的完成状态以V07验收记录及真实截图为准。']
(args.output/'实际布局参数对照.txt').write_text('\n'.join(ss)+'\n',encoding='utf-8')
print(json.dumps({'node_positions_unchanged':report['node_positions_unchanged'],
    'stair_geometry_unchanged':report['stair_geometry_unchanged'],
    'after_map':new.get('map'),'output':str(args.output/'LayoutComparison.json')},ensure_ascii=False))
