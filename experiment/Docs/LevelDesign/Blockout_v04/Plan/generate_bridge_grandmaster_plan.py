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
counts={'level_1':{'gate_outside':2,'gate_inside':6,'martial_court':36,'exit_encounter':6,'grandmasters':0,'total':50},
        'level_2':{'establish':8,'interrupt':10,'siege':12,'unseal':14,'left_entry_total':22,'right_entry_total':22,'grandmasters':0,'total':44},
        'level_3':{'bridge_mobs':4,'bridge_lower_swordsmen':2,'bridge_upper_talisman':2,
                   'grandmasters':4,'bridge_total':8,'boss':1,'phases':3,'boss_arena_additional_mobs':0,'total':9},
        'rest_nodes':{'02':0,'04':0,'summit_entry_132m':0,'08':0},'overall_total':103,
        'status':'Proposed cumulative spawn budget; not implemented encounter configuration',
        'active_enemy_test_budget':12,'existing_static_martial_silhouettes':36}
assert sum(counts['level_1'][k] for k in ('gate_outside','gate_inside','martial_court','exit_encounter'))==50
assert sum(counts['level_2'][k] for k in ('establish','interrupt','siege','unseal'))==44
assert 50+44+9==103 and 98+4+1==103 and len(pressure['enemies'])==36
masters=[
    {'id':'宗1','name':'问剑宗师','location':'御风桥 · 起桥台 +72m','position':[-42,302,72],'drop':'剑印','order':'守丹结束出院后，进入起桥战台',
     'combat':'慢节奏剑招；格挡后反击','level':3},
    {'id':'宗2','name':'镇符宗师','location':'御风桥 · 下桥台 +88m','position':[-69,347.5,88],'drop':'符印','order':'此台 2 名持剑弟子清完后登场',
     'combat':'错拍符击；剑气抓反击窗口','level':3},
    {'id':'宗3','name':'丹火宗师','location':'御风桥 · 中桥台 +104m','position':[-106.5,407.5,104],'drop':'丹印','order':'此台 2 名御符弟子清完后登场',
     'combat':'丹火蓄力；剑气击阵眼打断','level':3},
    {'id':'宗4','name':'御风宗师','location':'御风桥 · 登顶台 +122m','position':[-151.5,459.5,122],'drop':'风印','order':'桥尾单独登场；获胜后前往峰顶',
     'combat':'短距换位后停顿；远距剑气反击','level':3}
]
counts['grandmasters']=masters
counts['quest_items']={'individual_drops':['剑印','符印','丹印','风印'],'combined_item':'破界印','fixed_drop':True,'auto_collect':True,'purpose':'解除Boss开战结界','preserved_on_checkpoint_retry':True,'consumed':False,'save_progress_on_grandmaster_defeat':True,'defeated_grandmasters_respawn':False,'duplicate_rewards':False}
counts['grandmaster_region']='All four grandmasters belong to Yufeng Bridge; none in A, B or C courtyards'
counts['planned_bridge_arenas']=[{'id':m['id'],'center_m':m['position'],'size_m':[16,14],'combat_clearance_m':[12,12],'type':'new' if i==0 else 'expand','status':'proposal; stairs and rails need reconnecting; not applied to V09'} for i,m in enumerate(masters)]
counts['rest_rule']='Each defeated grandmaster platform becomes a safe rest point. Final pre-boss rest is at summit entry +132m, outside the proposed encounter gate.'
counts['summit_entry_rest_position_m']=[-168,489,132]
assert all(m['level']==3 for m in masters) and counts['level_3']['bridge_total']==4+len(masters)

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
text(111,113,'逆鳞',60,INK,700);text(300,111,'御风桥四大宗师 · 分布与掉落修订',46,INK,700)
text(112,160,'沿用 V09 平面  /  朱红＝累计人数  /  紫色＝宗师与掉落  /  设计修订，尚未实装',27,MUTED)
pill(3310,100,'全程 103 名',370,72,42)
text(3522,163,'第一关 50  +  第二关 44  +  第三关 9',25,INK,600,'end')
path('M78 194 H3522',stroke='#acb79b',sw=2)

# Keep the original drawing's overall plan and four courtyard detail layout.
rect(76,230,1578,2010,'#dce7db','#a3b7a2',2,22)
rect(76,230,1578,2010,'url(#grid)',r=22)
text(112,287,'总平面  /  各地点累计人数',32,INK,700)
text(112,333,'−X 向图右 · +Y 上山；地面、阶梯沿用现有平面。',24,MUTED)
text(112,373,'四位宗师全部位于御风桥；山门、演武庭、守丹院内均无宗师。',24,MUTED)
bb=[bounds(r) for r in platforms+rests+bridgeheads+footprints+terrain]
bb += [(n['ground'][0],n['ground'][0],n['ground'][1],n['ground'][1]) for n in nodes]
bb=union(bb);bb=(bb[0]-30,bb[1]+30,bb[2]-30,bb[3]+30)
overview=View(118,395,1488,1655,bb)
add('<clipPath id="overviewClip"><rect x="115" y="385" width="1495" height="1695"/></clipPath>')
add('<g clip-path="url(#overviewClip)">');draw_world(overview);crowd(overview);end()
count_callout(124,1810,360,'第一关 · A 山门','8 名','门前 2 + 门内 6',overview.point((0,0,0)))
count_callout(124,1470,360,'第一关 · B 演武庭','42 名','演武 36 + 丹道口 6',overview.point((0,140,28)))
count_callout(124,1080,360,'第二关 · C 守丹台','44 名','8 → 10 → 12 → 14',overview.point((0,300,72)))
count_callout(124,490,360,'第三关 · D 山顶','1 名 Boss','宗主 1 名，连续 3 阶段',overview.point(data['boss']))
bridge_low=(-69,347.5,88);bridge_high=(-106.5,407.5,104)
leader((484,928),overview.point(bridge_low))
count_callout(124,785,360,'第三关前奏 · 御风桥','8 名','持剑 2 + 御符 2 + 宗师 4',overview.point(bridge_high))
for m,by in zip(masters,(1240,1050,865,670)):
    x,y=overview.point(m['position'])
    rect(x-8*overview.s,y-7*overview.s,16*overview.s,14*overview.s,'#ebe1ef',ELITE,3,extra='fill-opacity=".55" stroke-dasharray="7 5"')
    circle(x,y,8,ELITE)
    leader((1225,by),(x,y),ELITE)
    pill(1410,by,m['id']+' · '+m['drop']+' · +'+str(m['position'][2])+'m',370,48,25,col=ELITE)
for n in nodes:
    if n['index'] in (2,4):
        x,y=overview.point(n['ground']);pill(x-90,y,'0',65,42,26,col=TEAL)
    elif n['index']==8:
        x,y=overview.point(n['ground']);pill(x+64,y-42,'0',65,42,26,col=TEAL)
bar=50*overview.s
path(f'M130 2110 h{bar:.2f}',stroke=INK,sw=6)
text(130+bar/2,2151,'50m',24,INK,600,'middle')
text(112,2200,'图上节点编号沿用白模；敌人数量为新增设计标注。',24,MUTED)

# An enlarged bridge plan makes the corrected four-encounter placement explicit.
rect(1720,230,1804,2010,'#e9e6d0','#a9b79c',2,22)
text(1758,287,'御风桥放大平面 · 四位宗师全部在此',34,INK,700)
text(1758,333,'桥路合计 8 名＝弟子 4 + 宗师 4；沿上山顺序逐一挑战。',27,ELITE,600)
r=View(1760,390,1724,1655,(-203,6,285,550))
rect(1760,390,1724,1655,'#dce5d5','#b3bea4',1,12)
add('<clipPath id="bridgeDetail"><rect x="1760" y="390" width="1724" height="1655" rx="12"/></clipPath>')
add('<g clip-path="url(#bridgeDetail)">');draw_world(r,False)
for i,m in enumerate(masters):
    x,y=r.point(m['position'])
    rect(x-8*r.s,y-7*r.s,16*r.s,14*r.s,'#e8d9ed',ELITE,3.5,extra='fill-opacity=".85" stroke-dasharray="9 6"')
    circle(x,y,25,ELITE);text(x,y+10,str(i+1),30,'#fff6e9',700,'middle')
# Short proposed level connector from the outside of C to the new bridgehead arena.
pp=[r.point(p) for p in ((-34,310,72),(-36,307,72),(-42,302,72))]
path('M'+' L'.join(f'{x:.1f} {y:.1f}' for x,y in pp),stroke=ELITE,sw=4,extra='stroke-dasharray="6 5"')
end()

bridge_boxes=[(2620,1775,800),(2705,1460,715),(1810,1130,665),(1810,785,850)]
for m,(bx,by,bw),sub in zip(masters,bridge_boxes,(
    '院外新增战台；短平接驳连回桥口',
    '持剑弟子 2 → 镇符宗师 1',
    '御符弟子 2 → 丹火宗师 1',
    '御风宗师 1；获胜后登顶')):
    target=r.point(m['position'])
    anchor=(bx if bx>target[0] else bx+bw,by+86)
    leader(anchor,(target[0]+(28 if bx>target[0] else -28),target[1]),ELITE)
    rect(bx,by,bw,176,PALE,'#bca5c4',2,14)
    text(bx+22,by+43,m['id']+' '+m['name']+'  ·  '+m['drop'],31,ELITE,700)
    text(bx+22,by+85,m['location'],27,INK,600)
    text(bx+22,by+128,sub,26,MUTED)
    text(bx+22,by+159,'拟'+('新增' if m['id']=='宗1' else '扩建')+' 16×14m；净空 ≥12×12m',22,ELITE)

# Boss encounter starts beyond the proposed rest / entry boundary.
bp=r.point(data['boss']);pill(bp[0],bp[1]-25,'山顶宗主 ×1',340,56,31)
rp=r.point(counts['summit_entry_rest_position_m'])
leader((3070,824),rp,TEAL)
pill(3205,850,'峰顶入口休整 0 · +132m',524,52,26,col=TEAL)
gate_a,gate_b=r.point((-178,494,132)),r.point((-155,494,132))
path(f'M{gate_a[0]:.1f} {gate_a[1]:.1f} L{gate_b[0]:.1f} {gate_b[1]:.1f}',stroke=ELITE,sw=4,extra='stroke-dasharray="9 6"')
text(3150,720,'四印解除开战结界',26,ELITE,600,'middle')
cp=r.point((0,289,72));pill(cp[0]-40,cp[1]-15,'C 守丹院 · 宗师 0',440,52,28,col=TEAL)
text(1760,2110,'四战台自下而上：+72m → +88m → +104m → +122m。',28,INK,600)
text(1760,2155,'每场胜利后原地休整；玩家继续前进才触发下一场。',27,INK)
text(1760,2200,'紫虚线＝拟新增 / 扩建与接驳；台阶、护栏需重接，尚未改白模。',25,MUTED)

# Keep the encounter proposal and item loop directly on the editable plan.
rect(76,2280,3448,594,'#e9e1d0','#b8a6b3',2,22)
text(112,2340,'四大宗师全部驻守御风桥 · 四场独立精英战',33,INK,700)
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
for x,title,value,detail in ((112,'第一关 · 破山门','50 名','山门 8 + 演武 36 + 丹道口 6；宗师 0'),
                            (1250,'第二关 · 守丹台','44 名','守丹 8 + 10 + 12 + 14；宗师 0'),
                            (2388,'第三关 · 逆鳞劫','9 名','御风桥弟子 4 + 四大宗师 4 + 宗主 1')):
    rect(x,3004,1078,144,PALE,'#d2bda0',1.5,13)
    text(x+24,3047,title,29,INK,600);text(x+1025,3052,value,38,RED,700,'end')
    text(x+24,3109,detail,26,MUTED)
text(112,3196,'全程累计 103 名＝原有弟子 / 执事等 98 名 + 四大宗师 4 名 + 宗主 Boss 1 名。宗师战与杂兵波次错开，单独进行。',28,INK,600)
text(112,3246,'御风桥起桥台拟新增，其余三台拟扩建；各台 16×14m、战斗净空至少 12×12m，连接阶梯需同步调整。',27,ELITE,600)
text(112,3296,'同时活跃敌人先按 ≤12 名测试，攻击错峰；演武庭 36 名分 6 批投入，保留高台待命阵列的视觉压迫。',27,RED,600)
text(112,3346,'桥路节奏：问剑 → 持剑 2 / 镇符 → 御符 2 / 丹火 → 御风 → 峰顶入口休整 → Boss；宗师战后保存并休整。',26,INK)
text(112,3396,'依据：资料包 §11–14 + V09 LayoutSpec。逐点人数、宗师与掉落均为建议，尚未写入 UE 波次 / 道具系统。  2026-10-23',25,MUTED)
text(78,3500,'金线：登山路线   ·   深绿：建筑投影   ·   红点：演武待命阵位   ·   朱红：累计人数   ·   紫色：宗师 / 掉落 / 拟扩台   ·   青色 0：休整',24,MUTED)
text(3522,3500,'GRANDMASTER ENCOUNTER PLAN / V09',22,MUTED,500,'end')
end();add('</svg>')
stem='逆鳞_关卡平面_御风桥四大宗师修订_V09'
svgpath=OUT/(stem+'.svg');svgpath.write_text('\n'.join(parts),encoding='utf-8');ET.parse(svgpath)
(OUT/'BridgeGrandmasterEncounterAnnotations.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2),encoding='utf-8')
runtime=Path(r'C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies')
code='const sharp=require('+json.dumps(str(runtime/'node/node_modules/sharp'))+');const p='+json.dumps(str(svgpath),ensure_ascii=False)+';Promise.all([sharp(p).png().toFile('+json.dumps(str(OUT/(stem+'.png')),ensure_ascii=False)+'),sharp(p).resize({width:1800}).png().toFile('+json.dumps(str(OUT/'preview_bridge_grandmasters.png'))+')]).then(()=>console.log("Rendered plan"));'
(OUT/'render_bridge_grandmaster_plan.cjs').write_text(code,encoding='utf-8')
subprocess.run([str(runtime/'node/bin/node.exe'),str(OUT/'render_bridge_grandmaster_plan.cjs')],check=True)
print(str(OUT/(stem+'.png')))
