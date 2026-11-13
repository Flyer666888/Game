"""Read-only analytic endpoint seam review. This is not a UE collision test."""
from pathlib import Path
import math,json,hashlib,html,subprocess
BASE=Path(__file__).resolve().parent.parent
source=BASE/'LayoutSpec.json';raw=source.read_bytes();data=json.loads(raw)
flights={s['name']:s for s in data['stairs']};rests={r['name']:r for r in data['rests']}
summit=next(p for p in data['platforms'] if p['name'].startswith('D_'))

def cross_section(stair,point):
    a,b=stair['a'],stair['b'];length=math.dist(a[:2],b[:2])
    return point,[-(b[1]-a[1])/length,(b[0]-a[0])/length],[-stair['width']/2,stair['width']/2]
def rect_interval(p,n,limits,rect):
    lo,hi=limits;center=rect['center'];size=rect['size']
    for axis in (0,1):
        lower=center[axis]-size[axis]/2;upper=center[axis]+size[axis]/2
        if abs(n[axis])<1e-12:
            if not lower<=p[axis]<=upper:return None
        else:
            l,h=sorted(((lower-p[axis])/n[axis],(upper-p[axis])/n[axis]));lo=max(lo,l);hi=min(hi,h)
    return [lo,hi] if hi>=lo else None
def circle_interval(p,n,limits,row):
    q=[p[i]-row['center'][i] for i in (0,1)]
    b=2*sum(q[i]*n[i] for i in (0,1));c=sum(v*v for v in q)-row['radius']**2;disc=b*b-4*c
    if disc<0:return None
    lo=max(limits[0],(-b-math.sqrt(disc))/2);hi=min(limits[1],(-b+math.sqrt(disc))/2)
    return [lo,hi] if hi>=lo else None

report={'source':str(source),'source_sha256':hashlib.sha256(raw).hexdigest(),
        'scope':'Intersections of ideal exported stair-end cross sections with landing/court XY footprints. Ignores tread mesh overhang, rail geometry and capsule sweeps; not a collision or passability result.',
        'seams':[]}
pairs=[('C_to_Ridge','RidgeLanding'),('Ridge_to_Node06','Node06_BridgeLanding'),('Node06_to_Upper','UpperLanding'),('Upper_to_Summit','D_SummitFloor')]
for name,target in pairs:
    s=flights[name];p,n,limits=cross_section(s,s['b']);floor=summit if target=='D_SummitFloor' else rests[target]
    interval=circle_interval(p,n,limits,floor) if floor.get('shape')=='circle' else rect_interval(p,n,limits,floor)
    report['seams'].append({'flight':name,'floor':target,'endpoint':p,'stair_width_m':s['width'],
        'supported_endpoint_cross_section_width_m':0 if interval is None else interval[1]-interval[0],
        'lateral_interval_m':interval,'height_matches':abs(p[2]-floor['center'][2])<.001})
s=flights['C_to_Ridge'];p,n,limits=cross_section(s,s['a']);interval=rect_interval(p,n,limits,rests['C_EastExit'])
report['C_entry']={'endpoint':p,'exit_floor':rests['C_EastExit'],
    'supported_start_cross_section_width_m':0 if interval is None else interval[1]-interval[0]}
(BASE/'WorkingComparison'/'GeometryReview.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
ss=['V07 首轮平面几何审阅（非最终）','源SHA256：'+report['source_sha256'],
    '此处只计算导出阶梯端点横截面与地板XY轮廓的相交宽度，不替代UE网格碰撞或角色运动。','']
for r in report['seams']:
    ss.append(f'{r["flight"]} → {r["floor"]}：阶梯宽{r["stair_width_m"]:.2f}m，端点横截面与落台交叠{r["supported_endpoint_cross_section_width_m"]:.2f}m，高程'+('一致。' if r['height_matches'] else '不同。'))
ss+=['','中心路线在平面上连续，C出口与院坪连接合理，未发现炉或右丹房占据中心出入口。',
     'Ridge/Upper的到达端偏落台边角；D到达端在圆台南切点。若角色沿阶梯边侧向前，支撑范围可能突然收窄，适合加桥头收口或使末端更深入落台/圆台。',
     '已有861地板/8节点胶囊/12坐站目标视线通过记录属于UE实测；本文观察只补充横向边缘收口，不能据此声称碰撞失败。']
(BASE/'WorkingComparison'/'平面几何审阅.txt').write_text('\n'.join(ss)+'\n',encoding='utf-8')
print(json.dumps(report['seams'],ensure_ascii=False))

# A clipped, true-top-down detail board makes the edge-support observation reviewable.
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="1300" viewBox="0 0 2000 1300">',
     '<rect width="2000" height="1300" fill="#f1ecd9"/>',
     '<g font-family="Microsoft YaHei,sans-serif" fill="#284d47">',
     '<text x="55" y="64" font-size="35" font-weight="700">V07 上层桥头平面收口 · 首轮审阅</text>',
     '<text x="55" y="105" font-size="22" fill="#a35c4c">读取当前真实参数；分析端点横截面，不是UE碰撞失败判定。后续变更后需重算。</text>']
titles=['88m 岭上落台','104m 桥路落台','122m 上层落台','132m 峰顶圆台']
for idx,review in enumerate(report['seams']):
    name=review['flight'];s=flights[name];floor=summit if review['floor']=='D_SummitFloor' else rests[review['floor']]
    x=50+(idx%2)*975;y=140+(idx//2)*550
    svg.append(f'<rect x="{x}" y="{y}" width="925" height="515" rx="16" fill="#e6e7d2" stroke="#a5b497"/>')
    svg.append(f'<text x="{x+25}" y="{y+42}" font-size="28" font-weight="700">{titles[idx]}</text>')
    svg.append(f'<text x="{x+25}" y="{y+74}" font-size="20">{html.escape(name)} → {review["floor"]}</text>')
    b=s['b'];a=s['a'];length=math.dist(a[:2],b[:2]);u=[(b[i]-a[i])/length for i in (0,1)];n=[-u[1],u[0]]
    scale=27
    def xy(p):return (x+480-(p[0]-b[0])*scale,y+278-(p[1]-b[1])*scale)
    def dpath(points):return 'M'+' L'.join(f'{px:.2f} {py:.2f}' for px,py in map(xy,points))+' Z'
    clip='seam'+str(idx)
    svg.append(f'<clipPath id="{clip}"><rect x="{x+20}" y="{y+90}" width="885" height="330" rx="8"/></clipPath><g clip-path="url(#{clip})">')
    if floor.get('shape')=='circle':
        cx,cy=xy(floor['center']);svg.append(f'<circle cx="{cx}" cy="{cy}" r="{floor["radius"]*scale}" fill="#d0dac1" stroke="#709076" stroke-width="3"/>')
    else:
        c=floor['center'];w,h=floor['size'];cx,cy=xy(c)
        svg.append(f'<rect x="{cx-w*scale/2}" y="{cy-h*scale/2}" width="{w*scale}" height="{h*scale}" fill="#d0dac1" stroke="#709076" stroke-width="3"/>')
    tail=[b[i]-u[i]*12 for i in (0,1)];hw=s['width']/2
    strip=[[tail[i]+n[i]*hw for i in (0,1)],[b[i]+n[i]*hw for i in (0,1)],
           [b[i]-n[i]*hw for i in (0,1)],[tail[i]-n[i]*hw for i in (0,1)]]
    svg.append(f'<path d="{dpath(strip)}" fill="#d7bc83" fill-opacity=".7" stroke="#b58a49" stroke-width="2"/>')
    for j in range(1,21):
        p=[b[i]-u[i]*j*.55 for i in (0,1)];p1=xy([p[i]+n[i]*hw for i in (0,1)]);p2=xy([p[i]-n[i]*hw for i in (0,1)])
        svg.append(f'<path d="M{p1[0]} {p1[1]} L{p2[0]} {p2[1]}" stroke="#ab9a6e" stroke-width="1"/>')
    p1=xy([b[i]+n[i]*hw for i in (0,1)]);p2=xy([b[i]-n[i]*hw for i in (0,1)])
    svg.append(f'<path d="M{p1[0]} {p1[1]} L{p2[0]} {p2[1]}" stroke="#a75b49" stroke-width="7"/>')
    if review['lateral_interval_m']:
        t0,t1=review['lateral_interval_m'];p1=xy([b[i]+n[i]*t0 for i in (0,1)]);p2=xy([b[i]+n[i]*t1 for i in (0,1)])
        svg.append(f'<path d="M{p1[0]} {p1[1]} L{p2[0]} {p2[1]}" stroke="#218774" stroke-width="9"/>')
    cx,cy=xy(b);tx,ty=xy(tail)
    svg.append(f'<path d="M{tx} {ty} L{cx} {cy}" stroke="#684c2e" stroke-width="2" stroke-dasharray="7 6"/><circle cx="{cx}" cy="{cy}" r="7" fill="#f1ecd9" stroke="#284d47" stroke-width="2"/></g>')
    width=review['supported_endpoint_cross_section_width_m']
    svg.append(f'<text x="{x+25}" y="{y+456}" font-size="22">阶梯{review["stair_width_m"]:g}m；端部横截面与落台交叠约{width:.2f}m；高程一致。</text>')
    svg.append(f'<text x="{x+25}" y="{y+491}" font-size="20" fill="#647d70">b = ({b[0]:g}, {b[1]:g}, {b[2]:g})m　浅绿地板 / 金阶梯 / 红末端 / 青交叠</text>')
svg+=['<text x="55" y="1265" font-size="20" fill="#647d70">世界-X向图右、+Y向图上；未计踏步网格微量超出、栏杆、胶囊运动。源SHA '+report['source_sha256'][:16]+'</text>','</g></svg>']
out=BASE/'WorkingComparison';svg_path=out/'桥头收口审阅.svg';svg_path.write_text('\n'.join(svg),encoding='utf-8')
runtime=Path(r'C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies')
js='const sharp=require('+json.dumps(str(runtime/'node/node_modules/sharp'))+');sharp('+json.dumps(str(svg_path),ensure_ascii=False)+').png().toFile('+json.dumps(str(out/'桥头收口审阅.png'),ensure_ascii=False)+');'
render=out/'render_seams.cjs';render.write_text(js,encoding='utf-8');subprocess.run([str(runtime/'node/bin/node.exe'),str(render)],check=True)
