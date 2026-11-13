"""Offline numeric audit; never changes package/game assets."""
import json,math,hashlib
from pathlib import Path
P=Path(r'D:/game design/experiment')
I=P/'Docs/Gameplay/PackSlashReview1104';O=P/'Docs/Gameplay/PackDIntegration1104';O.mkdir(exist_ok=True)
src=next(c for c in json.loads((I/'SourceMotion.json').read_text())['clips'] if c['name']=='Anim_CSATLI_04')
dst=next(c for c in json.loads((I/'CandidateMotion.json').read_text())['clips'] if c['name']=='Pack_Anim_CSATLI_04')
ratio=1.0886276993004262
grip=json.loads((I/'CaptureConfig.json').read_text(encoding='utf-8-sig'))['grip_override']
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def mul(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(v):return math.sqrt(dot(v,v))
def unit(v):return mul(v,1/norm(v)) if norm(v)>1e-8 else [0,0,0]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def rot(q,v):
    t=mul(cross(q[:3],v),2)
    return add(add(v,mul(t,q[3])),cross(q[:3],t))
def qdist(a,b):return math.degrees(2*math.acos(min(1,abs(dot(a,b))/(norm(a)*norm(b)))))
def forward(v):return [v[1]*ratio,-v[0]*ratio,0.0]
frames=[]
r0=forward(src['frames'][0]['bones']['root']['p'])
for i,f in enumerate(dst['frames']):
    root=sub(forward(src['frames'][i]['bones']['root']['p']),r0)
    h=f['bones']['RightHand'];q=h['q']
    origin=add(h['p'],rot(q,mul(grip['translation'],100)))
    def point(v):return add(origin,rot(q,rot(grip['quaternion_xyzw'],v)))
    edge=rot(q,rot(grip['quaternion_xyzw'],[-1,0,0]))
    row={'t':f['t'],'root':root,'hips':f['bones']['Hips']['p'],'hand':h['p'],'sword_origin':origin,
         'blade_root':point([0,0,9]),'mid':point([.7,0,39]),'tip':point([4.3,0,70.972]),'edge':edge}
    row.update({k+'_in_place':sub(row[k],root) for k in ['hips','hand','blade_root','mid','tip']})
    frames.append(row)
for i in range(1,len(frames)-1):
    p,f,n=frames[i-1:i+2];dt=n['t']-p['t']
    for k in ['root','hand','mid','tip','mid_in_place','tip_in_place']:
        v=mul(sub(n[k],p[k]),1/dt)
        f[k+'_velocity']=v;f[k+'_speed']=norm(v)
    f['mid_edge_cos']=dot(unit(f['mid_in_place_velocity']),f['edge'])
    f['tip_edge_cos']=dot(unit(f['tip_in_place_velocity']),f['edge'])
root_quats=[f['bones']['root']['q'] for f in src['frames']]
out={'source':src['name'],'duration_seconds':dst['duration'],'fps':30,'root_ratio':ratio,
     'source_root_start':src['frames'][0]['bones']['root']['p'],'source_root_end':src['frames'][-1]['bones']['root']['p'],
     'root_displacement_cm':frames[-1]['root'],'max_root_rotation_from_start_degrees':max(qdist(q,root_quats[0]) for q in root_quats),
     'hips_start_end_orientation_difference_degrees':qdist(dst['frames'][0]['bones']['Hips']['q'],dst['frames'][-1]['bones']['Hips']['q']),
     'hand_start_end_orientation_difference_degrees':qdist(dst['frames'][0]['bones']['RightHand']['q'],dst['frames'][-1]['bones']['RightHand']['q']),
     'hips_start':frames[0]['hips_in_place'],'hips_end':frames[-1]['hips_in_place'],'frames':frames}
(O/'DMotionAnalysis.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
recommendation={
    'source_clip':'/Game/Animations/Sword/Anim_CSATLI_04',
    'review_clip':dst['asset'],'duration':dst['duration'],'play_rate':1.0,
    'hit_window':[0.4,0.8],'hit_window_frames_30fps':[12,24],
    'telegraph_seconds':0.4,'attack_seconds':0.4,'recover_seconds':dst['duration']-0.8,
    'attack_range_cm':200.0,'original_ground_delta_cm':frames[-1]['root'],
    'source_ground_delta_cm':sub(src['frames'][-1]['bones']['root']['p'],src['frames'][0]['bones']['root']['p']),
    'source_to_native':{'yaw_degrees':-90,'uniform_translation_ratio':ratio},
    'root_rotation_max_delta_degrees':out['max_root_rotation_from_start_degrees'],
    'root_motion_method':'Copy the complete source ground-root path through coordinate/height conversion into an absolute-time curve. Subtract that same path from gameplay Hips; collision-swept actor capsule supplies the movement.',
    'evidence':[
        'Main cutting arc: t=.333-.767s, native pelvis-relative blade-mid speed 331-969-563cm/s. Cutting-edge/velocity cosine is strongly positive during the descending sweep and approaches zero at .767s.',
        'The blade crosses into the forward target at approximately .70-.80s. At .767s the capsule path is +129.8cm and tip is +78.2cm forward, +12.0cm lateral, 51.9cm high in capsule-ground coordinates. A 200cm initial target separation lies inside the blade sweep plus target radius.',
        'At .833-.933s the blade rapidly returns upward; edge/velocity alignment is negative. This recovery must not damage. Later motion is slower guard recovery and footsteps, not another equivalent strike.',
        'Source root has no rotation. Complete authored translation is +284.695cm in native forward; do not let visible Hips drift that far away from the collision capsule.',
        'D starts in a combo entry pose: Hips first/last rotation differs by 140.153 degrees. Its full source motion remains approved, but the actual idle-to-D blend needs visual inspection in live combat.'
    ],
    'phase_bounds':{'entry_and_telegraph':[0.0,0.4],'active_cut':[0.4,0.8],'blade_return':[0.8,1.0],'guard_and_footstep_recovery':[1.0,dst['duration']]},
    'integration_checks':[
        'Use the same animation time and playback rate for root curve and native hit window.',
        'Lock attack travel direction at commitment; do not steer the whole curve after the player moves.',
        'Block and drop attempted root deltas at collision instead of accumulating a later teleport.',
        'Verify death, stagger, pause, reset and interrupted blend clear or suspend root travel.',
        'Check the native window and real blade sweep against a target at approximately 200cm; this offline path analysis is not collision validation.',
        'Review the 140-degree entry pose blend before final delivery; do not silently truncate the selected source action.'
    ],
    'sampled_phase_frames':[{k:f[k] for k in ['t','root','hips_in_place','blade_root_in_place','mid_in_place','tip_in_place']} for f in [frames[0],frames[12],frames[16],frames[21],frames[23],frames[24],frames[30],frames[-1]]]
}
(O/'TimingRecommendation.json').write_text(json.dumps(recommendation,ensure_ascii=False,indent=2),encoding='utf-8')
c_asset='/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/PackSlashCandidates/V3/Pack_Anim_CSATLI_03'
c_file=P/'Content'/(c_asset.removeprefix('/Game/')+'.uasset')
selection={
    'user_choice_date':'2026-11-04',
    'current_enemy':{'candidate':'D','source_clip':'/Game/Animations/Sword/Anim_CSATLI_04','review_asset':dst['asset'],'status':'selected_for_gameplay_integration','grip':'forward grip; fixed package-to-native binding validated in comparison'},
    'reserved_for_future_enemy':{'candidate':'C','source_clip':'/Game/Animations/Sword/Anim_CSATLI_03','review_asset':c_asset,'reverse_grip_required':True,'status':'retained, not assigned to current enemy','grip_note':'User explicitly requires reverse grip for enemies using C. Do not treat a 180-degree cutting-edge roll as equivalent to reverse grip. Grip, blade sweep and native hit window must be validated when that later enemy is integrated.','asset_sha256_at_selection':hashlib.sha256(c_file.read_bytes()).hexdigest()},
    'animation_library':{'source_package':'3583AnimationsPack','source_sword_folder':'/Game/Animations/Sword','retain_for_later_enemy_design':True,'retargeted_candidates_folder':'/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/PackSlashCandidates/V3','originals_unchanged':True},
    'scope':'Selection record only. C and the original motion pack are retained unchanged; this file does not claim D gameplay assignment has finished.'
}
(O/'Selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='frames'},indent=2))
print(' t   rootX    tipLocalXYZ      bladeMidSpeed  edgeCos  rootSpeed')
for f in frames[1:-1]:
    if .3<=f['t']<=2.05:
        print('%5.3f %7.1f [%6.1f %6.1f %6.1f] %7.1f %6.2f %7.1f' % (f['t'],f['root'][0],*f['tip_in_place'],f['mid_in_place_speed'],f['mid_edge_cos'],f['root_speed']))
