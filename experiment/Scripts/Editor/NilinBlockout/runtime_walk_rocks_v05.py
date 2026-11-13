"""Walk the three ranged rock outcrops with actual PIE CharacterMovement.

One initial placement per station, then follow its complete access route to
both enemy feet and retrace it to the main-route rest. No teleport, collision
override, flight or movement-mode change is used during each walking circuit.
This is a local regression, not a full-level or combat/VR acceptance test.
"""
import json
import math
import os
import time
import traceback

import unreal


BASE = r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05'
OUT = os.path.join(BASE, 'RockRefinement')
MAP = '/Game/ReversedScale/Maps/L_NilinBlockoutV10'
TIMEOUT_SECONDS = 180
os.makedirs(OUT, exist_ok=True)
spec_path = os.path.join(BASE, 'LayoutSpec.json')
with open(spec_path, encoding='utf-8') as source:
    data = json.load(source)
if data.get('map') != MAP:
    raise RuntimeError('Rock walk requires the saved V10 layout')
if not unreal.EditorAssetLibrary.does_asset_exist(MAP):
    raise RuntimeError('V10 map is not saved')
stations = data.get('ranged_encounters', {}).get('stations', [])
if len(stations) != 3 or len({s['id'] for s in stations}) != 3:
    raise RuntimeError('Expected exactly three distinct ranged rock stations')

level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
began = time.monotonic()
last_tick = began
active_began = began
last = began
progress = began
phase = 0
busy = False
handle = None
pawn = None
movement = None
owns_play = False
finished = False
station_index = 0
index = 0
best = float('inf')
report = {
    'kind': 'Actual PIE CharacterMovement ranged-rock access regression',
    'map': MAP,
    'source_layout': spec_path,
    'state': 'starting',
    'success': False,
    'stations': [],
    'completed_stations': 0,
    'waypoints_reached': 0,
    'initial_teleport_count': 0,
    'teleports_during_walk': 0,
    'timeout_active_seconds': TIMEOUT_SECONDS,
    'failures': [],
    'limitations': [
        'Covers only the three ranged side routes, both enemy feet at each station, and the return paths.',
        'Each station has one explicit setup teleport to its main-route rest; the three stations are separate walking circuits.',
        'Every circuit uses the actual possessed character and ordinary CharacterMovement collision.',
        'No attack AI, damage, full-level traversal, VR input or headset performance is tested.',
    ],
}


def save():
    with open(os.path.join(OUT, 'RuntimeWalkRocks.json'), 'w', encoding='utf-8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)


def vec(point):
    return unreal.Vector(*[value * 100 for value in point])


def unique_append(points, point):
    point = list(point)
    if not points or math.dist(points[-1], point) > .01:
        points.append(point)


for station in stations:
    outward = []
    unique_append(outward, station['route_rest'])
    for point in station['access_route']:
        unique_append(outward, point)
    enemies = station.get('enemies', [])
    if len(enemies) != 2:
        raise RuntimeError(station['id'] + ' must contain two enemy foot targets')
    # Existing routes already include both feet. Retain that route order rather
    # than introducing an unnecessary reverse zig-zag on the raised surface.
    for enemy in enemies:
        if not any(math.dist(enemy['foot'], point) < .01 for point in outward):
            unique_append(outward, enemy['foot'])
    targets = outward[1:] + list(reversed(outward[:-1]))
    report['stations'].append({
        'id': station['id'],
        'state': 'pending',
        'initial_ground_m': station['route_rest'],
        'outward_waypoints_m': outward,
        'waypoints_m': targets,
        'total_waypoints': len(targets),
        'waypoints_reached': 0,
        'enemy_feet_m': {enemy['id']: enemy['foot'] for enemy in enemies},
        'enemy_feet_reached': [],
        'initial_teleport_count': 0,
        'teleports_during_walk': 0,
        'returned_to_rest': False,
    })
report['total_waypoints'] = sum(s['total_waypoints'] for s in report['stations'])


def finish(error=None):
    global handle, pawn, movement, finished
    if finished:
        return
    finished = True
    if error:
        report['failures'].append(error)
        if station_index < len(report['stations']):
            report['stations'][station_index]['state'] = 'failed'
    complete = all(s['state'] == 'passed' for s in report['stations'])
    report['success'] = complete and not report['failures']
    report['state'] = 'passed' if report['success'] else 'failed'
    report['elapsed_seconds'] = time.monotonic() - began
    report['active_elapsed_seconds'] = time.monotonic() - active_began
    save()
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        handle = None
    if movement is not None:
        movement.stop_movement_immediately()
    # Persistent review-worker namespaces must not retain a PIE pawn or UWorld.
    pawn = None
    movement = None
    if owns_play:
        level.editor_request_end_play()


def tick(delta):
    global phase, busy, last, index, pawn, movement, progress, best
    global last_tick, active_began, station_index, owns_play
    if busy or finished:
        return
    busy = True
    try:
        now = time.monotonic()
        gap = now - last_tick
        last_tick = now
        if gap > 2:
            # Exclude editor/render stalls from movement-stall and active-time
            # limits, but retain the unadjusted elapsed time in the report.
            report.setdefault('editor_stalls_seconds', []).append(round(gap, 2))
            active_began += gap
            last += gap
            progress += gap
        if now - active_began > TIMEOUT_SECONDS:
            finish({'error': 'Ranged rock regression timeout', 'station_index': station_index})
            return
        if phase == 0:
            if editor.get_game_world():
                finish({'error': 'Stop the existing PIE session before running this regression'})
                return
            if not editor.get_editor_world().get_path_name().startswith(MAP + '.'):
                if not level.load_level(MAP):
                    finish({'error': 'Cannot load V10'})
                    return
            level.editor_request_begin_play()
            owns_play = True
            phase = 1
            last = now
            return
        if phase == 1:
            world = editor.get_game_world()
            if not world or now - last < 2:
                return
            if MAP.rsplit('/', 1)[-1] not in world.get_path_name():
                finish({'error': 'Unexpected PIE map'})
                return
            pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
            if not pawn:
                if now - last > 30:
                    finish({'error': 'No possessed PIE pawn'})
                return
            report['pawn_class'] = pawn.get_class().get_path_name()
            if 'NLBlockoutCharacter' not in report['pawn_class']:
                finish({'error': 'Unexpected game pawn'})
                return
            movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
            if not movement:
                finish({'error': 'Pawn lacks CharacterMovement'})
                return
            unreal.SystemLibrary.execute_console_command(world, 't.IdleWhenNotForeground 0')
            unreal.SystemLibrary.execute_console_command(world, 'Slate.bAllowThrottling 0')
            unreal.GameplayStatics.set_game_paused(world, False)
            phase = 2
        if phase == 2:
            if station_index == len(report['stations']):
                finish()
                return
            current = report['stations'][station_index]
            ground = current['initial_ground_m']
            # The only actor relocation in this script: one setup per station.
            pawn.set_actor_location(vec((ground[0], ground[1], ground[2] + .94)), False, True)
            current['initial_teleport_count'] += 1
            report['initial_teleport_count'] += 1
            movement.stop_movement_immediately()
            movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
            current['state'] = 'settling'
            index = 0
            last = now
            phase = 3
            save()
            return
        current = report['stations'][station_index]
        if phase == 3 and now - last > .8:
            ground = current['initial_ground_m']
            loc = pawn.get_actor_location()
            smoke = {
                'location_m': [loc.x / 100, loc.y / 100, loc.z / 100],
                'grounded': movement.is_moving_on_ground(),
                'height_error_cm': loc.z - ground[2] * 100 - 90,
            }
            current['start_smoke'] = smoke
            if not smoke['grounded'] or abs(smoke['height_error_cm']) > 8:
                finish({'error': 'Station start is not grounded', 'station': current['id'], 'smoke': smoke})
                return
            movement.stop_movement_immediately()
            current['state'] = 'walking'
            report['state'] = 'walking'
            progress = now
            best = float('inf')
            phase = 4
            save()
        if phase == 4:
            targets = current['waypoints_m']
            if index == len(targets):
                movement.stop_movement_immediately()
                if set(current['enemy_feet_reached']) != set(current['enemy_feet_m']):
                    finish({'error': 'Not all enemy feet were reached', 'station': current['id']})
                    return
                if not movement.is_moving_on_ground():
                    finish({'error': 'Return endpoint is not grounded', 'station': current['id']})
                    return
                current['returned_to_rest'] = True
                current['state'] = 'passed'
                loc = pawn.get_actor_location()
                current['return_location_m'] = [loc.x / 100, loc.y / 100, loc.z / 100]
                report['completed_stations'] += 1
                station_index += 1
                phase = 2
                save()
                return
            target = targets[index]
            loc = pawn.get_actor_location()
            dx = target[0] * 100 - loc.x
            dy = target[1] * 100 - loc.y
            distance = math.hypot(dx, dy)
            enemy_ids = [enemy_id for enemy_id, foot in current['enemy_feet_m'].items()
                         if math.dist(target, foot) < .01]
            tolerance = 35 if enemy_ids or index == len(targets) - 1 else 55
            if distance < tolerance and abs(loc.z / 100 - .90 - target[2]) < .5:
                for enemy_id in enemy_ids:
                    if enemy_id not in current['enemy_feet_reached']:
                        current['enemy_feet_reached'].append(enemy_id)
                index += 1
                current['waypoints_reached'] = index
                report['waypoints_reached'] += 1
                progress = now
                best = float('inf')
                if index % 5 == 0:
                    save()
                return
            if distance < best - 10:
                best = distance
                progress = now
            if now - progress > 6:
                finish({
                    'error': 'Character movement stalled', 'station': current['id'],
                    'waypoint': index, 'target_m': target,
                    'position_m': [loc.x / 100, loc.y / 100, loc.z / 100],
                    'distance_cm': distance,
                    'movement_mode': str(movement.get_editor_property('movement_mode')),
                })
                return
            if loc.z < target[2] * 100 - 250:
                finish({'error': 'Character fell below route', 'station': current['id'],
                        'waypoint': index, 'target_m': target,
                        'position_m': [loc.x / 100, loc.y / 100, loc.z / 100]})
                return
            if distance > .001:
                pawn.add_movement_input(unreal.Vector(dx / distance, dy / distance, 0), 1.0, True)
    except Exception:
        finish({'error': traceback.format_exc(), 'station_index': station_index})
    finally:
        busy = False


handle = unreal.register_slate_post_tick_callback(tick)
save()
