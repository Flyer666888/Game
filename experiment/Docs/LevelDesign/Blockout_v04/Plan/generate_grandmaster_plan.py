"""Annotate the existing editable whitebox plan; no game assets are modified."""
from pathlib import Path
import sys,json,html,math,hashlib,subprocess,xml.etree.ElementTree as ET
ROOT=Path(r'D:\game design\experiment')
OUT=ROOT/'Docs/LevelDesign/Blockout_v04/Plan'
OUT.mkdir(parents=True,exist_ok=True)
SPEC=OUT.parent/'LayoutSpec.json'
BASE=ROOT/'Docs/LevelDesign/Blockout_v02/Plan/generate_plan.py'
# Reuse the same geometry projection and drawing helpers as the supplied plan.
sys.argv=[str(BASE),'--spec',str(SPEC),'--output',str(OUT)]
source=BASE.read_text(encoding='utf-8').split("add(f'<svg xmlns=")[0]
exec(compile(source,str(BASE),'exec'),globals())
W,H=3600,3560
RED='#ad4439'; PALE='#fff6e9'; DARK='#87352e'
ELITE='#75517f'
parts=[]
pressure=data['pressure']
counts={'level_1':{'gate_outside':2,'gate_inside':6,'martial_court':36,'exit_encounter':6,'grandmasters':2,'total':52},
        'level_2':{'establish':8,'interrupt':10,'siege':12,'unseal':14,'left_entry_total':22,'right_entry_total':22,'grandmasters':1,'total':45},
        'level_3':{'bridge_mobs':4,'bridge_lower_swordsmen':2,'bridge_upper_talisman':2,
                   'grandmasters':1,'boss':1,'phases':3,'boss_arena_additional_mobs':0,'total':6},
        'rest_nodes':{'02':0,'04':0,'upper_landing_122m':0,'08':0},'overall_total':103,
        'status':'Proposed cumulative spawn budget; not implemented encounter configuration',
        'active_enemy_test_budget':12,'existing_static_martial_silhouettes':36}
assert sum(counts['level_1'][k] for k in ('gate_outside','gate_inside','martial_court','exit_encounter'))==50
assert sum(counts['level_2'][k] for k in ('establish','interrupt','siege','unseal'))==44
assert 52+45+6==103 and 98+4+1==103 and len(pressure['enemies'])==36
masters=[
    {'id':'宗1','name':'问剑宗师','location':'A 山门内 · +0m','position':[0,8,0],'drop':'剑印','order':'门内 6 名弟子清完后，单独登场',
     'combat':'慢节奏剑招；格挡后反击','level':1},
    {'id':'宗2','name':'镇符宗师','location':'B 演武庭 · +28m','position':[0,144,28],'drop':'符印','order':'36 名敌阵结束后，丹道口遭遇前',
     'combat':'错拍符击；剑气抓反击窗口','level':1},
    {'id':'宗3','name':'丹火宗师','location':'C 守丹台 · +72m','position':[0,303,72],'drop':'丹印','order':'四阶段结束、挚友获救后单独登场',
     'combat':'丹火蓄力；剑气击阵眼打断','level':2},
    {'id':'宗4','name':'御风宗师','location':'御风桥望峰台 · +104m','position':[-106.5,407.5,104],'drop':'风印','order':'2 名御符弟子清完后，单独登场',
     'combat':'短距换位后停顿；远距剑气反击','level':3}
]
counts['grandmasters']=masters
counts['quest_items']={'individual_drops':['剑印','符印','丹印','风印'],'combined_item':'破界印','fixed_drop':True,'auto_collect':True,'purpose':'解除Boss开战结界','preserved_on_checkpoint_retry':True,'consumed':False,'save_progress_on_grandmaster_defeat':True,'defeated_grandmasters_respawn':False,'duplicate_rewards':False}
counts['alchemy_grandmaster_rule']='Only starts after friend rescue event completes; cannot attack friend or array and cannot reset rescue success'
counts['planned_bridge_arena']={'center_m':[-106.5,407.5,104],'size_m':[16,14],'combat_clearance_m':[12,12],'status':'proposed expansion; not applied to V09 geometry'}

def pill(x,y,label,w=190,h=50,size=29,col=RED):
    rect(x-w/2,y-h/2,w,h,PALE,col,2.5,12)
    text(x,y+size*.35,label,size,col,700,'middle')
def leader(a,b,col=RED):
    path(f'M{a[0]:.1f} {a[1]:.1f} L{b[0]:.1f} {b[1]:.1f}',stroke=col,sw=2.4)
    circle(*b,5,col)
def count_callout(x,y,w,title,main,detail,target):
    leader((x+w,y+68),target)
    rect(x,y,w,142,PALE,'#c6977c',2,14)
    text(x+20,y+32,title,25,INK,600)
    text(x+20,y+80,main,39,RED,700)
    text(x+20,y+116,detail,23,MUTED)
def crowd(view):
    for t in pressure['terraces']:
        footprint(t,view,'#bcbca0','#8a9277',1.8)
    for e in pressure['enemies']:
        x,y=view.point(e['foot']);circle(x,y,5 if view.s>5 else 2.4,RED)

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('<metadata>'+html.escape(json.dumps({'map':data['map'],'layout_sha256':hashlib.sha256(raw).hexdigest(),'count_design':counts},ensure_ascii=False))+'</metadata>')
add('''<defs>
<pattern id="paving" width="34" height="34" patternUnits="userSpaceOnUse"><rect width="34" height="34" fill="#d8d8ba"/><path d="M34 0H0V34" fill="none" stroke="#b7c0a4" stroke-width="1"/></pattern>
<pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" fill="none" stroke="#a6bbab" stroke-width="1" opacity=".4"/></pattern>
<marker id="goldArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#bb873e"/></marker>
<marker id="redArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#ad4439"/></marker>
<marker id="tealArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#368e81"/></marker>
</defs><g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">''')
rect(0,0,W,H,'#f1ecd9');rect(77,58,8,112,GOLD)
text(111,113,'逆鳞',60,INK,700);text(300,111,'四大宗师 · 敌人分布与破界道具',46,INK,700)
text(112,160,'沿用 V09 平面  /  朱红＝累计人数  /  紫色＝宗师与掉落  /  设计修订，尚未实装',27,MUTED)
pill(3310,100,'全程 103 名',370,72,42)
text(3522,163,'第一关 52  +  第二关 45  +  第三关 6',25,INK,600,'end')
path('M78 194 H3522',stroke='#acb79b',sw=2)

# Keep the original drawing's overall plan and four courtyard detail layout.
rect(76,230,1578,2010,'#dce7db','#a3b7a2',2,22)
rect(76,230,1578,2010,'url(#grid)',r=22)
text(112,287,'总平面  /  各地点累计人数',32,INK,700)
text(112,333,'−X 向图右 · +Y 上山；地面、阶梯沿用现有平面。',24,MUTED)
text(112,373,'四位宗师沿主线依次出现；02 / 04、峰前 +122m 和 08 保留休整。',24,MUTED)
bb=[bounds(r) for r in platforms+rests+bridgeheads+footprints+terrain]
bb += [(n['ground'][0],n['ground'][0],n['ground'][1],n['ground'][1]) for n in nodes]
bb=union(bb);bb=(bb[0]-30,bb[1]+30,bb[2]-30,bb[3]+30)
overview=View(118,395,1488,1655,bb)
add('<clipPath id="overviewClip"><rect x="115" y="385" width="1495" height="1695"/></clipPath>')
add('<g clip-path="url(#overviewClip)">');draw_world(overview);crowd(overview);end()
count_callout(124,1810,360,'第一关 · A 山门','9 名','门前 2 + 门内 6 + 宗师 1',overview.point((0,0,0)))
count_callout(124,1470,360,'第一关 · B 演武庭','43 名','演武 36 + 宗师 1 + 丹口 6',overview.point((0,140,28)))
count_callout(124,1080,360,'第二关 · C 守丹台','45 名','守点 44 + 宗师 1',overview.point((0,300,72)))
count_callout(124,490,360,'第三关 · D 山顶','1 名 Boss','宗主 1 名，连续 3 阶段',overview.point(data['boss']))
bridge_low=(-69,347.5,88);bridge_high=(-106.5,407.5,104)
leader((484,928),overview.point(bridge_low))
count_callout(124,785,360,'第三关前奏 · 御风桥','5 名','下层 2 + 上层 2 + 宗师 1',overview.point(bridge_high))
for p,label,dy in ((bridge_low,'持剑 ×2 · +88m',48),(bridge_high,'御符 ×2 · +104m',-59)):
    x,y=overview.point(p)
    leader((x+70,y+dy),(x,y))
    pill(x+188,y+dy,label,282,48,26)
sx,sy=overview.point((-151.5,459.5,122))
leader((sx+58,sy+15),(sx,sy));pill(sx+202,sy+15,'峰前休整 0 · +122m',300,44,24,col=TEAL)
for m,dx,dy in zip(masters,(215,235,245,345),(-26,-44,55,86)):
    x,y=overview.point(m['position'])
    leader((x+dx-135,y+dy),(x,y),ELITE)
    pill(x+dx,y+dy,m['id']+' · '+m['drop']+(' · 拟扩台' if m['id']=='宗4' else ''),332 if m['id']=='宗4' else 240,48,26,col=ELITE)
ex,ey=overview.point(bridge_high)
rect(ex-8*overview.s,ey-7*overview.s,16*overview.s,14*overview.s,'none',ELITE,3,extra='stroke-dasharray="7 5"')
for n in nodes:
    if n['index'] in (2,4):
        x,y=overview.point(n['ground']);pill(x-90,y,'0',65,42,26,col=TEAL)
    elif n['index']==8:
        x,y=overview.point(n['ground']);pill(x+64,y-42,'0',65,42,26,col=TEAL)
bar=50*overview.s
path(f'M130 2110 h{bar:.2f}',stroke=INK,sw=6)
text(130+bar/2,2151,'50m',24,INK,600,'middle')
text(112,2200,'图上节点编号沿用白模；敌人数量为新增设计标注。',24,MUTED)

cards={'A':(1720,230),'B':(2658,230),'C':(1720,1250),'D':(2658,1250)}
titles={'A':'山门 · 第一关前段','B':'演武庭 · 第一关后段','C':'守丹台 · 第二关','D':'峰顶封山台 · 第三关'}
totals={'A':'9 名','B':'43 名','C':'45 名','D':'1 Boss'}
for key,(cx,cy) in cards.items():
    rect(cx,cy,866,970,'#e9e6d0','#a9b79c',2,22)
    circle(cx+45,cy+51,24,INK);text(cx+45,cy+59,key,24,'#eee1b7',700,'middle')
    text(cx+87,cy+60,titles[key],32,INK,700)
    pill(cx+754,cy+52,totals[key],164,56,33)
    row=court_meta[key];p=centre(row)
    text(cx+40,cy+105,f'地面 +{fmt(p[2])}m  /  '+('宗主数量据资料包，其余杂兵为 0 名建议' if key=='D' else '累计出现建议；分批投入战斗'),24,MUTED)
    clip='detail'+key
    add(f'<clipPath id="{clip}"><rect x="{cx+30}" y="{cy+145}" width="806" height="640" rx="8"/></clipPath>')
    rect(cx+30,cy+145,806,640,'#dce5d5','#b3bea4',1,8)
    r=View(cx+30,cy+145,806,640,(p[0]-40,p[0]+40,p[1]-35,p[1]+35),scale=9.1)
    add(f'<g clip-path="url(#{clip})">');draw_world(r,True,key)
    if key=='A':
        pill(*r.point((0,-14,0)),'门前 2',174,50,29)
        pill(*r.point((0,20,0)),'门内 6',174,50,29)
        pill(*r.point(masters[0]['position']),'宗1 问剑 · 剑印',280,48,27,col=ELITE)
    elif key=='B':
        crowd(r)
        pill(*r.point((0,136,28)),'演武 36',180,50,29)
        pill(*r.point((0,151,28)),'丹道口 6',180,50,29)
        pill(*r.point(masters[1]['position']),'宗2 镇符 · 符印',280,44,27,col=ELITE)
        for x in (-12.5,12.5):
            pill(*r.point((x,167,32.8)),'待命 15',128,34,21)
    elif key=='C':
        pill(*r.point((0,291,72)),'守点累计 44',240,54,30)
        pill(*r.point(masters[2]['position']),'宗3 丹火 · 丹印',280,44,27,col=ELITE)
        for x,label in ((23,'左入口 22'),(-23,'右入口 22')):
            px,py=r.point((x,296,72));pill(px,py,label,186,50,27)
            leader((px,py+25),r.point((x*.65,288,72)))
    else:
        pill(*r.point((-174,522.5,132)),'宗主 × 1',214,56,32)
        x,y=r.point((-174,544.5,132));pill(x,y,'归途 0',164,44,25,col=TEAL)
    end()
    notes={
      'A':['门前 2 持剑；门内 4 持剑 + 2 御符，共 8 名。','清完门内弟子 → 问剑宗师 1 名 → 必掉剑印。','这是入门精英战；招式较少，保留明显反击窗口。'],
      'B':['敌阵 36：地面 6 + 三层高台各 10；6 批 × 6。','清完敌阵 → 镇符宗师 1 名 → 必掉符印。','再遇丹道口 4 持剑 + 2 执事；04 落台休整 0 名。'],
      'C':['四阶段：8 → 10 → 12 → 14，共 44；两侧各 22。','挚友获救后 → 丹火宗师 1 名 → 必掉丹印。','不攻击挚友 / 法阵；不重置已完成的解救进度。'],
      'D':['宗主 1 名 / 3 阶段；Boss 场内杂兵为 0。','四印自动合成破界印，解除此处开战结界。','峰前 +122m 休整；Boss 重试保留四印，不再收集。']}
    for i,s in enumerate(notes[key]):text(cx+32,cy+831+i*44,s,24,INK if i<2 else MUTED)

# Keep the encounter proposal and item loop directly on the editable plan.
rect(76,2280,3448,594,'#e9e1d0','#b8a6b3',2,22)
text(112,2340,'四大宗师 · 四场独立精英战',33,INK,700)
text(3488,2340,'战力层级：持符 / 御符弟子 ＜ 四大宗师 ＜ 宗主 Boss',29,ELITE,600,'end')
for i,m in enumerate(masters):
    x=112+i*853
    rect(x,2378,816,308,PALE,'#c7b4c7',1.5,14)
    text(x+24,2428,m['id']+'  '+m['name'],32,ELITE,700)
    text(x+24,2470,m['location'],25,INK,600)
    text(x+24,2520,m['order'],25,MUTED)
    text(x+24,2565,m['combat'],25,INK)
    pill(x+408,2631,'必掉 · '+m['drop'],730,56,30,col=ELITE)
text(1800,2744,'剑印  +  符印  +  丹印  +  风印   →   自动合成「破界印」   →   解除山顶 Boss 开战结界',33,ELITE,700,'middle')
text(1800,2801,'自动拾取并立即保存宗师完成状态；重试保留四印，已败宗师不再生成、奖励不重复；开战不消耗。',27,INK,500,'middle')
text(1800,2845,'用于解锁开战；开战后沿用剑气、近战与格挡循环。宗师名号、招式与四印名称均为本轮设计提案。',24,MUTED,400,'middle')

rect(76,2914,3448,532,'#e7e3c9','#aab69a',2,22)
text(112,2972,'人数合计与落地约束',33,INK,700)
for x,title,value,detail in ((112,'第一关 · 破山门','52 名','山门 9 + 演武庭及丹道口 43；含宗师 2'),
                            (1250,'第二关 · 守丹台','45 名','守丹 8 + 10 + 12 + 14，再遇宗师 1'),
                            (2388,'第三关 · 逆鳞劫','6 名','桥路弟子 4 + 御风宗师 1 + 宗主 1')):
    rect(x,3004,1078,144,PALE,'#d2bda0',1.5,13)
    text(x+24,3047,title,29,INK,600);text(x+1025,3052,value,38,RED,700,'end')
    text(x+24,3109,detail,26,MUTED)
text(112,3196,'全程累计 103 名＝原有弟子 / 执事等 98 名 + 四大宗师 4 名 + 宗主 Boss 1 名。宗师战与杂兵波次错开，单独进行。',28,INK,600)
text(112,3246,'御风桥 +104m：紫色虚线为拟扩建 16×14m 战台，战斗净空至少 12×12m；现有落台偏小，白模尚未修改。',27,ELITE,600)
text(112,3296,'同时活跃敌人先按 ≤12 名测试，攻击错峰；演武庭 36 名分 6 批投入，保留高台待命阵列的视觉压迫。',27,RED,600)
text(112,3346,'桥路：+88m 持剑 2 → +104m 御符 2（接近至 35–40m 后施法）→ 御风宗师 → +122m 休整 → 山顶 Boss。',26,INK)
text(112,3396,'依据：资料包 §11–14 + V09 LayoutSpec。逐点人数、宗师与掉落均为建议，尚未写入 UE 波次 / 道具系统。  2026-10-23',25,MUTED)
text(78,3500,'金线：登山路线   ·   深绿：建筑投影   ·   红点：演武待命阵位   ·   朱红：累计人数   ·   紫色：宗师 / 掉落 / 拟扩台   ·   青色 0：休整',24,MUTED)
text(3522,3500,'GRANDMASTER ENCOUNTER PLAN / V09',22,MUTED,500,'end')
end();add('</svg>')
stem='逆鳞_关卡平面_四大宗师与掉落_V09'
svgpath=OUT/(stem+'.svg');svgpath.write_text('\n'.join(parts),encoding='utf-8');ET.parse(svgpath)
(OUT/'GrandmasterEncounterAnnotations.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2),encoding='utf-8')
runtime=Path(r'C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies')
code='const sharp=require('+json.dumps(str(runtime/'node/node_modules/sharp'))+');const p='+json.dumps(str(svgpath),ensure_ascii=False)+';Promise.all([sharp(p).png().toFile('+json.dumps(str(OUT/(stem+'.png')),ensure_ascii=False)+'),sharp(p).resize({width:1800}).png().toFile('+json.dumps(str(OUT/'preview_grandmasters.png'))+')]).then(()=>console.log("Rendered plan"));'
(OUT/'render_grandmaster_plan.cjs').write_text(code,encoding='utf-8')
subprocess.run([str(runtime/'node/bin/node.exe'),str(OUT/'render_grandmaster_plan.cjs')],check=True)
print(str(OUT/(stem+'.png')))
