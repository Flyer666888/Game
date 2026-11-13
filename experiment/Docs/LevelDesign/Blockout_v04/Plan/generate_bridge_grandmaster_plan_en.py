"""Create a concise English edition from the same approved bridge encounter data."""
from pathlib import Path
import re

SOURCE=Path(r'D:\game design\experiment\Docs\LevelDesign\Blockout_v04\Plan\generate_bridge_grandmaster_plan.py')
prefix=SOURCE.read_text(encoding='utf-8').split("\nadd(f'<svg xmlns=")[0]
exec(compile(prefix,str(SOURCE),'exec'),globals())
W,H=3600,2700
parts=[]
PALE='#fffdf7'
master_names=['Sword Grandmaster','Talisman Grandmaster','Alchemy Grandmaster','Wind Grandmaster']
terrace_names=['Bridgehead','Lower Terrace','Middle Terrace','Upper Terrace']
seal_names=['Sword Seal','Talisman Seal','Alchemy Seal','Wind Seal']
for i,m in enumerate(masters):
    m.update(id=f'GM {i+1}',name=master_names[i],location=terrace_names[i],drop=seal_names[i])

def draw_base(view):
    """Reuse actual geometry while omitting duplicated node labels and annotations."""
    for row in terrain:
        footprint(row,view,'#d4dece','#b4c3af',1.4)
    for row in platforms:
        footprint(row,view,'url(#paving)','#80977e',2)
    for row in rests+bridgeheads:
        footprint(row,view,'#e5dec6','#8da084',1.5)
    for row in stairs:
        draw_stair(row,view)
    for row in sorted(footprints,key=lambda r:centre(r)[2] if len(centre(r))>2 else 0):
        kind=str(row.get('kind','roof')).lower();name=row.get('name','')
        if 'Furnace' in name:fill='#c4aa70'
        elif 'Seal' in name or 'wall' in kind:fill='#96a38f'
        else:fill='#55776b' if 'roof' in kind or 'pavilion' in kind else '#a1ad96'
        footprint(row,view,fill,'#6b8975',1.5)
    for row in stairs:
        ax,ay=view.point(row['a']);bx,by=view.point(row['b'])
        path(f'M{ax:.2f} {ay:.2f} L{bx:.2f} {by:.2f}',stroke=GOLD,sw=4,
             extra='stroke-dasharray="12 8" marker-end="url(#goldArrow)"')

def count_box(x,y,title,total,detail,target):
    leader((x+360,y+70),target)
    rect(x,y,360,144,PALE,'#c9b29d',1.5,12)
    text(x+20,y+35,title,25,INK,600)
    text(x+20,y+84,total,38,RED,700)
    text(x+20,y+121,detail,23,MUTED)

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('<metadata>'+html.escape(json.dumps({'language':'en','map':data['map'],'layout_sha256':hashlib.sha256(raw).hexdigest(),
    'source_annotation':'BridgeGrandmasterEncounterAnnotations.json','counts':[50,44,9],'total':103,
    'bridge_total':8,'grandmaster_positions_m':[m['position'] for m in masters]},ensure_ascii=True))+'</metadata>')
add('''<defs>
<pattern id="paving" width="34" height="34" patternUnits="userSpaceOnUse"><rect width="34" height="34" fill="#e1e2ca"/><path d="M34 0H0V34" fill="none" stroke="#cbd0b8" stroke-width="1"/></pattern>
<marker id="goldArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1L11 6L1 11Z" fill="#bb873e"/></marker>
</defs><g font-family="Arial, Segoe UI, sans-serif">''')
rect(0,0,W,H,'#f7f5eb')
rect(77,58,8,112,GOLD)
text(112,112,'NILIN / WINDBORNE BRIDGE',55,INK,700)
text(112,163,'FOUR GRANDMASTERS  /  ENCOUNTER PLAN',28,MUTED,500)
pill(3300,100,'103 ENEMIES',440,72,40)
text(3522,163,'LEVEL 1: 50     LEVEL 2: 44     LEVEL 3: 9',25,INK,600,'end')
path('M78 194 H3522',stroke='#bac6b2',sw=2)

# Overview: retain all count groups, but keep individual drops in the enlarged plan.
rect(76,230,1578,2010,'#edf1e7','#b3c1ac',1.5,18)
text(112,290,'LEVEL OVERVIEW',34,INK,700)
text(112,337,'Enemy totals along the ascent',26,MUTED)
bb=[bounds(row) for row in platforms+rests+bridgeheads+footprints+terrain]
bb+=[(n['ground'][0],n['ground'][0],n['ground'][1],n['ground'][1]) for n in nodes]
bb=union(bb);bb=(bb[0]-30,bb[1]+30,bb[2]-30,bb[3]+30)
overview=View(118,395,1488,1655,bb)
add('<clipPath id="overviewClip"><rect x="115" y="385" width="1495" height="1695"/></clipPath>')
add('<g clip-path="url(#overviewClip)">');draw_base(overview);crowd(overview);end()
count_box(124,1810,'A / Mountain Gate','8 enemies','2 outside + 6 inside',overview.point((0,0,0)))
count_box(124,1470,'B / Martial Court','42 enemies','36 court + 6 exit',overview.point((0,140,28)))
count_box(124,1080,'C / Alchemy Court','44 enemies','Waves: 8 / 10 / 12 / 14',overview.point((0,300,72)))
count_box(124,490,'D / Summit','1 boss','Sect Master / 3 phases',overview.point(data['boss']))
count_box(124,785,'Windborne Bridge','8 enemies','4 disciples + 4 masters',overview.point((-106.5,407.5,104)))
for m,by in zip(masters,(1240,1050,865,670)):
    x,y=overview.point(m['position'])
    rect(x-8*overview.s,y-7*overview.s,16*overview.s,14*overview.s,'#e8dced',ELITE,2.5,
         extra='fill-opacity=".85" stroke-dasharray="7 5"')
    circle(x,y,7,ELITE)
    leader((1247,by),(x,y),ELITE)
    pill(1420,by,m['id']+' / +'+str(m['position'][2])+' m',344,48,26,col=ELITE)
for n in nodes:
    if n['index'] in (2,4,8):
        x,y=overview.point(n['ground'])
        pill(x-65 if n['index']!=8 else x+70,y-25 if n['index']==8 else y,'REST',95,37,20,col=TEAL)
for p,s in [((0,-21,0),'START'),((-174,512.5,132),'+132 m')]:
    x,y=overview.point(p);text(x,y+72,s,25,INK,600,'middle')
bar=50*overview.s
path(f'M130 2110 h{bar:.2f}',stroke=INK,sw=6)
text(130+bar/2,2151,'50 m',24,INK,600,'middle')
text(1605,2190,'Elevations rise toward the summit.',25,MUTED,400,'end')

# Bridge detail: the four labels carry only name, place, drop and encounter order.
rect(1720,230,1804,2010,'#edf1e7','#b3c1ac',1.5,18)
text(1758,290,'WINDBORNE BRIDGE',34,INK,700)
text(1758,337,'4 disciples + 4 grandmasters / Fight in sequence',27,ELITE,600)
r=View(1760,390,1724,1655,(-203,6,285,550))
rect(1760,390,1724,1655,'#e7eddf','#c2cdb6',1,10)
add('<clipPath id="bridgeDetail"><rect x="1760" y="390" width="1724" height="1655" rx="10"/></clipPath>')
add('<g clip-path="url(#bridgeDetail)">');draw_base(r)
for i,m in enumerate(masters):
    x,y=r.point(m['position'])
    rect(x-8*r.s,y-7*r.s,16*r.s,14*r.s,'#e8d9ed',ELITE,3,
         extra='fill-opacity=".9" stroke-dasharray="9 6"')
    circle(x,y,25,ELITE);text(x,y+10,str(i+1),30,PALE,700,'middle')
pp=[r.point(p) for p in ((-34,310,72),(-36,307,72),(-42,302,72))]
path('M'+' L'.join(f'{x:.1f} {y:.1f}' for x,y in pp),stroke=ELITE,sw=4,extra='stroke-dasharray="6 5"')
end()

bridge_boxes=[(2620,1775,800),(2705,1460,715),(1810,1130,665),(1810,785,850)]
encounter_lines=['1 grandmaster','2 swordsmen, then the grandmaster','2 talisman disciples, then the grandmaster','1 grandmaster, then summit rest']
for i,(m,(bx,by,bw),encounter) in enumerate(zip(masters,bridge_boxes,encounter_lines)):
    target=r.point(m['position']);side=1 if bx>target[0] else -1
    leader((bx if side==1 else bx+bw,by+80),(target[0]+side*28,target[1]),ELITE)
    rect(bx,by,bw,174,PALE,'#bea8c5',1.5,12)
    text(bx+22,by+40,f'{i+1:02}  '+m['name'],33,ELITE,700)
    text(bx+22,by+80,m['location']+' / +'+str(m['position'][2])+' m',26,INK,500)
    text(bx+22,by+120,'Drop: '+m['drop'],27,ELITE,600)
    text(bx+22,by+154,encounter,23,MUTED)

bp=r.point(data['boss'])
pill(bp[0],bp[1]-25,'SECT MASTER / BOSS',530,60,30)
text(bp[0],bp[1]+36,'+132 m',26,INK,600,'middle')
rp=r.point(counts['summit_entry_rest_position_m'])
leader((3070,824),rp,TEAL)
pill(3205,850,'SUMMIT REST / 0 ENEMIES',524,52,26,col=TEAL)
gate_a,gate_b=r.point((-178,494,132)),r.point((-155,494,132))
path(f'M{gate_a[0]:.1f} {gate_a[1]:.1f} L{gate_b[0]:.1f} {gate_b[1]:.1f}',stroke=ELITE,sw=4,extra='stroke-dasharray="9 6"')
text(3150,720,'4 seals unlock the barrier',26,ELITE,600,'middle')
cp=r.point((0,289,72))
pill(cp[0]-40,cp[1]-15,'FROM ALCHEMY COURT',470,52,26,col=TEAL)
text(1760,2110,'Rest after each duel. Advance when ready.',28,INK,600)
text(1760,2160,'Talisman Disciple < Grandmaster < Sect Master',27,ELITE,500)
text(1760,2200,'Dashed arenas are proposed additions or expansions.',25,MUTED)

# Compact objective strip replaces the repeated cards and long implementation notes.
rect(76,2290,3448,272,'#eee8e4','#c8b9c8',1.5,18)
text(1800,2360,'4 SEALS  →  BARRIERBREAKER SEAL  →  SUMMIT BOSS',40,ELITE,700,'middle')
text(1800,2410,'Guaranteed drops / Auto-collect / Kept on retry',27,INK,500,'middle')
path('M112 2450 H3488',stroke='#d4c8d2',sw=1.5)
text(112,2504,'Arena: 16 × 14 m / Clear combat area: ≥12 × 12 m',27,MUTED)
text(3488,2504,'New bridgehead + 3 expanded terraces',27,MUTED,500,'end')
text(112,2540,'Enemy counts are cumulative; encounters are staged.',23,MUTED)

legend=[(112,GOLD,'Ascent'),(450,INK,'Buildings'),(860,RED,'Enemy count'),(1350,ELITE,'Grandmaster'),(1840,TEAL,'Rest')]
for x,col,label in legend:
    circle(x+8,2630,7,col);text(x+30,2639,label,25,MUTED)
text(3522,2640,'V09 / DESIGN PROPOSAL / NOT YET IMPLEMENTED',23,MUTED,500,'end')
end();add('</svg>')

stem='Nilin_Windborne_Bridge_Four_Grandmasters_EN_Simple_V09'
svgpath=OUT/(stem+'.svg')
svgpath.write_text('\n'.join(parts),encoding='utf-8')
tree=ET.parse(svgpath)
visible_text=' '.join(''.join(e.itertext()) for e in tree.iter('{http://www.w3.org/2000/svg}text'))
assert not re.search(r'[\u3400-\u9fff]',visible_text),'Untranslated visible label'
assert all(label in visible_text for label in master_names+seal_names)
assert all(n in visible_text for n in ['103 ENEMIES','LEVEL 1: 50','LEVEL 2: 44','LEVEL 3: 9'])
runtime=Path(r'C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies')
render='const sharp=require('+json.dumps(str(runtime/'node/node_modules/sharp'))+');const p='+json.dumps(str(svgpath))+';Promise.all([sharp(p,{density:96}).resize({width:4800}).png().toFile('+json.dumps(str(OUT/(stem+'.png')))+'),sharp(p).resize({width:1800}).png().toFile('+json.dumps(str(OUT/'preview_bridge_grandmasters_en.png'))+')]).then(()=>console.log("English plan rendered: 4800 x 3600"));'
renderer=OUT/'render_bridge_grandmaster_plan_en.cjs'
renderer.write_text(render,encoding='utf-8')
subprocess.run([str(runtime/'node/bin/node.exe'),str(renderer)],check=True)
print(str(OUT/(stem+'.png')))
