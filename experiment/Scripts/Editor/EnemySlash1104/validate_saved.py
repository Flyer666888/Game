"""Read saved enemy defaults and combat data in a fresh editor process."""
import json
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
out = project / 'Docs/Gameplay/EnemySlash1104'
report = json.loads((out / 'AssetChanges.json').read_text(encoding='utf-8'))
assets = unreal.EditorAssetLibrary
animation = assets.load_asset(report['clip'])
assert abs(animation.get_play_length() - 1.5) < 0.001
phases = ('telegraph_seconds', 'attack_seconds', 'recover_seconds')
for row in report['enemies']:
    path = '/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_' + row['enemy']
    default = unreal.get_default_object(assets.load_blueprint_class(path))
    assert default.get_editor_property('attack_animation') == animation, path
    brain = default.get_enemy_brain()
    assert all(abs(brain.get_editor_property(prop) - target) < 0.001
               for prop, target in zip(phases, row['after_seconds'])), path
for row in report['damage']:
    definition = assets.load_asset('/Game/ReversedScale/Combat/' + row['definition'])
    assert definition.get_editor_property('damage') == row['after'], row['definition']
notify_library = unreal.AnimationLibrary
notifies = [event for track in notify_library.get_animation_notify_track_names(animation)
            for event in notify_library.get_animation_notify_events_for_track(animation, track)]
assert len(notifies) == 1
event = notifies[0]
assert isinstance(event.get_editor_property('notify_state_class'), unreal.NLEnemyAttackWindowNotifyState)
start = notify_library.get_anim_notify_event_trigger_time(event)
end = start + notify_library.get_anim_notify_event_duration(event)
assert abs(start - 0.6) < 0.002 and abs(end - 25 / 30) < 0.002
(out / 'SavedVerification.json').write_text(json.dumps({'success': True, 'enemies': len(report['enemies']),
    'damage_assets': len(report['damage']), 'notify_seconds': [start, end]}, indent=2), encoding='utf-8')
