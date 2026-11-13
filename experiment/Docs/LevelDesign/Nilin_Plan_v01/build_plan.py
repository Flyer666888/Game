from pathlib import Path
import base64, io, html, math, json
from PIL import Image

OUT = Path(__file__).resolve().parent
REF = OUT.parents[1] / 'AI' / 'ReferencePack' / 'images'
W, H = 3200, 2100
P = []
def add(s): P.append(s)
def rect(x,y,w,h,fill,stroke='none',sw=1,r=0,extra=''):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def path(d,fill='none',stroke='#56716a',sw=2,extra=''):
    add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round" {extra}/>')
def circle(x,y,r,fill,stroke='none',sw=1,extra=''):
    add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def text(x,y,s,size=26,color='#e5e8dc',weight=400,anchor='start',extra=''):
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{html.escape(s)}</text>')
def lines(x,y,ss,size=25,color='#b7c8be',step=38):
    for i,s in enumerate(ss): text(x,y+i*step,s,size,color)
def label(x,y,title,sub,anchor='middle'):
    text(x,y,title,31,'#edf1e5',600,anchor)
    text(x,y+33,sub,21,'#b5c6bc',400,anchor)
def badge(x,y,n,col='#e2c578'):
    circle(x,y,29,'#172c2a',col,3)
    text(x,y+10,str(n).zfill(2),26,col,700,'middle')
def roof(x,y,w,h):
    rect(x,y,w,h,'#2b423b','#718577',2,3)
    path(f'M{x-12},{y+8} L{x+w/2},{y-15} L{x+w+12},{y+8} L{x+w},{y+h} L{x},{y+h} Z','#324d43','#8b9a7c',2)
    path(f'M{x},{y+8} L{x+w},{y+8}',stroke='#a5a784',sw=3)
    for j in range(1,int(w/22)):
        path(f'M{x+j*22},{y+10} l0,{h-14}',stroke='#536c58',sw=1)
def rock(x,y,s=1):
    path(f'M{x-25*s},{y+10*s} l{10*s},{-25*s} l{23*s},{-9*s} l{22*s},{25*s} l{-14*s},{22*s} Z','#243c36','#405950',2)
def floor_rect(x,y,w,h):
    rect(x+8,y+12,w,h,'#0b1919',r=7)
    rect(x,y,w,h,'url(#tiles)','#94aa91',6,7)
    rect(x+10,y+10,w-20,h-20,'none','#537366',2,3)
def floor_round(x,y,r):
    circle(x+8,y+12,r,'#0b1919')
    circle(x,y,r,'url(#tiles)','#94aa91',6)
    circle(x,y,r-13,'none','#537366',2)
def corridor(d,sw=76):
    path(d,stroke='#0b1919',sw=sw+15)
    path(d,stroke='#6e8676',sw=sw+7)
    path(d,stroke='#344e44',sw=sw)
def route(d):
    path(d,stroke='#142c27',sw=12)
    path(d,stroke='#eed385',sw=6,extra='marker-end="url(#arrowGold)" stroke-dasharray="16 11"')
def player(x,y,up=True):
    add('<g class="threat-layer">')
    dy=-1 if up else 1
    path(f'M{x},{y} L{x-115},{y+dy*176} Q{x},{y+dy*242} {x+115},{y+dy*176} Z','#72d7ba',stroke='#6fc6a6',sw=2,extra='fill-opacity="0.09" stroke-dasharray="6 8"')
    add('</g>')
    circle(x,y,19,'#92ddbe','#162b26',4)
    path(f'M{x},{y-9} l-7,13 l14,0 Z','#163e32','none')
    text(x+30,y+8,'P',23,'#b4edcb',700)
def spawn(x,y,tx,ty,kind='melee'):
    add('<g class="threat-layer">')
    c='#e88f76' if kind=='melee' else '#efba69'
    if kind=='melee': path(f'M{x},{y-13} l-13,25 h26 Z',c,'#322d26',2)
    elif kind=='caster': rect(x-12,y-12,24,24,c,'#322d26',2,2,extra=f'transform="rotate(45 {x} {y})"')
    else: path(f'M{x},{y-15} l-15,27 h30 Z','none',c,4)
    dx,dy=tx-x,ty-y
    l=math.hypot(dx,dy)
    if l>35:
        ex,ey=tx-dx/l*40,ty-dy/l*40
        path(f'M{x+dx/l*22},{y+dy/l*22} L{ex},{ey}',stroke=c,sw=3,extra='marker-end="url(#arrowThreat)" stroke-dasharray="7 8" opacity=".8"')
    add('</g>')
def checkpoint(x,y,caption='CP'):
    rect(x,y,49,30,'#263f36','#b2c9aa',2,6)
    text(x+24.5,y+22,caption,18,'#dbe7cb',700,'middle')
def upgrade(x,y,s):
    path(f'M{x},{y-17} l17,17 l-17,17 l-17,-17 Z','#e4cc85','#152f28',2)
    text(x,y+7,'↑',24,'#19352a',700,'middle')
    text(x+30,y+8,s,23,'#ebdba4',600)
def image_embed(filename,x,y,w,h):
    im=Image.open(REF/filename).convert('RGB'); im.thumbnail((1000,600))
    b=io.BytesIO(); im.save(b,'JPEG',quality=88)
    dat=base64.b64encode(b.getvalue()).decode()
    cid='clip'+str(x)+str(y)
    add(f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/></clipPath>')
    add(f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" clip-path="url(#{cid})" href="data:image/jpeg;base64,{dat}"/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('<defs><pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M64 0H0V64" fill="none" stroke="#708978" stroke-width="1" opacity=".10"/></pattern><pattern id="tiles" width="38" height="38" patternUnits="userSpaceOnUse"><rect width="38" height="38" fill="#425e50"/><path d="M38 0H0V38" fill="none" stroke="#6b8270" stroke-width="1.2" opacity=".50"/></pattern><marker id="arrowGold" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#eed385"/></marker><marker id="arrowThreat" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#e9a781"/></marker></defs>')
add('<g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">')
rect(0,0,W,H,'#102421')
rect(0,0,W,H,'url(#grid)')
rect(72,66,7,104,'#e8ce86')
text(105,112,'逆鳞',58,'#f1e7c8',700)
text(267,110,'宗门救援 · 关卡流程平面草图',43,'#eceddf',600)
text(108,157,'NILIN  /  LEVEL FLOW & TOP-DOWN BLOCKOUT',20,'#92ab9c',500,extra='letter-spacing="3"')
text(3118,100,'单人 PC VR  ·  三关线性推进  ·  双手战斗',24,'#c7d4c5',500,'end')
text(3118,143,'v0.1  /  2026.10.16  /  设计提案',22,'#96ac9b',400,'end')
path('M80 192H3120',stroke='#496153',sw=2)

# Central map field, with non-playable contour islands behind the usable floor.
rect(72,222,3056,1218,'#142c28','#3a5748',2,22)
text(110,267,'空间总览',25,'#d6e1cd',600)
text(3090,267,'示意比例 · 三张地图以虚线衔接 · 场地均保持水平',21,'#90ab99',400,'end')
for d in [
 'M130 1020 Q110 855 280 800 L360 725 Q440 610 620 585 L625 438 Q825 345 1095 360 L1300 360 Q1420 470 1370 610 L1200 720 Q1190 910 990 960 L800 1120 L600 1280 Q340 1400 130 1310Z',
 'M1340 650 Q1300 500 1460 452 Q1650 410 1860 510 Q2000 560 1960 790 L1990 1010 Q1900 1160 1670 1180 Q1430 1130 1320 980Z',
 'M2280 1070 Q2150 890 2280 640 Q2290 420 2480 390 Q2660 300 2880 455 L3030 580 Q3090 840 2920 1030 Q2690 1190 2470 1100Z']:
    path(d,'#1b3730','#355547',2)
for shift in (0,24,48):
    path(f'M{145+shift} 1040 Q{150+shift} 875 {290+shift} 855 L{420+shift} 785 Q{480+shift} 650 {610+shift} 647',stroke='#41614f',sw=2,extra='opacity=".42"')
    path(f'M{1350+shift} 1085 Q{1520+shift} 1230 {1850+shift} 1120',stroke='#41614f',sw=2,extra='opacity=".42"')
    path(f'M{2350+shift} 550 Q{2420+shift} 350 {2730+shift} 404',stroke='#41614f',sw=2,extra='opacity=".42"')
text(965,1280,'云 海 / 不 可 通 行',22,'#5c8070',400,'middle',extra='letter-spacing="4"')
text(2150,565,'断 崖',22,'#5c8070',400,'middle',extra='letter-spacing="6"')

# Act banners.
for x,w,n,title,sub,col in [(125,1000,'I','破山门','挥砍 → 格挡 → 清群 → 精英组合  /  约 7 分钟','#d9cf96'),(1400,580,'II','守丹台','识别目标 · 优先打断  /  约 6 分钟','#99cfac'),(2345,710,'III','逆鳞劫','反弹 · 破阵 · 输出  /  约 7–8 分钟','#9cbdd7')]:
    text(x,336,n,46,col,700)
    text(x+65,333,title,35,'#e5e9d9',600)
    text(x,372,sub,23,'#9bb29e')

# Connection footprints. Traversal is conceptual node transfer, not forced camera motion.
corridor('M300 1142L565 1005',74)
corridor('M590 852L590 755L795 755',72)
corridor('M1035 642L1190 540',72)
corridor('M1290 542L1385 542L1480 673',64)
corridor('M1830 936L2110 936L2350 936L2485 912',86)
corridor('M2690 518L2690 446L2925 446',62)

# Level one four courtyards.
floor_rect(158,1090,285,210)
floor_rect(430,835,332,234)
floor_rect(695,500,405,315)
floor_rect(1112,425,233,225)
# mountain gate and roofed side halls, pillars leave central line clear.
roof(450,813,100,38); roof(650,813,100,38)
rect(552,819,94,17,'#d9c397','#253e32',3)
for x,y in [(463,880),(727,880),(463,1030),(727,1030),(740,550),(1055,550),(740,770),(1055,770),(1140,465),(1315,465)]:
    circle(x,y,10,'#acb59b','#243e32',3)
roof(715,465,370,49)
roof(1105,400,250,35)
roof(387,926,45,127)
roof(766,861,42,127)
for x,y in [(204,1127),(402,1125),(215,1255),(401,1260),(652,1099),(885,862),(1093,859),(1357,708),(1185,776)]: rock(x,y,.7)

# Ritual terrace.
floor_round(1660,825,255)
circle(1660,825,181,'none','#607e64',3)
circle(1660,825,169,'none','#607e64',1,extra='stroke-dasharray="15 12"')
roof(1520,558,280,58)
roof(1365,742,65,150); roof(1890,742,65,150)
for a in (20,65,115,160,205,335):
    x=1660+233*math.cos(math.radians(a)); y=825+233*math.sin(math.radians(a))
    circle(x,y,11,'#9aab8d','#2b4537',3)
# alchemy furnace, objective friend.
circle(1660,662,32,'#6a6250','#c7b57c',4)
circle(1660,662,18,'#9e8049','#bba571',2)
for xx in (1620,1700): circle(xx,662,8,'#766646','#bdab76',2)
circle(1660,847,43,'#277d68','#9be6b9',4)
circle(1660,847,32,'none','#b2efc9',2,extra='stroke-dasharray="8 6"')
path('M1660 825l-12 22 12 22 12-22Z','#d9f3cf','#284e3b',2)
text(1660,792,'挚友 / 解救法阵',24,'#d0efcf',600,'middle')
text(1660,712,'丹炉地标',20,'#b6c2a2',400,'middle')

# Exit bridge / wide boss apron, same stationary point through all boss phases.
floor_rect(2020,887,320,98)
for x in range(2035,2340,27): path(f'M{x} 895V977',stroke='#6b8172',sw=2)
path('M2030 882H2330 M2030 990H2330',stroke='#a7b59a',sw=6)
floor_round(2680,774,263)
circle(2680,774,214,'none','#687e78',3)
circle(2680,774,191,'none','#526f67',2)
roof(2520,490,320,58)
for x,y in [(2480,608),(2880,608),(2435,853),(2925,853)]: circle(x,y,12,'#a9b7a3','#284536',3)
floor_rect(2895,391,165,110)
roof(2985,382,80,40)
circle(2680,742,35,'#706a5a','#e0b678',3)
circle(2680,742,52,'none','#aa9270',2,extra='stroke-dasharray="8 6"')
path('M2680 716l-22 25 22 27 22-27Z','#e7d6ad','#314b43',3)
text(2680,690,'宗主 · 护阵',23,'#ebd2a8',600,'middle')
for xx in (2580,2780):
    path(f'M{xx} 675l-16 28h32Z','none','#edac67',4)
text(2867,701,'△ 阵眼',22,'#e4b77b')
path('M2845 694H2805',stroke='#aa9770',sw=2)

# Player nodes, enemy portals, all attacks frontal to player.
player(300,1225); spawn(265,1150,300,1225); spawn(350,1132,300,1225)
player(594,1008); spawn(492,904,594,1008); spawn(690,905,594,1008); spawn(594,866,594,1008,'caster')
player(895,741); spawn(772,620,895,741); spawn(1005,620,895,741); spawn(895,554,895,741,'caster')
player(1228,595); spawn(1228,483,1228,595,'breaker'); spawn(1295,496,1228,595,'caster')
player(1660,920); spawn(1470,731,1660,920); spawn(1850,731,1660,920)
spawn(1527,647,1660,847,'caster'); spawn(1793,647,1660,847,'breaker')
text(1465,695,'左前入口',20,'#d5b0a0',400,'middle')
text(1855,695,'右前入口',20,'#d5b0a0',400,'middle')
text(1802,600,'破阵施法位',20,'#edbd7e',400,'middle')
player(2680,930)
add('<g class="threat-layer">')
for xx in (2550,2615,2680,2745,2810):
    path(f'M{xx} 807L{2680+(xx-2680)*.65} 867',stroke='#b9c9d7',sw=3,extra='stroke-dasharray="11 13"')
text(2680,829,'前方分组弹幕',23,'#bdd0db',600,'middle')
add('</g>')

# Main progression overlay follows gaps, with short turn arrows between rooms.
add('<g class="route-layer">')
route('M333 1110L458 1051')
route('M594 835L594 775L706 775')
route('M1090 650L1160 600')
route('M1348 542L1385 542L1460 640')
route('M1888 940H2020')
route('M2340 940L2438 920')
route('M2680 514V446H2895')
add('</g>')

# Node labels and checkpoints use a separate editable layer.
add('<g class="node-layer">')
badge(160,1040,1); label(212,1048,'山门外','挥砍教学 · 1′','start')
badge(432,1120,2); label(477,1129,'山门内','远近组合 · 2′','start')
badge(777,415,3); label(823,424,'演武场','清群＋震荡 · 2.5′','start')
badge(1140,713,4); label(1185,722,'丹道入口','执事＋支援 · 1.5′','start')
badge(1470,1118,5); label(1515,1127,'守丹台','同一站位 · 四段防守','start')
badge(2043,1050,6); label(2088,1059,'御风桥','过渡／休整 · 新增建议','start')
badge(2458,1118,7); label(2503,1127,'封山台','三阶段 Boss · 同一站位','start')
badge(2900,550,8); label(2945,559,'归途','救援完成','start')
checkpoint(345,1254); checkpoint(643,1025); checkpoint(992,738); checkpoint(1260,608)
checkpoint(1697,927); checkpoint(2723,937)
text(1660,1020,'4m · 目标始终在前方',21,'#a3cfad',400,'middle')
text(2680,1012,'约 10m · 反弹与刃气输出',21,'#acc5d2',400,'middle')
upgrade(1353,805,'Ⅱ 二级保底')
upgrade(1920,1115,'Ⅲ 三级保底')
text(300,1333,'起点 →',23,'#e9d99f',600,'middle')
text(900,911,'战场约 30 × 24m',22,'#9bb79e',400,'middle')
text(1660,1195,'丹台直径约 28m',22,'#9bb79e',400,'middle')
text(2690,1195,'决战台直径约 28m',22,'#a4b8bb',400,'middle')
add('</g>')

# Legend and map footnotes.
path('M110 1350H3090',stroke='#3c594b',sw=2)
path('M125 1391H190',stroke='#eed385',sw=5,extra='stroke-dasharray="12 8" marker-end="url(#arrowGold)"')
text(210,1400,'节点推进',22,'#c8d0b6')
circle(428,1391,12,'#92ddbe'); text(450,1400,'P 站位 / 朝向',22,'#c8d0b6')
path('M677 1378l-12 24h24Z','#e88f76','none'); text(700,1400,'近战入口',22,'#c8d0b6')
rect(888,1382,18,18,'#efba69',extra='transform="rotate(45 897 1391)"'); text(921,1400,'御符弟子',22,'#c8d0b6')
path('M1117 1377l-13 26h26Z','none','#efba69',3); text(1141,1400,'破阵 / 执事',22,'#c8d0b6')
checkpoint(1370,1376); text(1434,1400,'段落入口检查点',22,'#c8d0b6')
text(3090,1400,'尺寸为灰盒起点，平面不统一缩尺；非现有 UE 地图测绘',21,'#8fa692',400,'end')

# Three reference-and-gameplay cards, using supplied concept frames as evidence.
cards=[
 (72,'01','破山门','#d9cf96','01_破山门.png',['体验：从一刀清杂兵到远近组合','机制：02 引入格挡／精准反弹','03 引入范围震荡；04 对抗执事','解锁：清完波次＋处理有效威胁']),
 (1100,'02','守丹台','#99cfac','02_守丹台.png',['体验：保护法阵，判断优先级','节奏：建阵 → 截阵 → 围攻 → 解封','目标：有效守点 240s；打断干扰','解锁：进度 100%＋剩余威胁处理']),
 (2128,'03','逆鳞劫','#9cbdd7','03_逆鳞劫.png',['体验：三阶段综合使用已学机制','P1 飞剑反弹 → P2 符弹与阵眼','P3 机制组合；破阵约 5s 输出','解锁：宗主被击败 → 携挚友离开'])
]
for x,n,title,col,img,ss in cards:
    rect(x,1480,1000,376,'#1a332d','#3f5a4a',2,18)
    text(x+27,1529,n,32,col,700)
    text(x+90,1529,title,31,'#e6e9da',600)
    image_embed(img,x+26,1558,390,220)
    text(x+26,1820,'资料包关键画面 · 氛围参考',19,'#8ea593')
    lines(x+441,1593,ss,24,'#c4d1bd',45)
    text(x+441,1803,['节点重试 · Lv.2 保底','按守点阶段入口重试 · Lv.3 保底','按 Boss 阶段入口重试'][int(n)-1],22,col,600)

# Pacing strip, explicitly design estimates rather than measured performance.
text(85,1914,'节奏目标',25,'#e5dfc5',600)
text(3105,1914,'草案估时 22–25 分钟（含叙事 / 转场 / 休整 2–4 分钟）',23,'#adc0a7',400,'end')
segments=[(85,820,'约 7′  学习与清群','#a6a376'),(921,700,'约 6′  保护与判断','#6b9f81'),(1637,930,'约 7–8′  综合决战','#6e93a4'),(2583,532,'2–4′  叙事 / 休整','#746f58')]
for x,w,s,c in segments:
    rect(x,1935,w,45,c,r=7); text(x+w/2,1966,s,22,'#102b23',600,'middle')
text(85,2023,'设计前提：暂按节点淡出转场；前方可读威胁；稳定地平线；首版不安排强制跑动或环背防守。',23,'#a7bca6')
text(85,2063,'依据：开发方案 §8 / §12–15、VR 关键画面、工程 State 与资产盘点。新增空间、尺寸与估时需灰盒及头显验证。',20,'#7f9b88')
text(3115,2063,'LEVEL DESIGN  /  01',20,'#9cb59d',500,'end')
add('</g></svg>')
svg='\n'.join(P)
(OUT/'逆鳞_关卡平面草图_v01.svg').write_text(svg,encoding='utf-8')

viewer='''<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><title>逆鳞｜关卡流程平面草图 v0.1</title><style>
*{box-sizing:border-box}body{margin:0;background:#0d1c19;color:#dce6d6;font:15px "Microsoft YaHei",sans-serif}header{display:flex;gap:20px;align-items:center;padding:16px 24px;position:sticky;top:0;background:#142a24f5;z-index:2;border-bottom:1px solid #42604e}header strong{margin-right:auto;font-size:19px}label{cursor:pointer;white-space:nowrap}button{background:#d9c589;color:#193329;border:0;border-radius:6px;padding:9px 15px;cursor:pointer}#scroll{overflow:auto;height:calc(100vh - 74px);padding:18px}#board{margin:auto;width:1500px;max-width:none}svg{width:100%;height:auto;display:block;box-shadow:0 8px 50px #0005}.hint{color:#a5b9a6;font-size:13px}input[type=range]{width:130px}a{color:#ddce9a}
</style><header><strong>逆鳞 · 关卡流程研究</strong><label><input checked type="checkbox" data-layer="route-layer"> 推进路线</label><label><input checked type="checkbox" data-layer="threat-layer"> 威胁与视野</label><label><input checked type="checkbox" data-layer="node-layer"> 节点注释</label><span class="hint">缩放</span><input id="zoom" type="range" min="900" max="4200" value="1500" step="100"><button id="fit">适应宽度</button><a href="逆鳞_关卡平面草图_v01.png" download>PNG</a><a href="逆鳞_关卡平面草图_v01.svg" download>SVG</a></header><div id="scroll"><div id="board">'''+svg+'''</div></div><script>
const board=document.querySelector('#board'),zoom=document.querySelector('#zoom');function fit(){board.style.width=(innerWidth-50)+'px';zoom.value=innerWidth-50}zoom.oninput=()=>board.style.width=zoom.value+'px';document.querySelector('#fit').onclick=fit;document.querySelectorAll('[data-layer]').forEach(e=>e.onchange=()=>document.querySelectorAll('.'+e.dataset.layer).forEach(g=>g.style.display=e.checked?'':'none'));fit();</script></html>'''
(OUT/'逆鳞_关卡草图_可缩放查看.html').write_text(viewer,encoding='utf-8')

notes='''《逆鳞》关卡平面草图 v0.1 — 设计说明
日期：2026-10-16

用途
本图用于讨论关卡空间、推进条件与战斗节奏。依据提供的 ZIP、项目 Docs/AI/State.md 和 AssetReadiness.md 整理；没有读取 .umap 二进制来推断布局，也没有修改 UE 场景、玩法源码或项目配置。

已知依据
1. 妖族龙子闯宗门救挚友；PC VR、双手柄、单人三关，首次成功目标 20–30 分钟。
2. 第一关四段：山门外、山门内、演武场、丹道入口；总长约 7 分钟。
3. 第二关同一法阵守点，建阵→截阵→围攻→解封；基础有效守点 240 秒，总长约 6 分钟。干扰拖慢实际时长，完成还需处理规定剩余威胁。
4. Boss 三阶段；反弹削护阵、刃气打断阵眼、破阵后约 5 秒输出；目标约 6–8 分钟。普通刃气也能推进，精准反弹提升效率。
5. 两次主要升级，第一关结束二级保底，第二关结束三级保底；节点、守点阶段和 Boss 阶段入口重试。
6. 最新工程状态显示以 L_CombatLabVR 等测试图验证模块；完整三关属于设计与后续生产范围。当前实验室敌人生命 30、近战伤害 10，不等同于正式关卡“一刀清杂兵”的目标。

草图中的新增建议（不是既有实现）
1. 三张地图组合成一张宗门救援总览；图上拼接位置表达叙事空间关系，跨图转场可独立实现。
2. 第一关 01 约1分钟、02约2分钟、03约2.5分钟、04约1.5分钟；02教学格挡与精准反弹、03范围震荡、04组合检验。
3. 第二关玩家位于法阵后方，挚友约在前方4米。两路近战与两处施法位均在前半区，避免环背保护。刷怪入口需留展示与预警距离；近战沿独立接近路径到站位前缘，初始图标不表示近战攻击距离。
4. 御风桥是新增的无战斗过渡/休整意象，可作为跨图淡出前的观景段，切勿默认采用连续镜头推进。
5. 封山台是新增地名与空间提案，承接资料包“出口桥”的 Boss 战意图。玩家与宗主建议约10米，三阶段保持同一站位；08归途仅为胜利后推进，不在战斗中穿过Boss。
6. 演武场约30×24米；丹台、决战台直径约28米。尺寸仅供灰盒起点，图面不统一缩尺。其他连接走廊、房屋与悬崖轮廓为设计表达，没有测绘现有 AsianTemple 场景。
7. 第一关7分＋第二关6分＋第三关7–8分（含入场）＋其余叙事/转场/休整2–4分＝22–25分钟。是目标估时，未实测；干扰、失败重试另计。
8. CP 标在战斗点旁表示入口快照，不是玩家必须走到的物理交互装置。二级/三级奖励符号表示关末保底事件，不是拾取物。

建议节点与阻断条件
01 山门外：完成挥砍引导并击败教学敌人；目标完成后推进。
02 山门内：近远程混合波次全部生成且已处理；通过精准格挡可获得明显效率奖励，推进不强制要求精准。
03 演武场：有限群体波次清完，验证范围震荡；基础招式亦能完成。
04 丹道入口：执事与支援处理完，发放二级保底，进入守丹台。
05 守丹台：法阵进度100%锁定成功候选，停止后续波次，处理规定残余威胁，播放获救事件并发放三级保底。
06 御风桥：威胁清零后短暂休整，提示下一目标，再淡出到 Boss 入场点。
07 封山台：按 Boss 实际生命/护阵/阶段驱动，击败才开放出口；三阶段不当成三个地理房间。
08 归途：宗主被击败后携挚友离开，完成主线。

灰盒评审重点
先以02山门内、05守丹台、07封山台三个切片验证：远程提示能否越过近战看清；拦截法阵弹道是否在自然伸手范围；10米Boss是否适合刃气/阵眼辨认；节点转移是否舒适。依次再连通完整三关。
计时需区分有效战斗、叙事、转场、暂停及失败重试；不得把图上的建议分钟数作为完成计时器。

文件
逆鳞_关卡平面草图_v01.png：3200×2100演示图片。
逆鳞_关卡平面草图_v01.svg：自包含矢量源稿，概念图以JPEG嵌入，可在Figma/Illustrator/Inkscape等工具继续编辑。
逆鳞_关卡草图_可缩放查看.html：本地查看器，支持缩放、切换路线/威胁/节点注释图层。
build_plan.py：可复现SVG与HTML的生成脚本。概念图来自原资料包，不是工程实机截图。
'''
(OUT/'设计说明_v01.txt').write_text(notes,encoding='utf-8')
print(OUT/'逆鳞_关卡平面草图_v01.svg')
