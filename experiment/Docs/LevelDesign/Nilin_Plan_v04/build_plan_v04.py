"""A new orthographic plan reconstructed from the user's final v03 concept image.
Only qualitative placement/relative size is extracted; no measured world dimensions.
"""
from pathlib import Path
import math, html, base64, io, json, subprocess, xml.etree.ElementTree as ET
from PIL import Image

OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'Nilin_Plan_v03'/'逆鳞_仙山寺观_正对总览镜头_v03.png'
W,H=3600,2500
P=[]
INK='#244d44'; MUTED='#637d6a'; GOLD='#bc853d'; RED='#a95845'; TEAL='#2f8e80'
def add(s): P.append(s)
def path(d,fill='none',stroke=INK,sw=2,extra=''):
    add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" {extra}/>')
def rect(x,y,w,h,fill,stroke='none',sw=1,r=0,extra=''):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def ellipse(x,y,rx,ry,fill,stroke='none',sw=1,extra=''):
    add(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def circle(x,y,r,fill,stroke='none',sw=1,extra=''): ellipse(x,y,r,r,fill,stroke,sw,extra)
def text(x,y,s,size=28,color=INK,weight=400,anchor='start',extra=''):
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{html.escape(s)}</text>')
def lines(x,y,ss,size=26,color=MUTED,step=40):
    for i,s in enumerate(ss): text(x,y+i*step,s,size,color)
def label(x,y,letter,title,sub,width=470):
    rect(x-30,y-43,width,93,'#f2ecd8','#a6b59b',1.5,12,extra='fill-opacity=".97"')
    circle(x,y-4,25,INK); text(x,y+4,letter,23,'#f1e5bc',700,'middle')
    text(x+43,y-3,title,32,INK,700); text(x+43,y+32,sub,23,MUTED)
def node(x,y,n):
    circle(x,y,23,'#f7edcd',GOLD,3); text(x,y+8,f'{n:02}',22,'#99682e',700,'middle')
def tag(x,y,s,size=23,col=INK):
    rect(x-10,y-26,len(s)*size+22,36,'#f4eedb',r=6,extra='fill-opacity=".92"'); text(x,y,s,size,col,600)
def octagon(x,y,w,h,c=24):
    return f'M{x+c} {y} H{x+w-c} L{x+w} {y+c} V{y+h-c} L{x+w-c} {y+h} H{x+c} L{x} {y+h-c} V{y+c} Z'
def court(x,y,w,h):
    path(octagon(x,y,w,h),'url(#paving)','#758f79',5)
    path(octagon(x+13,y+13,w-26,h-26,17),'none','#b3bba0',2)
    # True plan: a flat perimeter, no cliff skirt or vertical side extrusion.
    for xx in range(int(x+42),int(x+w-24),60):
        rect(xx-4,y+5,8,12,'#9da989')
        rect(xx-4,y+h-17,8,12,'#9da989')
    for yy in range(int(y+43),int(y+h-24),60):
        rect(x+5,yy-4,12,8,'#9da989'); rect(x+w-17,yy-4,12,8,'#9da989')
def roof(x,y,w,h,name,door=True):
    # Roof projection with a horizontal ridge, not a front elevation.
    rect(x-11,y-9,w+22,h+18,'#b3b99a','#758b70',2,4)
    path(f'M{x-7} {y} Q{x+w/2} {y+10} {x+w+7} {y} L{x+w} {y+h} Q{x+w/2} {y+h-10} {x} {y+h} Z','#37675a','#234d42',3)
    path(f'M{x} {y+h/2} H{x+w}',stroke='#c2ad71',sw=5)
    for xx in range(int(x+15),int(x+w-8),16):
        path(f'M{xx} {y+7} V{y+h/2-5} M{xx} {y+h/2+5} V{y+h-7}',stroke='#71917b',sw=1.3)
    path(f'M{x} {y} L{x+26} {y+h/2} L{x} {y+h} M{x+w} {y} L{x+w-26} {y+h/2} L{x+w} {y+h}',stroke='#779779',sw=2)
    text(x+w/2,y+h/2+9,name,27,'#e9dcb4',600,'middle')
    if door:
        rect(x+w/2-23,y+h-5,46,13,'#f3e9cd','#715e45',2,2)
        path(f'M{x+w/2} {y+h+12} v38',stroke=RED,sw=3.5,extra='marker-end="url(#redArrow)"')
def steps(x,y,w,h):
    rect(x,y,w,h,'#e2d8b9','#8f9e80',2,2)
    for yy in range(int(y+7),int(y+h),10): path(f'M{x+4} {yy} H{x+w-4}',stroke='#91a084',sw=2)
    path(f'M{x+w/2} {y+h-7} V{y+7}',stroke='#7a8e73',sw=2,extra='marker-end="url(#greenArrow)"')
def passage(d,width=75):
    path(d,stroke='#7b967c',sw=width+16)
    path(d,stroke='#e1d7b7',sw=width+8)
    path(d,stroke='#b9c4a4',sw=width-8)
    path(d,stroke='#7f987d',sw=width-18,extra='stroke-dasharray="3 12"')
def route(d):
    path(d,stroke='#fbf0cd',sw=11)
    path(d,stroke=GOLD,sw=5,extra='stroke-dasharray="17 9" marker-end="url(#goldArrow)"')
def furnace(x,y,r=48):
    circle(x,y,r+12,'none','#a3ad8b',2)
    circle(x,y,r,'#c1a363','#6d7654',4); circle(x,y,r*.67,'#507968','#e5c885',3)
    circle(x,y,r*.3,'#e4bc67','#9b8550',2)
    for a in (0,120,240):
        aa=math.radians(a); xx=x+(r+3)*math.cos(aa); yy=y+(r+3)*math.sin(aa)
        circle(xx,yy,8,'#998952','#6d7654',2)
    for a in (40,160,280):
        aa=math.radians(a); xx=x+(r+8)*math.cos(aa); yy=y+(r+8)*math.sin(aa)
        path(f'M{xx} {yy} l{12*math.cos(aa)} {12*math.sin(aa)}',stroke='#7b7751',sw=7)
def incense(x,y):
    circle(x,y,33,'#c2ba8c','#8b9573',2); circle(x,y,22,'#ae985b','#6f7654',3)
    path(f'M{x-19} {y-9} l-14 -8 M{x+19} {y-9} l14 -8',stroke='#7a794f',sw=5)
def pine():
    # One giant pine only, west of the shared middle complex; its root projection binds the lower levels.
    for d in ['M485 1370 Q420 1235 530 1100','M475 1340 Q530 1260 650 1190','M476 1350 Q430 1410 355 1532','M480 1360 Q595 1450 740 1480','M463 1380 Q450 1530 415 1590','M510 1290 Q585 1370 650 1420']:
        path(d,stroke='#8c9370',sw=32)
        path(d,stroke='#c7c49b',sw=9)
    for dx,dy,rx,ry in [(360,1070,160,85),(505,1035,160,94),(625,1110,126,86),(460,1160,150,88),(285,1165,125,85),(610,1220,132,77)]:
        ellipse(dx,dy,rx,ry,'#83a285','#65886c',3)
        path(f'M{dx-rx*.65} {dy+10} Q{dx} {dy+ry*.6} {dx+rx*.65} {dy-8}',stroke='#b7c29c',sw=2)
    circle(480,1260,49,'#9b9e74','#658669',3)
    text(435,930,'巨型古松',28,'#5a7a60',700,'middle')
    text(435,969,'树冠 / 根系投影',23,'#6e8a70',400,'middle')
def image_embed(x,y,w,h):
    im=Image.open(SOURCE).convert('RGB'); im.thumbnail((1200,700))
    b=io.BytesIO(); im.save(b,'JPEG',quality=88)
    data=base64.b64encode(b.getvalue()).decode()
    add(f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet" href="data:image/jpeg;base64,{data}"/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('''<defs>
<pattern id="paving" width="38" height="38" patternUnits="userSpaceOnUse"><rect width="38" height="38" fill="#d6d7ba"/><path d="M38 0H0V38" fill="none" stroke="#afbaa0" stroke-width="1.2"/></pattern>
<pattern id="paper" width="90" height="90" patternUnits="userSpaceOnUse"><rect width="90" height="90" fill="#f1ecd9"/><path d="M0 27H90M16 0V90" fill="none" stroke="#cdcdb4" stroke-width=".5" opacity=".22"/></pattern>
<marker id="goldArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#bc853d"/></marker>
<marker id="redArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#a95845"/></marker>
<marker id="greenArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#7a8e73"/></marker>
</defs>''')
add('<g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">')
rect(0,0,W,H,'url(#paper)')
rect(76,58,8,111,GOLD)
text(109,111,'逆鳞',61,INK,700)
text(300,109,'最终意向对应平面图',47,INK,600)
text(111,157,'从最终总览图反推空间关系  /  3 组主台地 · 4 层院坪 · 8 个玩法节点',27,MUTED)
text(3522,100,'正投影平面 · 建筑占地与连接研究',27,INK,500,'end')
text(3522,147,'v04  /  2026.10.16  /  相对关系提取，非测绘',24,MUTED,400,'end')
path('M78 195 H3522',stroke='#aab69c',sw=2)

rect(76,230,2530,1830,'#d8e5d7','#a3b8a4',2,24)
text(113,280,'图面上方 / 下方对应最后图片方向，不表示地理北',24,MUTED)
# Background contour and cloud texture are subordinate to the actual flat plan.
for off in (0,28,56):
    path(f'M{140+off} 1900 Q{60+off} 1650 {250+off} 1480 Q{460+off} 1310 {670+off} 1440',stroke='#adc8b0',sw=2,extra='opacity=".55"')
    path(f'M{710+off} 1460 Q{635+off} 1120 {1040+off} 1060 Q{1050+off} 620 {1370+off} 585 Q1760 {495+off} {1970+off} 760',stroke='#adc8b0',sw=2,extra='opacity=".55"')
    path(f'M{1900+off} 700 Q{1840+off} 380 {2110+off} 245 Q{2470+off*.3} 230 {2510+off*.2} 620',stroke='#adc8b0',sw=2,extra='opacity=".55"')
for x,y,rx,ry in [(380,2000,260,49),(1070,1930,355,70),(1695,1715,300,65),(2220,1250,300,65),(920,760,260,55),(1770,410,240,50),(2280,1930,240,60)]:
    ellipse(x,y,rx,ry,'#e9efdf',extra='opacity=".76"')
    path(f'M{x-rx*.85} {y} Q{x-rx*.3} {y-ry*1.2} {x+rx*.3} {y+ry*.2} T{x+rx*.9} {y-ry*.2}',stroke='#b1ccba',sw=3,extra='opacity=".7"')
text(1840,1820,'云海 / 不可达背景',26,'#7c9c83',500,'middle')

# Single mountain pine behind the flat platforms. No terrain extrusion is used.
pine()

# Main connectors: the bridge/stair route is continuous and has no standalone 06 floor.
passage('M260 2025 Q350 1990 480 1970',96)
passage('M710 1530 Q805 1485 885 1460',108)
passage('M1910 1020 Q2015 1000 2075 920 Q2118 870 2080 820 Q2170 825 2305 890',80)

# A: a gate complex, accommodating both exterior and interior tutorial points.
court(180,1500,650,490)
steps(420,1915,130,110)
roof(300,1635,410,150,'山门殿')
roof(184,1665,108,105,'配廊',False); roof(718,1665,108,105,'配廊',False)
# Through-gate opening shown explicitly as a passage projection, not a new room.
rect(474,1629,62,164,'#e2d8b7','#e9d5a3',2,2,extra='fill-opacity=".62" stroke-dasharray="6 5"')
text(505,1720,'门洞',22,INK,700,'middle')
steps(748,1470,130,108)

# B/C are adjacent levels of ONE connected middle temple complex.
court(760,1110,700,420)
court(1070,630,860,480)
roof(800,1125,400,145,'前院主殿')
roof(1240,650,520,175,'大丹殿')
roof(1090,835,196,130,'西配殿')
roof(1730,835,196,130,'东配殿')
# Connecting galleries are small subordinate footprints, not additional stages.
rect(1095,720,65,104,'#b3c0a0','#789578',2,4)
rect(1840,720,65,104,'#b3c0a0','#789578',2,4)
incense(1080,1370)
furnace(1500,943,54)
circle(1500,943,100,'none','#a2b18b',2,extra='stroke-dasharray="8 8"')
text(1500,1034,'巨型炼丹炉',24,INK,600,'middle')
text(1080,1430,'小香炉',22,INK,500,'middle')
steps(1328,1088,132,128)
text(1400,1243,'上下院连接石阶',23,INK,600,'middle')

# D: one circular summit court with its main hall at the rear center.
circle(2305,580,295,'url(#paving)','#758f79',5)
circle(2305,580,280,'none','#a8b69b',2)
circle(2305,672,140,'none','#a4b18b',3)
circle(2305,672,119,'none','#b7bea1',2)
roof(2125,350,360,140,'峰顶主殿')
for x,y in [(2065,450),(2512,450),(2055,690),(2517,690)]:
    circle(x,y,18,'#b5ba91','#70866c',3)
    rect(x-7,y-7,14,14,'#69836a')
steps(2239,834,132,94)
# Airborne crown is a dashed projection ON this court, with no side exit terrace.
circle(2305,420,113,'none','#c39a4e',3,extra='stroke-dasharray="10 8"')
for a in range(0,360,45):
    aa=math.radians(a); xx=2305+113*math.cos(aa); yy=420+113*math.sin(aa)
    add(f'<g transform="rotate({a} {xx} {yy})">')
    path(f'M{xx} {yy-15} l5 9 l-2 25 h-6 l-2 -25 Z','#d9bc72','#a38646',1)
    path(f'M{xx-10} {yy+7} h20',stroke='#b4934d',sw=3)
    add('</g>')
tag(2387,542,'空中金剑环投影',22,'#987940')
path('M2380 531 L2366 491',stroke='#b3924c',sw=2)

# Top-plan rails of the two arched bridge spans; support arches are not drawn as facades.
for x,y,ang in [(1997,983,-31),(2124,820,7)]:
    add(f'<g transform="rotate({ang} {x} {y})">')
    rect(x-50,y-47,100,94,'none','#6c8e73',3,6)
    path(f'M{x-48} {y-57} H{x+48} M{x-48} {y+57} H{x+48}',stroke='#6c8e73',sw=3)
    add('</g>')
tag(2045,1083,'连续石阶 / 两段拱桥',22)

# Four clear location callouts, reflecting the source image rather than eight arenas.
label(216,1445,'A','山门院坪','同一院坪承载 01 / 02',500)
label(800,1600,'B','半山下层前院','03 演武场；后侧主殿 + 小香炉',620)
label(1535,1174,'C','上层丹炉院','05 守丹台；炉在中轴，大丹殿在后',700)
label(1885,275,'D','峰顶圆院','07 / 08 共用同一台地',500)
path('M1863 320 L2075 420',stroke='#77957b',sw=2)

# New gameplay mappings are minimal and explicitly distinguished from extracted geometry.
route('M505 1875 V1812')
route('M505 1612 V1530 Q650 1475 727 1520 Q803 1500 901 1460')
route('M1168 1380 Q1270 1320 1395 1220 V1122')
route('M1558 1050 Q1750 1090 1898 1018 Q2015 1000 2075 920 Q2118 870 2080 820 Q2170 825 2305 890 V805')
node(505,1875,1); node(560,1535,2); node(1180,1380,3); node(1395,1163,4)
node(1575,1055,5); node(2100,914,6); node(2237,744,7); node(2374,744,8)
text(2305,795,'胜利收束仍在峰顶',23,INK,600,'middle')

# A stable camera direction is shown without inventing geographic north.
path('M2460 1950 V1810',stroke=RED,sw=5,extra='marker-end="url(#redArrow)"')
text(2460,1988,'总览镜头看向图上方',24,RED,600,'end')
text(113,2084,'纯平面：建筑占地 / 院坪边缘 / 阶梯桥路；不绘制斜立面或崖壁挤出。',23,MUTED)

# Right column: the actual final concept is embedded and registered by A/B/C/D.
rect(2654,230,870,1830,'#e9e5ce','#a8b69c',2,24)
text(2694,288,'对应的最终总览图',33,INK,700)
text(2694,328,'以此图提取相对位置与比例',25,MUTED)
image_embed(2694,354,790,445)
for xx,yy,ss in [(2827,687,'A'),(2963,595,'B'),(3068,553,'C'),(3334,437,'D')]:
    circle(xx,yy,22,'#f5e9c5',INK,3); text(xx,yy+8,ss,23,INK,700,'middle')
text(2694,840,'4 层院坪，而非 8 个独立场地',30,INK,700)
lines(2694,887,['A 山门：前后院与门洞属于同一门院。','B 前院：较紧凑，主殿靠后，中间小香炉。','C 丹炉院：更大，中轴大炉，后中大丹殿。','D 峰顶：圆院与后中主殿，金剑环同台投影。'],26,MUTED,44)
path('M2694 1060 H3481',stroke='#b2bea1',sw=2)
text(2694,1110,'八节点映射（玩法建议）',30,INK,700)
text(2694,1152,'编号不是从图片识别出的房间或实机布点。',24,MUTED)
rows=[('01 / 02','A 山门','门外教学 / 门内混合波次'),('03','B 前院','演武与清群'),('04','B → C 石阶','丹道入口 / 执事检验'),('05','C 丹炉院','守阵获救 / 三级保底'),('06','C → D 桥路','休整与目标提示，无独立台地'),('07 / 08','D 同一峰顶','Boss / 胜利后归途收束')]
for i,(a,b,c) in enumerate(rows):
    y=1208+i*86
    if i%2==0: rect(2682,y-30,812,76,'#e0e2c6',r=6)
    text(2701,y,a,25,'#946d35',700)
    text(2832,y,b,25,INK,600)
    text(2832,y+35,c,23,MUTED)
path('M2694 1730 H3481',stroke='#b2bea1',sw=2)
text(2694,1780,'读图与实施边界',29,INK,700)
lines(2694,1823,['朱色箭头：主要建筑正立面统一朝图下。','金色虚线：玩法推进建议，非图片中的铺装。','山门 → 巨松右侧 → 前院 → 右侧阶梯登峰。','图上尺寸未核定；+0～+132m 仍是既定高程建议。','任何位置可见终点：保留为设计要求，待 UE 验证。'],24,MUTED,39)

# Linear node mapping, with elevations segregated as prior design recommendations.
rect(76,2100,3448,295,'#e6e2c9','#abb69a',2,22)
text(113,2155,'流程与既定高程建议',30,INK,700)
text(3487,2154,'四层院坪来自图像；八节点与高程来自既有玩法提案，不能混作图像测量。',24,MUTED,400,'end')
flow=[('01','A 门外','+0m'),('02','A 门内','+12m'),('03','B 前院','+28m'),('04','B→C 石阶','+44m'),('05','C 丹炉院','+72m'),('06','C→D 桥路','+104m'),('07','D 山顶战','+132m'),('08','D 同台归途','+132m')]
for i,(a,b,c) in enumerate(flow):
    x=113+i*424
    rect(x,2194,396,147,'#f0e9cf','#b8bfa1',1.5,11)
    text(x+20,2230,a,27,'#9c7138',700)
    text(x+20,2273,b,28,INK,600)
    text(x+20,2315,c,24,MUTED)
    if i<7: path(f'M{x+401} 2266 h16',stroke=GOLD,sw=3,extra='marker-end="url(#goldArrow)"')
text(113,2374,'战斗净空约 28m、VR 淡出转场等旧建议仍需灰盒复核；本图不据此增加新台地或声明现有工程已实现。',23,MUTED)
text(78,2460,'依据最终 v03 美术意向重新提取：保留单株巨松、连体半山殿院、炉前后中轴、右侧阶梯拱桥及同台峰顶结局。',24,MUTED)
text(3520,2460,'NILIN / IMAGE → PLAN / v04',22,MUTED,500,'end')
add('</g></svg>')
svg='\n'.join(P)
svgpath=OUT/'逆鳞_最终意向对应平面图_v04.svg'
svgpath.write_text(svg,encoding='utf-8'); ET.parse(svgpath)
runtime=Path(r'C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies')
render=OUT/'render_plan_v04.cjs'
render.write_text('const sharp=require('+json.dumps(str(runtime/'node/node_modules/sharp'))+');\nsharp('+json.dumps(str(svgpath),ensure_ascii=False)+').png().toFile('+json.dumps(str(OUT/'逆鳞_最终意向对应平面图_v04.png'),ensure_ascii=False)+').then(()=>console.log("rendered"));',encoding='utf-8')
subprocess.run([str(runtime/'node/bin/node.exe'),str(render)],check=True)
im=Image.open(OUT/'逆鳞_最终意向对应平面图_v04.png'); im.thumbnail((1800,1250)); im.save(OUT/'preview_v04.png')
print('SVG parsed; PNG rendered:',Image.open(OUT/'逆鳞_最终意向对应平面图_v04.png').size)
