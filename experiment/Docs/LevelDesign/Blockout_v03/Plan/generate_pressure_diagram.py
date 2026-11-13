"""Render the editable B-court pressure specification as a native SVG diagram.

Run with Python. This reads the pure layout module and writes only beside itself.
The PNG companion can be refreshed with render_pressure_diagram.cjs and sharp.
"""
from pathlib import Path
from html import escape
import math

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
SOURCE = PROJECT / 'Scripts/Editor/NilinBlockout/pressure_layout_v03.py'
namespace = {'__name__': 'pressure_source', '__file__': str(SOURCE)}
exec(compile(SOURCE.read_text(encoding='utf-8'), str(SOURCE), 'exec'), namespace)
data = namespace['make_pressure']()
assert len(data['enemies']) == 36
assert sum(e['rank'] == 0 for e in data['enemies']) == 6

W, H = 1600, 1660
INK = '#27312e'
MUTED = '#65726b'
PALE = '#f2f4ef'
LINE = '#c6ccc4'
RED = '#a84d38'
TEAL = '#35766d'
HEIGHTS = {1: '#e9e1d4', 2: '#d4c3aa', 3: '#baa487'}
parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
 <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7Z" fill="{TEAL}"/></marker>
</defs>
<style>
text {{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;fill:{INK};font-size:23px}}
.small {{font-size:19px;fill:{MUTED}}}
.tiny {{font-size:17px;fill:{MUTED}}}
.label {{font-size:21px;font-weight:600}}
.head {{font-size:29px;font-weight:700}}
</style>
<rect width="1600" height="1660" fill="#fff"/>
''']

def text(x, y, message, cls='', anchor=None, fill=None):
    attrs = ''
    if cls: attrs += f' class="{cls}"'
    if anchor: attrs += f' text-anchor="{anchor}"'
    if fill: attrs += f' style="fill:{fill}"'
    parts.append(f'<text x="{x:.2f}" y="{y:.2f}"{attrs}>{escape(message)}</text>')

def line(x1, y1, x2, y2, color=LINE, width=1.5, dash=None, arrow=False):
    attrs = f' stroke-dasharray="{dash}"' if dash else ''
    if arrow: attrs += ' marker-end="url(#arrow)"'
    parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}"{attrs}/>')

def rect(x, y, w, h, fill, stroke=None, radius=0, width=1):
    attrs = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ''
    parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{radius}" fill="{fill}"{attrs}/>')

def circle(x, y, r, fill, stroke=None, width=1):
    attrs = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ''
    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}"{attrs}/>')

text(90, 83, '演武庭 · 层叠敌阵', 'head')
text(90, 123, '36 个静态轮廓 / 低处入场 / 三层抬升', 'small')
text(1510, 82, 'V08 · 布阵研究', 'small', 'end')
line(90, 153, 1510, 153)
text(90, 199, '01  俯视布阵', 'label')
text(1510, 199, '位置依照 pressure_layout_v03.py / 单位：米', 'tiny', 'end')

# World -X maps to the right side of the page, matching the UE overview.
S, CX, TOP = 12.0, 520.0, 240.0
def p(x, y): return CX - x*S, TOP + (166-y)*S
court = [[30,116],[-15,116],[-15,138],[-30,138],[-30,164],[30,164]]
points = ' '.join(f'{p(x,y)[0]:.2f},{p(x,y)[1]:.2f}' for x,y in court)
parts.append(f'<polygon points="{points}" fill="{PALE}" stroke="{LINE}" stroke-width="2"/>')

# The main route is 8m wide. The wider gap between staging banks is separate.
rx, ry = p(4,166)
rect(rx, ry, 8*S, (166-126)*S, '#dcebe6')
cx, cy = p(*data['combat_disk']['center'][:2])
circle(cx, cy, 14*S, 'none', TEAL, 2)
parts.append(f'<circle cx="{cx}" cy="{cy}" r="{14*S}" fill="none" stroke="{TEAL}" stroke-dasharray="5 7" stroke-width="1"/>')

# Back terraces and access stairs are drawn with exact source footprint bounds.
for stage in data['terraces']:
    x, y, _ = stage['center']; w, d = stage['size']
    xx, yy = p(x+w/2, y+d/2)
    rect(xx, yy, w*S, d*S, HEIGHTS[stage['rank']], '#ac9c85', 0, 1)
for stair in data['stairs']:
    xx, yy = p(stair['x']+stair['width']/2, stair['landing_end_y'])
    rect(xx, yy, stair['width']*S, (stair['landing_end_y']-stair['start_y'])*S, '#f8f6f0', '#ad9d86')
    for _, step_y, _ in stair['steps']:
        x1,y1=p(stair['x']-stair['width']/2,step_y-.16)
        x2,y2=p(stair['x']+stair['width']/2,step_y-.16)
        line(x1,y1,x2,y2,'#ad9d86',1)

for enemy in data['enemies']:
    x,y=p(*enemy['foot'][:2])
    circle(x,y,5.2,RED,'#fff',1)
    # A forward-facing tick gives the top-view markers a clear facing direction.
    line(x,y+5.2,x,y+9.2,RED,1.8)

# Dimensional guide and route direction.
route_x, route_y=p(0,141)
line(route_x,route_y,route_x,p(0,168)[1],TEAL,3,arrow=True)
text(CX, 222, '继续登山  +Y', 'small', 'middle', TEAL)
x1,yd=p(4,133);x2,_=p(-4,133)
line(x1,yd,x2,yd,TEAL,1.5)
line(x1,yd-5,x1,yd+5,TEAL,1.5);line(x2,yd-5,x2,yd+5,TEAL,1.5)
rect(CX-62,yd+8,124,29,'#fff',None,4)
text(CX, yd+29, '主通道 8m', 'tiny', 'middle', TEAL)

px,py=p(0,126)
circle(px,py,11,'#fff',TEAL,2.5)
parts.append(f'<path d="M{px-6} {py+3}L{px} {py-7}L{px+6} {py+3}Z" fill="{TEAL}"/>')
text(px,py+42,'玩家入场', 'small','middle',TEAL)
text(135, 879, '画面左侧 = +X', 'tiny')
text(880, 879, '画面右侧 = −X', 'tiny','end')
line(135,896,255,896,INK,3)
line(135,890,135,902,INK,2);line(255,890,255,902,INK,2)
text(195,920,'10m','tiny','middle')

# Restrained legend and counting information remain outside the geometry.
LX=1010
text(LX,288,'敌阵数量', 'label')
text(LX,335,'地面 6  +  高台 30  =  36', 'head')
text(LX,376,'两翼各 18 个静态轮廓', 'small')
for index,(rank,height) in enumerate(((3,4.8),(2,3.2),(1,1.6))):
    yy=432+index*65
    rect(LX,yy-23,44,30,HEIGHTS[rank],'#ac9c85')
    text(LX+65,yy,f'第 {rank} 层  +{height:.1f}m  /  10 人','small')
circle(LX+22,619,6,RED)
text(LX+65,625,'地面层  +0m  /  6 人','small')
circle(LX+22,688,15,'none',TEAL,2)
text(LX+65,696,'中央战斗区  R14m','small')
line(LX,735,1480,735)
text(LX,776,'前后排头肩错开，保留待命队列。','small')
text(LX,812,'两侧石阶连接高台；中央持续向上。','small')
text(LX,854,'人物图标为示意尺寸，落点使用实际坐标。','tiny')

line(90,953,1510,953)
text(90,1000,'02  纵向剖面投影', 'label')
text(1510,1000,'两翼压缩为一组层高示意；人数以俯视图为准', 'tiny','end')

BX, BASE, HS, DS=190.0,1456.0,60.0,24.0
def q(y,z): return BX+(y-126)*DS, BASE-z*HS

# Terrace profile, one side projected onto the direction of travel.
stages=sorted((t for t in data['terraces'] if t['side']=='L'),key=lambda t:t['rank'])
for t in stages:
    start=t['center'][1]-t['size'][1]/2
    x,y=q(start,t['height'])
    rect(x,y,t['size'][1]*DS,t['height']*HS,HEIGHTS[t['rank']],'#ac9c85')
line(110,BASE,1430,BASE,INK,2)

def silhouette(x,foot,color):
    # Matches the UE dummy's approximate body/head dimensions at this vertical scale.
    circle(x,foot-1.6*HS,.18*HS,color)
    rect(x-.23*HS,foot-1.425*HS,.46*HS,1.15*HS,color,None,10)
    parts.append(f'<ellipse cx="{x:.2f}" cy="{foot:.2f}" rx="18" ry="4" fill="{color}" opacity=".6"/>')

eye_x,eye_y=q(126,1.62)
representatives=[]
for rank in (1,2,3):
    same=sorted((e for e in data['enemies'] if e['rank']==rank and e['foot'][0]>0),key=lambda e:e['foot'][0])
    e=same[2]
    x,foot=q(e['foot'][1],e['foot'][2]-data['ground_z'])
    representatives.append((rank,x,foot,e['foot'][2]-data['ground_z']))
    line(eye_x,eye_y,x,foot-1.6*HS,'#9baaa1',1.4,'6 7')

silhouette(*q(126,0),TEAL)
circle(eye_x+8,eye_y,3.5,'#fff')
line(122,eye_y,eye_x-18,eye_y,TEAL,1.5)
text(112,eye_y-20,'眼高 +1.62m','small',None,TEAL)
text(eye_x,BASE+37,'玩家','small','middle',TEAL)

front=sorted((e for e in data['enemies'] if e['rank']==0 and e['foot'][0]>0),key=lambda e:e['foot'][0])[1]
gx,gf=q(front['foot'][1],0)
silhouette(gx,gf,RED)
text(gx,BASE+37,'地面队列','small','middle')

for rank,x,foot,h in representatives:
    silhouette(x,foot,RED)
    text(x,foot+31,f'+{h:.1f}m','label','middle')
    text(x,foot-122,f'第 {rank} 层','tiny','middle')

text(443,BASE-28,'中央战斗地坪保持同高','small','middle',TEAL)
line(360,BASE-9,560,BASE-9,TEAL,2,arrow=True)
text(1310,1121,'头肩逐层露出','label','middle')
text(1310,1160,'远排仍有敌人在待命','small','middle')
line(1190,1174,1115,1210,'#ac9c85',1.5)
text(1310,1302,'层高：+1.6 / +3.2 / +4.8m','small','middle')
text(1310,1340,'垂直方向放大以便观察','tiny','middle')

rect(90,1540,1420,70,'#f2f4ef',None,10)
text(120,1584,'视觉人数 ≠ 同时攻击人数','label')
text(625,1584,'当前仅为静态布阵；分批下台与战斗波次尚未实现。','small')
text(90,1641,'范围：仅 B 演武庭样段；C 炼丹庭、D 山顶 Boss 构图沿用 V07。','tiny')
parts.append('</svg>')
out=HERE/'敌阵高低差_平面与剖面.svg'
out.write_text('\n'.join(parts),encoding='utf-8')
print(out)

