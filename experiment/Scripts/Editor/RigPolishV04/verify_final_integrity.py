"""Compare saved scope and source hashes after the v04 asset assignment."""
import copy,hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parents[3];O=P/'Docs/Gameplay/RigPolish_v04'
def read(name):return json.loads((O/name).read_text(encoding='utf-8-sig'))
before={r['key']:r for r in read('BeforeAssetAudit.json')['enemies']}
after={r['key']:r for r in read('AssetAudit.json')['enemies']}
melee={'sword','GM01','GM04','boss'};rows=[]
for key in before:
    a,b=copy.deepcopy(before[key]),copy.deepcopy(after[key])
    # UE's struct repr includes a process-local wrapper address; compare the
    # complete type/value text while excluding that transient memory address.
    for row in (a,b):
        row['mesh_relative']={p:re.sub(r'\(0x[0-9a-fA-F]+\)','(transient)',v)
            for p,v in row['mesh_relative'].items()}
    if key in melee:
        assert b['mesh'].split('.')[-1]=='SK_WuxiaMale_Hands_v04',key
        assert b['animations']['attack_animation'].split('.')[-1]=='Wuxia_Attack_Sword_Natural_v04',key
        del a['mesh'],b['mesh']
        del a['animations']['attack_animation'],b['animations']['attack_animation']
    assert a==b,'Unexpected saved enemy property change: '+key
    rows.append({'enemy':key,'expected_scope_only':True})
protected=[]
for item in read('BeforeIntegrity.json'):
    actual=hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
    assert actual.lower()==item['sha256'].lower(),item['path']
    protected.append({'path':item['path'],'unchanged_sha256':actual})
for name in ('HandsImport.json','AttackAssignments.json','NaturalAttackValidation.json','HandDetailPreview.json',
             'GripPalmPreview.json','NaturalAttackComparison.json','AfterMotion.json'):
    report=read(name)
    assert report['state']=='passed' and not report.get('failures'),name
result={'state':'passed','enemy_scope':rows,'protected_files':protected,
    'scope':'Four sword archetypes: right-hand mesh, attack and grip attachment; four casters, death, root/feet, maps and engine configuration preserved.'}
(O/'FinalIntegrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'state':'passed','enemies':len(rows),'protected_files':len(protected)}))
