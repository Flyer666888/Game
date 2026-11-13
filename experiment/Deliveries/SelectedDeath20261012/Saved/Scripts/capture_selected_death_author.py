"""Observe a naturally played authoring animation after shaders stabilize.

Replays only the plain SkeletalMeshActor, records natural clip positions, and
captures five frames. It never sends input or invokes gameplay combat.
"""
import json
import time
from pathlib import Path
import unreal

_death_author_out = Path(unreal.Paths.project_dir()) / 'Docs/AI'
_death_author_start = time.monotonic()
_death_author_handle = None
_death_author_mesh = None
_death_author_actor = None
_death_author_camera = None
_death_author_initialized = False
_death_author_replayed = False
_death_author_first_frame_pending = False
_death_author_targets = []
_death_author_rows = []

def _death_author_vector(value):
    return [value.x, value.y, value.z]

def _death_author_world():
    return unreal.find_object(None, '/Game/ReversedScale/Maps/L_DeathAuthorPreview.L_DeathAuthorPreview')

def _death_author_write():
    report = {'date': '2026-10-12', 'map': '/Game/ReversedScale/Maps/L_DeathAuthorPreview',
              'actor': _death_author_actor.get_path_name(),
              'mesh': _death_author_mesh.get_editor_property('skeletal_mesh_asset').get_path_name(),
              'animation': _death_author_mesh.get_editor_property('animation_data').get_editor_property('anim_to_play').get_path_name(),
              'grip_morph': 'EnemyGrip_R', 'grip_weight': 1.0, 'frames': _death_author_rows,
              'scope': 'Natural single-node animation authoring presentation, independent of combat. Screenshot requests may render on the following engine frame.'}
    (_death_author_out / 'SelectedDeathAuthorPreviewRuntime.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

def _death_author_capture(delta):
    global _death_author_mesh, _death_author_actor, _death_author_camera
    global _death_author_initialized, _death_author_replayed, _death_author_first_frame_pending
    world = _death_author_world()
    if not world:
        return
    if not _death_author_initialized:
        visuals = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SkeletalMeshActor)
                   if actor.actor_has_tag('NL_DeathAuthorPreview')]
        cameras = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CameraActor)
                   if actor.actor_has_tag('NL_DeathAuthorCamera')]
        if not visuals or not cameras:
            return
        _death_author_actor = visuals[0]
        _death_author_mesh = _death_author_actor.get_component_by_class(unreal.SkeletalMeshComponent)
        _death_author_camera = cameras[0]
        _death_author_mesh.set_morph_target('EnemyGrip_R', 1.0)
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        if controller:
            controller.set_view_target_with_blend(_death_author_camera, 0.0)
        _death_author_initialized = True
    if time.monotonic() - _death_author_start < 20.0:
        return
    if not _death_author_replayed:
        animation = _death_author_mesh.get_editor_property('animation_data').get_editor_property('anim_to_play')
        duration = float(animation.get_play_length())
        _death_author_targets.extend([(0.0, 'Start'), (0.8, 'BalanceLost'),
                                     (1.65, 'FirstFall'), (2.2, 'Relaxing'),
                                     (duration, 'FinalHold')])
        _death_author_mesh.set_morph_target('EnemyGrip_R', 1.0)
        _death_author_mesh.set_position(0.0, False)
        _death_author_mesh.play(False)
        _death_author_replayed = True
        _death_author_first_frame_pending = True
        unreal.log('SELECTED_DEATH_AUTHOR_NATURAL_REPLAY_STARTED')
        return
    if _death_author_first_frame_pending:
        # The replay begins on the previous callback. Wait for the next normal
        # skeletal animation update before requesting the standing photograph.
        _death_author_first_frame_pending = False
    if not _death_author_targets:
        return
    requested, label = _death_author_targets[0]
    position = float(_death_author_mesh.get_position())
    # A non-looping clip can end one rounding unit below its nominal duration.
    if position + 0.002 < requested:
        return
    image = _death_author_out / ('SelectedDeathAuthor_' + label + '.png')
    row = {'label': label, 'requested_clip_seconds': requested,
           'observed_clip_seconds': position, 'image': str(image),
           'mesh_world_cm': _death_author_vector(_death_author_mesh.get_world_location()),
           'head_world_cm': _death_author_vector(_death_author_mesh.get_socket_location('head')),
           'right_hand_world_cm': _death_author_vector(_death_author_mesh.get_socket_location('hand_r'))}
    _death_author_rows.append(row)
    _death_author_write()
    unreal.SystemLibrary.execute_console_command(world,
        'HighResShot 1200x1200 filename="' + str(image).replace('\\', '/') + '"')
    unreal.log('SELECTED_DEATH_AUTHOR_FRAME ' + label + ' ' + str(position))
    _death_author_targets.pop(0)
    if not _death_author_targets:
        unreal.unregister_slate_post_tick_callback(_death_author_handle)
        unreal.log('SELECTED_DEATH_AUTHOR_CAPTURE_COMPLETE')

_death_author_handle = unreal.register_slate_post_tick_callback(_death_author_capture)
unreal.log('SELECTED_DEATH_AUTHOR_CAPTURE_REGISTERED')
