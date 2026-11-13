"""Record the applied fit and protection checks after actual saved-map validation."""
import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104';A=unreal.EditorAssetLibrary
def read(name):return json.loads((O/name).read_text(encoding='utf-8-sig'))
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
applied=read('Applied.json');candidate=applied['candidate'];prepared=read('Prepared_'+candidate['id']+'.json')
live=read('LiveD.json');capture=read('AfterCapture.json');tests=read('FinalAutomation/index.json')
assert live['state']=='passed' and all(live['checks'].values()),live['checks']
assert capture['state']=='passed' and all(capture['checks'].values())
assert tests['failed']==0 and tests['notRun']==0 and tests['inProcess']==0
protected=read('PoseSamples.json')['protected_sha256']
old=json.loads((P/'Docs/Gameplay/PackDIntegration1104/GameplayDPrepared.json').read_text())
protected.update(old['protected_sha256'])
sword=read('SwordBaseline.json');protected[sword['mesh']]=sword['sha256']
for path,sha in protected.items():
    file=P/'Content'/(path.split('.')[0].removeprefix('/Game/')+'.uasset')
    assert hashlib.sha256(file.read_bytes()).hexdigest()==sha,path
properties={'attack':'attack_animation','idle':'idle_animation','walk':'walk_animation','hit':'hit_reaction_animation','death':'death_animation','cast':'cast_animation'}
for row in applied['enemies']:
    obj=unreal.get_default_object(A.load_blueprint_class(row['asset']))
    for key,prop in properties.items():assert obj.get_editor_property(prop).get_path_name()==prepared['clips'][key]['asset']
    assert obj.sword.static_mesh.get_path_name()==row['sword']
    assert obj.attack_root_motion_curve.get_path_name()==row['root_curve']
selection_path=P/'Docs/Gameplay/PackDIntegration1104/Selection.json'
selection=json.loads(selection_path.read_text(encoding='utf-8-sig'))
selection['current_enemy'].update({'gameplay_asset':prepared['clips']['attack']['asset'],
    'grip':'Forward grip fitted to the actual native hand; fixed right-finger pose shared by all six equipped clips.',
    'grip_revision':str(O/'Delivery.json'),'enemy_sword':applied['enemies'][0]['sword']})
selection_path.write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
report={'state':'verified','selected_motion':'D','future_motion':'C remains unmodified and reserved for a reverse-grip enemy',
    'candidate':candidate,'enemies':applied['enemies'],'live_checks':live['checks'],
    'combat':live.get('root_motion_summary'),'captures':capture['frames'],
    'regression':{k:tests[k] for k in ['succeeded','succeededWithWarnings','failed','notRun','inProcess']},
    'protected_sha256':protected,'body_wrist_and_ground_motion_unchanged':True,
    'geometry_note':'Visible palm/knuckle penetration removed. Conservative offline surface test retains up to 1.87 mm of local contact overlap; this is not a claim of exact zero intersection.',
    'scope':'Actual saved-map AI, animation transitions and physical blade hits; isolated test profile, no human/HMD playtest.'}
(O/'Delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
