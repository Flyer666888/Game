"""Record delivery only after real scene, walk, capture and build checks pass."""
from pathlib import Path
import json,hashlib,datetime,math
ROOT=Path(r'D:\game design\experiment')
OUT=ROOT/'Docs/LevelDesign/Blockout_v05'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8-sig'))
check=read('CheckSceneReport.json');walk=read('RuntimeWalk.json');scene=read('SceneBuild.json')
spec=read('LayoutSpec.json');actual=read('Readback.json');capture=read('Screenshots/CaptureReport.json')
assert check['success'],check
assert scene['saved'] and scene['map']==spec['map']
assert actual['save_confirmed'] and actual['map']==spec['map']
def verify_nodes(node_report):
    nodes=node_report.get('nodes',[])
    assert sorted(n['node'] for n in nodes)==list(range(1,9)),'Eight actual node landings are required'
    assert all(n['grounded'] and abs(n['height_error_cm'])<=8 for n in nodes),'A node landing did not pass'
def report_digest(name):return hashlib.sha256((OUT/name).read_bytes()).hexdigest()
if walk['state']=='passed' and not walk['failures']:
    assert walk['map']==spec['map'] and walk['waypoints_reached']==walk['total_waypoints']
    verify_nodes(walk)
    walking={'state':'passed_single_run','unique_targets_covered':walk['waypoints_reached'],
             'original_waypoint_count':walk['total_waypoints'],'run_count':1,'single_run_full_pass':True,
             'runs':[{'report':'RuntimeWalk.json','sha256':report_digest('RuntimeWalk.json'),
                      'state':walk['state'],'covered_range':{'start_inclusive':0,'end_exclusive':walk['waypoints_reached']}}]}
else:
    # The original run must have the one specific, diagnosed summit obstruction;
    # arbitrary partial runs or unrelated failures cannot satisfy this guard.
    earlier_name='RuntimeWalk_before_summit_rail_fix.json'
    summit_name='RuntimeWalkSummit.json'
    earlier=read(earlier_name);summit=read(summit_name)
    assert earlier['map']==summit['map']==spec['map']
    assert earlier['state']=='failed' and earlier['total_waypoints']==533 and earlier['waypoints_reached']==513
    assert len(earlier['failures'])==1 and earlier['failures'][0]['error']=='Character movement stalled'
    assert earlier['failures'][0]['waypoint']==513,'Earlier failure differs from the repaired summit rail obstruction'
    assert len(earlier['waypoints_m'])==533
    assert math.dist(earlier['failures'][0]['target'],earlier['waypoints_m'][513])<=.001
    verify_nodes(earlier)
    assert summit['state']=='passed' and summit.get('success') is True and not summit['failures']
    assert summit['original_waypoint_count']==533 and summit['start_index']==480
    assert summit['total_waypoints']==summit['waypoints_reached']==summit['completed_target_count']==53
    assert summit['initial_position_original_index']==479 and summit['initial_teleport_count']==1
    assert summit['teleports_during_walk']==0,'Regression must use continuous CharacterMovement after initial placement'
    assert summit['section_start_smoke']['grounded'] and abs(summit['section_start_smoke']['height_error_cm'])<=8
    assert summit['original_waypoint_indices_reached']==list(range(480,533))
    assert summit['covered_range']=={'start_inclusive':480,'end_exclusive':533}
    assert len(summit['waypoints_m'])==53
    assert all(math.dist(a,b)<=.001 for a,b in zip(earlier['waypoints_m'][480:],summit['waypoints_m'])),'Regression targets differ from the full route'
    assert math.dist(earlier['waypoints_m'][479],summit['initial_ground_m'])<=.001
    first_coverage=set(range(513));second_coverage=set(summit['original_waypoint_indices_reached'])
    combined=first_coverage|second_coverage;overlap=first_coverage&second_coverage
    assert combined==set(range(533)),'The two measured runs leave untested route targets'
    walking={'state':'covered_across_two_runs','unique_targets_covered':len(combined),
             'original_waypoint_count':533,'run_count':2,'single_run_full_pass':False,
             'overlap_target_count':len(overlap),'overlap_range':{'start_inclusive':480,'end_exclusive':513},
             'runs':[{'report':earlier_name,'sha256':report_digest(earlier_name),'state':earlier['state'],
                      'covered_range':{'start_inclusive':0,'end_exclusive':513},'targets_reached':513,
                      'node_landings_passed':8,'original_failure':earlier['failures'][0]},
                     {'report':summit_name,'sha256':report_digest(summit_name),'state':summit['state'],
                      'covered_range':summit['covered_range'],'targets_reached':53,
                      'initial_teleport_count':1,'teleports_during_walk':0}],
             'repair':'Removed the bridgehead end rail that obstructed movement from the final stair into the enlarged boss floor.',
             'limitations':'All 533 original targets have actual CharacterMovement coverage across two runs with 33 overlapping targets. The first 513 were reached before the local summit rail repair; the final 53 were tested afterward. This is not a single uninterrupted full-route pass after the repair. Final saved geometry checks are separate.'}
assert capture['error'] is None and len(capture['captures'])>=6
assert capture['map']==spec['map'],'Screenshots were captured from a different map'
local_timezone=datetime.datetime.now().astimezone().tzinfo
def timestamp(value):
    parsed=datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=local_timezone)
    return parsed.astimezone(datetime.timezone.utc)
scene_saved_at=timestamp(scene['time'])
assert timestamp(check['checked_at'])>scene_saved_at,'Scene checks predate the final saved build'
assert timestamp(capture['captured_at'])>scene_saved_at,'Screenshots predate the final saved build'
assert len({item['file'] for item in capture['captures']})>=6,'Six distinct final screenshots are required'
for item in capture['captures']:
    screenshot=Path(item['file'])
    assert screenshot.is_file(),'Missing screenshot: '+str(screenshot)
    assert screenshot.stat().st_size==item['bytes'],'Screenshot changed after capture verification: '+str(screenshot)
assert 'Result: Succeeded' in (OUT/'Build.log').read_text(encoding='utf-8-sig')
rock_review=None
if scene.get('rock_refinement'):
    change=read('RockRefinement/ChangeReport.json')
    rock_walk=read('RockRefinement/RuntimeWalkRocks.json')
    assert spec['ranged_encounters'].get('visual_theme')=='natural_rock_outcrops'
    assert change['outside_geometry_unchanged'] and change['access_routes_unchanged']
    assert change['enemy_positions_and_shot_lanes_unchanged']
    assert timestamp(change['saved_at'])==scene_saved_at
    assert rock_walk['state']=='passed' and rock_walk['success'] and not rock_walk['failures']
    assert rock_walk['map']==spec['map'] and rock_walk['completed_stations']==3
    assert rock_walk['initial_teleport_count']==3 and rock_walk['teleports_during_walk']==0
    assert rock_walk['waypoints_reached']==rock_walk['total_waypoints']
    assert {s['id'] for s in rock_walk['stations']}=={s['id'] for s in spec['ranged_encounters']['stations']}
    for station in rock_walk['stations']:
        assert station['state']=='passed' and station['returned_to_rest']
        assert station['waypoints_reached']==station['total_waypoints']
        assert len(station['enemy_feet_reached'])==2
    rock_review={'theme':'natural_rock_outcrops','outside_geometry_unchanged':True,
        'report':'RockRefinement/ChangeReport.json','walk_report':'RockRefinement/RuntimeWalkRocks.json',
        'walk_report_sha256':report_digest('RockRefinement/RuntimeWalkRocks.json'),
        'local_walk_targets_reached':rock_walk['waypoints_reached'],'station_circuits_passed':3,
        'scope':'Only the three ranged sites changed. Each replaced outcrop was walked from the main route to both enemy positions and back after the change. Prior unchanged-route evidence remains separate.'}
    walking['subsequent_local_geometry_regression']=rock_review
baseline=read('SourceBaseline.json')
source=Path(baseline['source']);original_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==baseline['sha256']
assert original_unchanged,'V09 source changed unexpectedly'
report={'version':'V10','map':spec['map'],'completed_at':datetime.datetime.now().astimezone().isoformat(),
    'source_v09_sha256_unchanged':original_unchanged,'map_sha256':hashlib.sha256((ROOT/'Content/ReversedScale/Maps/L_NilinBlockoutV10.umap').read_bytes()).hexdigest(),
    'changes':{'ranged_stations':3,'ranged_silhouettes':6,'ranged_gallery_size_m':[12,10],
        'grandmasters':4,'grandmaster_terrace_m':[24,22],'grandmaster_clear_core_m':[18,16],
        'bridge_length_m':spec['upper_ascent_change']['centerline_length_m'],
        'previous_bridge_length_m':spec['upper_ascent_change']['original_centerline_length_m'],
        'boss_floor_diameter_m':92,'boss_clear_diameter_m':60,'boss_placeholder_height_m':4.8},
    'actor_count':actual['actor_count'],'checks':{'scene':check['state'],'floor_width_samples':read('EdgeAudit.json')['samples'],
        'new_encounter_marker_and_shooting_lane_checks':read('PressureAudit.json')['new_encounters']['success'],
        'major_nodes_seated_standing_target_visibility':read('Validation.json')['checks']['node_sightlines_pass'],
        'actual_character_walk_points':walking['unique_targets_covered'],'actual_character_walk_state':walking['state'],
        'build':'Succeeded'},'walking_coverage':walking,
    'evidence_freshness':{'scene_saved_at':scene['time'],'checks_started_at':check['checked_at'],
        'screenshots_captured_at':capture['captured_at'],'checks_and_screenshots_after_final_scene_save':True,
        'screenshot_files_exist_and_match_recorded_bytes':True},'screenshots':capture['captures'],
    'scope':'Desktop level-layout whitebox. New ranged enemies, four masters and boss are static, non-damaging silhouettes. No AI, reward drops or barrier progression is claimed. No VR performance or comfort acceptance.'}
if rock_review:
    report['rock_refinement']=rock_review
    report['changes']['ranged_outcrop_footprint_m']=report['changes'].pop('ranged_gallery_size_m')
(OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'state':'complete','version':'V10','walk_points':walking['unique_targets_covered'],'walk_coverage':walking['state'],'walk_runs':walking['run_count'],'source_preserved':original_unchanged},ensure_ascii=False))
