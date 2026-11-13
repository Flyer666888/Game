from pathlib import Path
import html, math, json, subprocess, xml.etree.ElementTree as ET
from PIL import Image

OUT = Path(__file__).resolve().parent
W, H = 3600, 2830
P=[]
INK='#244b43'; MUTED='#5d7a6c'; GOLD='#bf873d'; TEAL='#278a80'; AXIS='#ad5946'
def add(s): P.append(s)
def path(d, fill='none', stroke=INK, sw=2, extra=''):
    add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round" {extra}/>')
def rect(x,y,w,h,fill,stroke='none',sw=1,r=0,extra=''):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def ellipse(x,y,rx,ry,fill,stroke='none',sw=1,extra=''):
    add(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
def circle(x,y,r,fill,stroke='none',sw=1,extra=''): ellipse(x,y,r,r,fill,stroke,sw,extra)
def text(x,y,s,size=28,color=INK,weight=400,anchor='start',extra=''):
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{html.escape(s)}</text>')
def lines(x,y,ss,size=27,color=MUTED,step=41,weight=400):
    for i,s in enumerate(ss): text(x,y+i*step,s,size,color,weight)
def group(id): add(f'<g id="{id}" class="{id}">')
def end(): add('</g>')
def badge(x,y,n,col=INK):
    circle(x,y,30,'#f3e9cd',col,3); text(x,y+10,f'{n:02}',28,col,700,'middle')
def roof(x,y,w,h,rot=0):
    add(f'<g transform="rotate({rot} {x+w/2} {y+h/2})">')
    rect(x+12,y+21,w,h,'#41675a',r=5,extra='opacity=".22"')
    rect(x+18,y+15,w-36,h-25,'#b1b392','#727c61',3,3)
    # Curved eaves, two roof pitches, and generous footprint.
    path(f'M{x-12} {y+5} Q{x+18} {y+22} {x+w*.24} {y+14} L{x+w*.5} {y-12} L{x+w*.76} {y+14} Q{x+w-18} {y+22} {x+w+12} {y+5} L{x+w+2} {y+h*.48} Q{x+w-12} {y+h*.55} {x+w+14} {y+h+8} Q{x+w*.5} {y+h-10} {x-14} {y+h+8} Q{x+12} {y+h*.55} {x-2} {y+h*.48} Z', '#315f55','#244a43',3)
    path(f'M{x-2} {y+h*.49} Q{x+w*.5} {y+h*.26} {x+w+2} {y+h*.49}',stroke='#92aa85',sw=3)
    path(f'M{x+5} {y+h*.54} Q{x+w*.5} {y+h*.68} {x+w-5} {y+h*.54}',stroke='#203f39',sw=3)
    path(f'M{x+10} {y+11} Q{x+w*.5} {y-8} {x+w-10} {y+11}',stroke='#c1a66a',sw=5)
    for j in range(1,int(w/17)):
        xx=x+j*17
        path(f'M{xx} {y+23} L{xx} {y+h*.40}',stroke='#688778',sw=1.7)
        path(f'M{xx} {y+h*.66} L{xx} {y+h-5}',stroke='#638376',sw=1.7)
    for xx in (x+4,x+w-4):
        circle(xx,y+9,5,'#c9b375'); path(f'M{xx} {y+6} l0 -9',stroke='#c9b375',sw=3)
    end()
def octagon(x,y,w,h,c=26):
    return [(x+c,y),(x+w-c,y),(x+w,y+c),(x+w,y+h-c),(x+w-c,y+h),(x+c,y+h),(x,y+h-c),(x,y+c)]
def points_path(pts): return 'M'+' L'.join(f'{x:.1f} {y:.1f}' for x,y in pts)+' Z'
def court(x,y,w,h,depth=45):
    pts=octagon(x,y,w,h)
    path(points_path([(a+3,b+depth) for a,b in pts]),'#38695e','#315c52',3)
    for xx in range(int(x+25),int(x+w),40):
        path(f'M{xx} {y+h-2} l3 {depth-4}',stroke='#6d9180',sw=2)
    path(points_path(pts),'url(#paving)','#789281',4)
    path(points_path(octagon(x+13,y+13,w-26,h-26,18)),'none','#a6b49a',2)
    # Railings deliberately stop at openings facing the mountain.
    path(f'M{x+24} {y+h-17} H{x+w-24}',stroke='#929e83',sw=5)
    for xx in range(int(x+35),int(x+w-20),42): path(f'M{xx} {y+h-29} v14',stroke='#73846b',sw=3)
def roundcourt(cx,cy,r,depth=65):
    ellipse(cx+3,cy+depth,r,r*.83,'#37695f','#315b50',3)
    for a in range(8,176,13):
        rad=math.radians(a); xx=cx+r*math.cos(rad); yy=cy+r*.83*math.sin(rad)
        path(f'M{xx} {yy} l3 {depth-7}',stroke='#6c9180',sw=2)
    ellipse(cx,cy,r,r*.83,'url(#paving)','#78917b',5)
    ellipse(cx,cy,r-16,(r-16)*.83,'none','#9cae92',3)
def bridge(d,sw=65):
    path(d,stroke='#345e52',sw=sw+20)
    path(d,stroke='#b4b295',sw=sw+9)
    path(d,stroke='#d9d5b6',sw=sw)
    path(d,stroke='#819b83',sw=sw-14,extra='stroke-dasharray="3 13"')
def route(d): path(d,stroke='#f9f1cf',sw=12); path(d,stroke=GOLD,sw=6,extra='marker-end="url(#arrowGold)" stroke-dasharray="19 12"')
T=(2315,545)
nodes={1:(450,1705),2:(610,1170),3:(1120,1540),4:(1235,805),5:(1650,1560),6:(2180,970),7:(2317,645),8:(2580,395)}
# User clarified the overview camera: major facades all face screen-down.
# Player/observation points are placed directly south of the corresponding door.
halls={1:(450,1513,250,76),2:(610,1040,270,90),3:(1120,1220,300,100),4:(1235,690,260,77),5:(1650,1180,400,140),7:(2317,373,310,116)}
doors={}
def oriented_hall(cx,cy,w,h,px,py,label=None,gap=0):
    dx,dy=px-cx,py-cy; nn=math.hypot(dx,dy); ux,uy=dx/nn,dy/nn
    rot=math.degrees(math.atan2(dy,dx))-90
    if gap:
        # Two major roof masses flank a real open sight passage. The low lintel is not a roof.
        rr=math.radians(rot)
        half=(w-gap)/2
        for side in (-1,1):
            local=side*(gap/2+half/2)
            hx=cx+local*math.cos(rr); hy=cy+local*math.sin(rr)
            roof(hx-half/2,hy-h/2,half,h,rot)
        add(f'<g transform="rotate({rot} {cx} {cy})">')
        rect(cx-gap/2,cy-h*.7,gap,h*1.7,'#d2dac0','#9fb394',1)
        path(f'M{cx-gap/2} {cy+h/2-2} H{cx+gap/2}',stroke='#c0a56a',sw=6)
        for side in (-1,1):
            rect(cx+side*gap/2-5,cy+h/2-7,10,17,'#825d45','#584d39',1)
        if label:
            text(cx-w*.29,cy+9,label,24,'#eadab0',600,'middle')
            text(cx+w*.29,cy+9,'侧殿',24,'#eadab0',600,'middle')
        end()
    else:
        roof(cx-w/2,cy-h/2,w,h,rot)
    add(f'<g transform="rotate({rot} {cx} {cy})">')
    # The front wall and its central door are explicit, rather than inferred from roof shape.
    if not gap:
        rect(cx-w*.35,cy+h/2-2,w*.7,10,'#8f5a46','#584d39',1)
        rect(cx-21,cy+h/2-4,42,18,'#293f35','#ceb985',2,2)
    for j in range(4):
        rect(cx-37-j*3,cy+h/2+16+j*8,74+j*6,6,'#d0c5a1','#8f9b7e',1)
    path(f'M{cx} {cy+h/2+20} v50',stroke=AXIS,sw=3,extra='marker-end="url(#arrowRed)"')
    if label and not gap: text(cx,cy+9,label,28,'#eadab0',600,'middle')
    end()
    return (cx+ux*(h/2+14),cy+uy*(h/2+14))
def inward_door(x,y,side='E'):
    # Side galleries open into the court; arrows point out of the building into its courtyard.
    a=0 if side=='E' else 180
    add(f'<g transform="rotate({a} {x} {y})">')
    rect(x-6,y-20,12,40,'#293f35','#ccb77c',2,2)
    for j in range(3): rect(x+9+j*9,y-28,6,56,'#d4c9a5','#8d9b7b',1)
    path(f'M{x+12} {y} h57',stroke=AXIS,sw=3,extra='marker-end="url(#arrowRed)"')
    end()
def axis_line(p,door,label=None):
    px,py=p; tx,ty=door
    path(f'M{px} {py} L{tx} {ty}',stroke='#f5e6cf',sw=8)
    path(f'M{px} {py} L{tx} {ty}',stroke=AXIS,sw=3.5,extra='stroke-dasharray="13 7 3 7" marker-end="url(#arrowRed)"')
    if label: text((px+tx)/2-20,(py+ty)/2+9,label,22,AXIS,600,'end')
def entry_steps(x,y,door):
    dx,dy=door[0]-x,door[1]-y; rot=math.degrees(math.atan2(dy,dx))+90
    add(f'<g transform="rotate({rot} {x} {y})">')
    for j in range(4): rect(x-38-j*3,y+j*8,76+j*6,6,'#d2c7a4','#8b997a',1)
    end()
def sight(x,y,target=T,band=34):
    tx,ty=target
    path(f'M{x} {y} L{tx} {ty}',stroke='#8ad3be',sw=band,extra='opacity=".14"')
    path(f'M{x} {y} L{tx} {ty}',stroke=TEAL,sw=2.7,extra='stroke-dasharray="10 11" opacity=".72" marker-end="url(#arrowTeal)"')
def player(x,y,target=T):
    tx,ty=target; dx,dy=tx-x,ty-y; n=math.hypot(dx,dy); ux,uy=dx/n,dy/n
    a=math.atan2(dy,dx); r=116
    p1=(x+math.cos(a-.98)*r,y+math.sin(a-.98)*r); p2=(x+math.cos(a+.98)*r,y+math.sin(a+.98)*r)
    path(f'M{x} {y} L{p1[0]} {p1[1]} Q{x+ux*147} {y+uy*147} {p2[0]} {p2[1]} Z','#69cbb4',TEAL,2,extra='fill-opacity=".13" stroke-dasharray="6 7"')
    circle(x,y,19,'#2b7463','#f3efd5',4)
    path(f'M{x+ux*11} {y+uy*11} L{x-ux*6-uy*7} {y-uy*6+ux*7} L{x-ux*6+uy*7} {y-uy*6-ux*7} Z','#f6efd5','none')
    text(x-27,y+37,'P',21,INK,700)
def enemy(x,y,kind='melee'):
    if kind=='melee': path(f'M{x} {y-13} l-13 25 h26 Z','#ca755b','#924c3d',2)
    else: rect(x-10,y-10,20,20,'#e5b363','#99743e',2,0,extra=f'transform="rotate(45 {x} {y})"')
def furnace(x,y,s=1):
    add(f'<g transform="translate({x} {y}) scale({s})">')
    circle(0,0,34,'#b89e63','#6b6b47',4); circle(0,0,22,'#4b7160','#d9bb72',3)
    path('M-28 -25 Q0 -47 28 -25 M-35 -2 Q-53 -25 -45 -34 M35 -2 Q53 -25 45 -34 M-17 29 l-7 18 M17 29 l7 18',stroke='#6b704d',sw=7)
    circle(0,0,10,'#e4be6c'); end()
def pine(x,y,s=1):
    add(f'<g transform="translate({x} {y}) scale({s})">')
    for d in ['M0 110 Q20 22 -18 -52','M8 73 Q-30 42 -72 28','M0 28 Q50 1 93 -24','M-7 -15 Q-65 -35 -90 -60']:
        path(d,stroke='#6b8261',sw=17)
    for dx,dy,rx,ry in [(-70,-57,70,30),(-20,-78,66,29),(49,-47,75,31),(88,-18,60,27),(-56,16,60,27),(20,-2,70,29)]:
        ellipse(dx,dy,rx,ry,'#72997d','#557c65',3)
        path(f'M{dx-rx*.6} {dy} Q{dx} {dy+ry*.5} {dx+rx*.55} {dy-5}',stroke='#a7b28a',sw=2)
    path('M0 91 Q-5 135 -65 157 M9 96 Q45 141 93 151 M2 109 Q20 152 -3 181',stroke='#738365',sw=12)
    end()
def node_title(x,y,n,name,elev,sub,anchor='start',width=470):
    rect(x-36,y-49,width,94,'#f1ecd7','#a3b79d',1.4,12,extra='fill-opacity=".95"')
    badge(x,y-10,n)
    xx=x+45
    text(xx,y-9,name,34,INK,700)
    text(xx,y+25,f'+{elev}m  ·  {sub}',24,MUTED)
def tag(x,y,s,fill='#f6efda'):
    rect(x,y-26,len(s)*22+24,37,fill,'#a3b59d',1.5,8); text(x+12,y,s,22,INK,600)

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('''<defs>
<pattern id="paper" width="140" height="140" patternUnits="userSpaceOnUse"><rect width="140" height="140" fill="#f2ecd8"/><path d="M0 28H140M25 0V140M0 111H140" stroke="#d1cfb4" stroke-width=".5" opacity=".18"/></pattern>
<pattern id="paving" width="34" height="34" patternUnits="userSpaceOnUse"><rect width="34" height="34" fill="#d4d3b5"/><path d="M34 0H0V34" fill="none" stroke="#a8b398" stroke-width="1.2"/></pattern>
<linearGradient id="sea" x2="1" y2="1"><stop stop-color="#dce9dc"/><stop offset="1" stop-color="#c2dbd4"/></linearGradient>
<marker id="arrowGold" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#bf873d"/></marker>
<marker id="arrowTeal" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#278a80"/></marker>
<marker id="arrowRed" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#ad5946"/></marker>
</defs>''')
add('<g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">')
rect(0,0,W,H,'url(#paper)')
rect(73,64,8,108,GOLD)
text(108,116,'逆鳞',62,INK,700)
text(295,114,'登山关卡平面研究',47,INK,600)
text(109,163,'低处入宗 / 丹院守阵 / 登顶破封',27,MUTED)
text(3512,103,'中式仙侠 · 三关八节点 · 单人 PC VR',27,INK,500,'end')
text(3512,149,'v03   /   正面对总览镜头   /   2026.10.16',24,MUTED,400,'end')
path('M80 195 H3520',stroke='#aeb99b',sw=2)

# The map remains top-down; the cliff skirt supplies depth cues only.
rect(76,230,2630,1784,'url(#sea)','#a7bdac',2,24)
text(113,280,'01—08  /  露天平台与登山序列',27,INK,600)
text(2667,1979,'平面主导 · 非统一比例 · 相对高程提案',22,MUTED,400,'end')
group('cloud-layer')
for x,y,rx,ry in [(225,1840,200,70),(675,1930,380,59),(1310,1850,370,110),(2090,1850,350,80),(2500,1320,240,70),(1780,530,340,60),(430,640,290,60),(1560,1040,180,70)]:
    ellipse(x,y,rx,ry,'#e5eee0',extra='opacity=".8"')
    path(f'M{x-rx*.9} {y} C{x-rx*.5} {y-ry*1.5} {x} {y+ry*.9} {x+rx*.55} {y-ry*.3}',stroke='#9fc4b5',sw=3,extra='opacity=".55"')
    path(f'M{x-rx*.6} {y+ry*.35} Q{x} {y+ry*1.1} {x+rx*.88} {y+ry*.18}',stroke='#bbd7c7',sw=3)
end()
text(1360,1937,'云海谷地  −35～−5m  /  低云下沉，保持峰顶与台缘轮廓',24,'#688f7a',400,'middle')

# Mountain skirts and contour bands, kept subordinate to flat combat floors.
group('terrain-layer')
path('M175 1780 Q100 1640 230 1485 Q250 1290 340 1150 Q340 960 540 915 Q740 835 775 1010 L920 1170 Q940 1000 1030 900 Q940 680 1090 625 Q1310 540 1430 700 Q1480 840 1400 1000 L1430 1155 Q1620 1040 1870 1130 Q2040 1100 2045 965 Q1985 805 2070 700 Q2000 530 2115 350 Q2280 210 2495 345 Q2630 470 2605 655 L2475 875 Q2400 1040 2295 1145 Q2205 1435 2110 1660 Q1890 1845 1580 1735 L1320 1640 Q1040 1770 850 1605 Q670 1445 690 1420 Q610 1635 580 1780 Q350 1910 175 1780Z','#95b69a','#729780',3)
for off in (0,24,48):
    path(f'M{175+off} {1760+off*.1} Q{100+off} 1610 {255+off} 1485 Q{260+off} 1295 {385+off} 1185',stroke='#c0c9a5',sw=3,extra='opacity=".72"')
    path(f'M{1010+off} 920 Q{920+off} 710 {1110+off} 650 Q{1290+off} 600 {1390+off} 760',stroke='#bfcca9',sw=3,extra='opacity=".7"')
    path(f'M{1410+off} {1620+off*.25} Q{1730+off*.3} {1810+off*.25} {2050+off*.15} {1630+off*.4}',stroke='#c0c9a5',sw=3,extra='opacity=".8"')
    path(f'M{2100+off} {691+off*.3} Q{1980+off} 400 {2215+off*.5} {305+off*.3} Q2450 {260+off*.3} {2560+off*.4} {470+off*.3}',stroke='#c1cbaa',sw=3,extra='opacity=".7"')
text(980,1892,'崖壁层级与等高线仅表示地形意向；战斗面均为水平石台',22,'#769482')
end()

# Traversal folds around the open valley; vertical changes occur between courts.
group('connection-layer')
bridge('M410 1570 Q405 1460 520 1320',65)
bridge('M750 1235 Q805 1445 848 1580 Q865 1650 1045 1620',67)
bridge('M910 1260 Q1010 1080 1140 955',66)
bridge('M1370 892 Q1410 1090 1370 1300 Q1336 1450 1450 1570',66)
bridge('M1970 1340 Q2090 1240 2155 1070',65)
bridge('M2180 865 Q2220 810 2317 770',66)
bridge('M2460 475 Q2515 455 2535 414',54)
end()

# Broad, clear, slightly tiered courts.
group('floor-layer')
court(245,1510,380,292,46)
court(410,1000,402,338,52)
court(865,1110,535,506,57)
court(1072,656,345,307,58)
court(1390,1110,715,632,80)
court(2084,843,202,246,65)
roundcourt(2315,548,243,124)
court(2500,317,167,152,72)
# Temple plinths and garden strips suggest enlarged building footprints.
for x,y,w,h in [(224,1528,128,224),(381,1036,130,278),(855,1370,136,208),(1260,1495,125,109),(1067,680,115,202),(1404,1400,125,260),(1950,1470,125,200)]:
    rect(x,y,w,h,'#b6bd99','#7d987e',2,3)
end()

# Final landmark is an actual rocky summit terrace plus sword crown.
group('landmark-layer')
for a in (18,45,72,108,135,165):
    r=math.radians(a); xx=2315+212*math.cos(r); yy=548+175*math.sin(r)
    path(f'M{xx} {yy} l4 63 l-22 14',stroke='#5c8270',sw=6)
ellipse(2315,548,169,140,'none','#92a78b',3)
ellipse(2315,548,155,128,'none','#9db498',2,extra='stroke-dasharray="9 8"')
ellipse(2448,483,73,60,'#729c86','#4f7a64',4)
ellipse(2448,483,57,47,'none','#d6c887',4)
for a in range(0,360,60):
    rad=math.radians(a); xx=2448+59*math.cos(rad); yy=483+48*math.sin(rad)
    add(f'<g transform="rotate({a+15} {xx} {yy})">')
    path(f'M{xx} {yy-43} l9 22 l-5 39 h-8 l-5 -39 Z','#d5c284','#6e825d',2)
    path(f'M{xx-17} {yy+12} h34',stroke='#b5a268',sw=5); end()
text(2448,573,'悬剑冠',24,INK,600,'middle')
text(2448,605,'最高 +158m',22,MUTED,400,'middle')
text(2320,766,'实体岩峰台缘  +132m',24,INK,600,'middle')
end()

# Architecture is now a major visible mass. Central view openings are preserved.
group('architecture-layer')
roof(225,1537,120,202)
roof(382,1030,119,285)
roof(423,1301,264,74)
roof(855,1370,130,208)
roof(1260,1505,125,89)
roof(1058,686,118,204)
roof(1404,1400,124,260)
roof(1950,1470,124,200)
for i,(cx,cy,ww,hh) in halls.items():
    doors[i]=oriented_hall(cx,cy,ww,hh,*nodes[i],label='丹殿' if i==5 else ('峰顶主殿' if i==7 else None))
inward_door(985,1475,'E'); inward_door(1528,1530,'E'); inward_door(1950,1570,'W')
roof(2520,308,126,70)
# Gate pillar stones and side prayer lanterns.
for x,y in [(350,1554),(535,1554),(440,1272),(670,1272),(905,1295),(1220,1295),(1190,730),(1350,730),(1538,1250),(1938,1250),(2140,686),(2465,686)]:
    rect(x-7,y-7,14,14,'#c1ba8c','#6e896f',2,2)
    circle(x,y,4,'#677f65')
end()

# Side and rear plants stay outside the protected central vistas.
group('vegetation-layer')
pine(293,790,1.52); pine(2352,1630,1.64); pine(912,507,1.08)
text(210,1015,'侧后巨松',23,'#5d8166')
text(2190,1876,'巨木与根系在侧后方',24,'#5d8166')
text(2190,1910,'树冠避开望峰廊道',22,'#789279')
end()

# Explicit sightlines are a design protection overlay, not a 3D occlusion result.
group('sight-layer')
for i in range(1,7): sight(*nodes[i],band=38)
end()

group('route-layer')
for d in ['M450 1600 Q415 1450 555 1290','M750 1240 Q805 1445 848 1580 Q865 1670 1040 1650 L1120 1648 L1120 1615','M910 1265 Q1010 1090 1140 935','M1380 905 Q1410 1090 1370 1300 Q1330 1490 1470 1610 Q1550 1690 1650 1668 L1650 1625','M1960 1330 Q2110 1225 2168 1050','M2192 870 Q2220 810 2317 770 L2317 720','M2460 468 Q2510 450 2548 416']:
    route(d)
for x,y,s in [(400,1440,'↑ +12m'),(765,1450,'↑ +16m'),(990,1065,'↑ +16m'),(1435,1035,'↑ +28m'),(2090,1280,'↑ +32m'),(2190,824,'↑ +28m')]:
    rect(x-5,y-29,135,40,'#f3e6c6',r=7); text(x+8,y,s,23,'#9c6d33',600)
end()

# Battle targets and enemies share the forward sector with the peak.
group('combat-layer')
for i in range(1,8):
    if i in doors:
        axis_line(nodes[i],doors[i])
        px,py=nodes[i]; dx,dy=px-doors[i][0],py-doors[i][1]; nn=math.hypot(dx,dy)
        entry_steps(px+dx/nn*108,py+dy/nn*108,doors[i])
    player(*nodes[i],target=doors.get(i,T))
for x,y,k in [(478,1628,'melee'),(650,1114,'melee'),(725,1110,'caster'),(1035,1390,'melee'),(1170,1380,'melee'),(1190,1350,'caster'),(1290,771,'melee'),(1338,800,'caster'),(1590,1450,'melee'),(1860,1430,'melee'),(1550,1365,'caster'),(1890,1350,'caster')]: enemy(x,y,k)
# Friend and alchemical furnace stay ahead of fixed defense position.
furnace(1567,1430,1.05)
circle(1650,1520,13,'#d1c78f','#6f815b',3)
text(1690,1527,'挚友 ≈4m',22,INK,500)
text(1567,1372,'炼丹炉',25,INK,600,'middle')
ellipse(1745,1480,153,126,'none','#99aa80',2,extra='stroke-dasharray="9 9"')
text(1585,1605,'殿前战斗净空 ≈28m',22,INK,500)
text(1755,1470,'法阵',22,INK,600,'middle')
circle(2317,540,21,'#b96b53','#f1dfb6',4)
path('M2317 518 l-10 -17 M2317 518 l10 -17',stroke='#965d46',sw=3)
text(2356,632,'宗主 ≈10m',22,INK,600)
text(2345,702,'战斗净空 ≈28m',22,INK,500,'middle')
for x,y in [(468,1753),(703,1304),(1284,1581),(1350,933),(1910,1700),(2220,1086),(2220,726)]:
    rect(x,y-27,45,29,'#f5eed4','#8eaa8a',2,5); text(x+22,y-6,'CP',17,INK,600,'middle')
tag(1250,1002,'关末二级保底')
tag(1818,1773,'获救 / 三级保底')
end()

group('annotation-layer')
node_title(205,1887,1,'山门外',0,'首见山顶')
node_title(392,943,2,'山门内',12,'开敞山门院')
node_title(883,1747,3,'演武场',28,'平整战台')
node_title(1073,578,4,'丹道入口',44,'望峰开口')
node_title(1510,1035,5,'守丹台',72,'正对总览镜头 / 侧向望峰',width=620)
node_title(2144,1210,6,'御风桥',104,'休整 / 淡出',width=525)
node_title(1720,365,7,'山顶封山台',132,'最终目标',width=425)
path('M2110 363 L2200 442',stroke='#658776',sw=2)
rect(2480,698,188,164,'#f1ecd7','#a3b79d',1.4,12,extra='fill-opacity=".95"')
badge(2574,734,8)
text(2574,790,'归途',29,INK,700,'middle')
text(2574,823,'+132m',23,MUTED,400,'middle')
text(2574,851,'胜利后开放',21,MUTED,400,'middle')
text(360,1771,'山门殿',22,INK,600)
text(474,1166,'山',25,'#e1d6af',600,'middle'); text(474,1200,'门',25,'#e1d6af',600,'middle')
text(1660,1695,'进场台阶',22,INK,600,'middle')
text(1465,1480,'西',24,'#ddd1a4',600,'middle'); text(1465,1515,'廊',24,'#ddd1a4',600,'middle')
text(2010,1540,'东',24,'#ddd1a4',600,'middle'); text(2010,1575,'廊',24,'#ddd1a4',600,'middle')
text(1900,1300,'右侧开口望峰',22,TEAL,600)
tag(767,813,'谷地全程露天')
tag(1720,756,'望峰保护廊道')
path('M1708 752 L1633 788',stroke=TEAL,sw=2)
text(1555,905,'主峰台缘 + 悬剑冠',25,TEAL,600)
text(1555,942,'共用唯一最终地标',23,TEAL)
text(113,1980,'节点间高差意向；默认 VR 淡出，连续栈道须另行验证。',23,MUTED)
path('M2600 1880 V1755',stroke=AXIS,sw=5,extra='marker-end="url(#arrowRed)"')
text(2655,1925,'总览镜头视向 ↑',24,AXIS,600,'end')
end()

# Right column: make the requested increase and courtyard additions reviewable.
rect(2750,230,774,1784,'#ebe6cf','#acb99d',2,24)
text(2792,292,'正面对总览镜头',36,INK,700)
text(2792,335,'总览观察方向：从图下方看向图上方',26,MUTED)
path('M2792 365 H3480',stroke='#b0bb9c',sw=2)
for y,n,title,ss in [(411,'A','主要殿宇正立面统一朝图下',['主殿屋脊宽向近水平，正门与台阶朝观察者。','主角观察点 P 在殿门正南，来路弯入正轴。']), (545,'B','丹台正殿恢复完整正立面',['大丹殿位于前方，门洞与 P 构成竖直主轴。','右侧留望峰开口，炉置侧边，翼廊朝向内院。'])]:
    circle(2810,y-10,21,INK); text(2810,y-3,n,20,'#e9dfb9',700,'middle'); text(2850,y,title,28,INK,700); lines(2792,y+46,ss,25,MUTED,37)
text(2792,717,'丹院 / 总览朝向示意',29,INK,700)
text(3480,715,'殿门朝图下方',23,AXIS,500,'end')
rect(2792,746,690,562,'#d9dfc1','#a4b393',2,14)
court(2830,770,612,481,33)
# Diagram intentionally oriented by the mountain view, not global north.
roof(2834,962,103,196)
roof(3336,1110,103,70)
minidoor=oriented_hall(3055,870,400,100,3055,1150,label='丹殿正立面')
inward_door(2937,1072,'E'); inward_door(3336,1145,'W')
path('M3055 1150 L3405 774',stroke='#63b8a0',sw=48,extra='opacity=".15"')
path('M3055 1150 L3405 774',stroke=TEAL,sw=3,extra='stroke-dasharray="10 8" marker-end="url(#arrowTeal)"')
axis_line((3055,1150),minidoor)
entry_steps(3055,1235,minidoor)
ellipse(3075,1110,118,94,'none','#96a782',3,extra='stroke-dasharray="9 7"')
player(3055,1150,target=minidoor); furnace(2985,1040,.8)
circle(3055,1110,10,'#d1c78f','#6f815b',2)
enemy(3040,980); enemy(3270,1100); enemy(3320,1092,'caster')
text(3377,813,'主峰',22,TEAL,600,'end')
text(3330,940,'侧向望峰',22,TEAL,600,'end')
text(3090,1190,'P 观察 / 守阵站位',22,INK,600,'middle')
text(3140,1258,'入口台阶',22,INK,600,'middle')
text(2892,1068,'廊',25,'#ddd0a4',600,'middle'); text(3388,1157,'廊',25,'#ddd0a4',600,'middle')
path('M3275 1230 V1140',stroke=AXIS,sw=4,extra='marker-end="url(#arrowRed)"')
text(3315,1267,'总览镜头 ↑',22,AXIS,600)
text(2813,1283,'正立面朝总览观察者；来路先弯入殿门正南的观察点。',23,MUTED)
text(2792,1378,'纵深与可见性约束',30,INK,700)
lines(2792,1422,['• 主殿门口正南是 P 点，朱色轴呈图面竖直。','• 青色望峰轴偏右，不强制与殿门主轴重合。','• 屋脊、树冠从保护廊道退让；低云沉在谷底。','• 峰顶殿门正对 Boss 前院，剑冠偏侧退让。','• 全可达范围与转场落点仍须在 UE 复核视线。'],25,MUTED,46)
path('M2792 1652 H3480',stroke='#b0bb9c',sw=2)
text(2792,1700,'图例',29,INK,700)
path('M2800 1744 H2880',stroke=GOLD,sw=6,extra='stroke-dasharray="15 10" marker-end="url(#arrowGold)"'); text(2902,1752,'推进方向 / 高差',25,INK)
path('M2800 1791 H2880',stroke=TEAL,sw=3,extra='stroke-dasharray="10 9"'); text(2902,1799,'望峰意图 / 保护廊道',25,INK)
path('M2800 1838 H2880',stroke=AXIS,sw=3.5,extra='stroke-dasharray="13 7 3 7" marker-end="url(#arrowRed)"'); text(2902,1846,'玩家进场视线 / 殿门朝向',25,INK)
circle(2817,1885,15,'#2b7463','#f3efd5',3); enemy(2870,1885); enemy(2910,1885,'caster'); text(2950,1893,'玩家 / 近战 / 施法入口',25,INK)
text(2792,1955,'建筑、距离、高程均为设计建议，未在 UE 验证。',22,MUTED)

# Route-unrolled elevation strip. Explicitly not an optical cross-section.
rect(76,2050,3448,342,'#e7e4cb','#aab79a',2,22)
text(113,2105,'路线展开高程',32,INK,700)
text(3485,2104,'各战斗面保持水平；这不是实际直线视线剖面，不能用于证明无遮挡。',24,MUTED,400,'end')
ex=[225,620,1015,1410,1805,2200,2595,2990]
heights=[0,12,28,44,72,104,132,132]
names=['山门外','山门内','演武场','丹道入口','守丹台','御风桥','山顶封山台','归途']
ys=[2322-h*1.14 for h in heights]
path('M170 2332 H3415',stroke='#b9c1a2',sw=2)
for i in range(7):
    path(f'M{ex[i]+70} {ys[i]} L{ex[i+1]-70} {ys[i+1]}',stroke=GOLD,sw=5)
for i,(x,yy,h,n) in enumerate(zip(ex,ys,heights,names)):
    path(f'M{x-70} {yy} H{x+70}',stroke=INK,sw=8)
    circle(x,yy,8,'#f5ebcc',INK,3)
    text(x,yy-21,f'{i+1:02}  +{h}m',25,INK,700,'middle')
    text(x,2370,n,23,MUTED,500,'middle')
path(f'M{ex[6]} {ys[6]-11} v-30 l-10 -19 l10 -24 l10 24 l-10 19',stroke='#9e8c57',sw=5)
text(3210,2152,'剑冠最高 +158m',24,'#8e7c48',600)
text(3210,2192,'低处至峰顶约 +132m',24,MUTED)
text(3210,2232,'抬升在节点之间完成',24,MUTED)

# Eight concise condition cards retain original progression rules.
cards=[('01  山门外','完成挥砍引导与教学敌人。','约 1 min / 低处首见峰顶'),('02  山门内','远近混合波次全部处理。','约 2 min / 格挡与反弹'),('03  演武场','有限群体波次清完。','约 2.5 min / 范围震荡'),('04  丹道入口','执事与支援清完 → 二级保底。','约 1.5 min / 组合检验'),('05  守丹台','有效守点 240s + 规定残余威胁。','约 6 min / 获救 → 三级保底'),('06  御风桥','威胁清零 → 休整 → 淡出。','无战斗 / 确认登顶破封目标'),('07  山顶封山台','三阶段同一场地；击败宗主解封。','约 6–8 min / 反弹 → 破阵 → 输出'),('08  归途','胜利后携友离开，完成主线。','山顶收束 / 战斗中出口锁定')]
for i,(title,cond,sub) in enumerate(cards):
    col=i%4; row=i//4; x=76+col*870; y=2430+row*154
    rect(x,y,838,132,'#efe8cf','#c0c4a6',1.5,13)
    text(x+23,y+38,title,28,INK,700)
    text(x+23,y+77,cond,24,INK)
    text(x+23,y+111,sub,22,MUTED)
text(78,2789,'三关总目标约 22–25 分钟，未实测；图面是关卡与美术讨论稿，不代表 UE 场景已完成。',23,MUTED)
text(3521,2789,'NILIN / LEVEL DESIGN STUDY / v03',21,MUTED,500,'end',extra='letter-spacing="2"')
end(); add('</svg>')
svg='\n'.join(P)
svgpath=OUT/'逆鳞_登山关卡平面图_v03.svg'
svgpath.write_text(svg,encoding='utf-8')
ET.parse(svgpath)
runtime=Path(r'C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies')
render=OUT/'render_plan_v03.cjs'
render.write_text("const sharp=require("+json.dumps(str(runtime/'node/node_modules/sharp'))+");\nsharp("+json.dumps(str(svgpath),ensure_ascii=False)+").png().toFile("+json.dumps(str(OUT/'逆鳞_登山关卡平面图_v03.png'),ensure_ascii=False)+").then(()=>console.log('rendered'));\n",encoding='utf-8')
subprocess.run([str(runtime/'node/bin/node.exe'),str(render)],check=True)
im=Image.open(OUT/'逆鳞_登山关卡平面图_v03.png')
im.thumbnail((1800,1415)); im.save(OUT/'preview_v03.png')
print('SVG parsed; PNG rendered:', Image.open(OUT/'逆鳞_登山关卡平面图_v03.png').size)
