"""Create an editable plan directly from the actual whitebox LayoutSpec.

No UE or image generation is invoked. Missing source geometry is disclosed, not invented.
The source specification is owned by the builder; this script never edits it.
"""
from pathlib import Path
import argparse, math, json, html, hashlib, datetime, subprocess
from PIL import Image

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--spec',type=Path,default=HERE.parent/'LayoutSpec.json')
parser.add_argument('--output',type=Path,default=HERE)
args=parser.parse_args()
raw=args.spec.read_bytes(); data=json.loads(raw)
X_SIGN=-1 if data.get('world_mirrored_x',False) else 1
OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
W,H=3600,2800
INK='#284d47'; MUTED='#647d70'; GOLD='#bb873e'; TEAL='#368e81'; RED='#a35c4c'
parts=[]
def add(s):parts.append(s)
def rect(x,y,w,h,fill,stroke='none',sw=1,r=0,extra=''):
    add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def path(d,fill='none',stroke=INK,sw=2,extra=''):
    add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round" {extra}/>')
def circle(x,y,r,fill,stroke='none',sw=1,extra=''):
    add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def text(x,y,s,size=26,col=INK,weight=400,anchor='start',extra=''):
    add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{col}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{html.escape(str(s))}</text>')
def lines(x,y,ss,size=25,col=MUTED,step=37):
    for i,s in enumerate(ss):text(x,y+i*step,s,size,col)
def group(cls):add(f'<g class="{cls}">')
def end():add('</g>')
def fmt(n):return f'{n:g}' if isinstance(n,(int,float)) else str(n)

platforms=data.get('platforms',[])
rests=data.get('rests',data.get('landings',[]))
footprints=data.get('footprints',[])
nodes=sorted(data['nodes'],key=lambda n:n['index'])
stairs=data['stairs']
court_names={'A':'山门外防','B':'演武石院','C':'守护丹台','D':'峰顶封山台'}
node_names={1:'山门外',2:'上山落台',3:'演武院',4:'丹道入口',5:'守丹台',6:'御风桥路',7:'山顶决战',8:'同台归途'}
court_meta={}
for row in platforms:
    key=str(row.get('name',''))[:1]
    if key in court_names and key not in court_meta:court_meta[key]=row
if 'D' not in court_meta and data.get('summit'):
    court_meta['D']={'name':'D_SummitFloor','shape':'circle',**data['summit']}
missing=[]
for key in court_names:
    if key not in court_meta:missing.append(f'{key} 院坪边界尚未写入 LayoutSpec')
if not footprints:missing.append('建筑占地尚未写入 LayoutSpec，本版不推测屋顶轮廓')
if not rests:missing.append('过渡落台边界尚未写入 LayoutSpec，位置由节点标明')

def centre(row):return row.get('center',row.get('p',row.get('location',[0,0,0])))
def dims(row):return row.get('size',row.get('dimensions',row.get('scale',[1,1])))
def iscircle(row):return str(row.get('shape',row.get('kind',''))).lower() in ('circle','cylinder','cyl','disk')
def ispolygon(row):return str(row.get('shape','')).lower()=='polygon' and bool(row.get('points'))
def radius(row):return float(row.get('radius',dims(row)[0]/2))
def bounds(row):
    p=centre(row)
    if ispolygon(row):
        points=row['points'];return (min(v[0] for v in points),max(v[0] for v in points),min(v[1] for v in points),max(v[1] for v in points))
    if iscircle(row):rx=ry=radius(row)
    else:
        s=dims(row);yaw=math.radians(float(row.get('yaw',0)));rx=abs(s[0]*math.cos(yaw)/2)+abs(s[1]*math.sin(yaw)/2);ry=abs(s[0]*math.sin(yaw)/2)+abs(s[1]*math.cos(yaw)/2)
    return (p[0]-rx,p[0]+rx,p[1]-ry,p[1]+ry)
def union(bb):return (min(b[0] for b in bb),max(b[1] for b in bb),min(b[2] for b in bb),max(b[3] for b in bb))
class View:
    def __init__(self,x,y,w,h,bb,pad=20,scale=None):
        self.x,self.y,self.w,self.h=x,y,w,h
        self.s=scale or min((w-2*pad)/(bb[1]-bb[0]),(h-2*pad)/(bb[3]-bb[2]))
        self.ox=x+w/2-X_SIGN*(bb[0]+bb[1])/2*self.s
        self.oy=y+h/2+(bb[2]+bb[3])/2*self.s
    def point(self,p):return self.ox+X_SIGN*p[0]*self.s,self.oy-p[1]*self.s
    def contains(self,p,margin=0):
        x,y=self.point(p);return self.x-margin<=x<=self.x+self.w+margin and self.y-margin<=y<=self.y+self.h+margin

def footprint(row,view,fill,stroke,sw=2):
    p=centre(row);x,y=view.point(p)
    if ispolygon(row):
        pp=[view.point(v) for v in row['points']]
        path('M'+' L'.join(f'{xx:.2f} {yy:.2f}' for xx,yy in pp)+' Z',fill,stroke,sw)
    elif iscircle(row):circle(x,y,radius(row)*view.s,fill,stroke,sw)
    else:
        size=dims(row);yaw=-X_SIGN*float(row.get('yaw',0))
        rect(x-size[0]*view.s/2,y-size[1]*view.s/2,size[0]*view.s,size[1]*view.s,fill,stroke,sw,2,
             extra=f'transform="rotate({yaw:.3f} {x:.2f} {y:.2f})"')
def draw_stair(row,view):
    a,b=row['a'],row['b'];ax,ay=view.point(a);bx,by=view.point(b);width=row['width']*view.s
    dx,dy=bx-ax,by-ay;nn=math.hypot(dx,dy)
    if not nn:return
    ux,uy=dx/nn,dy/nn;nx,ny=-uy,ux
    pp=[(ax+nx*width/2,ay+ny*width/2),(bx+nx*width/2,by+ny*width/2),
        (bx-nx*width/2,by-ny*width/2),(ax-nx*width/2,ay-ny*width/2)]
    path('M'+' L'.join(f'{xx:.2f} {yy:.2f}' for xx,yy in pp)+' Z','#ded7bb','#79927d',2)
    tick_count=min(row['steps'],max(2,int(nn/6)))
    for i in range(tick_count):
        t=(i+.5)/tick_count;xx=ax+dx*t;yy=ay+dy*t
        path(f'M{xx-nx*width*.43:.2f} {yy-ny*width*.43:.2f} L{xx+nx*width*.43:.2f} {yy+ny*width*.43:.2f}',stroke='#99a78b',sw=1)
def draw_facing(row,view):
    if row.get('facing') is False or iscircle(row):return
    p=centre(row);size=dims(row);yaw=math.radians(float(row.get('yaw',0)))
    front=(p[0]+math.sin(yaw)*size[1]/2,p[1]-math.cos(yaw)*size[1]/2)
    x,y=view.point(front);length=35 if view.s>5 else 18
    path(f'M{x:.2f} {y:.2f} l{X_SIGN*math.sin(yaw)*length:.2f} {math.cos(yaw)*length:.2f}',stroke=RED,sw=2.5,extra='marker-end="url(#redArrow)"')

def draw_world(view,zoom=False,key=None):
    for row in platforms:
        footprint(row,view,'url(#paving)','#708b77',3)
    for row in rests:footprint(row,view,'#d8cfad','#80987f',2)
    for row in stairs:draw_stair(row,view)
    group('building-layer')
    building_names={'Shanmen':'山门屋顶投影','OpenAlchemyPavilion':'开放高亭投影','Furnace':'巨炉占地','SealWall':'封山圆阵壁投影'}
    for row in sorted(footprints,key=lambda r:centre(r)[2] if len(centre(r))>2 else 0):
        kind=str(row.get('kind','roof')).lower()
        name=row.get('name','')
        if 'Furnace' in name:fill='#bea264'
        elif 'Seal' in name or 'wall' in kind:fill='#89998a'
        else:fill='#416c60' if 'roof' in kind or 'pavilion' in kind else '#93a28a'
        footprint(row,view,fill,'#51755f',2)
        if zoom and view.contains(centre(row)):
            x,y=view.point(centre(row));caption=row.get('label',building_names.get(name,name))
            if len(caption)>16:caption=caption[:16]
            if caption and 'Furnace' not in name:text(x,y+7,caption,20,'#ebe0b9' if fill=='#416c60' else INK,600,'middle')
            draw_facing(row,view)
    end()
    group('route-layer')
    pts=data.get('route',[])
    # The route array is stair tread samples; preserve separate stair runs instead of
    # joining across unrelated courts and inventing a floor route.
    for row in stairs:
        ax,ay=view.point(row['a']);bx,by=view.point(row['b'])
        path(f'M{ax:.2f} {ay:.2f} L{bx:.2f} {by:.2f}',stroke=GOLD,sw=3 if zoom else 4,
             extra='stroke-dasharray="12 8" marker-end="url(#goldArrow)"')
    end()
    # Named points are positions, not invented dimensioned footprints.
    group('point-layer')
    point_specs=[('furnace','炉位','#b99b59','炉'),('friend','挚友 / 法阵',TEAL,'友'),('boss','Boss',RED,'B')]
    for field,caption,col,glyph in point_specs:
        if field not in data:continue
        if not zoom and field!='furnace':continue  # Close points are resolved in the equal-scale court cards.
        p=data[field]
        if not view.contains(p,40):continue
        x,y=view.point(p);r=22 if zoom else 14
        circle(x,y,r,'#f3e7c3',col,3);text(x,y+7,glyph,20,col,700,'middle')
        if zoom:
            rect(x+r+6,y-18,len(caption)*22+18,34,'#f4ecd3',r=5,extra='fill-opacity=".96"')
            text(x+r+13,y+7,caption,22,INK,600)
    end()
    group('node-layer')
    for n in nodes:
        p=n['ground']
        if not view.contains(p,20):continue
        x,y=view.point(p);rr=18 if zoom else 17
        circle(x,y,rr,'#f2e5bd',GOLD,3)
        text(x,y+7,f'{n["index"]:02}',20,'#91662f',700,'middle')
        yaw=math.radians(n.get('yaw',90));dx,dy=X_SIGN*math.cos(yaw),-math.sin(yaw)
        path(f'M{x+dx*(rr+3):.2f} {y+dy*(rr+3):.2f} l{dx*23:.2f} {dy*23:.2f}',stroke=TEAL,sw=2,extra='marker-end="url(#tealArrow)"')
        if not zoom:
            caption=f'{node_names.get(n["index"],"节点")}  +{fmt(p[2])}m'
            # Keep node 08's annotation on the other side of the summit.
            off=-45 if n['index']==8 else 38
            anchor='end' if off<0 else 'start'
            text(x+off,y+8,caption,24,INK,600,anchor)
    end()

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('<metadata>'+html.escape(json.dumps({'source':str(args.spec),'sha256':hashlib.sha256(raw).hexdigest(),'generated_at':data.get('generated_at')},ensure_ascii=False))+'</metadata>')
add('''<defs>
<pattern id="paving" width="34" height="34" patternUnits="userSpaceOnUse"><rect width="34" height="34" fill="#d8d8ba"/><path d="M34 0H0V34" fill="none" stroke="#b7c0a4" stroke-width="1"/></pattern>
<pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" fill="none" stroke="#a6bbab" stroke-width="1" opacity=".4"/></pattern>
<marker id="goldArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#bb873e"/></marker>
<marker id="redArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#a35c4c"/></marker>
<marker id="tealArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#368e81"/></marker>
</defs>''')
add('<g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">')
rect(0,0,W,H,'#f1ecd9')
rect(77,58,8,112,GOLD)
text(111,113,'逆鳞',60,INK,700);text(300,111,'实际白模平面与登高流程',46,INK,600)
text(112,158,'L_NilinBlockoutV06  /  按 LayoutSpec 米制参数绘制  /  与旧概念图比例区分',26,MUTED)
text(3522,104,'四院坪 · 八节点 · 连续桥阶',28,INK,600,'end')
text(3522,150,'数据生成：'+str(data.get('generated_at','未记录')).replace('T',' ')[:19],23,MUTED,400,'end')
path('M78 194 H3522',stroke='#acb79b',sw=2)

rect(76,230,1578,2010,'#dce7db','#a3b7a2',2,22)
rect(76,230,1578,2010,'url(#grid)',r=22)
text(112,287,'总平面  /  统一比例',32,INK,700)
text(112,329,('−X 向图右 / +Y 上山；正立面朝 −Y' if X_SIGN<0 else '+X 向图右 / +Y 上山；正立面朝 −Y'),23,MUTED)
bb=[bounds(r) for r in platforms+rests+footprints]
bb += [(n['ground'][0],n['ground'][0],n['ground'][1],n['ground'][1]) for n in nodes]
for s in stairs:
    for p in (s['a'],s['b']):bb.append((p[0],p[0],p[1],p[1]))
bb=union(bb);bb=(bb[0]-30,bb[1]+30,bb[2]-30,bb[3]+30)
overview=View(118,365,1488,1685,bb)
add('<clipPath id="overviewClip"><rect x="115" y="350" width="1495" height="1730"/></clipPath>')
add('<g clip-path="url(#overviewClip)">');draw_world(overview);end()
bar=50*overview.s
path(f'M130 2110 h{bar:.2f}',stroke=INK,sw=6);path(f'M130 2099 v22 M{130+bar:.2f} 2099 v22',stroke=INK,sw=2)
text(130+bar/2,2151,'50m',24,INK,600,'middle')
path('M1508 2080 v85',stroke=RED,sw=4,extra='marker-end="url(#redArrow)"')
text(1465,2193,'−Y / 建筑正面',23,RED,600,'end')
text(112,2204,'总图位置和院坪大小采用同一缩尺；右侧放大图采用一致缩尺。',22,MUTED)

cards={'A':(1720,230),'B':(2658,230),'C':(1720,1240),'D':(2658,1240)}
card_notes={'A':['01 在山门外；02 在上山望峰翼台。','高门贯通，双侧廊与旗列退让主路。'],
 'B':['03 演武场；04 位于丹道望峰翼台。','02 / 04 / 06 仅用于转场与休整。'],
 'C':['05 → 挚友：按节点与友位实距绘制。','炉居中轴后方，高檐亭架在其后。'],
 'D':['07 / 08 同一实体峰顶。','08 在后侧；圆阵壁以实际占地记录为准。']}
if data.get('friend') and data.get('furnace'):
    n5=next(n for n in nodes if n['index']==5)
    card_notes['C'][0]=f'05 → 挚友 {fmt(math.dist(n5["ground"],data["friend"]))}m；挚友 → 炉位 {fmt(math.dist(data["friend"],data["furnace"]))}m。'
if data.get('boss'):
    n7=next(n for n in nodes if n['index']==7)
    card_notes['D'][0]=f'07 → Boss {fmt(math.dist(n7["ground"],data["boss"]))}m；07 / 08 同台。'
zoom_scale=9.1
for key,(cx,cy) in cards.items():
    rect(cx,cy,866,930,'#e9e6d0','#a9b79c',2,22)
    circle(cx+45,cy+51,24,INK);text(cx+45,cy+59,key,24,'#eee1b7',700,'middle')
    text(cx+87,cy+60,court_names[key],34,INK,700)
    row=court_meta.get(key)
    if not row:
        lines(cx+40,cy+165,[key+' 院坪边界未写入当前数据','待最终 LayoutSpec 补充后自动绘制'],27,RED,45)
        continue
    p=centre(row);z=p[2]
    if ispolygon(row):
        qb=bounds(row);dimension=f'外包络 {fmt(qb[1]-qb[0])} × {fmt(qb[3]-qb[2])}m / 切角院坪'
    else:dimension=(f'直径 {fmt(radius(row)*2)}m' if iscircle(row) else f'{fmt(dims(row)[0])} × {fmt(dims(row)[1])}m')
    text(cx+40,cy+104,f'地面 +{fmt(z)}m  /  {dimension}',25,MUTED)
    clipid='clip'+key
    add(f'<clipPath id="{clipid}"><rect x="{cx+30}" y="{cy+145}" width="806" height="640" rx="8"/></clipPath>')
    rect(cx+30,cy+145,806,640,'#dce5d5','#b3bea4',1,8)
    r=View(cx+30,cy+145,806,640,(p[0]-40,p[0]+40,p[1]-35,p[1]+35),scale=zoom_scale)
    add(f'<g clip-path="url(#{clipid})">');draw_world(r,True,key);end()
    # Dimension lines are actual platform values from the spec.
    dimw=(bounds(row)[1]-bounds(row)[0]) if ispolygon(row) else radius(row)*2 if iscircle(row) else dims(row)[0]
    mx,my=r.point(p);x1=mx-dimw*r.s/2;x2=mx+dimw*r.s/2
    path(f'M{x1:.2f} {cy+810} H{x2:.2f}',stroke='#82977e',sw=2)
    path(f'M{x1:.2f} {cy+802} v16 M{x2:.2f} {cy+802} v16',stroke='#82977e',sw=2)
    text((x1+x2)/2,cy+838,f'{fmt(dimw)}m',23,INK,600,'middle')
    lines(cx+40,cy+875,card_notes[key],23,MUTED,33)

# Profile is node sequence, not invented measured distance along free movement.
rect(76,2300,3448,380,'#e7e3c9','#aab69a',2,22)
text(113,2358,'节点展开高程',32,INK,700)
text(3484,2356,'纵轴来自真实白模 Z；横轴为节点顺序，不代表行走里程或直线视线剖面。',24,MUTED,400,'end')
for elev in (0,40,80,120):
    yy=2598-elev*1.2
    path(f'M190 {yy:.2f} H3450',stroke='#bec5a6',sw=1.4,extra='stroke-dasharray="7 9"')
    text(171,yy+7,f'+{elev}',20,MUTED,400,'end')
xs=[275+i*(3100/7) for i in range(8)]
pts=[(xs[i],2598-n['ground'][2]*1.2) for i,n in enumerate(nodes)]
path('M'+' L'.join(f'{x:.2f} {y:.2f}' for x,y in pts),stroke=GOLD,sw=5)
for n,(x,y) in zip(nodes,pts):
    path(f'M{x-54:.2f} {y:.2f} h108',stroke=INK,sw=7)
    circle(x,y,8,'#f4e9c7',INK,3)
    text(x,y-24,f'{n["index"]:02}  +{fmt(n["ground"][2])}m',24,INK,700,'middle')
    text(x,2647,node_names.get(n['index'],'节点'),23,MUTED,500,'middle')
text(113,2396,'玩家节点、挚友、炉位和 Boss 均读取本次生成数据；图上圆点不表示实体尺寸。',23,MUTED)

# Legend and provenance are explicit and concise.
text(78,2731,'金虚线：阶梯推进  ·  青箭头：节点实际朝向  ·  朱箭头：建筑正立面  ·  炉 / 友 / B：位置标记',24,MUTED)
if missing:
    text(78,2770,'数据待补：'+'；'.join(missing),21,RED)
else:
    text(78,2770,'已按当前白模参数绘制；碰撞、全程步行、终点视线与性能结论以验收记录为准。',22,MUTED)
text(3520,2731,'ACTUAL WHITEBOX SPEC / PLAN',22,MUTED,500,'end')
text(3520,2770,'LayoutSpec SHA256 '+hashlib.sha256(raw).hexdigest()[:16],20,MUTED,400,'end')
end();add('</svg>')
svg='\n'.join(parts)
stem='逆鳞_实际白模平面图_v01'
svgpath=OUT/(stem+'.svg');svgpath.write_text(svg,encoding='utf-8')
import xml.etree.ElementTree as ET
ET.parse(svgpath)
viewer='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>逆鳞 · 实际白模平面图</title><style>
*{box-sizing:border-box}body{margin:0;background:#213e36;color:#eee7cd;font:15px "Microsoft YaHei",sans-serif}header{position:sticky;top:0;z-index:10;background:#23473df5;border-bottom:1px solid #789477;padding:14px 22px;display:flex;align-items:center;gap:18px}strong{margin-right:auto;font-size:19px}button,a{border:1px solid #9caa86;border-radius:5px;background:#e2d5ad;color:#24473b;padding:7px 12px;text-decoration:none;cursor:pointer}label{white-space:nowrap;cursor:pointer}#scroll{overflow:auto;height:calc(100vh - 65px);padding:20px}#board{margin:auto;width:1800px}svg{width:100%;height:auto;display:block;box-shadow:0 8px 36px #0004}input[type=range]{width:140px}@media print{header{display:none}#scroll{height:auto;padding:0}#board{width:100%}body{background:white}}
</style><header><strong>逆鳞 · 实际白模平面</strong><label><input type="checkbox" checked data-layer="building-layer">建筑</label><label><input type="checkbox" checked data-layer="route-layer">推进</label><label><input type="checkbox" checked data-layer="node-layer">节点</label><label><input type="checkbox" checked data-layer="point-layer">炉 / 挚友 / Boss</label><input id="zoom" type="range" min="900" max="4800" step="100" value="1800"><button id="fit">适应宽度</button><a href="'''+stem+'''.svg" download>SVG</a><a href="'''+stem+'''.png" download>PNG</a></header><div id="scroll"><div id="board">'''+svg+'''</div></div><script>
const board=document.querySelector('#board'),zoom=document.querySelector('#zoom');function fit(){board.style.width=(innerWidth-48)+'px';zoom.value=innerWidth-48}zoom.oninput=()=>board.style.width=zoom.value+'px';document.querySelector('#fit').onclick=fit;document.querySelectorAll('[data-layer]').forEach(c=>c.onchange=()=>document.querySelectorAll('.'+c.dataset.layer).forEach(g=>g.style.display=c.checked?'':'none'));fit();</script></html>'''
(OUT/'逆鳞_实际白模平面图_交互查看.html').write_text(viewer,encoding='utf-8')
runtime=Path(r'C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies')
nodecode='const sharp=require('+json.dumps(str(runtime/'node/node_modules/sharp'))+');sharp('+json.dumps(str(svgpath),ensure_ascii=False)+').png().toFile('+json.dumps(str(OUT/(stem+'.png')),ensure_ascii=False)+').then(()=>console.log("PNG rendered"));'
render=OUT/'render_plan.cjs';render.write_text(nodecode,encoding='utf-8')
subprocess.run([str(runtime/'node/bin/node.exe'),str(render)],check=True)
im=Image.open(OUT/(stem+'.png'));im.thumbnail((1800,1400));im.save(OUT/'preview.png')
(OUT/'PlanSource.json').write_text(json.dumps({'source':str(args.spec),'map':data['map'],'source_sha256':hashlib.sha256(raw).hexdigest(),
    'generated_at':data.get('generated_at'),'world_mirrored_x':data.get('world_mirrored_x',False),
    'screen_right_world_axis':'-X' if X_SIGN<0 else '+X','screen_up_world_axis':'+Y',
    'nodes':len(nodes),'court_records':list(court_meta),
 'building_footprints':len(footprints),'rest_records':len(rests),'missing_data':missing,
 'dimensions_px':[W,H],'scope':'Actual saved whitebox parameters; geometric plan, not a visual ray or playtest result.'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'svg':str(svgpath),'png':str(OUT/(stem+'.png')),'missing':missing},ensure_ascii=False))
